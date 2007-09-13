# Copyright (c) 2006  Shaun McCance  <shaunm@gnome.org>
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
from sqlobject.inheritance import InheritableSQLObject
from sqlobject.sqlbuilder import LEFTJOINOn

import pulse.config as config
import pulse.utils as utils

conn = sql.connectionForURI (config.dbroot)
sql.sqlhub.processConnection = conn
sql.setDeprecationLevel (None)

class textprop (property):
    def __init__ (self, verb, default=None):
        def getter (s):
            # FIXME: internationalize right
            out = s.get_text (verb, ['C'])
            if out != None:
                return out
            elif default != None:
                return default (s)
            else:
                return None
        property.__init__ (self, getter)

class relatedprop (property):
    def __init__ (self, verb, cls=None, invert=False):
        self.verb = verb
        self.cls = cls
        self.invert = invert
        property.__init__ (self,
                           lambda s: s.get_related (verb=verb, cls=cls, invert=invert))

class Resource (InheritableSQLObject):
    class sqlmeta:
        table = 'Resource'
    
    def __init__ (self, **kw):
        InheritableSQLObject.__init__ (self, **kw)
        self._texts = {}

    # These produce an AttributeError in sqlobject 0.7.0
    # We really need to do introspection, and we don't
    # actually need these two, so *POOF*!
    delIndex = None
    getSchema = None

    ident = sql.StringCol (alternateID=True)
    nick = sql.StringCol (default=None)
    icon = sql.StringCol (default=None)
    web  = sql.StringCol (default=None)
    mail = sql.StringCol (default=None)

    name = textprop ('name', lambda s: s.ident.split('/')[-1])
    blurb = textprop ('blurb')
    def get_text (self, verb, langs):
        if self._texts.has_key (verb):
            if self._texts[verb][0] == langs[0]:
                return self._texts[verb][1]

        texts = Text.select (sql.AND (Text.q.resourceID == self.id,
                                      Text.q.verb == verb,
                                      sql.IN (Text.q.lang, langs)))
        txt = None
        pri = None
        for t in texts:
            try:
                idx = langs.index (t.lang)
                if idx == 0:
                    txt = t
                    break
                elif pri == None or idx < pri:
                    txt = t
                    pri = idx
            except ValueError:
                pass
        if txt != None:
            self._texts[verb] = (txt.lang, txt.text)
            return self._texts[verb][1]
        else:
            return None

    def set_text (self, verb, lang, text):
        texts = Text.select (sql.AND (Text.q.resourceID == self.id,
                                      Text.q.verb == verb,
                                      Text.q.lang == lang))
        fin = False
        if texts.count() > 0:
            t = texts[0]
            if t.text != text:
                t.set (text=text)
            if texts.count() > 1:
                for t in texts[1:]:
                    t.destroySelf()
        else:
            Text (resource=self, verb=verb, lang=lang, text=text)

    def get_related (self, verb=None, cls=None, invert=False):
        if invert:
            subjp = (Relation.q.predID == self.id)
            keyp = (Relation.q.subjID == Resource.q.id)
        else:
            subjp = (Relation.q.subjID == self.id)
            keyp = (Relation.q.predID == Resource.q.id)

        if verb == None:
            verbp = True
        elif isinstance (verb, list):
            verbp = sql.IN (Relation.q.verb, verb)
        else:
            verbp = (Relation.q.verb == verb)

        rels = Relation.select (
            subjp,
            join = LEFTJOINOn (Relation, Resource, sql.AND (keyp, verbp)) )

        ret = []
        for r in rels:
            rel = Related (r, invert=invert)
            if cls == None:
                ret.append (rel)
            elif isinstance (cls, list):
                for t in cls:
                    if isinstance (t, basestring):
                        if isinstance (rel.resource, getattr (sys.modules[__name__], t)):
                            ret.append (rel)
                            break
                    else:
                        if isinstance (rel.resource, t):
                            ret.append (rel)
                            break
            elif isinstance (cls, basestring):
                if isinstance (rel.resource, getattr (sys.modules[__name__], cls)):
                    ret.append (rel)
            else:
                if isinstance (rel.resource, cls):
                    ret.append (rel)
        return ret

    def add_related (self, resource, verb, comment=None, invert=False):
        if invert:
            subj = resource
            pred = self
        else:
            subj = self
            pred = resource
        rel = Relation.select (sql.AND(Relation.q.subjID == subj.id,
                                       Relation.q.predID == pred.id,
                                       Relation.q.verb == verb))
        if rel.count() == 0:
            rel = Relation (subj = subj, pred = pred,
                            verb = verb, comment = comment)
        else:
            rel = rel[0]
            if comment != None and rel.comment != comment:
                rel.comment = comment

        return Related (rel)

    @classmethod
    def get_column_defs (cls):
        # sqlmeta.columnDefinitions only returns the columns for the
        # particular table, but we want to see all the columns of all
        # inherited tables.
        defs = {}
        for c in inspect.getmro (cls):
            if c.__module__ != __name__:
                break
            defs.update (c.sqlmeta.columnDefinitions)
        defs.update (cls.sqlmeta.columnDefinitions)
        # childName is an artifact of InheritableSQLObject, and we don't
        # want to deal with it in any code that consumes this module.
        del defs['childName']
        return defs

class RcsResource (Resource):
    class sqlmeta:
        table = 'RcsResource'
    rcs_server = sql.ForeignKey ('RcsServer', default=None)
    rcs_module = sql.StringCol ()
    rcs_branch = sql.StringCol (default=None)
    rcs_dir    = sql.StringCol (default=None)
    rcs_file   = sql.StringCol (default=None)
    rcs_web    = sql.StringCol (default=None)

    download = sql.StringCol (default=None)

    bug_server = sql.ForeignKey ('BugServer', default=None)
    bug_product = sql.StringCol (default=None)
    bug_component = sql.StringCol (default=None)
    bug_assignee = sql.ForeignKey ('Person', default=None)
    bug_contact = sql.ForeignKey ('Person', default=None)
    bug_assignee_email = sql.StringCol (default=None)
    bug_contact_email = sql.StringCol (default=None)
    # maybe "bug_version" or some such

    # If an error occured, a description of the error
    error = sql.UnicodeCol (default=None)

    # When was the information last updates from the rcs?
    updated = sql.DateCol (default=None)


class Module (RcsResource):
    # ident = modules/<module>/<branch>
    class sqlmeta:
        table = 'Module'
    _inheritable = False

    developers = relatedprop ('developer')
    mail_lists = relatedprop ('mail_list')

class Branch (RcsResource):
    # ident = modules/<module>/<branch>
    class sqlmeta:
        table = 'Branch'
    _inheritable = False

    module = sql.ForeignKey ('Module')

class Document (RcsResource):
    # ident = docs/<module>/<branch>/<document>
    class sqlmeta:
        table = 'Document'
    _inheritable = False

    branch = sql.ForeignKey ('Branch')

    # Which tool is responsible for managing this document?
    # For GNOME, this is either gnome-doc-utils or gtk-doc.
    tool = sql.StringCol ()

    authors = relatedprop ('author')
    editors = relatedprop ('editor')
    mail_lists = relatedprop ('mail_list')

    status = sql.StringCol (default=None)

    translations = sql.MultipleJoin ('Translation',
                                     joinColumn='source', orderBy='ident')

class Domain (RcsResource):
    # ident = i18n/<module>/<branch>/<domain>
    class sqlmeta:
        table = 'Domain'
    _inheritable = False

    branch = sql.ForeignKey ('Branch')

    translations = sql.MultipleJoin ('Translation',
                                     joinColumn='source', orderBy='ident')

class Translation (RcsResource):
    # ident = l10n/<lang>/<module>/<branch>/[i18n/<domain>|docs/<document>]
    class sqlmeta:
        table = 'Translation'
    _inheritable = False

    # This points to a Domain or a Document
    source = sql.ForeignKey ('RcsResource', default=None)

    # Which tool is responsible for managing this translation?
    # For GNOME, this is either intltool or xml2po.
    tool = sql.StringCol (default=None)


class MailList (Resource):
    # ident = lists/<list>
    class sqlmeta:
        table = 'MailList'
    _inheritable = False

    list_type = sql.StringCol (default=None)
    list_info = sql.StringCol (default=None)
    list_archive = sql.StringCol (default=None)

    resource = relatedprop ('mail_list', invert=True)
    documents = relatedprop ('mail_list', 'Document', invert=True)
    modules = relatedprop ('mail_list', 'Module', invert=True)
    translation_teams = relatedprop ('mail_list', 'TranslationTeam', invert=True)


class Person (Resource):
    # ident = people/<person>
    class sqlmeta:
        table = 'Person'
    _inheritable = False

    developer_for = relatedprop ('developer', invert=True)
    translator_for = relatedprop ('member', 'TranslationTeam', invert=True)
    author_for = relatedprop ('author', 'Document', invert=True)
    editor_for = relatedprop ('editor', 'Document', invert=True)

    def get_accounts (self):
        acctd = {}
        accts = ServerAccount.select (ServerAccount.q.personID == self.id)
        for acct in acct:
            acctd[acct.server.name] = acct
        return map (lambda key: acctd[key], utils.isorted (acctd.keys()))
    accounts = property (lambda s: s.get_accounts())


class TranslationTeam (Resource):
    # ident = l10n/<lang>
    class sqlmeta:
        table = 'TranslationTeam'
    _inheritable = False

    members = relatedprop ('member')
    mail_lists = relatedprop ('mail_list')


class Server (Resource):
    class sqlmeta:
        table = 'Server'

    def get_accounts (self):
        acctd = {}
        accts = ServerAccount.select (ServerAccount.q.serverID == self.id)
        for acct in acct:
            acctd[acct.person.name] = acct
        return map (lambda key: acctd[key], utils.isorted (acctd.keys()))
    accounts = property (lambda s: s.get_accounts())

class BugServer (Server):
    # ident = bug/<server>
    class sqlmeta:
        table = 'BugServer'
    _inheritable = False

    bug_type = sql.StringCol ()
    bug_root = sql.StringCol ()

class RcsServer (Server):
    # ident = rcs/<server>
    class sqlmeta:
        table = 'RcsServer'
    _inheritable = False

    rcs_type = sql.StringCol ()
    rcs_root = sql.StringCol ()

class ServerAccount (sql.SQLObject):
    class sqlmeta:
        table = 'ServerAccount'
    person = sql.ForeignKey ('Person')
    server = sql.ForeignKey ('Server')
    user = sql.StringCol ()



# l10n-team    l10n/<lang>
# translation  l10n/<lang>/<module>/<branch>/po/<domain>
# translation  l10n/<lang>/<module>/<branch>/doc/<document>
# release      sets/<release>
# program      ???

class Related:
    def __init__ (self, relation, invert=False):
        self._relation = relation
        self._invert = invert
        self.verb = self._relation.verb
        self.comment = self._relation.comment
        if invert:
            self.resource = self._relation.subj
        else:
            self.resource = self._relation.pred

class Relation (sql.SQLObject):
    class sqlmeta:
        table = 'Relation'
    subj = sql.ForeignKey ('Resource', dbName='subj')
    pred = sql.ForeignKey ('Resource', dbName='pred')
    verb = sql.StringCol ()
    comment = sql.StringCol (default=None)

class Text (sql.SQLObject):
    class sqlmeta:
        table = 'Text'
    resource = sql.ForeignKey ('Resource')
    verb = sql.StringCol ()
    lang = sql.StringCol ()
    text = sql.UnicodeCol ()


def create_tables ():
    for table in inspect.getmembers (sys.modules[__name__]):
        if (hasattr (table[1], 'createTable')
            and inspect.isclass (table[1])
            and not table[0].endswith('SQLObject')):

            table[1].createTable (ifNotExists=True)
