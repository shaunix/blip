import datetime
import inspect
import os
import sys

from storm.locals import *
from storm.expr import Variable, LeftJoin
from storm.info import ClassAlias
import storm.properties
import storm.references
import storm.store

import pulse.config
import pulse.utils

database = create_database (pulse.config.database)
store = Store (database)
store_options = {'rollback' : False}

def flush ():
    store.flush()

def commit ():
    if store_options.get ('rollback', False):
        pulse.utils.log ('Not committing changes')
    else:
        pulse.utils.log ('Committing changes')
        store.commit ()

def rollback ():
    pulse.utils.log ('Rolling back changes')
    try:
        store.rollback ()
    except:
        pulse.utils.warn ('Could not roll back changes')

def rollback_all ():
    store_options['rollback'] = True

def block_implicit_flushes ():
    store.block_implicit_flushes ()


################################################################################
## Debugging

class PulseTracer (object):
    select_count = 0
    select_total = 0
    insert_count = 0
    insert_total = 0
    update_count = 0
    update_total = 0
    other_count = 0
    other_total = 0
    
    def __init__ (self, stream=None):
        self._stream = stream or sys.stderr
        self._last_time = None

    @staticmethod
    def timing_string (seconds):
        milli = 1000 * seconds
        micro = 1000 * (milli - int(milli))
        timing = '%03i.%03i' % (int(milli), int(micro))
        return timing

    def connection_raw_execute (self, connection, raw_cursor, statement, params):
        self._last_time = datetime.datetime.now()
        self.print_command (statement, params)

    def print_command (self, statement, params):
        diff = datetime.datetime.now() - self._last_time
        sec = diff.seconds + (diff.microseconds / 1000000.)
        timing = PulseTracer.timing_string (sec)
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
            import re
            outtxt = re.split (' (?=WHERE|AND|GROUP BY|ORDER BY|LIMIT)', cmd)
            sel, frm = outtxt[0].split (' FROM ')
            if not sel.startswith ('SELECT COUNT'):
                sel = 'SELECT ...'
            outtxt[0] = sel + ' FROM ' + frm
        elif cmd.startswith ('INSERT '):
            self.__class__.insert_count += 1
            self.__class__.insert_total += sec
            outtxt.append (cmd)
        elif cmd.startswith ('UPDATE '):
            self.__class__.update_count += 1
            self.__class__.update_total += sec
            outtxt.append (cmd)
        elif cmd.startswith ('COMMIT') or cmd.startswith ('ROLLBACK'):
            outtxt.append (cmd)
        else:
            self.__class__.other_count += 1
            self.__class__.other_total += sec
            outtxt.append (cmd)

        self._stream.write ((u'%sms  %s\n' % (timing, outtxt[0])).encode ('utf8'))
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

def debug_summary ():
    print '---------'
    timing = PulseTracer.timing_string (PulseTracer.select_total)
    print '%i SELECT statements in %sms' % (PulseTracer.select_count, timing)
    if PulseTracer.insert_total > 0:
        timing = PulseTracer.timing_string (PulseTracer.insert_total)
        print '%i INSERT statements in %sms' % (PulseTracer.insert_count, timing)
    if PulseTracer.update_total > 0:
        timing = PulseTracer.timing_string (PulseTracer.update_total)
        print '%i UPDATE statements in %sms' % (PulseTracer.update_count, timing)
    if PulseTracer.other_total > 0:
        timing = PulseTracer.timing_string (PulseTracer.other_total)
        print '%i other statements in %sms' % (PulseTracer.other_count, timing)
    


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
        record = cls.get (ident)
        if record != None:
            return record
        return cls (ident, type, **kw)

    @classmethod
    def get (cls, ident):
        return store.get (cls, ident)

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
        return record

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


class ReleaseSet (PulseRecord):
    parent_ident = Unicode ()
    parent = Reference (parent_ident, 'ReleaseSet.ident')

    subsets = ReferenceSet ('ReleaseSet.ident', parent_ident)

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

    @property
    def watchable (self):
        return self.type == 'Module'

    @property
    def is_default (self):
        return self.scm_branch == pulse.scm.default_branches.get (self.scm_type)

    @classmethod
    def count_branchables (cls, type):
        return store.find (cls, type=type).count (cls.branchable, distinct=True)

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
        args, kw = cls._select_args (*args, **kw)
        return store.find (cls, *args, **kw)

    @ classmethod
    def select_with_mod_person (cls, *args, **kw):
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
    def select_with_statistic (cls, stattype, *args, **kw):
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


class Entity (PulseRecord):
    parent_ident = Unicode ()
    parent = Reference (parent_ident, 'Entity.ident')
    nick = Unicode ()
    mod_score = Int ()
    mod_score_diff = Int ()
    post_score = Int ()
    post_score_diff = Int ()

    @classmethod
    def get (cls, ident, alias=True):
        ent = store.get (cls, ident)
        if ent == None and alias:
            ent = Alias.get (ident)
            if ent != None:
                ent = ent.entity
        return ent

    def select_children (self):
        return self.__class__.select (parent=self)

    @property
    def linkable (self):
        return self.type != 'Ghost'

    @property
    def watchable (self):
        return self.type == 'Module'


class Alias (PulseRecord):
    entity_ident = Unicode ()
    entity = Reference (entity_ident, 'Entity.ident')

    def delete (self):
        raise WillNotDelete ('Pulse will not delete aliases')

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
            args.append (Revision.id == RevisionFile.revision_id)
            if len(files) == 1:
                args.append (RevisionFile.filename == files[0])
            else:
                args.append (RevisionFile.filename.is_in (files))
        if range != None:
            args.append (And (Revision.weeknum >= range[0],
                              Revision.weeknum <= range[1]))
        sel = store.find (cls, *args, **kw)
        if files != None:
            sel = sel.group_by (Revision.id)
        return sel.order_by (Desc (Revision.datetime))

    @classmethod
    def count_revisions (cls, *args, **kw):
        args = list (args)
        files = kw.pop ('files', None)
        range = kw.pop ('week_range', None)
        if files != None:
            args.append (Revision.id == RevisionFile.revision_id)
            if len(files) == 1:
                args.append (RevisionFile.filename == files[0])
            else:
                args.append (RevisionFile.filename.is_in (files))
        if range != None:
            args.append (And (Revision.weeknum >= range[0],
                              Revision.weeknum <= range[1]))
        sel = store.find (cls, *args, **kw)
        return sel.count (Revision.id, distinct=True)


class RevisionFile (PulseModel):
    id = Int (primary=True)

    revision_id = Int ()
    revision = Reference (revision_id, Revision.id)

    filename = Unicode ()
    filerev = Unicode ()
    prevrev = Unicode ()

    def log_create (self):
        pass


class Statistic (PulseModel):
    __storm_primary__ = 'branch_ident', 'daynum', 'type'

    branch_ident = Unicode ()
    branch = Reference (branch_ident, Branch.ident)
    daynum = Int ()
    type = Unicode ()
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
        indexes = []
        for key, field in cls.get_fields ().items ():
            if not isinstance (field[0], storm.properties.PropertyColumn):
                continue
            fieldtype = fieldtypes.get (field[1].__name__, {}).get (dbtype)
            if fieldtype == None:
                continue
            txt = '%s %s' % (key, fieldtype)
            if field[1].__name__ != 'Pickle':
                indexes.append ('CREATE INDEX IF NOT EXISTS %s__%s ON %s (%s);'
                                % (cls.__name__, key, cls.__name__, key))
            if field[0].primary:
                txt += ' PRIMARY KEY'
                if field[1].__name__ == 'Int':
                    txt += ' AUTOINCREMENT'
            fields.append (txt)
        cmd = 'CREATE TABLE IF NOT EXISTS %s (%s)' % (cls.__name__, ','.join(fields))
        store.execute (cmd, noresult=True)
        for index in indexes:
            store.execute (index, noresult=True)
