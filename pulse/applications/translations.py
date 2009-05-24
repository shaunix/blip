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

import math
import urllib

from pulse import applications, core, db, html, utils

class TranslationsTab (applications.TabProvider):
    application_id = 'translations'
    tab_group = applications.TabProvider.CORE_TAB

    def __init__ (self, handler):
        super (TranslationsTab, self).__init__ (handler)

    def get_tab_title (self):
        return utils.gettext ('Translations')

    def handle_request (self):
        contents = None
        action = self.handler.request.query.get ('action')
        if action == 'domain':
            contents = self.get_domain_div ()
        elif action == 'tab':
            contents = self.get_tab ()
        if contents is not None:
            self.handler.response.set_contents (contents)

    def get_tab (self):
        box = html.PaddingBox ()
        domains = self.handler.record.select_children (u'Domain')
        domains = utils.attrsorted (list(domains), 'title')
        if len(domains) > 0:
            for domain in domains:
                domainid = domain.ident.split('/')[-2].replace('-', '_')
                translations = db.Branch.select (type=u'Translation', parent=domain)
                cont = html.ContainerBox ()
                cont.set_id ('po_' + domainid)
                if len(domains) > 1:
                    cont.set_title (utils.gettext ('%s (%s)')
                                    % (domain.title, translations.count()))
                cont.set_sortable_tag ('tr')
                cont.set_sortable_class ('po_' + domainid)
                cont.add_sort_link ('title', utils.gettext ('lang'), 1)
                cont.add_sort_link ('percent', utils.gettext ('percent'))
                if len(domains) > 1:
                    div = html.AjaxBox ('%s?application=translations&action=domain&domain=%s'
                                        % (self.handler.record.pulse_url,
                                           urllib.quote (domain.ident)))
                else:
                    div = self.get_domain_div (domain.ident)
                cont.add_content (div)
                box.add_content (cont)
        else:
            box.add_content (html.AdmonBox (html.AdmonBox.warning,
                                            utils.gettext ('No domains') ))
        return box

    def get_domain_div (self, ident=None):
        if ident is None:
            ident = self.handler.request.query.get ('domain', None)
        domain = db.Branch.get (ident)
        domainid = domain.ident.split('/')[-2].replace('-', '_')
        translations = db.Branch.select_with_statistic (u'Messages',
                                                        type=u'Translation',
                                                        parent=domain)
        translations = utils.attrsorted (list(translations), (0, 'title'))
        topdiv = html.Div ()
        pad = html.PaddingBox ()
        topdiv.add_content (pad)

        if domain.error is not None:
            pad.add_content (html.AdmonBox (html.AdmonBox.error, domain.error))

        if domain.scm_dir == 'po':
            potfile = domain.scm_module + '.pot'
        else:
            potfile = domain.scm_dir + '.pot'
        of = db.OutputFile.select (type=u'l10n', ident=domain.ident, filename=potfile)
        try:
            of = of[0]
            div = html.Div()
            pad.add_content (div)

            linkdiv = html.Div()
            linkspan = html.Span (divider=html.SPACE)
            linkdiv.add_content (linkspan)
            div.add_content (linkdiv)
            linkspan.add_content (html.Link (of.pulse_url,
                                             utils.gettext ('POT file'),
                                             icon='download' ))
            # FIXME: i18n reordering
            linkspan.add_content (utils.gettext ('(%i messages)')
                                  % of.statistic)
            linkspan.add_content (utils.gettext ('on %s')
                                  % of.datetime.strftime('%Y-%m-%d %T'))
            missing = of.data.get ('missing', [])
            if len(missing) > 0:
                msg = utils.gettext('%i missing files') % len(missing)
                admon = html.AdmonBox (html.AdmonBox.warning, msg, tag='span')
                mdiv = html.Div()
                popup = html.PopupLink (admon, '\n'.join(missing))
                mdiv.add_content (popup)
                div.add_content (mdiv)
        except IndexError:
            pad.add_content (html.AdmonBox (html.AdmonBox.warning,
                                            utils.gettext ('No POT file') ))

        if len(translations) == 0:
            pad.add_content (html.AdmonBox (html.AdmonBox.warning,
                                            utils.gettext ('No translations') ))
        else:
            grid = html.GridBox ()
            pad.add_content (grid)
            for translation, statistic in translations:
                span = html.Span (translation.scm_file[:-3])
                span.add_class ('title')
                link = html.Link (translation.pulse_url, span)
                row = [link]
                percent = 0
                stat1 = statistic.stat1
                stat2 = statistic.stat2
                total = statistic.total
                untranslated = total - stat1 - stat2
                percent = total and math.floor (100 * (float(stat1) / total)) or 0
                span = html.Span ('%i%%' % percent)
                span.add_class ('percent')
                row.append (span)

                row.append (utils.gettext ('%i.%i.%i') %
                            (stat1, stat2, untranslated))
                idx = grid.add_row (*row)
                grid.add_row_class (idx, 'po')
                grid.add_row_class (idx, 'po_' + domainid)
                if percent >= 80:
                    grid.add_row_class (idx, 'po80')
                elif percent >= 50:
                    grid.add_row_class (idx, 'po50')
        return topdiv

def initialize (handler):
    if handler.__class__.__name__ == 'ModuleHandler':
        domains = handler.record.select_children (u'Domain')
        if domains.count() > 0:
            handler.register_application (TranslationsTab (handler))

def initialize_application (handler, application):
    if application == 'translations':
        if handler.__class__.__name__ == 'ModuleHandler':
            handler.register_application (TranslationsTab (handler))
