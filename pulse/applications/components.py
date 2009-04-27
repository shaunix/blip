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

from pulse import applications, core, db, html, utils

class ComponentsTab (applications.TabProvider):
    application_id = 'components'
    tab_group = applications.TabProvider.CORE_TAB

    def __init__ (self, handler):
        super (ComponentsTab, self).__init__ (handler)

    def get_tab_title (self):
        return utils.gettext ('Components')

    def handle_request (self):
        contents = None
        action = self.handler.request.query.get ('action')
        if action == 'tab':
            contents = self.get_tab ()
        if contents is not None:
            self.handler.response.set_contents (contents)

    def get_tab (self):
        columns = html.ColumnBox (2)

        # Programs and Libraries
        for branchtype, title in (
            (u'Application', utils.gettext ('Applications')),
            (u'Capplet', utils.gettext ('Capplets')),
            (u'Applet', utils.gettext ('Applets')),
            (u'Library', utils.gettext ('Libraries')) ):

            box = self.get_component_info_box (branchtype, title)
            if box is not None:
                columns.add_to_column (0, box)

        # Documents
        box = html.InfoBox (utils.gettext ('Documents'))
        columns.add_to_column (1, box)
        docs = self.handler.record.select_children (u'Document')
        docs = utils.attrsorted (list(docs), 'title')
        if len(docs) > 0:
            if len(docs) > 1:
                box.add_sort_link ('title', utils.gettext ('title'), 1)
                box.add_sort_link ('status', utils.gettext ('status'), 0)
                box.add_sort_link ('translations', utils.gettext ('translations'), 0)
            for doc in docs:
                lbox = box.add_link_box (doc)
                lbox.add_fact (utils.gettext ('status'),
                               html.StatusSpan (doc.data.get('status')))
                res = doc.select_children (u'Translation')
                span = html.Span (str(res.count()))
                span.add_class ('translations')
                lbox.add_fact (utils.gettext ('translations'), span)
        else:
            box.add_content (html.AdmonBox (html.AdmonBox.warning,
                                            utils.gettext ('No documents') ))
        return columns

    def get_component_info_box (self, branchtype, title):
        objs = self.handler.record.select_children (branchtype)
        objs = utils.attrsorted (list(objs), 'title')
        if len(objs) > 0:
            box = html.InfoBox (title)
            for obj in objs:
                lbox = box.add_link_box (obj)
                doc = db.Documentation.get_related (subj=obj)
                try:
                    doc = doc[0]
                    lbox.add_fact (utils.gettext ('docs'), doc.pred)
                except IndexError:
                    pass
            return box
        return None


def initialize (handler):
    if handler.__class__.__name__ == 'ModuleHandler':
        handler.register_application (ComponentsTab (handler))

def initialize_application (handler, application):
    if application == 'components':
        initialize (handler)
