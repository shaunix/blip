import inspect
import sys

from storm.locals import *
import storm.properties
import storm.tracer

import pulse.config
import pulse.utils

#storm.tracer.debug (True, stream=sys.stdout)

database = create_database (pulse.config.database)
store = Store (database)

def flush ():
    store.flush()

def commit ():
    store.commit ()

def rollback ():
    store.rollback ()


################################################################################
## Trigger decorators

def field_trigger (cls, field):
    def triggered (func):
        cls.add_field_trigger (field, func)
        return func
    return triggered


################################################################################
## Base Classes


class PulseModelType (storm.properties.PropertyPublisherMeta):
    def __new__ (meta, name, bases, attrs):
        cls = super (PulseModelType, meta).__new__ (meta, name, bases, attrs)
        cls._field_triggers = {}
        cls._record_cache = {}
        if not name in ['PulseModel', 'PulseRecord', 'PulseRelation']:
            cls.__storm_table__ = cls.__name__
        return cls


class PulseModel (Storm):
    __metaclass__ = PulseModelType

    @classmethod
    def get_fields (cls):
        fields = {}
        for key, prop in inspect.getmembers (cls):
            if not isinstance (prop, storm.properties.PropertyColumn):
                continue
            fields[key] = (prop, prop.__get__.im_class)
        return fields


class PulseRelation (PulseModel):
    id = Int (primary=True)
    subj_ident = Unicode ()
    pred_ident = Unicode ()

    @classmethod
    def set_related (cls, subj, pred, **kw):
        rel = store.find (cls, subj_ident=subj.ident, pred_ident=pred.ident).one ()
        if rel == None:
            rel = cls ()
            rel.subj = subj
            rel.pred = pred
            store.add (rel)
        if len(kw) > 0:
            for k, v in kw.items():
                setattr (rel, k, v)
        return rel

    @classmethod
    def get_related (cls, subj, pred):
        if subj != None and pred != None:
            rel = store.find (cls, subj_ident=subj.ident, pred_ident=pred.ident)
            return rel or False
        elif subj != None:
            # FIXME STORM: django has select_related
            return list(store.find (cls, subj_ident=subj.ident))
        elif pred != None:
            # FIXME STORM
            return list(store.find (cls, pred_ident=pred.ident))
        else:
            return None


class PulseRecord (PulseModel):
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
            return self.title_default ()
        return self.localized_name

    @classmethod
    def create (cls, ident, type):
        record = cls ()
        record.ident = ident
        record.type = type
        store.add (record)
        cls.set_cached (ident, record)
        record._emit_field_triggers ('ident')
        return record

    @classmethod
    def get_or_create (cls, ident, type):
        record = cls.get_cached (ident)
        if record != None:
            return record
        return cls.create (ident, type)

    @classmethod
    def get_cached (cls, ident):
        if cls._record_cache.has_key (ident):
            return cls._record_cache[ident]
        record = cls.find (ident=ident).one ()
        if record != None:
            cls.set_cached (ident, record)
        return record

    @classmethod
    def set_cached (cls, ident, record):
        cls._record_cache[ident] = record

    @ classmethod
    def find (cls, *args, **kw):
        return store.find (cls, *args, **kw)

    def _update_or_extend (self, overwrite, data={}, **kw):
        fields = self.__class__.get_fields ()
        triggers = []
        for key, val in data.items() + kw.items():
            field, fieldcls = fields.get (key, (None, None))
            if fieldcls == None:
                if overwrite or (self.data.get (key) == None):
                    for trig in ('data', 'data.' + key):
                        if not trig in triggers:
                            triggers.append (trig)
                    self.data[key] = val
                pass
            elif issubclass (fieldcls, Pickle):
                dd = getattr (self, key, {})
                if not isinstance (val, dict):
                    val = {'C': val}
                for subkey, subval in val.items ():
                    if overwrite or (dd.get (subkey) == None):
                        for trig in (key, key + '.' + subkey):
                            if not trig in triggers:
                                triggers.append (trig)
                        dd[subkey] = subval
            else:
                if overwrite or (getattr (self, key) == None):
                    if not key in triggers:
                        triggers.append (key)
                    if issubclass (fieldcls, Unicode) and isinstance (val, str):
                        val = pulse.utils.utf8dec (val)
                    setattr (self, key, val)
        for field in triggers:
            self._emit_field_triggers (field)
        return self

    def update (self, data={}, **kw):
        return self._update_or_extend (True, data, **kw)

    def extend (self, data={}, **kw):
        return self._update_or_extend (False, data, **kw)

    def set_relations (self, cls, rels):
        old = list (store.find (cls, subj_ident=self.ident))
        olddict = {}
        for rel in old:
            olddict[rel.pred_ident] = rel
        for rel in rels:
            olddict.pop (rel.pred_ident, None)
        oldids = [old.id for old in olddict.values()]
        store.find (cls, cls.id.is_in (oldids)).remove ()

    @classmethod
    def add_field_trigger (cls, field, func):
        cls._field_triggers.setdefault (field, [])
        cls._field_triggers[field].append (func)

    def _emit_field_triggers (self, field):
        for func in self.__class__._field_triggers.get (field, []):
            func (self, field)


################################################################################
## Records


class ReleaseSet (PulseRecord):
    parent_ident = Unicode ()
    parent = Reference (parent_ident, 'ReleaseSet.ident')
    pass


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

    @property
    def title_default (self):
        id = self.ident.split('/')[-2]
        if self.type == 'Domain':
            if id == 'po':
                return self.scm_module
            else:
                return pulse.utils.gettext ('%s (%s)') % (self.scm_module, id)
        return id

@field_trigger (Branch, 'ident')
def set_branchable (record, field):
    ident = u'/'.join (record.ident.split('/')[:-1])
    record.update (branchable=ident)


class Entity (PulseRecord):
    parent_ident = Unicode ()
    parent = Reference (parent_ident, 'Entity.ident')
    nick = Unicode ()
    mod_score = Int ()
    mod_score_diff = Int ()
    post_score = Int ()
    post_score_diff = Int ()


class Alias (PulseRecord):
    entity_ident = Unicode ()
    entity = Reference (entity_ident, 'Entity.ident')


class Forum (PulseRecord):
    post_score = Int ()
    post_score_diff = Int ()


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


@field_trigger (ForumPost, 'datetime')
def forum_post_weeknum (post, field):
    post.weeknum = pulse.utils.weeknum (post.datetime)


################################################################################
## Relations

class Documentation (PulseRelation):
    subj = Reference (PulseRelation.subj_ident, Branch.ident)
    pred = Reference (PulseRelation.pred_ident, Branch.ident)

class DocumentEntity (PulseRelation):
    subj = Reference (PulseRelation.subj_ident, Branch.ident)
    pred = Reference (PulseRelation.pred_ident, Entity.ident)
    maintainer = Bool (default=False)
    author = Bool (default=False)
    editor = Bool (default=False)
    publisher = Bool (default=False)

class ModuleDependency (PulseRelation):
    subj = Reference (PulseRelation.subj_ident, Branch.ident)
    pred = Reference (PulseRelation.pred_ident, Branch.ident)
    direct = Bool ()

class ModuleEntity (PulseRelation):
    subj = Reference (PulseRelation.subj_ident, Branch.ident)
    pred = Reference (PulseRelation.pred_ident, Entity.ident)
    maintainer = Bool (default=False)

class SetModule (PulseRelation):
    subj = Reference (PulseRelation.subj_ident, ReleaseSet.ident)
    pred = Reference (PulseRelation.pred_ident, Branch.ident)

class TeamMember (PulseRelation):
    subj = Reference (PulseRelation.subj_ident, Entity.ident)
    pred = Reference (PulseRelation.pred_ident, Entity.ident)
    coordinator = Bool (default=False)


################################################################################

def create_tables ():
    dbtype = pulse.config.database[:pulse.config.database.find(':')]
    fieldtypes = {
        'Bool':      {'postgres': 'BOOL',      'mysql': 'TINYINT(1)', 'sqlite': 'INT'},
        'Int':       {'postgres': 'INT',       'mysql': 'INT',        'sqlite': 'INT'},
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
    for cls in sys.modules[__name__].__dict__.values():
        if not inspect.isclass (cls):
            continue
        if not issubclass (cls, PulseModel):
            continue
        if not hasattr (cls, '__storm_table__'):
            continue
        fields = []
        for key, field in cls.get_fields ().items ():
            fieldtype = fieldtypes.get (field[1].__name__, {}).get (dbtype)
            if fieldtype == None:
                continue
            txt = '%s %s' % (key, fieldtype)
            if field[0].primary:
                txt += ' PRIMARY KEY'
            fields.append (txt)
        cmd = 'CREATE TABLE IF NOT EXISTS %s (%s)' % (cls.__name__, ','.join(fields))
        store.execute (cmd)
