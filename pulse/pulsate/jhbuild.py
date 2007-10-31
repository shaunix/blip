# Copyright (c) 2006  Shaun McCance  <shaunm@gnome.org>
#
# This file is part of Pulse, a program for displaying various statistics
# of questionable relevance about software and the people who make it.
#
# Pulse is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# Pulse is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along
# with Pulse; if not, write to the Free Software Foundation, 59 Temple Place,
# Suite 330, Boston, MA  0211-1307  USA.
#

import os
import sys

import xml.dom.minidom

import pulse.db
import pulse.scm
import pulse.xmldata

synop = 'update information from Gnome\'s jhbuild module'
args = pulse.utils.odict()
args['no-update']  = (None, 'do not update SCM checkouts')

modulesets = {}
checkouts = {}

def get_moduleset (file):
    if not modulesets.has_key (file):
        modulesets[file] = ModuleSet (file)
    return modulesets[file]

class ModuleSet:
    def __init__ (self, file):
        self._packages = {}
        self._metas = {}
        self.parse (file)

    def get_packages (self):
        return self._packages.keys()

    def has_package (self, key):
        return self._packages.has_key (key)

    def get_package (self, key):
        return self._packages[key]

    def get_metamodules (self):
        return self._metas.keys()

    def has_metamodule (self, key):
        return self._metas.has_key (key)

    def get_metamodule (self, key):
        return self._metas[key]

    def parse (self, file):
        dom = xml.dom.minidom.parse (file)
        repos = {}
        default_repo = None
        for node in dom.documentElement.childNodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue
            if node.tagName == 'repository':
                repo_data = {}
                repo_data['scm_type'] = node.getAttribute ('type')
                if repo_data['scm_type'] == 'cvs':
                    repo_data['scm_server'] = node.getAttribute ('cvsroot')
                else:
                    repo_data['scm_server'] = node.getAttribute ('href')
                repo_data['repo_name'] = node.getAttribute ('name')
                if node.hasAttribute ('name'):
                    repos[node.getAttribute ('name')] = repo_data
                if node.getAttribute ('default') == 'yes':
                    default_repo = repo_data
            elif node.tagName == 'autotools':
                pkg_data = {'id' : node.getAttribute ('id')}
                for branch in node.childNodes:
                    if branch.nodeType == branch.ELEMENT_NODE and branch.tagName == 'branch':
                        if branch.hasAttribute ('repo'):
                            repo_data = repos.get (branch.getAttribute ('repo'), None)
                        else:
                            repo_data = default_repo
                        if repo_data != None:
                            pkg_data['scm_type'] = repo_data['scm_type']
                            pkg_data['scm_server'] = repo_data['scm_server']
                        if branch.hasAttribute ('module'):
                            pkg_data['scm_path'] = branch.getAttribute ('module')
                            if branch.hasAttribute ('checkoutdir'):
                                pkg_data['scm_module'] = branch.getAttribute ('checkoutdir')
                            else:
                                pkg_data['scm_module'] = pkg_data['id']
                        else:
                            pkg_data['scm_module'] = pkg_data['id']
                        if branch.hasAttribute ('revision'):
                            pkg_data['scm_branch'] = branch.getAttribute ('revision')
                        else:
                            pkg_data['scm_branch'] = pulse.scm.default_branches.get(pkg_data['scm_type'])
                        break
                if pkg_data.has_key ('scm_type'):
                    self._packages[pkg_data['id']] = pkg_data
            elif node.tagName == 'metamodule':
                meta = []
                for deps in node.childNodes:
                    if deps.nodeType == deps.ELEMENT_NODE and deps.tagName == 'dependencies':
                        for dep in deps.childNodes:
                            if dep.nodeType == dep.ELEMENT_NODE and dep.tagName == 'dep':
                                meta.append (dep.getAttribute ('package'))
                        break
                self._metas[node.getAttribute ('id')] = meta
            elif node.tagName == 'include':
                self.parse (os.path.join (os.path.dirname (file), node.getAttribute ('href')))


def update_branch (moduleset, key, update=True):
    if not moduleset.has_package (key):
        return None
    pkg_data = moduleset.get_package (key)

    data = {}
    for k in pkg_data.keys():
        if k[:4] == 'scm_':
            data[k] = pkg_data[k]
    servername = pulse.scm.server_name (pkg_data['scm_type'], pkg_data['scm_server'])
    if servername == None:
        return None
    ident = '/'.join (['/mod', servername, pkg_data['scm_module'], pkg_data['scm_branch']])

    record = pulse.db.Branch.get_record (ident=ident, type='Module')
    record.update (data)
    return record

def update_set (data, update=True):
    ident = '/set/' + data['id']
    record = pulse.db.Record.get_record (ident=ident, type='Set')

    # Sets may contain either other sets or modules, not both
    if data.has_key ('set'):
        for subset in data['set'].keys():
            subrecord = update_set (data['set'][subset], update=update)
            pulse.db.RecordRelation.set_related (record, 'SetSubset', subrecord)
    elif (data.has_key ('jhbuild_scm_type')   and
          data.has_key ('jhbuild_scm_server') and
          data.has_key ('jhbuild_scm_module') and
          data.has_key ('jhbuild_scm_branch') and
          data.has_key ('jhbuild_scm_dir')    and
          data.has_key ('jhbuild_scm_file')):

        coid = '/'.join (['jhbuild',
                          data['jhbuild_scm_type'],
                          data['jhbuild_scm_server'],
                          data['jhbuild_scm_module'],
                          data['jhbuild_scm_branch']])
        if checkouts.has_key (coid):
            checkout = checkouts[coid]
        else:
            checkout = pulse.scm.Checkout (scm_type=data['jhbuild_scm_type'],
                                           scm_server=data['jhbuild_scm_server'],
                                           scm_module=data['jhbuild_scm_module'],
                                           scm_branch=data['jhbuild_scm_branch'],
                                           update=update)
            checkouts[coid] = checkout
        file = os.path.join (checkout.directory,
                             data['jhbuild_scm_dir'],
                             data['jhbuild_scm_file'])
        moduleset = get_moduleset (file)

        packages = []
        if not data.has_key ('jhbuild_metamodule'):
            packages = moduleset.get_packages()
        else:
            modules = data['jhbuild_metamodule']
            if isinstance (modules, basestring):
                modules = [modules]

            for module in modules:
                if not moduleset.has_metamodule (module):
                    continue
                packages += moduleset.get_metamodule (module)

        for pkg in packages:
            branch = update_branch (moduleset, pkg, update=update)
            if branch != None:
                pulse.db.RecordBranchRelation.set_related (record, 'SetModule', branch)

    return record

def main (argv, options={}):
    update = not options.get ('--no-update', False)

    data = pulse.xmldata.get_data (os.path.join (pulse.config.datadir, 'xml', 'sets.xml'))

    for key in data.keys():
        if data[key]['__type__'] == 'set':
            update_set (data[key], update=update)
