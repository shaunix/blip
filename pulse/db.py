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


## Resource ident schemas per-type
## Branch idents have /<branch> appended
# Module       /mod/<server>/<module>
# Document     /doc/<server>/<module>/<document>  (gnome-doc-utils)
#              /ref/<server>/<module>/<document>  (gtk-doc)
# Application  /app/<server>/<module>/<app>
# Applet       /applet/<server>/<module>/<applet>
# Library      /lib/<server>/<module>/<lib>
# Plugin       /ext/<server>/<module>/<ext>
# Domain       /i18n/<server>/<module>/<domain>
# Translation  /l10n/<lang>/i18n/<server>/<module>/<domain>
#              /l10n/<lang>/doc/<server>/<module>/<document>
#              /l10n/<lang>/ref/<server>/<module>/<document>


################################################################################
## Records

class Record (sql.SQLObject):
    class sqlmeta:
        table = 'Record'

    ident = sql.StringCol (alternateID=True)
    type = sql.StringCol ()

    name = sql.PickleCol (default={})
    desc = sql.PickleCol (default={})

    icon_dir = sql.StringCol (default=None)
    icon_name = sql.StringCol (default=None)

    email = sql.StringCol (default=None)
    web = sql.StringCol (default=None)

    data = sql.PickleCol (default={})

    def _create (self, *args, **kw):
        pulse.utils.log ('Creating %s %s' % (kw['type'], kw['ident']))
        sql.SQLObject._create (self, *args, **kw)

    @ classmethod
    def get_record (cls, ident, type):
        record = cls.selectBy (ident=ident, type=type)
        if record.count() > 0:
            return record[0]
        else:
            return cls (ident=ident, type=type)

    def remove (self):
        cls = self.__class__
        self.remove_relations ()
        pulse.utils.log ('Removing %s %s' % (self.type, self.ident))
        cls.delete (self.id)

    def remove_relations (self):
        for rel in RecordBranchRelation.selectBy (subj=self):
            rel.remove ()

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

    def get_pulse_url (self):
        return pulse.config.webroot + self.ident[1:]
    pulse_url = property (get_pulse_url)

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
            if self.__class__ == Branch:
                return self.ident.split('/')[-2]
            else:
                return self.ident.split('/')[-1]
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

    def set_relations (self, cls, verb, relations):
        old = cls.selectBy (subj=self, verb=verb)
        olddict = {}
        for rel in old:
            olddict[rel.pred.ident] = rel
        for relation in relations:
            olddict.pop (relation.pred.ident, None)
        for old in olddict.values():
            old.remove ()


class Resource (Record):
    class sqlmeta:
        table = 'Resource'

    default_branch = sql.ForeignKey ('Branch', dbName='default_branch', default=None)

    def remove_relations (self):
        for branch in Branch.selectBy (resource=self):
            branch.remove ()
        for rel in ResourceRelation.selectBy (subj=self):
            rel.remove ()
        for rel in ResourceRelation.selectBy (pred=self):
            rel.remove ()


class Branch (Record):
    class sqlmeta:
        table = 'Branch'

    subtype = sql.StringCol (default=None)
    parent = sql.ForeignKey ('Branch', dbName='parent', default=None)
    resource = sql.ForeignKey ('Resource', dbName='resource', default=None)

    scm_type = sql.StringCol (default=None)
    scm_server = sql.StringCol (default=None)
    scm_module = sql.StringCol (default=None)
    scm_branch = sql.StringCol (default=None)
    scm_path = sql.StringCol (default=None)
    scm_dir = sql.StringCol (default=None)
    scm_file = sql.StringCol (default=None)

    def _ensure_default_branch (self):
        if getattr (self, 'scm_type', None) != None and getattr (self, 'scm_branch', None) != None:
            if pulse.scm.default_branches[self.scm_type] == self.scm_branch:
                self.resource.default_branch = self
    def _set_scm_type (self, value):
        self._ensure_default_branch ()
        self._SO_set_scm_type (value)
    def _set_scm_branch (self, value):
        self._ensure_default_branch ()
        self._SO_set_scm_branch (value)

    @ classmethod
    def get_record (cls, ident, type):
        record = cls.selectBy (ident=ident, type=type)
        if record.count() > 0:
            record = record[0]
        else:
            record = cls (ident=ident, type=type)
        if record.resource == None:
            ident = '/'.join(record.ident.split('/')[:-1])
            record.resource = Resource.get_record (ident=ident, type=record.type)
        record._ensure_default_branch ()
        return record

    def get_branch_title (self):
        return pulse.utils.gettext ('%s (%s)') % (self.title, self.scm_branch)
    branch_title = property (get_branch_title)

    def remove_relations (self):
        if self.resource != None and Branch.selectBy (resource=self.resource).count() <= 1:
            # Bad things happen if we don't do this
            resource = self.resource
            self.resource = None
            resource.remove ()
        for rel in RecordBranchRelation.selectBy (pred=self):
            rel.remove ()
        for rel in BranchRelation.selectBy (subj=self):
            rel.remove ()
        for rel in BranchRelation.selectBy (pred=self):
            rel.remove ()
        for commit in Commits.selectBy (branch=self):
            commit.remove ()

    def set_children (self, type, children):
        old = Branch.selectBy (type=type, parent=self)
        olddict = {}
        for res in old:
            olddict[res.ident] = res
        for child in children:
            olddict.pop (child.ident, None)
            child.parent = self
            if self.resource.default_branch == self:
                child.resource.default_branch = child
        for old in olddict.values():
            old.remove ()


class Entity (Record):
    class sqlmeta:
        table = 'Entity'

    nick = sql.StringCol (default=None)

    def get_name_nick (self):
        # FIXME: latinized names
        if self.nick != None:
            return pulse.utils.gettext ('%s (%s)') % (self.localized_name, self.nick)
        else:
            return self.localized_name
    name_nick = property (get_name_nick)

    def remove_relations (self):
        for rel in ResourceEntityRelation.selectBy (pred=self):
            rel.remove ()
        for rel in BranchEntityRelation.selectBy (pred=self):
            rel.remove ()
        for rel in EntityRelation.selectBy (subj=self):
            rel.remove ()
        for rel in EntityRelation.selectBy (pred=self):
            rel.remove ()


class ScmCommit (sql.SQLObject):
    class sqlmeta:
        table = 'ScmCommit'

    branch =  sql.ForeignKey ('Branch', dbName='branch')
    person = sql.ForeignKey ('Entity', dbName='person')
    filename = sql.StringCol ()
    filetype = sql.StringCol (default=None)
    revision = sql.StringCol ()
    datetime = sql.DateTimeCol ()
    comment = sql.StringCol ()


################################################################################
## Relations

class PulseRelation (object):
    def _create (self, *args, **kw):
        pulse.utils.log ('Creating relation %s -%s- %s' %
                         (kw['subj'].ident, kw['verb'], kw['pred'].ident))
        sql.SQLObject._create (self, *args, **kw)

    @ classmethod
    def set_related (cls, subj, verb, pred):
        res = cls.selectBy (subj=subj, verb=verb, pred=pred)
        if res.count() > 0:
            return res[0]
        else:
            return cls (subj=subj, verb=verb, pred=pred)

    @ classmethod
    def is_related (cls, subj, verb, pred):
        res = cls.selectBy (subj=subj, verb=verb, pred=pred)
        return res.count() > 0

    def remove (self):
        pulse.utils.log ('Removing relation %s -%s- %s' % (self.subj.ident, self.verb, self.pred.ident))
        self.__class__.delete (self.id)

class RecordRelation (PulseRelation, sql.SQLObject):
    class sqlmeta:
        table = 'RecordRelation'

    subj = sql.ForeignKey ('Record', dbName='subj')
    pred = sql.ForeignKey ('Record', dbName='pred')
    verb = sql.StringCol ()

class RecordBranchRelation (PulseRelation, sql.SQLObject):
    class sqlmeta:
        table = 'RecordBranchRelation'

    subj = sql.ForeignKey ('Record', dbName='subj')
    pred = sql.ForeignKey ('Branch', dbName='pred')
    verb = sql.StringCol ()
  
class ResourceRelation (PulseRelation, sql.SQLObject):
    class sqlmeta:
        table = 'ResourceRelation'
    subj = sql.ForeignKey ('Resource', dbName='subj')
    pred = sql.ForeignKey ('Resource', dbName='pred')
    verb = sql.StringCol ()

class BranchRelation (PulseRelation, sql.SQLObject):
    class sqlmeta:
        table = 'BranchRelation'
    subj = sql.ForeignKey ('Branch', dbName='subj')
    pred = sql.ForeignKey ('Branch', dbName='pred')
    verb = sql.StringCol ()

class EntityRelation (PulseRelation, sql.SQLObject):
    class sqlmeta:
        table = 'EntityRelation'
    subj = sql.ForeignKey ('Entity', dbName='subj')
    pred = sql.ForeignKey ('Entity', dbName='pred')
    verb = sql.StringCol ()

class ResourceEntityRelation (PulseRelation, sql.SQLObject):
    class sqlmeta:
        table = 'ResourceEntityRelation'
    subj = sql.ForeignKey ('Resource', dbName='subj')
    pred = sql.ForeignKey ('Entity', dbName='pred')
    verb = sql.StringCol ()

class BranchEntityRelation (PulseRelation, sql.SQLObject):
    class sqlmeta:
        table = 'BranchEntityRelation'
    subj = sql.ForeignKey ('Branch', dbName='subj')
    pred = sql.ForeignKey ('Entity', dbName='pred')
    verb = sql.StringCol ()


################################################################################
## Timestamps

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


################################################################################
## Utilities

def create_tables ():
    for table in inspect.getmembers (sys.modules[__name__]):
        if (hasattr (table[1], 'createTable')
            and inspect.isclass (table[1])
            and not table[0].endswith('SQLObject')):

            table[1].createTable (ifNotExists=True)
