# -*- coding: utf-8 -*-
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
Generate HTML output.

This module allows you to construct an HTML page using widgets,
in much the same way as you would construct a user interface in
a graphical toolkit.  High-level widgets are provided for various
common interface elements in Pulse pages.
"""

import datetime
import cgi
import md5
import re
import sys

import pulse.config
import pulse.models as db
import pulse.utils


SPACE = ' '
BULLET = u' • '
TRIANGLE = u' ‣ '


class Widget (object):
    """
    Base class for all widgets.
    """

    def __init__ (self, **kw):
        super (Widget, self).__init__ (**kw)

    def output (self, fd=None):
        """
        Output the HTML for this widget.

        This is an abstract method that subclasses must implement.
        """
        pass


class Component (object):
    """
    Base class for all components.

    Components are effectively interfaces that widgets can implement.
    Their output methods are called at an appropriate place within a
    widget's output method to create a portion of that widget's HTML.
    """

    def __init__ (self, **kw):
        super (Component, self).__init__ (**kw)

    def output (self, fd=None):
        """
        Output the HTML for this component.

        This is an abstract method that subclasses must implement.
        """
        pass


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

    def output (self, fd=None):
        """Output the HTML."""
        for cont in self._content:
            p (fd, None, cont)


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

    def output (self, fd=None):
        """Output the HTML."""
        if len(self._sublinks) > 0:
            p (fd, '<div class="sublinks">', None, False)
            for i in range(len(self._sublinks)):
                if i != 0:
                    p (fd, None, self._divider, False)
                if self._sublinks[i][0] != None:
                    p (fd, '<a href="%s">%s</a>', self._sublinks[i], False)
                else:
                    p (fd, None, self._sublinks[i][1], False)
            p (fd, '</div>')


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

    def add_fact_sep (self):
        self._facts.append (None)

    def output (self, fd=None):
        """Output the HTML."""
        if len (self._facts) == 0:
            return
        p (fd, '<table class="facts">')
        for fact in self._facts:
            if fact == None:
                p (fd, '<tr class="fact-sep"><td></td><td></td></tr>')
            else:
                p (fd, '<tr>', None, False)
                if fact['label'] != None:
                    p (fd, '<td class="fact-key">', None, False)
                    key = esc(fact['label']).replace(' ', '&nbsp;')
                    key = esc(pulse.utils.gettext ('%s:')) % key
                    p (fd, key, None, False)
                    p (fd, '</td>')
                    p (fd, '<td class="fact-val">', None, False)
                else:
                    p (fd, '<td class="fact-val" colspan="2">', None, False)
                def factout (val):
                    if isinstance (val, (basestring, Widget, Component)):
                        p (fd, None, val, False)
                    elif isinstance (val, db.PulseRecord):
                        p (fd, Link(val))
                    elif hasattr (val, '__getitem__'):
                        for subval in val:
                            p (fd, '<div>', None, False)
                            factout (subval)
                            p (fd, '</div>')
                factout (fact['content'])
                p (fd, '</td></tr>')
        p (fd, '</table>')


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

    def add_sort_link (self, key, txt, cur=False):
        self._slinks.append ((key, txt, cur))

    def get_sort_links (self):
        return self._slinks

    def output (self, fd=None):
        """Output the HTML."""
        slinktag = self._slinktag or 'table'
        slinkclass = self._slinkclass or 'lbox'
        p (fd, '<div class="slinks" id="slink__%s"><span class="slinks">', slinkclass, False)
        p (fd, None, pulse.utils.gettext ('sort by: '), False)
        for slink in self._slinks:
            if slink[2] == 1:
                p (fd, '<a href="javascript:slinkmenu(\'%s\')" class="slinkcur">%s ▴</a>',
                   (slinkclass, slink[1]), False)
                break
            elif slink[2] == -1:
                p (fd, '<a href="javascript:slinkmenu(\'%s\')" class="slinkcur">%s ▾</a>',
                   (slinkclass, slink[1]), False)
                break
        p (fd, '<div class="slinkmenu" id="slinkmenu__%s">', slinkclass)
        for slink in self._slinks:
            p (fd, '<div class="slinkitem">', None, False)
            p (fd, '<span class="slinklabel" id="slink__%s__%s__%s">%s</span>:',
               (slinktag, slinkclass, slink[0], slink[1]))
            if slink[2] == 1:
                p (fd, '<span class="slink" id="slink__%s__%s__%s__1">▴</span>',
                   (slinktag, slinkclass, slink[0]))
            else:
                p (fd, ('<a class="slink" id="slink__%s__%s__%s__1"'
                        ' href="javascript:sort(\'%s\', \'%s\', \'%s\', 1)">▴</a>'),
                   (slinktag, slinkclass, slink[0],
                    slinktag, slinkclass, slink[0]))
            if slink[2] == -1:
                p (fd, '<span class="slink" id="slink__%s__%s__%s__-1">▾</span>',
                   (slinktag, slinkclass, slink[0]))
            else:
               p (fd, ('<a class="slink" id="slink__%s__%s__%s__-1"'
                        ' href="javascript:sort(\'%s\', \'%s\', \'%s\', -1)">▾</a>'),
                   (slinktag, slinkclass, slink[0],
                    slinktag, slinkclass, slink[0]))
            p (fd, '</div>')
        p (fd, '</div></span></div>')


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

    def add_link_box (self, *args, **kw):
        """Add a link box."""
        lbox = LinkBox (*args, **kw)
        self._boxes.append (lbox)
        return lbox

    def set_columns (self, columns):
        """Set the number of columns."""
        self._columns = columns

    def output (self, fd=None):
        """Output the HTML."""
        if self._columns > 1:
            p (fd, '<table class="cols"><tr>')
            p (fd, '<td class="col col-first">')
            width = str(100 // self._columns)
            for box, col, pos in pulse.utils.split (self._boxes, self._columns):
                if pos == 0:
                    if col > 0:
                        p (fd, '</td><td class="col" style="width: ' + width + '%">')
                else:
                    p (fd, '<div class="pad">')
                p (fd, box)
                if pos > 0:
                    p (fd, '</div>')
            p (fd, '</td></tr></table>')
        else:
            for i in range(len(self._boxes)):
                box = self._boxes[i]
                if i != 0:
                    p (fd, '<div class="pad">')
                p (fd, box)
                if i != 0:
                    p (fd, '</div>')


class HttpComponent (Component):
    """
    Component for widgets that output HTTP headers.

    Widgets using this component are generally top-level that are not added to
    any other widgets.  The output method will generate the HTTP headers, if the
    http paramater has not been set to False.

    FIXME: document **kw
    """

    def __init__ (self, **kw):
        super (HttpComponent, self).__init__ (**kw)
        self._http = kw.get ('http', True)
        self._status = kw.get ('status', 200)

    def output (self, fd=None):
        """Output the HTML."""
        if self._http == True:
            if self._status == 404:
                p (fd, 'Status: 404 Not found')
            elif self._status == 500:
                p (fd, 'Status: 500 Internal server error')
            p (fd, 'Content-type: text/html; charset=utf-8\n')
        


################################################################################
## Pages

class Page (Widget, HttpComponent, ContentComponent):
    """
    Complete web page.

    The output method creates all the standard HTML for the top and bottom
    of the page, and call output_page_content in between.  Subclasses should
    override output_page_content.

    Keyword arguments:
    title -- The title of the page.
    icon  -- The URL of an icon for the page.
    """

    def __init__ (self, **kw):
        super (Page, self).__init__ (**kw)
        self._title = kw.get ('title')
        self._icon = kw.get ('icon')
        self._screenshot_file = None

    def set_title (self, title):
        """Set the title of the page."""
        self._title = title

    def set_icon (self, icon):
        """Set the URL of an icon for the page."""
        self._icon = icon

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
            of = db.OutputFile.objects.get (id=screen)
            self._screenshot_file = of
        except:
            pass

    def output (self, fd=None):
        """Output the HTML."""
        HttpComponent.output (self, fd=fd)
        p (fd, ('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN"'
                ' "http://www.w3.org/TR/html4/strict.dtd">'))
        p (fd, '<html><head>')
        p (fd, '  <title>%s</title>', self._title)
        p (fd, '  <meta http-equiv="Content-type" content="text/html; charset=utf-8">')
        p (fd, '  <link rel="stylesheet" href="%spulse.css">', pulse.config.data_root)
        p (fd, '  <script language="javascript" type="text/javascript" src="%sjquery.js"></script>',
           pulse.config.data_root)
        p (fd, '  <script language="javascript" type="text/javascript" src="%spulse.js"></script>',
           pulse.config.data_root)
        p (fd, '</head><body>')
        p (fd, '<ul id="general">')
        p (fd, ('  <li id="siteaction-gnome_home" class="home">'
                '<a href="http://www.gnome.org/">Home</a></li>'))
        p (fd, ('  <li id="siteaction-gnome_news">'
                '<a href="http://news.gnome.org">News</a></li>'))
        p (fd, ('  <li id="siteaction-gnome_projects">'
                '<a href="http://www.gnome.org/projects/">Projects</a></li>'))
        p (fd, ('  <li id="siteaction-gnome_art">'
                '<a href="http://art.gnome.org">Art</a></li>'))
        p (fd, ('  <li id="siteaction-gnome_support">'
                '<a href="http://www.gnome.org/support/">Support</a></li>'))
        p (fd, ('  <li id="siteaction-gnome_development">'
                '<a href="http://developer.gnome.org">Development</a></li>'))
        p (fd, ('  <li id="siteaction-gnome_community">'
                '<a href="http://www.gnome.org/community/">Community</a></li>'))
        p (fd, '</ul>')
        p (fd, '<div id="header"><a href="%s"><img src="%s" alt="Pulse"></a></div>',
           (pulse.config.web_root, pulse.config.data_root + 'pulse-logo.png'))
        p (fd, '<h1>')
        if self._icon != None:
            p (fd, '<img class="icon" src="%s" alt="%s"> ', (self._icon, self._title), False)
        p (fd, None, self._title)
        p (fd, '</h1>')
        p (fd, '<div id="body">')
        if self._screenshot_file != None:
            p (fd, '<div class="screenshot">', None, False)
            url = self._screenshot_file.get_pulse_url ()
            p (fd, '<a href="%s" class="zoom">', self._screenshot_file.pulse_url, False)
            p (fd, '<img src="%s" width="%i" height="%i">',
               (self._screenshot_file.get_pulse_url ('thumbs'),
                self._screenshot_file.data['thumb_width'],
                self._screenshot_file.data['thumb_height']))
            p (fd, '</a></div>')
        
        self.output_page_content (fd=fd)
        p (fd, '</div></body></html>')
        
    def output_page_content (self, fd=None):
        """Output the contents of the page."""
        ContentComponent.output (self, fd=fd)


class Fragment (Widget, HttpComponent, ContentComponent):
    """
    Fragment of a web page.

    Unlike Page, Fragment will not output any boilerplate HTML.  Instead, it
    only outputs the HTTP headers and the added content.  This is generally
    used for AJAX content.
    """

    def __init__ (self, **kw):
        super (Fragment, self).__init__ (**kw)

    def output (self, fd=None):
        """Output the HTML."""
        HttpComponent.output (self, fd=fd)
        ContentComponent.output (self, fd=fd)


class RecordPage (Page, SublinksComponent, FactsComponent):
    """
    Convenience wrapper for Page for Records.

    This convenience class knows how to extract basic information from Records
    and insert it into the page.
    """

    def __init__ (self, record, **kw):
        kw.setdefault ('title', record.title)
        kw.setdefault ('icon', record.icon_url)
        super (RecordPage, self).__init__ (**kw)

    def output_page_content (self, fd=None):
        """Output the contents of the page."""
        SublinksComponent.output (self, fd=fd)
        FactsComponent.output (self, fd=fd)
        Page.output_page_content (self, fd=fd)


class PageNotFound (Page):
    """
    A page for when an object is not found.

    FIXME: document **kw
    """

    def __init__ (self, message, **kw):
        kw.setdefault ('title', pulse.utils.gettext('Page Not Found'))
        super (PageNotFound, self).__init__ (**kw)
        self._pages = kw.get ('pages', [])
        self._message = message

    def output_page_content (self, fd=None):
        """Output the contents of the page."""
        p (fd, '<div class="notfound">')
        p (fd, '<div class="message">%s</div>', self._message)
        if len(self._pages) > 0:
            p (fd, '<div class="pages">%s',
               pulse.utils.gettext ('The following pages might interest you:'))
            p (fd, '<ul>')
            for page in self._pages:
                p (fd, '<li><a href="%s%s">%s</a></li>' %
                   (pulse.config.web_root, page[0], page[1]))
            p (fd, '</ul></div>')
        p (fd, '</div>')
        Page.output_page_content (self, fd=fd)


class PageError (Page):
    """
    A page for when an error has occurred.

    FIXME: document **kw
    """

    def __init__ (self, message, **kw):
        kw.setdefault ('title', pulse.utils.gettext('Bad Monkeys'))
        super (PageError, self).__init__ (**kw)
        self._pages = kw.get ('pages', [])
        self._message = message
    
    def output_page_content (self, fd=None):
        """Output the contents of the page."""
        p (fd, '<div class="servererror">')
        p (fd, '<div class="message">%s</div>', self._message)
        p (fd, '</div>')
        ContentComponent.output (self, fd=fd)


################################################################################
## Boxes

class AjaxBox (Widget):
    """
    A box that loads its contents over AJAX.
    """
    def __init__ (self, url, **kw):
        super (AjaxBox, self).__init__ (**kw)
        self._url = url

    def output (self, fd=None):
        """Output the HTML."""
        p (fd, '<div class="ajax"><img src="%sprocess00.png"><a href="%s">%s</a></div>',
           (pulse.config.data_root, self._url, pulse.utils.gettext ('Loading')) )


class InfoBox (Widget, ContentComponent, LinkBoxesComponent):
    """
    A box containing information.

    An info box is a framed and titled box that contains various related bits
    of information.  Most pages are constructed primarily of info boxes.
    """
    def __init__ (self, title, **kw):
        super (InfoBox, self).__init__ (**kw)
        self._title = title

    def output (self, fd=None):
        """Output the HTML."""
        p (fd, '<div class="info">')
        p (fd, '<div class="info-title">', None, False)
        p (fd, '<span><img class="info-img" src="%sexpander-open.png"></span>',
           (pulse.config.data_root), False)
        p (fd, '%s</div>', self._title)
        p (fd, '<div class="info-content"><div>')
        ContentComponent.output (self, fd=fd)
        LinkBoxesComponent.output (self, fd=fd)
        p (fd, '</div></div></div>')


class ContainerBox (Widget, SortableComponent, ContentComponent, LinkBoxesComponent):
    """
    An all-purpose container box.

    A container box wraps arbitrary content with various useful things.
    If a title has been set, a container box will allow the box to be
    expanded and collapsed.  If sort links have been added, a sort link
    bar will be output.

    FIXME: document **kw
    """

    def __init__ (self, **kw):
        self._id = kw.get('id', None)
        self._title = kw.get('title', None)
        if self._id != None:
            kw.setdefault ('sortable_class', self._id)
        super (ContainerBox, self).__init__ (**kw)

    def add_link_box (self, *args, **kw):
        """
        Add a link box.

        This extends the method from LinkBoxesComponent to call add_class
        on the added link box, allowing the link boxes to be sorted.
        """
        lbox = LinkBoxesComponent.add_link_box (self, *args, **kw)
        scls = self.get_sortable_class()
        if scls != None:
            lbox.add_class (scls)
        return lbox

    def set_id (self, id_):
        """Set the id of the container."""
        if self.get_sortable_class() == None:
            self.set_sortable_class (id_)
        self._id = id_

    def set_title (self, title):
        """Set the title of the container."""
        self._title = title

    def output (self, fd=None):
        """Output the HTML."""
        slinks = len(self.get_sort_links())
        if self._title != None or slinks > 0:
            p (fd, '<div>')
            if self._title != None:
                p (fd, '<table class="cont"><tr>')
                p (fd, '<td class="contexp">&#9662;</td>')
                p (fd, '<td class="cont-title">', None, False)
            if self._title != None and slinks > 0:
                p (fd, '<table><tr><td>')
            if self._title != None:
                p (fd, '<span class="contexp">%s</span>', (self._title), False)
            if self._title != None and slinks > 0:
                p (fd, '</td><td class="cont-slinks">')
            if slinks > 0:
                if self.get_sortable_class() == None:
                    self.set_sortable_class (self._id)
                SortableComponent.output (self, fd=fd)
            if self._title != None and slinks > 0:
                p (fd, '</td></tr></table>')
            if self._title != None:
                p (fd, '</td></tr>')
                p (fd, '<tr><td></td><td class="cont-content">', None, False)
            p (fd, '<div class="cont-content">')
        ContentComponent.output (self, fd=fd)
        LinkBoxesComponent.output (self, fd=fd)
        p (fd, '</div>')
        if self._title != None:
            p (fd, '</td></tr></table>')
        p (fd, '</div>')


class Calendar (Widget):
    def __init__ (self, **kw):
        super (Calendar, self).__init__ (**kw)
        self._events = []

    def add_event (self, start, end, summary, desc):
        self._events.append ((start, end, summary, desc))

    def output (self, fd=None):
        p (fd, '<div class="cal">')
        p (fd, '<table class="cal">')
        p (fd, '<tr class="calnav">')
        p (fd, '<td class="calprev">&#9666;</td>')
        p (fd, '<td class="calnav" colspan="5">', None, False)
        p (fd, '<span class="calmonth"></span> <span class="calyear"></span></td>')
        p (fd, '<td class="calnext">&#9656;</td>')
        p (fd, '</tr>')
        p (fd, '<tr class="calhead">', None, False)
        for day in ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'):
            p (fd, '<td>%s</td>', day, False)
        p (fd, '</tr>')
        for i in range (6):
            p (fd, '<tr class="calweek">', None, False)
            for j in range (7):
                p (fd, '<td class="calday"></td>', None, False)
            p (fd, '</tr>')
        p (fd, '</table>')
        p (fd, '<dl class="calevents">')
        for event in self._events:
            p (fd, '<dt class="calevent">', None, False)
            p (fd, '<span class="caldtstart">%s</span> ', event[0].strftime('%Y-%m-%d'), False)
            p (fd, '<span class="calsummary">%s</span>', event[2], False)
            p (fd, '</dt>')
            p (fd, '<dd class="calevent">%s</dd>', event[3])
        p (fd, '</dl>')
        p (fd, '</div>')

class LinkBox (Widget, FactsComponent, ContentComponent):
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
        if isinstance (args[0], db.PulseRecord):
            if args[0].linkable:
                self._url = args[0].pulse_url
            self._title = args[0].title
            self._desc = args[0].localized_desc
            self._icon = args[0].icon_url
            if isinstance (args[0], db.Entity):
                self._icon_size = 36
        elif len(args) > 1:
            self._url = args[0]
            self._title = args[1]
        else:
            self._href = self._text = args[0]
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

    def output (self, fd=None):
        """Output the HTML."""
        cls = ' '.join(['lbox'] + self._classes)
        p (fd, '<table class="%s"><tr>', cls)
        if self._show_icon:
            if self._icon_size != None:
                p (fd, '<td class="lbox-icon" style="width: %ipx">', self._icon_size, False)
            else:
                p (fd, '<td class="lbox-icon">', None, False)
            if self._icon != None:
                p (fd, '<img class="icon" src="%s" alt="%s">', (self._icon, self._title), False)
            p (fd, '</td>')
        p (fd, '<td class="lbox-text">')
        if self._heading == True:
            p (fd, '<div class="lbox-heading">')
        else:
            p (fd, '<div class="lbox-title">')
        if self._url != None:
            p (fd, '<a href="%s"><span class="title">%s</span></a>', (self._url, self._title))
        else:
            p (fd, '<span class="title">%s</span>', self._title)
        if len(self._badges) > 0:
            p (fd, ' ')
            for badge in self._badges:
                p (fd, '<img src="%sbadge-%s-16.png" width="16" height="16" alt="%s">',
                   (pulse.config.data_root, badge, badge))
        p (fd, '</div>')
        if self._desc != None:
            p (fd, '<div class="lbox-desc desc">')
            p (fd, EllipsizedLabel (self._desc, 130))
            p (fd, '</div>')
        FactsComponent.output (self, fd=fd)
        ContentComponent.output (self, fd=fd)
        p (fd, '</td>')
        if len(self._graphs) > 0:
            p (fd, '<td class="lbox-graph">')
            for graph in self._graphs:
                pulse.html.Graph (graph[0], width=graph[1], height=graph[2]).output(fd=fd)
            p (fd, '</td>')
        p (fd, '</tr></table>')
        

class ColumnBox (Widget):
    def __init__ (self, num, **kw):
        super (ColumnBox, self).__init__ (**kw)
        self._columns = [[] for i in range(num)]

    def add_to_column (self, index, content):
        self._columns[index].append (content)
        return content

    def output (self, fd=None):
        """Output the HTML."""
        p (fd, '<table class="cols"><tr>', None)
        width = str (100 / len(self._columns))
        for i in range(len(self._columns)):
            column = self._columns[i]
            if i == 0:
                p (fd, '<td class="col col-first">')
            else:
                p (fd, '<td class="col" style="width: ' + width + '%">')
            for item in column:
                p (fd, None, item)
            p (fd, '</td>')
        p (fd, '</tr></table>')


class GridBox (Widget):
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

    def output (self, fd=None):
        """Output the HTML."""
        if len (self._rows) == 0:
            return
        cls = ' '.join(['grid'] + self._classes)
        p (fd, '<table class="%s">', cls)
        cols = max ([len(x['data']) for x in self._rows])
        for row in self._rows:
            cls = row.get('classes', None)
            if cls != None:
                p (fd, '<tr class="%s">', ' '.join(cls))
            else:
                p (fd, '<tr>')
            for i in range (cols):
                if i == 0:
                    p (fd, '<td class="grid-td-first">')
                else:
                    p (fd, '<td class="grid-td">')
                if i < len (row['data']):
                    p (fd, None, row['data'][i])
                p (fd, '</td>')
            p (fd, '</tr>')
        p (fd, '</table>')


class PaddingBox (Widget, ContentComponent):
    """A box which puts vertical padding between its children."""
    def __init__ (self, **kw):
        super (PaddingBox, self).__init__ (**kw)

    def output (self, fd=None):
        """Output the HTML."""
        content = self.get_content()
        for i in range(len(content)):
            if i == 0:
                p (fd, None, content[i])
            else:
                p (fd, '<div class="pad">')
                p (fd, None, content[i])
                p (fd, '</div>')


class AdmonBox (Widget):
    error = "error"
    information = "information"
    warning = "warning"
    
    def __init__ (self, kind, title, **kw):
        super (AdmonBox, self).__init__ (**kw)
        self._kind = kind
        self._title = title
        self._tag = kw.get('tag', 'div')
        self._classes = []

    def add_class (self, class_):
        self._classes.append (class_)

    def output (self, fd=None):
        """Output the HTML."""
        class_ = ' '.join(['admon'] + self._classes)
        p (fd, '<%s class="admon-%s %s">', (self._tag, self._kind, class_))
        p (fd, '<img src="%sadmon-%s-16.png" width="16" height="16">',
           (pulse.config.data_root, self._kind))
        p (fd, None, self._title)
        p (fd, '</%s>', self._tag)


class TabbedBox (Widget, ContentComponent):
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

    def output (self, fd=None):
        """Output the HTML."""
        p (fd, '<div class="tabbed">')
        p (fd, '<div class="tabbed-tabs">')
        for url, title in self._tabs:
            title = esc(title).replace(' ', '&nbsp;')
            if url == True:
                p (fd, '<span class="tabbed-tab-active">' + title + '</span>')
            else:
                p (fd, '<span class="tabbed-tab-link"><a href="%s">' + title + '</a></span>', url)
        p (fd, '</div>')
        p (fd, '<div class="tabbed-content">')
        ContentComponent.output (self, fd=fd)
        p (fd, '</div>')


class TranslationForm (Widget):
    def __init__ (self, **kw):
        super (TranslationForm, self).__init__ (**kw)
        self._msgs = []

    class Entry (Widget):
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

        def output (self, fd=None):
            if self._trans == None:
                p (fd, '<div class="trentry trnotrans">')
            else:
                p (fd, '<div class="trentry">')
            p (fd, '<div class="trsource">')
            lines = self._msg.split('\\n')
            p (fd, None, lines[0])
            for line in lines[1:]:
                p (fd, '<br>')
                p (fd, None, line)
            p (fd, '</div>')
            if self._plural != None:
                p (fd, '<div class="trsource">')
                lines = self._plural.split('\\n')
                p (fd, None, lines[0])
                for line in lines[1:]:
                    p (fd, '<br>')
                    p (fd, None, line)
                p (fd, '</div>')
            if self._comment != None:
                lines = self._comment.split('\n')
                if lines[-1] == '':
                    lines = lines[:-1]
                if len(lines) > 0:
                    p (fd, '<div class="trcomment">')
                    p (fd, '# %s', lines[0])
                    for line in lines[1:]:
                        p (fd, '<br>')
                        p (fd, '# %s', line)
                    p (fd, '</div>')
            if self._trans != None:
                for trans in self._trans:
                    p (fd, '<div class="trtrans">')
                    lines = trans.split('\\n')
                    p (fd, None, lines[0])
                    for line in lines[1:]:
                        p (fd, '<br>')
                        p (fd, None, line)
                    p (fd, '</div>')
            p (fd, '</div>')

    def add_entry (self, msg):
        entry = TranslationForm.Entry (msg)
        self._msgs.append (entry)
        return entry

    def output (self, fd=None):
        p (fd, '<div class="trform">')
        for msg in self._msgs:
            msg.output (fd=fd)
        p (fd, '</div>')


################################################################################
## Lists

class DefinitionList (Widget):
    def __init__ (self, **kw):
        super (DefinitionList, self).__init__ (**kw)
        self._id = kw.get('id', None)
        self._classname = kw.get('classname', None)
        self._all = []

    def add_term (self, term, classname=None):
        self._all.append (('dt', term, classname))

    def add_entry (self, entry, classname=None):
        self._all.append (('dd', entry, classname))

    def add_divider (self):
        self._all.append (('dt', None, 'hr'))
        
    def output (self, fd=None):
        """Output the HTML."""
        p (fd, '<dl', None, False)
        if self._id != None:
            p (fd, ' id="%s"', self._id, False)
        if self._classname != None:
            p (fd, ' class="%s"', self._classname, False)
        p (fd, '>')
        for tag, content, cname in self._all:
            if cname != None:
                p (fd, '<%s class="%%s">' % tag, cname, False)
            else:
                p (fd, '<%s>' % tag, None, False)
            if content:
                p (fd, None, content, False)
            else:
                p (fd, '<hr>', None, False)
            p (fd, '</%s>' % tag)
        p (fd, '</dl>')


class FactList (DefinitionList):
    def __init__ (self, **kw):
        kw.setdefault ('classname', 'facts')
        super (FactList, self).__init__ (**kw)


class BulletList (Widget):
    def __init__ (self, **kw):
        super (BulletList, self).__init__ (**kw)
        self._id = kw.get ('id', None)
        self._items = []

    def add_item (self, item, classname=None):
        self._items.append ((item, classname))

    def output (self, fd=None):
        """Output the HTML."""
        if self._id != None:
            p (fd, '<ul id="%s">', self._id)
        else:
            p (fd, '<ul>')
        for item, cname in self._items:
            if cname != None:
                p (fd, '<li class="%s">', cname, False)
            else:
                p (fd, '<li>', None, False)
            p (fd, None, item, False)
            p (fd, '</li>')
        p (fd, '</ul>')
                


################################################################################
## Other...

class Rule (Widget):
    def output (self, fd=None):
        """Output the HTML."""
        p (fd, '<div class="hr"><hr></div>')


class Graph (Widget):
    """
    A generated graph with optional comments.
    """

    _count = 0

    def __init__ (self, url, **kw):
        super (Graph, self).__init__ (**kw)
        self._url = url
        self._count = kw.get('count', None)
        self._num = kw.get('num', 0)
        self._links = kw.get('links', False)
        self._width = kw.get('width', None)
        self._height = kw.get('height', None)
        self._map_only = kw.get('map_only', False)
        self._comments = []

    def add_comment (self, coords, comment, href=None):
        """
        Add a comment to the graph.

        Comments are displayed as tooltips when the user hovers over the
        area defined by coords.  If the href argument is not None, that
        area will be a link to href.
        """
        self._comments.append ((coords, comment, href))

    def output (self, fd=None):
        """Output the HTML."""
        if self._count == None:
            Graph._count += 1
            self._count = Graph._count
        if not self._map_only:
            if self._links:
                p (fd, '<table class="graph"><tr><td colspan="2">', None, False)
            p (fd, '<div class="graph" id="graph-%i">', self._count, False)
        if len(self._comments) == 0:
            if not self._map_only:
                p (fd, '<img src="%s"', self._url, False)
                if self._width != None:
                    p (fd, ' width="%i"', self._width, False)
                if self._height != None:
                    p (fd, ' height="%i"', self._height, False)
                p (fd, '>', None, False)
        else:
            if not self._map_only:
                p (fd, '<img src="%s" usemap="#graphmap%i-%i" ismap',
                   (self._url, self._count, self._num), False)
                if self._width != None:
                    p (fd, ' width="i"', self._width, False)
                if self._height != None:
                    p (fd, ' height="i"', self._height, False)
                p (fd, '>', None, False)
            p (fd, '<div class="comments">', None, False)
            p (fd, '<map name="graphmap%i-%i">', (self._count, self._num))
            i = 0
            for comment in self._comments:
                i += 1
                p (fd, '<area shape="rect" coords="%s"',
                   ','.join(map(str, comment[0])), False)
                p (fd, ' onmouseover="javascript:comment(%i, %i, %i, %i)"',
                   (self._count, self._num, i, comment[0][0]), False)
                p (fd, ' onmouseout="javascript:comment(%i, %i, %i)"',
                   (self._count, self._num, i), False)
                if comment[2] != None:
                    p (fd, ' href="%s"', comment[2])
                p (fd, '>')
            p (fd, '</map>')
            i = 0
            for comment in self._comments:
                i += 1
                p (fd, '<div class="comment" id="comment-%i-%i-%i">%s</div>',
                   (self._count, self._num, i, comment[1]))
            p (fd, '</div>', None, False)
        if not self._map_only:
            p (fd, '</div>', None, False)
            if self._links:
                p (fd, '</td></tr><tr>')
                p (fd, '<td class="graphprev">', None, False)
                p (fd, '<a class="graphprev" id="graphprev-%i" href="javascript:slide(%i, -1)"',
                   (self._count, self._count), False)
                p (fd, '<img src="%sgo-prev.png" height="12" width="12"></a>',
                   pulse.config.data_root, False)
                p (fd, '</td><td class="graphnext">', None, False)
                p (fd, '<a class="graphnext" id="graphnext-%i" href="javascript:slide(%i, 1)">',
                   (self._count, self._count), False)
                p (fd, '<img src="%sgo-next.png" height="12" width="12"></a>',
                   pulse.config.data_root, False)
                p (fd, '</td></tr></table>')

    @classmethod
    def activity_graph (cls, of, url, **kw):
        """A convenience constructor to make an activity graph from an OutputFile."""
        kw.setdefault ('links', True)
        kw.setdefault ('width', of.data.get('width'))
        kw.setdefault ('height', of.data.get('height'))
        graph = cls (of.pulse_url, **kw)
        thisweek = pulse.utils.weeknum (datetime.datetime.now())
        for (coords, tot, weeknum) in of.data.get ('coords', []):
            ago = thisweek - weeknum
            if ago == 0:
                cmt = pulse.utils.gettext ('this week: %i commits') % tot
            elif ago == 1:
                cmt = pulse.utils.gettext ('last week: %i commits') % tot
            else:
                cmt = pulse.utils.gettext ('%i weeks ago: %i commits') % (ago, tot)
            jslink = 'javascript:replace(\'commits\', '
            jslink += '\'%s?ajax=commits&weeknum=%i\')' % (url, weeknum)
            graph.add_comment (coords, cmt, jslink)
        return graph


class EllipsizedLabel (Widget):
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

    def output (self, fd=None):
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
                p (fd, None, self._label)
            else:
                p (fd, None, self._label[:i])
                p (fd, '<span class="elliptxt">%s</span>', (self._label[i+1:]))
        else:
            p (fd, None, self._label)


class MenuLink (Widget):
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
        if isinstance (args[0], Widget):
            self._links.append (args[0])
        else:
            self._links.append (Link(*args))

    def set_menu_url (self, url):
        self._menu_url = url

    def output (self, fd=None):
        """Output the HTML."""
        MenuLink._count += 1
        if self._menu_only != True:
            p (fd, '<a class="mlink" id="mlink%s" href="javascript:mlink(\'%s\')">%s</a>',
               (self._id, self._id, self._txt or self._id))
        if self._menu_url != None:
            p (fd, '<div class="mstub" id="mcont%s">%s</div>',
               (self._id, self._menu_url))
        else:
            p (fd, '<div class="mcont" id="mcont%s">', self._id)
            p (fd, '<div class="mcont-cont">')
            for link in self._links:
                p (fd, '<div>', None, False)
                p (fd, link, None, False)
                p (fd, '</div>')
            p (fd, '</div></div>')


class PopupLink (Widget):
    _count = 0

    def __init__ (self, short, full, **kw):
        super (PopupLink, self).__init__ (**kw)
        self._short = short
        self._full = full
        self._links = []

    def add_link (self, *args):
        if isinstance (args[0], Widget):
            self._links.append (args[0])
        else:
            self._links.append (Link(*args))

    def output (self, fd=None):
        """Output the HTML."""
        PopupLink._count += 1
        id = md5.md5(self._full).hexdigest()[:6] + str(PopupLink._count)
        p (fd, '<a class="plink" id="plink%s" href="javascript:plink(\'%s\')">',
           (id, id), False)
        p (fd, None, self._short, False)
        p (fd, '</a>')
        p (fd, '<div class="pcont" id="pcont%s">', id)
        if isinstance (self._full, basestring):
            while len(self._full) > 0 and self._full[-1] == '\n': self._full = self._full[:-1]
        p (fd, '<pre class="pcont-content">', None, False)
        p (fd, None, self._full)
        p (fd, '</pre>')
        if self._links != []:
            p (fd, '<div class="pcont-links">', None, False)
            for i in range(len(self._links)):
                if i != 0:
                    p (fd, BULLET)
                p (fd, self._links[i])
            p (fd, '</div>')
        p (fd, '</div>')

    @classmethod
    def from_revision (cls, rev, **kw):
        comment = rev.comment
        if comment.strip() == '':
            lnk = cls (AdmonBox (AdmonBox.warning, pulse.utils.gettext ('No comment')),
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
            if len(line) > 40:
                i = 30
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
                mlink.set_menu_url (branch.pulse_url + '?ajax=revfiles&revid=' + str(rev.id))
                lnk.add_link (mlink)
                infourl = base + '?view=revision&revision=' + rev.revision
                lnk.add_link (infourl, pulse.utils.gettext ('info'))

        return lnk


class Span (Widget, ContentComponent):
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
        self._classes = []

    def set_divider (self, divider):
        """Set a divider to be placed between child elements."""
        self._divider = divider

    def add_class (self, class_):
        """Add an HTML class to the span."""
        self._classes.append (class_)

    def output (self, fd=None):
        """Output the HTML."""
        if len(self._classes) > 0:
            p (fd, '<span class="%s">', ' '.join(self._classes), False)
        else:
            p (fd, '<span>', None, False)
        content = self.get_content()
        for i in range(len(content)):
            if i != 0 and self._divider != None:
                p (fd, None, self._divider, False)
            p (fd, None, content[i], False)
        p (fd, '</span>')


class StatusSpan (Widget, ContentComponent):
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

    def output (self, fd=None):
        """Output the HTML."""
        p (fd, '<span class="status">%i</span>', self._status, False)
        ContentComponent.output (self, fd=fd)


class Div (Widget, ContentComponent):
    """
    A simple block.

    Any non-keyword arguments passed to the constructor are taken to
    be child content, and are automatically added with add_content.

    Keyword arguments:
    id -- An optional HTML id for the div tag.
    """

    def __init__ (self, *args, **kw):
        super (Div, self).__init__ (**kw)
        self._id = kw.get('id', None)
        for arg in args:
            self.add_content (arg)

    def output (self, fd=None):
        """Output the HTML."""
        if self._id != None:
            p (fd, '<div id="%s">', self._id)
        else:
            p (fd, '<div>')
        ContentComponent.output (self, fd=fd)
        p (fd, '</div>')


class Pre (Widget, ContentComponent):
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

    def output (self, fd=None):
        """Output the HTML."""
        if self._id != None:
            p (fd, '<pre id="%s">', self._id)
        else:
            p (fd, '<pre>')
        ContentComponent.output (self, fd=fd)
        p (fd, '</pre>')


class Link (Widget):
    """
    A link to another page.

    This widget constructs a link to another page.  The constructor
    can be called multiple ways.  If it is passed a PulseRecord, it
    automatically extracts the URL and title from that object.  If
    it is passed two strings, it considers them to be the URL and
    text of the link.  Otherwise, if it is passed a single string,
    it is used as both the URL and title.

    Keyword arguments:
    icon -- The name of an icon in Pulse to prefix the link text with.
    classname -- The value of the HTML class attribute.
    """

    def __init__ (self, *args, **kw):
        super (Link, self).__init__ (**kw)
        self._href = self._text = None
        if isinstance (args[0], db.PulseRecord):
            if args[0].linkable:
                self._href = args[0].pulse_url
            self._text = args[0].title
        elif len(args) > 1:
            self._href = args[0]
            self._text = args[1]
        else:
            self._href = self._text = args[0]
        self._icon = kw.get ('icon', None)
        self._classname = kw.get ('classname', None)
    
    def output (self, fd=None):
        """Output the HTML."""
        if self._href != None:
            if self._classname != None:
                p (fd, '<a href="%s" class="%s">', (self._href, self._classname), False)
            else:
                p (fd, '<a href="%s">', self._href, False)
        if self._icon != None:
            p (fd, '<img src="%s%s-16.png" height="16" width="16"> ',
               (pulse.config.data_root, self._icon),
               False)
        p (fd, None, self._text, False)
        if (self._href != None):
            p (fd, '</a>')


################################################################################
## Utility Functions

def p (fd, obj, arg=None, newline=True):
    """
    Generalized thing printer.

    This function is used to print widgets, components, and plain old strings
    in a consistent manner that avoids littering the rest of the code with a
    bunch of conditionals.

    A widget or component can be printed by passing it in as the obj argument,
    or by passing None for obj and passing the object in as the arg argument.

    If obj is a string and arg is None, obj is simply printed.  If arg is not
    None, it is interpolated in, except all substituted values are escaped to
    be safe for HTML.  Note that obj itself is not escaped, since that is used
    to print the actual HTML.  If obj is None, it is treated as "%s".

    String printing can suppress a trailing newline by passing in False for
    the newline argument.
    """
    if fd == None:
        fd = sys.stdout
    if isinstance (obj, Widget) or isinstance (obj, Component):
        obj.output (fd=fd)
    elif obj == None and (isinstance (arg, Widget) or isinstance (arg, Component)):
        arg.output (fd=fd)
    else:
        if obj == None:
            outstr = esc(arg)
        elif arg == None:
            outstr = obj
        else:
            outstr = obj % esc(arg)
        if newline:
            outstr += '\n'
        try:
            fd.write(outstr.encode('utf-8'))
        except:
            fd.write(outstr)

def esc (obj):
    """
    Make some object safe for HTML output.

    This function works on everything you can put on the right-hand side of
    an interpolation.  Strings are simply escaped, tuples have their elements
    escaped, and dictionaries are wrapped with escdict.
    """
    if isinstance (obj, basestring):
        return cgi.escape (obj, True)
    elif isinstance (obj, tuple):
        return tuple (map (esc, obj))
    elif isinstance (obj, dict):
        return escdict (obj)
    else:
        return obj

class escdict (dict):
    """
    A dictionary wrapper that HTML escaped its values.
    """
    def __init__ (self, *args):
        dict.__init__ (self, *args)

    def __getitem__ (self, key):
        """Get the value for key, HTML escaped."""
        return esc (dict.__getitem__ (self, key))
