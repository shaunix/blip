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

import pulse.config
import pulse.db
import pulse.html
import pulse.utils

def main (path=[], query={}, http=True, fd=None):
    if len(path) == 3:
        modules = pulse.db.Resource.selectBy (ident=('/' + '/'.join(path)))
        if modules.count() == 0:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Module Not Found')
            # FIXME: this is not a good place to redirect
            kw['pages'] = [('mod', pulse.utils.gettext ('All Modules'))]
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the module %s') % path[2],
                **kw)
            page.output(fd=fd)
            return 404
        else:
            return output_module (modules[0], path, query, http, fd)
    elif len(path) == 4:
        branches = pulse.db.Resource.selectBy (ident=('/' + '/'.join(path)))
        if branches.count() == 0:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Branch Not Found')
            modules = pulse.db.Resource.selectBy (ident=('/' + '/'.join(path[0:-1])))
            if modules.count() > 0:
                module = modules[0]
                # FIXME: i18n
                kw['pages'] = [(module.ident, module.title)]
            else:
                kw['pages'] = []
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the branch %s of the module %s') % (path[3], path[2]),
                **kw)
            page.output(fd=fd)
            return 404
        else:
            return output_branch (branches[0], path, query, http, fd)
    else:
        # FIXME: redirect to /set or something
        pass
    return 0

def get_developers_box (module):
    box = pulse.html.InfoBox ('developers', pulse.utils.gettext ('Developers'))
    developers = pulse.db.Relation.selectBy (subj=module,
                                             verb=pulse.db.Relation.module_developer)
    if developers.count() > 0:
        for rel in pulse.utils.attrsorted (developers[0:], 'pred', 'title'):
            box.add_resource_link (rel.pred, rel.superlative)
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No developers') ))
    return box

def output_module (module, path=[], query={}, http=True, fd=None):
    page = pulse.html.ResourcePage (module, http=http)

    branches = pulse.db.Resource.selectBy (parent=module, type='Branch')
    bsorted = pulse.utils.attrsorted (branches[0:], 'scm_branch')
    if branches.count() > 0:
        for b in bsorted:
            page.add_sublink (b.url, b.scm_branch)

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    box = get_developers_box (module)
    columns.add_content (0, box)

    box = pulse.html.InfoBox ('branches', pulse.utils.gettext ('Branches'))
    columns.add_content (1, box)
    if len(bsorted) > 0:
        for branch in bsorted:
            rlink = box.add_resource_link (branch, False)
            rlink.set_title (branch.scm_branch)
            rlink.set_description (None)
            # FIXME: ngettext
            # FIXME: fact tables aren't the right way to do this
            res = pulse.db.Resource.selectBy (parent=branch, type='Application')
            rlink.add_fact ('', pulse.utils.gettext ('%i applications') % res.count())
            res = pulse.db.Resource.selectBy (parent=branch, type='Applet')
            rlink.add_fact ('', pulse.utils.gettext ('%i applets') % res.count())
            res = pulse.db.Resource.selectBy (parent=branch, type='Library')
            rlink.add_fact ('', pulse.utils.gettext ('%i libraries') % res.count())
            res = pulse.db.Resource.selectBy (parent=branch, type='Document')
            rlink.add_fact ('', pulse.utils.gettext ('%i documents') % res.count())
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No branches') ))

    page.output(fd=fd)

    return 0

def output_branch (branch, path=[], query=[], http=True, fd=None):
    module = branch.parent

    page = pulse.html.ResourcePage (branch, http=http)

    branches = pulse.db.Resource.selectBy (parent=module)
    if branches.count() > 1:
        for b in pulse.utils.attrsorted (branches[0:], 'scm_branch'):
            if b.ident != branch.ident:
                page.add_sublink (b.url, b.ident.split('/')[-1])
            else:
                page.add_sublink (None, b.ident.split('/')[-1])

    sep = False
    try:
        desc = branch.localized_desc
        page.add_fact (pulse.utils.gettext ('Description'), desc)
        sep = True
    except:
        pass

    rels = pulse.db.Relation.selectBy (pred=branch, verb=pulse.db.Relation.set_branch)
    if rels.count() > 0:
        sets = pulse.utils.attrsorted ([rel.subj for rel in rels], 'title')
        page.add_fact (pulse.utils.gettext ('Release Sets'), sets)
        sep = True

    if sep: page.add_fact_sep ()
    
    if branch.scm_type == 'cvs':
        page.add_fact (pulse.utils.gettext ('CVS Server'), branch.scm_server)
        page.add_fact (pulse.utils.gettext ('CVS Module'), branch.scm_module)
        page.add_fact (pulse.utils.gettext ('CVS Branch'), branch.scm_branch)
    elif branch.scm_type == 'svn':
        loc = branch.scm_server + branch.scm_module
        if branch.scm_branch == 'trunk':
            loc += '/trunk'
        else:
            loc += '/branches/' + branch.scm_branch
        page.add_fact (pulse.utils.gettext ('SVN Location'), loc)

    if branch.data.has_key ('tarname'):
        page.add_fact_sep ()
        page.add_fact (pulse.utils.gettext ('Tarball Name'), branch.data['tarname'])

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Developers
    box = get_developers_box (module)
    columns.add_content (0, box)

    # Domains
    box = pulse.html.InfoBox ('domains', pulse.utils.gettext ('Domains'))
    columns.add_content (0, box)
    domains = pulse.db.Resource.selectBy (type='Domain', parent=branch)
    if domains.count() > 0:
        for domain in pulse.utils.attrsorted (domains[0:], 'title'):
            # FIXME: let's not do a simple resource link, but a tree with other info
            reslink = box.add_resource_link (domain)
            translations = pulse.db.Resource.selectBy (type='Translation', parent=domain)
            grid = pulse.html.GridBox ()
            reslink.add_content (grid)
            for translation in pulse.utils.attrsorted (translations[0:], 'title'):
                grid.add_row ((translation.title,))
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No domains') ))

    # Applications
    apps = pulse.db.Resource.selectBy (type='Application', parent=branch)
    if apps.count() > 0:
        box = pulse.html.InfoBox ('applications', pulse.utils.gettext ('Applications'))
        columns.add_content (1, box)
        for app in pulse.utils.attrsorted (apps[0:], 'title'):
            box.add_resource_link (app)

    # Applets
    applets = pulse.db.Resource.selectBy (type='Applet', parent=branch)
    if applets.count() > 0:
        box = pulse.html.InfoBox ('applets', pulse.utils.gettext ('Applets'))
        columns.add_content (1, box)
        for applet in pulse.utils.attrsorted (applets[0:], 'title'):
            box.add_resource_link (applet)

    # Libraries
    libs = pulse.db.Resource.selectBy (type='Library', parent=branch)
    if libs.count() > 0:
        box = pulse.html.InfoBox ('libraries', pulse.utils.gettext ('Libraries'))
        columns.add_content (1, box)
        for lib in pulse.utils.attrsorted (libs[0:], 'title'):
            box.add_resource_link (lib)

    # Documents
    box = pulse.html.InfoBox ('documents', pulse.utils.gettext ('Documents'))
    columns.add_content (1, box)
    docs = pulse.db.Resource.selectBy (type='Document', parent=branch)
    if docs.count() > 0:
        for doc in pulse.utils.attrsorted (docs[0:], 'title'):
            box.add_resource_link (doc)
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No documents') ))

    page.output(fd=fd)

    return 0
