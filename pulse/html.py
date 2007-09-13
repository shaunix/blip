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

import sys

import pulse.config as config
import pulse.utils as utils

class Block:
    def __init__ (self, **kw):
        self._head = []
        self._foot = []
    def add (self, text):
        self._head.append (text)
    def foot (self, text):
        self._foot.insert (0, text)
    def output (self, fd=sys.stdout):
        for s in self._head:
            if isinstance (s, Block):
                s.output(fd)
            else:
                print >>fd, unicode(s).encode('utf-8')
        for s in self._foot:
            if isinstance (s, Block):
                s.output(fd)
            else:
                print >>fd, unicode(s).encode('utf-8')
            
class Page (Block):
    headText = ('<html><head>\n' +
                '<title>%(title)s</title>\n'
                '<link rel="stylesheet" href="%(webroot)sdata/pulse.css" />\n' +
                '<script language="javascript" type="text/javascript"' +
                ' src="%(webroot)sdata/pulse.js" />\n' +
                '</head><body>\n' +
                '<div id="head"><a href="http://www.gnome.org">' +
                '<img src="%(webroot)sdata/gnome-logo.png"' +
                ' width="110" height="20" class="logo" alt="GNOME" /></a></div>\n' +
                '<div id="body"><h1>%(title)s</h1>')
    footText = '</div></body></html>'
    def __init__ (self, **kw):
        Block.__init__ (self, **kw)
        self.http = kw.get ('http')
        self.status = kw.get ('status')
        self.title = kw.get ('title')
        self.webroot = config.webroot
        if self.http == True:
            if self.status == 404:
                self.add ('Status: 404 Not found\n')
            self.add ('Content-type: text/html; charset=utf-8\n\n')
        self.add (self.headText % self.__dict__ )
        self.foot (self.footText)

class PageNotFound (Page):
    def __init__ (self, message, **kw):
        http = kw.get ('http', True)
        pages = kw.get ('pages', [])
        title = kw.get ('title', 'Page Not Found')
        d = utils.attrdict ([config])
        d['title'] = title
        d['message'] = message
        Page.__init__ (self,
                       http=http,
                       status=404,
                       title=title)
        self.add ('<div class="notfound">\n')
        self.add ('<div class="title">%(title)s</div>\n' %d)
        self.add ('<div class="message">%(message)s</div>' %d)
        if len(pages) > 0:
            self.add ('<div class="pages">These pages might interest you:<ul>\n')
            for page in pages:
                d['href'] = page[0]
                d['name'] = page[1]
                self.add ('<li><a href="%(webroot)s%(href)s">%(name)s</a></li>\n' %d)
            self.add ('</ul></div>\n')
        self.add ('</div>\n')

class InformationPage (Page):
    def __init__ (self, thing, **kw):
        Page.__init__ (self, **kw)
        self.add (SynopsisDiv (thing))

class SynopsisDiv (Block):
    def __init__ (self, resource, **kw):
        Block.__init__ (self, **kw)
        self._resource = resource
        self._sublinks = []
        self._affils = {}
        self._graphs = []

    def add_sublink (self, href, title):
        self._sublinks.append ((href, title))

    def add_affiliation (self, title, href, name, comment=None):
        self._affils.setdefault (title, [])
        self._affils[title].append ({'href': href,
                                     'name': name,
                                     'comment': comment})
    
    def add_graph (self, title, href, src, alt):
        self._graphs.append ({'title': title,
                              'href': href,
                              'src': src,
                              'alt': alt})

    def output (self, fd=sys.stdout):
        def p (s):
            if isinstance (s, Block):
                s.output (fd=fd)
            else:
                # FIXME: we need to escape all incoming text
                print >>fd, s.encode('utf-8')
        d = utils.attrdict ([self._resource, config])

        # A few keys we assume are always there
        if not d.has_val ('name'):
            d['name'] = d['ident']
        if not d.has_val ('type'):
            d['type'] = self._resource.sqlmeta.table

        p ('<div class="%(type)s synopsis">' %d)
        p ('<table class="%(type)s synopsis"><tr>\n' %d)

        p ('<td class="icon">')
        if d.has_val ('icon'):
            p ('<img class="icon" src="%(icon)s" alt="%(name)s" />' %d)
        p ('</td>\n')

        p ('<td class="info">\n')

        p ('<div class="name">')
        if len(self._sublinks) > 0:
            name_ = d['name']
        else:
            name_ = ('<a href="%(webroot)s%(ident)s/">%(name)s</a>' %d)
        if d.has_val ('nick'):
            nick_ =  (' (%(nick)s)' %d)
        else:
            nick_ = ''
        p ('%s%s</div>' %(name_, nick_))

        if len(self._sublinks) > 0:
            p ('<div class="sublinks">')
            for i in range(len(self._sublinks)):
                str = (i != 0 and u' • ' or '')
                if self._sublinks[i][0] != None:
                    str += ('<a href="%s">%s</a>' %self._sublinks[i])
                else:
                    str += ('%s' %self._sublinks[i][0])
                p (str)
            p ('</div>\n')
        if d.has_val ('mail'):
            p ('<div class="mail">')
            p ('<a href="mailto:%(mail)s">%(mail)s</a></div>\n' %d)
            if d.has_val ('list_info') or d.has_val ('list_archive'):
                p ('<div class="sublinks">')
                p (u'<a href="%(list_info)s">Information</a> • ' %d)
                p ('<a href="%(list_archive)s">Archives</a>' %d)
                p ('</div>\n')
        if d.has_val ('web'):
            p ('<div class="web">')
            p ('<a href="%(web)s">%(web)s</a></div>\n' %d)
        if d.has_val ('blurb'):
            p ('<p class="blurb">%(blurb)s</p>' %d)
        if hasattr (self._resource, 'mail_lists'):
            for list in self._resource.mail_lists:
                d.prepend (list.resource)
                p ('<div class="mail_list"><div class="mail">')
                p ('<a href="mailto:%(mail)s">%(mail)s</a>' %d)
                if list.resource.list_type == 'users': p (' (Users)')
                if list.resource.list_type == 'devel': p (' (Developers)')
                p ('</div><div class="sublinks">')
                p (u'<a href="%(webroot)s%(ident)s/">Pluse</a> • ' %d)
                p (u'<a href="%(list_info)s/">Information</a> • ' %d)
                p (u'<a href="%(list_archive)s/">Archive</a>' %d)
                p ('</div></div>\n')
                d.remove (list.resource)

        for key in self._affils:
            p ('<div class="affiliation">\n')
            p ('<div class="title">%s</div><ul>\n' %key)
            for affil in self._affils[key]:
                p ('<li><a href="%(href)s/">%(name)s</a>' % affil)
                if affil['comment'] != None:
                    p (' %(comment)s' %affil)
                p ('</li>\n')
            p ('</ul></div>\n')
        p ('</td>')

        p ('<td class="graphs">\n')
        for g in self._graphs:
            p ('<div class="graph">')
            p ('<div class="title">%(title)s</div>' %g)
            p ('<img src="%(src)s" alt="%(alt)s" />' %g)
            p ('</div></div>\n')
        p ('</td>')

        p ('</tr></table></div>\n')

class SummaryDiv (Block):
    def __init__ (self, resource, **kw):
        Block.__init__ (self, **kw)
        self._resource = resource
        self._blocks = []

    def add_block (self, block):
        self._blocks.append (block)
    
    def output (self, fd=sys.stdout):
        def p (s):
            if isinstance (s, Block):
                s.output (fd=fd)
            else:
                # FIXME: we need to escape all incoming text
                print >>fd, s.encode('utf-8')
        p ('<div class="summary">')
        p ('<div class="title"><a href="%s%s">%s</a></div>' % (config.webroot,
                                                               self._resource.ident,
                                                               self._resource.name))
        for block in self._blocks:
            p (block)
        p ('</div>')

class TabbedDiv (Block):
    def __init__ (self, **kw):
        Block.__init__ (self, **kw)
        self._tabs = []

    def add_tab (self, id, title, div, open=None):
        if open:
            for tab in self._tabs:
                tab['open'] = False
        elif open == None:
            open = (len(self._tabs) == 0) and True or False
        self._tabs.append ({'id': id, 'title': title, 'div': div, 'open': open})

    def output (self, fd=sys.stdout):
        def p (s):
            if isinstance (s, Block):
                s.output (fd=fd)
            else:
                # FIXME: we need to escape all incoming text
                print >>fd, s.encode('utf-8')
        p ('<div class="tabbed">')
        p ('<div class="tabbed-tabs">')
        p ('<table class="tabbed-tabs"><tr>')
        for tab in self._tabs:
            if tab['open']:
               str = ('<td class="tabbed-tab-expanded" id="%(id)s--tab">' %tab)
            else:
               str = ('<td class="tabbed-tab-collapsed" id="%(id)s--tab">' %tab)
            str += ('<div><a href="javascript:tab(\'%(id)s\')">' %tab)
            str += ('%(title)s</a></div></td>' %tab)
            p (str)
        p ('<td class="tabbed-tab-fin"></td>')
        p ('</tr></table></div>')
        for tab in self._tabs:
            if tab['open']:
                p ('<div class="tabbed-expanded" id="%(id)s">' %tab)
            else:
                p ('<div class="tabbed-collapsed" id="%(id)s">' %tab)

            if isinstance (tab['div'], Block):
                tab['div'].output(fd)
            else:
                print >>fd, unicode(tab['div']).encode('utf-8')

            p ('</div>')
        p ('</div>')

class Admonition (Block):
    def __init__ (self, text, type, **kw):
        Block.__init__ (self, **kw)
        self._text = text
        self._type = type

    def output (self, fd=sys.stdout):
        def p (s):
            if isinstance (s, Block):
                s.output (fd=fd)
            else:
                # FIXME: we need to escape all incoming text
                print >>fd, s.encode('utf-8')
        p ('<div class="admonition %s">' % self._type)
        p ('<img src="%sdata/admon-%s-16.png" class="admonition"/>'
           % (config.webroot, self._type))
        p ('%s</div>' % self._text)
