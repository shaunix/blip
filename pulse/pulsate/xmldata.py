#!/usr/bin/env python
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

import sqlobject as sql

import pulse.config as config
import pulse.db as db
import pulse.xmldata as xmldata
import pulse.utils as utils

synop = 'update data from XML files'
def usage (fd=sys.stderr):
    print >>fd, ('Usage: %s xml' % sys.argv[0])

def updateResource (cls, ident, data, defs={}):
    cols = cls.get_column_defs()
    attr = {}
    attr.update (defs)
    attr['ident'] = ident
    rows = cls.selectBy (**attr)
    for col in cols:
        if col == 'ident':
            continue
        if isinstance (cols[col], sql.StringCol) or isinstance (cols[col], sql.UnicodeCol):
            attr[col] = data.get (col)
    if rows.count() > 0:
        row = rows[0]
        for key in attr.keys():
            if (getattr (row, key) == attr[key] or attr[key] == None or key == 'ident'):
                del attr[key]
        if len (attr) > 0:
            row.set (**attr)
        resource = row
    else:
        resource = cls (**attr)

    # Set the translated text columns
    for prop in dir (cls):
        if isinstance (getattr(cls, prop), db.textprop):
            if data.has_key (prop):
                resource.set_text (prop, 'C', data[prop])

    return resource

def updateRelations (resource, idents, verb, comment=None, invert=False):
    dbrels = {}
    for rel in resource.get_related (verb, invert=invert):
        dbrels[rel.resource.ident] = rel
    xmlrels = map (lambda s: s, idents)
    for id in dbrels.keys():
        if id in xmlrels:
            if comment != None and dbrels[id].comment != comment:
                dbrels[id].comment = comment
            xmlrels.remove (id)
        else:
            dbrels[id].destroySelf ()
    for id in xmlrels:
        res = db.Resource.select (db.Resource.q.ident == id)
        if res.count() > 0:
            resource.add_related (res[0], verb, comment, invert=invert)
        else:
            utils.warn ('Could not locate resource "%s" when setting the "%s" of the resource "%s".'
                  % (id, verb, resource.id))

def updateModule (module):
    mrec = updateResource (db.Module, ('modules/' + module['id']), module)

    if module.has_key ('rcs_server'):
        rcsrec = db.RcsServer.selectBy (ident = ('rcs/' + module['rcs_server'][0]))
        if rcsrec.count() > 0:
            mrec.rcs_server = rcsrec[0]
        else:
            utils.warn ('Could not locate the RCS server "%s" for the module "%s".'
                  % (module['rcs_server'][0], module['id']))

    if module.has_key ('maintainer'):
        updateRelations (mrec,
                         map (lambda s: 'people/' + s, module['maintainer']),
                         'developer', 'maintainer')

    if module.has_key ('mail_list'):
        updateRelations (mrec,
                         map (lambda s: 'lists/' + s, module['mail_list']),
                         'mail_list')

    # Create the branches in the module
    for branch in module.get('branch', {}).values():
        brec = updateResource (db.Branch,
                               ('modules/%s/%s' % (module['id'], branch['id'])),
                               branch,
                               {'moduleID': mrec.id})

        if branch.has_key ('rcs_server'):
            rcsrec = db.RcsServer.selectBy (ident = ('rcs/' + branch['rcs_server'][0]))
            if rcsrec.count() > 0:
                brec.rcs_server = rcsrec[0]
            else:
                utils.warn ('Could not locate the RCS server "%s" for the branch "%s".'
                  % (branch['rcs_server'][0], branch['id']))
        
        # Create the translation domains in the branch
        for domain in branch.get('domain', {}).values():
            drec = updateResource (db.Domain,
                                   '/'.join (['i18n',
                                              module['id'],
                                              branch['id'],
                                              domain['id']]),
                                   domain,
                                   {'branchID': brec.id})

            if domain.has_key ('rcs_server'):
                rcsrec = db.RcsServer.selectBy (ident = ('rcs/' + domain['rcs_server'][0]))
                if rcsrec.count() > 0:
                    drec.rcs_server = rcsrec[0]
                else:
                    utils.warn ('Could not locate the RCS server "%s" for the domain "%s".'
                          % (domain['rcs_server'][0], domain['id']))

        # I think we've got this automatically from rcs, so we can remove this
        # Create the documents in the branch
##         for document in branch.get('document', {}).values():
##             drec = updateResource (Document,
##                                    '/'.join (['docs',
##                                               module['id'],
##                                               branch['id'],
##                                               document['id']]),
##                                    document,
##                                    {'branchID': brec.id})

##             if document.has_key ('rcs_server'):
##                 rcsrec = RcsServer.selectBy (ident = ('rcs/' + document['rcs_server'][0]))
##                 if rcsrec.count() > 0:
##                     drec.rcs_server = rcsrec[0]
##                 else:
##                     warn ('Could not locate the RCS server "%s" for the document "%s".'
##                           % (document['rcs_server'][0], document['id']))

def updateTranslationTeam (team):
    rec = updateResource (db.TranslationTeam, ('l10n/' + team['id']), team)

    if team.has_key ('coordinator'):
        updateRelations (rec,
                         map (lambda s: 'people/' + s, team['coordinator']),
                         'member', 'coordinator')

def main (argv):
    db.create_tables ()

    data = xmldata.getData (config.datadir ('xml/lists.xml'))
    for val in data.values():
        updateResource (db.MailList, ('lists/' + val['id']), val)

    data = xmldata.getData (config.datadir ('xml/people.xml'))
    for val in data.values():
        updateResource (db.Person, 'people/' + val['id'], val)

    data = xmldata.getData (config.datadir ('xml/l10n-teams.xml'))
    for val in data.values():
        updateTranslationTeam (val)

    data = xmldata.getData (config.datadir ('xml/modules.xml'))
    for val in data.values():
        if val['__type__'] == 'server':
            updateResource (db.RcsServer, 'rcs/' + val['id'], val)
        elif val['__type__'] == 'module':
            updateModule (val)

    return 0
