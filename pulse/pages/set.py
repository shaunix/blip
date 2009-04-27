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

from pulse import config, core, db, html, utils

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
        action = self.request.query.get ('action')
        if action == 'tab':
            tab = self.request.query.get ('application')
            if tab == 'subsets':
                contents = self.get_subsets_tab ()
            elif tab == 'modules':
                contents = self.get_modules_tab ()
            elif tab == 'documents':
                contents = self.get_documents_tab ()
            elif tab == 'domains':
                contents = self.get_domains_tab ()
            elif tab == 'programs':
                contents = self.get_programs_tab ()
            elif tab == 'libraries':
                contents = self.get_libraries_tab ()
            self.response.set_contents (html.Div('foo'))
        elif self.record is None:
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
                add_set_info (rset, lbox)
        return page

    def get_set_page (self):
        """Output information about a release set"""
        page = html.Page (self.record)

        page.set_sublinks_divider (html.TRIANGLE)
        page.add_sublink (config.web_root + 'set', utils.gettext ('Sets'))
        for superset in get_supersets (self.record):
            page.add_sublink (superset.pulse_url, superset.title)

        page.add_tab ('overview', utils.gettext ('Overview'))

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

        # Sets
        setcnt = self.record.subsets.count()
        if setcnt > 0:
            page.add_tab ('subsets', utils.gettext ('Subsets (%i)') % setcnt)

        # Modules
        modcnt = db.SetModule.count_related (subj=self.record)
        if modcnt > 0:
            page.add_tab ('modules', utils.gettext ('Modules (%i)') % modcnt)

            # Documents
            objs = db.Branch.select (type=u'Document', parent_in_set=self.record)
            cnt = objs.count()
            if cnt > 0:
                page.add_tab ('documents', utils.gettext ('Documents (%i)') % cnt)

            # Domains
            objs = db.Branch.select (type=u'Domain', parent_in_set=self.record)
            cnt = objs.count()
            if cnt > 0:
                page.add_tab ('domains', utils.gettext ('Domains (%i)') % cnt)

            # Programs
            objs = db.Branch.select (
                db.Branch.type.is_in ((u'Application', u'Capplet', u'Applet')),
                parent_in_set=self.record)
            cnt = objs.count()
            if cnt > 0:
                page.add_tab ('programs', utils.gettext ('Programs (%i)') % cnt)

            # Libraries
            objs = db.Branch.select (type=u'Library', parent_in_set=self.record)
            cnt = objs.count()
            if cnt > 0:
                page.add_tab ('libraries', utils.gettext ('Libraries (%i)') % cnt)

        return page

    def get_subsets_tab (self):
        subsets = utils.attrsorted (list(self.record.subsets), ['title'])
        cont = html.ContainerBox ()
        cont.set_show_icons (False)
        cont.set_columns (2)
        for subset in subsets:
            lbox = cont.add_link_box (subset)
            add_set_info (subset, lbox)
        return cont

    def get_modules_tab (self):
        mods = db.Branch.select_with_mod_person (
            db.Branch.type == u'Module',
            db.SetModule.pred_ident == db.Branch.ident,
            db.SetModule.subj == self.record,
            using=db.SetModule)
        mods = utils.attrsorted (mods, (0, 'title'))
        modcnt = len(mods)
        cont = html.ContainerBox (widget_id='c-modules')
        cont.add_sort_link ('title', utils.gettext ('title'), 1)
        cont.add_sort_link ('module', utils.gettext ('module'))
        cont.add_sort_link ('mtime', utils.gettext ('modified'))
        cont.add_sort_link ('score', utils.gettext ('score'))
        for i in range(modcnt):
            mod = mods[i][0]
            lbox = cont.add_link_box (mod)
            lbox.add_graph (config.graphs_root +
                            '/'.join(mod.ident.split('/')[1:] + ['commits-tight.png']),
                            width=208, height=40)
            span = html.Span (mod.branch_module)
            span.add_class ('module')
            lbox.add_fact (utils.gettext ('module'), html.Link (mod.pulse_url, span))
            if mod.mod_datetime != None:
                span = html.Span (divider=html.SPACE)
                # FIXME: i18n, word order, but we want to link person
                span.add_content (html.Span(mod.mod_datetime.strftime('%Y-%m-%d %T')))
                span.add_class ('mtime')
                if mod.mod_person_ident != None:
                    span.add_content (utils.gettext ('by'))
                    span.add_content (html.Link (mod.mod_person))
                lbox.add_fact (utils.gettext ('modified'), span)
            if mod.mod_score != None:
                span = html.Span(str(mod.mod_score))
                span.add_class ('score')
                lbox.add_fact (utils.gettext ('score'), span)
        return cont

    def get_documents_tab (self):
        boxes = (
            {'box' : html.ContainerBox (widget_id='c-user-docs'),
             'cnt' : 0, 'err' : False },
            {'box' : html.ContainerBox (widget_id='c-devel-docs'),
             'cnt' : 0, 'err' : False }
            )

        docs = db.Branch.select_with_mod_person (type=u'Document',
                                                 parent_in_set=self.record,
                                                 using=db.SetModule)
        docs = utils.attrsorted (list(docs), (0, 'title'))
        for doc, person in docs:
            boxid = doc.subtype == 'gtk-doc' and 1 or 0
            lbox = boxes[boxid]['box'].add_link_box (doc)
            boxes[boxid]['cnt'] += 1
            lbox.add_graph (config.graphs_root + doc.ident[1:] + '/commits-tight.png',
                            width=240, height=40)
            if doc.error != None:
                slink_error = True
                span = html.Span (doc.error)
                span.add_class ('errormsg')
                lbox.add_fact (utils.gettext ('error'),
                               html.AdmonBox (html.AdmonBox.error, span))
                boxes[boxid]['err'] = True
            span = html.Span (doc.branch_module)
            span.add_class ('module')
            url = doc.ident.split('/')
            url = '/'.join(['mod'] + url[2:4] + [url[5]])
            url = config.web_root + url
            lbox.add_fact (utils.gettext ('module'), html.Link (url, span))
            if doc.mod_datetime != None:
                span = html.Span (divider=html.SPACE)
                # FIXME: i18n, word order, but we want to link person
                span.add_content (html.Span(doc.mod_datetime.strftime('%Y-%m-%d %T')))
                span.add_class ('mtime')
                if doc.mod_person_ident != None:
                    span.add_content (utils.gettext ('by'))
                    span.add_content (html.Link (doc.mod_person))
                lbox.add_fact (utils.gettext ('modified'), span)
            if doc.mod_score != None:
                span = html.Span(str(doc.mod_score))
                span.add_class ('score')
                lbox.add_fact (utils.gettext ('score'), span)
            lbox.add_fact (utils.gettext ('status'),
                           html.StatusSpan (doc.data.get('status')))

        pad = html.PaddingBox()
        for boxid in (0, 1):
            if boxes[boxid]['cnt'] > 0:
                if boxid == 0:
                    boxes[boxid]['box'].set_title (
                        utils.gettext ('User Documentation (%i)') % boxes[boxid]['cnt'])
                else:
                    boxes[boxid]['box'].set_title (
                        utils.gettext ('Developer Documentation (%i)') % boxes[boxid]['cnt'])
                boxes[boxid]['box'].add_sort_link ('title', utils.gettext ('title'), 1)
                if boxes[boxid]['err']:
                    boxes[boxid]['box'].add_sort_link ('errormsg', utils.gettext ('error'))
                boxes[boxid]['box'].add_sort_link ('mtime', utils.gettext ('modified'))
                boxes[boxid]['box'].add_sort_link ('score', utils.gettext ('score'))
                boxes[boxid]['box'].add_sort_link ('status', utils.gettext ('status'))
            pad.add_content (boxes[boxid]['box'])

        return pad

    def get_domains_tab (self):
        objs = db.Branch.select_with_output_file (db.Branch.type == u'Domain',
                                                  parent_in_set=self.record,
                                                  on=db.And(db.OutputFile.type == u'l10n',
                                                            db.OutputFile.filename.like (u'%.pot')),
                                                  using=db.SetModule)
        objs = utils.attrsorted (list(objs), (0, 'title'))
        cont = html.ContainerBox (widget_id='c-domains')
        cont.set_columns (2)
        slink_error = False

        for obj, of in objs:
            lbox = cont.add_link_box (obj)
            if obj.error != None:
                slink_error = True
                span = html.Span (obj.error)
                span.add_class ('errormsg')
                lbox.add_fact (utils.gettext ('error'),
                               html.AdmonBox (html.AdmonBox.error, span))
                slink_error = True
            span = html.Span (obj.branch_module)
            span.add_class ('module')
            url = obj.ident.split('/')
            url = '/'.join(['mod'] + url[2:4] + [url[5]])
            url = config.web_root + url
            lbox.add_fact (utils.gettext ('module'), html.Link (url, span))
            if obj.scm_dir == 'po':
                potfile = obj.scm_module + '.pot'
            else:
                potfile = obj.scm_dir + '.pot'

            if of != None:
                span = html.Span (str(of.statistic))
                span.add_class ('messages')
                lbox.add_fact (utils.gettext ('messages'), span)
                slink_messages = True

        cont.add_sort_link ('title', utils.gettext ('title'), 1)
        if slink_error:
            cont.add_sort_link ('errormsg', utils.gettext ('error'))
        cont.add_sort_link ('module', utils.gettext ('module'))
        cont.add_sort_link ('messages', utils.gettext ('messages'))
        return cont

    def get_programs_tab (self):
        pad = html.PaddingBox()
        for widget_id, type, title in (
            ('c-applications', u'Application', utils.gettext ('Applications (%i)')),
            ('c-capplets', u'Capplet', utils.gettext ('Control Panels (%i)')),
            ('c-applets',u'Applet', utils.gettext ('Panel Applets (%i)')) ):
            objs = db.Branch.select (type=type, parent_in_set=self.record)
            objs = utils.attrsorted (list(objs), 'title')
            if len(objs) == 0:
                continue
            cont = html.ContainerBox (widget_id=widget_id)
            cont.set_title (title % len(objs))
            cont.set_columns (2)
            slink_docs = False
            slink_error = False
            for obj in objs:
                lbox = cont.add_link_box (obj)
                if obj.error != None:
                    slink_error = True
                    span = html.Span (obj.error)
                    span.add_class ('errormsg')
                    lbox.add_fact (utils.gettext ('error'),
                                   html.AdmonBox (html.AdmonBox.error, span))
                    slink_error = True
                span = html.Span (obj.branch_module)
                span.add_class ('module')
                url = obj.ident.split('/')
                url = '/'.join(['mod'] + url[2:4] + [url[5]])
                url = config.web_root + url
                lbox.add_fact (utils.gettext ('module'), html.Link (url, span))
                docs = db.Documentation.get_related (subj=obj)
                for doc in docs:
                    # FIXME: multiple docs look bad and sort poorly
                    doc = doc.pred
                    span = html.Span(doc.title)
                    span.add_class ('docs')
                    lbox.add_fact (utils.gettext ('docs'),
                                   html.Link (doc.pulse_url, span))
                    slink_docs = True
            cont.add_sort_link ('title', utils.gettext ('title'), 1)
            if slink_error:
                cont.add_sort_link ('errormsg', utils.gettext ('error'))
            if slink_docs:
                cont.add_sort_link ('docs', utils.gettext ('docs'))
            cont.add_sort_link ('module', utils.gettext ('module'))
            pad.add_content (cont)
        return pad

    def get_libraries_tab (self):
        objs = db.Branch.select (type=u'Library', parent_in_set=self.record)
        objs = utils.attrsorted (list(objs), 'title')
        cont = html.ContainerBox (widget_id='c-libraries')
        cont.set_columns (2)
        slink_docs = False
        slink_error = False
        for obj in objs:
            lbox = cont.add_link_box (obj)
            if obj.error != None:
                slink_error = True
                span = html.Span (obj.error)
                span.add_class ('errormsg')
                lbox.add_fact (utils.gettext ('error'),
                               html.AdmonBox (html.AdmonBox.error, span))
                slink_error = True
            span = html.Span (obj.branch_module)
            span.add_class ('module')
            url = obj.ident.split('/')
            url = '/'.join(['mod'] + url[2:4] + [url[5]])
            url = config.web_root + url
            lbox.add_fact (utils.gettext ('module'), html.Link (url, span))
            docs = db.Documentation.get_related (subj=obj)
            for doc in docs:
                # FIXME: multiple docs look bad and sort poorly
                doc = doc.pred
                span = html.Span(doc.title)
                span.add_class ('docs')
                lbox.add_fact (utils.gettext ('docs'),
                               html.Link (doc.pulse_url, span))
                slink_docs = True
        cont.add_sort_link ('title', utils.gettext ('title'), 1)
        if slink_error:
            cont.add_sort_link ('errormsg', utils.gettext ('error'))
        if slink_docs:
            cont.add_sort_link ('docs', utils.gettext ('docs'))
        cont.add_sort_link ('module', utils.gettext ('module'))
        return cont


def get_request_handler (request, response):
    return SetHandler (request, response)


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


def get_supersets (rset):
    """Get a list of the supersets of a release set"""
    superset = rset.parent
    if superset == None:
        return []
    else:
        supers = get_supersets (superset)
        return supers + [superset]

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
