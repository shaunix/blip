# Copyright (c) 2006-2009  Shaun McCance  <shaunm@gnome.org>
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

"""
Update information from module and branch checkouts
"""

import commands
import datetime
import os
import os.path
import re

import xml.dom.minidom

import pulse.db
import pulse.graphs
import pulse.scm
import pulse.parsers
import pulse.pulsate
import pulse.utils

import pulse.pulsate.docs

synop = 'update information from module and branch checkouts'
usage_extra = '[ident]'
args = pulse.utils.odict()
args['no-history'] = (None, 'do not check SCM history')
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
args['no-update']  = (None, 'do not update SCM checkouts')
args['no-docs'] = (None, 'do not update the documentation')
args['no-i18n'] = (None, 'do not update the translations')
def help_extra (fd=None):
    """Print extra help information."""
    print >> fd, 'If ident is passed, only modules and branches with a matching identifier will be updated.'


class ModuleScanner (object):
    _plugins = []
    
    def __init__ (self, branch, **kw):
        self.branch = branch
        self.checkout = pulse.scm.Checkout.from_record (branch,
                                                        update=(not kw.get('no_update', False)))
        self._plugins = {}
        for cls in self.__class__._plugins:
            plugin = cls (self)
            self._plugins[cls] = plugin
        self._parsed_files = {}
        self._children = {}

    @classmethod
    def register_plugin (cls, plugin):
        cls._plugins.append (plugin)

    def get_plugin (self, cls):
        return self._plugins.get (cls, None)

    def add_child (self, child):
        self._children.setdefault (child.type, [])
        if child not in self._children[child.type]:
            self._children[child.type].append (child)

    def get_parsed_file (self, parser, filename):
        if not self._parsed_files.has_key ((parser, filename)):
            self._parsed_files[(parser, filename)] = parser (filename)
        return self._parsed_files[(parser, filename)]

    def update (self, **kw):
        if self.checkout.error is not None:
            self.branch.update (error=checkout.error)
            return
        else:
            self.branch.update (error=None)

        if not kw.get ('no_history', False):
            self.check_history ()

        pulse.pulsate.update_graphs (self.branch, {'branch' : self.branch}, 80, **kw)

        def visit (arg, dirname, names):
            for ignore in (self.checkout.ignoredir, 'examples', 'test', 'tests'):
                if ignore in names:
                    names.remove (ignore)
            for basename in names:
                filename = os.path.join (dirname, basename)
                if not os.path.isfile (filename):
                    continue
                for plugin in self._plugins.values():
                    if hasattr (plugin, 'process_file'):
                        plugin.process_file (dirname, basename, **kw)
        os.path.walk (self.checkout.directory, visit, None)

        for plugin in self._plugins.values():
            if hasattr (plugin, 'post_process'):
                plugin.post_process (**kw)

        for type in self._children.keys ():
            self.branch.set_children (type, self._children[type])


    def check_history (self):
        since = pulse.db.Revision.get_last_revision (branch=self.branch)
        if since != None:
            since = since.revision
            current = self.checkout.get_revision()
            if current != None and since == current[0]:
                pulse.utils.log ('Skipping history for %s' % self.branch.ident)
                return
        pulse.utils.log ('Checking history for %s' % self.branch.ident)
        serverid = u'.'.join (pulse.scm.server_name (self.checkout.scm_type,
                                                     self.checkout.scm_server).split('.')[-2:])
        for hist in self.checkout.read_history (since=since):
            if hist['author'][0] != None:
                pident = u'/person/%s@%s' % (hist['author'][0], serverid)
                person = pulse.db.Entity.get_or_create (pident, u'Person')
            elif hist['author'][2] != None:
                pident = u'/person/' + hist['author'][2]
                person = pulse.db.Entity.get_or_create_email (hist['author'][2])
            else:
                pident = u'/ghost/%' % hist['author'][1]
                person = pulse.db.Entity.get_or_create (pident, u'Ghost')

            if person.type == u'Person':
                pulse.db.Queue.push (u'people', person.ident)
            if hist['author'][1] != None:
                person.extend (name=hist['author'][1])
            if hist['author'][2] != None:
                person.extend (email=hist['author'][2])
            # IMPORTANT: If we were to just set branch and person, instead of
            # branch_ident and person_ident, Storm would keep referencess to
            # the Revision object.  That would eat your computer.
            revident = self.branch.ident + u'/' + hist['revision']
            rev = {'ident': revident,
                   'branch_ident': self.branch.ident,
                   'person_ident': person.ident,
                   'revision': hist['revision'],
                   'datetime': hist['datetime'],
                   'comment': hist['comment'] }
            if person.ident != pident:
                rev['alias_ident'] = pident
            if pulse.db.Revision.select(ident=revident).count() > 0:
                continue
            rev = pulse.db.Revision (**rev)
            rev.decache ()
            for filename, filerev, prevrev in hist['files']:
                revfile = rev.add_file (filename, filerev, prevrev)
                revfile.decache ()
            pulse.db.flush()

        pulse.db.Revision.flush_file_cache ()
        revision = pulse.db.Revision.get_last_revision (branch=self.branch)
        if revision != None:
            self.branch.mod_datetime = revision.datetime
            self.branch.mod_person = revision.person



#############################################

def update_branch (branch, **kw):

    default_child = None

    if default_child == None:
        if len(applications) == 1 and len(applets) == 0:
            default_child = applications[0]
        elif len(applets) == 1 and len(applications) == 0:
            default_child = applets[0]
        elif len(applications) > 0:
            for app in applications:
                if app.data.get ('exec', None) == branch.scm_module:
                    default_child = app
                    break
        elif len(applets) > 0:
            pass
        elif len(capplets) == 1:
            default_child = capplets[0]

    if default_child != None:
        branch.name = default_child.name
        branch.desc = default_child.desc
        branch.icon_dir = default_child.icon_dir
        branch.icon_name = default_child.icon_name
        if default_child.data.has_key ('screenshot'):
            branch.data['screenshot'] = default_child.data['screenshot']
    else:
        branch.name = {'C' : branch.scm_module}
        branch.desc = {}
        branch.icon_dir = None
        branch.icon_name = None
        branch.data.pop ('screenshot', None)

    branch.updated = datetime.datetime.utcnow ()
    pulse.db.Queue.remove ('modules', branch.ident)
    

def main (argv, options={}):
    kw = {'no_update': options.get ('--no-update', False),
          'no_timestamps': options.get ('--no-timestamps', False),
          'no_history': options.get ('--no-history', False),
          'no_docs': options.get ('--no-docs', False),
          'no_i18n': options.get ('--no-i18n', False)
          }
    if len(argv) == 0:
        ident = None
    else:
        ident = pulse.utils.utf8dec (argv[0])

    if ident != None:
        if ident[:5] == u'/set/':
            branches = pulse.db.Branch.select (pulse.db.Branch.type == u'Module',
                                               pulse.db.Branch.ident == pulse.db.SetModule.pred_ident,
                                               pulse.db.SetModule.subj_ident.like (ident))
        else:
            branches = pulse.db.Branch.select (pulse.db.Branch.type == u'Module',
                                               pulse.db.Branch.ident.like (ident))
    else:
        branches = pulse.db.Branch.select (pulse.db.Branch.type == u'Module')

    for branch in list(branches):
        try:
            ModuleScanner (branch, **kw).update (**kw)
            pulse.db.flush ()
        except:
            pulse.db.rollback ()
            raise
        else:
            pulse.db.commit ()

    return 0
