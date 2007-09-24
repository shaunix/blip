# Copyright (c) 2007  Shaun McCance  <shaunm@gnome.org>
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

import inspect
import sys

import sqlobject as sql

import pulse.config
import pulse.utils

conn = sql.connectionForURI (pulse.config.dbroot)
sql.sqlhub.processConnection = conn
sql.setDeprecationLevel (None)


class Resource (sql.SQLObject):
    class sqlmeta:
        table = 'Resource'

    def _create (self, *args, **kw):
        pulse.utils.log ('Creating resource %s' % kw['ident'])
        sql.SQLObject._create (self, *args, **kw)

    # Set          /set/<set>
    # Module       /mod/<server>/<module>
    # Branch       /mod/<server>/<module>/<branch>
    # Document     /doc/<server>/<module>/<branch>/<document>
    # Domain       /pot/<server>/<module>/<branch>/<domain>
    # Translation  /po/<server>/<module>/<branch>/[doc|pot]/<doc|pot>/<lang>
    # Team         /team/<server>/<team>
    # Person       /person/<server>/<person>
    # List         /list/<server>/<list>
    ident = sql.StringCol (alternateID=True)
    type = sql.StringCol ()
    parent = sql.ForeignKey ('Resource', dbName='parent', default=None)

    name = sql.PickleCol (default={})
    desc = sql.PickleCol (default={})

    icon = sql.StringCol (default=None)
    nick = sql.StringCol (default=None)

    email = sql.StringCol (default=None)
    web = sql.StringCol (default=None)

    data = sql.PickleCol (default={})

class Relation (sql.SQLObject):
    class sqlmeta:
        table = 'Relation'
    subj = sql.ForeignKey ('Resource', dbName='subj')
    pred = sql.ForeignKey ('Resource', dbName='pred')
    verb = sql.StringCol ()
    superlative = sql.BoolCol (default=False)

    # Relations, so that we don't have typos
    set_subset = 'set_subset'             # Set -> Set
    set_branch = 'set_branch'             # Set -> Branch
    module_branch = 'module_branch'       # Module -> Branch
    module_developer = 'module_developer' # Module -> Person/Team

    @classmethod
    def set_relation (cls, subj, verb, pred, superlative=False):
        # FIXME: pulse.utils.log
        rel = Relation.selectBy (subj=subj, pred=pred, verb=verb)
        if rel.count() > 0:
            if superlative:
                rel[0].superlative = True
                return rel[0]
        else:
            return Relation (subj=subj, pred=pred, verb=verb, superlative=superlative)


def create_tables ():
    for table in inspect.getmembers (sys.modules[__name__]):
        if (hasattr (table[1], 'createTable')
            and inspect.isclass (table[1])
            and not table[0].endswith('SQLObject')):

            table[1].createTable (ifNotExists=True)
