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

import pulse.config as config
import pulse.db as db
import pulse.html as html
import pulse.utils as utils

import pulse.pages.docs

def main (path=[], query={}, http=True, fd=None):
    if len(path) == 1:
        modules = db.Module.select ()
        print_modules (modules, path, query, http=http, fd=fd)
    elif len(path) == 2:
        modules = db.Module.select (db.Module.q.ident == 'modules/' + path[1])
        if modules.count() == 0:
            kw = {'http': http}
            kw['title'] = 'Module Not Found'
            kw['pages'] = [('modules', 'All Modules')]
            page = html.PageNotFound (
                'Could not find the module "%s"' % path[1],
                **kw)
            page.output(fd=fd)
            return 404
        else:
            print_modules (modules, path, query, title=modules[0].name, http=http, fd=fd)
    else:
        branch = db.Branch.select (db.Branch.q.ident == 'modules/%s/%s' % (path[1], path[2]))
        if branch.count() == 0:
            kw = {'http': http}
            kw['title'] = 'Branch Not Found'
            kw['pages'] = [('modules', 'All Modules')]
            module = db.Module.select (db.Module.q.ident == 'modules/' + path[1])
            if module.count() > 0:
                module = module[0]
                kw['pages'].insert (0, (module.ident, module.name))
            page = html.PageNotFound ('Could not find the branch "%s"' % path[1],
                                      **kw)
            page.output(fd=fd)
            return 404
        else:
            branch = branch[0]
            print_branch (branch, path, query, http=http, fd=fd)
    return 0


def print_modules (modules, path=[], query={}, title='Modules', http=True, fd=None):
    kw = {'http': http, 'title': title}

    page = html.Page (**kw)

    moduled = {}
    for module in modules:
        moduled[module.name] = module
    for key in utils.isorted (moduled.keys()):
        module = moduled[key]
        syn = get_synopsis (module)
        page.add (syn)

    page.output(fd=fd)

def print_branch (branch, path=[], query={}, http=True, fd=None):
    kw = {'http': http}

    module = branch.module
    kw['title'] = '%s (%s)' % (module.name, branch.name)

    page = html.Page (**kw)
    syn = html.SynopsisDiv (module)
    page.add (syn)
    tab = html.TabbedDiv ()
    page.add (tab)

    docs = db.Document.select (db.Document.q.branchID == branch.id)
    if docs.count() > 0:
        block = html.Block ()
        tab.add_tab ('docs', 'Documents', block)
        docd = {}
        for doc in docs:
            docd[doc.name] = doc
        for key in utils.isorted (docd.keys()):
            doc = docd[key]
            sum = pulse.pages.docs.get_summary (doc)
            block.add (sum)
    
    domains = db.Domain.select (db.Domain.q.branchID == branch.id)
    if domains.count() > 0:
        block = html.Block ()
        tab.add_tab ('i18n', 'Domains', block)
        domaind = {}
        for domain in domains:
            domaind[domain.name] = domain
        for key in utils.isorted (domaind.keys()):
            domain = domaind[key]
            sum = html.SummaryDiv (domain)
            block.add (sum)

    page.output(fd=fd)

def get_synopsis (module):
    syn = html.SynopsisDiv (module)

    branches = db.Branch.select (db.Branch.q.moduleID == module.id)
    branchd = {}
    for branch in branches:
        branchd[branch.name] = branch.ident
    for branch in utils.isorted (branchd.keys()):
        syn.add_sublink (config.webroot (branchd[branch]), branch)

    devs = module.developers
    affils = {}
    for dev in devs:
        affild = {'href': config.webroot (dev.resource.ident)}
        affild['name'] = dev.resource.name
        if dev.comment == 'maintainer':
            affild['comment'] = '(Maintainer)'
        else:
            affild['comment'] = None
        affils[dev.resource.name] = affild
    for key in utils.isorted (affils.keys()):
        syn.add_affiliation ('Developers', **affils[key])

    syn.add_graph ('Commit Activity', None,
                   '%sgraphs/%s/rcs.png' % (config.webroot, module.ident),
                   'Commit Activity for %s' % module.name)
    if len (module.mail_lists) > 0:
        syn.add_graph ('Mailing List Activity', None,
                       '%sgraphs/%s/ml.png' % (config.webroot, module.ident),
                       'Mailing List Activity for %s' % module.name)

    return syn
