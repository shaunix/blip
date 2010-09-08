# coding=UTF-8
# Copyright (c) 2006  Shaun McCance  <shaunm@gnome.org>
#
# This file is part of Blip, a program for displaying various statistics
# of questionable relevance about software and the people who make it.
#
# Blip is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# Blip is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along
# with Blip; if not, write to the Free Software Foundation, 59 Temple Place,
# Suite 330, Boston, MA  0211-1307  USA.
#

import math
import os.path

import blinq.utils

import blip.db
import blip.html
import blip.utils

class TranslationsTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1 or request.path[0] != 'doc':
            return None
        if not (isinstance (request.record, blip.db.Branch) and
                request.record.type == u'Document'):
            return None
        cnt = blip.db.Branch.select (parent=request.record, type=u'Translation').count ()
        if cnt > 0:
            page.add_tab ('i18n',
                          blip.utils.gettext ('Translations (%i)') % cnt,
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] != 'doc':
            return None
        if not blip.html.TabProvider.match_tab (request, 'i18n'):
            return None

        response = blip.web.WebResponse (request)
        pad = blip.html.PaddingBox ()
        response.payload = pad

        of = blip.db.OutputFile.select_one (type=u'l10n', ident=request.record.ident,
                                            filename=(request.record.ident.split('/')[-2] + u'.pot'))
        if of is not None:
            span = blip.html.Span (divider=blip.html.SPACE)
            span.add_content (blip.html.Link (of.blip_url,
                                              blip.utils.gettext ('POT file'),
                                              icon='download'))
            # FIXME: i18n reordering
            if of.statistic is not None:
                span.add_content (blip.utils.gettext ('(%i messages)') % of.statistic)
            span.add_content (blip.utils.gettext ('on %s') % of.datetime.strftime('%Y-%m-%d %T'))
            pad.add_content (span)

        translations = blip.db.Branch.select_with_statistic ([u'Messages', u'ImageMessages'],
                                                             type=u'Translation',
                                                             parent=request.record)
        translations = list(translations)
        for translation in translations:
            setattr (translation[0], 'x_lang_name',
                     blip.utils.language_name (translation[0].ident.split('/')[2]))
        translations = blinq.utils.attrsorted (translations, (0, 'x_lang_name'))
        if len(translations) == 0:
            pad.add_content (blip.html.AdmonBox (blip.html.AdmonBox.warning,
                                                 blip.utils.gettext ('No translations')))
            return response

        cont = blip.html.ContainerBox ()
        cont.add_sort_link ('title', blip.utils.gettext ('title'), 1)
        cont.add_sort_link ('language', blip.utils.gettext ('language'))
        pad.add_content (cont)
        sort_percent = False
        sort_fuzzy = True
        sort_images = False
        for translation, mstat, istat in translations:
            lbox = cont.add_link_box (translation.blip_url, translation.x_lang_name)
            lbox.add_fact (blip.utils.gettext ('language'),
                           blip.html.Span (translation.ident.split('/')[2],
                                           html_class='language'))
            percent = 0
            if mstat is not None:
                sort_percent = True
                try:
                    percent = math.floor (100 * (float(mstat.stat1) / mstat.total))
                except:
                    percent = 0
                span = blip.html.Span ('%i / %i (%i%%)' %
                                       (mstat.stat1, mstat.total, percent),
                                       html_class='translated')
                span.add_data_attribute ('sort-key', str(mstat.stat1))
                lbox.add_fact (blip.utils.gettext ('translated'), span)
                if mstat.stat2 is not None:
                    sort_fuzzy = True
                    try:
                        percent = math.floor (100 * (float(mstat.stat2) / mstat.total))
                    except:
                        percent = 0
                    span = blip.html.Span ('%i / %i (%i%%)' %
                                           (mstat.stat2, mstat.total, percent),
                                           html_class='fuzzy')
                    span.add_data_attribute ('sort-key', str(mstat.stat2))
                    lbox.add_fact (blip.utils.gettext ('fuzzy'), span)
            if istat is not None:
                sort_images = True
                try:
                    percent = math.floor (100 * (float(istat.stat1) / istat.total))
                except:
                    percent = 0
                span = blip.html.Span ('%i / %i (%i%%)' %
                                       (istat.stat1, istat.total, percent),
                                       html_class='images')
                span.add_data_attribute ('sort-key', str(istat.stat1))
                lbox.add_fact (blip.utils.gettext ('images'), span)
        if sort_percent:
            cont.add_sort_link ('translated', blip.utils.gettext ('translated'))
        if sort_fuzzy:
            cont.add_sort_link ('fuzzy', blip.utils.gettext ('fuzzy'))
        if sort_images:
            cont.add_sort_link ('images', blip.utils.gettext ('images'))

        return response
