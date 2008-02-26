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
    def __init__ (self, **kw):
        super (Widget, self).__init__ (**kw)
    def output (self, fd=sys.stdout):
        pass

class Component (object):
    def __init__ (self, **kw):
        super (Component, self).__init__ (**kw)
    def output (self, fd=sys.stdout):
        pass


################################################################################
## Components

class ContentComponent (Component):
    """
    A simple component for widgets that have generic content.  The output
    method will call output on each of the added widgets.  Some widgets
    may use this component only for the add_content method, and control
    how the added widgets are output by mapping over get_content.
    """
    def __init__ (self, **kw):
        super (ContentComponent, self).__init__ (**kw)
        self._content = []

    def add_content (self, content):
        self._content.append (content)

    def get_content (self):
        return self._content

    def output (self, fd=sys.stdout):
        for s in self._content:
            p (fd, None, s)


class SublinksComponent (Component):
    """
    A component for widgets that contain sublinks.  Sublinks are a list of
    links found under the title of a widget.  They may provide alternate
    pages or a heirarchy of parent pages, depending on context.  The ouput
    method will create the sublinks.
    """
    def __init__ (self, **kw):
        super (SublinksComponent, self).__init__ (**kw)
        self._sublinks = []
        self._divider = kw.get('divider', BULLET)

    def add_sublink (self, href, title):
        self._sublinks.append ((href, title))

    def set_sublinks_divider (self, div):
        self._divider = div

    def output (self, fd=sys.stdout):
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
    A component for widgets that contain fact tables.  Fact tables are
    key-value tables providing more information about whatever thing
    the widget is showing.  The output method will create the table of
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

    def output (self, fd=sys.stdout):
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
                def factout (f):
                    if isinstance (f, basestring) or isinstance (f, Widget) or isinstance (f, Component):
                        p (fd, None, f, False)
                    elif isinstance (f, db.PulseRecord):
                        p (fd, Link(f))
                    elif hasattr (f, '__getitem__'):
                        for ff in f:
                            p (fd, '<div>', None, False)
                            factout (ff)
                            p (fd, '</div>')
                factout (fact['content'])
                p (fd, '</td></tr>')
        p (fd, '</table>')


class SortableComponent (Component):
    """
    A component for widgets that have sortable content.  The output method
    will create the link bar for sorting the content.
    """
    def __init__ (self, *args, **kw):
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

    def add_sort_link (self, key, txt, on=True):
        self._slinks.append ((key, txt, on))

    def get_sort_links (self):
        return self._slinks

    def output (self, fd=sys.stdout):
        slinktag = self._slinktag or 'table'
        slinkclass = self._slinkclass or 'lbox'
        p (fd, '<div class="slinks"><span class="slinks" id="slink-%s">', slinkclass)
        for i in range(len(self._slinks)):
            if i != 0: p (fd, u' • ')
            slink = self._slinks[i]
            if slink[2]:
                p (fd, '<a class="slink" id="slink-%s-%s-%s" href="javascript:sort(\'%s\', \'%s\', \'%s\')">%s</a>',
                   (slinktag, slinkclass, slink[0],
                    slinktag, slinkclass, slink[0], slink[1]),
                   False)
            else:
                p (fd, '<span class="slink" id="slink-%s-%s-%s">%s</span>',
                   (slinktag, slinkclass, slink[0], slink[1]),
                   False)
        p (fd, '</span></div>')


class LinkBoxesComponent (Component):
    """
    A component for widgets containing link boxes, possibly in multiple columns.
    """
    def __init__ (self, **kw):
        super (LinkBoxesComponent, self).__init__ (**kw)
        self._boxes = []
        self._columns = kw.get('columns', 1)

    def add_link_box (self, *args, **kw):
        lbox = LinkBox (*args, **kw)
        self._boxes.append (lbox)
        return lbox

    def set_columns (self, columns):
        self._columns = columns

    def output (self, fd=sys.stdout):
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
    A component for widgets that may need to output HTTP headers.  Widgets using
    this component are generally top-level that are not added to any other widgets.
    The output method will generate the HTTP headers, if the http paramater has
    not been set to False.
    """
    def __init__ (self, **kw):
        super (HttpComponent, self).__init__ (**kw)
        self._http = kw.get ('http', True)
        self._status = kw.get ('status', 200)

    def output (self, fd=sys.stdout):
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
    A complete web page.  The output method creates all the standard HTML for
    the top and bottom of the page, and call output_page_content in between.
    Subclasses should override output_page_content.
    """
    def __init__ (self, **kw):
        super (Page, self).__init__ (**kw)
        self._title = kw.get ('title')
        self._icon = kw.get ('icon')
        self._screenshot_file = None

    def set_title (self, title):
        self._title = title

    def set_icon (self, icon):
        self._icon = icon

    def add_screenshot (self, screenshot):
        try:
            # FIXME: i18n
            screen = screenshot['C']
            of = db.OutputFile.objects.get (id=screen)
            self._screenshot_file = of
        except:
            pass

    def output (self, fd=sys.stdout):
        HttpComponent.output (self, fd=fd)
        p (fd, '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">')
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
        p (fd, '  <li id="siteaction-gnome_home" class="home"><a href="http://www.gnome.org/">Home</a></li>')
        p (fd, '  <li id="siteaction-gnome_news"><a href="http://news.gnome.org">News</a></li>')
        p (fd, '  <li id="siteaction-gnome_projects"><a href="http://www.gnome.org/projects/">Projects</a></li>')
        p (fd, '  <li id="siteaction-gnome_art"><a href="http://art.gnome.org">Art</a></li>')
        p (fd, '  <li id="siteaction-gnome_support"><a href="http://www.gnome.org/support/">Support</a></li>')
        p (fd, '  <li id="siteaction-gnome_development"><a href="http://developer.gnome.org">Development</a></li>')
        p (fd, '  <li id="siteaction-gnome_community"><a href="http://www.gnome.org/community/">Community</a></li>')
        p (fd, '</ul>')
        p (fd, '<div id="header">')
        p (fd, '  <h1>Pulse</h1>')
        p (fd, '</div>')
        p (fd, '<div id="body">')
        p (fd, '<h1>')
        if self._icon != None:
            p (fd, '<img class="icon" src="%s" alt="%s"> ', (self._icon, self._title), False)
        p (fd, None, self._title)
        p (fd, '</h1>')
        if self._screenshot_file != None:
            p (fd, '<div class="screenshot">', None, False)
            url = self._screenshot_file.get_pulse_url ()
            p (fd, '<a href="%s">', self._screenshot_file.pulse_url, False)
            p (fd, '<img src="%s" width="%i" height="%i">',
               (self._screenshot_file.get_pulse_url ('thumbs'),
                self._screenshot_file.data['thumb_width'],
                self._screenshot_file.data['thumb_height']))
            p (fd, '</a></div>')
        
        self.output_page_content (fd=fd)
        p (fd, '</div></body></html>')
        
    def output_page_content (self, fd=sys.stdout):
        ContentComponent.output (self, fd=fd)


class Fragment (Widget, HttpComponent, ContentComponent):
    """
    A fragment of a web page.  Unlike Page, Fragment will not output any
    boilerplate HTML.  Instead, it only outputs the HTTP headers and the
    added content.  This is generally used for AJAX content.
    """
    def __init__ (self, **kw):
        super (Fragment, self).__init__ (**kw)

    def output (self, fd=sys.stdout):
        HttpComponent.output (self, fd=fd)
        ContentComponent.output (self, fd=fd)


class RecordPage (Page, SublinksComponent, FactsComponent):
    """
    A convenience wrapper for Page that knows how to extract information
    from database records.
    """
    def __init__ (self, record, **kw):
        kw.setdefault ('title', record.title)
        kw.setdefault ('icon', record.icon_url)
        super (RecordPage, self).__init__ (**kw)

    def output_page_content (self, fd=sys.stdout):
        SublinksComponent.output (self, fd=fd)
        FactsComponent.output (self, fd=fd)
        Page.output_page_content (self, fd=fd)


class PageNotFound (Page):
    """A 404 page."""
    def __init__ (self, message, **kw):
        kw.setdefault ('title', pulse.utils.gettext('Page Not Found'))
        super (PageNotFound, self).__init__ (**kw)
        self._pages = kw.get ('pages', [])
        self._message = message

    def output_page_content (self, fd=sys.stdout):
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
    """A 500 page."""
    def __init__ (self, message, **kw):
        kw.setdefault ('title', pulse.utils.gettext('Bad Monkeys'))
        super (PageError, self).__init__ (**kw)
        self._pages = kw.get ('pages', [])
        self._message = message
    
    def output_page_content (self, fd=sys.stdout):
        p (fd, '<div class="servererror">')
        p (fd, '<div class="message">%s</div>', self._message)
        p (fd, '</div>')
        ContentComponent.output (self, fd=fd)


################################################################################
## Boxes

class InfoBox (Widget, ContentComponent, LinkBoxesComponent):
    def __init__ (self, id, title, **kw):
        super (InfoBox, self).__init__ (**kw)
        self._id = id
        self._title = title

    def output (self, fd=sys.stdout):
        p (fd, '<div class="info" id="%s">', self._id)
        p (fd, '<div class="info-title">', None, False)
        p (fd, '<a href="javascript:info(\'%s\')">', self._id, False)
        p (fd, '<img id="infoimg-%s" class="info-img" src="%sexpander-open.png"></a>',
           (self._id, pulse.config.data_root), False)
        p (fd, '%s</div>', self._title)
        p (fd, '<div class="info-content"><div>')
        ContentComponent.output (self, fd=fd)
        LinkBoxesComponent.output (self, fd=fd)
        p (fd, '</div></div></div>')


class ContainerBox (Widget, SortableComponent, ContentComponent, LinkBoxesComponent):
    def __init__ (self, **kw):
        self._id = kw.get('id', None)
        self._title = kw.get('title', None)
        if self._id != None:
            kw.setdefault ('sortable_class', self._id)
        super (ContainerBox, self).__init__ (**kw)

    def add_link_box (self, *args, **kw):
        lbox = LinkBoxesComponent.add_link_box (self, *args, **kw)
        scls = self.get_sortable_class()
        if scls != None:
            lbox.add_class (scls)
        return lbox

    def set_id (self, id):
        if self.get_sortable_class() == None:
            self.set_sortable_class (id)
        self._id = id

    def set_title (self, title):
        self._title = title

    def output (self, fd=sys.stdout):
        if self._title != None or self._id != None:
            if self._id == None:
                self._id = md5.md5(self._title).hexdigest()
            p (fd, '<div class="cont" id="%s">', self._id)
        else:
            p (fd, '<div class="cont">')
        slinks = len(self.get_sort_links())
        if self._title != None or slinks > 0:
            if self._title != None:
                p (fd, '<div class="exp-title">', None, False)
            if self._title != None and slinks > 0:
                p (fd, '<table><tr><td>')
            if self._title != None:
                p (fd, '<a href="javascript:expander(\'%s\')">', self._id, False)
                p (fd, '<img id="img-%s" class="exp-img" src="%sexpander-open.png"> %s</a>',
                   (self._id, pulse.config.data_root, self._title))
            if self._title != None and slinks > 0:
                p (fd, '</td><td>')
            if slinks > 0:
                if self.get_sortable_class() == None:
                    self.set_sortable_class (self._id)
                SortableComponent.output (self, fd=fd)
            if self._title != None and slinks > 0:
                p (fd, '</td></tr></table>')
            if self._title != None:
                p (fd, '</div>')
                p (fd, '<div class="exp-content">')
        ContentComponent.output (self, fd=fd)
        LinkBoxesComponent.output (self, fd=fd)
        if self._title != None:
            p (fd, '</div>')
        p (fd, '</div>')


class LinkBox (Widget, FactsComponent, ContentComponent):
    def __init__ (self, *args, **kw):
        super (LinkBox, self).__init__ (**kw)
        self._url = self._title = self._icon = self._desc = None
        self._show_icon = True
        self._heading = False
        if isinstance (args[0], db.PulseRecord):
            if args[0].linkable:
                self._url = args[0].pulse_url
            self._title = args[0].title
            self._desc = args[0].localized_desc
            self._icon = args[0].icon_url
        elif len(args) > 1:
            self._url = args[0]
            self._title = args[1]
        else:
            self._href = self._text = args[0]
        self._badges = []
        self._classes = []
        self._graphs = []

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

    def add_graph (self, url):
        self._graphs.append (url)

    def output (self, fd=sys.stdout):
        cls = ' '.join(['lbox'] + self._classes)
        p (fd, '<table class="%s"><tr>', cls)
        if self._show_icon:
            p (fd, '<td class="lbox-icon">')
            if self._icon != None:
                p (fd, '<img class="icon" src="%s" alt="%s">', (self._icon, self._title))
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
            p (fd, '<div class="lbox-desc">')
            p (fd, EllipsizedLabel (self._desc, 130))
            p (fd, '</div>')
        FactsComponent.output (self, fd=fd)
        ContentComponent.output (self, fd=fd)
        p (fd, '</td>')
        if len(self._graphs) > 0:
            p (fd, '<td class="lbox-graph">')
            for graph in self._graphs:
                pulse.html.Graph(graph).output(fd=fd)
            p (fd, '</td>')
        p (fd, '</tr></table>')
        

class ColumnBox (Widget):
    def __init__ (self, num, **kw):
        super (ColumnBox, self).__init__ (**kw)
        self._columns = [[] for i in range(num)]

    def add_to_column (self, index, content):
        self._columns[index].append (content)
        return content

    def output (self, fd=sys.stdout):
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

    def output (self, fd=sys.stdout):
        if len (self._rows) == 0:
            return
        cls = ' '.join(['grid'] + self._classes)
        p (fd, '<table class="%s">', cls)
        cols = max (map (lambda x: len(x['data']), self._rows))
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
    def __init__ (self, **kw):
        super (PaddingBox, self).__init__ (**kw)

    def output (self, fd=sys.stdout):
        content = self.get_content()
        for i in range(len(content)):
            s = content[i]
            if i == 0:
                p (fd, None, s)
            else:
                p (fd, '<div class="pad">')
                p (fd, None, s)
                p (fd, '</div>')


class AdmonBox (Widget):
    error = "error"
    information = "information"
    warning = "warning"
    
    def __init__ (self, type, title, **kw):
        super (AdmonBox, self).__init__ (**kw)
        self._type = type
        self._title = title
        self._classes = []

    def add_class (self, cls):
        self._classes.append (cls)

    def output (self, fd=sys.stdout):
        cls = ' '.join(['admon'] + self._classes)
        p (fd, '<div class="admon-%s %s">', (self._type, cls))
        p (fd, '<img src="%sadmon-%s-16.png" width="16" height="16">',
           (pulse.config.data_root, self._type))
        p (fd, None, self._title)
        p (fd, '</div>')


class TabbedBox (Widget, ContentComponent):
    def __init__ (self, **kw):
        super (TabbedBox, self).__init__ (**kw)
        self._tabs = []

    def add_tab (self, url, title):
        self._tabs.append ((url, title))

    def output (self, fd=sys.stdout):
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


################################################################################
## Lists

class DefinitionList (Widget):
    def __init__ (self, **kw):
        super (DefinitionList, self).__init__ (**kw)
        self._id = kw.get('id', None)
        self._all = []

    def add_term (self, term, class_name=None):
        self._all.append (('dt', term, class_name))

    def add_entry (self, entry, class_name=None):
        self._all.append (('dd', entry, class_name))

    def add_divider (self):
        self._all.append (('dt', None, 'hr'))
        
    def output (self, fd=sys.stdout):
        if self._id != None:
            p (fd, '<dl id="%s">', self._id)
        else:
            p (fd, '<dl>')
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


################################################################################
## Other...

class Rule (Widget):
    def output (self, fd=sys.stdout):
        p (fd, '<div class="hr"><hr></div>')


class Graph (Widget):
    _count = 0

    def __init__ (self, url, **kw):
        super (Graph, self).__init__ (**kw)
        self._url = url
        self._comments = []

    def add_comment (self, coords, comment, href=None):
        self._comments.append ((coords, comment, href))

    def output (self, fd=sys.stdout):
        if len(self._comments) == 0:
            p (fd, '<div class="graph"><img src="%s"></div>', self._url)
        else:
            Graph._count += 1
            p (fd, '<div class="graph" id="graph-%i"><img src="%s" usemap="#graphmap%i" ismap>',
               (Graph._count, self._url, Graph._count))
            p (fd, '<map name="graphmap%i">', Graph._count)
            i = 0
            for comment in self._comments:
                i += 1
                p (fd, '<area shape="rect" coords="%s"', ','.join(map(str, comment[0])), False)
                p (fd, ' onmouseover="javascript:comment(%i, %i, %i)"', (Graph._count, i, comment[0][0]), False)
                p (fd, ' onmouseout="javascript:comment(%i, %i)"', (Graph._count, i), False)
                if comment[2] != None:
                    p (fd, ' href="%s"', comment[2])
                p (fd, '>')
            p (fd, '</map>')
            i = 0
            p (fd, '<div class="comments">')
            for comment in self._comments:
                i += 1
                p (fd, '<div class="comment" id="comment-%i-%i">%s</div>',
                   (Graph._count, i, comment[1]))
            p (fd, '</div></div>')

    @classmethod
    def activity_graph (cls, of, url):
        graph = cls (of.pulse_url)
        thisweek = pulse.utils.weeknum (datetime.datetime.now())
        for (c, tot, weeknum) in of.data.get ('coords', []):
            ago = thisweek - weeknum
            if ago == 0:
                cmt = pulse.utils.gettext ('this week: %i commits') % tot
            elif ago == 1:
                cmt = pulse.utils.gettext ('last week: %i commits') % tot
            else:
                cmt = pulse.utils.gettext ('%i weeks ago: %i commits') % (ago, tot)
            jslink = 'javascript:replace(\'commits\', '
            jslink += '\'%s?ajax=commits&weeknum=%i\')' % (url, weeknum)
            graph.add_comment (c, cmt, jslink)
        return graph


class EllipsizedLabel (Widget):
    def __init__ (self, label, size, **kw):
        super (EllipsizedLabel, self).__init__ (**kw)
        self._label = label
        self._size = size

    def output (self, fd=sys.stdout):
        if len (self._label) > self._size:
            i = self._size - 10
            if i <= 0: i = self._size
            while i < len(self._label):
                if self._label[i] == ' ':
                    break
                i += 1
            if i == len(self._label):
                p (fd, None, self._label)
            else:
                id = md5.md5(self._label).hexdigest()[:6]
                p (fd, None, self._label[:i])
                p (fd, '<span class="elliplnk" id="elliplnk-%s">(<a href="javascript:ellip(\'%s\')">%s</a>)</span>',
                   (id, id, pulse.utils.gettext ('more')))
                p (fd, '<span class="elliptxt" id="elliptxt-%s">%s</span>', (id, self._label[i+1:]))
        else:
            p (fd, None, self._label)


class MenuLink (Widget):
    _count = 0

    def __init__ (self, id, txt=None, **kw):
        self._menu_only = kw.pop ('menu_only', False)
        super (MenuLink, self).__init__ (**kw)
        self._id = id
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

    def output (self, fd=sys.stdout):
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

    def output (self, fd=sys.stdout):
        PopupLink._count += 1
        p (fd, '<a class="plink" id="plink%i" href="javascript:plink(\'%i\')">',
           (PopupLink._count, PopupLink._count), False)
        p (fd, None, self._short, False)
        p (fd, '</a>')
        p (fd, '<div class="pcont" id="pcont%i">', PopupLink._count)
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
                    cm = colonre.match(line)
                    if cm:
                        line = cm.group(1).strip()
                        if line != '':
                            break
                    else:
                        break
            if line == '': line = maybe
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
    def __init__ (self, *args, **kw):
        super (Span, self).__init__ (**kw)
        for arg in args:
            self.add_content (arg)
        self._divider = kw.get('divider', None)
        self._classes = []

    def set_divider (self, divider):
        self._divider = divider

    def add_class (self, cls):
        self._classes.append (cls)

    def output (self, fd=sys.stdout):
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


class Div (Widget, ContentComponent):
    def __init__ (self, *args, **kw):
        super (Div, self).__init__ (**kw)
        self._id = kw.get('id', None)
        for arg in args:
            self.add_content (arg)

    def output (self, fd=sys.stdout):
        if self._id != None:
            p (fd, '<div id="%s">', self._id)
        else:
            p (fd, '<div>')
        ContentComponent.output (self, fd=fd)
        p (fd, '</div>')


class Pre (Widget, ContentComponent):
    def __init__ (self, *args, **kw):
        super (Pre, self).__init__ (**kw)
        self._id = kw.get('id', None)
        for arg in args:
            self.add_content (arg)

    def output (self, fd=sys.stdout):
        if self._id != None:
            p (fd, '<pre id="%s">', self._id)
        else:
            p (fd, '<pre>')
        ContentComponent.output (self, fd=fd)
        p (fd, '</pre>')


class Link (Widget):
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
        self._icon = kw.get('icon', None)
    
    def output (self, fd=sys.stdout):
        if self._href != None:
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

def p (fd, s, arg=None, nl=True):
    if fd == None:
        fd = sys.stdout
    if isinstance (s, Widget) or isinstance (s, Component):
        s.output (fd=fd)
    elif s == None and (isinstance (arg, Widget) or isinstance (arg, Component)):
        arg.output (fd=fd)
    else:
        if s == None:
            outstr = esc(arg)
        elif arg == None:
            outstr = s
        else:
            outstr = s % esc(arg)
        if nl:
            outstr += '\n'
        try:
            fd.write(outstr.encode('utf-8'))
        except:
            fd.write(outstr)

def esc (s):
    if isinstance (s, basestring):
        return cgi.escape (s, True)
    elif isinstance (s, tuple):
        return tuple (map (esc, s))
    elif isinstance (s, dict):
        return escdict (s)
    else:
        return s

class escdict (dict):
    def __init__ (self, *args):
        dict.__init__ (self, *args)

    def __getitem__ (self, key):
        return esc (dict.__getitem__ (self, key))

