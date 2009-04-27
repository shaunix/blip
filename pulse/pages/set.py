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

"""Output information about release sets"""

from pulse import applications, config, core, db, html, utils

class SetHandler (core.RequestHandler):
    def initialize (self):
        if len(self.request.path) > 1:
            ident = '/' + '/'.join(self.request.path)
            rset = db.ReleaseSet.get (ident)
            if rset is None:
                raise core.RequestHandlerException (
                    utils.gettext ('Set Not Found'),
                    utils.gettext ('Pulse could not find the set %s')
                    % '/'.join(self.request.path[1:]))
            self.record = rset
        else:
            self.record = None

    def handle_request (self):
        contents = None
        if self.record is None:
            contents = self.get_top_page ()
        else:
            contents = self.get_set_page ()
        if contents is not None:
            self.response.set_contents (contents)
            

    def get_top_page (self):
        """Output a page showing all release sets"""
        page = html.Page ()
        page.set_title (utils.gettext ('Sets'))
        cont = html.ContainerBox ()
        cont.set_show_icons (False)
        cont.set_columns (2)
        page.add_content (cont)

        sets = db.ReleaseSet.select (parent=None)
        sets = utils.attrsorted (list(sets), 'title')
        for rset in sets:
            lbox = cont.add_link_box (rset)
            subsets = utils.attrsorted (list(rset.subsets), ['title'])
            if len(subsets) > 0:
                bl = html.BulletList ()
                lbox.add_content (bl)
                for subset in subsets:
                    bl.add_link (subset)
            else:
                SetHandler.add_set_info (rset, lbox)
        return page

    def get_set_page (self):
        """Output information about a release set"""
        page = html.Page (self)

        page.set_sublinks_divider (html.TRIANGLE)
        page.add_sublink (config.web_root + 'set', utils.gettext ('Sets'))
        for superset in SetHandler.get_supersets (self.record):
            page.add_sublink (superset.pulse_url, superset.title)

        # Schedule
        schedule = self.record.data.get ('schedule', [])
        if len(schedule) == 0 and self.record.parent != None:
            schedule = self.record.parent.data.get ('schedule', [])
        if len(schedule) > 0:
            box = html.SectionBox (utils.gettext ('Schedule'))
            cal = html.Calendar ()
            box.add_content (cal)
            page.add_to_tab ('overview', box)
            for event in schedule:
                cal.add_event (*event)

        # Links
        links = self.record.data.get ('links', [])
        if len(links) == 0 and self.record.parent != None:
            links = self.record.parent.data.get ('links', [])
        if len(links) > 0:
            box = html.InfoBox (utils.gettext ('Links'))
            box.set_show_icons (False)
            page.add_to_tab ('overview', box)
            for link in links:
                lbox = box.add_link_box (link[0], link[1])
                lbox.set_description (link[2])

        return page

    @staticmethod
    def add_set_info (rset, lbox):
        cnt = db.SetModule.count_related (subj=rset)
        if cnt > 0:
            bl = html.BulletList ()
            lbox.add_content (bl)
            bl.add_link (rset.pulse_url + '#modules',
                         utils.gettext ('%i modules') % cnt)
        else:
            return

        # Documents
        cnt = db.Branch.select (type=u'Document', parent_in_set=rset)
        cnt = cnt.count()
        if cnt > 0:
            bl.add_link (rset.pulse_url + '#documents',
                         utils.gettext ('%i documents') % cnt)

        # Domains
        cnt = db.Branch.select (type=u'Domain', parent_in_set=rset)
        cnt = cnt.count()
        if cnt > 0:
            bl.add_link (rset.pulse_url + '#domains',
                         utils.gettext ('%i domains') % cnt)

        # Programs
        objs = db.Branch.select (
            db.Branch.type.is_in ((u'Application', u'Capplet', u'Applet')),
            parent_in_set=rset)
        cnt = objs.count()
        if cnt > 0:
            bl.add_link (rset.pulse_url + '#programs',
                         utils.gettext ('%i programs') % cnt)

        # Libraries
        cnt = db.Branch.select (type=u'Library', parent_in_set=rset)
        cnt = cnt.count()
        if cnt > 0:
            bl.add_link (rset.pulse_url + '#libraries',
                         utils.gettext ('%i libraries') % cnt)

    @staticmethod
    def get_supersets (rset):
        """Get a list of the supersets of a release set"""
        superset = rset.parent
        if superset == None:
            return []
        else:
            supers = SetHandler.get_supersets (superset)
            return supers + [superset]


def get_request_handler (request, response):
    return SetHandler (request, response)


def synopsis ():
    """Construct an info box for the front page"""
    box = html.SidebarBox (utils.gettext ('Sets'))
    bl = html.BulletList ()
    box.add_content (bl)
    sets = db.ReleaseSet.find (db.ReleaseSet.parent_ident == None)
    sets = utils.attrsorted (list(sets), 'title')
    for rset in sets:
        bl.add_link (rset)
    return box
