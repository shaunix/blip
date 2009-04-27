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

import re

from pulse import applications, core, db, html, scm, utils

class OverviewTab (applications.TabProvider):
    application_id = 'overview'
    tab_group = applications.TabProvider.FIRST_TAB

    def __init__ (self, handler):
        super (OverviewTab, self).__init__ (handler)

    def get_tab_title (self):
        return utils.gettext ('Overview')

    def handle_request (self):
        contents = None
        if self.handler.request.query.get ('file') == 'doap':
            self.handle_doap_request ()
            return
        action = self.handler.request.query.get ('action')
        if action == 'tab':
            contents = self.get_tab ()
        if contents is not None:
            self.handler.response.set_contents (contents)

    def get_tab (self):
        tab = html.PaddingBox()

        if self.handler.record.error != None:
            tab.add_content (html.AdmonBox (html.AdmonBox.error, self.handler.record.error))

        facts = html.FactsTable()
        tab.add_content (facts)

        sep = False
        try:
            facts.add_fact (utils.gettext ('Description'),
                            self.handler.record.localized_desc)
            sep = True
        except:
            pass

        rels = db.SetModule.get_related (pred=self.handler.record)
        if len(rels) > 0:
            sets = utils.attrsorted ([rel.subj for rel in rels], 'title')
            span = html.Span (*[html.Link(rset) for rset in sets])
            span.set_divider (html.BULLET)
            facts.add_fact (utils.gettext ('Release Sets'), span)
            sep = True

        if sep:
            facts.add_fact_divider ()

        checkout = scm.Checkout.from_record (self.handler.record, checkout=False, update=False)
        facts.add_fact (utils.gettext ('Location'), checkout.location)

        if self.handler.record.mod_datetime != None:
            span = html.Span(divider=html.SPACE)
            # FIXME: i18n, word order, but we want to link person
            span.add_content (self.handler.record.mod_datetime.strftime('%Y-%m-%d %T'))
            if self.handler.record.mod_person_ident != None:
                span.add_content (' by ')
                span.add_content (html.Link (self.handler.record.mod_person))
            facts.add_fact (utils.gettext ('Last Modified'), span)

        if self.handler.record.data.has_key ('tarname'):
            facts.add_fact_divider ()
            facts.add_fact (utils.gettext ('Tarball Name'), self.handler.record.data['tarname'])
        if self.handler.record.data.has_key ('tarversion'):
            if not self.handler.record.data.has_key ('tarname'):
                facts.add_fact_divider ()
            facts.add_fact (utils.gettext ('Version'), self.handler.record.data['tarversion'])

        facts.add_fact_divider ()
        facts.add_fact (utils.gettext ('Score'), str(self.handler.record.mod_score))

        if self.handler.record.updated is not None:
            facts.add_fact_divider ()
            facts.add_fact (utils.gettext ('Last Updated'),
                            self.handler.record.updated.strftime('%Y-%m-%d %T'))

        doapdiv = html.Div ()
        tab.add_content (doapdiv)
        doaplink = html.Link (
            self.handler.record.pulse_url + '?application=overview&file=doap',
            'Download DOAP template file',
            icon='download')
        doapdiv.add_content (doaplink)

        # Developers
        box = self.get_developers_box ()
        tab.add_content (box)

        # Dependencies
        deps = db.ModuleDependency.get_related (subj=self.handler.record)
        deps = utils.attrsorted (list(deps), ['pred', 'scm_module'])
        if len(deps) > 0:
            box = html.ContainerBox (utils.gettext ('Dependencies'))
            tab.add_content (box)
            d1 = html.Div()
            d2 = html.Div()
            box.add_content (d1)
            box.add_content (html.Rule())
            box.add_content (d2)
            for dep in deps:
                depdiv = html.Div ()
                link = html.Link (dep.pred.pulse_url, dep.pred.scm_module)
                depdiv.add_content (link)
                if dep.direct:
                    d1.add_content (depdiv)
                else:
                    d2.add_content (depdiv)
        return tab


    def get_developers_box (self):
        box = html.ContainerBox (utils.gettext ('Developers'))
        rels = db.ModuleEntity.get_related (subj=self.handler.record)
        if len(rels) > 0:
            people = {}
            for rel in rels:
                people[rel.pred] = rel
            for person in utils.attrsorted (people.keys(), 'title'):
                lbox = box.add_link_box (person)
                rel = people[person]
                if rel.maintainer:
                    lbox.add_badge ('maintainer')
        else:
            box.add_content (html.AdmonBox (html.AdmonBox.warning,
                                            utils.gettext ('No developers') ))
        return box


    def handle_doap_request (self):
        module = self.handler.record
        content = core.HttpTextPacket ()
        self.handler.response.set_contents (content)
        self.handler.response.http_content_type = 'application/rdf+xml'
        self.handler.response.http_content_disposition = (
            'attachment; filename=%s.doap' % module.scm_module)

        content.add_text_content (
            '<Project xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"\n' +
            '         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"\n' +
            '         xmlns:foaf="http://xmlns.com/foaf/0.1/"\n' +
            '         xmlns:gnome="http://api.gnome.org/doap-extensions#"\n' +
            '         xmlns="http://usefulinc.com/ns/doap#">\n\n')

        content.add_text_content (
            '  <!--\n'
            '  This is a DOAP template file.  It contains Pulse\'s best guesses at\n'
            '  some basic content.  You should verify the information in this file\n'
            '  and modify anything that isn\'t right.  Add the corrected file to your\n'
            '  source code repository to help tools better understand your project.\n'
            '  -->\n\n')

        content.add_text_content ('  <name xml:lang="en">%s</name>\n'
                                  % core.esc (module.title))
        desc = module.localized_desc
        if desc is not None:
            content.add_text_content ('  <shortdesc xml:lang="en">%s</shortdesc>\n'
                                      % core.esc (desc))
        else:
            content.add_text_content (
                '  <!-- Description, e.g.\n' +
                '       "Falling blocks game"\n' +
                '       "Internationalized text layout and rendering library"\n' +
                '  <shortdesc xml:lang="en">FIXME</shortdesc>\n' +
                '  -->\n')
        content.add_text_content (
            '  <!--\n' + 
            '  <homepage rdf:resource="http://www.gnome.org/" />\n' +
            '  -->\n')
        content.add_text_content (
            '  <!--\n' + 
            '  <mailing-list rdf:resource="http://mail.gnome.org/mailman/listinfo/desktop-devel-list" />\n' +
            '  -->\n')

        if module.data.has_key ('tarname'):
            content.add_text_content (
                '  <download-page rdf:resource="http://download.gnome.org/sources/%s/" />\n'
                % module.data['tarname'])
        else:
            content.add_text_content (
                '  <!--\n' + 
                '  <download-page rdf:resource="http://download.gnome.org/sources/FIXME/" />\n'
                '  -->\n')
        content.add_text_content (
            '  <bug-database rdf:resource="http://bugzilla.gnome.org/browse.cgi?product=%s" />\n'
            % module.scm_module)

        rels = db.SetModule.get_related (pred=module)
        group = None
        bindings = re.compile ('.*-bindings-.*')
        for rel in rels:
            if bindings.match (rel.subj.ident):
                group = 'bindings'
                break
            elif rel.subj.ident.endswith ('-desktop'):
                group = 'desktop'
                break
            elif rel.subj.ident.endswith ('-devtools'):
                group = 'development'
                break
            elif rel.subj.ident.endswith ('-infrastructure'):
                group = 'infrastructure'
                break
            elif rel.subj.ident.endswith ('-platform'):
                group = 'platform'
                break
        content.add_text_content (
            '\n  <!-- DOAP category: This is used to categorize repositories in cgit.\n'
            )
        if group is None:
            content.add_text_content (
                '       Pulse could not find an appropriate category for this repository.\n' +
                '       Set the rdf:resource attribute with one of the following:\n')
        else:
            content.add_text_content (
                '       Pulse has taken its best guess at the correct category.  You may\n' +
                '       want to replace the rdf:resource attribute with one of the following:\n')
        content.add_text_content (
            '         http://api.gnome.org/doap-extensions#admin\n' +
            '         http://api.gnome.org/doap-extensions#bindings\n' +
            '         http://api.gnome.org/doap-extensions#deprecated\n' +
            '         http://api.gnome.org/doap-extensions#desktop\n' +
            '         http://api.gnome.org/doap-extensions#development\n' +
            '         http://api.gnome.org/doap-extensions#infrastructure\n' +
            '         http://api.gnome.org/doap-extensions#platform\n' +
            '         http://api.gnome.org/doap-extensions#productivity\n')
        if group is None:
            content.add_text_content (
                '  <category rdf:resource="FIXME" />\n' +
            '  -->\n')
        else:
            content.add_text_content ('  -->\n')
            content.add_text_content (
                '  <category rdf:resource="http://api.gnome.org/doap-extensions#%s" />\n'
            % group)

        content.add_text_content ('\n')
        rels = db.ModuleEntity.get_related (subj=module)
        regexp = re.compile ('^/person/(.*)@gnome.org$')
        for rel in rels:
            if not rel.maintainer:
                continue
            content.add_text_content (
                '  <maintainer>\n' +
                '    <foaf:Person>\n')
            content.add_text_content ('      <foaf:name>%s</foaf:name>\n'
                                      % core.esc (rel.pred.title))
            if rel.pred.email is not None:
                content.add_text_content ('      <foaf:mbox rdf:resource="%s" />\n'
                                          % core.esc (rel.pred.email))
            match = regexp.match (rel.pred.ident)
            if match:
                content.add_text_content ('      <gnome:userid>%s</gnome:userid>\n'
                                          % match.group (1))
            content.add_text_content (
                '    </foaf:Person>\n'
                '  </maintainer>\n')

        content.add_text_content ('</Project>\n')


def initialize (handler):
    if handler.__class__.__name__ == 'ModuleHandler':
        handler.register_application (OverviewTab)
