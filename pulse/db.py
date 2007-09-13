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

import pulse.config as config
import pulse.utils as utils

conn = sql.connectionForURI (config.dbroot)
sql.sqlhub.processConnection = conn
sql.setDeprecationLevel (None)


class Resource (sql.SQLObject):
    class sqlmeta:
        table = 'Resource'
    # Set          /set/<set>
    # Module       /scm/<server>/<module>
    # Branch       /scm/<server>/<module>/<branch>
    # Document     /doc/<server>/<module>/<branch>/<document>
    # Domain       /pot/<server>/<module>/<branch>/<domain>
    # Translation  /po/<server>/<module>/<branch>/[doc|pot]/<doc|pot>/<lang>
    # Team         /team/<server>/<team>
    # Person       /person/<server>/<person>
    # List         /list/<server>/<list>
    ident = sql.StringCol (alternateID=True)
    resourceType = sql.StringCol ()

    name = sql.PickleCol ()
    desc = sql.PickleCol ()

    icon = sql.StringCol ()
    nick = sql.StringCol ()

    email = sql.StringCol ()
    web = sql.StringCol ()

class ResourceData (sql.SQLObject):
    class sqlmeta:
        tabe = 'ResourceData'
    resource = sql.ForeignKey ('Resource', dbName='resource')
    data = sql.PickleCol ()

class Relation (sql.SQLObject):
    class sqlmeta:
        table = 'Relation'
    subj = sql.ForeignKey ('Resource', dbName='subj')
    pred = sql.ForeignKey ('Resource', dbName='pred')
    verb = sql.StringCol ()
    superlative = sql.BoolCol ()

def create_tables ():
    for table in inspect.getmembers (sys.modules[__name__]):
        if (hasattr (table[1], 'createTable')
            and inspect.isclass (table[1])
            and not table[0].endswith('SQLObject')):

            table[1].createTable (ifNotExists=True)
