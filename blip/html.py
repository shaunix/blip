# -*- coding: utf-8 -*-
# Copyright (c) 2006-2010  Shaun McCance  <shaunm@gnome.org>
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

"""
Generate HTML output.

This module allows you to construct an HTML page using objects,
in much the same way as you would construct a user interface in
a graphical toolkit.  High-level objects are provided for various
common interface elements in Blip pages.
"""

import datetime
import sys

import blinq.config
import blinq.reqs.web

import blip.db
import blip.utils
import blip.web

SPACE = ' '
BULLET = u' • '
TRIANGLE = u' ‣ '


class HtmlObject (blinq.reqs.web.HtmlPayload):
    """
    Base class for all HTML objects.
    """
    def __init__ (self, **kw):
        self.content_type = 'text/html; charset=utf-8'
        self._html_id = kw.pop ('html_id', None)
        self._html_class = kw.pop ('html_class', None)
        super (HtmlObject, self).__init__ (**kw)
        

    def set_html_id (self, html_id):
        self._html_id = html_id

    def get_html_id (self):
        if self._html_id != None:
            return self._html_id
        else:
            return 'x' + str(hash(self))

    def add_html_class (self, html_class):
        if isinstance (self._html_class, basestring):
            self._html_class = self._html_class + ' ' + html_class
        else:
            self._html_class = html_class

    def set_html_class (self, html_class):
        self._html_class = html_class

    def get_html_class (self):
        return self._html_class


class Component (blinq.reqs.web.HtmlPayload):
    """
    Base class for all components.

    Components are effectively interfaces that objects can implement.
    Their output methods are called at an appropriate place within a
    object's output method to create a portion of that object's HTML.
    """
    def __init__ (self, **kw):
        super (Component, self).__init__ (**kw)


################################################################################
## Components

class ContentComponent (Component):
    """
    Simple component for objects with generic content.

    The output method will call output on each of the added objects.  Some
    objects may use this component only for the add_content method, and
    control how the added objects are output by mapping over get_content.
    """

    def __init__ (self, **kw):
        super (ContentComponent, self).__init__ (**kw)
        self._content = []

    def add_content (self, content):
        """Add an object or text to this container."""
        self._content.append (content)

    def get_content (self):
        """Get a list of all added content."""
        return self._content

    def output (self, res):
        """Output the HTML."""
        for cont in self._content:
            res.write(self.escape(cont))


class SublinksComponent (Component):
    """
    Component for objects that contain sublinks.

    Sublinks are a list of links found under the title of an object.  They
    may provide alternate pages or a heirarchy of parent pages, depending
    on context.  The ouput method will create the sublinks.

    FIXME: document **kw
    """

    def __init__ (self, **kw):
        self._sublinks = []
        self._divider = kw.pop ('divider', BULLET)
        super (SublinksComponent, self).__init__ (**kw)

    def add_sublink (self, href, title):
        self._sublinks.append ((href, title))

    def set_sublinks_divider (self, div):
        self._divider = div

    def output (self, res):
        """Output the HTML."""
        if len(self._sublinks) > 0:
            res.write('<div class="sublinks">')
            for i in range(len(self._sublinks)):
                if i != 0:
                    res.write(self.escape(self._divider))
                if self._sublinks[i][0] != None:
                    res.write('<a href="%s">%s</a>' % self.escape(self._sublinks[i]))
                else:
                    res.write(self.escape(self._sublinks[i][1]))
            res.write('</div>')


class FactsComponent (Component):
    """
    Component for objects that contain fact tables.

    Fact tables are key-value tables providing more information about whatever
    thing the object is showing.  The output method will create the table of
    facts.
    """

    def __init__ (self, **kw):
        super (FactsComponent, self).__init__ (**kw)
        self._facts = []

    def add_fact (self, label, content, **kw):
        fact = {'label' : label, 'content' : content, 'badge' : kw.get('badge', None)}
        self._facts.append (fact)

    def add_fact_divider (self):
        self._facts.append (None)

    def has_facts (self):
        return len(self._facts) > 0

    def output (self, res):
        """Output the HTML."""
        if len (self._facts) == 0:
            return
        res.write('<table class="facts">')
        for fact in self._facts:
            if fact == None:
                res.write('<tr class="fact-sep"><td></td><td></td></tr>')
            else:
                res.write('<tr>')
                if fact['label'] != None:
                    res.write('<td class="fact-key">')
                    key = self.escape(fact['label']).replace(' ', '&nbsp;')
                    key = self.escape(blip.utils.gettext ('%s:')) % key
                    res.write(key)
                    res.write('</td>')
                    res.write('<td class="fact-val">')
                else:
                    res.write('<td class="fact-val" colspan="2">')
                def factout (val):
                    if isinstance (val, (basestring, HtmlObject, Component)):
                        res.write(self.escape(val))
                    elif isinstance (val, blip.db.BlipRecord):
                        Link(val).output (res)
                    elif hasattr (val, '__getitem__'):
                        for subval in val:
                            res.write('<div>')
                            factout (subval)
                            res.write('</div>')
                factout (fact['content'])
                res.write('</td></tr>')
        res.write('</table>')


class FilterableComponent (Component):
    def __init__ (self, **kw):
        self._filtertag = kw.pop ('filterable_tag', None)
        self._filterclass = kw.pop ('filterable_class', None)
        self._filters = []
        super (FilterableComponent, self).__init__ (**kw)

    def set_filterable_tag (self, tag):
        self._filtertag = tag

    def get_filterable_tag (self):
        return self._filtertag

    def set_filterable_class (self, cls):
        self._filterclass = cls

    def get_filterable_class (self):
        return self._filterclass

    def add_badge_filter (self, badge):
        self._filters.append (badge)

    def output (self, res):
        if len(self._filters) == 0:
            return
        filterid = self.get_html_id ()
        filtertag = self._filtertag or 'table'
        filterclass = self._filterclass or 'lbox'
        res.write('<div class="filters" id="filters__%s"><span class="filters">'
                  % self.escape(filterclass))
        res.write('<a class="filter filter-%s filterall filteron"'
                  % self.escape(filterid))
        res.write(' href="javascript:filter(\'%s\',\'%s\',\'%s\',null)"'
                  % self.escape((filterid, filtertag, filterclass)))
        res.write(' id="filter__%s___all">' % self.escape(filterid))
        res.write(self.escape(blip.utils.gettext ('All')))
        res.write('</a>')
        for badge in self._filters:
            txt = get_badge_title (badge)
            res.write('<a class="filter filter-%s"' % self.escape(filterid))
            res.write(' href="javascript:filter(\'%s\',\'%s\',\'%s\',\'%s\')"'
                      % self.escape((filterid, filtertag, filterclass, badge)))
            res.write(' id="filter__%s__%s">' % self.escape((filterid, badge)))
            res.write('<img src="%sbadge-%s-16.png" width="16" height="16" alt="%s">'
                      % self.escape((blinq.config.web_data_url, badge, txt)))
            res.write(' %s</a>' % self.escape(txt))
        res.write('</span></div>')


class SortableComponent (Component):
    """
    Component for objects that have sortable content.

    The output method will create the link bar for sorting the content.
    FIXME: explaing tag and class and how sort keys are gathered.

    FIXME: document **kw
    """

    def __init__ (self, **kw):
        self._slinktag = kw.pop ('sortable_tag', None)
        self._slinkclass = kw.pop ('sortable_class', None)
        self._slinks = []
        super (SortableComponent, self).__init__ (**kw)

    def set_sortable_tag (self, tag):
        self._slinktag = tag

    def get_sortable_tag (self):
        return self._slinktag

    def set_sortable_class (self, cls):
        self._slinkclass = cls

    def get_sortable_class (self):
        return self._slinkclass

    def add_sort_link (self, key, txt, cur=0):
        self._slinks.append ((key, txt, cur))

    def get_sort_links (self):
        return self._slinks

    def output (self, res):
        """Output the HTML."""
        if len(self._slinks) == 0:
            return
        slinkid = self.get_html_id ()
        slinktag = self._slinktag or 'table'
        slinkclass = self._slinkclass or 'lbox'
        res.write('<div class="sortlinks" id="sortlinks__%s">' % self.escape(slinkid))
        res.write('<span class="sortlinks">')
        res.write(self.escape(blip.utils.gettext ('sort by: ')))
        for key, txt, cur in self._slinks:
            if cur == 1:
                res.write('<span class="sortcur">%s ▴</span>' % self.escape(txt))
                break
            elif cur == -1:
                res.write('<span class="sortcur">%s ▾</span>' % self.escape(txt))
                break
        res.write('</span>')
        res.write('<div class="sortmenu" id="sortmenu__%s">' % self.escape(slinkid))
        for key, txt, cur in self._slinks:
            res.write('<div class="sortlink">')
            res.write('<span class="sortlabel" id="sortlink__%s__%s">%s</span>:'
                      % self.escape((slinkid, key, txt)))
            if cur == 1:
                res.write('<span class="sortlink" id="sortlink__%s__%s__%s__%s__1">▴</span>'
                          % self.escape((slinkid, slinktag, slinkclass, key)))
            else:
                res.write(('<a class="sortlink" id="sortlink__%s__%s__%s__%s__1"' +
                           ' href="javascript:sort(\'%s\',\'%s\',\'%s\',\'%s\',1)">▴</a>')
                          % self.escape((slinkid, slinktag, slinkclass, key,
                                         slinkid, slinktag, slinkclass, key)))
            if cur == -1:
                res.write('<span class="sortlink" id="sortlink__%s__%s__%s__%s__-1">▾</span>'
                          % self.escape((slinkid, slinktag, slinkclass, key)))
            else:
                res.write(('<a class="sortlink" id="sortlink__%s__%s__%s__%s__-1"' +
                           ' href="javascript:sort(\'%s\',\'%s\',\'%s\',\'%s\',-1)">▾</a>')
                          % self.escape((slinkid, slinktag, slinkclass, key,
                                         slinkid, slinktag, slinkclass, key)))
            res.write('</div>')
        res.write('</div></div>')


class LinkBoxesComponent (Component):
    """
    Component for objects containing link boxes.

    This provides a convenience routine for adding link boxes, and can
    display the link boxes in multiple columns.

    FIXME: document **kw
    """

    def __init__ (self, **kw):
        self._boxes = []
        self._columns = kw.pop ('columns', 1)
        self._show_icons = None
        super (LinkBoxesComponent, self).__init__ (**kw)

    def add_link_box (self, *args, **kw):
        """Add a link box."""
        lbox = LinkBox (*args, **kw)
        self._boxes.append (lbox)
        return lbox

    def set_show_icons (self, show):
        self._show_icons = show

    def set_columns (self, columns):
        """Set the number of columns."""
        self._columns = columns

    def output (self, res):
        """Output the HTML."""
        if self._show_icons == None:
            self._show_icons = False
            for box in self._boxes:
                if box.has_icon():
                    self._show_icons = True
                    break
        if self._columns > 1:
            res.write('<table class="cols"><tr>')
            res.write('<td class="col col-first">')
            width = str(100 // self._columns)
            for box, col, pos in blip.utils.split (self._boxes, self._columns):
                if pos == 0:
                    if col > 0:
                        res.write('</td><td class="col" style="width: ' + width + '%">')
                else:
                    res.write('<div class="pad">')
                box.set_show_icon (self._show_icons)
                box.output (res)
                if pos > 0:
                    res.write('</div>')
            res.write('</td></tr></table>')
        else:
            for i in range(len(self._boxes)):
                box = self._boxes[i]
                if i != 0:
                    res.write('<div class="pad">')
                box.set_show_icon (self._show_icons)
                box.output (res)
                if i != 0:
                    res.write('</div>')


################################################################################
## Pages


class HeaderLinksProvider (blinq.ext.ExtensionPoint):
    FIRST_LINK = 0
    CORE_LINK = 10
    EXTRA_LINK = 20

    @classmethod
    def add_header_links (cls, page, request):
        pass


class TabProvider (blip.web.ContentResponder):
    FIRST_TAB = 0
    CORE_TAB = 10
    EXTRA_TAB = 20

    @classmethod
    def add_tabs (cls, page, request):
        pass

    @classmethod
    def match_tab (cls, request, tabid):
        if request.query.get ('q', None) != 'tab':
            return False
        return (request.query.get ('tab', None) == tabid)

    @classmethod
    def respond (cls, request):
        return None


class Page (HtmlObject, ContentComponent, SublinksComponent, FactsComponent):
    """
    Complete web page.

    The output method creates all the standard HTML for the top and bottom
    of the page, and calls output_page_content in between.  Subclasses should
    override output_page_content.

    Keyword arguments:
    title -- The title of the page.
    icon  -- The URL of an icon for the page.
    """

    def __init__ (self, **kw):
        self._ident = None
        self._title = None
        self._desc = None
        self._icon = None
        self._url = None

        request = kw.pop ('request', None)
        record = kw.pop ('record', None)
        if record is None and request is not None:
            record = request.record
        if record is not None:
            self._title = record.title
            self._desc = record.desc
            self._icon = record.icon_url
            self._url = record.blip_url
            if record.watchable:
                self._ident = record.ident

        self._title = kw.pop ('title', self._title)
        self._desc = kw.pop ('desc', self._desc)
        self._icon = kw.pop ('icon', self._icon)
        self._url = kw.pop ('url', self._url)
        self._screenshot_file = None
        self._sidebar = None
        self._tabs = {}
        self._header_links = {}
        self._panes = {}

        super (Page, self).__init__ (**kw)

        if request is not None:
            if self._url is None:
                self._url = blinq.config.web_root_url + '/'.join(request.path)
            for provider in TabProvider.get_extensions ():
                provider.add_tabs (self, request)
            for provider in HeaderLinksProvider.get_extensions ():
                provider.add_header_links (self, request)

    def set_title (self, title):
        """Set the title of the page."""
        self._title = title

    def set_desc (self, desc):
        """Set the description of the page."""
        self._desc = desc

    def set_icon (self, icon):
        """Set the URL of an icon for the page."""
        self._icon = icon

    def add_tab (self, tabid, title, group=TabProvider.EXTRA_TAB):
        self._tabs.setdefault (group, [])
        self._tabs[group].append ((tabid, title))

    def add_header_link (self, href, title, group=HeaderLinksProvider.EXTRA_LINK):
        self._header_links.setdefault (group, [])
        self._header_links[group].append ((href, title))

    def add_to_tab (self, tabid, content):
        pane = self._panes.get(tabid, None)
        if pane is None:
            pane = ContentComponent()
            self._panes[tabid] = pane
        pane.add_content (content)

    def add_screenshot (self, screenshot):
        """
        Add a screenshot to the page.

        The screenshot argument is expected to be a dictionary which maps
        language codes to integer IDs, where the IDs are the id attribute
        of an OutputFile.  Information such as height, width, and thumbnail
        are retreived from the OutputFile.
        """
        try:
            # FIXME: i18n
            screen = screenshot['C']
            of = blip.db.OutputFile.get (screen)
            self._screenshot_file = of
        except:
            pass

    def add_sidebar_content (self, content):
        if self._sidebar is None:
            self._sidebar = ContentComponent ()
        self._sidebar.add_content (content)

    def output (self, res):
        """Output the HTML."""
        res.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN"')
        res.write(' "http://www.w3.org/TR/html4/strict.dtd">\n')
        res.write('<html><head>\n')
        res.write('<title>%s</title>\n' % self.escape(self._title))
        res.write('<meta http-equiv="Content-type" content="text/html; charset=utf-8">\n')
        res.write('<link rel="stylesheet" href="%sblip.css">\n'
                  % self.escape(blinq.config.web_data_url))
        res.write('<script language="javascript" type="text/javascript">\n')
        res.write('blip_root="%s";\n' % self.escape(blinq.config.web_root_url))
        res.write('blip_data="%s";\n' % self.escape(blinq.config.web_data_url))
        if self._url != None:
            res.write('blip_url="%s";\n' % self.escape(self._url))
        res.write('</script>\n')
        res.write('<script language="javascript" type="text/javascript" src="%sjquery.js"></script>\n'
                  % self.escape(blinq.config.web_data_url))
        res.write('<script language="javascript" type="text/javascript" src="%sjquery.cookie.js"></script>\n'
                  % self.escape(blinq.config.web_data_url))
        res.write('<script language="javascript" type="text/javascript" src="%sblip.js"></script>\n'
                  % self.escape(blinq.config.web_data_url))
        res.write('</head><body>')

        res.write('<div id="header"><table><tr>')
        res.write('<td class="headerlogo"><a href="%s" id="headerlink"><img src="%s" alt="Blip">%s</a></td>'
                  % self.escape((blinq.config.web_root_url,
                                 blinq.config.web_data_url + 'header-logo.png',
                                 blinq.config.web_site_name
                                 )))
        res.write('<td class="headerlinks">')
        linktot = reduce (lambda cnt, lst: cnt + len(lst),
                          self._header_links.values(), 0)
        linki = 0
        for linkgroup in sorted (self._header_links.keys()):
            for href, title in self._header_links[linkgroup]:
                linki += 1
                res.write('<a href="%s">%s</a>' % self.escape((href, title)))
                if linki != linktot:
                    res.write(BULLET)
        res.write('</td></tr></table></div>')

        res.write('<div id="all"><div id="subheader">')
        if res.request.account is not None and self._ident is not None:
            # FIXME STORM
            if not blip.db.AccountWatch.has_watch (res.request.account, self._ident):
                res.write('<div class="watch"><a href="javascript:watch(\'%s\')">%s</a></div>'
                          % self.escape((self._ident, blip.utils.gettext ('Watch'))))
        res.write('<h1>')
        if self._icon is not None:
            res.write('<table><tr><td><img class="icon" src="%s" alt="%s"></td><td>'
                      % self.escape((self._icon, self._title)))
        res.write('<div class="title">%s</div>' % self.escape(self._title))
        if self._desc is not None:
            res.write('<div class="desc">%s</div>' % self.escape(self._desc))
        if self._icon is not None:
            res.write('</td></tr></table>')
        res.write('</h1>')
        SublinksComponent.output (self, res)
        res.write('</div>')

        res.write('<div id="sidebar">')

        if len(self._tabs) > 0:
            res.write('<ul id="tabs">')
            for tabgroup in sorted (self._tabs.keys()):
                for tabid, title in self._tabs[tabgroup]:
                    title = self.escape(title).replace(' ', '&nbsp;')
                    res.write('<li class="tab" id="tab-%s">' % self.escape(tabid))
                    res.write(('<a href="javascript:tab(\'%s\')"><div>' + title + '</div></a></li>')
                              % self.escape(tabid))
            res.write('</ul>')

        if self._screenshot_file != None:
            res.write('<div class="screenshot">')
            url = self._screenshot_file.get_blip_url ()
            res.write('<a href="%s" class="zoom">' % self.escape(self._screenshot_file.blip_url))
            res.write('<img src="%s" width="%i" height="%i">'
                      % self.escape((self._screenshot_file.get_blip_url ('thumbs'),
                                     self._screenshot_file.data['thumb_width'],
                                     self._screenshot_file.data['thumb_height'])))
            res.write('</a></div>')

        if self._sidebar is not None:
            self._sidebar.output (res)
        res.write('</div>')

        res.write('<div id="body"><div id="panes">')
        FactsComponent.output (self, res)
        self.output_page_content (res)
        if len(self._tabs) > 0:
            for pane in self._panes:
                res.write('<div class="pane" id="pane-%s">' % self.escape(pane))
                self._panes[pane].output (res)
                res.write('</div>')
        res.write('</div></div>\n')
        res.write('</div></body></html>\n')
        
    def output_page_content (self, res):
        """Output the contents of the page."""
        ContentComponent.output (self, res)


class PageNotFound (Page):
    """
    A page for when an object is not found.

    FIXME: document **kw
    """

    def __init__ (self, message, **kw):
        kw.setdefault ('title', blip.utils.gettext('Page Not Found'))
        self._pages = kw.pop ('pages', [])
        self._message = message
        super (PageNotFound, self).__init__ (**kw)
        self.http_status = 400

    def output_page_content (self, res):
        """Output the contents of the page."""
        res.write('<div class="notfound">')
        res.write('<div class="message">%s</div>' % self.escape(self._message))
        if len(self._pages) > 0:
            res.write('<div class="pages">%s'
                      % self.escape(blip.utils.gettext ('The following pages might interest you:')))
            res.write('<ul>')
            for page in self._pages:
                res.write('<li><a href="%s%s">%s</a></li>' %
                          (blinq.config.web_root_url, page[0], page[1]))
            res.write('</ul></div>')
        res.write('</div>')
        Page.output_page_content (self, res)


class PageError (Page):
    """
    A page for when an error has occurred.

    FIXME: document **kw
    """

    def __init__ (self, message, **kw):
        kw.setdefault ('title', blip.utils.gettext('Bad Monkeys'))
        self._pages = kw.pop ('pages', [])
        self._message = message
        super (PageError, self).__init__ (**kw)
        self.http_status = 500
    
    def output_page_content (self, res):
        """Output the contents of the page."""
        res.write('<div class="servererror">')
        res.write('<div class="message">%s</div>' % self.escape(self._message))
        res.write('</div>')
        ContentComponent.output (self, res)


################################################################################
## Boxes

class AjaxBox (HtmlObject):
    """
    A box that loads its contents over AJAX.
    """
    def __init__ (self, url, **kw):
        super (AjaxBox, self).__init__ (**kw)
        self._url = url

    def output (self, res):
        """Output the HTML."""
        res.write('<div class="ajax"><a href="%s">%s</a></div>'
                  % self.escape((self._url, blip.utils.gettext ('Loading'))))


class SidebarBox (HtmlObject, ContentComponent, LinkBoxesComponent):
    def __init__ (self, title, **kw):
        super (SidebarBox, self).__init__ (**kw)
        self._title = title

    def output (self, res):
        """Output the HTML."""
        res.write('<div class="sidetitle">%s</div>' % self.escape(self._title))
        res.write('<div class="sidecont">')
        ContentComponent.output (self, res)
        LinkBoxesComponent.output (self, res)
        res.write('</div>')


class InfoBox (HtmlObject, SortableComponent, ContentComponent, FilterableComponent, LinkBoxesComponent):
    """
    A box containing information.

    An info box is a framed and titled box that contains various related bits
    of information.  Most pages are constructed primarily of info boxes.
    """
    def __init__ (self, title, **kw):
        super (InfoBox, self).__init__ (**kw)
        self._title = title

    def output (self, res):
        """Output the HTML."""
        res.write('<div class="info"')
        wid = self.get_html_id ()
        if wid != None:
            res.write(' id="%s"' % self.escape(wid))
        res.write('><div class="infotitle">%s</div>' % self.escape(self._title or ''))
        res.write('<div class="infocont">')
        SortableComponent.output (self, res)
        FilterableComponent.output (self, res)
        ContentComponent.output (self, res)
        LinkBoxesComponent.output (self, res)
        res.write('</div></div>')


class SectionBox (HtmlObject, ContentComponent):
    def __init__ (self, title, **kw):
        super (SectionBox, self).__init__ (**kw)
        self._title = title

    def output (self, res):
        res.write('<div class="section"')
        wid = self.get_html_id ()
        if wid != None:
            res.write(' id="%s"' % self.escape(wid))
        res.write('><div class="sectiontitle">%s</div>' % self.escape(self._title))
        ContentComponent.output (self, res)
        res.write('</div>')


class ContainerBox (HtmlObject, FilterableComponent, SortableComponent, ContentComponent, LinkBoxesComponent):
    """
    An all-purpose container box.

    A container box wraps arbitrary content with various useful things.
    If a title has been set, a container box will allow the box to be
    expanded and collapsed.  If sort links have been added, a sort link
    bar will be output.

    FIXME: document **kw
    """

    def __init__ (self, title=None, **kw):
        super (ContainerBox, self).__init__ (**kw)
        self._title = title

    def set_title (self, title):
        """Set the title of the container."""
        self._title = title

    def output (self, res):
        """Output the HTML."""
        slinks = len(self.get_sort_links())
        res.write('<div class="cont"')
        wid = self.get_html_id ()
        if wid != None:
            res.write(' id="%s"' % self.escape(wid))
        res.write('>')
        if self._title != None or slinks > 0:
            if self._title != None:
                res.write('<table class="cont"><tr>')
                res.write('<td class="contexp">&#9662;</td>')
                res.write('<td class="cont-title">')
            if self._title != None and slinks > 0:
                res.write('<table><tr><td>')
            if self._title != None:
                res.write('<span class="contexp">%s</span>' % self.escape(self._title))
            if self._title != None and slinks > 0:
                res.write('</td><td class="cont-slinks">')
            SortableComponent.output (self, res)
            if self._title != None and slinks > 0:
                res.write('</td></tr></table>')
            if self._title != None:
                res.write('</td></tr>')
                res.write('<tr><td></td><td class="cont-content">')
        FilterableComponent.output (self, res)
        res.write('<div class="cont-content">')
        ContentComponent.output (self, res)
        LinkBoxesComponent.output (self, res)
        res.write('</div>')
        if self._title != None:
            res.write('</td></tr></table>')
        res.write('</div>')


class TickerBox (HtmlObject):
    def __init__ (self, title, **kw):
        super (TickerBox, self).__init__ (**kw)
        self._title = title
        self._events = []

    def add_event (self, event, icon=None):
        self._events.append ((event, icon))

    def output (self, res):
        res.write('<div class="ticker">')
        res.write('<div class="tickertitle">%s</div>' % self.escape(self._title))
        for event, icon in self._events:
            res.write('<div class="tickerevent">')
            if icon != None:
                res.write('<div class="tickericon">')
                res.write('<img src="%s">' % self.escape(icon))
                res.write('</div>')
            res.write('<div class="tickertext">')
            res.write(self.escape(event))
            res.write('</div></div>')
        res.write('</div>')


class Calendar (HtmlObject):
    def __init__ (self, **kw):
        super (Calendar, self).__init__ (**kw)
        self._events = []

    def add_event (self, start, end, summary, desc):
        self._events.append ((start, end, summary, desc))

    def output (self, res):
        res.write('<div class="cal">')
        res.write('<table class="cal">')
        res.write('<tr class="calnav">')
        res.write('<td class="calprev">&#9666;</td>')
        res.write('<td class="calnav" colspan="5">')
        res.write('<span class="calmonth"></span> <span class="calyear"></span></td>')
        res.write('<td class="calnext">&#9656;</td>')
        res.write('</tr>')
        res.write('<tr class="calhead">')
        for day in ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'):
            res.write('<td>%s</td>' % day)
        res.write('</tr>')
        for i in range (6):
            res.write('<tr class="calweek">')
            for j in range (7):
                res.write('<td class="calday"></td>')
            res.write('</tr>')
        res.write('</table>')
        res.write('<dl class="calevents">')
        for event in self._events:
            res.write('<dt class="calevent">')
            res.write('<span class="caldtstart">%s</span> '
                      % self.escape(event[0].strftime('%Y-%m-%d')))
            res.write('<span class="calsummary">%s</span>' % self.escape(event[2]))
            res.write('</dt>')
            res.write('<dd class="calevent">')
            EllipsizedLabel (event[3], 130).output (res)
            res.write('</dd>')
        res.write('</dl>')
        res.write('</div>')


class LinkBox (HtmlObject, FactsComponent, ContentComponent):
    """
    A block-level link to an object with optional extra information.

    Link boxes display a link to some object, optionally including an icon,
    a graph, and a fact table.

    FIXME: document **kw
    """

    def __init__ (self, *args, **kw):
        self._url = self._title = self._icon = self._desc = None
        self._show_icon = True
        self._heading = False
        self._icon_size = None
        if isinstance (args[0], blip.db.BlipRecord):
            if args[0].linkable:
                self._url = args[0].blip_url
            self._title = args[0].title
            self._desc = args[0].desc
            self._icon = args[0].icon_url
            if isinstance (args[0], blip.db.Entity):
                self._icon_size = 36
        elif len(args) > 1:
            self._url = args[0]
            self._title = args[1]
        else:
            self._url = self._text = args[0]
        self._badges = []
        self._classes = []
        self._graphs = []
        icon_size = kw.pop ('icon_size', None)
        if icon_size is not None:
            self._icon_size = icon_size
        super (LinkBox, self).__init__ (**kw)

    def set_url (self, url):
        self._url = url

    def set_title (self, title):
        self._title = title

    def set_icon (self, icon):
        self._icon = icon

    def get_icon (self):
        return self._icon

    def has_icon (self):
        return self._icon != None

    def set_show_icon (self, show):
        self._show_icon = show

    def set_heading (self, heading):
        self._heading = heading

    def set_description (self, description):
        self._desc = description

    def add_class (self, cls):
        self._classes.append (cls)

    def add_badge (self, badge):
        self._badges.append (badge)

    def add_graph (self, url, width=None, height=None):
        self._graphs.append ((url, width, height))

    def output (self, res):
        """Output the HTML."""
        cls = ' '.join(['lbox'] + self._classes)
        res.write('<table class="%s"><tr>' % self.escape(cls))
        if self._show_icon:
            if self._icon_size != None:
                res.write('<td class="lboxicon" style="width: %ipx">' % self.escape(self._icon_size))
            else:
                res.write('<td class="lboxicon">')
            if self._icon != None:
                res.write('<img class="icon" src="%s" alt="%s">'
                         % self.escape((self._icon, self._title)))
            res.write('</td>')
            res.write('<td class="lboxtext">')
        else:
            res.write('<td class="lboxtext lboxtextonly">')
        if self._heading == True:
            res.write('<div class="lboxhead">')
        else:
            res.write('<div class="lboxtitle">')
        if self._url != None:
            res.write('<a href="%s"><span class="title">%s</span></a>'
                      % self.escape((self._url, self._title)))
        else:
            res.write('<span class="title">%s</span>' % self.escape(self._title))
        if len(self._badges) > 0:
            res.write(' ')
            for badge in self._badges:
                res.write('<img class="badge-%s" src="%sbadge-%s-16.png" width="16" height="16" alt="%s">'
                          % self.escape((badge, blinq.config.web_data_url, badge, get_badge_title (badge))))
        res.write('</div>')
        if self._desc != None:
            res.write('<div class="lboxdesc desc">')
            EllipsizedLabel (self._desc, 130).output (res)
            res.write('</div>')
        FactsComponent.output (self, res)
        ContentComponent.output (self, res)
        res.write('</td>')
        if len(self._graphs) > 0:
            res.write('<td class="lboxgraph">')
            for graph in self._graphs:
                Graph (graph[0], width=graph[1], height=graph[2]).output(res)
            res.write('</td>')
        res.write('</tr></table>')


class IconBox (HtmlObject, ContentComponent):
    def __init__ (self, **kw):
        super (IconBox, self).__init__ (**kw)
        self._title = None
        self._icons = []

    def set_title (self, title, **kw):
        self._title = title

    def add_link (self, *args):
        if isinstance (args[0], blip.db.BlipRecord):
            if args[0].linkable:
                url = args[0].blip_url
            title = args[0].title
            icon = args[0].icon_url
            self._icons.append ((url, title, icon))

    def output (self, res):
        """Output the HTML."""
        res.write('<div class="iconbox">')
        if self._title != None:
            res.write('<div class="iconboxtitle">%s</div>' % self.escape(self._title))
        res.write('<div class="iconboxcont">')
        ContentComponent.output (self, res)
        for url, title, icon in self._icons:
            res.write('<a href="%s" class="iconboxentry">' % self.escape(url))
            if icon != None:
                res.write('<div class="iconboxicon"><img class="img24" src="%s"></div>'
                          % self.escape(icon))
            else:
                res.write('<div class="iconboxicon"></div>')
            res.write('<div class="iconboxname">%s</div>' % self.escape(title))
            res.write('</a>')
        res.write('<div class="iconboxclear"></div>')
        res.write('</div></div>')


class ColumnBox (HtmlObject):
    def __init__ (self, num, **kw):
        super (ColumnBox, self).__init__ (**kw)
        self._columns = [[] for i in range(num)]

    def add_to_column (self, index, content):
        self._columns[index].append (content)
        return content

    def output (self, res):
        """Output the HTML."""
        res.write('<table class="cols"><tr>')
        width = str (100 / len(self._columns))
        for i in range(len(self._columns)):
            column = self._columns[i]
            if i == 0:
                res.write('<td class="col col-first">')
            else:
                res.write('<td class="col" style="width: ' + width + '%">')
            for item in column:
                res.write(self.escape(item))
            res.write('</td>')
        res.write('</tr></table>')


class GridBox (HtmlObject):
    def __init__ (self, **kw):
        super (GridBox, self).__init__ (**kw)
        self._rows = []
        self._classes = []

    def add_row (self, *row):
        self._rows.append ({'data': row})
        return len(self._rows) - 1

    def add_class (self, cls):
        self._classes.append (cls)

    def add_row_class (self, idx, cls):
        self._rows[idx].setdefault ('classes', [])
        self._rows[idx]['classes'].append (cls)

    def output (self, res):
        """Output the HTML."""
        if len (self._rows) == 0:
            return
        cls = ' '.join(['grid'] + self._classes)
        res.write('<table class="%s">' % self.escape(cls))
        cols = max ([len(x['data']) for x in self._rows])
        for row in self._rows:
            cls = row.get('classes', None)
            if cls != None:
                res.write('<tr class="%s">' % self.escape(' '.join(cls)))
            else:
                res.write('<tr>')
            for i in range (cols):
                if i == 0:
                    res.write('<td class="grid-td-first">')
                else:
                    res.write('<td class="grid-td">')
                if i < len (row['data']):
                    res.write(self.escape(row['data'][i]))
                res.write('</td>')
            res.write('</tr>')
        res.write('</table>')


class PaddingBox (HtmlObject, ContentComponent):
    """A box which puts vertical padding between its children."""
    def __init__ (self, **kw):
        super (PaddingBox, self).__init__ (**kw)

    def output (self, res):
        """Output the HTML."""
        content = self.get_content()
        for i in range(len(content)):
            if i == 0:
                res.write(self.escape(content[i]))
            else:
                res.write('<div class="pad">')
                res.write(self.escape(content[i]))
                res.write('</div>')


class AdmonBox (HtmlObject):
    error = "error"
    information = "information"
    warning = "warning"
    
    def __init__ (self, kind, title, **kw):
        self._kind = kind
        self._title = title
        self._tag = kw.pop ('tag', 'div')
        self._classes = []
        super (AdmonBox, self).__init__ (**kw)
        # We often use AdmonBox as an error fragment
        self.http_status = 500

    def add_class (self, class_):
        self._classes.append (class_)

    def output (self, res):
        """Output the HTML."""
        class_ = ' '.join(['admon'] + self._classes)
        res.write('<%s class="admon-%s %s"' % self.escape((self._tag, self._kind, class_)))
        wid = self.get_html_id ()
        if wid != None:
            res.write(' id="%s"' % self.escape(wid))
        res.write('><img src="%sadmon-%s-16.png" width="16" height="16"> '
                  % self.escape ((blinq.config.web_data_url, self._kind)))
        res.write(self.escape(self._title))
        res.write('</%s>' % self.escape(self._tag))


class TabbedBox (HtmlObject, ContentComponent):
    def __init__ (self, **kw):
        super (TabbedBox, self).__init__ (**kw)
        self._tabs = []

    def add_tab (self, url, title):
        """
        Add a tab to the box.

        This function takes a URL and a title for the new tab.  If the
        URL is None, the new tab is considered to be the active tab.
        """
        self._tabs.append ((url, title))

    def output (self, res):
        """Output the HTML."""
        res.write('<div class="tabbed">')
        res.write('<div class="tabbed-tabs">')
        for url, title in self._tabs:
            title = self.escape(title).replace(' ', '&nbsp;')
            if url == True:
                res.write('<span class="tabbed-tab-active">%s</span>' % self.escape(title))
            else:
                res.write('<span class="tabbed-tab-link"><a href="%s">%s</a></span>'
                          % self.escape((url, title)))
        res.write('</div>')
        res.write('<div class="tabbed-content">')
        ContentComponent.output (self, res)
        res.write('</div>')


class TranslationForm (HtmlObject):
    def __init__ (self, **kw):
        super (TranslationForm, self).__init__ (**kw)
        self._msgs = []

    class Entry (HtmlObject):
        def __init__ (self, msgkey, **kw):
            super (TranslationForm.Entry, self).__init__ (**kw)
            self._msg = msgkey[0]
            self._plural = msgkey[1]
            self._context = msgkey[2]
            self._comment = None
            self._trans = None

        def set_plural (self, plural):
            self._plural = plural

        def set_comment (self, comment):
            self._comment = comment

        def set_translated (self, trans):
            self._trans = trans

        def output (self, res):
            if self._trans == None:
                res.write('<div class="trentry trnotrans">')
            else:
                res.write('<div class="trentry">')
            res.write('<div class="trsource">')
            lines = self._msg.split('\\n')
            res.write(self.escape(lines[0]))
            for line in lines[1:]:
                res.write('<br>')
                res.write(self.escape(line))
            res.write('</div>')
            if self._plural != None:
                res.write('<div class="trsource">')
                lines = self._plural.split('\\n')
                res.write(self.escape(lines[0]))
                for line in lines[1:]:
                    res.write('<br>')
                    res.write(self.escape(line))
                res.write('</div>')
            if self._comment != None:
                lines = self._comment.split('\n')
                if lines[-1] == '':
                    lines = lines[:-1]
                if len(lines) > 0:
                    res.write('<div class="trcomment">')
                    res.write('# %s' % self.escape(lines[0]))
                    for line in lines[1:]:
                        res.write('<br>')
                        res.write('# %s' % self.escape(line))
                    res.write('</div>')
            if self._trans != None:
                for trans in self._trans:
                    res.write('<div class="trtrans">')
                    lines = trans.split('\\n')
                    res.write(self.escape(lines[0]))
                    for line in lines[1:]:
                        res.write('<br>')
                        res.write(self.escape(line))
                    res.write('</div>')
            res.write('</div>')

    def add_entry (self, msg):
        entry = TranslationForm.Entry (msg)
        self._msgs.append (entry)
        return entry

    def output (self, res):
        res.write('<div class="trform">')
        for msg in self._msgs:
            msg.output (res)
        res.write('</div>')


################################################################################
## Forms

class Form (HtmlObject, ContentComponent):
    def __init__ (self, method, action, **kw):
        super (Form, self).__init__ (**kw)
        self._method = method
        self._action = action

    def output (self, res):
        """Output the HTML."""
        res.write('<form method="%s" action="%s">'
                  % self.escape((self._method, self._action)))
        ContentComponent.output (self, res)
        res.write('</form>')
        

class TextInput (HtmlObject):
    def __init__ (self, name, **kw):
        self._name = name
        self._password = kw.pop ('password', False)
        super (TextInput, self).__init__ (**kw)
 
    def output (self, res):
        """Output the HTML."""
        res.write('<input type="%s" id="%s" name="%s" class="text">'
                  % self.escape((self._password and 'password' or 'text',
                                 self._name, self._name)))


class SubmitButton (HtmlObject):
    def __init__ (self, name, title, **kw):
        super (SubmitButton, self).__init__ (**kw)
        self._name = name
        self._title = title

    def output (self, res):
        """Output the HTML."""
        res.write('<input type="submit" id="%s" name="%s" value="%s" class="submit">'
                  % self.escape((self._name, self._name, self._title)))
    


################################################################################
## Lists

class DefinitionList (HtmlObject):
    def __init__ (self, **kw):
        self._all = []
        super (DefinitionList, self).__init__ (**kw)

    def add_term (self, term, classname=None):
        self._all.append (('dt', term, classname))

    def add_bold_term (self, term, classname=None):
        if classname == None:
            self._all.append (('dt', term, 'bold'))
        else:
            self._all.append (('dt', term, classname + ' bold'))

    def add_entry (self, entry, classname=None):
        self._all.append (('dd', entry, classname))

    def add_divider (self):
        self._all.append (('dt', None, 'hr'))
        
    def output (self, res):
        """Output the HTML."""
        res.write('<dl')
        if self.get_html_id() is not None:
            res.write(' id="%s"' % self.escape(self.get_html_id()))
        if self.get_html_class() is not None:
            res.write(' class="%s"' % self.escape(self.get_html_class()))
        res.write('>')
        for tag, content, cname in self._all:
            if cname != None:
                res.write('<%s class="%s">' % self.escape((tag, cname)))
            else:
                res.write('<%s>' % tag)
            if content:
                res.write(self.escape(content))
            else:
                res.write('<hr>')
            res.write('</%s>' % tag)
        res.write('</dl>')


class FactList (DefinitionList):
    def __init__ (self, **kw):
        kw.setdefault ('classname', 'facts')
        super (FactList, self).__init__ (**kw)


class BulletList (HtmlObject):
    def __init__ (self, **kw):
        self._id = kw.pop ('id', None)
        self._items = []
        self._title = None
        self._classname = kw.pop ('classname', None)
        super (BulletList, self).__init__ (**kw)

    def add_item (self, item, classname=None):
        self._items.append ((item, classname))

    def add_link (self, *args, **kw):
        self.add_item (Link(*args, **kw), 'link')

    def set_title (self, title):
        self._title = title

    def output (self, res):
        """Output the HTML."""
        res.write('<div class="ul">')
        if self._title != None:
            res.write('<div class="ultitle">')
            res.write(self.escape(self._title))
            res.write('</div>')
        res.write('<ul')
        if self._id != None:
            res.write(' id="%s"' % self.escape(self._id))
        if self._classname != None:
            res.write(' class="%s"' % self.escape(self._classname))
        res.write('>')
        for item, cname in self._items:
            if cname != None:
                res.write('<li class="%s">' % self.escape(cname))
            else:
                res.write('<li>')
            res.write(self.escape(item))
            res.write('</li>')
        res.write('</ul></div>')


################################################################################
## Other...

class Rule (HtmlObject):
    def output (self, res):
        """Output the HTML."""
        res.write('<div class="hr"><hr></div>')


class Graph (HtmlObject):
    """
    A generated graph with optional comments.
    """

    _count = 0

    def __init__ (self, url, **kw):
        self._url = url
        self._graph_id = kw.pop ('graph_id', None)
        self._count = kw.pop ('count', None)
        self._num = kw.pop ('num', 0)
        self._links = kw.pop ('links', False)
        self._width = kw.pop ('width', None)
        self._height = kw.pop ('height', None)
        self._map_only = kw.pop ('map_only', False)
        self._comments = []
        super (Graph, self).__init__ (**kw)

    def add_comment (self, coords, label, comment, href=None):
        """
        Add a comment to the graph.

        Comments are displayed as tooltips when the user hovers over the
        area defined by coords.  If the href argument is not None, that
        area will be a link to href.
        """
        self._comments.append ((coords, label, comment, href))

    def output (self, res):
        """Output the HTML."""
        if self._count == None:
            Graph._count += 1
            self._count = Graph._count
        if not self._map_only:
            if self._links:
                res.write('<table class="graph"><tr><td colspan="2">')
            res.write('<div class="graph" id="graph-%i">' % self.escape(self._count))
            res.write('<img src="%s"' % self.escape(self._url))
            if len(self._comments) > 0:
                res.write(' class="graphmap" id="graphmap-%i-%i" '
                          % self.escape((self._count, self._num)))
            if self._width != None:
                res.write(' width="%i"' % self.escape(self._width))
            if self._height != None:
                res.write(' height="%i"' % self.escape(self._height))
            res.write('>')
        if len(self._comments) > 0:
            res.write('<div class="comments" id="comments-%i-%i">'
                      % self.escape((self._count, self._num)))
            for comment in self._comments:
                res.write('<a class="comment" id="comment-%i-%i-%i" href="%s">'
                          % self.escape((self._count, self._num,
                                         comment[0][0], comment[3])))
                res.write('<div class="label">%s</div>' % self.escape(comment[1]))
                res.write('<div>%s</div></a>' % self.escape(comment[2]))
            res.write('</div>')
        if not self._map_only:
            res.write('</div>')
            if self._links:
                res.write('</td></tr><tr>')
                res.write('<td class="graphprev">')
                res.write('<a class="graphprev" id="graphprev-%i" href="javascript:slide(\'%s\', %i, -1)"'
                          % self.escape((self._count, self._graph_id, self._count)))
                res.write('<img src="%sgo-prev.png" height="12" width="12"></a>'
                          % self.escape(blinq.config.web_data_url))
                res.write('</td><td class="graphnext">')
                res.write('<a class="graphnext" id="graphnext-%i" href="javascript:slide(\'%s\', %i, 1)">'
                          % self.escape((self._count, self._graph_id, self._count)))
                res.write('<img src="%sgo-next.png" height="12" width="12"></a>'
                          % self.escape(blinq.config.web_data_url))
                res.write('</td></tr></table>')

    @classmethod
    def activity_graph (cls, outfile, boxid, title, **kw):
        """A convenience constructor to make an activity graph from an OutputFile."""
        kw.setdefault ('links', True)
        kw.setdefault ('width', outfile.data.get('width'))
        kw.setdefault ('height', outfile.data.get('height'))
        kw['graph_id'] = boxid
        graph = cls (outfile.blip_url, **kw)
        thisweek = blip.utils.weeknum (datetime.datetime.now())
        qs = '?q=%s&' % boxid
        for (coords, tot, weeknum) in outfile.data.get ('coords', []):
            ago = thisweek - weeknum
            if ago == 0:
                label = blip.utils.gettext ('this week:')
            elif ago == 1:
                label = blip.utils.gettext ('last week:')
            else:
                label = (blip.utils.gettext ('week of %s:') %
                         blip.utils.weeknumday(weeknum).strftime('%Y-%m-%d'))
            cmt = title % tot
            jslink = 'javascript:replace(\'' + boxid + '\', '
            jslink += ('blip_url + \'%sweeknum=%i\')') % (qs, weeknum)
            graph.add_comment (coords, label, cmt, jslink)
        return graph


class EllipsizedLabel (HtmlObject):
    """
    A text label that gets ellipsized if it exceeds a certain length.

    The constructor takes a string and a maximum length.  If the string is
    longer than the maximum length, it will be cut on a word boundary, and
    a (more) link will be inserted to show the remaining text.
    """
    
    def __init__ (self, label, size, **kw):
        self._label = label
        self._size = size
        self._truncate = kw.pop ('truncate', False)
        super (EllipsizedLabel, self).__init__ (**kw)

    def output (self, res):
        """Output the HTML."""
        if len (self._label) > self._size:
            i = self._size - 10
            if i <= 0:
                i = self._size
            while i < len(self._label):
                if self._label[i] == ' ':
                    break
                i += 1
            if i == len(self._label):
                res.write(self.escape(self._label))
            else:
                res.write(self.escape(self._label[:i+1]))
                if self._truncate:
                    res.write(self.escape(blip.utils.gettext ('...')))
                else:
                    res.write('<span class="elliptxt">%s</span>' % self.escape(self._label[i+1:]))
        else:
            res.write(self.escape(self._label))


class MenuLink (HtmlObject):
    """
    A link that pops down a menu of links.

    The constructor takes an ID and the text of the link.  The text
    may be omitted if menu_only is True.

    Keyword arguments:
    menu_only -- Only output the menu, not the link.
    """

    _count = 0

    def __init__ (self, id_, txt=None, **kw):
        self._menu_only = kw.pop ('menu_only', False)
        super (MenuLink, self).__init__ (**kw)
        self._id = id_
        self._txt = txt
        self._links = []
        self._menu_url = None

    def add_link (self, *args):
        if isinstance (args[0], HtmlObject):
            self._links.append (args[0])
        else:
            self._links.append (Link(*args))

    def set_menu_url (self, url):
        self._menu_url = url

    def output (self, res):
        """Output the HTML."""
        MenuLink._count += 1
        if self._menu_only != True:
            res.write('<a class="mlink" id="mlink%s" href="javascript:mlink(\'%s\')">%s</a>'
                      % self.escape((self._id, self._id, self._txt or self._id)))
        if self._menu_url != None:
            res.write('<div class="mstub" id="mcont%s">%s</div>'
                      % self.escape((self._id, self._menu_url)))
        else:
            res.write('<div class="mcont" id="mcont%s">' % self.escape(self._id))
            res.write('<div class="mcont-cont">')
            for link in self._links:
                res.write('<div>')
                res.write(link)
                res.write('</div>')
            res.write('</div></div>')


class PopupLink (HtmlObject, ContentComponent):
    def __init__ (self, text, content, **kw):
        super (PopupLink, self).__init__ (**kw)
        self._text = text
        self._links = []
        ContentComponent.add_content (self, content)

    def add_link (self, *args):
        if isinstance (args[0], HtmlObject):
            self._links.append (args[0])
        else:
            self._links.append (Link(*args))

    def output (self, res):
        """Output the HTML."""
        res.write('<a class="PopupLink" href="#">')
        res.write(self.escape(self._text))
        res.write('</a>')
        res.write('<div class="PopupLinkBody">')
        res.write('<div class="PopupLinkContent">')
        ContentComponent.output (self, res)
        res.write('</div>')
        if self._links != []:
            res.write('<div class="PopupLinkLinks">')
            for i in range(len(self._links)):
                if i != 0:
                    res.write(BULLET)
                res.write(self._links[i])
            res.write('</div>')
        res.write('</div>')


class Span (HtmlObject, ContentComponent):
    """
    A simple inline span.

    Any non-keyword arguments passed to the constructor are taken to
    be child content, and are automatically added with add_content.

    Keyword arguments:
    divider -- An optional divider to place between each element.
    """

    def __init__ (self, *args, **kw):
        self._divider = kw.pop ('divider', None)
        super (Span, self).__init__ (**kw)
        for arg in args:
            self.add_content (arg)

    def set_divider (self, divider):
        """Set a divider to be placed between child elements."""
        self._divider = divider

    def output (self, res):
        """Output the HTML."""
        res.write('<span')
        wid = self.get_html_id ()
        if wid != None:
            res.write(' id="%s"' % self.escape(wid))
        wcls = self.get_html_class ()
        if wcls != None:
            res.write(' class="%s"' % self.escape(wcls))
        res.write('>')
        content = self.get_content()
        for i in range(len(content)):
            if i != 0 and self._divider != None:
                res.write(self.escape(self._divider))
            res.write(self.escape(content[i]))
        res.write('</span>')


class StatusSpan (HtmlObject, ContentComponent):
    _statuses = {
        'none' : 0,
        'stub' : 1,
        'incomplete' : 2,
        'update': 3,
        'draft' : 4,
        'review' : 5,
        'candidate' : 6,
        'final' : 7
        }

    def __init__ (self, str, **kw):
        super (StatusSpan, self).__init__ (**kw)
        self._status = StatusSpan._statuses.get (str)
        if self._status == None:
            self._status = 0
            self.add_content ('none')
        else:
            self.add_content (str)

    def output (self, res):
        """Output the HTML."""
        res.write('<span class="status">%i</span>' % self.escape(self._status))
        ContentComponent.output (self, res)


class FactsTable (FactsComponent):
    pass


class Div (HtmlObject, ContentComponent):
    """
    A simple block.

    Any non-keyword arguments passed to the constructor are taken to
    be child content, and are automatically added with add_content.

    Keyword arguments:
    id -- An optional HTML id for the div tag.
    """

    def __init__ (self, *args, **kw):
        super (Div, self).__init__ (**kw)
        for arg in args:
            self.add_content (arg)

    def output (self, res):
        """Output the HTML."""
        res.write('<div')
        wid = self.get_html_id ()
        if wid != None:
            res.write(' id="%s"' % self.escape(wid))
        wcls = self.get_html_class ()
        if wcls != None:
            res.write(' class="%s"' % self.escape(wcls))
        res.write('>')
        ContentComponent.output (self, res)
        res.write('</div>')


class Table (HtmlObject):
    def __init__ (self, **kw):
        super (Table, self).__init__ (**kw)
        self._cols = 0
        self._rows = []

    def add_row (self, *args):
        self._cols = max (self._cols, len(args))
        self._rows.append (args)

    def output (self, res):
        res.write('<div class="table"><table')
        wid = self.get_html_id ()
        if wid != None:
            res.write(' id="%s"' % self.escape(wid))
        wcls = self.get_html_class ()
        if wcls != None:
            res.write(' class="%s"' % self.escape(wcls))
        res.write('>')
        for row in self._rows:
            res.write('<tr>')
            for col in row:
                res.write('<td>')
                res.write(self.escape(col))
                res.write('</td>')
            for col in range(self._cols - len(row)):
                res.write('<td></td>')
            res.write('</tr>')
        res.write('</table></div>')


class Pre (HtmlObject, ContentComponent):
    """
    A simple pre-formatted block.

    Any non-keyword arguments passed to the constructor are taken to
    be child content, and are automatically added with add_content.
    """

    def __init__ (self, *args, **kw):
        super (Pre, self).__init__ (**kw)
        for arg in args:
            self.add_content (arg)

    def output (self, res):
        """Output the HTML."""
        wid = self.get_html_id ()
        if wid is not None:
            res.write('<pre id="%s">' % self.escape(wid))
        else:
            res.write('<pre>')
        ContentComponent.output (self, res)
        res.write('</pre>')


class Link (HtmlObject):
    """
    A link to another page.

    This object constructs a link to another page.  The constructor
    can be called multiple ways.  If it is passed a BlipRecord, it
    automatically extracts the URL and title from that object.  If
    it is passed two strings, it considers them to be the URL and
    text of the link.  Otherwise, if it is passed a single string,
    it is used as both the URL and title.

    Keyword arguments:
    icon -- The name of an icon in Blip to prefix the link text with.
    classname -- The value of the HTML class attribute.
    """

    def __init__ (self, *args, **kw):
        self._href = self._text = None
        if isinstance (args[0], blip.db.BlipRecord):
            if args[0].linkable:
                self._href = args[0].blip_url
            self._text = args[0].title
        elif len(args) > 1:
            self._href = args[0]
            self._text = args[1]
        else:
            self._href = self._text = args[0]
        self._icon = kw.pop ('icon', None)
        self._classname = kw.pop ('classname', None)
        super (Link, self).__init__ (**kw)
    
    def output (self, res):
        """Output the HTML."""
        if self._href != None:
            if self._classname != None:
                res.write('<a href="%s" class="%s">'
                          % self.escape((self._href, self._classname)))
            else:
                res.write('<a href="%s">' % self.escape(self._href))
        if self._icon != None:
            res.write('<img src="%s%s-16.png" height="16" width="16"> '
                      % self.escape((blinq.config.web_data_url, self._icon)))
        res.write(self.escape(self._text))
        if (self._href != None):
            res.write('</a>')



def get_badge_title (badge):
    if badge == 'maintainer':
        return blip.utils.gettext ('Maintainer')
    elif badge == 'coordinator':
        return blip.utils.gettext ('Coordinator')
    elif badge == 'author':
        return blip.utils.gettext ('Author')
    elif badge == 'editor':
        return blip.utils.gettext ('Editor')
    elif badge == 'publisher':
        return blip.utils.gettext ('Publisher')
    else:
        return ''
