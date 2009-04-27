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

class OverviewTab (applications.TabProvider):
    application_id = 'overview'
    tab_group = applications.TabProvider.FIRST_TAB

    def __init__ (self, handler):
        super (OverviewTab, self).__init__ (handler)

    def get_tab_title (self):
        return utils.gettext ('Overview')

    def handle_request (self):
        self.handler.response.set_contents (self.get_tab ())

    def get_tab (self):
        subsets = utils.attrsorted (list(self.handler.record.subsets), ['title'])
        cont = html.ContainerBox ()
        cont.set_show_icons (False)
        cont.set_columns (2)
        for subset in subsets:
            lbox = cont.add_link_box (subset)
            self.handler.add_set_info (subset, lbox)
        return cont

class SubsetsTab (applications.TabProvider):
    application_id = 'subsets'
    tab_group = applications.TabProvider.CORE_TAB

    def __init__ (self, handler, count=None):
        super (SubsetsTab, self).__init__ (handler)
        self.count = count

    def get_tab_title (self):
        return utils.gettext ('Subsets (%i)') % self.count

    def handle_request (self):
        self.handler.response.set_contents (self.get_tab ())

    def get_tab (self):
        subsets = utils.attrsorted (list(self.handler.record.subsets), ['title'])
        cont = html.ContainerBox ()
        cont.set_show_icons (False)
        cont.set_columns (2)
        for subset in subsets:
            lbox = cont.add_link_box (subset)
            self.handler.add_set_info (subset, lbox)
        return cont

class ModulesTab (applications.TabProvider):
    application_id = 'modules'
    tab_group = applications.TabProvider.CORE_TAB
    tab_sort = -1

    def __init__ (self, handler, count=None):
        super (ModulesTab, self).__init__ (handler)
        self.count = count

    def get_tab_title (self):
        return utils.gettext ('Modules (%i)') % self.count

    def handle_request (self):
        self.handler.response.set_contents (self.get_tab ())

    def get_tab (self):
        mods = db.Branch.select_with_mod_person (
            db.Branch.type == u'Module',
            db.SetModule.pred_ident == db.Branch.ident,
            db.SetModule.subj == self.handler.record,
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

class DocumentsTab (applications.TabProvider):
    application_id = 'documents'
    tab_group = applications.TabProvider.CORE_TAB

    def __init__ (self, handler, count=None):
        super (DocumentsTab, self).__init__ (handler)
        self.count = count

    def get_tab_title (self):
        return utils.gettext ('Documents (%i)') % self.count

    def handle_request (self):
        self.handler.response.set_contents (self.get_tab ())

    def get_tab (self):
        boxes = (
            {'box' : html.ContainerBox (widget_id='c-user-docs'),
             'cnt' : 0, 'err' : False },
            {'box' : html.ContainerBox (widget_id='c-devel-docs'),
             'cnt' : 0, 'err' : False }
            )

        docs = db.Branch.select_with_mod_person (type=u'Document',
                                                 parent_in_set=self.handler.record,
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

class DomainsTab (applications.TabProvider):
    application_id = 'domains'
    tab_group = applications.TabProvider.CORE_TAB

    def __init__ (self, handler, count=None):
        super (DomainsTab, self).__init__ (handler)
        self.count = count

    def get_tab_title (self):
        return utils.gettext ('Domains (%i)') % self.count

    def handle_request (self):
        self.handler.response.set_contents (self.get_tab ())

    def get_tab (self):
        objs = db.Branch.select_with_output_file (db.Branch.type == u'Domain',
                                                  parent_in_set=self.handler.record,
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

class ProgramsTab (applications.TabProvider):
    application_id = 'programs'
    tab_group = applications.TabProvider.CORE_TAB

    def __init__ (self, handler, count=None):
        super (ProgramsTab, self).__init__ (handler)
        self.count = count

    def get_tab_title (self):
        return utils.gettext ('Programs (%i)') % self.count

    def handle_request (self):
        self.handler.response.set_contents (self.get_tab ())

    def get_tab (self):
        pad = html.PaddingBox()
        for widget_id, type, title in (
            ('c-applications', u'Application', utils.gettext ('Applications (%i)')),
            ('c-capplets', u'Capplet', utils.gettext ('Control Panels (%i)')),
            ('c-applets',u'Applet', utils.gettext ('Panel Applets (%i)')) ):
            objs = db.Branch.select (type=type, parent_in_set=self.handler.record)
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

class LibrariesTab (applications.TabProvider):
    application_id = 'libraries'
    tab_group = applications.TabProvider.CORE_TAB

    def __init__ (self, handler, count=None):
        super (LibrariesTab, self).__init__ (handler)
        self.count = count

    def get_tab_title (self):
        return utils.gettext ('Libraries (%i)') % self.count

    def handle_request (self):
        self.handler.response.set_contents (self.get_tab ())

    def get_tab (self):
        objs = db.Branch.select (type=u'Library', parent_in_set=self.handler.record)
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

def initialize (handler):
    if handler.__class__.__name__ != 'SetHandler':
        return

    handler.register_application (OverviewTab (handler))

    cnt = handler.record.subsets.count()
    if cnt > 0:
        handler.register_application (SubsetsTab (handler, cnt))

    cnt = db.SetModule.count_related (subj=handler.record)
    if cnt == 0:
        return
    handler.register_application (ModulesTab (handler, cnt))

    cnt = db.Branch.select (type=u'Document', parent_in_set=handler.record).count ()
    if cnt > 0:
        handler.register_application (DocumentsTab (handler, cnt))

    cnt = db.Branch.select (type=u'Domain', parent_in_set=handler.record).count ()
    if cnt > 0:
        handler.register_application (DomainsTab (handler, cnt))

    cnt = db.Branch.select (
        db.Branch.type.is_in ((u'Application', u'Capplet', u'Applet')),
        parent_in_set=handler.record
        ).count ()
    if cnt > 0:
        handler.register_application (ProgramsTab (handler, cnt))

    cnt = db.Branch.select (type=u'Library', parent_in_set=handler.record).count ()
    if cnt > 0:
        handler.register_application (LibrariesTab (handler, cnt))

def initialize_application (handler, application):
    if handler.__class__.__name__ != 'SetHandler':
        return
    if application == 'subsets':
        handler.register_application (SubsetsTab (handler))
    elif application == 'modules':
        handler.register_application (ModulesTab (handler))
    elif application == 'documents':
        handler.register_application (DocumentsTab (handler))
    elif application == 'domains':
        handler.register_application (DomainsTab (handler))
    elif application == 'programs':
        handler.register_application (ProgramsTab (handler))
    elif application == 'libraries':
        handler.register_application (LibrariesTab (handler))
