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
import inspect
import os
import os.path
import sys
import time

os.environ['DJANGO_SETTINGS_MODULE'] = 'pulse.config'
from django.core import validators
import django.db
import django.db.backends.util
from django.db import models
from django.db.models import signals
from django.db.models.base import ModelBase
from django.dispatch import dispatcher

import pulse.config
import pulse.scm
import pulse.utils


################################################################################
## Abusing Django

# Django doesn't have any types mapped to blob, so we have to
# add that mapping in ourselves.  Note that this should work
# with SQLite and MySQL.  To support other databases, we'll
# have to switch on DATABASE_ENGINE here.
data_types = django.db.get_creation_module().DATA_TYPES
data_types['BlobField'] = 'blob'

# We have to do this to avoid encoding errors.  Note that
# I've not yet tested with any other databases.  We might
# have to add other hacks here for other databases.
if pulse.config.DATABASE_ENGINE == 'sqlite3':
    from django.db.backends.sqlite3.base import Database
    Database.register_converter ('blob', lambda s: s)


################################################################################
## Debugging and Logging

# This is a nasty hack that allows us to only log INSERTs below
__was_insert = False


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
            text = text[:7] + '...' + text[i:]
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
                print '  ' + ('%.3f' % diff) + ' -- ' + text.replace('"', '')

    def execute_many (self, sql, param_list):
        return self.cursor.executemany (sql, param_list)

    def __getattr__ (self, attr):
        if self.__dict__.has_key (attr):
            return self.__dict__[attr]
        else:
            return getattr (self.cursor, attr)

django.db.backends.util.CursorDebugWrapper = PulseDebugCursor

def __pulse_log_save (instance):
    if not PulseDebugCursor.was_insert:
        return
    if isinstance (instance, PulseRecord):
        pulse.utils.log ('Created %s %s' % (instance.type, instance.ident))
    elif isinstance (instance, PulseRelation):
        pulse.utils.log ('Created %s %s : %s' %
                         (instance.__class__.__name__,
                          instance.subj.ident, instance.pred.ident))

def __pulse_log_delete (instance):
    if isinstance (instance, PulseRecord):
        pulse.utils.log ('Deleted %s %s' % (instance.type, instance.ident))
    elif isinstance (instance, PulseRelation):
        pulse.utils.log ('Deleted %s %s : %s' %
                         (instance.__class__.__name__,
                          instance.subj.ident, instance.pred.ident))

dispatcher.connect (__pulse_log_save, signal=signals.post_save)
dispatcher.connect (__pulse_log_delete, signal=signals.post_delete)


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

    # Convenience routine to get objects that might already exist
    @classmethod
    def get_record (cls, ident, type):
        rec, cr = cls.objects.get_or_create (ident=ident, type=type)
        return rec

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
    ident = models.CharField (maxlength=200)
    type = models.CharField (maxlength=80)

    name = PickleField ()
    desc = PickleField ()

    icon_dir = models.CharField (maxlength=200, null=True)
    icon_name = models.CharField (maxlength=80, null=True)

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
    scm_type = models.CharField (maxlength=20, null=True)
    scm_server = models.CharField (maxlength=200, null=True)
    scm_module = models.CharField (maxlength=80, null=True)
    scm_path = models.CharField (maxlength=200, null=True)
    scm_dir = models.CharField (maxlength=200, null=True)
    scm_file = models.CharField (maxlength=80, null=True)

    default = models.ForeignKey ('Branch', related_name='is_default_query', null=True)


class Branch (PulseRecord, models.Model):
    __metaclass__ = PulseModelBase
    subtype = models.CharField (maxlength=80, null=True)
    parent = models.ForeignKey ('Branch', related_name='children', null=True)
    branchable = models.ForeignKey ('Branchable', related_name='branches', null=True)

    scm_type = models.CharField (maxlength=20, null=True)
    scm_server = models.CharField (maxlength=200, null=True)
    scm_module = models.CharField (maxlength=80, null=True)
    scm_branch = models.CharField (maxlength=80, null=True)
    scm_path = models.CharField (maxlength=200, null=True)
    scm_dir = models.CharField (maxlength=200, null=True)
    scm_file = models.CharField (maxlength=80, null=True)

    mod_score = models.IntegerField (null=True)
    mod_datetime = models.DateTimeField (null=True)
    mod_person = models.ForeignKey ('Entity', related_name='branch_mods', null=True)

    def is_default (self):
        return (self.is_default_query.count() > 0)

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
            if self.is_default:
                child.branchable.default = child
            child.save()
        for old in olddict.values():
            old.delete ()

    def save (self):
        if self.branchable == None:
            ident = '/'.join (self.ident.split('/')[:-1])
            rec = Branchable.get_record (ident, self.type)
            self.branchable = rec
        if getattr (self, 'scm_type', None) != None and getattr (self, 'scm_branch', None) != None:
            if pulse.scm.default_branches[self.scm_type] == self.scm_branch:
                self.branchable.default = self
                do_save = False
                for f in Branchable._meta.fields:
                    if f.name.startswith ('scm_'):
                        val = getattr (self, f.name, None)
                        if getattr (self.branchable, f.name) != val:
                            setattr (self.branchable, f.name, val)
                            do_save = True
                if do_save:
                    self.branchable.save()
        models.Model.save (self)

    def delete_relations (self):
        # FIXME: remove branchable if orphaned
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


class Entity (PulseRecord, models.Model):
    __metaclass__ = PulseModelBase

    nick = models.CharField (maxlength=80, null=True)
    mod_score = models.IntegerField (null=True)

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
    subj = models.ForeignKey (Record, related_name='set_module_preds')
    pred = models.ForeignKey (Branch, related_name='set_module_subjs')

class SetSubset (PulseRelation, models.Model):
    __metaclass__ = PulseModelBase
    subj = models.ForeignKey (Record, related_name='set_subset_preds')
    pred = models.ForeignKey (Record, related_name='set_subset_subjs')


################################################################################
## Other Tables

class Revision (models.Model):
    __metaclass__ = PulseModelBase

    branch = models.ForeignKey (Branch)
    person = models.ForeignKey (Entity)
    filename = models.CharField (maxlength=200, null=True, default=None)
    filetype = models.CharField (maxlength=20, null=True, default=None)
    revision = models.CharField (maxlength=80)
    datetime = models.DateTimeField ()
    comment = models.TextField ()

    @classmethod
    def get_last_revision (cls, branch=None, person=None, filename=False):
        revs = cls.select_revisions (branch=branch, person=person, filename=filename)
        try:
            return revs[0]
        except IndexError:
            return None

    @classmethod
    def select_revisions (cls, branch=None, person=None, filename=False, since=None):
        args = {}
        if since != None:
            args['datetime__gt'] = since
        if branch != None:
            args['branch'] = branch
        if person != None:
            args['person'] = person
        if isinstance (filename, basestring):
            args['filename'] = filename
        elif filename == True:
            args['filename__isnull'] = False
        elif filename == None:
            args['filename__isnull'] = True
        revs = cls.objects.filter (**args)
        return revs.order_by ('-datetime')


class Statistic (models.Model):
    __metaclass__ = PulseModelBase

    branch = models.ForeignKey (Branch)
    daynum = models.IntegerField ()
    type = models.CharField (maxlength=20)
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

    filename = models.CharField (maxlength=200)
    sourcefunc = models.CharField (maxlength=200)
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

    type = models.CharField (maxlength=80)
    ident = models.CharField (maxlength=200)
    subdir = models.CharField (maxlength=200, null=True)
    filename = models.CharField (maxlength=200)
    source = models.CharField (maxlength=200, null=True)
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
