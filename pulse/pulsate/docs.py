# Copyright (c) 2006-2008  Shaun McCance  <shaunm@gnome.org>
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

import datetime

from pulse import db, scm, utils

synop = 'update information about documentation'
usage_extra = '[ident]'
args = utils.odict()
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
args['no-update']  = (None, 'do not update SCM checkouts')
def help_extra (fd=None):
    """Print extra help information."""
    print >> fd, 'If ident is passed, only documents with a matching identifier will be updated.'


class DocumentScanner (object):
    _plugins = []
    _checkouts = {}

    def __init__ (self, document, **kw):
        self.document = document
        checkout = kw.pop('checkout', None)
        if checkout == None:
            checkout = DocumentScanner.get_checkout (document,
                                                     update=(not kw.get('no_update', False)))
        self.checkout = checkout
        self._plugins = {}
        for cls in self.__class__._plugins:
            plugin = cls (self)
            self._plugins[cls] = plugin

    @classmethod
    def get_checkout (cls, record, update=True):
        key = '::'.join(map(str,
                            [record.scm_type, record.scm_server,
                             record.scm_module, record.scm_branch,
                             record.scm_path]))
        if not cls._checkouts.has_key (key):
            cls._checkouts[key] = scm.Checkout.from_record (record, update=update)
        return cls._checkouts[key]

    @classmethod
    def register_plugin (cls, plugin):
        cls._plugins.append (plugin)

    def update_document (self, **kw):
        handled = False
        for plugin in self._plugins.values():
            if hasattr (plugin, 'update_document'):
                done = plugin.update_document (**kw)
                handled = handled or (done is True)
        if handled:
            self.document.updated = datetime.datetime.utcnow ()
        else:
            utils.warn ('Skipping document %s with unknown type %s'
                        % (self.document.ident, self.document.subtype))


def main (argv, options=None):
    if options is None:
        options = {}
    kw = {'no_update': options.get ('--no-update', False),
          'no_timestamps': options.get ('--no-timestamps', False)
          }
    if len(argv) == 0:
        ident = None
    else:
        ident = utils.utf8dec (argv[0])

    if ident == None:
        docs = db.Branch.select (type=u'Document')
    elif ident.startswith ('/mod/'):
        docs = db.Branch.select (db.Branch.type == u'Document',
                                 db.Branch.parent_ident.like (ident))
    elif ident.startswith ('/set/'):
        docs = db.Branch.select (db.Branch.type == u'Document',
                                 db.Branch.parent_ident == db.SetModule.pred_ident,
                                 db.SetModule.subj_ident.like (ident))
    else:
        docs = db.Branch.select (db.Branch.type == u'Document',
                                 db.Branch.ident.like (ident))

    for doc in list(docs):
        try:
            DocumentScanner (doc, **kw).update_document (**kw)
            db.flush ()
        except:
            db.rollback ()
            raise
        else:
            db.commit ()

    return 0
