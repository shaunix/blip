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

def output_module (module, path=[], query={}, http=True, fd=None):
    page = pulse.html.ResourcePage (module, http=http)

    # FIXME: do stuff

    page.output(fd=fd)

    return 0

def output_branch (branch, path=[], query=[], http=True, fd=None):
    module = branch.parent

    page = pulse.html.ResourcePage (branch, http=http)

    branches = pulse.db.Resource.selectBy (parent=branch.parent)
    # FIXME: sort
    for b in branches:
        if b.ident != branch.ident:
            # FIXME: url, not ident
            page.add_sublink (b.ident, b.ident.split('/')[-1])
        else:
            page.add_sublink (None, b.ident.split('/')[-1])

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Developers
    box = pulse.html.RelationBox ('developers', pulse.utils.gettext ('Developers'))
    columns.add_content (0, box)
    developers = pulse.db.Relation.selectBy (subj=module,
                                             verb=pulse.db.Relation.module_developer)
    for rel in developers:
        box.add_relation (rel.pred, rel.superlative)

    # Applications
    apps = pulse.db.Resource.selectBy (type='Application', parent=branch)
    if apps.count() > 0:
        box = pulse.html.RelationBox ('applications', pulse.utils.gettext ('Applications'))
        columns.add_content (1, box)
        for app in apps:
            box.add_relation (app, False)

    page.output(fd=fd)

    return 0
