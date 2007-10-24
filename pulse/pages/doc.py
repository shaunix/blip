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
    if len(path) == 4:
        modules = pulse.db.Resource.selectBy (ident=('/' + '/'.join(path)))
        if modules.count() == 0:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Document Not Found')
            # FIXME: this is not a good place to redirect
            kw['pages'] = [('mod', pulse.utils.gettext ('All Modules'))]
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the document %s') % path[3],
                **kw)
            page.output(fd=fd)
            return 404
        else:
            doc = modules[0].default_branch
            if doc == None:
                kw = {'http': http}
                kw['title'] = pulse.utils.gettext ('Default Branch Not Found')
                # FIXME: this is not a good place to redirect
                kw['pages'] = [('mod', pulse.utils.gettext ('All Modules'))]
                page = pulse.html.PageNotFound (
                    pulse.utils.gettext ('Pulse could not find a default branch for the document %s') % path[3],
                    **kw)
                page.output(fd=fd)
                return 404
    elif len(path) == 5:
        docs = pulse.db.Branch.selectBy (ident=('/' + '/'.join(path)))
        if docs.count() == 0:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Document Not Found')
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the branch %s of the document %s') % (path[4], path[3]),
                **kw)
            page.output(fd=fd)
            return 404
        else:
            doc = docs[0]
    else:
        # FIXME: redirect to /set or something
        pass

    return output_doc (doc, path, query, http, fd)


def output_doc (doc, path=[], query=[], http=True, fd=None):
    page = pulse.html.ResourcePage (doc, http=http)

    branches = pulse.db.Branch.selectBy (resource=doc.resource)
    if branches.count() > 1:
        for b in pulse.utils.attrsorted (branches[0:], 'scm_branch'):
            if b.ident != doc.ident:
                page.add_sublink (b.pulse_url, b.ident.split('/')[-1])
            else:
                page.add_sublink (None, b.ident.split('/')[-1])

    sep = False
    try:
        desc = doc.localized_desc
        page.add_fact (pulse.utils.gettext ('Description'), desc)
        sep = True
    except:
        pass

    if sep: page.add_fact_sep ()
    
    if doc.scm_type == 'cvs':
        page.add_fact (pulse.utils.gettext ('CVS Server'), doc.scm_server)
        page.add_fact (pulse.utils.gettext ('CVS Module'), doc.scm_module)
        page.add_fact (pulse.utils.gettext ('CVS Branch'), doc.scm_branch)
    elif doc.scm_type == 'svn':
        loc = doc.scm_server + doc.scm_module
        if doc.scm_branch == 'trunk':
            loc += '/trunk'
        else:
            loc += '/branches/' + doc.scm_branch
        page.add_fact (pulse.utils.gettext ('SVN Location'), loc)

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Developers
    box = pulse.html.InfoBox ('developers', pulse.utils.gettext ('Developers'))
    authors = pulse.db.BranchEntityRelation.selectBy (subj=doc, verb='DocumentAuthor')
    editors = pulse.db.BranchEntityRelation.selectBy (subj=doc, verb='DocumentEditor')
    credits = pulse.db.BranchEntityRelation.selectBy (subj=doc, verb='DocumentCredit')
    maints = pulse.db.BranchEntityRelation.selectBy (subj=doc, verb='DocumentMaintainer')
    people = {}
    for t, l in (('author', authors), ('editor', editors), ('credit', credits), ('maint', maints)):
        for cr in l:
            people.setdefault (cr.pred, [])
            people[cr.pred].append(t)
    if len(people) > 0:
        for person in pulse.utils.attrsorted (people.keys(), 'title'):
            reslink = box.add_resource_link (person)
            badges = people[person]
            if 'maint' in badges:
                reslink.add_badge ('maintainer')
            if 'author' in badges:
                reslink.add_badge ('author')
            if 'editor' in badges:
                reslink.add_badge ('editor')
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No developers') ))
    columns.add_content (0, box)

    page.output(fd=fd)

    return 0
