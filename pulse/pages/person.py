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
import pulse.scm
import pulse.utils

from sqlobject.sqlbuilder import *

def main (path=[], query={}, http=True, fd=None):
    person = None
    if len(path) == 3:
        person = pulse.db.Entity.selectBy (ident=('/' + '/'.join(path)), type='Person')
        if person.count() == 0:
            person = None
        else:
            person = person[0]
    if person == None:
        kw = {'http': http}
        kw['title'] = pulse.utils.gettext ('Person Not Found')
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('Pulse could not find the person %s') % '/'.join(path[1:]),
            **kw)
        page.output(fd=fd)
        return 404

    return output_person (person, path, query, http, fd)


def output_person (person, path=[], query=[], http=True, fd=None):
    page = pulse.html.ResourcePage (person, http=http)

    if person.nick != None:
        page.add_fact (pulse.utils.gettext ('Nick'), person.nick)
        page.add_fact_sep ()
    if person.email != None:
        page.add_fact (pulse.utils.gettext ('Email'),
                       pulse.html.Link ('mailto:' + person.email, person.email))
    if person.web != None:
        page.add_fact (pulse.utils.gettext ('Website'), pulse.html.Link (person.web))

    branches = pulse.db.Branch.select (
        pulse.db.BranchEntityRelation.q.predID == person.id,
        join=INNERJOINOn(None, pulse.db.BranchEntityRelation,
                         pulse.db.BranchEntityRelation.q.subjID == pulse.db.Branch.q.id) )
    branches = pulse.utils.attrsorted (list(branches), 'title')

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    modules = pulse.html.InfoBox ('modules', pulse.utils.gettext ('Modules'))
    documents = pulse.html.InfoBox ('documents', pulse.utils.gettext ('Documents'))
    columns.add_content (0, modules)
    columns.add_content (1, documents)

    resources = []
    for branch in branches:
        # FIXME: this gives random results, do it better
        if branch.resourceID in resources:
            continue
        else:
            resources.append (branch.resourceID)
        if branch.type == 'Module':
            modules.add_resource_link (branch)
        elif branch.type == 'Document':
            documents.add_resource_link (branch)
        # FIXME: more

    page.output(fd=fd)

    return 0