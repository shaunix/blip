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

    scm_data = {}
    scm_data['scm_type'] = repo.getAttribute ('type')
    if scm_data['scm_type'] == 'cvs':
        scm_data['scm_server'] = repo.getAttribute ('cvsroot')
    else:
        scm_data['scm_server'] = repo.getAttribute ('href')
    scm_data['scm_module'] = key
    if branch.hasAttribute ('revision'):
        scm_data['scm_branch'] = branch.getAttribute ('revision')

    checkout = pulse.scm.Checkout(checkout=False, update=False, **scm_data)
    scm_data['scm_branch'] = checkout.scm_branch

    m_ident = '/mod/' + repo.getAttribute ('name') + '/' + key
    b_ident = m_ident + '/' + scm_data['scm_branch']

    m_res = pulse.db.Resource.make (ident=m_ident, type='Module')
    b_res = pulse.db.Resource.make (ident=b_ident, type='Branch')

    m_data = b_data = {}

    for key in ('scm_type', 'scm_server', 'scm_module'):
        m_data[key] = b_data[key] = scm_data[key]
    b_data['scm_branch'] = scm_data['scm_branch']

    m_res.update (m_data)
    b_res.update (b_data)

    b_res.parent = m_res

    return b_res

def update_set (data, update=True):
    ident = '/set/' + data['id']
    res = pulse.db.Resource.selectBy (ident=ident)
    if res.count() > 0:
        res = res[0]
    else:
        res = pulse.db.Resource (ident=ident, type='Set')

    if data.has_key ('set'):
        for subset in data['set'].keys():
            subres = update_set (data['set'][subset], update=update)
            pulse.db.Relation.make (res, pulse.db.Relation.set_subset, subres)

    if (data.has_key ('jhbuild_scm_type')   and
        data.has_key ('jhbuild_scm_server') and
        data.has_key ('jhbuild_scm_module') and
        data.has_key ('jhbuild_scm_branch') and
        data.has_key ('jhbuild_scm_dir')    and
        data.has_key ('jhbuild_scm_file')   and
        data.has_key ('jhbuild_metamodule') ):

        ident = '/' + '/'.join (['jhbuild',
                                 data['jhbuild_scm_type'],
                                 data['jhbuild_scm_server'],
                                 data['jhbuild_scm_module'],
                                 data['jhbuild_scm_branch']])
        if checkouts.has_key (ident):
            checkout = checkouts[ident]
        else:
            checkout = pulse.scm.Checkout (scm_type=data['jhbuild_scm_type'],
                                           scm_server=data['jhbuild_scm_server'],
                                           scm_module=data['jhbuild_scm_module'],
                                           scm_branch=data['jhbuild_scm_branch'],
                                           update=update)
            checkouts[ident] = checkout
        file = os.path.join (checkout.directory,
                             data['jhbuild_scm_dir'],
                             data['jhbuild_scm_file'])
        moduleset = get_moduleset (file)

        modules = data['jhbuild_metamodule']
        if isinstance (modules, basestring):
            modules = [modules]

        packages = []

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
                pulse.db.Relation.make (res, pulse.db.Relation.set_branch, branch)

    return res

def main (argv, options={}):
    update = not options.get ('--no-update', False)

    data = pulse.xmldata.get_data (os.path.join (pulse.config.datadir, 'xml', 'sets.xml'))

    for key in data.keys():
        if data[key]['__type__'] == 'set':
            update_set (data[key], update=update)
