import datetime
import inspect
import os
import sys

from storm.locals import *
from storm.expr import Variable
from storm.info import ClassAlias
from storm.store import EmptyResultSet
import storm.properties
import storm.references

import pulse.config
import pulse.utils

database = create_database (pulse.config.database)
store = Store (database)

def flush ():
    store.flush()

def commit ():
    pulse.utils.log ('Committing changes')
    store.commit ()

def rollback ():
    pulse.utils.log ('Rolling back changes')
    store.rollback ()

################################################################################
## Debugging

class PulseTracer (object):
    def __init__ (self, stream=None):
        self._stream = stream or sys.stderr
        self._last_time = None
        self._select_count = 0
        self._select_total = 0

    def connection_raw_execute (self, connection, raw_cursor, statement, params):
        self._last_time = datetime.datetime.now()

    def print_command (self, statement, params):
        diff = datetime.datetime.now() - self._last_time
        sec = diff.seconds + (diff.microseconds / 1000000.)
        milli = 1000 * sec
        micro = 1000 * (milli - int(milli))
        timing = '%03i.%03i' % (int(milli), int(micro))
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
            self._select_count += 1
            self._select_total += sec
            pos = cmd.find (' FROM ')
            outfirst = cmd[:pos]
            outrest = cmd[pos:]
            if outfirst.startswith ('SELECT COUNT'):
                outtxt.append (outfirst)
            else:
                outtxt.append ('SELECT ...')
            pos = outrest.find (' WHERE ')
            if pos < 0:
                outtxt[0] = outtxt[0] + outrest
            else:
                outtxt[0] = outtxt[0] + outrest[:pos]
                outrest = outrest[pos+1:]
                if outrest.find ('(OID=') >= 0:
                    outtxt[0] = outtxt[0] + ' ' + outrest
                else:
                    for txt in outrest.split (' AND '):
                        if txt.startswith ('WHERE '):
                            outtxt.append (txt)
                        else:
                            outtxt.append ('AND ' + txt)
        elif cmd.startswith ('UPDATE '):
            outtxt.append (cmd)
        elif cmd.startswith ('INSERT '):
            outtxt.append (cmd)
        else:
            outtxt.append (cmd)

        self._stream.write ((u'(%s)  %s\n' % (timing, outtxt[0])).encode ('utf8'))
        for txt in outtxt[1:]:
            self._stream.write ((u'           %s\n' % txt).encode ('utf8'))

    def connection_raw_execute_error (self, connection, raw_cursor,
                                      statement, params, error):
        self.print_command (statement, params)
        self._stream.write ('ERROR: %s\n' % error)

    def connection_raw_execute_success (self, connection, raw_cursor,
                                        statement, params):
        self.print_command (statement, params)

def debug ():
    import storm.tracer
    storm.tracer.install_tracer (PulseTracer ())


################################################################################
## Exceptions

class NoSuchFieldError (Exception):
    pass

class WillNotDelete (Exception):
    pass


################################################################################
## Base Classes

class PulseModelType (storm.properties.PropertyPublisherMeta):
    def __new__ (meta, name, bases, attrs):
        cls = super (PulseModelType, meta).__new__ (meta, name, bases, attrs)
        cls._record_cache = {}
        if not cls.__dict__.get ('__abstract__', False):
            cls.__storm_table__ = cls.__name__
        return cls


class PulseModel (Storm):
    __abstract__ = True
    __metaclass__ = PulseModelType

    def __init__ (self, **kw):
        self.update (**kw)
        self.log_create ()
        store.add (self)
        store.flush ()

    def __repr__ (self):
        if hasattr (self, 'id'):
            return '%s %s' % (self.__class__.__name__, self.id)
        else:
            return self.__class__.__name__

    def log_create (self):
        pulse.utils.log ('Creating %s' % self)

    @ classmethod
    def find (cls, *args, **kw):
        # let's remove this in favor of select
        return store.find (cls, *args, **kw)

    @ classmethod
    def select (cls, *args, **kw):
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
                if overwrite or (self.data.get (key) == None):
                    self.data[key] = val
                pass
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
                        val = pulse.utils.utf8dec (val)
                    setattr (self, key, val)
        return self

    def update (self, _update_data={}, **kw):
        return self._update_or_extend (True, _update_data, **kw)

    def extend (self, _update_data={}, **kw):
        return self._update_or_extend (False, _update_data, **kw)

    def delete (self):
        for table in get_tables ():
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
        pulse.utils.log ('Deleting %s' % self)
        store.remove (self)


class PulseRecord (PulseModel):
    __abstract__ = True
    ident = Unicode (primary=True)
    type = Unicode ()

    name = Pickle (default_factory=dict)
    desc = Pickle (default_factory=dict)

    icon_dir = Unicode ()
    icon_name = Unicode ()

    email = Unicode ()
    web = Unicode ()

    data = Pickle (default_factory=dict)
    
    # Whether Pulse should link to this thing, i.e. whether it
    # displays pages for this kind of thing.  Subclasses will
    # want to override this, possibly with a property.
    linkable = True

    # Whether Pulse can watch this thing.  Subclasses will want
    # to override this, possible with a property.
    watchable = False

    def __init__ (self, ident, type, **kw):
        kw['ident'] = ident
        kw['type'] = type
        PulseModel.__init__ (self, **kw)

    def __repr__ (self):
        if self.type != None:
            return '%s %s' % (self.type, self.ident)
        else:
            return '%s %s' % (self.__class__.__name__, self.ident)

    @property
    def pulse_url (self):
        return pulse.config.web_root + self.ident[1:]

    @property
    def icon_url (self):
        if self.icon_name == None or self.icon_dir.startswith ('__icon__'):
            return None
        elif self.icon_dir == None:
            return pulse.config.icons_root + self.icon_name + '.png'
        else:
            return pulse.config.icons_root + self.icon_dir + '/' + self.icon_name + '.png'

    @property
    def localized_name (self):
        # FIXME: i18n
        return self.name.get ('C')

    @property
    def localized_desc (self):
        # FIXME: i18n
        return self.desc.get ('C')

    @property
    def title_default (self):
        return self.ident.split('/')[-1]

    @property
    def title (self):
        if self.name == {}:
            return self.title_default
        return self.localized_name

    @classmethod
    def get_or_create (cls, ident, type, **kw):
        record = cls.get_cached (ident)
        if record != None:
            return record
        return cls (ident, type, **kw)

    @classmethod
    def get (cls, ident):
        try:
            return cls.select (ident=ident).one ()
        except:
            return None

    @classmethod
    def get_cached (cls, ident):
        if cls._record_cache.has_key (ident):
            return cls._record_cache[ident]
        record = cls.get (ident)
        if record != None:
            cls.set_cached (ident, record)
        return record

    @classmethod
    def set_cached (cls, ident, record):
        cls._record_cache[ident] = record

    def set_relations (self, cls, rels):
        old = list (store.find (cls, subj_ident=self.ident))
        olddict = {}
        for rel in old:
            olddict[rel.pred_ident] = rel
        for rel in rels:
            olddict.pop (rel.pred_ident, None)
        oldids = [old.id for old in olddict.values()]
        store.find (cls, cls.id.is_in (oldids)).remove ()


class PulseRelation (PulseModel):
    __abstract__ = True
    id = Int (primary=True)
    subj_ident = Unicode ()
    pred_ident = Unicode ()

    def __repr__ (self):
        return '%s %s %s' % (self.__class__.__name__, self.subj_ident, self.pred_ident)

    @classmethod
    def set_related (cls, subj, pred, **kw):
        rel = store.find (cls, subj_ident=subj.ident, pred_ident=pred.ident).one ()
        if rel == None:
            rel = cls (subj=subj, pred=pred)
        if len(kw) > 0:
            for k, v in kw.items():
                setattr (rel, k, v)
        return rel

    @classmethod
    def select_related (cls, subj=None, pred=None):
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
            return EmptyResultSet ()

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


class ReleaseSet (PulseRecord):
    parent_ident = Unicode ()
    parent = Reference (parent_ident, 'ReleaseSet.ident')

    subsets = ReferenceSet ('ReleaseSet.ident', parent_ident)

    def delete (self):
        for record in ReleaseSet.select (parent=self):
            record.delete ()
        PulseRecord.delete (self)

    @property
    def subsets (self):
        return ReleaseSet.select (parent=self)


class Branch (PulseRecord):
    subtype = Unicode ()
    parent_ident = Unicode ()
    parent = Reference (parent_ident, 'Branch.ident')
    branchable = Unicode ()
    error = Unicode ()

    scm_type = Unicode ()
    scm_server = Unicode ()
    scm_module = Unicode ()
    scm_branch = Unicode ()
    scm_path = Unicode ()
    scm_dir = Unicode ()
    scm_file = Unicode ()

    mod_score = Int ()
    mod_score_diff = Int ()
    mod_datetime = DateTime ()
    mod_person_ident = Unicode ()
    mod_person = Reference (mod_person_ident, 'Entity.ident')
    post_score = Int ()
    post_score_diff = Int ()

    def __init__ (self, ident, type, **kw):
        kw['branchable'] = u'/'.join (ident.split('/')[:-1])
        PulseRecord.__init__ (self, ident, type, **kw)

    @property
    def title_default (self):
        id = self.ident.split('/')[-2]
        if self.type == 'Domain':
            if id == 'po':
                return self.scm_module
            else:
                return pulse.utils.gettext ('%s (%s)') % (self.scm_module, id)
        return id

    @property
    def branch_module (self):
        return pulse.utils.gettext ('%s (%s)') % (self.scm_module, self.scm_branch)

    @property
    def branch_title (self):
        return pulse.utils.gettext ('%s (%s)') % (self.title, self.scm_branch)

    @classmethod
    def select (cls, *args, **kw):
        args = list (args)
        rset = kw.pop ('parent_in_set', None)
        if rset != None:
            args.append (cls.parent_ident == SetModule.pred_ident)
            args.append (SetModule.subj_ident == rset.ident)
        return store.find (cls, *args, **kw)

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

    def delete (self):
        for record in Branch.select (parent=self):
            record.delete ()
        PulseRecord.delete (self)


class Entity (PulseRecord):
    parent_ident = Unicode ()
    parent = Reference (parent_ident, 'Entity.ident')
    nick = Unicode ()
    mod_score = Int ()
    mod_score_diff = Int ()
    post_score = Int ()
    post_score_diff = Int ()

    def delete (self):
        raise WillNotDelete ('Pulse will not delete entities')

    @classmethod
    def get (cls, ident):
        try:
            ent = cls.select (ident=ident).one ()
        except:
            ent = None
        if ent == None:
            ent = Alias.get (ident)
            if ent != None:
                ent = ent.entity
        return ent


class Alias (PulseRecord):
    entity_ident = Unicode ()
    entity = Reference (entity_ident, 'Entity.ident')

    def delete (self):
        raise WillNotDelete ('Pulse will not delete aliases')


class Forum (PulseRecord):
    post_score = Int ()
    post_score_diff = Int ()

    def delete (self):
        raise WillNotDelete ('Pulse will not delete forums')


class ForumPost (PulseRecord):
    forum_ident = Unicode ()
    forum = Reference (forum_ident, 'Forum.ident')

    author_ident = Unicode ()
    author = Reference (author_ident, 'Entity.ident')

    alias_ident = Unicode ()
    alias = Reference (alias_ident, 'Alias.ident')

    parent_ident = Unicode ()
    parent = Reference (parent_ident, 'ForumPost.ident')

    datetime = DateTime ()
    weeknum = Int ()

    def __init__ (self, ident, type, forum, author, parent, datetime, **kw):
        kw['forum'] = forum
        kw['author'] = author
        kw['parent'] = parent
        kw['datetime'] = datetime
        kw['weeknum'] = pulse.utils.weeknum (datetime)
        PulseRecord.__init__ (self, ident, type, **kw)

    def delete (self):
        raise WillNotDelete ('Pulse will not delete forum posts')


################################################################################
## Relations

class Documentation (PulseRelation):
    subj_ident = Unicode ()
    pred_ident = Unicode ()
    subj = Reference (subj_ident, Branch.ident)
    pred = Reference (pred_ident, Branch.ident)

class DocumentEntity (PulseRelation):
    subj_ident = Unicode ()
    pred_ident = Unicode ()
    subj = Reference (subj_ident, Branch.ident)
    pred = Reference (pred_ident, Entity.ident)
    maintainer = Bool (default=False)
    author = Bool (default=False)
    editor = Bool (default=False)
    publisher = Bool (default=False)

class ModuleDependency (PulseRelation):
    subj_ident = Unicode ()
    pred_ident = Unicode ()
    subj = Reference (subj_ident, Branch.ident)
    pred = Reference (pred_ident, Branch.ident)
    direct = Bool ()

class ModuleEntity (PulseRelation):
    subj_ident = Unicode ()
    pred_ident = Unicode ()
    subj = Reference (subj_ident, Branch.ident)
    pred = Reference (pred_ident, Entity.ident)
    maintainer = Bool (default=False)

class SetModule (PulseRelation):
    subj_ident = Unicode ()
    pred_ident = Unicode ()
    subj = Reference (subj_ident, ReleaseSet.ident)
    pred = Reference (pred_ident, Branch.ident)

class TeamMember (PulseRelation):
    subj_ident = Unicode ()
    pred_ident = Unicode ()
    subj = Reference (subj_ident, Entity.ident)
    pred = Reference (pred_ident, Entity.ident)
    coordinator = Bool (default=False)


################################################################################
## Other Tables

class Revision (PulseModel):
    id = Int (primary=True)

    branch_ident = Unicode ()
    branch = Reference (branch_ident, Branch.ident)

    person_ident = Unicode ()
    person = Reference (person_ident, Entity.ident)

    alias_ident = Unicode ()
    alias = Reference (alias_ident, Alias.ident)

    revision = Unicode ()
    datetime = DateTime ()
    weeknum = Int ()
    comment = Unicode ()

    def __init__ (self, **kw):
        kw['weeknum'] = pulse.utils.weeknum (kw['datetime'])
        PulseModel.__init__ (self, **kw)

    def log_create (self):
        pass

    def add_file (self, filename, filerev, prevrev):
        rfile = RevisionFile (revision=self,
                              filename=filename,
                              filerev=filerev,
                              prevrev=prevrev)

    def display_revision (self, branch=None):
        if branch == None:
            branch = self.branch
        if branch.scm_type == 'git':
            return self.revision[:6]
        else:
            return self.revision

    @classmethod
    def get_last_revision (cls, **kw):
        try:
            return cls.select_revisions (**kw)[0]
        except IndexError:
            return None

    @classmethod
    def select_revisions (cls, *args, **kw):
        args = list (args)
        files = kw.pop ('files', None)
        range = kw.pop ('week_range', None)
        if files != None:
            args.append (Select (Count('*') > 0,
                                 where=And (RevisionFile.revision_id == Revision.id,
                                            RevisionFile.filename.is_in (files)),
                                 tables=RevisionFile ))
        if range != None:
            args.append (And (Revision.weeknum >= range[0],
                              Revision.weeknum <= range[1]))
        sel = cls.select (*args, **kw)
        return sel.order_by (Desc (Revision.datetime))


class RevisionFile (PulseModel):
    id = Int (primary=True)

    revision_id = Int ()
    revision = Reference (revision_id, Revision.id)

    filename = Unicode ()
    filerev = Unicode ()
    prevrev = Unicode ()

    def log_create (self):
        pass


class OutputFile (PulseModel):
    id = Int (primary=True)

    type = Unicode ()
    ident = Unicode ()
    subdir = Unicode ()
    filename = Unicode ()
    source = Unicode ()
    datetime = DateTime ()
    statistic = Int ()
    data = Pickle (default_factory=dict)

    def log_create (self):
        pass

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


class Timestamp (PulseModel):
    __storm_primary__ = 'filename', 'sourcefunc'
    filename = Unicode ()
    sourcefunc = Unicode ()
    stamp = Int ()

    def log_create (self):
        pass

    @classmethod
    def set_timestamp (cls, filename, stamp):
        sfunc = inspect.stack()[1]
        sfunc = unicode (os.path.basename (sfunc[1]) + '#' + sfunc[3])
        obj = cls.select (filename=filename, sourcefunc=sfunc)
        try:
            obj = obj[0]
            obj.stamp = int(stamp)
        except IndexError:
            cls (filename=filename, sourcefunc=sfunc, stamp=int(stamp))

    @classmethod
    def get_timestamp (cls, filename):
        sfunc = inspect.stack()[1]
        sfunc = unicode (os.path.basename (sfunc[1]) + '#' + sfunc[3])
        obj = cls.select (filename=filename, sourcefunc=sfunc)
        try:
            return obj[0].stamp
        except IndexError:
            return -1


class Queue (PulseModel):
    __storm_primary__ = 'module', 'ident'
    module = Unicode ()
    ident = Unicode ()

    def log_create (self):
        pass

    @classmethod
    def push (cls, module, ident):
        if cls.select (cls.module == module, cls.ident == ident).count () == 0:
            cls (module=module, ident=ident)

    @classmethod
    def pop (cls):
        try:
            sel = cls.select()[0]
            module = sel.module
            ident = sel.ident
            store.remove (sel)
            return {'module': module, 'ident': ident}
        except:
            return None

    @classmethod
    def remove (cls, module, ident):
        try:
            rec = cls.select (module=module, ident=ident)
            store.remove (rec)
        except:
            pass


################################################################################

def get_tables ():
    tables = []
    for cls in sys.modules[__name__].__dict__.values():
        if not inspect.isclass (cls):
            continue
        if not issubclass (cls, PulseModel):
            continue
        if not hasattr (cls, '__storm_table__'):
            continue
        tables.append (cls)
    return tables

def create_tables ():
    dbtype = pulse.config.database[:pulse.config.database.find(':')]
    fieldtypes = {
        'Bool':      {'postgres': 'BOOL',      'mysql': 'TINYINT(1)', 'sqlite': 'INT'},
        'Int':       {'postgres': 'INT',       'mysql': 'INT',        'sqlite': 'INTEGER'},
        'Float':     {'postgres': 'FLOAT',     'mysql': 'FLOAT',      'sqlite': 'FLOAT'},
        'Decimal':   {'postgres': 'DECIMAL',   'mysql': 'DECIMAL',    'sqlite': 'TEXT'},
        'Unicode':   {'postgres': 'TEXT',      'mysql': 'TEXT',       'sqlite': 'TEXT'},
        'RawStr':    {'postgres': 'BYTEA',     'mysql': 'BLOB',       'sqlite': 'BLOB'},
        'Pickle':    {'postgres': 'BYTEA',     'mysql': 'BLOB',       'sqlite': 'BLOB'},
        'DateTime':  {'postgres': 'TIMESTAMP', 'mysql': 'DATETIME',   'sqlite': 'TEXT'},
        'Date':      {'postgres': 'DATE',      'mysql': 'DATE',       'sqlite': 'TEXT'},
        'Time':      {'postgres': 'TIME',      'mysql': 'TIME',       'sqlite': 'TEXT'},
        'TimeDelta': {'postgres': 'INTERVAL',  'mysql': 'TEXT',       'sqlite': 'TEXT'},
        'List':      {'postgres': 'ARRAY[]',   'mysql': None,         'sqlite': 'TEXT'},
        }
    for cls in get_tables ():
        fields = []
        for key, field in cls.get_fields ().items ():
            if not isinstance (field[0], storm.properties.PropertyColumn):
                continue
            fieldtype = fieldtypes.get (field[1].__name__, {}).get (dbtype)
            if fieldtype == None:
                continue
            txt = '%s %s' % (key, fieldtype)
            if field[0].primary:
                txt += ' PRIMARY KEY'
                if field[1].__name__ == 'Int':
                    txt += ' AUTOINCREMENT'
            fields.append (txt)
        cmd = 'CREATE TABLE IF NOT EXISTS %s (%s)' % (cls.__name__, ','.join(fields))
        store.execute (cmd)
