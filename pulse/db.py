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
    # Application  /app/<server>/<module>/<branch>/<app>
    # Domain       /i18n/<server>/<module>/<branch>/<domain>
    # Translation  /i18n/<server>/<module>/<branch>/po/<domain>/<lang>
    #              /i18n/<server>/<module>/<branch>/doc/<doc>/<lang>
    # Team         /team/<server>/<team>
    # Person       /person/<server>/<person>
    # List         /list/<server>/<list>
    ident = sql.StringCol (alternateID=True)
    type = sql.StringCol ()
    parent = sql.ForeignKey ('Resource', dbName='parent', default=None, cascade=True)

    name = sql.PickleCol (default={})
    desc = sql.PickleCol (default={})

    icon = sql.StringCol (default=None)
    nick = sql.StringCol (default=None)

    email = sql.StringCol (default=None)
    web = sql.StringCol (default=None)

    data = sql.PickleCol (default={})

    @ classmethod
    def make (cls, ident, type):
        res = cls.selectBy (ident=ident, type=type)
        if res.count() > 0:
            return res[0]
        else:
            return cls (ident=ident, type=type)

    def get_title (self):
        if self.nick != None:
            return pulse.utils.gettext ('%s (%s)') % (self.localized_name, self.nick)
        else:
            return self.localized_name
    title = property (get_title)

    def get_localized_name (self):
        # FIXME: i18n
        return self.name['C']
    localized_name = property (get_localized_name)

    def get_localized_desc (self):
        # FIXME: i18n
        return self.desc['C']
    localized_desc = property (get_localized_desc)

    def update_name (self, d):
        name = self.name
        for k in d:
            name[k] = d[k]
        self.name = name

    def update_desc (self, d):
        desc = self.desc
        for k in d:
            desc[k] = d[k]
        self.desc = desc

    def update_data (self, d):
        data = self.data
        for k in d:
            data[k] = d[k]
        self.data = data

    def delete_full (self):
        pulse.utils.log ('Deleting resource %s' % self.ident)
        Resource.delete (self.id)

    def set_children (self, type, children):
        old = Resource.selectBy (type=type, parent=self)
        olddict = {}
        for res in old:
            olddict[res.ident] = res
        for child in children:
            olddict.pop (child.ident, None)
            child.parent = self
        for old in olddict.values():
            old.delete_full ()
        
            

class Relation (sql.SQLObject):
    class sqlmeta:
        table = 'Relation'
    subj = sql.ForeignKey ('Resource', dbName='subj', cascade=True)
    pred = sql.ForeignKey ('Resource', dbName='pred', cascade=True)
    verb = sql.StringCol ()
    superlative = sql.BoolCol (default=False)

    # Relations, so that we don't have typos
    set_subset = 'set_subset'             # Set -> Set
    set_branch = 'set_branch'             # Set -> Branch
    module_branch = 'module_branch'       # Module -> Branch
    module_developer = 'module_developer' # Module -> Person/Team

    @classmethod
    def make (cls, subj, verb, pred, superlative=False):
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
