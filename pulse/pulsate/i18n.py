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

"""
Update information about translations and translation domains.
"""

import datetime

import storm.info

from pulse import db, scm, utils

synop = 'update information about translations'
usage_extra = '[ident]'
args = utils.odict()
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
args['no-update']  = (None, 'do not update SCM checkouts')
def help_extra (fd=None):
    """Print extra help information."""
    print >> fd, 'If ident is passed, only translations with a matching identifier will be updated.'


class TranslationScanner (object):
    _plugins = []
    _checkouts = {}

    def __init__ (self, translation, **kw):
        self.translation = translation
        checkout = kw.pop('checkout', None)
        if checkout == None:
            checkout = TranslationScanner.get_checkout (translation,
                                                        update=(not kw.get('no_update', False)))
        self.checkout = checkout
        self._plugins = {}
        for cls in self.__class__._plugins:
            plugin = cls (self)
            self._plugins[cls] = plugin

    @classmethod
    def get_checkout (cls, record, update=True):
        """
        Get an SCM checkout for a translation.
        """
        key = '::'.join(map(str,
                            [record.scm_type, record.scm_server,
                             record.scm_module, record.scm_branch,
                             record.scm_path]))
        if not cls._checkouts.has_key (key):
            cls._checkouts[key] = scm.Checkout.from_record (record, update=update)
        return cls._checkouts[key]

    @classmethod
    def register_plugin (cls, plugin):
        """
        Register a plugin class for all TranslationScanner objects.
        """
        cls._plugins.append (plugin)

    def update_translation (self, **kw):
        """
        Update information about a translation.
        """
        handled = False
        for plugin in self._plugins.values():
            if hasattr (plugin, 'update_translation'):
                done = plugin.update_translation (**kw)
                handled = handled or (done is True)
        if handled:
            self.translation.updated = datetime.datetime.utcnow ()
        else:
            utils.warn ('Skipping translation %s with unknown type %s'
                        % (self.translation.ident, self.translation.subtype))


def update_translation (translation, **kw):
    """
    Update information about a translation.
    """
    TranslationScanner (translation, **kw).update_translation (**kw)


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
        pos = db.Branch.select (type=u'Translation')
    elif ident.startswith ('/set/'):
        Domain = storm.info.ClassAlias (db.Branch)
        pos = db.Branch.select (
            db.Branch.type == u'Translation',
            db.Branch.parent_ident == Domain.ident,
            Domain.parent_ident == db.SetModule.pred_ident,
            db.SetModule.subj_ident.like (ident))
    elif (ident.startswith ('/i18n/') or
          ident.startswith ('/doc/')  or
          ident.startswith ('/ref/')  ):
        pos = db.Branch.select (
            db.Branch.type == u'Translation',
            db.Branch.parent_ident.like (ident))
    elif ident.startswith ('/mod/'):
        Domain = storm.info.ClassAlias (db.Branch)
        pos = db.Branch.select (
            db.Branch.type == u'Translation',
            db.Branch.parent_ident == Domain.ident,
            Domain.parent_ident.like (ident))
    else:
        pos = db.Branch.select (
            db.Branch.type == u'Translation',
            db.Branch.ident.like (ident))

    for po in list(pos):
        try:
            update_translation (po, **kw)
            db.flush ()
        except:
            db.rollback ()
            raise
        else:
            db.commit ()

    return 0

