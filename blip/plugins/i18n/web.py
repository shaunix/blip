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

class TranslationResponder (blip.web.RecordLocator, blip.web.PageResponder):
    @classmethod
    def locate_record (cls, request):
        if not (len(request.path) in (6, 7) and request.path[0] == 'l10n'):
            return False
        ident = u'/' + u'/'.join(request.path)
        if len(request.path) == 6:
            trs = list(blip.db.Branch.select (project_ident=ident))
            if len(trs) == 0:
                return True
            tr = [tr for tr in trs if tr.is_default]
            if len(tr) == 0:
                return True
            request.record = tr[0]
        else:
            tr = blip.db.Branch.get (ident)
            if tr is None:
                return True
            request.record = tr
            trs = list(blip.db.Branch.select (project_ident=tr.project_ident))
        request.set_data ('branches', trs)
        return True

    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) < 1 or request.path[0] != 'l10n':
            return None

        response = blip.web.WebResponse (request)

        if request.record is None:
            page = blip.html.PageNotFound (None)
            response.payload = page
            return response

        lang = request.record.ident.split('/')[2]
        page = blip.html.Page (request=request,
                               title=blip.utils.language_name (lang))
        response.payload = page

        if request.record.parent.type == u'Document':
            page.add_trail_link (request.record.parent.parent.blip_url + '#docs',
                                 request.record.parent.parent.title)
            page.add_trail_link (request.record.parent.blip_url + '#i18n',
                                 request.record.parent.title)
        else:
            domid = request.record.parent.ident.split('/')[-2]
            page.add_trail_link (request.record.parent.parent.blip_url,
                                 request.record.parent.parent.title)
            page.add_trail_link (request.record.parent.parent.blip_url + '#i18n/' + domid,
                                 domid)

        branches = request.get_data ('branches', [])
        if len(branches) > 1:
            for branch in blinq.utils.attrsorted (branches, '-is_default', 'scm_branch'):
                if branch.ident != request.record.ident:
                    page.add_sublink (branch.blip_url, branch.scm_branch)
                else:
                    page.add_sublink (None, branch.scm_branch)

        return response

class OverviewTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1 or request.path[0] != 'l10n':
            return None
        page.add_tab ('overview',
                      blip.utils.gettext ('Overview'),
                      blip.html.TabProvider.FIRST_TAB),
        page.add_to_tab ('overview', cls.get_tab (request))

    @classmethod
    def get_tab (cls, request):
        tab = blip.html.PaddingBox ()

        for err in blip.db.Error.select (ident=request.record.ident):
            tab.add_content (blip.html.AdmonBox (blip.html.AdmonBox.error, err.message))

        facts = blip.html.FactsTable ()
        tab.add_content (facts)

        facts.start_fact_group ()
        lang = request.record.ident.split('/')[2]
        facts.add_fact (blip.utils.gettext ('Language'),
                        blip.utils.language_name (lang))
        facts.add_fact (blip.utils.gettext ('Code'), lang)
        if request.record.desc not in (None, ''):
            facts.add_fact (blip.utils.gettext ('Description'),
                            request.record.desc)

        facts.start_fact_group ()
        stat = blip.db.Statistic.select_statistic (request.record, u'Messages')
        try:
            stat = stat[0]
            meter = blip.html.Meter ()
            meter.add_bar (stat.stat1,
                           blip.utils.gettext ('%i translated') % stat.stat1)
            meter.add_bar (stat.stat2,
                           blip.utils.gettext ('%i fuzzy') % stat.stat2)
            untranslated = stat.total - stat.stat1 - stat.stat2
            meter.add_bar (untranslated,
                           blip.utils.gettext ('%i untranslated') % untranslated)
            facts.add_fact ('Translated', meter)
        except IndexError:
            pass

        module = request.record.parent.parent
        rels = blip.db.SetModule.get_related (pred=module)
        if len(rels) > 0:
            sets = blinq.utils.attrsorted ([rel.subj for rel in rels], 'title')
            span = blip.html.Span (*[blip.html.Link(rset.blip_url + '#docs',
                                                    rset.title)
                                     for rset in sets])
            span.set_divider (blip.html.BULLET)
            facts.start_fact_group ()
            facts.add_fact (blip.utils.gettext ('Release Sets'), span)

        facts.start_fact_group ()
        if request.record.parent.type == u'Document':
            facts.add_fact (blip.utils.gettext ('Document'),
                            blip.html.Link (request.record.parent))
        elif request.record.parent.type == u'Domain':
            domid = request.record.ident.split('/')[-2]
            facts.add_fact (blip.utils.gettext ('Domain'),
                            blip.html.Link (module.blip_url + '#i18n/' + domid, domid))

        facts.start_fact_group ()
        checkout = blip.scm.Repository.from_record (request.record, checkout=False, update=False)
        facts.add_fact (blip.utils.gettext ('Module'),
                        blip.html.Link (module.blip_url,
                                        request.record.scm_module))
        facts.add_fact (blip.utils.gettext ('Branch'), request.record.scm_branch)
        facts.add_fact (blip.utils.gettext ('Location'), checkout.location)
        if request.record.scm_dir is not None:
            if request.record.scm_file is not None:
                facts.add_fact (blip.utils.gettext ('File'),
                                os.path.join (request.record.scm_dir, request.record.scm_file))
            else:
                facts.add_fact (blip.utils.gettext ('Directory'), request.record.scm_dir)

        if request.record.mod_datetime is not None:
            facts.start_fact_group ()
            if request.record.mod_person_ident is not None:
                facts.add_fact (blip.utils.gettext ('Modified'),
                                blip.html.Link (request.record.mod_person))
                facts.add_fact ('',
                                request.record.mod_datetime.strftime('%Y-%m-%d %T'))
            else:
                facts.add_fact (blip.utils.gettext ('Modified'),
                                request.record.mod_datetime.strftime('%Y-%m-%d %T'))

        if request.record.updated is not None:
            facts.start_fact_group ()
            facts.add_fact (blip.utils.gettext ('Last Updated'),
                            request.record.updated.strftime('%Y-%m-%d %T'))

        return tab

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] != 'l10n':
            return None
        if not blip.html.TabProvider.match_tab (request, 'overview'):
            return None

        response = blip.web.WebResponse (request)

        response.payload = cls.get_tab (request)
        return response


class TranslationsTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1 or request.path[0] not in ('mod', 'doc'):
            return None
        if not isinstance (request.record, blip.db.Branch):
            return None
        if request.record.type == u'Module':
            store = blip.db.get_store (blip.db.Branch)
            domain = blip.db.ClassAlias (blip.db.Branch)
            using = store.using (blip.db.LeftJoin (blip.db.Branch, domain,
                                                   blip.db.Branch.parent_ident == domain.ident))
            cnt = using.find (blip.db.Branch.scm_file,
                              blip.db.Branch.type == u'Translation',
                              domain.type == u'Domain',
                              domain.parent_ident == request.record.ident
                              ).config(distinct=True).count()
        elif request.record.type == u'Document':
            cnt = blip.db.Branch.select (parent=request.record, type=u'Translation').count ()
        else:
            return None
        if cnt > 0:
            page.add_tab ('i18n',
                          blip.utils.gettext ('Translations (%i)') % cnt,
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] not in ('mod', 'doc'):
            return None
        if not (blip.html.TabProvider.match_tab (request, 'i18n') or
                blip.html.TabProvider.match_tab (request, 'i18n/*')):
            return None

        response = blip.web.WebResponse (request)
        pad = blip.html.PaddingBox ()
        response.payload = pad

        if request.record.type == u'Module':
            domain = list(request.record.select_children (u'Domain'))
            if len(domain) == 0:
                pad.add_content (blip.html.AdmonBox (blip.html.AdmonBox.warning,
                                                     blip.utils.gettext ('No translation domains')))
                return response
            elif len(domain) > 1:
                reqtab = request.query.get ('tab', None)
                if reqtab is not None and reqtab.startswith ('i18n/'):
                    reqtab = reqtab[5:]
                tabbar = blip.html.TabBar ()
                pad.add_content (tabbar)
                domains = blinq.utils.attrsorted (domain, 'scm_dir')
                domain = None
                for dom in domains:
                    domid = dom.ident.split('/')[-2]
                    active = False
                    if domid == reqtab:
                        active = True
                        domain = dom
                    tabbar.add_tab ('i18n/' + domid, domid, active)
                if domain is None:
                    domain = domains[0]
            else:
                domain = domain[0]
        else:
            domain = request.record

        for err in blip.db.Error.select (ident=domain.ident):
            pad.add_content (blip.html.AdmonBox (blip.html.AdmonBox.error, err.message))

        of = blip.db.OutputFile.select_one (type=u'l10n', ident=domain.ident,
                                            filename=(domain.ident.split('/')[-2] + u'.pot'))
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
                                                             parent=domain)
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
        sort_fuzzy = False
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
            if mstat is not None:
                meter = blip.html.Meter ()
                meter.add_bar (mstat.stat1,
                               blip.utils.gettext ('%i translated') % mstat.stat1)
                if mstat.stat2 is not None:
                    meter.add_bar (mstat.stat2,
                                   blip.utils.gettext ('%i fuzzy') % mstat.stat2)
                untranslated = mstat.total - mstat.stat1 - mstat.stat2
                meter.add_bar (untranslated,
                               blip.utils.gettext ('%i untranslated') % untranslated)
                lbox.add_fact (None, meter)
        if sort_percent:
            cont.add_sort_link ('translated', blip.utils.gettext ('translated'))
        if sort_fuzzy:
            cont.add_sort_link ('fuzzy', blip.utils.gettext ('fuzzy'))
        if sort_images:
            cont.add_sort_link ('images', blip.utils.gettext ('images'))

        return response
