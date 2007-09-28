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
    def __init__ (self):
        self._sublinks = []

    def add_sublink (self, href, title):
        self._sublinks.append ((href, title))

    @classmethod
    def output_sublinks (cls, sublinks, fd):
        if len(sublinks) > 0:
            p (fd, '<div class="sublinks">')
            for i in range(len(sublinks)):
                str = (i != 0 and u' • ' or '')
                if sublinks[i][0] != None:
                    str += ('<a href="%s">%s</a>' %sublinks[i])
                else:
                    str += ('%s' %sublinks[i][1])
                p (fd, str)
            p (fd, '</div>\n')

    def output (self, fd=sys.stdout):
        SublinksComponent.output_sublinks (self._sublinks, fd)


################################################################################
## Pages

class Page (Block):
    # FIXME: i18n
    _head_text = '''
<html><head>
  <title>%(_title)s</title>\n
  <link rel="stylesheet" href="%(_webroot)sdata/pulse.css" />
  <script language="javascript" type="text/javascript" src="%(_webroot)sdata/pulse.js" />
</head><body>
<ul id="general">
  <li id="siteaction-gnome_home" class="home"><a href="http://www.gnome.org/">Home</a></li>
  <li id="siteaction-gnome_news"><a href="http://news.gnome.org">News</a></li>
  <li id="siteaction-gnome_projects"><a href="http://www.gnome.org/projects/">Projects</a></li>
  <li id="siteaction-gnome_art"><a href="http://art.gnome.org">Art</a></li>
  <li id="siteaction-gnome_support"><a href="http://www.gnome.org/support/">Support</a></li>
  <li id="siteaction-gnome_development"><a href="http://developer.gnome.org">Development</a></li>
  <li id="siteaction-gnome_community"><a href="http://www.gnome.org/community/">Community</a></li>
</ul>
<div id="header">
  <h1>Pulse</h1>
  <div id="tabs"><ul id="portal-globalnav">
    <li id="portaltab-root" class="selected"><a href="/"><span>Home</span></a></li>
    <li id="portaltab-users"><a href="/users/"><span>Users</span></a></li>
    <li id="portaltab-sysadmins"><a href="/admin/"><span>Administrators</span></a></li>
    <li id="portaltab-developers"><a href="/devel/"><span>Developers</span></a></li>
    <li id="portaltab-about"><a href="/about/about"><span>About</span></a></li>
  </ul></div>
</div>
<div id="body"><h1>%(_title)s</h1>'''
    _foot_text = '</div></body></html>'

    def __init__ (self, **kw):
        Block.__init__ (self, **kw)
        self._http = kw.get ('http')
        self._status = kw.get ('status')
        self._title = kw.get ('title')
        self._webroot = pulse.config.webroot
        self._content = []

    def set_title (self, title):
        self._title = title

    def add_content (self, content):
        self._content.append (content)

    def output_top (self, fd=sys.stdout):
        if self._http == True:
            if self._status == 404:
                p (fd, 'Status: 404 Not found\n')
            p (fd, 'Content-type: text/html; charset=utf-8\n\n')
        p (fd, self._head_text % self.__dict__)

    def output_middle (self, fd=sys.stdout):
        for s in self._content:
            p (fd, s)

    def output_bottom (self, fd=sys.stdout):
        p (fd, self._foot_text % self.__dict__)

class ResourcePage (Page, SublinksComponent):
    def __init__ (self, resource, **kw):
        Page.__init__ (self, **kw)
        # FIXME: i18n
        self.set_title (resource.title)
        self._sublinks = []
        self._affils = {}
        self._graphs = []

    def output_middle (self, fd=sys.stdout):
        SublinksComponent.output (self, fd=fd)
        Page.output_middle (self, fd=fd)

class PageNotFound (Page):
    def __init__ (self, message, **kw):
        http = kw.get ('http', True)
        pages = kw.get ('pages', [])
        title = kw.get ('title', pulse.utils.gettext('Page Not Found'))
        d = pulse.utils.attrdict ([pulse.config])
        d['title'] = title
        d['message'] = message
        Page.__init__ (self,
                       http=http,
                       status=404,
                       title=title)
        self.pack_start ('<div class="notfound">\n')
        self.pack_start ('<div class="title">%(title)s</div>\n' %d)
        self.pack_start ('<div class="message">%(message)s</div>' %d)
        if len(pages) > 0:
            self.pack_start ('<div class="pages">' +
                             pulse.utils.gettext ('The following pages might interest you:') +
                             '<ul>\n')
            for page in pages:
                d['href'] = page[0]
                d['name'] = page[1]
                self.pack_start ('<li><a href="%(webroot)s%(href)s">%(name)s</a></li>\n' %d)
            self.pack_start ('</ul></div>\n')
        self.pack_start ('</div>\n')


################################################################################
## Other...

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

    def output_middle (self, fd=sys.stdout):
        def p (s):
            if isinstance (s, Block):
                s.output (fd=fd)
            else:
                # FIXME: we need to escape all incoming text
                print >>fd, s.encode('utf-8')
        d = pulse.utils.attrdict ([self._resource, pulse.config])

        # FIXME: i18n
        d['name'] = self._resource.localized_name
        d['__url__'] = '/'.join ([pulse.config.webroot] + self._resource.ident.split('/')[1:])

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
            name_ = ('<a href="%(__url__)s/">%(name)s</a>' %d)
        if d.has_val ('nick'):
            # FIXME: i18n
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
                p (u'<a href="%(__url__)s/">Pluse</a> • ' %d)
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
        p ('<div class="title"><a href="%s%s">%s</a></div>' % (pulse.config.webroot,
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
        p (fd, '<div class="admonition %s">' % self._type)
        p (fd, '<img src="%sdata/admon-%s-16.png" class="admonition"/>'
           % (pulse.config.webroot, self._type))
        p (fd, '%s</div>' % self._text)

        

def p (fd, s):
    if isinstance (s, Block):
        s.output (fd=fd)
    else:
        print >>fd, unicode(s).encode('utf-8')
