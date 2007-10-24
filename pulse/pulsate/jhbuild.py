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
    if modulesets.has_key (file):
        return modulesets[file]
    modulesets[file] = {'__dom__' : xml.dom.minidom.parse (file)}
    def proc_element (node):
        if node.tagName == 'repository':
            modulesets[file].setdefault ('__repos__', {})
            if node.hasAttribute ('name'):
                modulesets[file]['__repos__'][node.getAttribute ('name')] = node
            if node.getAttribute ('default') == 'yes':
                modulesets[file]['__repos__']['__default__'] = node
        else:
            if node.hasAttribute ('id'):
                modulesets[file][node.getAttribute ('id')] = node
            for child in node.childNodes:
                if child.nodeType == child.ELEMENT_NODE:
                    proc_element (child)
    proc_element (modulesets[file]['__dom__'].documentElement)
    return modulesets[file]

def update_branch (moduleset, key, update=True):
    node = moduleset[key]
    if node.tagName != 'autotools':
        return None
    for branch in node.childNodes:
        if branch.nodeType == branch.ELEMENT_NODE and branch.tagName == 'branch':
            break
    if branch.nodeType != branch.ELEMENT_NODE or branch.tagName != 'branch':
        return None
    if branch.hasAttribute ('repo'):
        repo = moduleset['__repos__'][branch.getAttribute ('repo')]
    else:
        repo = moduleset['__repos__']['__default__']

    data = {}
    data['scm_type'] = repo.getAttribute ('type')

    if data['scm_type'] == 'cvs':
        data['scm_server'] = repo.getAttribute ('cvsroot')
    else:
        data['scm_server'] = repo.getAttribute ('href')

    if branch.hasAttribute ('module'):
        data['scm_module'] = branch.getAttribute ('module')
    else:
        data['scm_module'] = key

    if branch.hasAttribute ('revision'):
        data['scm_branch'] = branch.getAttribute ('revision')
    else:
        data['scm_branch'] = pulse.scm.default_branches.get(data['scm_type'])

    if branch.hasAttribute ('checkoutdir'):
        data['module_dir'] = branch.getAttribute ('checkoutdir')

    ident = '/mod/' + repo.getAttribute ('name') + '/' + data['scm_module'] + '/' + data['scm_branch']

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
            for node in moduleset['__dom__'].getElementsByTagName ('autotools'):
                packages.append (node.getAttribute ('id'))
        else:
            modules = data['jhbuild_metamodule']
            if isinstance (modules, basestring):
                modules = [modules]

            for module in modules:
                if not moduleset.has_key (module):
                    continue
                node = moduleset[module]
                if node.tagName != 'metamodule':
                    continue
                for deps in node.childNodes:
                    if deps.nodeType == deps.ELEMENT_NODE and deps.tagName == 'dependencies':
                        break
                for child in deps.childNodes:
                    if child.nodeType == child.ELEMENT_NODE and child.tagName == 'dep':
                        if not child.hasAttribute ('package'):
                            continue
                        pkg = child.getAttribute ('package')
                        if moduleset.has_key (pkg) and moduleset[pkg].tagName != 'metamodule':
                            packages.append (pkg)

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
