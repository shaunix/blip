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
import os.path
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
    # Document     /doc/<server>/<module>/<branch>/<document> (gnome-doc-utils)
    #              /ref/<server>/<module>/<branch>/<document> (gtk-doc)
    # Application  /app/<server>/<module>/<branch>/<app>
    # Applet       /applet/<server>/<module>/<branch>/<applet>
    # Library      /lib/<server>/<module>/<branch>/<lib>
    # Domain       /i18n/<server>/<module>/<branch>/<domain>
    # FIXME: I don't like the translation naming scheme
    # Translation  /i18n/<server>/<module>/<branch>/po/<domain>/<lang>
    #              /i18n/<server>/<module>/<branch>/doc/<doc>/<lang>
    # Maybe this:
    # Translation  /l10n/<lang>/[i18n|doc|ref]/<server>/<module>/<branch>/<i18n|doc|ref>
    # Team         /team/<server>/<team>
    # FIXME: what do we do about people with accounts in different places?
    # Person       /person/<server>/<person>
    # List         /list/<server>/<list>
    ident = sql.StringCol (alternateID=True)
    type = sql.StringCol ()
    subtype = sql.StringCol (default=None)
    parent = sql.ForeignKey ('Resource', dbName='parent', default=None)

    name = sql.PickleCol (default={})
    desc = sql.PickleCol (default={})

    icon_dir = sql.StringCol (default=None)
    icon_name = sql.StringCol (default=None)

    nick = sql.StringCol (default=None)

    email = sql.StringCol (default=None)
    web = sql.StringCol (default=None)

    scm_type = sql.StringCol (default=None)
    scm_server = sql.StringCol (default=None)
    scm_module = sql.StringCol (default=None)
    scm_branch = sql.StringCol (default=None)
    scm_dir = sql.StringCol (default=None)
    scm_file = sql.StringCol (default=None)

    data = sql.PickleCol (default={})

    @ classmethod
    def make (cls, ident, type):
        res = cls.selectBy (ident=ident, type=type)
        if res.count() > 0:
            return res[0]
        else:
            return cls (ident=ident, type=type)

    def get_icon_url (self):
        if self.icon_name == None or self.icon_dir.startswith ('__icon__'):
            return None
        elif self.icon_dir == None:
            return pulse.config.iconroot + self.icon_name + '.png'
        else:
            return pulse.config.iconroot + self.icon_dir + '/' + self.icon_name + '.png'
    icon_url = property (get_icon_url)

    def get_title (self):
        if self.name == {}:
            return self.ident.split('/')[-1]
        if self.nick != None:
            return pulse.utils.gettext ('%s (%s)') % (self.localized_name, self.nick)
        return self.localized_name
    title = property (get_title)

    def get_localized_name (self):
        # FIXME: i18n
        return self.name.get('C')
    localized_name = property (get_localized_name)

    def get_localized_desc (self):
        # FIXME: i18n
        return self.desc.get('C')
    localized_desc = property (get_localized_desc)

    def get_url (self):
        return pulse.config.webroot + self.ident[1:]
    url = property (get_url)

    def update (self, d):
        stuff = {}
        data = {}
        for k in d.keys():
            if k == 'name':
                stuff['name'] = self.updated_name (d[k])
            elif k == 'desc':
                stuff['desc'] = self.updated_desc (d[k])
            elif self.sqlmeta.columnDefinitions.has_key (k):
                stuff[k] = d[k]
            else:
                data[k] = d[k]
        if len(data) > 0:
            stuff['data'] = self.updated_data (data)
        self.set (**stuff)

    def updated_name (self, d):
        if isinstance (d, basestring):
            d = {'C' : d}
        name = self.name
        for k in d:
            name[k] = d[k]
        return name
    def update_name (self, d):
        self.name = self.updated_name (d)

    def updated_desc (self, d):
        if isinstance (d, basestring):
            d = {'C' : d}
        desc = self.desc
        for k in d:
            desc[k] = d[k]
        return desc
    def update_desc (self, d):
        self.desc = self.updated_desc (d)

    def updated_data (self, d):
        data = self.data
        for k in d:
            data[k] = d[k]
        return data
    def update_data (self, d):
        self.data = self.updated_data (d)

    def delete_full (self):
        rels = pulse.db.Relation.selectBy (subj=self)
        for rel in rels:
            rel.delete_full ()
        rels = pulse.db.Relation.selectBy (pred=self)
        for rel in rels:
            rel.delete_full ()
        children = pulse.db.Resource.selectBy (parent=self)
        for child in children:
            child.delete_full ()
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

    def set_relations (self, verb, relations):
        old = Relation.selectBy (subj=self, verb=verb)
        olddict = {}
        for rel in old:
            olddict[rel.pred.ident] = rel
        for relation in relations:
            olddict.pop (relation.pred.ident, None)
        for old in olddict.values():
            old.delete_full ()


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
    module_developer = 'module_developer' # Module -> Person/Team

    def delete_full (self):
        pulse.utils.log ('Deleting relation (%s %s %s)' % (self.subj.ident, self.verb, self.pred.ident))
        Relation.delete (self.id)

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


class Timestamp (sql.SQLObject):
    class sqlmeta:
        table = 'Timestamp'

    filename = sql.StringCol ()
    sourcefunc = sql.StringCol ()
    stamp = sql.IntCol ()

    @classmethod
    def set_timestamp (cls, filename, stamp):
        sfunc = inspect.stack()[1]
        sfunc = os.path.basename (sfunc[1]) + '#' + sfunc[3]
        obj = Timestamp.selectBy (filename=filename, sourcefunc=sfunc)
        if obj.count() > 0:
            obj[0].stamp = int(stamp)
        else:
            Timestamp (filename=filename, sourcefunc=sfunc, stamp=int(stamp))
        return stamp

    @classmethod
    def get_timestamp (cls, filename):
        sfunc = inspect.stack()[1]
        sfunc = os.path.basename (sfunc[1]) + '#' + sfunc[3]
        obj = Timestamp.selectBy (filename=filename, sourcefunc=sfunc)
        if obj.count() > 0:
            return obj[0].stamp
        else:
            return -1

def create_tables ():
    for table in inspect.getmembers (sys.modules[__name__]):
        if (hasattr (table[1], 'createTable')
            and inspect.isclass (table[1])
            and not table[0].endswith('SQLObject')):

            table[1].createTable (ifNotExists=True)
