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

import pulse.models as db
import pulse.scm
import pulse.xmldata

synop = 'update information from Gnome\'s jhbuild module'
args = pulse.utils.odict()
args['no-deps'] = (None, 'do not check dependencies')
args['no-update']  = (None, 'do not update SCM checkouts')

modulesets = {}
checkouts = {}
records = {}

def get_moduleset (filename):
    if not modulesets.has_key (filename):
        modulesets[filename] = ModuleSet (filename)
    return modulesets[filename]

class ModuleSet:
    def __init__ (self, filename):
        self._packages = {}
        self._metas = {}
        self.filename = filename
        self.parse (filename)

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

    def parse (self, filename):
        base = os.path.basename (filename)
        dom = xml.dom.minidom.parse (filename)
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
                for child in node.childNodes:
                    if child.nodeType != child.ELEMENT_NODE:
                        continue
                    if child.tagName == 'branch':
                        if child.hasAttribute ('repo'):
                            repo_data = repos.get (child.getAttribute ('repo'), None)
                        else:
                            repo_data = default_repo
                        if repo_data != None:
                            pkg_data['scm_type'] = repo_data['scm_type']
                            pkg_data['scm_server'] = repo_data['scm_server']
                        if child.hasAttribute ('module'):
                            pkg_data['scm_path'] = child.getAttribute ('module')
                            if child.hasAttribute ('checkoutdir'):
                                pkg_data['scm_module'] = child.getAttribute ('checkoutdir')
                            else:
                                pkg_data['scm_module'] = pkg_data['id']
                        else:
                            pkg_data['scm_module'] = pkg_data['id']
                        if child.hasAttribute ('revision'):
                            pkg_data['scm_branch'] = child.getAttribute ('revision')
                        else:
                            pkg_data['scm_branch'] = pulse.scm.default_branches.get(pkg_data['scm_type'])
                    elif child.tagName == 'dependencies':
                        deps = []
                        for dep in child.childNodes:
                            if dep.nodeType == dep.ELEMENT_NODE and dep.tagName == 'dep':
                                deps.append (dep.getAttribute ('package'))
                        pkg_data['deps'] = deps
                if pkg_data.has_key ('scm_type'):
                    self._packages[pkg_data['id']] = pkg_data
                    self._metas.setdefault (base, [])
                    self._metas[base].append (pkg_data['id'])
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
                href = node.getAttribute ('href')
                if not href.startswith ('http:'):
                    self.parse (os.path.join (os.path.dirname (filename), href))


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

    record = db.Branch.get_record (ident, 'Module')
    record.update (data)
    record.save()
    pkg_data['__record__'] = record
    records.setdefault (record.ident, {'record' : record, 'pkgdatas' : []})
    # Records could have package information defined in multiple modulesets,
    # so we record all of them.  See the comment in update_deps.
    records[record.ident]['pkgdatas'].append ((moduleset, key))
    return record

def update_set (data, update=True, parent=None):
    ident = '/set/' + data['id']
    record = db.ReleaseSet.get_record (ident, 'Set')
    record.parent = parent

    if data.has_key ('name'):
        record.update (name=data['name'])

    if data.has_key ('links'):
        pulse.pulsate.update_links (record, data['links'])

    if data.has_key ('schedule'):
        pulse.pulsate.update_schedule (record, data['schedule'])

    # Sets may contain either other sets or modules, not both
    if data.has_key ('set'):
        rels = []
        for subset in data['set'].keys():
            subrecord = update_set (data['set'][subset], update=update, parent=record)
    elif (data.has_key ('module')):
        rels = []
        for xml_data in data['module'].values():
            mod_data = {}
            for k in xml_data.keys():
                if k[:4] == 'scm_':
                    mod_data[k] = xml_data[k]
            servername = pulse.scm.server_name (mod_data['scm_type'], mod_data['scm_server'])
            if servername == None:
                continue
            if mod_data.get ('scm_branch', '') == '':
                mod_data['scm_branch'] = pulse.scm.default_branches.get (mod_data['scm_type'])
            if mod_data.get ('scm_branch', '') == '':
                continue
            ident = '/'.join (['/mod', servername, mod_data['scm_module'], mod_data['scm_branch']])
            branch = db.Branch.get_record (ident, 'Module')
            if branch == None:
                continue
            branch.update (mod_data)
            rels.append (db.SetModule.set_related (record, branch))
            branch.save()
        record.set_relations (db.SetModule, rels)
    elif (data.has_key ('jhbuild_scm_type')   and
          data.has_key ('jhbuild_scm_server') and
          data.has_key ('jhbuild_scm_module') and
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
                                           scm_branch=data.get('jhbuild_scm_branch'),
                                           scm_path=data.get('jhbuild_scm_path'),
                                           update=update)
            checkouts[coid] = checkout
        filename = os.path.join (checkout.directory,
                                 data['jhbuild_scm_dir'],
                                 data['jhbuild_scm_file'])
        moduleset = get_moduleset (filename)

        packages = []
        if not data.has_key ('jhbuild_metamodule'):
            packages = moduleset.get_metamodule (os.path.basename (filename))
        else:
            modules = data['jhbuild_metamodule']
            if isinstance (modules, basestring):
                modules = [modules]

            for module in modules:
                if not moduleset.has_metamodule (module):
                    continue
                packages += moduleset.get_metamodule (module)

        rels = []
        for pkg in packages:
            branch = update_branch (moduleset, pkg, update=update)
            if branch != None:
                rels.append (db.SetModule.set_related (record, branch))
        record.set_relations (db.SetModule, rels)

    record.save()
    return record

def update_deps ():
    for ident, recdata in records.items():
        # Records could have package information defined in multiple modulesets.
        # If the jhbuild maintainers are on the ball, the dependencies in either
        # should be equivalent, except they might end up pointing to different
        # branches, as a result of what branches of other modules are included
        # in the particular moduleset.
        #
        # I toyed around with having dependencies go from Branch to Branchable,
        # which would make this a moot point, but it makes it difficult to do
        # dependency graphs, because you have to arbitrarily choose branches
        # of dependencies, and that could affect further dependencies.
        #
        # So we arbitrarity take the first moduleset.  It's probably a good
        # idea to keep newer modulesets first in sets.xml.
        moduleset, pkgkey = recdata['pkgdatas'][0]
        rec = recdata['record']
        pkgdata = moduleset.get_package (pkgkey)
        deps = get_deps (moduleset, pkgkey)
        pkgrels = []
        pkgdrels = []
        for dep in deps:
            depdata = moduleset.get_package (dep)
            if not depdata.has_key ('__record__'): continue
            deprec = depdata['__record__']
            rel = db.ModuleDependency.set_related (rec, deprec)
            pkgrels.append (rel)
            direct = (dep in pkgdata['deps'])
            if rel.direct != direct:
                rel.direct = direct
                rel.save()
        rec.set_relations (db.ModuleDependency, pkgrels)

known_deps = {}
def get_deps (moduleset, pkg, seen=[]):
    depskey = moduleset.filename + ':' + pkg
    if known_deps.has_key (depskey):
        return known_deps[depskey]
    pkgdata = moduleset.get_package (pkg)
    deps = []
    for dep in pkgdata.get('deps', []):
        # Prevent infinite loops for circular dependencies
        if dep in seen: continue
        if not moduleset.has_package (dep): continue
        depdata = moduleset.get_package (dep)
        if not dep in deps:
            deps.append (dep)
            for depdep in get_deps (moduleset, dep, seen + [pkg]):
                if not depdep in deps:
                    deps.append (depdep)
    known_deps[depskey] = deps
    return deps

def main (argv, options={}):
    update = not options.get ('--no-update', False)

    data = pulse.xmldata.get_data (os.path.join (pulse.config.input_dir, 'xml', 'sets.xml'))

    for key in data.keys():
        if data[key]['__type__'] == 'set':
            update_set (data[key], update=update)

    if not options.get ('--no-deps', False):
        update_deps ()