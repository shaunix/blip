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

import cgi
import md5
import sys

import pulse.config
import pulse.utils

class Block:
    def __init__ (self, **kw):
        pass
    def output_top (self, fd=sys.stdout):
        pass
    def output_middle (self, fd=sys.stdout):
        pass
    def output_bottom (self, fd=sys.stdout):
        pass
    def output (self, fd=sys.stdout):
        self.output_top (fd=fd)
        self.output_middle (fd=fd)
        self.output_bottom (fd=fd)


################################################################################
## Components

class SublinksComponent (Block):
    BULLET = u' • '
    TRIANGLE = u' ‣ '
    
    def __init__ (self, **kw):
        Block.__init__ (self, **kw)
        self._sublinks = []
        self._divider = kw.get('divider', self.BULLET)

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


class FactsComponent (Block):
    def __init__ (self, **kw):
        Block.__init__ (self, **kw)
        self._divs = []
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
                    if isinstance (f, basestring) or isinstance (f, Block):
                        p (fd, None, f, False)
                    elif isinstance (f, pulse.db.Record):
                        p (fd, Link(f))
                    elif hasattr (f, '__getitem__'):
                        for ff in f:
                            p (fd, '<div>', None, False)
                            factout (ff)
                            p (fd, '</div>')
                factout (fact['content'])
                p (fd, '</td></tr>')
        p (fd, '</table>')


class ContentComponent (Block):
    def __init__ (self, **kw):
        Block.__init__ (self, **kw)
        self._content = []

    def add_content (self, content):
        self._content.append (content)

    def get_content (self):
        return self._content

    def output (self, fd=sys.stdout):
        for s in self._content:
            p (fd, None, s)


################################################################################
## Pages

class Page (Block, ContentComponent):
    def __init__ (self, **kw):
        Block.__init__ (self, **kw)
        ContentComponent.__init__ (self, **kw)
        self._http = kw.get ('http', True)
        self._status = kw.get ('status')
        self._title = kw.get ('title')
        self._icon = kw.get ('icon')

    def set_title (self, title):
        self._title = title

    def set_icon (self, icon):
        self._icon = icon

    def output_top (self, fd=sys.stdout):
        if self._http == True:
            if self._status == 404:
                p (fd, 'Status: 404 Not found')
            elif self._status == 500:
                p (fd, 'Status: 500 Internal server error')
            p (fd, 'Content-type: text/html; charset=utf-8\n')
        p (fd, '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">')
        p (fd, '<html><head>')
        p (fd, '  <title>%s</title>', self._title)
        p (fd, '  <meta http-equiv="Content-type" content="text/html; charset=utf-8">')
        p (fd, '  <link rel="stylesheet" href="%sdata/pulse.css">', pulse.config.webroot)
        p (fd, '  <script language="javascript" type="text/javascript" src="%sdata/pulse.js"></script>',
           pulse.config.webroot)
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
            p (fd, '<img class="icon" src="%s" alt="%s">', (self._icon, self._title), False)
        p (fd, None, self._title)
        p (fd, '</h1>')

    def output_middle (self, fd=sys.stdout):
        ContentComponent.output (self, fd=fd)

    def output_bottom (self, fd=sys.stdout):
        p (fd, '</div></body></html>')

class ResourcePage (Page, SublinksComponent, FactsComponent):
    def __init__ (self, resource, **kw):
        Page.__init__ (self, **kw)
        SublinksComponent.__init__ (self, **kw)
        FactsComponent.__init__ (self, **kw)
        self.set_title (resource.title)
        if resource.icon_url != None:
            self.set_icon (resource.icon_url)

    def output_middle (self, fd=sys.stdout):
        SublinksComponent.output (self, fd=fd)
        FactsComponent.output (self, fd=fd)
        Page.output_middle (self, fd=fd)

class PageNotFound (Page):
    def __init__ (self, message, **kw):
        Page.__init__ (self, status=404, **kw)
        if not kw.has_key ('title'):
            self.set_title (pulse.utils.gettext('Page Not Found'))
        self._pages = kw.get ('pages', [])
        self._message = message

    def output_middle (self, fd=sys.stdout):
        p (fd, '<div class="notfound">')
        p (fd, '<div class="message">%s</div>', self._message)
        if len(self._pages) > 0:
            p (fd, '<div class="pages">%s',
               pulse.utils.gettext ('The following pages might interest you:'))
            p (fd, '<ul>')
            for page in self._pages:
                p (fd, '<li><a href="%s%s">%s</a></li>' %
                   (pulse.config.webroot, page[0], page[1]))
            p (fd, '</ul></div>')
        p (fd, '</div>')
        ContentComponent.output (self, fd=fd)

class PageError (Page):
    def __init__ (self, message, **kw):
        Page.__init__ (self, status=404, **kw)
        if not kw.has_key ('title'):
            self.set_title (pulse.utils.gettext('Bad Monkeys'))
        self._pages = kw.get ('pages', [])
        self._message = message
    
    def output_middle (self, fd=sys.stdout):
        p (fd, '<div class="servererror">')
        p (fd, '<div class="message">%s</div>', self._message)
        p (fd, '</div>')
        ContentComponent.output (self, fd=fd)


################################################################################
## Boxes

class InfoBox (ContentComponent):
    def __init__ (self, id, title, **kw):
        ContentComponent.__init__ (self, **kw)
        self._id = id
        self._title = title

    def add_resource_link (self, resource, superlative=False):
        reslink = ResourceLinkBox (resource, superlative=superlative)
        self.add_content (reslink)
        return reslink

    def output (self, fd=sys.stdout):
        p (fd, '<div class="info" id="%s">', self._id)
        p (fd, '<div class="info-title">%s</div>', self._title)
        p (fd, '<div class="info-content">')
        ContentComponent.output (self, fd=fd)
        p (fd, '</div></div>')


class ResourceLinkBox (ContentComponent, FactsComponent):
    def __init__ (self, *args, **kw):
        FactsComponent.__init__ (self, **kw)
        ContentComponent.__init__ (self, **kw)
        self._url = self._title = self._icon = self._desc = None
        if isinstance (args[0], pulse.db.Record):
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

    def set_url (self, url):
        self._url = url

    def set_title (self, title):
        self._title = title

    def set_icon (self, icon):
        self._icon = icon

    def set_description (self, description):
        self._desc = description

    def add_badge (self, badge):
        self._badges.append (badge)

    def output (self, fd=sys.stdout):
        d = pulse.utils.attrdict ([self, pulse.config])
        p (fd, '<table class="rlink"><tr>')
        p (fd, '<td class="rlink-icon">')
        if self._icon != None:
            p (fd, '<img class="icon" src="%s" alt="%s">', (self._icon, self._title))
        p (fd, '</td><td class="rlink-text">')
        p (fd, '<div class="rlink-title">')
        if self._url != None:
            p (fd, '<a href="%s">%s</a>', (self._url, self._title))
        else:
            p (fd, None, self._title)
        if len(self._badges) > 0:
            p (fd, ' ')
            for badge in self._badges:
                p (fd, '<img src="%sdata/badge-%s-16.png" width="16" height="16" alt="%s">',
                   (pulse.config.webroot, badge, badge))
        p (fd, '</div>')
        if self._desc != None:
            p (fd, '<div class="rlink-desc">')
            p (fd, EllipsizedLabel (self._desc, 130))
            p (fd, '</div>')
        FactsComponent.output (self, fd=fd)
        ContentComponent.output (self, fd=fd)
        p (fd, '</td></tr></table>')
        

class ColumnBox (Block):
    def __init__ (self, num, **kw):
        Block.__init__ (self, **kw)
        self._columns = [[] for i in range(num)]

    def add_content (self, index, content):
        self._columns[index].append (content)
        return content

    def output (self, fd=sys.stdout):
        p (fd, '<table class="cols"><tr>')
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


class GridBox (Block):
    def __init__ (self, **kw):
        Block.__init__ (self, **kw)
        self._rows = []

    def add_row (self, *row):
        self._rows.append (row)

    def output (self, fd=sys.stdout):
        if len (self._rows) == 0:
            return
        p (fd, '<table class="grid">')
        cols = max (map (len, self._rows))
        for row in self._rows:
            p (fd, '<tr>')
            for i in range (cols):
                if i == 0:
                    p (fd, '<td class="grid-td-first">')
                else:
                    p (fd, '<td class="grid-td">')
                if i < len (row):
                    p (fd, None, row[i])
                p (fd, '</td>')
            p (fd, '</tr>')
        p (fd, '</table>')


class VBox (ContentComponent):
    def __init__ (self, **kw):
        ContentComponent.__init__ (self, **kw)

    def output (self, fd=sys.stdout):
        p (fd, '<div class="vbox">')
        content = self.get_content()
        for i in range(len(content)):
            s = content[i]
            if i == 0:
                p (fd, '<div class="vbox-el-first">')
            else:
                p (fd, '<div class="vbox-el">')
            p (fd, None, s)
            p (fd, '</div>')
        p (fd, '</div>')


class AdmonBox (Block):
    error = "error"
    information = "information"
    warning = "warning"
    
    def __init__ (self, type, title, **kw):
        Block.__init__ (self, **kw)
        self._type = type
        self._title = title

    def output (self, fd=sys.stdout):
        p (fd, '<div class="admon admon-%s">', self._type)
        p (fd, '<img src="%sdata/admon-%s-16.png" width="16" height="16">',
           (pulse.config.webroot, self._type))
        p (fd, None, self._title)
        p (fd, '</div>')


class ExpanderBox (ContentComponent):
    def __init__ (self, id, title, **kw):
        ContentComponent.__init__ (self, **kw)
        self._id = id
        self._title = title

    def output (self, fd=sys.stdout):
        p (fd, '<div class="expander" id="%s">', self._id)
        p (fd, '<div class="expander-title">', None, False)
        p (fd, '<a href="javascript:expander_toggle(\'%s\')">', self._id, False)
        p (fd, '<img id="img-%s" class="expander-img" src="%sdata/expander-open.png"> %s</a></div>',
           (self._id, pulse.config.webroot, self._title))
        p (fd, '<div class="expander-content">')
        ContentComponent.output (self, fd=fd)
        p (fd, '</div>')


class TabbedBox (Block):
    def __init__ (self, **kw):
        Block.__init__ (self, **kw)
        self._tabs = []

    def add_tab (self, title, active, data):
        self._tabs.append ((title, active, data))

    def output (self, fd=sys.stdout):
        content = None
        p (fd, '<div class="tabbed">')
        p (fd, '<div class="tabbed-tabs">')
        for tab in self._tabs:
            title = esc(tab[0]).replace(' ', '&nbsp;')
            if tab[1]:
                p (fd, '<span class="tabbed-tab-active">' + title + '</span>')
                content = tab[2]
            else:
                p (fd, '<span class="tabbed-tab-link"><a href="%s">' + title + '</a></span>', tab[2])
        p (fd, '</div>')
        if content != None:
            p (fd, '<div class="tabbed-content">')
            p (fd, content)
            p (fd, '</div>')


################################################################################
## Lists

class DefinitionList (Block):
    def __init__ (self, **kw):
        Block.__init__ (self, **kw)
        self._all = []

    def add_term (self, term):
        self._all.append (('dt', term))

    def add_entry (self, entry):
        self._all.append (('dd', entry))
        
    def output (self, fd=sys.stdout):
        p (fd, '<dl>')
        for d in self._all:
            p (fd, '<%s>' % d[0])
            p (fd, None, d[1])
            p (fd, '</%s>' % d[0])
        p (fd, '</dl>')


################################################################################
## Other...

class Graph (Block):
    def __init__ (self, url, **kw):
        Block.__init__ (self, **kw)
        self._url = url

    def output (self, fd=sys.stdout):
        p (fd, '<div class="graph"><img src="%s"></div>',
           '/'.join ([pulse.config.webroot, 'var', 'graph', self._url]))


class EllipsizedLabel (Block):
    def __init__ (self, label, size, **kw):
        Block.__init__ (self, **kw)
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


class Span (ContentComponent):
    SPACE = ' '
    BULLET = u' • '
    TRIANGLE = u' ‣ '

    def __init__ (self, *args, **kw):
        ContentComponent.__init__ (self, **kw)
        for arg in args:
            self.add_content (arg)
        self._divider = kw.get('divider', None)

    def set_divider (self, divider):
        self._divider = divider

    def output (self, fd=sys.stdout):
        p (fd, '<span>')
        content = self.get_content()
        for i in range(len(self.get_content())):
            if i != 0 and self._divider != None:
                p (fd, None, self._divider)
            p (fd, None, content[i])
        p (fd, '</span>')


class Link (Block):
    def __init__ (self, *args, **kw):
        Block.__init__ (self, **kw)
        self._href = self._text = None
        if isinstance (args[0], pulse.db.Record):
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
        if self._icon == None and self._href == None:
            p (fd, None, self._text)
        elif self._icon == None:
            p (fd, '<a href="%s">%s</a>', (self._href, self._text))
        elif self._href == None:
            p (fd, '<img src="%sdata/%s-16.png" height="16" width="16"> %s',
               (pulse.config.webroot, self._icon, self._text))
        else:
            p (fd, '<a href="%s"><img src="%sdata/%s-16.png" height="16" width="16"> %s</a>',
               (self._href, pulse.config.webroot, self._icon, self._text))


################################################################################
## Utility Functions

def p (fd, s, arg=None, nl=True):
    if fd == None:
        fd = sys.stdout
    if isinstance (s, Block):
        s.output (fd=fd)
    elif s == None and isinstance (arg, Block):
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

