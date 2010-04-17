# Copyright (c) 2007-2010  Shaun McCance  <shaunm@gnome.org>
#
# This file is part of Blip, a program for displaying various statistics
# of questionable relevance about software and the people who make it.
#
# Blip is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# Blip is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along
# with Blip; if not, write to the Free Software Foundation, 59 Temple Place,
# Suite 330, Boston, MA  0211-1307  USA.
#

import datetime
import inspect
import itertools
import os
import re
import sys

from storm.locals import *
from storm.expr import Variable, LeftJoin
from storm.info import ClassAlias
import storm.properties
import storm.references
import storm.store

import blinq.config

import blip.utils
import blip.scm


################################################################################
## Basics


database = create_database (blinq.config.db_uri)
stores = {}
def get_store (store):
    if isinstance (store, Store):
        return store
    if hasattr (store, '__blip_store__'):
        return store.__blip_store__
    if not stores.has_key (store):
        stores[store] = Store (database)
    return stores[store]
store_options = {'rollback' : False}


def flush (store='default'):
    store = get_store (store)
    store.flush()


def commit (store='default'):
    store = get_store (store)
    if store_options.get ('rollback', False):
        blip.utils.log ('Not committing changes')
    else:
        blip.utils.log ('Committing changes')
        store.commit ()


def rollback (store='default'):
    store = get_store (store)
    blip.utils.log ('Rolling back changes')
    try:
        store.rollback ()
    except:
        blip.utils.warn ('Could not roll back changes')


def rollback_all ():
    store_options['rollback'] = True


def block_implicit_flushes (store='default'):
    store = get_store (store)
    store.block_implicit_flushes ()


def read_tables ():
    for cls in blip.utils.read_subclasses (blip.db.BlipModel):
        if not hasattr (cls, '__storm_table__'):
            continue
        yield cls


################################################################################
## Debugging


class BlipTracer (object):
    select_count = 0
    select_total = 0
    insert_count = 0
    insert_total = 0
    update_count = 0
    update_total = 0
    other_count = 0
    other_total = 0
    
    def __init__ (self, log=True):
        self._log = log
        self._last_time = None

    @staticmethod
    def timing_string (seconds):
        milli = 1000 * seconds
        micro = 1000 * (milli - int(milli))
        timing = '%03i.%03i' % (int(milli), int(micro))
        return timing

    def connection_raw_execute (self, connection, raw_cursor, statement, params):
        self._last_time = datetime.datetime.now()

    def print_command (self, statement, params):
        diff = datetime.datetime.now() - self._last_time
        sec = diff.seconds + (diff.microseconds / 1000000.)
        timing = BlipTracer.timing_string (sec)
        outtxt = []
        raw_params = []
        for param in params:
            if isinstance (param, Variable):
                raw_params.append (param.get ())
            elif isinstance (param, basestring):
                raw_params.append (param)
            else:
                raw_params.append (str(param))
        raw_params = tuple (raw_params)
        cmd = statement.replace ('?', '%s') % raw_params
        if cmd.startswith ('SELECT '):
            self.__class__.select_count += 1
            self.__class__.select_total += sec
            if not self._log:
                return
            outtxt = re.split (' (?=WHERE|AND|GROUP BY|ORDER BY|LIMIT)', cmd)
            sel, frm = outtxt[0].split (' FROM ')
            if not sel.startswith ('SELECT COUNT'):
                sel = 'SELECT ...'
            outtxt[0] = sel + ' FROM ' + frm
        elif cmd.startswith ('INSERT '):
            self.__class__.insert_count += 1
            self.__class__.insert_total += sec
            if not self._log:
                return
            outtxt = re.split (' (?=VALUES)', cmd)
        elif cmd.startswith ('UPDATE '):
            self.__class__.update_count += 1
            self.__class__.update_total += sec
            if not self._log:
                return
            outtxt = re.split (' (?=SET|WHERE|AND)', cmd)
        elif cmd.startswith ('COMMIT') or cmd.startswith ('ROLLBACK'):
            if not self._log:
                return
            outtxt.append (cmd)
        else:
            self.__class__.other_count += 1
            self.__class__.other_total += sec
            if not self._log:
                return
            outtxt.append (cmd)

        if not self._log:
            return
        blip.utils.log_write ((u'%sms  %s\n' % (timing, outtxt[0])).encode ('utf8'))
        for txt in outtxt[1:]:
            blip.utils.log_write ((u'           %s\n' % txt).encode ('utf8'))

    def connection_raw_execute_error (self, connection, raw_cursor,
                                      statement, params, error):
        self.print_command (statement, params)
        blip.utils.log_write ('ERROR: %s\n' % error)

    def connection_raw_execute_success (self, connection, raw_cursor,
                                        statement, params):
        self.print_command (statement, params)


def debug (log=True):
    import storm.tracer
    storm.tracer.install_tracer (BlipTracer (log=log))


def debug_summary ():
    blip.utils.log_write ('---------\n')
    timing = BlipTracer.timing_string (BlipTracer.select_total)
    blip.utils.log_write ('%i SELECT statements in %sms\n' % (BlipTracer.select_count, timing))
    if BlipTracer.insert_total > 0:
        timing = BlipTracer.timing_string (BlipTracer.insert_total)
        blip.utils.log_write ('%i INSERT statements in %sms\n'
                               % (BlipTracer.insert_count, timing))
    if BlipTracer.update_total > 0:
        timing = BlipTracer.timing_string (BlipTracer.update_total)
        blip.utils.log_write ('%i UPDATE statements in %sms\n'
                               % (BlipTracer.update_count, timing))
    if BlipTracer.other_total > 0:
        timing = BlipTracer.timing_string (BlipTracer.other_total)
        blip.utils.log_write ('%i other statements in %sms\n'
                               % (BlipTracer.other_count, timing))


################################################################################
## Exceptions


class NoSuchFieldError (Exception):
    pass


class WillNotDelete (Exception):
    pass


################################################################################
## Base Classes


# FIXME
def get_by_ident (ident):
    first = ident.split('/')[1]
    try:
        if first == 'set':
            cls = ReleaseSet
        elif first in ('mod', 'doc', 'ref', 'app', 'applet', 'lib', 'ext', 'i18n', 'l10n'):
            cls = Branch
        elif first in ('person', 'team', 'ghost'):
            cls = Entity
        elif first == 'list':
            cls = Forum
        return cls.get (ident)
    except:
        return None


class ShortText (Unicode):
    pass
        

class BlipModelType (storm.properties.PropertyPublisherMeta):
    def __new__ (meta, name, bases, attrs):
        cls = super (BlipModelType, meta).__new__ (meta, name, bases, attrs)
        cls._record_cache = {}
        if not cls.__dict__.get ('__abstract__', False):
            cls.__storm_table__ = cls.__name__
        return cls


class BlipModel (Storm):
    __abstract__ = True
    __metaclass__ = BlipModelType
    __blip_store__ = get_store ('default')

    def __init__ (self, **kw):
        store = get_store (kw.pop ('__blip_store__', self.__class__.__blip_store__))
        self.update (**kw)
        self.log_create ()
        store.add (self)
        store.flush ()

    def __repr__ (self):
        if hasattr (self, 'id'):
            return '%s %s' % (self.__class__.__name__, getattr (self, 'id'))
        else:
            return self.__class__.__name__

    def log_create (self):
        blip.utils.log ('Creating %s' % self)

    def decache (self):
        storm.store.Store.of(self)._cache.remove (self)

    @classmethod
    def get (cls, key, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        return store.get (cls, key)

    @classmethod
    def select (cls, *args, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        return store.find (cls, *args, **kw)

    @classmethod
    def get_fields (cls):
        fields = {}
        for key, prop in inspect.getmembers (cls):
            if not (isinstance (prop, storm.properties.PropertyColumn) or
                    isinstance (prop, storm.references.Reference) ):
                continue
            fields[key] = (prop, prop.__get__.im_class)
        return fields

    def _update_or_extend (self, overwrite, _update_data={}, **kw):
        fields = self.__class__.get_fields ()
        for key, val in _update_data.items() + kw.items():
            field, fieldcls = fields.get (key, (None, None))
            if fieldcls == None:
                raise NoSuchFieldError ('Table %s has no field for %s'
                                        % (self.__class__.__name__, key))
            elif issubclass (fieldcls, Pickle):
                dd = getattr (self, key, {})
                if not isinstance (val, dict):
                    val = {'C': val}
                for subkey, subval in val.items ():
                    if overwrite or (dd.get (subkey) == None):
                        dd[subkey] = subval
            else:
                if overwrite or (getattr (self, key) == None):
                    if issubclass (fieldcls, Unicode) and isinstance (val, str):
                        val = blip.utils.utf8dec (val)
                    setattr (self, key, val)
        return self

    def update (self, _update_data={}, **kw):
        return self._update_or_extend (True, _update_data, **kw)

    def extend (self, _update_data={}, **kw):
        return self._update_or_extend (False, _update_data, **kw)

    def delete (self):
        for table in read_tables ():
            fields = table.get_fields ()
            for key in fields.keys ():
                if not isinstance (fields[key][0], storm.references.Reference):
                    continue
                remote = fields[key][0]._remote_key
                if isinstance (remote, basestring):
                    if remote.split('.')[0] != self.__class__.__name__:
                        continue
                elif isinstance (remote, storm.properties.PropertyColumn):
                    if remote.table.__name__ != self.__class__.__name__:
                        continue
                elif (isinstance (remote, tuple) and len(remote) > 0 and
                      isinstance (remote[0], storm.properties.PropertyColumn)):
                    if remote[0].table.__name__ != self.__class__.__name__:
                        continue
                else:
                    continue
                sel = table.select (fields[key][0] == self)
                for rec in sel:
                    rec.delete ()
        blip.utils.log ('Deleting %s' % self)
        self.__blip_store__.remove (self)


class BlipRecord (BlipModel):
    __abstract__ = True
    ident = ShortText (primary=True)
    type = ShortText ()

    name = Unicode ()
    desc = Unicode ()

    icon_dir = Unicode ()
    icon_name = Unicode ()

    email = Unicode ()
    web = Unicode ()

    data = Pickle (default_factory=dict)

    updated = DateTime ()
    
    # Whether Blip should link to this thing, i.e. whether it
    # displays pages for this kind of thing.  Subclasses will
    # want to override this, possibly with a property.
    linkable = True

    # Whether Blip can watch this thing.  Subclasses will want
    # to override this, possible with a property.
    watchable = False

    def __init__ (self, ident, type, **kw):
        kw['ident'] = ident
        kw['type'] = type
        BlipModel.__init__ (self, **kw)

    def __repr__ (self):
        if self.type != None:
            return '%s %s' % (self.type, self.ident)
        else:
            return '%s %s' % (self.__class__.__name__, self.ident)

    @property
    def blip_url (self):
        return blinq.config.web_root_url + self.ident[1:]

    @property
    def icon_url (self):
        if self.icon_name == None or self.icon_dir.startswith ('__icon__'):
            return None
        elif self.icon_dir == None:
            return blinq.config.web_files_url + 'icons/' + self.icon_name + '.png'
        else:
            return blinq.config.web_files_url + 'icons/' + self.icon_dir + '/' + self.icon_name + '.png'

    @property
    def title_default (self):
        return self.ident.split('/')[-1]

    @property
    def title (self):
        if self.name is None or self.name == '':
            return self.title_default
        return self.name

    @classmethod
    def get_or_create (cls, ident, type, **kw):
        record = cls.get (ident)
        if record != None:
            return record
        return cls (ident, type, **kw)

    def set_relations (self, cls, rels):
        old = list (self.__blip_store__.find (cls, subj_ident=self.ident))
        olddict = {}
        for rel in old:
            olddict[rel.pred_ident] = rel
        for rel in rels:
            olddict.pop (rel.pred_ident, None)
        oldids = [old.id for old in olddict.values()]
        self.__blip_store__.find (cls, cls.id.is_in (oldids)).remove ()


class BlipRelation (BlipModel):
    __abstract__ = True
    id = Int (primary=True)
    subj_ident = Unicode ()
    pred_ident = Unicode ()

    def __repr__ (self):
        return '%s %s %s' % (self.__class__.__name__, self.subj_ident, self.pred_ident)

    @classmethod
    def set_related (cls, subj, pred, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        rel = store.find (cls, subj_ident=subj.ident, pred_ident=pred.ident).one ()
        if rel == None:
            rel = cls (subj=subj, pred=pred, __blip_store__=store)
        if len(kw) > 0:
            for k, v in kw.items():
                setattr (rel, k, v)
        return rel

    @classmethod
    def get_or_create (cls, **kw):
        record = list(cls.select (**kw))
        print record
        if record != None:
            return record
        return cls (**kw)

    @classmethod
    def select_related (cls, subj=None, pred=None, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        if subj != None and pred != None:
            rel = store.find (cls, subj_ident=subj.ident, pred_ident=pred.ident)
            return rel
        elif subj != None:
            # FIXME STORM: django has select_related
            return store.find (cls, subj_ident=subj.ident)
        elif pred != None:
            # FIXME STORM
            return store.find (cls, pred_ident=pred.ident)
        else:
            return storm.store.EmptyResultSet ()

    @classmethod
    def get_related (cls, subj=None, pred=None):
        sel = cls.select_related (subj=subj, pred=pred)
        return list(sel)

    @classmethod
    def count_related (cls, subj=None, pred=None):
        sel = cls.select_related (subj=subj, pred=pred)
        return sel.count ()


################################################################################
## Records


class ReleaseSet (BlipRecord):
    parent_ident = ShortText ()
    parent = Reference (parent_ident, 'ReleaseSet.ident')

    subsets = ReferenceSet ('ReleaseSet.ident', parent_ident)


class Project (BlipRecord):
    score = Int ()
    score_diff = Int ()

    default_ident = ShortText ()
    default = Reference (default_ident, 'Branch.ident')


class Branch (BlipRecord):
    subtype = ShortText ()
    parent_ident = ShortText ()
    parent = Reference (parent_ident, 'Branch.ident')
    project_ident = ShortText ()
    project = Reference (project_ident, 'Project.ident')
    error = Unicode ()

    scm_type = ShortText ()
    scm_server = ShortText ()
    scm_module = ShortText ()
    scm_branch = ShortText ()
    scm_path = ShortText ()
    scm_dir = ShortText ()
    scm_file = ShortText ()

    bug_database = ShortText ()

    score = Int ()
    score_diff = Int ()

    mod_datetime = DateTime ()
    mod_person_ident = ShortText ()
    mod_person = Reference (mod_person_ident, 'Entity.ident')

    def __init__ (self, ident, type, **kw):
        kw['project_ident'] = u'/'.join (ident.split('/')[:-1])
        proj = Project.get_or_create (kw['project_ident'], type)
        BlipRecord.__init__ (self, ident, type, **kw)
        if self.is_default:
            proj.default = self

    @property
    def title_default (self):
        id = self.ident.split('/')[-2]
        if self.type == 'Domain':
            if id == 'po':
                return self.scm_module
            else:
                return blip.utils.gettext ('%s (%s)') % (self.scm_module, id)
        return id

    @property
    def branch_module (self):
        return blip.utils.gettext ('%s (%s)') % (self.scm_module, self.scm_branch)

    @property
    def branch_title (self):
        return blip.utils.gettext ('%s (%s)') % (self.title, self.scm_branch)

    @property
    def watchable (self):
        return self.type == 'Module'

    @property
    def is_default (self):
        return self.scm_branch == blip.scm.Repository.get_default_branch (self.scm_type)

    @classmethod
    def _select_args (cls, *args, **kw):
        args = list (args)
        rset = kw.pop ('parent_in_set', None)
        if rset != None:
            args.append (cls.parent_ident == SetModule.pred_ident)
            args.append (SetModule.subj_ident == rset.ident)
        return (args, kw)

    @classmethod
    def select (cls, *args, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        args, kw = cls._select_args (*args, **kw)
        return store.find (cls, *args, **kw)

    @classmethod
    def select_with_mod_person (cls, *args, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        join = LeftJoin (cls, Entity, cls.mod_person_ident == Entity.ident)
        using = kw.pop ('using', None)
        if using is not None:
            if isinstance (using, list):
                using = tuple (using)
            elif isinstance (using, tuple):
                pass
            else:
                using = (using,)
            join = (join,) + using
        args, kw = cls._select_args (*args, **kw)
        kwarg = storm.store.get_where_for_args ([], kw, cls)
        if kwarg != storm.store.Undef:
            args.append (kwarg)
        return store.using (join).find((cls, Entity), *args)

    @classmethod
    def select_with_output_file (cls, *args, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        joinon = (cls.ident == OutputFile.ident)
        on = kw.pop ('on', None)
        if on != None:
            joinon = And (joinon, on)
        join = LeftJoin (cls, OutputFile, joinon)
        using = kw.pop ('using', None)
        if using is not None:
            if isinstance (using, list):
                using = tuple (using)
            elif isinstance (using, tuple):
                pass
            else:
                using = (using,)
            join = (join,) + using
        args, kw = cls._select_args (*args, **kw)
        kwarg = storm.store.get_where_for_args ([], kw, cls)
        if kwarg != storm.store.Undef:
            args.append (kwarg)
        return store.using (join).find((cls, OutputFile), *args)

    @classmethod
    def select_with_statistic (cls, stattype, *args, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        if isinstance (stattype, basestring):
            stattype = [stattype]
        args = [arg for arg in args]
        for key in kw.keys ():
            args.append (getattr (cls, key) == kw[key])
        tables = [cls]
        for stype in stattype:
            stat = ClassAlias (Statistic)
            tables.append (stat)
            args.append (stat.branch_ident == cls.ident)
            args.append (stat.type == stype)
            args.append (stat.daynum == Select (Max (stat.daynum),
                                                where=And (stat.branch_ident == cls.ident,
                                                           stat.type == stype),
                                                tables=stat))
        # FIXME: left join
        sel = store.find (tuple(tables), *args)
        return sel

    def select_children (self, type):
        return self.__class__.select (type=type, parent=self)

    def set_children (self, type, children):
        old = list(Branch.select (type=type, parent=self))
        olddict = {}
        for rec in old:
            olddict[rec.ident] = rec
        for child in children:
            olddict.pop (child.ident, None)
            child.parent = self
        for old in olddict.values():
            old.delete ()


class Entity (BlipRecord):
    parent_ident = ShortText ()
    parent = Reference (parent_ident, 'Entity.ident')
    nick = Unicode ()
    score = Int ()
    score_diff = Int ()

    @classmethod
    def get (cls, ident, alias=True, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        ent = store.get (cls, ident)
        if ent == None and alias:
            ent = Alias.get (ident, __blip_store__=store)
            if ent != None:
                ent = ent.entity
        return ent

    @classmethod
    def get_or_create_email (cls, email, **kw):
        if email.find('@') < 0:
            ident = u'/person/' + email + u'@'
            ent = cls.get_or_create (ident, u'Person', **kw)
        else:
            ent = cls.get_or_create (u'/person/' + email, u'Person', **kw)
        ent.extend (email=email)
        return ent

    def select_children (self):
        return self.__class__.select (parent=self)

    @property
    def title_default (self):
        if self.email is not None:
            return self.email
        return self.ident.split('/')[-1]

    @property
    def linkable (self):
        return self.type != 'Ghost'

    @property
    def watchable (self):
        return self.type == 'Module'


class Alias (BlipRecord):
    entity_ident = ShortText ()
    entity = Reference (entity_ident, 'Entity.ident')

    def delete (self):
        raise WillNotDelete ('Blip will not delete aliases')

    @classmethod
    def update_alias (cls, entity, ident):
        updated = False

        alias = cls.get (ident)
        if alias == None:
            updated = True
            alias = Alias (ident, u'Alias')
        alias.entity = entity

        old = Entity.get (ident, alias=False)
        if old == None:
            return updated

        blip.utils.log ('Copying %s to %s' % (ident, entity.ident))
        pdata = {}
        for pkey, pval in old.data.items():
            pdata[pkey] = pval
        pdata['name'] = old.name
        pdata['desc'] = old.desc
        pdata['icon_dir'] = old.icon_dir
        pdata['icon_name'] = old.icon_name
        pdata['email'] = old.email
        pdata['web'] = old.web
        pdata['nick'] = old.nick
        pdata['mod_score'] = old.mod_score
        entity.extend (pdata)

        # Revision and ForumPost record historical data, so we record the
        # alias of the entity they pointed to.
        revs = Revision.select (person=old)
        if not updated and revs.count() > 0:
            updated = True
        revs.set (person=entity, alias=alias)

        posts = ForumPost.select (author=old)
        if not updated and posts.count() > 0:
            updated = True
        posts.set (author=entity, alias=alias)

        # The rest of these don't need the historical alias to be recorded.
        rels = DocumentEntity.select (pred=old)
        if not updated and rels.count() > 0:
            updated = True
        rels.set (pred=entity)

        rels = ModuleEntity.select (pred=old)
        if not updated and rels.count() > 0:
            updated = True
        rels.set (pred=entity)

        rels = TeamMember.select (subj=old)
        if not updated and rels.count() > 0:
            updated = True
        rels.set (subj=entity)

        rels = TeamMember.select (pred=old)
        if not updated and rels.count() > 0:
            updated = True
        rels.set (pred=entity)

        branches = Branch.select (mod_person=old)
        if not updated and branches.count() > 0:
            updated = True
        branches.set (mod_person=entity)

        watches = AccountWatch.select (ident=old.ident)
        if not updated and watches.count() > 0:
            updated = True
        watches.set (ident=entity.ident)

        # FIXME STORM: we disallowed Entity.delete
        old.delete()

        return updated


class Forum (BlipRecord):
    score = Int ()
    score_diff = Int ()

    def delete (self):
        raise WillNotDelete ('Blip will not delete forums')


class ForumPost (BlipRecord):
    forum_ident = ShortText ()
    forum = Reference (forum_ident, 'Forum.ident')

    author_ident = ShortText ()
    author = Reference (author_ident, 'Entity.ident')

    alias_ident = ShortText ()
    alias = Reference (alias_ident, 'Alias.ident')

    parent_ident = ShortText ()
    parent = Reference (parent_ident, 'ForumPost.ident')

    datetime = DateTime ()
    weeknum = Int ()

    def __init__ (self, ident, type, **kw):
        if kw.has_key ('datetime'):
            kw['weeknum'] = blip.utils.weeknum (kw['datetime'])
        BlipRecord.__init__ (self, ident, type, **kw)

    def log_create (self):
        pass

    def delete (self):
        raise WillNotDelete ('Blip will not delete forum posts')


# FIXME
class Component (BlipModel):
    __storm_table__ = 'Component'
    ident = ShortText (primary=True)
    product = Unicode ()
    tracker = Unicode ()
    name = Unicode ()
    default_owner = Unicode ()
    default_qa = Unicode ()

    @classmethod
    def get_or_create (cls, ident, **kw):
        record = cls.get (ident)
        if record != None:
            return record
        return cls (ident=ident)


# FIXME
class Issue (BlipModel):
    __storm_table__ = 'Issue'
    ident = ShortText (primary=True)
    bug_id = Int()
    datetime = DateTime ()
    severity = Unicode()
    priority = Unicode()
    status = Unicode()
    resolution = Unicode()
    comp_ident = Unicode()
    comp = Reference (comp_ident, Component.ident)
    summary = Unicode()
    owner = Unicode()

    def __cmp__(self, other):
        if hasattr(other, 'datetime'):
            return cmp(self.datetime, other.datetime)
        return 1

    @classmethod
    def get_or_create (cls, ident, **kw):
        record = cls.get (ident)
        if record != None:
            return record
        return cls (ident=ident)

    def get_last_change(self):
        store = get_store()
        cls = self.__class__
        query = store.find(cls, cls.bug_id == self.bug_id, cls.time < self.time)
        return query.order_by(Desc(cls.time)).first()


# FIXME
class Cache(BlipModel):
    ident = ShortText (primary=True)
    value = Pickle (default_factory=dict)
    mtime = Int ()


################################################################################
## Relations


class Documentation (BlipRelation):
    subj_ident = ShortText ()
    pred_ident = ShortText ()
    subj = Reference (subj_ident, Branch.ident)
    pred = Reference (pred_ident, Branch.ident)


class DocumentEntity (BlipRelation):
    subj_ident = ShortText ()
    pred_ident = ShortText ()
    subj = Reference (subj_ident, Branch.ident)
    pred = Reference (pred_ident, Entity.ident)
    maintainer = Bool (default=False)
    author = Bool (default=False)
    editor = Bool (default=False)
    publisher = Bool (default=False)


class ModuleComponents (BlipRelation):
    subj_ident = ShortText ()
    pred_ident = ShortText ()
    subj = Reference (subj_ident, Branch.ident)
    pred = Reference (pred_ident, Component.ident)


class ModuleDependency (BlipRelation):
    subj_ident = ShortText ()
    pred_ident = ShortText ()
    subj = Reference (subj_ident, Branch.ident)
    pred = Reference (pred_ident, Branch.ident)
    direct = Bool ()


class ModuleEntity (BlipRelation):
    subj_ident = ShortText ()
    pred_ident = ShortText ()
    subj = Reference (subj_ident, Branch.ident)
    pred = Reference (pred_ident, Entity.ident)
    maintainer = Bool (default=False)


class SetModule (BlipRelation):
    subj_ident = ShortText ()
    pred_ident = ShortText ()
    subj = Reference (subj_ident, ReleaseSet.ident)
    pred = Reference (pred_ident, Branch.ident)


class TeamMember (BlipRelation):
    subj_ident = ShortText ()
    pred_ident = ShortText ()
    subj = Reference (subj_ident, Entity.ident)
    pred = Reference (pred_ident, Entity.ident)
    coordinator = Bool (default=False)


################################################################################
## User Accounts


class Account (BlipModel):
    __blip_store__ = get_store ('account')

    username = ShortText (primary=True)
    password = ShortText ()

    person_ident = ShortText ()
    person = Reference (person_ident, Entity.ident)

    email = ShortText ()

    check_time = DateTime ()
    check_type = ShortText ()
    check_hash = ShortText ()

    data = Pickle (default_factory=dict)


class Login (BlipModel):
    __storm_primary__ = 'username', 'ipaddress'
    __blip_store__ = get_store ('account')

    username = ShortText ()
    account = Reference (username, Account.username)

    token = ShortText ()
    datetime = DateTime ()
    ipaddress = ShortText ()

    @classmethod
    def set_login (cls, account, token, ipaddress):
        ipaddress = blip.utils.utf8dec (ipaddress)
        login = cls.__blip_store__.get (cls, (account.username, ipaddress))
        if login is None:
            login = cls (username=account.username, token=token, ipaddress=ipaddress,
                         datetime=datetime.datetime.utcnow())
        else:
            login.token = token
            login.datetime = datetime.datetime.utcnow()
        flush (cls)
        commit (cls)
        return login

    @classmethod
    def get_login (cls, token, ipaddress):
        store = get_store ('login')
        store.block_implicit_flushes ()
        ipaddress = blip.utils.utf8dec (ipaddress)
        login = store.find (cls, token=token, ipaddress=ipaddress)
        try:
            login = login[0]
            now = datetime.datetime.utcnow()
            if (now - login.datetime).days > 0:
                store.remove (login)
                return None
            login.datetime = now
            login.account
            store.flush ()
            store.commit ()
        except:
            store.rollback ()
            return None
        return login


class AccountWatch (BlipModel):
    __storm_primary__ = 'username', 'ident'
    __blip_store__ = get_store ('account')

    username = ShortText ()
    account = Reference (username, Account.username)
    ident = ShortText ()

    @classmethod
    def add_watch (cls, username, ident):
        watch = cls.__blip_store__.get (cls, (username, ident))
        if watch is None:
            watch = cls (username=username, ident=ident)
        return watch

    @classmethod
    def has_watch (cls, account, ident):
        return cls.select (account=account, ident=ident).count() > 0


# FIXME
class Message (BlipModel):
    id = Int (primary=True)

    type = ShortText ()
    subj = ShortText ()
    pred = ShortText ()
    count = Int ()

    datetime = DateTime ()
    weeknum = Int ()

    def __init__ (self, *args, **kw):
        if kw.has_key ('datetime'):
            kw['weeknum'] = blip.utils.weeknum (kw['datetime'])
        BlipModel.__init__ (self, **kw)

    def log_create (self):
        pass

    @classmethod
    def make_message (cls, type, subj, pred, dt):
        daystart = datetime.datetime (dt.year, dt.month, dt.day)
        dayend = daystart + datetime.timedelta (days=1)
        if (datetime.datetime.utcnow() - daystart).days > 14:
            return None
        filterargs = [blip.db.Message.type == type,
                      blip.db.Message.datetime >= daystart,
                      blip.db.Message.datetime < dayend,
                      blip.db.Message.subj == subj,
                      blip.db.Message.pred == pred]
        oldmsg = cls.select (*filterargs)
        try:
            oldmsg = oldmsg[0]
        except:
            oldmsg = None
        if oldmsg != None:
            if oldmsg.count == None:
                oldmsg.count = 1
            oldmsg.count = oldmsg.count + 1
            oldmsg.datetime = max (oldmsg.datetime, dt)
            return oldmsg
        msg = cls (type=type, subj=subj, pred=pred, count=1,
                   datetime=dt, weeknum=blip.utils.weeknum(daystart))
        return msg


################################################################################
## Revisions


class Revision (BlipModel):
    ident = ShortText (primary=True)

    project_ident = ShortText ()
    project = Reference (project_ident, Project.ident)

    person_ident = ShortText ()
    person = Reference (person_ident, Entity.ident)

    alias_ident = ShortText ()
    alias = Reference (alias_ident, Alias.ident)

    revision = ShortText ()
    datetime = DateTime ()
    weeknum = Int ()
    comment = Unicode ()

    _file_cache = {}

    # FIXME BELOW
    def __init__ (self, **kw):
        kw['weeknum'] = blip.utils.weeknum (kw['datetime'])
        BlipModel.__init__ (self, **kw)
        Message.make_message (u'commit', self.person_ident, self.project_ident, self.datetime)
        Message.make_message (u'commit', self.project_ident, None, self.datetime)

    def __cmp__(self, other):
        if hasattr(other, 'datetime'):
            return cmp(self.datetime, other.datetime)
        return 1

    def log_create (self):
        pass

    def add_file (self, filename, filerev, prevrev):
        rfile = RevisionFile (revision_ident=self.ident,
                              filename=filename,
                              filerev=filerev,
                              prevrev=prevrev)
        return rfile

    def add_branch (self, branch):
        cnt = RevisionBranch.select (revision_ident=self.ident, branch_ident=branch.ident).count ()
        if cnt == 0:
            RevisionBranch (revision_ident=self.ident, branch_ident=branch.ident)
        rfiles = RevisionFile.select (revision_ident=self.ident)
        for rfile in rfiles:
            Revision._file_cache.setdefault (branch.ident, {})
            if not Revision._file_cache[branch.ident].has_key (rfile.filename):
                Revision._file_cache[branch.ident][rfile.filename] = self
            elif Revision._file_cache[branch.ident][rfile.filename].datetime < self.datetime:
                Revision._file_cache[branch.ident][rfile.filename] = self

    def display_revision (self, branch=None):
        if branch == None:
            branch = self.branch
        if branch.scm_type == 'git':
            return self.revision[:6]
        else:
            return self.revision

    @classmethod
    def flush_file_cache (cls):
        for branch_ident in cls._file_cache.keys ():
            branch_cache = cls._file_cache.pop (branch_ident)
            for filename in branch_cache.keys ():
                revision = branch_cache.pop (filename)
                sel = RevisionFileCache.select_with_revision (branch_ident=branch_ident, filename=filename)
                try:
                    cache, oldrev = sel[0]
                    if revision.datetime > oldrev.datetime:
                        cache.revision_ident = revision.ident
                except IndexError:
                    RevisionFileCache (branch_ident=branch_ident,
                                       filename=filename,
                                       revision_ident=revision.ident)
            flush (RevisionFileCache)

    @classmethod
    def get_last_revision (cls, **kw):
        try:
            ret = cls._get_last_revision_cached (**kw)
        except:
            ret = cls._get_last_revision_expensive (**kw)
        return ret

    @classmethod
    def _get_last_revision_cached (cls, **kw):
        args = []
        files = kw.pop ('files', None)
        if files is not None:
            args.append (Revision.ident == RevisionFileCache.revision_ident)
            if len(files) == 1:
                args.append (RevisionFileCache.filename == files[0])
            else:
                args.append (RevisionFileCache.filename.is_in (files))
        else:
            raise blip.utils.BlipException ('Cannot fetch from file cache')
        for key in kw.keys ():
            if key == 'branch':
                args.append (blip.db.RevisionFileCache.branch_ident == kw[key].ident)
            elif key == 'branch_ident':
                args.append (blip.db.RevisionFileCache.branch_ident == kw[key])
            else:
                raise blip.utils.BlipException ('Cannot fetch from file cache')

        return cls.select (*args).order_by (Desc(Revision.datetime))[0]

    @classmethod
    def _get_last_revision_expensive (cls, **kw):
        ret = None
        # This function is expensive.  To lighten the load a bit, we first
        # restrict the query to the last year.  Failing that, we look at
        # everything.  In tests against SQLite, we get around 30% increase
        # in speed.  We should test this against other databases to see
        # how much of a bottleneck this function is, how much of a speed
        # increase this gets us, and if there's a better first-pass than
        # 52 weeks.
        if not kw.has_key ('week_range'):
            try:
                ret = cls.select_revisions (cls.weeknum > (blip.utils.weeknum() - 52), **kw)[0]
            except IndexError:
                ret = None
        if ret is None:
            try:
                ret = cls.select_revisions (**kw)[0]
            except IndexError:
                ret = None
        return ret
                
    @classmethod
    def select_revisions (cls, *args, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        args = list (args)
        files = kw.pop ('files', None)
        range = kw.pop ('week_range', None)
        if files != None:
            args.append (Revision.ident == RevisionFile.revision_ident)
            if len(files) == 1:
                args.append (RevisionFile.filename == files[0])
            else:
                args.append (RevisionFile.filename.is_in (files))
        if range is not None:
            args.append (Revision.weeknum >= range[0])
            if len(range) > 1 and range[1] is not None:
                args.append (Revision.weeknum <= range[1])
        branch_ident = kw.pop ('branch_ident', None)
        if branch_ident is None:
            branch = kw.pop ('branch', None)
            if branch is not None:
                branch_ident = branch.ident
        if branch_ident is not None:
            args.append (RevisionBranch.revision_ident == cls.ident)
            args.append (RevisionBranch.branch_ident == branch_ident)
        sel = store.find (cls, *args, **kw)
        if files != None:
            sel = sel.group_by (Revision.ident)
        return sel.order_by (Desc (Revision.datetime))

    @classmethod
    def count_revisions (cls, *args, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        args = list (args)
        files = kw.pop ('files', None)
        range = kw.pop ('week_range', None)
        if files is not None:
            args.append (Revision.ident == RevisionFile.revision_ident)
            if len(files) == 1:
                args.append (RevisionFile.filename == files[0])
            else:
                args.append (RevisionFile.filename.is_in (files))
        if range is not None:
            args.append (And (Revision.weeknum >= range[0],
                              Revision.weeknum <= range[1]))
        branch_ident = kw.pop ('branch_ident', None)
        if branch_ident is None:
            branch = kw.pop ('branch', None)
            if branch is not None:
                branch_ident = branch.ident
        if branch_ident is not None:
            args.append (RevisionBranch.revision_ident == cls.ident)
            args.append (RevisionBranch.branch_ident == branch_ident)
        sel = store.find (cls, *args, **kw)
        return sel.count (Revision.ident, distinct=True)


class RevisionBranch (BlipModel):
    __storm_primary__ = 'revision_ident', 'branch_ident'

    revision_ident = ShortText ()
    revision = Reference (revision_ident, Revision.ident)

    branch_ident = ShortText ()
    branch = Reference (branch_ident, Branch.ident)

    def log_create (self):
        pass


class RevisionFile (BlipModel):
    __storm_primary__ = 'revision_ident', 'filename'

    revision_ident = ShortText ()
    revision = Reference (revision_ident, Revision.ident)

    filename = Unicode ()
    filerev = ShortText ()
    prevrev = ShortText ()

    def log_create (self):
        pass


class RevisionFileCache (BlipModel):
    __storm_primary__ = 'branch_ident', 'filename'

    branch_ident = ShortText ()
    filename = Unicode ()

    revision_ident = ShortText ()
    revision = Reference (revision_ident, Revision.ident)

    def log_create (self):
        pass

    @classmethod
    def select_with_revision (cls, *args, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        args = list(args)
        files = kw.pop ('files', None)
        if files is not None:
            if len(files) == 1:
                args.append (RevisionFileCache.filename == files[0])
            else:
                args.append (RevisionFileCache.filename.is_in (files))
        branch = kw.pop ('branch', None)
        if branch is not None:
            kw['branch_ident'] = branch.ident
        kwarg = storm.store.get_where_for_args ([], kw, cls)
        if kwarg != storm.store.Undef:
            args.append (kwarg)
        args.append (cls.revision_ident == Revision.ident)
        sel = store.find ((cls, Revision), *args)
        return sel


################################################################################
## Other Tables

class Statistic (BlipModel):
    __storm_primary__ = 'branch_ident', 'daynum', 'type'

    branch_ident = ShortText ()
    branch = Reference (branch_ident, Branch.ident)
    daynum = Int ()
    type = ShortText ()
    stat1 = Int ()
    stat2 = Int ()
    total = Int ()

    def log_create (self):
        pass

    @classmethod
    def select_statistic (cls, branch, type):
        stat = cls.select (branch=branch, type=type)
        return stat.order_by (Desc (Statistic.daynum))

    @classmethod
    def set_statistic (cls, branch, daynum, type, stat1, stat2, total):
        res = cls.select (branch=branch, daynum=daynum, type=type)
        try:
            res = res[0]
            res.stat1 = stat1
            res.stat2 = stat2
            res.total = total
            return res
        except IndexError:
            return cls (branch=branch, daynum=daynum, type=type,
                        stat1=stat1, stat2=stat2, total=total)


class OutputFile (BlipModel):
    id = Int (primary=True)

    type = ShortText ()
    ident = ShortText ()
    subdir = Unicode ()
    filename = Unicode ()
    source = Unicode ()
    datetime = DateTime ()
    statistic = Int ()
    data = Pickle (default_factory=dict)

    def log_create (self):
        pass

    def get_blip_url (self, subsub=None):
        lst = [self.ident[1:]]
        if self.subdir != None:
            lst.append (self.subdir)
        if subsub != None:
            lst.append (subsub)
        lst.append (self.filename)
        rootdir = blinq.config.web_files_url + self.type + '/'
        return rootdir + '/'.join(lst)
    blip_url = property (get_blip_url)

    def get_file_path (self, subsub=None):
        lst = self.ident[1:].split('/')
        if self.subdir != None:
            lst.append (self.subdir)
        if subsub != None:
            lst.append (subsub)
        lst.append (self.filename)
        rootdir = getattr (blinq.config, 'web_' + self.type + '_dir', None)
        if rootdir == None:
            lst.insert (0, self.type)
            rootdir = blinq.config.web_files_dir
        return os.path.join(rootdir, *lst)


class Timestamp (BlipModel):
    __storm_primary__ = 'filename', 'sourcefunc'
    filename = Unicode ()
    sourcefunc = Unicode ()
    stamp = Int ()

    def log_create (self):
        pass

    class stamped:
        class stampedout (Exception):
            pass
        def __init__ (self, filename, repository):
            self.filename = filename
            self.repository = repository
            self.rel_scm = blip.utils.relative_path (filename, blinq.config.scm_dir)
        def check (self, check):
            self.mtime = int(os.stat(self.filename).st_mtime)
            if check:
                stamp = blip.db.Timestamp.get_timestamp (self.rel_scm)
                if self.mtime <= stamp:
                    blip.utils.log ('Skipping file %s' % self.rel_scm)
                    raise Timestamp.stamped.stampedout(None)
            blip.utils.log ('Processing file %s' % self.rel_scm)
        def __enter__ (self):
            return self
        def __exit__ (self, type, value, tb):
            if type is None:
                Timestamp.set_timestamp (self.rel_scm, self.mtime)
            else:
                if issubclass(type, Timestamp.stamped.stampedout):
                    return True

    @classmethod
    def _get_sourcefunc (cls):
        for frame in inspect.stack():
            mod = inspect.getmodule(frame[0])
            if mod == sys.modules[__name__]:
                continue
            return unicode(mod.__name__ + '.' + frame[3])

    @classmethod
    def set_timestamp (cls, filename, stamp):
        sfunc = cls._get_sourcefunc()
        obj = cls.select (filename=filename, sourcefunc=sfunc)
        try:
            obj = obj[0]
            obj.stamp = int(stamp)
        except IndexError:
            cls (filename=filename, sourcefunc=sfunc, stamp=int(stamp))

    @classmethod
    def get_timestamp (cls, filename):
        sfunc = cls._get_sourcefunc()
        obj = cls.select (filename=filename, sourcefunc=sfunc)
        try:
            return obj[0].stamp
        except IndexError:
            return -1


class Queue (BlipModel):
    ident = ShortText (primary=True)
    cache = {}

    def log_create (self):
        pass

    @classmethod
    def push (cls, ident, **kw):
        if not cls.cache.get (ident, False):
            store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
            if cls.select (cls.ident == ident).count () == 0:
                cls (ident=ident, __blip_store__=store)
            cls.cache[ident] = True

    @classmethod
    def pop (cls, ident=None, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        try:
            if ident is not None:
                sel = cls.select(cls.ident.like (ident))[0]
            else:
                sel = cls.select()[0]
            ident = sel.ident
            store.remove (sel)
            return ident
        except:
            return None

    @classmethod
    def remove (cls, ident, **kw):
        store = get_store (kw.pop ('__blip_store__', cls.__blip_store__))
        try:
            rec = cls.select (ident=ident)
            store.remove (rec)
        except:
            pass
