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

This module allows you to construct an HTML page using widgets,
in much the same way as you would construct a user interface in
a graphical toolkit.  High-level widgets are provided for various
common interface elements in Blip pages.
"""

import Cookie
import datetime
import cgi
import re
import sys

import blip.config
import blip.db
import blip.utils
import blip.web

esc = blip.web.esc

SPACE = ' '
BULLET = u' • '
TRIANGLE = u' ‣ '


class HtmlWidget (blip.web.WebWidget):
    """
    Base class for all HTML widgets.
    """
    def __init__ (self, **kw):
        super (HtmlWidget, self).__init__ (**kw)
        self.http_content_type = 'text/html; charset=utf-8'
        self._widget_id = kw.get ('widget_id', None)
        self._widget_class = kw.get ('widget_class', None)
        

    def set_id (self, widget_id):
        self._widget_id = widget_id

    def get_id (self):
        if self._widget_id != None:
            return self._widget_id
        else:
            return 'x' + str(hash(self))

    def add_class (self, widget_class):
        if isinstance (self._widget_class, basestring):
            self._widget_class = self._widget_class + ' ' + widget_class
        else:
            self._widget_class = widget_class

    def set_class (self, widget_class):
        self._widget_class = widget_class

    def get_class (self):
        return self._widget_class


class Component (blip.web.WebWidget):
    """
    Base class for all components.

    Components are effectively interfaces that widgets can implement.
    Their output methods are called at an appropriate place within a
    widget's output method to create a portion of that widget's HTML.
    """
    def __init__ (self, **kw):
        super (Component, self).__init__ (**kw)


################################################################################
## Components

class ContentComponent (Component):
    """
    Simple component for widgets with generic content.

    The output method will call output on each of the added widgets.  Some
    widgets may use this component only for the add_content method, and
    control how the added widgets are output by mapping over get_content.
    """

    def __init__ (self, **kw):
        super (ContentComponent, self).__init__ (**kw)
        self._content = []

    def add_content (self, content):
        """Add a widget or text to this container."""
        self._content.append (content)

    def get_content (self):
        """Get a list of all added content."""
        return self._content

    def output (self, res):
        """Output the HTML."""
        for cont in self._content:
            res.out (None, cont)


class SublinksComponent (Component):
    """
    Component for widgets that contain sublinks.

    Sublinks are a list of links found under the title of a widget.  They
    may provide alternate pages or a heirarchy of parent pages, depending
    on context.  The ouput method will create the sublinks.

    FIXME: document **kw
    """

    def __init__ (self, **kw):
        super (SublinksComponent, self).__init__ (**kw)
        self._sublinks = []
        self._divider = kw.get('divider', BULLET)

    def add_sublink (self, href, title):
        self._sublinks.append ((href, title))

    def set_sublinks_divider (self, div):
        self._divider = div

    def output (self, res):
        """Output the HTML."""
        if len(self._sublinks) > 0:
            res.out ('<div class="sublinks">', None, False)
            for i in range(len(self._sublinks)):
                if i != 0:
                    res.out (None, self._divider, False)
                if self._sublinks[i][0] != None:
                    res.out ('<a href="%s">%s</a>', self._sublinks[i], False)
                else:
                    res.out (None, self._sublinks[i][1], False)
            res.out ('</div>')


class FactsComponent (Component):
    """
    Component for widgets that contain fact tables.

    Fact tables are key-value tables providing more information about whatever
    thing the widget is showing.  The output method will create the table of
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
        res.out ('<table class="facts">')
        for fact in self._facts:
            if fact == None:
                res.out ('<tr class="fact-sep"><td></td><td></td></tr>')
            else:
                res.out ('<tr>', None, False)
                if fact['label'] != None:
                    res.out ('<td class="fact-key">', None, False)
                    key = esc(fact['label']).replace(' ', '&nbsp;')
                    key = esc(blip.utils.gettext ('%s:')) % key
                    res.out (key, None, False)
                    res.out ('</td>')
                    res.out ('<td class="fact-val">', None, False)
                else:
                    res.out ('<td class="fact-val" colspan="2">', None, False)
                def factout (val):
                    if isinstance (val, (basestring, HtmlWidget, Component)):
                        res.out (None, val, False)
                    elif isinstance (val, blip.db.BlipRecord):
                        res.out (Link(val))
                    elif hasattr (val, '__getitem__'):
                        for subval in val:
                            res.out ('<div>', None, False)
                            factout (subval)
                            res.out ('</div>')
                factout (fact['content'])
                res.out ('</td></tr>')
        res.out ('</table>')


class FilterableComponent (Component):
    def __init__ (self, **kw):
        super (FilterableComponent, self).__init__ (**kw)
        self._filtertag = kw.get ('filterable_tag', None)
        self._filterclass = kw.get ('filterable_class', None)
        self._filters = []

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
        filterid = self.get_id ()
        filtertag = self._filtertag or 'table'
        filterclass = self._filterclass or 'lbox'
        res.out ('<div class="filters" id="filters__%s"><span class="filters">', filterclass, False)
        res.out ('<a class="filter filter-%s filterall filteron"', filterid, False)
        res.out (' href="javascript:filter(\'%s\',\'%s\',\'%s\',null)"',
           (filterid, filtertag, filterclass), False)
        res.out (' id="filter__%s___all">', filterid, False)
        res.out (None, blip.utils.gettext ('All'), False)
        res.out ('</a>', None, False)
        for badge in self._filters:
            txt = get_badge_title (badge)
            res.out ('<a class="filter filter-%s"', filterid, False)
            res.out (' href="javascript:filter(\'%s\',\'%s\',\'%s\',\'%s\')"',
               (filterid, filtertag, filterclass, badge), False)
            res.out (' id="filter__%s__%s">', (filterid, badge), False)
            res.out ('<img src="%sbadge-%s-16.png" width="16" height="16" alt="%s">',
               (blip.config.web_data_url, badge, txt), False)
            res.out (' %s</a>', txt, False)
        res.out ('</span></div>')


class SortableComponent (Component):
    """
    Component for widgets that have sortable content.

    The output method will create the link bar for sorting the content.
    FIXME: explaing tag and class and how sort keys are gathered.

    FIXME: document **kw
    """

    def __init__ (self, **kw):
        super (SortableComponent, self).__init__ (**kw)
        self._slinktag = kw.get ('sortable_tag', None)
        self._slinkclass = kw.get ('sortable_class', None)
        self._slinks = []

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
        slinkid = self.get_id ()
        slinktag = self._slinktag or 'table'
        slinkclass = self._slinkclass or 'lbox'
        res.out ('<div class="sortlinks" id="sortlinks__%s">', slinkid, False)
        res.out ('<span class="sortlinks">', None, False)
        res.out (None, blip.utils.gettext ('sort by: '), False)
        for key, txt, cur in self._slinks:
            if cur == 1:
                res.out ('<span class="sortcur">%s ▴</span>', txt, False)
                break
            elif cur == -1:
                res.out ('<span class="sortcur">%s ▾</span>', txt, False)
                break
        res.out ('</span>')
        res.out ('<div class="sortmenu" id="sortmenu__%s">', slinkid)
        for key, txt, cur in self._slinks:
            res.out ('<div class="sortlink">', None, False)
            res.out ('<span class="sortlabel" id="sortlink__%s__%s">%s</span>:',
               (slinkid, key, txt))
            if cur == 1:
                res.out ('<span class="sortlink" id="sortlink__%s__%s__%s__%s__1">▴</span>',
                   (slinkid, slinktag, slinkclass, key))
            else:
                res.out (('<a class="sortlink" id="sortlink__%s__%s__%s__%s__1"'
                        ' href="javascript:sort(\'%s\',\'%s\',\'%s\',\'%s\',1)">▴</a>'),
                   (slinkid, slinktag, slinkclass, key,
                    slinkid, slinktag, slinkclass, key))
            if cur == -1:
                res.out ('<span class="sortlink" id="sortlink__%s__%s__%s__%s__-1">▾</span>',
                   (slinkid, slinktag, slinkclass, key))
            else:
                res.out (('<a class="sortlink" id="sortlink__%s__%s__%s__%s__-1"'
                        ' href="javascript:sort(\'%s\',\'%s\',\'%s\',\'%s\',-1)">▾</a>'),
                   (slinkid, slinktag, slinkclass, key,
                    slinkid, slinktag, slinkclass, key))
            res.out ('</div>')
        res.out ('</div></div>')


class LinkBoxesComponent (Component):
    """
    Component for widgets containing link boxes.

    This provides a convenience routine for adding link boxes, and can
    display the link boxes in multiple columns.

    FIXME: document **kw
    """

    def __init__ (self, **kw):
        super (LinkBoxesComponent, self).__init__ (**kw)
        self._boxes = []
        self._columns = kw.get('columns', 1)
        self._show_icons = None

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
            res.out ('<table class="cols"><tr>')
            res.out ('<td class="col col-first">')
            width = str(100 // self._columns)
            for box, col, pos in blip.utils.split (self._boxes, self._columns):
                if pos == 0:
                    if col > 0:
                        res.out ('</td><td class="col" style="width: ' + width + '%">')
                else:
                    res.out ('<div class="pad">')
                box.set_show_icon (self._show_icons)
                res.out (box)
                if pos > 0:
                    res.out ('</div>')
            res.out ('</td></tr></table>')
        else:
            for i in range(len(self._boxes)):
                box = self._boxes[i]
                if i != 0:
                    res.out ('<div class="pad">')
                box.set_show_icon (self._show_icons)
                res.out (box)
                if i != 0:
                    res.out ('</div>')


################################################################################
## Pages

class Page (HtmlWidget, ContentComponent, SublinksComponent, FactsComponent):
    """
    Complete web page.

    The output method creates all the standard HTML for the top and bottom
    of the page, and calls output_page_content in between.  Subclasses should
    override output_page_content.

    Keyword arguments:
    title -- The title of the page.
    icon  -- The URL of an icon for the page.
    """

    def __init__ (self, *args, **kw):
        super (Page, self).__init__ (**kw)
        self._ident = None
        self._title = None
        self._desc = None
        self._icon = None
        self._url = None
        handler = None
        record = None
        if len(args) > 0 and isinstance (args[0], blip.db.BlipRecord):
            record = args[0]
        elif len(args) > 0 and isinstance (args[0], pulse.core.RequestHandler):
            handler = args[0]
            if getattr (handler, 'record', None) is not None:
                record = args[0].record
        if record is not None:
            self._title = record.title
            self._desc = record.localized_desc
            self._icon = record.icon_url
            self._url = record.blip_url
            if record.watchable:
                self._ident = record.ident
        self._title = kw.get ('title') or self._title
        self._desc = kw.get ('desc') or self._desc
        self._icon = kw.get ('icon') or self._icon
        self._url = kw.get ('url') or self._url
        self._screenshot_file = None
        self._sidebar = None
        self._tabs = []
        self._panes = {}

        if handler is not None:
            tabs = []
            tabs = [app for app in handler.applications
                    if isinstance (app, pulse.applications.TabProvider)]
            for tab in blip.utils.attrsorted (tabs, 'tab_group', 'tab_sort', 'application_id'):
                self.add_tab (tab.application_id, tab.get_tab_title ())
                if tab.tab_group == pulse.applications.TabProvider.FIRST_TAB:
                    self.add_to_tab (tab.application_id, tab.get_tab())


    def set_title (self, title):
        """Set the title of the page."""
        self._title = title

    def set_desc (self, desc):
        """Set the description of the page."""
        self._desc = desc

    def set_icon (self, icon):
        """Set the URL of an icon for the page."""
        self._icon = icon

    def add_tab (self, tabid, title):
        self._tabs.append ((tabid, title))

    def add_to_tab (self, id, content):
        pane = self._panes.get(id, None)
        if pane == None:
            pane = ContentComponent()
            self._panes[id] = pane
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
        res.out (('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN"'
                ' "http://www.w3.org/TR/html4/strict.dtd">'))
        res.out ('<html><head>')
        res.out ('<title>%s</title>', self._title)
        res.out ('<meta http-equiv="Content-type" content="text/html; charset=utf-8">')
        res.out ('<link rel="stylesheet" href="%spulse.css">', blip.config.web_data_url)
        res.out ('<script language="javascript" type="text/javascript">')
        res.out ('pulse_root="%s"', blip.config.web_url)
        res.out ('pulse_data="%s"', blip.config.web_data_url)
        if self._url != None:
            res.out ('pulse_url="%s";', self._url)
        res.out ('</script>')
        res.out ('<script language="javascript" type="text/javascript" src="%sjquery.js"></script>',
           blip.config.web_data_url)
        res.out ('<script language="javascript" type="text/javascript" src="%spulse.js"></script>',
           blip.config.web_data_url)
        res.out ('</head><body>')

        res.out ('<div id="header"><table><tr>')
        res.out ('<td class="headerpulse"><a href="%s" id="headerlink"><img src="%s" alt="Pulse">Pulse</a></td>',
           (blip.config.web_url, blip.config.web_data_url + 'pulse-logo-small.png'))
        res.out ('<td class="headerlinks">')
        if res.http_account == None:
            res.out ('<a href="%saccount/login">%s</a>',
               (blip.config.web_url, blip.utils.gettext ('Log in')))
            res.out (' | ')
            res.out ('<a href="%saccount/new">%s</a>',
               (blip.config.web_url, blip.utils.gettext ('Register')))
        else:
            res.out ('<a href="%shome">%s</a>',
               (blip.config.web_url, blip.utils.gettext ('Home')))
            res.out (' | ')
            res.out ('<a href="%saccount/logout">%s</a>',
               (blip.config.web_url, blip.utils.gettext ('Log out')))
        res.out ('</td></tr></table></div>')

        res.out ('<div id="subheader"><div id="subheaderbar">', None, False)
        if res.http_account != None and self._ident != None:
            # FIXME STORM
            if not blip.db.AccountWatch.has_watch (res.http_account, self._ident):
                res.out ('<div class="watch"><a href="javascript:watch(\'%s\')">%s</a></div>',
                   (self._ident, blip.utils.gettext ('Watch')), False)
        res.out ('<h1>', None, False)
        if self._icon is not None:
            res.out ('<table><tr><td><img class="icon" src="%s" alt="%s"></td><td>',
               (self._icon, self._title), False)
        res.out ('<div class="title">%s</div>', self._title)
        if self._desc is not None:
            res.out ('<div class="desc">%s</div>', self._desc)
        if self._icon is not None:
            res.out ('</td></tr></table>', None, False)
        res.out ('</h1>')
        SublinksComponent.output (self, res)
        res.out ('</div></div>')

        res.out ('<div id="sidebar">')

        if len(self._tabs) > 0:
            res.out ('<ul id="tabs">')
            for tabid, title in self._tabs:
                title = esc (title).replace(' ', '&nbsp;')
                res.out ('<li class="tab" id="tab-%s">', tabid, False)
                res.out ('<a href="javascript:tab(\'%s\')"><div>' + title + '</div></a></li>', tabid)
            res.out ('</ul>')

        if self._screenshot_file != None:
            res.out ('<div class="screenshot">', None, False)
            url = self._screenshot_file.get_blip_url ()
            res.out ('<a href="%s" class="zoom">', self._screenshot_file.blip_url, False)
            res.out ('<img src="%s" width="%i" height="%i">',
               (self._screenshot_file.get_blip_url ('thumbs'),
                self._screenshot_file.data['thumb_width'],
                self._screenshot_file.data['thumb_height']))
            res.out ('</a></div>')

        if self._sidebar is not None:
            self._sidebar.output (res)
        res.out ('</div>')

        res.out ('<div id="body"><div id="panes">')
        FactsComponent.output (self, res)
        self.output_page_content (res)
        if len(self._tabs) > 0:
            for pane in self._panes:
                res.out ('<div class="pane" id="pane-%s">', pane)
                self._panes[pane].output (res)
                res.out ('</div>')
        res.out ('</div></div>')

        res.out ('</body></html>')
        
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
        super (PageNotFound, self).__init__ (**kw)
        self.http_status = 400
        self._pages = kw.get ('pages', [])
        self._message = message

    def output_page_content (self, res):
        """Output the contents of the page."""
        res.out ('<div class="notfound">')
        res.out ('<div class="message">%s</div>', self._message)
        if len(self._pages) > 0:
            res.out ('<div class="pages">%s',
               blip.utils.gettext ('The following pages might interest you:'))
            res.out ('<ul>')
            for page in self._pages:
                res.out ('<li><a href="%s%s">%s</a></li>' %
                   (blip.config.web_url, page[0], page[1]))
            res.out ('</ul></div>')
        res.out ('</div>')
        Page.output_page_content (self, res)


class PageError (Page):
    """
    A page for when an error has occurred.

    FIXME: document **kw
    """

    def __init__ (self, message, **kw):
        kw.setdefault ('title', blip.utils.gettext('Bad Monkeys'))
        super (PageError, self).__init__ (**kw)
        self.http_status = 500
        self._pages = kw.get ('pages', [])
        self._message = message
    
    def output_page_content (self, res):
        """Output the contents of the page."""
        res.out ('<div class="servererror">')
        res.out ('<div class="message">%s</div>', self._message)
        res.out ('</div>')
        ContentComponent.output (self, res)


################################################################################
## Boxes

class AjaxBox (HtmlWidget):
    """
    A box that loads its contents over AJAX.
    """
    def __init__ (self, url, **kw):
        super (AjaxBox, self).__init__ (**kw)
        self._url = url

    def output (self, res):
        """Output the HTML."""
        res.out ('<div class="ajax"><a href="%s">%s</a></div>',
           (self._url, blip.utils.gettext ('Loading')) )


class SidebarBox (HtmlWidget, ContentComponent, LinkBoxesComponent):
    def __init__ (self, title, **kw):
        super (SidebarBox, self).__init__ (**kw)
        self._title = title

    def output (self, res):
        """Output the HTML."""
        res.out ('<div class="sidetitle">%s</div>', self._title, False)
        res.out ('<div class="sidecont">')
        ContentComponent.output (self, res)
        LinkBoxesComponent.output (self, res)
        res.out ('</div>')


class InfoBox (HtmlWidget, SortableComponent, ContentComponent, FilterableComponent, LinkBoxesComponent):
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
        res.out ('<div class="info"', None, False)
        wid = self.get_id ()
        if wid != None:
            res.out (' id="%s"', wid, False)
        res.out ('><div class="infotitle">%s</div>', self._title or '')
        res.out ('<div class="infocont">')
        SortableComponent.output (self, res)
        FilterableComponent.output (self, res)
        ContentComponent.output (self, res)
        LinkBoxesComponent.output (self, res)
        res.out ('</div></div>')


class SectionBox (HtmlWidget, ContentComponent):
    def __init__ (self, title, **kw):
        super (SectionBox, self).__init__ (**kw)
        self._title = title

    def output (self, res):
        res.out ('<div class="section"', None, False)
        wid = self.get_id ()
        if wid != None:
            res.out (' id="%s"', wid, False)
        res.out ('><div class="sectiontitle">%s</div>', self._title)
        ContentComponent.output (self, res)
        res.out ('</div>')


class ContainerBox (HtmlWidget, FilterableComponent, SortableComponent, ContentComponent, LinkBoxesComponent):
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
        res.out ('<div class="cont"', None, False)
        wid = self.get_id ()
        if wid != None:
            res.out (' id="%s"', wid, False)
        res.out ('>', None, False)
        if self._title != None or slinks > 0:
            if self._title != None:
                res.out ('<table class="cont"><tr>')
                res.out ('<td class="contexp">&#9662;</td>')
                res.out ('<td class="cont-title">', None, False)
            if self._title != None and slinks > 0:
                res.out ('<table><tr><td>')
            if self._title != None:
                res.out ('<span class="contexp">%s</span>', (self._title), False)
            if self._title != None and slinks > 0:
                res.out ('</td><td class="cont-slinks">')
            SortableComponent.output (self, res)
            if self._title != None and slinks > 0:
                res.out ('</td></tr></table>')
            if self._title != None:
                res.out ('</td></tr>')
                res.out ('<tr><td></td><td class="cont-content">', None, False)
        FilterableComponent.output (self, res)
        res.out ('<div class="cont-content">')
        ContentComponent.output (self, res)
        LinkBoxesComponent.output (self, res)
        res.out ('</div>')
        if self._title != None:
            res.out ('</td></tr></table>')
        res.out ('</div>')


class TickerBox (HtmlWidget):
    def __init__ (self, title, **kw):
        super (TickerBox, self).__init__ (**kw)
        self._title = title
        self._events = []

    def add_event (self, event, icon=None):
        self._events.append ((event, icon))

    def output (self, res):
        res.out ('<div class="ticker">')
        res.out ('<div class="tickertitle">%s</div>', self._title)
        for event, icon in self._events:
            res.out ('<div class="tickerevent">', None, False)
            if icon != None:
                res.out ('<div class="tickericon">', None, False)
                res.out ('<img src="%s">', icon, False)
                res.out ('</div>', None, False)
            res.out ('<div class="tickertext">', None, False)
            res.out (None, event, False)
            res.out ('</div></div>')
        res.out ('</div>')


class Calendar (HtmlWidget):
    def __init__ (self, **kw):
        super (Calendar, self).__init__ (**kw)
        self._events = []

    def add_event (self, start, end, summary, desc):
        self._events.append ((start, end, summary, desc))

    def output (self, res):
        res.out ('<div class="cal">')
        res.out ('<table class="cal">')
        res.out ('<tr class="calnav">')
        res.out ('<td class="calprev">&#9666;</td>')
        res.out ('<td class="calnav" colspan="5">', None, False)
        res.out ('<span class="calmonth"></span> <span class="calyear"></span></td>')
        res.out ('<td class="calnext">&#9656;</td>')
        res.out ('</tr>')
        res.out ('<tr class="calhead">', None, False)
        for day in ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'):
            res.out ('<td>%s</td>', day, False)
        res.out ('</tr>')
        for i in range (6):
            res.out ('<tr class="calweek">', None, False)
            for j in range (7):
                res.out ('<td class="calday"></td>', None, False)
            res.out ('</tr>')
        res.out ('</table>')
        res.out ('<dl class="calevents">')
        for event in self._events:
            res.out ('<dt class="calevent">', None, False)
            res.out ('<span class="caldtstart">%s</span> ', event[0].strftime('%Y-%m-%d'), False)
            res.out ('<span class="calsummary">%s</span>', event[2], False)
            res.out ('</dt>')
            res.out ('<dd class="calevent">', None, False)
            res.out (EllipsizedLabel (event[3], 130), None, False)
            res.out ('</dd>')
        res.out ('</dl>')
        res.out ('</div>')


class LinkBox (HtmlWidget, FactsComponent, ContentComponent):
    """
    A block-level link to an object with optional extra information.

    Link boxes display a link to some object, optionally including an icon,
    a graph, and a fact table.

    FIXME: document **kw
    """

    def __init__ (self, *args, **kw):
        super (LinkBox, self).__init__ (**kw)
        self._url = self._title = self._icon = self._desc = None
        self._show_icon = True
        self._heading = False
        self._icon_size = None
        if isinstance (args[0], blip.db.BlipRecord):
            if args[0].linkable:
                self._url = args[0].blip_url
            self._title = args[0].title
            self._desc = args[0].localized_desc
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
        if kw.get('icon_size') != None:
            self._icon_size = kw['icon_size']

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
        res.out ('<table class="%s"><tr>', cls)
        if self._show_icon:
            if self._icon_size != None:
                res.out ('<td class="lboxicon" style="width: %ipx">', self._icon_size, False)
            else:
                res.out ('<td class="lboxicon">', None, False)
            if self._icon != None:
                res.out ('<img class="icon" src="%s" alt="%s">', (self._icon, self._title), False)
            res.out ('</td>')
            res.out ('<td class="lboxtext">')
        else:
            res.out ('<td class="lboxtext lboxtextonly">')
        if self._heading == True:
            res.out ('<div class="lboxhead">')
        else:
            res.out ('<div class="lboxtitle">')
        if self._url != None:
            res.out ('<a href="%s"><span class="title">%s</span></a>', (self._url, self._title))
        else:
            res.out ('<span class="title">%s</span>', self._title)
        if len(self._badges) > 0:
            res.out (' ')
            for badge in self._badges:
                res.out ('<img class="badge-%s" src="%sbadge-%s-16.png" width="16" height="16" alt="%s">',
                   (badge, blip.config.web_data_url, badge, get_badge_title (badge)))
        res.out ('</div>')
        if self._desc != None:
            res.out ('<div class="lboxdesc desc">')
            res.out (EllipsizedLabel (self._desc, 130))
            res.out ('</div>')
        FactsComponent.output (self, res)
        ContentComponent.output (self, res)
        res.out ('</td>')
        if len(self._graphs) > 0:
            res.out ('<td class="lboxgraph">')
            for graph in self._graphs:
                Graph (graph[0], width=graph[1], height=graph[2]).output(res)
            res.out ('</td>')
        res.out ('</tr></table>')


class IconBox (HtmlWidget, ContentComponent):
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
        res.out ('<div class="iconbox">')
        if self._title != None:
            res.out ('<div class="iconboxtitle">%s</div>', self._title)
        res.out ('<div class="iconboxcont">')
        ContentComponent.output (self, res)
        for url, title, icon in self._icons:
            res.out ('<a href="%s" class="iconboxentry">', url, False)
            if icon != None:
                res.out ('<div class="iconboxicon"><img class="img24" src="%s"></div>', icon, None)
            else:
                res.out ('<div class="iconboxicon"></div>')
            res.out ('<div class="iconboxname">%s</div>', title, None)
            res.out ('</a>')
        res.out ('<div class="iconboxclear"></div>')
        res.out ('</div></div>')


class ColumnBox (HtmlWidget):
    def __init__ (self, num, **kw):
        super (ColumnBox, self).__init__ (**kw)
        self._columns = [[] for i in range(num)]

    def add_to_column (self, index, content):
        self._columns[index].append (content)
        return content

    def output (self, res):
        """Output the HTML."""
        res.out ('<table class="cols"><tr>', None)
        width = str (100 / len(self._columns))
        for i in range(len(self._columns)):
            column = self._columns[i]
            if i == 0:
                res.out ('<td class="col col-first">')
            else:
                res.out ('<td class="col" style="width: ' + width + '%">')
            for item in column:
                res.out (None, item)
            res.out ('</td>')
        res.out ('</tr></table>')


class GridBox (HtmlWidget):
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
        res.out ('<table class="%s">', cls)
        cols = max ([len(x['data']) for x in self._rows])
        for row in self._rows:
            cls = row.get('classes', None)
            if cls != None:
                res.out ('<tr class="%s">', ' '.join(cls))
            else:
                res.out ('<tr>')
            for i in range (cols):
                if i == 0:
                    res.out ('<td class="grid-td-first">')
                else:
                    res.out ('<td class="grid-td">')
                if i < len (row['data']):
                    res.out (None, row['data'][i])
                res.out ('</td>')
            res.out ('</tr>')
        res.out ('</table>')


class PaddingBox (HtmlWidget, ContentComponent):
    """A box which puts vertical padding between its children."""
    def __init__ (self, **kw):
        super (PaddingBox, self).__init__ (**kw)

    def output (self, res):
        """Output the HTML."""
        content = self.get_content()
        for i in range(len(content)):
            if i == 0:
                res.out (None, content[i])
            else:
                res.out ('<div class="pad">')
                res.out (None, content[i])
                res.out ('</div>')


class AdmonBox (HtmlWidget):
    error = "error"
    information = "information"
    warning = "warning"
    
    def __init__ (self, kind, title, **kw):
        super (AdmonBox, self).__init__ (**kw)
        # We often use AdmonBox as an error fragment
        self.http_status = 500
        self._kind = kind
        self._title = title
        self._tag = kw.get('tag', 'div')
        self._classes = []

    def add_class (self, class_):
        self._classes.append (class_)

    def output (self, res):
        """Output the HTML."""
        class_ = ' '.join(['admon'] + self._classes)
        res.out ('<%s class="admon-%s %s"', (self._tag, self._kind, class_))
        wid = self.get_id ()
        if wid != None:
            res.out (' id="%s"', wid, False)
        res.out ('><img src="%sadmon-%s-16.png" width="16" height="16">',
           (blip.config.web_data_url, self._kind))
        res.out (None, self._title)
        res.out ('</%s>', self._tag)


class TabbedBox (HtmlWidget, ContentComponent):
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
        res.out ('<div class="tabbed">')
        res.out ('<div class="tabbed-tabs">')
        for url, title in self._tabs:
            title = esc(title).replace(' ', '&nbsp;')
            if url == True:
                res.out ('<span class="tabbed-tab-active">' + title + '</span>')
            else:
                res.out ('<span class="tabbed-tab-link"><a href="%s">' + title + '</a></span>', url)
        res.out ('</div>')
        res.out ('<div class="tabbed-content">')
        ContentComponent.output (self, res)
        res.out ('</div>')


class TranslationForm (HtmlWidget):
    def __init__ (self, **kw):
        super (TranslationForm, self).__init__ (**kw)
        self._msgs = []

    class Entry (HtmlWidget):
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
                res.out ('<div class="trentry trnotrans">')
            else:
                res.out ('<div class="trentry">')
            res.out ('<div class="trsource">')
            lines = self._msg.split('\\n')
            res.out (None, lines[0])
            for line in lines[1:]:
                res.out ('<br>')
                res.out (None, line)
            res.out ('</div>')
            if self._plural != None:
                res.out ('<div class="trsource">')
                lines = self._plural.split('\\n')
                res.out (None, lines[0])
                for line in lines[1:]:
                    res.out ('<br>')
                    res.out (None, line)
                res.out ('</div>')
            if self._comment != None:
                lines = self._comment.split('\n')
                if lines[-1] == '':
                    lines = lines[:-1]
                if len(lines) > 0:
                    res.out ('<div class="trcomment">')
                    res.out ('# %s', lines[0])
                    for line in lines[1:]:
                        res.out ('<br>')
                        res.out ('# %s', line)
                    res.out ('</div>')
            if self._trans != None:
                for trans in self._trans:
                    res.out ('<div class="trtrans">')
                    lines = trans.split('\\n')
                    res.out (None, lines[0])
                    for line in lines[1:]:
                        res.out ('<br>')
                        res.out (None, line)
                    res.out ('</div>')
            res.out ('</div>')

    def add_entry (self, msg):
        entry = TranslationForm.Entry (msg)
        self._msgs.append (entry)
        return entry

    def output (self, res):
        res.out ('<div class="trform">')
        for msg in self._msgs:
            msg.output (res)
        res.out ('</div>')


################################################################################
## Forms

class Form (HtmlWidget, ContentComponent):
    def __init__ (self, method, action, **kw):
        super (Form, self).__init__ (**kw)
        self._method = method
        self._action = action

    def output (self, res):
        """Output the HTML."""
        res.out ('<form method="%s" action="%s">', (self._method, self._action))
        ContentComponent.output (self, res)
        res.out ('</form>')
        

class TextInput (HtmlWidget):
    def __init__ (self, name, **kw):
        super (TextInput, self).__init__ (**kw)
        self._name = name
        self._password = kw.get('password', False)
 
    def output (self, res):
        """Output the HTML."""
        res.out ('<input type="%s" id="%s" name="%s" class="text">', 
           (self._password and 'password' or 'text', self._name, self._name))


class SubmitButton (HtmlWidget):
    def __init__ (self, name, title, **kw):
        super (SubmitButton, self).__init__ (**kw)
        self._name = name
        self._title = title

    def output (self, res):
        """Output the HTML."""
        res.out ('<input type="submit" id="%s" name="%s" value="%s" class="submit">',
           (self._name, self._name, self._title))
    


################################################################################
## Lists

class DefinitionList (HtmlWidget):
    def __init__ (self, **kw):
        super (DefinitionList, self).__init__ (**kw)
        self._id = kw.get('id', None)
        self._classname = kw.get('classname', None)
        self._all = []

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
        res.out ('<dl', None, False)
        if self._id != None:
            res.out (' id="%s"', self._id, False)
        if self._classname != None:
            res.out (' class="%s"', self._classname, False)
        res.out ('>')
        for tag, content, cname in self._all:
            if cname != None:
                res.out ('<%s class="%%s">' % tag, cname, False)
            else:
                res.out ('<%s>' % tag, None, False)
            if content:
                res.out (None, content, False)
            else:
                res.out ('<hr>', None, False)
            res.out ('</%s>' % tag)
        res.out ('</dl>')


class FactList (DefinitionList):
    def __init__ (self, **kw):
        kw.setdefault ('classname', 'facts')
        super (FactList, self).__init__ (**kw)


class BulletList (HtmlWidget):
    def __init__ (self, **kw):
        super (BulletList, self).__init__ (**kw)
        self._id = kw.get ('id', None)
        self._items = []
        self._title = None
        self._classname = kw.get ('classname', None)

    def add_item (self, item, classname=None):
        self._items.append ((item, classname))

    def add_link (self, *args, **kw):
        self.add_item (Link(*args, **kw), 'link')

    def set_title (self, title):
        self._title = title

    def output (self, res):
        """Output the HTML."""
        res.out ('<div class="ul">')
        if self._title != None:
            res.out ('<div class="ultitle">', None, False)
            res.out (None, self._title, False)
            res.out ('</div>')
        res.out ('<ul', None, False)
        if self._id != None:
            res.out (' id="%s"', self._id, False)
        if self._classname != None:
            res.out (' class="%s"', self._classname, False)
        res.out ('>')
        for item, cname in self._items:
            if cname != None:
                res.out ('<li class="%s">', cname, False)
            else:
                res.out ('<li>', None, False)
            res.out (None, item, False)
            res.out ('</li>')
        res.out ('</ul></div>')


################################################################################
## Other...

class Rule (HtmlWidget):
    def output (self, res):
        """Output the HTML."""
        res.out ('<div class="hr"><hr></div>')


class Graph (HtmlWidget):
    """
    A generated graph with optional comments.
    """

    _count = 0

    def __init__ (self, url, **kw):
        super (Graph, self).__init__ (**kw)
        self._url = url
        self._application = kw.get('application')
        self._count = kw.get('count', None)
        self._num = kw.get('num', 0)
        self._links = kw.get('links', False)
        self._width = kw.get('width', None)
        self._height = kw.get('height', None)
        self._map_only = kw.get('map_only', False)
        self._comments = []

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
                res.out ('<table class="graph"><tr><td colspan="2">', None, False)
            res.out ('<div class="graph" id="graph-%i">', self._count, False)
            res.out ('<img src="%s"', self._url, False)
            if len(self._comments) > 0:
                res.out (' class="graphmap" id="graphmap-%i-%i" ',
                   (self._count, self._num), False)
            if self._width != None:
                res.out (' width="%i"', self._width, False)
            if self._height != None:
                res.out (' height="%i"', self._height, False)
            res.out ('>', None, False)
        if len(self._comments) > 0:
            res.out ('<div class="comments" id="comments-%i-%i">',
               (self._count, self._num), False)
            for comment in self._comments:
                res.out ('<a class="comment" id="comment-%i-%i-%i" href="%s">',
                   (self._count, self._num, comment[0][0], comment[3]), False)
                res.out ('<div class="label">%s</div>', comment[1], False)
                res.out ('<div>%s</div></a>', comment[2], False)
            res.out ('</div>', None, False)
        if not self._map_only:
            res.out ('</div>', None, False)
            if self._links:
                res.out ('</td></tr><tr>')
                res.out ('<td class="graphprev">', None, False)
                res.out ('<a class="graphprev" id="graphprev-%i" href="javascript:slide(\'%s\', %i, -1)"',
                   (self._count, self._application, self._count), False)
                res.out ('<img src="%sgo-prev.png" height="12" width="12"></a>',
                   blip.config.web_data_url, False)
                res.out ('</td><td class="graphnext">', None, False)
                res.out ('<a class="graphnext" id="graphnext-%i" href="javascript:slide(\'%s\', %i, 1)">',
                   (self._count, self._application, self._count), False)
                res.out ('<img src="%sgo-next.png" height="12" width="12"></a>',
                   blip.config.web_data_url, False)
                res.out ('</td></tr></table>')

    @classmethod
    def activity_graph (cls, outfile, url, boxid, title, application, data, **kw):
        """A convenience constructor to make an activity graph from an OutputFile."""
        kw.setdefault ('links', True)
        kw.setdefault ('width', outfile.data.get('width'))
        kw.setdefault ('height', outfile.data.get('height'))
        kw['application'] = application
        graph = cls (outfile.blip_url, **kw)
        thisweek = blip.utils.weeknum (datetime.datetime.now())
        qs = '?application=%s&' % application
        for key in data.keys():
            qs += '%s=%s&' % (key, data[key])
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
            jslink += ('\'%s%sweeknum=%i\')') % (url, qs, weeknum)
            graph.add_comment (coords, label, cmt, jslink)
        return graph


class EllipsizedLabel (HtmlWidget):
    """
    A text label that gets ellipsized if it exceeds a certain length.

    The constructor takes a string and a maximum length.  If the string is
    longer than the maximum length, it will be cut on a word boundary, and
    a (more) link will be inserted to show the remaining text.
    """
    
    def __init__ (self, label, size, **kw):
        super (EllipsizedLabel, self).__init__ (**kw)
        self._label = label
        self._size = size
        self._truncate = kw.get ('truncate', False)

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
                res.out (None, self._label, False)
            else:
                res.out (None, self._label[:i+1], False)
                if self._truncate:
                    res.out (None, blip.utils.gettext ('...'), False)
                else:
                    res.out ('<span class="elliptxt">%s</span>', self._label[i+1:], False)
        else:
            res.out (None, self._label)


class MenuLink (HtmlWidget):
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
        if isinstance (args[0], HtmlWidget):
            self._links.append (args[0])
        else:
            self._links.append (Link(*args))

    def set_menu_url (self, url):
        self._menu_url = url

    def output (self, res):
        """Output the HTML."""
        MenuLink._count += 1
        if self._menu_only != True:
            res.out ('<a class="mlink" id="mlink%s" href="javascript:mlink(\'%s\')">%s</a>',
               (self._id, self._id, self._txt or self._id))
        if self._menu_url != None:
            res.out ('<div class="mstub" id="mcont%s">%s</div>',
               (self._id, self._menu_url))
        else:
            res.out ('<div class="mcont" id="mcont%s">', self._id)
            res.out ('<div class="mcont-cont">')
            for link in self._links:
                res.out ('<div>', None, False)
                res.out (link, None, False)
                res.out ('</div>')
            res.out ('</div></div>')


class PopupLink (HtmlWidget):
    _count = 0

    def __init__ (self, short, full, **kw):
        super (PopupLink, self).__init__ (**kw)
        self._short = short
        self._full = full
        self._links = []

    def add_link (self, *args):
        if isinstance (args[0], HtmlWidget):
            self._links.append (args[0])
        else:
            self._links.append (Link(*args))

    def output (self, res):
        """Output the HTML."""
        PopupLink._count += 1
        pid = str(PopupLink._count)
        res.out ('<a class="plink" id="plink%s" href="javascript:plink(\'%s\')">',
           (pid, pid), False)
        res.out (None, self._short, False)
        res.out ('</a>')
        res.out ('<div class="pcont" id="pcont%s">', pid)
        if isinstance (self._full, basestring):
            while len(self._full) > 0 and self._full[-1] == '\n': self._full = self._full[:-1]
        res.out ('<pre class="pcont-content">', None, False)
        res.out (None, self._full)
        res.out ('</pre>')
        if self._links != []:
            res.out ('<div class="pcont-links">', None, False)
            for i in range(len(self._links)):
                if i != 0:
                    res.out (BULLET)
                res.out (self._links[i])
            res.out ('</div>')
        res.out ('</div>')

    @classmethod
    def from_revision (cls, rev, app, **kw):
        comment = rev.comment
        if comment.strip() == '':
            lnk = cls (AdmonBox (AdmonBox.warning, blip.utils.gettext ('No comment')),
                       '', **kw)
        else:
            datere = re.compile ('^\d\d\d\d-\d\d-\d\d ')
            colonre = re.compile ('^\* [^:]*:(.*)')
            maybe = ''
            for line in comment.split('\n'):
                line = line.strip()
                if line == '':
                    pass
                elif datere.match(line):
                    maybe = line
                else:
                    cmatch = colonre.match(line)
                    if cmatch:
                        line = cmatch.group(1).strip()
                        if line != '':
                            break
                    else:
                        break
            if line == '':
                line = maybe
            if len(line) > 80:
                i = 60
                while i < len(line):
                    if line[i] == ' ':
                        break
                    i += 1
                if i < len(comment):
                    line = line[:i] + '...'

            lnk = cls (line, comment, **kw)

        branch = kw.get ('branch', None)
        if branch == None:
            branch = rev.branch
        if branch.scm_type == 'svn':
            if branch.scm_server.endswith ('/svn/'):
                base = branch.scm_server[:-4] + 'viewvc/'
                colon = base.find (':')
                if colon < 0:
                    return lnk
                if base[:colon] != 'http':
                    base = 'http' + base[colon:]
                if branch.scm_path != None:
                    base += branch.scm_path
                elif branch.scm_branch == 'trunk':
                    base += branch.scm_module + '/trunk'
                else:
                    base += branch.scm_module + '/branches/' + branch.scm_branch
                mlink = MenuLink (rev.revision, 'files')
                mlink.set_menu_url ('%s?application=%s&action=revfiles&revid=%s'
                                    % (branch.blip_url, app, str(rev.ident)))
                lnk.add_link (mlink)
                infourl = base + '?view=revision&revision=' + rev.revision
                lnk.add_link (infourl, blip.utils.gettext ('info'))

        return lnk


class Span (HtmlWidget, ContentComponent):
    """
    A simple inline span.

    Any non-keyword arguments passed to the constructor are taken to
    be child content, and are automatically added with add_content.

    Keyword arguments:
    divider -- An optional divider to place between each element.
    """

    def __init__ (self, *args, **kw):
        super (Span, self).__init__ (**kw)
        for arg in args:
            self.add_content (arg)
        self._divider = kw.get('divider', None)

    def set_divider (self, divider):
        """Set a divider to be placed between child elements."""
        self._divider = divider

    def output (self, res):
        """Output the HTML."""
        res.out ('<span', None, False)
        wid = self.get_id ()
        if wid != None:
            res.out (' id="%s"', wid, False)
        wcls = self.get_class ()
        if wcls != None:
            res.out (' class="%s"', wcls, False)
        res.out ('>', None, False)
        content = self.get_content()
        for i in range(len(content)):
            if i != 0 and self._divider != None:
                res.out (None, self._divider, False)
            res.out (None, content[i], False)
        res.out ('</span>')


class StatusSpan (HtmlWidget, ContentComponent):
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
        res.out ('<span class="status">%i</span>', self._status, False)
        ContentComponent.output (self, res)


class FactsTable (FactsComponent):
    pass


class Div (HtmlWidget, ContentComponent):
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
        res.out ('<div', None, False)
        wid = self.get_id ()
        if wid != None:
            res.out (' id="%s"', wid, False)
        wcls = self.get_class ()
        if wcls != None:
            res.out (' class="%s"', wcls, False)
        res.out ('>', None, False)
        ContentComponent.output (self, res)
        res.out ('</div>')


class Table (HtmlWidget):
    def __init__ (self, **kw):
        super (Table, self).__init__ (**kw)
        self._cols = 0
        self._rows = []

    def add_row (self, *args):
        self._cols = max (self._cols, len(args))
        self._rows.append (args)

    def output (self, res):
        res.out ('<div class="table"><table', None, False)
        wid = self.get_id ()
        if wid != None:
            res.out (' id="%s"', wid, False)
        wcls = self.get_class ()
        if wcls != None:
            res.out (' class="%s"', wcls, False)
        res.out ('>', None, False)
        for row in self._rows:
            res.out ('<tr>')
            for col in row:
                res.out ('<td>', None, False)
                res.out (None, col, False)
                res.out ('</td>')
            for col in range(self._cols - len(row)):
                res.out ('<td></td>')
            res.out ('</tr>')
        res.out ('</table></div>')


class Pre (HtmlWidget, ContentComponent):
    """
    A simple pre-formatted block.

    Any non-keyword arguments passed to the constructor are taken to
    be child content, and are automatically added with add_content.

    Keyword arguments:
    id -- An optional HTML id for the pre tag.
    """

    def __init__ (self, *args, **kw):
        super (Pre, self).__init__ (**kw)
        self._id = kw.get('id', None)
        for arg in args:
            self.add_content (arg)

    def output (self, res):
        """Output the HTML."""
        if self._id != None:
            res.out ('<pre id="%s">', self._id)
        else:
            res.out ('<pre>')
        ContentComponent.output (self, res)
        res.out ('</pre>')


class Link (HtmlWidget):
    """
    A link to another page.

    This widget constructs a link to another page.  The constructor
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
        super (Link, self).__init__ (**kw)
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
        self._icon = kw.get ('icon', None)
        self._classname = kw.get ('classname', None)
    
    def output (self, res):
        """Output the HTML."""
        if self._href != None:
            if self._classname != None:
                res.out ('<a href="%s" class="%s">', (self._href, self._classname), False)
            else:
                res.out ('<a href="%s">', self._href, False)
        if self._icon != None:
            res.out ('<img src="%s%s-16.png" height="16" width="16"> ',
               (blip.config.web_data_url, self._icon),
               False)
        res.out (None, self._text, False)
        if (self._href != None):
            res.out ('</a>')



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
