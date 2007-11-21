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

import math
import os

import pulse.config
import pulse.db
import pulse.html
import pulse.scm
import pulse.utils

def main (path=[], query={}, http=True, fd=None):
    if len(path) == 3:
        modules = pulse.db.Resource.selectBy (ident=('/' + '/'.join(path)))
        if modules.count() == 0:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Module Not Found')
            # FIXME: this is not a good place to redirect
            kw['pages'] = [('mod', pulse.utils.gettext ('All Modules'))]
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the module %s') % path[2],
                **kw)
            page.output(fd=fd)
            return 404
        else:
            branch = modules[0].default_branch
            if branch == None:
                kw = {'http': http}
                kw['title'] = pulse.utils.gettext ('Default Branch Not Found')
                # FIXME: this is not a good place to redirect
                kw['pages'] = [('mod', pulse.utils.gettext ('All Modules'))]
                page = pulse.html.PageNotFound (
                    pulse.utils.gettext ('Pulse could not find a default branch for the module %s') % path[2],
                    **kw)
                page.output(fd=fd)
                return 404
    elif len(path) == 4:
        branches = pulse.db.Branch.selectBy (ident=('/' + '/'.join(path)))
        if branches.count() == 0:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Branch Not Found')
            modules = pulse.db.Resource.selectBy (ident=('/' + '/'.join(path[:-1])))
            if modules.count() > 0:
                module = modules[0]
                # FIXME: i18n
                kw['pages'] = [(module.ident, module.title)]
            else:
                kw['pages'] = []
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the branch %s of the module %s') % (path[3], path[2]),
                **kw)
            page.output(fd=fd)
            return 404
        else:
            branch = branches[0]
    else:
        # FIXME: redirect to /set or something
        pass

    return output_branch (branch, path, query, http, fd)


def output_branch (branch, path=[], query=[], http=True, fd=None):
    module = branch.resource
    checkout = pulse.scm.Checkout.from_record (branch, checkout=False, update=False)

    page = pulse.html.ResourcePage (branch, http=http)

    branches = pulse.db.Branch.selectBy (resource=module)
    branches = pulse.utils.attrsorted (list(branches), 'scm_branch')
    if len(branches) > 1:
        for b in branches:
            if b.ident != branch.ident:
                page.add_sublink (b.pulse_url, b.ident.split('/')[-1])
            else:
                page.add_sublink (None, b.ident.split('/')[-1])

    sep = False
    try:
        desc = branch.localized_desc
        page.add_fact (pulse.utils.gettext ('Description'), desc)
        sep = True
    except:
        pass

    # FIXME: use a JOIN
    rels = pulse.db.RecordBranchRelation.selectBy (pred=branch, verb='SetModule')
    if rels.count() > 0:
        sets = pulse.utils.attrsorted ([rel.subj for rel in rels], 'title')
        span = pulse.html.Span (*[pulse.html.Link(rel.subj) for rel in rels])
        span.set_divider (span.BULLET)
        page.add_fact (pulse.utils.gettext ('Release Sets'), span)
        sep = True

    if sep: page.add_fact_sep ()

    page.add_fact (pulse.utils.gettext ('Location'), checkout.location)

    if branch.data.has_key ('tarname'):
        page.add_fact_sep ()
        page.add_fact (pulse.utils.gettext ('Tarball Name'), branch.data['tarname'])
    if branch.data.has_key ('tarversion'):
        if not branch.data.has_key ('tarname'):
            page.add_fact_sep ()
        page.add_fact (pulse.utils.gettext ('Version'), branch.data['tarversion'])

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Developers
    # FIXME: use a JOIN
    box = pulse.html.InfoBox ('developers', pulse.utils.gettext ('Developers'))
    developers = pulse.db.BranchEntityRelation.selectBy (subj=branch, verb='ModuleMaintainer')
    developers = pulse.utils.attrsorted (list(developers), 'pred', 'title')
    if len(developers) > 0:
        for rel in developers:
            box.add_resource_link (rel.pred)
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No developers') ))
    columns.add_content (0, box)

    # Translations
    box = pulse.html.InfoBox ('translations', pulse.utils.gettext ('Translations'))
    columns.add_content (0, box)
    domains = pulse.db.Branch.selectBy (type='Domain', parent=branch)
    domains = pulse.utils.attrsorted (list(domains), 'title')
    if len(domains) > 0:
        for domain in domains:
            translations = pulse.db.Branch.selectBy (type='Translation', parent=domain)
            translations = pulse.utils.attrsorted (list(translations), 'title')
            exp = pulse.html.ExpanderBox (domain.ident.split('/')[-2],
                                          pulse.utils.gettext ('%s (%s)')
                                          % (domain.title, len(translations)))
            box.add_content (exp)
            vbox = pulse.html.VBox()
            exp.add_content (vbox)

            potlst = ['var', 'l10n'] + domain.ident.split('/')[1:]
            if domain.scm_dir == 'po':
                potlst.append (domain.parent.scm_module + '.pot')
            else:
                potlst.append (domain.scm_dir + '.pot')
            poturl = pulse.config.webroot + '/'.join (potlst)
            potfile = os.path.join (*potlst)
            vf = pulse.db.VarFile.selectBy (filename=potfile)
            if vf.count() > 0:
                linkspan = pulse.html.Span (divider=pulse.html.Span.SPACE)
                vbox.add_content (linkspan)
                vf = vf[0]
                linkspan.add_content (pulse.html.Link (poturl,
                                                       pulse.utils.gettext ('POT file'),
                                                       icon='download' ))
                # FIXME: i18n reordering
                linkspan.add_content (pulse.utils.gettext ('(%i messages)') % vf.statistic)
                linkspan.add_content (pulse.utils.gettext ('on %s') % str(vf.datetime))
            else:
                vbox.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                                       pulse.utils.gettext ('No POT file') ))

            grid = pulse.html.GridBox ()
            vbox.add_content (grid)
            if len(translations) == 0:
                grid.add_row (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                                   pulse.utils.gettext ('No translations') ))
            else:
                for translation in translations:
                    stat = pulse.db.Statistic.select ((pulse.db.Statistic.q.branchID == translation.id) &
                                                      (pulse.db.Statistic.q.type == 'Messages'),
                                                      orderBy='-daynum')
                    if stat.count() == 0:
                        grid.add_row (translation.scm_file[:-3])
                    else:
                        stat = stat[0]
                        untranslated = stat.total - stat.stat1 - stat.stat2
                        percent = math.floor(100 * (float(stat.stat1) / stat.total))
                        text = pulse.utils.gettext ('%i%% (%i/%i/%i)') % (
                            percent, stat.stat1, stat.stat2, untranslated)
                        grid.add_row (translation.scm_file[:-3], text)
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No domains') ))

    # Applications
    apps = pulse.db.Branch.selectBy (type='Application', parent=branch)
    apps = pulse.utils.attrsorted (list(apps), 'title')
    if len(apps) > 0:
        box = pulse.html.InfoBox ('applications', pulse.utils.gettext ('Applications'))
        columns.add_content (1, box)
        for app in apps:
            box.add_resource_link (app)

    # Applets
    applets = pulse.db.Branch.selectBy (type='Applet', parent=branch)
    applets = pulse.utils.attrsorted (list(applets), 'title')
    if len(applets) > 0:
        box = pulse.html.InfoBox ('applets', pulse.utils.gettext ('Applets'))
        columns.add_content (1, box)
        for applet in applets:
            box.add_resource_link (applet)

    # Libraries
    libs = pulse.db.Branch.selectBy (type='Library', parent=branch)
    libs = pulse.utils.attrsorted (list(libs), 'title')
    if len(libs) > 0:
        box = pulse.html.InfoBox ('libraries', pulse.utils.gettext ('Libraries'))
        columns.add_content (1, box)
        for lib in libs:
            box.add_resource_link (lib)

    # Documents
    box = pulse.html.InfoBox ('documents', pulse.utils.gettext ('Documents'))
    columns.add_content (1, box)
    docs = pulse.db.Branch.selectBy (type='Document', parent=branch)
    docs = pulse.utils.attrsorted (list(docs), 'title')
    if len(docs) > 0:
        for doc in docs:
            rlink = box.add_resource_link (doc)
            res = pulse.db.Branch.selectBy (parent=doc, type='Translation')
            rlink.add_fact_div (pulse.utils.gettext ('%i translations') % res.count())
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No documents') ))

    page.output(fd=fd)

    return 0

