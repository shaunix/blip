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
                kw['pages'] = [(module.ident, module.get_localized_name (['C']))]
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
    kw = {'http' : http}
    # FIXME: i18n
    kw['title'] = module.get_localized_name (['C'])

    page = pulse.html.Page (**kw)

    # FIXME: do stuff

    page.output(fd=fd)

    return 0

def output_branch (branch, path=[], query=[], http=True, fd=None):
    kw = {'http' : http}
    # FIXME: i18n
    kw['title'] = pulse.utils.gettext('%s (%s)') % (branch.get_localized_name (['C']), path[-1])

    page = pulse.html.Page (**kw)

    apps = pulse.db.Resource.selectBy (type='Application', parent=branch)

    page.output(fd=fd)

    return 0
