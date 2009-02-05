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

import cPickle
import datetime
import inspect
import os
import os.path
import sys
import time

os.environ['DJANGO_SETTINGS_MODULE'] = 'pulse.config'
import django
import django.db
import django.db.backends.util
from django.db import models
from django.db.models import signals
from django.db.models.base import ModelBase
from django.dispatch import dispatcher

import pulse.config
import pulse.scm
import pulse.utils


# Django changed this keyword argument in 1.0, and I want to keep
# compatibility with 0.96 for now.
if django.VERSION[0] >= 1:
    maxlength200 = {'max_length' : 200}
    maxlength80 = {'max_length' : 80}
    maxlength20 = {'max_length' : 20}
else:
    maxlength200 = {'maxlength' : 200}
    maxlength80 = {'maxlength' : 80}
    maxlength20 = {'maxlength' : 20}


################################################################################
## Abusing Django

# Django doesn't have any types mapped to blob, so we have to
# add that mapping in ourselves.  Note that this should work
# with SQLite and MySQL.  To support other databases, we'll
# have to switch on DATABASE_ENGINE here.
try:
    data_types = django.db.get_creation_module().DATA_TYPES
except:
    data_types = django.db.connection.creation.data_types
data_types['BlobField'] = 'blob'

# We have to do this to avoid encoding errors.  Note that
# I've not yet tested with any other databases.  We might
# have to add other hacks here for other databases.
if pulse.config.DATABASE_ENGINE == 'sqlite3':
    from django.db.backends.sqlite3.base import Database
    Database.register_converter ('blob', lambda s: s)


################################################################################
## Debugging and Logging

class PulseDebugCursor (object):
    def __init__ (self, cursor, db):
        self.cursor = cursor
        self.db = db

    debug_select_count = 0
    debug_select_time = 0
    was_insert = False

    def execute (self, sql, params=()):
        if isinstance (params, dict):
            ps = params
        else:
            ps = []
            for p in params:
                if isinstance (p, basestring):
                    try:
                        ps.append (str(p))
                    except:
                        ps.append ('...')
                else:
                    ps.append (p)
            ps = tuple(ps)
        text = sql % ps

        select = False
        if text.startswith ('SELECT COUNT'):
            select = True
        elif text.startswith ('SELECT 1 '):
            select = True
        elif text.startswith ('SELECT '):
            select = True
            i = text.index (' FROM ')
            ellip = '...'
            try:
                j = text.index ('(SELECT ')
                if j < i:
                    ellip = '... '
                    i = j
            except ValueError:
                pass
            text = text[:7] + ellip + text[i:]
        elif text.startswith ('UPDATE '):
            PulseDebugCursor.was_insert = False
            i = text.index (' SET ')
            j = text.index (' WHERE ')
            text = text[:i+5] + '...' + text[j:]
        elif text.startswith ('INSERT INTO '):
            PulseDebugCursor.was_insert = True
            i = text[12:].index(' ')
            text = text[:13+i] + '...'
        start = time.time()
        try:
            return self.cursor.execute (sql, params)
        finally:
            if getattr (pulse.config, 'debug_db', False):
                stop = time.time()
                diff = stop - start
                if select:
                    PulseDebugCursor.debug_select_count += 1
                    PulseDebugCursor.debug_select_time += diff
                print '  ' + ('%.3f' % diff) + ' -- ' + text

    def execute_many (self, sql, param_list):
        return self.cursor.executemany (sql, param_list)

    def __getattr__ (self, attr):
        if self.__dict__.has_key (attr):
            return self.__dict__[attr]
        else:
            return getattr (self.cursor, attr)

django.db.backends.util.CursorDebugWrapper = PulseDebugCursor

def __pulse_log_save (instance, **kw):
    if not PulseDebugCursor.was_insert:
        return
    if isinstance (instance, PulseRecord):
        if isinstance (instance, Alias):
            pulse.utils.log ('Created Alias %s' % instance.ident)
        else:
            pulse.utils.log ('Created %s %s' % (instance.type, instance.ident))
    elif isinstance (instance, PulseRelation):
        pulse.utils.log ('Created %s %s : %s' %
                         (instance.__class__.__name__,
                          instance.subj.ident, instance.pred.ident))

def __pulse_log_delete (instance, **kw):
    if isinstance (instance, PulseRecord):
        pulse.utils.log ('Deleted %s %s' % (instance.type, instance.ident))
    elif isinstance (instance, PulseRelation):
        pulse.utils.log ('Deleted %s %s : %s' %
                         (instance.__class__.__name__,
                          instance.subj.ident, instance.pred.ident))

try:
    dispatcher.connect (__pulse_log_save, signal=signals.post_save)
    dispatcher.connect (__pulse_log_delete, signal=signals.post_delete)
except:
    signals.post_save.connect (__pulse_log_save)
    signals.post_delete.connect (__pulse_log_delete)


################################################################################
## Custom Fields

class BitMaskField (models.fields.IntegerField):
    def __init__ (self, *args, **kw):
        self.bits = args
        models.fields.IntegerField.__init__ (self, **kw)

    def get_internal_type (self):
        return 'IntegerField'

    def has_default (self):
        return True

    def get_default (self):
        return 0


class PickleField (models.fields.Field):
    def get_internal_type (self):
        return 'BlobField'

    def get_db_prep_save (self, value):
        return cPickle.dumps (value)
        pass

    def has_default (self):
        return True

    def get_default (self):
        return {}


################################################################################
##

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
        return cls.get_cached (ident)
    except:
        return None


################################################################################
## Base Class

class PulseModelBase (ModelBase):
    def __new__ (meta, name, bases, attrs):
        # We use extra base classes like PulseRecord to insert common
        # database fields.  These base classes don't actually inherit
        # from models.Model because Django behaves badly when they do.
        # So we have to manually insert their extra fields into attrs.
        for base in bases:
            for attname, attval in base.__dict__.items():
                if isinstance (attval, models.fields.Field):
                    attrs[attname] = attval

        # Now let ModelBase.__new__ do its thing
        cls = super (PulseModelBase, meta).__new__ (meta, name, bases, attrs)

        # Special-case our custom field types
        for fname, field in attrs.items():
            if isinstance (field, PickleField):
                PulseModelBase.add_pickle_field (cls, fname)
            elif isinstance (field, BitMaskField):
                PulseModelBase.add_bitmask_field (cls, fname, field)

        # I never like the way ORMs mangle my class names for names
        # of database tables.  This lets me override it all at once,
        # instead of setting it on each individual class.
        cls._meta.db_table = name

        return cls

    # Magic for PickleField
    # Digging through the Django source code reveals no better way
    # of doing this.  Django's ModelBase metaclass doesn't actually
    # put fields into the class, but instead stores them in _meta.
    # This means we're free to turn those into properties, which
    # allows us to ensure that pickled data gets unpickled.
    #
    # Note that, due to the way Django constructs these objects,
    # there's no good way to determine if application code set
    # the attribute or if it's data from the database.  Instead,
    # we just assume that strings are pickled data.  This means
    # you can't store a string in a PickleField.
    @staticmethod
    def add_pickle_field (cls, fname):
        def set_pickle_prop (self, value):
            if isinstance (value, basestring):
                self.__dict__[fname] = cPickle.loads (str(value))
            else:
                self.__dict__[fname] = value
        setattr (cls, fname,
                 property (lambda self: self.__dict__[fname],
                           set_pickle_prop))

    # Magic for BitMaskField
    @staticmethod
    def add_bitmask_field (cls, fname, field):
        for str, bit in zip(field.bits, range(len(field.bits))):
            PulseModelBase.add_bitmask_bit (cls, fname, field, str, bit)
    @staticmethod
    def add_bitmask_bit (cls, fname, field, str, bit):
        val = 1 << bit
        def is_func (self):
            return (getattr (self, fname) & val) != 0
        setattr (cls, 'is_' + str, is_func)
        def set_func (self, tf):
            if tf == True:
                setattr (self, fname, getattr (self, fname) | val)
            else:
                setattr (self, fname, getattr (self, fname) & (sys.maxint ^ val))
        setattr (cls, 'set_' + str, set_func)


class PulseRecord (object):
    def delete (self):
        self.delete_relations ()
        models.Model.delete (self)

    # Delete custom relations.
    def delete_relations (self):
        for cls in sys.modules[__name__].__dict__.values():
            if isinstance (cls, PulseModelBase) and issubclass (cls, PulseRelation):
                for field in cls._meta.fields:
                    if isinstance (field, models.ForeignKey):
                        if field.rel.to == self.__class__:
                            for rel in list(cls.objects.filter(**{field.name : self})):
                                rel.delete()
        for of in OutputFile.objects.filter (ident=self.ident):
            of.delete()

    # Whether Pulse should link to this thing, i.e. whether it
    # displays pages for this kind of thing.  Subclasses will
    # want to override this, possibly with a property.
    linkable = True

    # Whether Pulse can watch this thing.  Subclasses will want
    # to override this, possible with a property.
    watchable = False

    # Convenience routine to get objects that might already exist
    @classmethod
    def get_record (cls, ident, type):
        rec, cr = cls.objects.get_or_create (ident=ident, type=type)
        return rec

    cached_records = {}

    @classmethod
    def get_cached (cls, record_id):
        cls.cached_records.setdefault (cls, {})
        if not cls.cached_records[cls].has_key (record_id):
            if isinstance (record_id, basestring):
                cls.cached_records[cls][record_id] = cls.objects.get (ident=record_id)
            else:
                cls.cached_records[cls][record_id] = cls.objects.get (id=record_id)
        return cls.cached_records[cls][record_id]

    @classmethod
    def set_cached (cls, record_id, record):
        cls.cached_records.setdefault (cls, {})
        cls.cached_records[cls][record_id] = record
        return cls.cached_records[cls][record_id]

    # Convenience routine to set multiple attributes
    def update (self, data={}, **kw):
        for key, val in data.items() + kw.items():
            try:
                field = self._meta.get_field (key)
                if isinstance (field, PickleField):
                    dd = getattr (self, key, {})
                    if not isinstance (val, dict):
                        val = {'C' : val}
                    for k, v in val.items():
                        dd[k] = v
                    setattr (self, key, dd)
                else:
                    setattr (self, key, val)
            except models.fields.FieldDoesNotExist:
                self.data[key] = val

    def extend (self, data={}, **kw):
        for key, val in data.items() + kw.items():
            try:
                field = self._meta.get_field (key)
                if isinstance (field, PickleField):
                    dd = getattr (self, key, {})
                    if not isinstance (val, dict):
                        val = {'C' : val}
                    for k, v in val.items():
                        dd.setdefault (k, v)
                    setattr (self, key, dd)
                else:
                    dd = getattr(self, key, None)
                    if dd == None or dd == '':
                        setattr (self, key, val)
            except models.fields.FieldDoesNotExist:
                if self.data.get (key) != None:
                    self.data[key] = val

    # Sets the relations of a given type of a PulseRecord to those
    # given in rels, where rels is a list of PulseRelation objects
    # that have already been created.  Basically, this asserts that
    # rels are the only relations of a type for self, and removes
    # any other stale relations.
    def set_relations (self, cls, rels):
        old = list(cls.objects.filter (subj=self))
        olddict = {}
        for rel in old:
            olddict[rel.pred.ident] = rel
        for rel in rels:
            olddict.pop (rel.pred.ident, None)
        for old in olddict.values():
            old.delete ()
        pass


    def get_localized_name (self):
        # FIXME: i18n
        return self.name.get('C')
    localized_name = property (get_localized_name)

    def get_localized_desc (self):
        # FIXME: i18n
        return self.desc.get('C')
    localized_desc = property (get_localized_desc)

    def get_pulse_url (self):
        return pulse.config.web_root + self.ident[1:]
    pulse_url = property (get_pulse_url)

    def get_icon_url (self):
        if self.icon_name == None or self.icon_dir.startswith ('__icon__'):
            return None
        elif self.icon_dir == None:
            return pulse.config.icons_root + self.icon_name + '.png'
        else:
            return pulse.config.icons_root + self.icon_dir + '/' + self.icon_name + '.png'
    icon_url = property (get_icon_url)

    def get_title_default (self):
        return self.ident.split('/')[-1]
    def get_title (self):
        if self.name == {}:
            return self.get_title_default ()
        return self.localized_name
    title = property (get_title)


    # Common database fields
    ident = models.CharField (**maxlength200)
    type = models.CharField (**maxlength80)

    name = PickleField ()
    desc = PickleField ()

    icon_dir = models.CharField (null=True, **maxlength200)
    icon_name = models.CharField (null=True, **maxlength80)

    email = models.EmailField (null=True)
    web = models.URLField (verify_exists=False, null=True)

    data = PickleField ()


class PulseRelation (object):
    @classmethod
    def set_related (cls, subj, pred, **kw):
        rel, cr = cls.objects.get_or_create (subj=subj, pred=pred)
        if len(kw) > 0:
            for k, v in kw.items():
                setattr (rel, k, v)
            rel.save()
        return rel

    @classmethod
    def get_related (cls, subj=None, pred=None):
        if subj != None and pred != None:
            rel = cls.objects.filter (subj=subj, pred=pred)
            try:
                return rel[0]
            except IndexError:
                return False
        elif subj != None:
            return list(cls.objects.filter (subj=subj).select_related(depth=1))
        elif pred != None:
            return list(cls.objects.filter (pred=pred).select_related(depth=1))
        else:
            return None

    @classmethod
    def get_one_related (cls, subj=None, pred=None):
        if subj != None and pred != None:
            rel = cls.objects.filter (subj=subj, pred=pred)
        elif subj != None:
            rel = cls.objects.filter (subj=subj)
        elif pred != None:
            rel = cls.objects.filter (pred=pred)
        else:
            return None
        try:
            return rel.select_related()[0]
        except IndexError:
            return None

    @classmethod
    def count_related (cls, subj=None, pred=None):
        if subj != None and pred != None:
            return cls.objects.filter (subj=subj, pred=pred).count()
        elif subj != None:
            return cls.objects.filter (subj=subj).count()
        elif pred != None:
            return cls.objects.filter (pred=pred).count()
        else:
            return 0


################################################################################
## Records

class Record (PulseRecord, models.Model):
    __metaclass__ = PulseModelBase


class ReleaseSet (PulseRecord, models.Model):
    __metaclass__ = PulseModelBase
    parent = models.ForeignKey ('ReleaseSet', related_name='subsets', null=True)


class Branchable (PulseRecord, models.Model):
    __metaclass__ = PulseModelBase

    ## ident schemas per-type
    ## Branch idents have /<branch> appended
    # Module       /mod/<server>/<module>
    # Document     /doc/<server>/<module>/<document>  (gnome-doc-utils)
    #              /ref/<server>/<module>/<document>  (gtk-doc)
    # Application  /app/<server>/<module>/<app>
    # Capplet      /capplet/<server>/<module>/<capplet>
    # Applet       /applet/<server>/<module>/<applet>
    # Library      /lib/<server>/<module>/<lib>
    # Plugin       /ext/<server>/<module>/<ext>
    # Domain       /i18n/<server>/<module>/<domain>
    # Translation  /l10n/<lang>/i18n/<server>/<module>/<domain>
    #              /l10n/<lang>/doc/<server>/<module>/<document>
    #              /l10n/<lang>/ref/<server>/<module>/<document>
    scm_type = models.CharField (null=True, **maxlength20)
    scm_server = models.CharField (null=True, **maxlength200)
    scm_module = models.CharField (null=True, **maxlength80)
    scm_path = models.CharField (null=True, **maxlength200)
    scm_dir = models.CharField (null=True, **maxlength200)
    scm_file = models.CharField (null=True, **maxlength80)

    def get_default (self):
        rec = self.branches.filter (scm_branch=pulse.scm.default_branches.get(self.scm_type))
        try:
            rec = rec[0]
        except:
            rec = None
        return rec


class Branch (PulseRecord, models.Model):
    __metaclass__ = PulseModelBase
    subtype = models.CharField (null=True, **maxlength80)
    parent = models.ForeignKey ('Branch', related_name='children', null=True)
    branchable = models.ForeignKey ('Branchable', related_name='branches', null=True)
    error = models.CharField (null=True, **maxlength200)

    scm_type = models.CharField (null=True, **maxlength20)
    scm_server = models.CharField (null=True, **maxlength200)
    scm_module = models.CharField (null=True, **maxlength80)
    scm_branch = models.CharField (null=True, **maxlength80)
    scm_path = models.CharField (null=True, **maxlength200)
    scm_dir = models.CharField (null=True, **maxlength200)
    scm_file = models.CharField (null=True, **maxlength80)

    mod_score = models.IntegerField (null=True)
    mod_score_diff = models.IntegerField (null=True)
    mod_datetime = models.DateTimeField (null=True)
    mod_person = models.ForeignKey ('Entity', related_name='branch_mods', null=True)
    post_score = models.IntegerField (null=True)
    post_score_diff = models.IntegerField (null=True)

    def get_is_default (self):
        return self.scm_branch == pulse.scm.default_branches.get (self.scm_type)
    is_default = property (get_is_default)

    def select_children (self, type):
        return self.__class__.objects.filter (type=type, parent=self)

    def set_children (self, type, children):
        old = list(Branch.objects.filter (type=type, parent=self))
        olddict = {}
        for rec in old:
            olddict[rec.ident] = rec
        for child in children:
            olddict.pop (child.ident, None)
            child.parent = self
            child.save()
        for old in olddict.values():
            old.delete ()

    def save (self, **kw):
        if self.branchable == None:
            ident = '/'.join (self.ident.split('/')[:-1])
            rec = Branchable.get_record (ident, self.type)
            self.branchable = rec
        if getattr (self, 'scm_type', None) != None and getattr (self, 'scm_branch', None) != None:
            if self.is_default:
                do_save = False
                for f in Branchable._meta.fields:
                    if f.name.startswith ('scm_'):
                        val = getattr (self, f.name, None)
                        if getattr (self.branchable, f.name) != val:
                            setattr (self.branchable, f.name, val)
                            do_save = True
                if do_save:
                    self.branchable.save(**kw)
        models.Model.save (self, **kw)

    def delete_relations (self):
        # FIXME: remove branchable if orphaned
        for rev in Revision.objects.filter (branch=self):
            rev.delete()
        PulseRecord.delete_relations (self)

    def get_title_default (self):
        id = self.ident.split('/')[-2]
        if self.type == 'Domain':
            if id == 'po':
                return self.scm_module
            else:
                return pulse.utils.gettext ('%s (%s)') % (self.scm_module, id)
        return id

    def get_branch_module (self):
        return pulse.utils.gettext ('%s (%s)') % (self.scm_module, self.scm_branch)
    branch_module = property (get_branch_module)

    def get_branch_title (self):
        return pulse.utils.gettext ('%s (%s)') % (self.title, self.scm_branch)
    branch_title = property (get_branch_title)

    @classmethod
    def select_with_statistic (cls, stattype, **kw):
        sel = cls.objects.filter (**kw)
        if isinstance (stattype, basestring):
            stattype = [stattype]
        for stype in stattype:
            # I'm splicing stype directly in, because it turns out that when we use
            # params, Django merges stuff together in whatever order it sees fit and
            # gets the order of the parameters wrong when there are multiple types.
            # The statistic types are completely under our control, and we only ever
            # use alphanumeric, so there's no real risk of an injection.
            sel = sel.extra (tables = ['Statistic AS ' + stype + 'Statistic'],
                             select = {stype + '_daynum' : stype + 'Statistic.daynum',
                                       stype + '_stat1' : stype + 'Statistic.stat1',
                                       stype + '_stat2' : stype + 'Statistic.stat2',
                                       stype + '_total' : stype + 'Statistic.total'
                                       },
                             where = [stype + 'Statistic.type = "' + stype + '"',
                                      stype + 'Statistic.branch_id = Branch.id',
                                      (stype + 'Statistic.daynum = (' +
                                       'SELECT daynum FROM Statistic' +
                                       ' WHERE Statistic.branch_id = Branch.id' +
                                       ' AND Statistic.type = "' + stype + '"' +
                                       ' ORDER BY daynum DESC LIMIT 1)')
                                      ])
        return sel

    def _is_watchable (self):
        return self.type == 'Module'
    watchable = property (_is_watchable)


class Entity (PulseRecord, models.Model):
    __metaclass__ = PulseModelBase

    parent = models.ForeignKey ('Entity', related_name='children', null=True)
    nick = models.CharField (null=True, **maxlength80)
    mod_score = models.IntegerField (null=True)
    mod_score_diff = models.IntegerField (null=True)
    post_score = models.IntegerField (null=True)
    post_score_diff = models.IntegerField (null=True)


    # Convenience routine to get objects that might already exist
    @classmethod
    def get_record (cls, ident, type):
        return cls.get_entity_alias (ident, type)[0]


    @classmethod
    def get_entity_alias (cls, ident, type):
        try:
            rec = cls.objects.filter (ident=ident, type=type)
            rec = rec[0]
            return (rec, None)
        except IndexError:
            try:
                rec = Alias.objects.filter (ident=ident)
                rec = rec[0]
                return (rec.entity, rec)
            except IndexError:
                rec, cr = cls.objects.get_or_create (ident=ident, type=type)
                return (rec, None)


    @classmethod
    def get_by_email (cls, email):
        try:
            rec = cls.objects.filter (email=email)
            rec = rec[0]
            return rec
        except IndexError:
            pass
        ident = '/person/' + email
        try:
            rec = cls.objects.filter (ident=ident)
            rec = rec[0]
            return rec
        except IndexError:
            pass
        try:
            rec = Alias.objects.filter (ident=ident)
            rec = rec[0]
            return rec.entity
        except IndexError:
            pass
        rec, cr = cls.objects.get_or_create (ident=ident, type='Person')
        return rec


    def get_name_nick (self):
        # FIXME: latinized names
        if self.nick != None:
            return pulse.utils.gettext ('%s (%s)') % (self.localized_name, self.nick)
        else:
            return self.localized_name
    name_nick = property (get_name_nick)

    def _is_linkable (self):
        return self.type != 'Ghost'
    linkable = property (_is_linkable)

    def _is_watchable (self):
        return self.type in ('Person', 'Team')
    watchable = property (_is_watchable)


class Alias (PulseRecord, models.Model):
    __metaclass__ = PulseModelBase

    entity = models.ForeignKey (Entity)

    @classmethod
    def update_alias (cls, entity, ident):
        updated = False
        try:
            alias = cls.objects.get (ident=ident)
        except IndexError:
            updated = True
            alias = Alias (ident=alias)
        alias.entity = entity
        alias.save()
        try:
            old = Entity.objects.filter (ident=ident)
            old = old[0]
        except IndexError:
            old = None
        if old == None:
            return updated

        pulse.utils.log ('Copying %s to %s' % (ident, entity.ident))
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
        # FIXME: set default for entity

        # Revision and ForumPost record historical data, so we record the
        # alias of the entity they pointed to.
        revs = Revision.objects.filter (person=old)
        for rev in revs:
            updated = True
            rev.person = entity
            rev.alias = alias
            rev.save()
        posts = ForumPost.objects.filter (author=old)
        for post in posts:
            updated = True
            post.author = entity
            post.alias = alias
            post.save()

        # The rest of these don't need the historical alias to be recorded.
        rels = DocumentEntity.objects.filter (pred=old)
        for rel in rels:
            updated = True
            rel.pred = entity
            rel.save()
        rels = ModuleEntity.objects.filter (pred=old)
        for rel in rels:
            updated = True
            rel.pred = entity
            rel.save()
        rels = TeamMember.objects.filter (subj=old)
        for rel in rels:
            updated = True
            rel.subj = entity
            rel.save()
        rels = TeamMember.objects.filter (pred=old)
        for rel in rels:
            updated = True
            rel.pred = entity
            rel.save()
        branches = Branch.objects.filter (mod_person=old)
        for branch in branches:
            updated = True
            branch.mod_person = entity
            branch.save()
        watches = Revision.objects.filter (ident=old.ident)
        for watch in watches:
            updated = True
            watch.ident = entity.ident
            watch.save()
        old.delete()

        return updated


class Forum (PulseRecord, models.Model):
    __metaclass__ = PulseModelBase
    post_score = models.IntegerField (null=True)
    post_score_diff = models.IntegerField (null=True)


class ForumPost (PulseRecord, models.Model):
    __metaclass__ = PulseModelBase

    def __init__ (self, *args, **kw):
        models.Model.__init__ (self, *args, **kw)
        if self.weeknum == None and self.datetime != None:
            self.weeknum = pulse.utils.weeknum (self.datetime)

    forum = models.ForeignKey (Forum, related_name='forum_posts')
    author = models.ForeignKey (Entity, related_name='forum_posts', null=True)
    alias = models.ForeignKey (Alias, null=True)
    parent = models.ForeignKey ('ForumPost', related_name='children', null=True)
    datetime = models.DateTimeField (null=True)
    weeknum = models.IntegerField (null=True)


################################################################################
## Relations

class Documentation (PulseRelation, models.Model):
    __metaclass__ = PulseModelBase
    subj = models.ForeignKey (Branch, related_name='documentation_preds')
    pred = models.ForeignKey (Branch, related_name='documentation_subjs')

class DocumentEntity (PulseRelation, models.Model):
    __metaclass__ = PulseModelBase
    subj = models.ForeignKey (Branch, related_name='document_entity_preds')
    pred = models.ForeignKey (Entity, related_name='document_entity_subjs')
    maintainer = models.BooleanField (default=False)
    author = models.BooleanField (default=False)
    editor = models.BooleanField (default=False)
    publisher = models.BooleanField (default=False)

class ModuleDependency (PulseRelation, models.Model):
    __metaclass__ = PulseModelBase
    subj = models.ForeignKey (Branch, related_name='module_dependency_preds')
    pred = models.ForeignKey (Branch, related_name='module_dependency_subjs')
    direct = models.BooleanField ()

class ModuleEntity (PulseRelation, models.Model):
    __metaclass__ = PulseModelBase
    subj = models.ForeignKey (Branch, related_name='module_entity_preds')
    pred = models.ForeignKey (Entity, related_name='module_entity_subjs')
    maintainer = models.BooleanField (default=False)

class SetModule (PulseRelation, models.Model):
    __metaclass__ = PulseModelBase
    subj = models.ForeignKey (ReleaseSet, related_name='set_module_preds')
    pred = models.ForeignKey (Branch, related_name='set_module_subjs')

class TeamMember (PulseRelation, models.Model):
    __metaclass__ = PulseModelBase
    subj = models.ForeignKey (Entity, related_name='team_member_preds')
    pred = models.ForeignKey (Entity, related_name='team_member_subjs')
    coordinator = models.BooleanField (default=False)


################################################################################
## User Accounts

class Account (models.Model):
    __metaclass__ = PulseModelBase

    username = models.CharField (**maxlength200)
    password = models.CharField (**maxlength200)
    person = models.ForeignKey (Entity, related_name='account')
    realname = models.TextField ()
    email = models.EmailField ()
    check_time = models.DateTimeField (null=True)
    check_type = models.CharField (null=True, **maxlength20)
    check_hash = models.CharField (null=True, **maxlength200)
    data = PickleField ()


class Login (models.Model):
    __metaclass__ = PulseModelBase

    account = models.ForeignKey (Account, related_name='logins')
    token = models.CharField (**maxlength200)
    datetime = models.DateTimeField ()
    ipaddress = models.CharField (**maxlength20)

    @classmethod
    def set_login (cls, account, token, ipaddress):
        try:
            login = cls.objects.get (account=account, ipaddress=ipaddress)
            login.token = token
            login.datetime = datetime.datetime.now()
        except:
            login = cls (account=account, token=token, ipaddress=ipaddress,
                         datetime=datetime.datetime.now())
        login.save ()
        return login

    @classmethod
    def get_login (cls, token, ipaddress):
        try:
            login = cls.objects.get (token=token, ipaddress=ipaddress)
            now = datetime.datetime.now ()
            if (now - login.datetime).days > 0:
                login.delete ()
                raise
            login.datetime = now
            login.save ()
            return login
        except:
            return None


class AccountWatch (models.Model):
    __metaclass__ = PulseModelBase

    account = models.ForeignKey (Account, related_name='account_watches')
    ident = models.CharField (**maxlength200)

    @classmethod
    def add_watch (cls, account, ident):
        rec, cr = cls.objects.get_or_create (account=account, ident=ident)
        return rec

    @classmethod
    def has_watch (cls, account, ident):
        return cls.objects.filter (account=account, ident=ident).count() > 0


class Message (models.Model):
    __metaclass__ = PulseModelBase

    def __init__ (self, *args, **kw):
        models.Model.__init__ (self, *args, **kw)
        if self.weeknum == None and self.datetime != None:
            self.weeknum = pulse.utils.weeknum (self.datetime)

    @classmethod
    def make_message (cls, type, subj, pred, dt):
        daystart = datetime.datetime (dt.year, dt.month, dt.day)
        dayend = daystart + datetime.timedelta (days=1)
        if (datetime.datetime.now() - daystart).days > 28:
            return None
        filterargs = {'type': type, 'datetime__gte': daystart, 'datetime__lt': dayend}
        if subj != None:
            filterargs['subj'] = subj
        else:
            filterargs['subj__isnull'] = True
        if pred != None:
            filterargs['pred'] = pred
        else:
            filterargs['pred__isnull'] = True
        oldmsg = cls.objects.filter (**filterargs)
        try:
            oldmsg = oldmsg[0]
        except:
            oldmsg = None
        if oldmsg != None:
            if oldmsg.count == None:
                oldmsg.count = 1
            oldmsg.count = oldmsg.count + 1
            oldmsg.datetime = max (oldmsg.datetime, dt)
            oldmsg.save ()
            return oldmsg
        msg = cls (type=type, subj=subj, pred=pred, count=1,
                   datetime=dt, weeknum=pulse.utils.weeknum(daystart))
        msg.save ()
        return msg

    type = models.CharField (null=True, **maxlength80)
    subj = models.CharField (null=True, **maxlength200)
    pred = models.CharField (null=True, **maxlength200)
    count = models.IntegerField (null=True)

    datetime = models.DateTimeField (null=True)
    weeknum = models.IntegerField (null=True)


################################################################################
## Other Tables

class Revision (models.Model):
    __metaclass__ = PulseModelBase

    def __init__ (self, *args, **kw):
        models.Model.__init__ (self, *args, **kw)
        if self.weeknum == None and self.datetime != None:
            self.weeknum = pulse.utils.weeknum (self.datetime)

    branch = models.ForeignKey (Branch)
    person = models.ForeignKey (Entity)
    alias = models.ForeignKey (Alias, null=True)
    revision = models.CharField (**maxlength80)
    datetime = models.DateTimeField ()
    weeknum = models.IntegerField (null=True)
    comment = models.TextField ()

    def display_revision (self, branch=None):
        if branch == None:
            branch = self.branch
        if branch.scm_type == 'git':
            return self.revision[:6]
        else:
            return self.revision

    def delete (self):
        for rfile in RevisionFile.objects.filter (revision=self):
            rfile.delete()
        models.Model.delete (self)

    @classmethod
    def make_revision (cls, **kw):
        branch = kw.get ('branch')
        person = kw.get ('person')
        dt = kw.get ('datetime')
        rev = cls (branch=branch, person=person,
                   revision=kw.get ('revision'),
                   comment=kw.get ('comment'),
                   datetime=dt)
        rev.save()
        Message.make_message ('commit', branch.ident, None, dt)
        Message.make_message ('commit', person.ident, branch.ident, dt)
        return rev

    @classmethod
    def get_last_revision (cls, **kw):
        revs = cls.select_revisions (**kw)
        try:
            return revs[0]
        except IndexError:
            return None

    @classmethod
    def select_revisions (cls, **kw):
        files = kw.pop ('files', None)
        sel = cls.objects.filter (**kw)
        if files != None and len(files) > 0:
            where = '(SELECT COUNT(*) FROM RevisionFile where revision_id = Revision.id AND filename IN ('
            where += ','.join(['%s'] * len(files))
            where += ')) > 0'
            sel = sel.extra (where=[where], params=files)
        return sel.order_by ('-datetime')


class RevisionFile (models.Model):
    __metaclass__ = PulseModelBase

    revision = models.ForeignKey (Revision, related_name='files')
    filename = models.CharField (**maxlength200)
    filerev = models.CharField (**maxlength80)
    prevrev = models.CharField (null=True, **maxlength80)


class Statistic (models.Model):
    __metaclass__ = PulseModelBase

    branch = models.ForeignKey (Branch)
    daynum = models.IntegerField ()
    type = models.CharField (**maxlength20)
    stat1 = models.IntegerField ()
    stat2 = models.IntegerField ()
    total = models.IntegerField ()

    @classmethod
    def select_statistic (cls, branch, type):
        stat = cls.objects.filter (branch=branch, type=type)
        return stat.order_by ('-daynum')

    @classmethod
    def set_statistic (cls, branch, daynum, type, stat1, stat2, total):
        res = cls.objects.filter (branch=branch, daynum=daynum, type=type)
        if res.count() > 0:
            res = res[0]
            res.stat1 = stat1
            res.stat2 = stat2
            res.total = total
            res.save()
            return res
        else:
            return cls.objects.create (branch=branch, daynum=daynum, type=type,
                                       stat1=stat1, stat2=stat2, total=total)


class Timestamp (models.Model):
    __metaclass__ = PulseModelBase

    filename = models.CharField (**maxlength200)
    sourcefunc = models.CharField (**maxlength200)
    stamp = models.IntegerField ()

    @classmethod
    def set_timestamp (cls, filename, stamp):
        sfunc = inspect.stack()[1]
        sfunc = os.path.basename (sfunc[1]) + '#' + sfunc[3]
        obj = cls.objects.filter (filename=filename, sourcefunc=sfunc)
        try:
            obj = obj[0]
            obj.stamp = int(stamp)
            obj.save()
        except IndexError:
            cls (filename=filename, sourcefunc=sfunc, stamp=int(stamp)).save()
        return stamp

    @classmethod
    def get_timestamp (cls, filename):
        sfunc = inspect.stack()[1]
        sfunc = os.path.basename (sfunc[1]) + '#' + sfunc[3]
        obj = cls.objects.filter (filename=filename, sourcefunc=sfunc)
        try:
            return obj[0].stamp
        except IndexError:
            return -1


class OutputFile (models.Model):
    __metaclass__ = PulseModelBase

    type = models.CharField (**maxlength80)
    ident = models.CharField (**maxlength200)
    subdir = models.CharField (null=True, **maxlength200)
    filename = models.CharField (**maxlength200)
    source = models.CharField (null=True, **maxlength200)
    datetime = models.DateTimeField ()
    statistic = models.IntegerField (null=True)
    data = PickleField ()

    def get_pulse_url (self, subsub=None):
        lst = [self.ident[1:]]
        if self.subdir != None:
            lst.append (self.subdir)
        if subsub != None:
            lst.append (subsub)
        lst.append (self.filename)
        rootdir = getattr (pulse.config, self.type + '_root', None)
        if rootdir == None:
            lst.insert (0, self.type)
            rootdir = pulse.config.web_root
        return rootdir + '/'.join(lst)
    pulse_url = property (get_pulse_url)

    def get_file_path (self, subsub=None):
        lst = self.ident[1:].split('/')
        if self.subdir != None:
            lst.append (self.subdir)
        if subsub != None:
            lst.append (subsub)
        lst.append (self.filename)
        rootdir = getattr (pulse.config, 'web_' + self.type + '_dir', None)
        if rootdir == None:
            lst.insert (0, self.type)
            rootdir = pulse.config.web_files_dir
        return os.path.join(rootdir, *lst)


class Queue (models.Model):
    __metaclass__ = PulseModelBase

    module = models.CharField (**maxlength80)
    ident = models.CharField (**maxlength200)

    @classmethod
    def push (cls, module, ident):
        rec, cr = cls.objects.get_or_create (module=module, ident=ident)
        return rec

    @classmethod
    def pop (cls):
        try:
            rec = cls.objects.all()[0]
            module = rec.module
            ident = rec.ident
            rec.delete()
            return {'module': module, 'ident': ident}
        except:
            return None

    @classmethod
    def remove (cls, module, ident):
        try:
            rec = cls.objects.filter (module=module, ident=ident)
            rec.delete()
        except:
            pass
