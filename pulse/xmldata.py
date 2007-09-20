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

import re
import xml.dom.minidom

import pulse.utils as utils

def get_data (file):
    dom = xml.dom.minidom.parse (file)
    return get_group_data (dom.firstChild)

def get_group_data (node, **kw):
    if kw.has_key ('data'):
        data = kw['data']
        del (kw['data'])
    else:
        data = utils.odict()
    defaults = kw.get ('defaults', ())
    for el in node.childNodes:
        if el.nodeType == el.ELEMENT_NODE:
            if el.nodeName == 'defaults':
                kw['defaults'] = (get_defaults_data (el, **kw),) + defaults
            elif el.nodeName == 'group':
                get_group_data (el, data=data, **kw)
            elif el.getAttribute ('id'):
                ndata = get_node_data (el, **kw)
                data[ndata['id']] = ndata
            else:
                utils.warn ('A node (%s) without an id was encountered while getting group data.'
                      %el.nodeName)
    return data

def get_defaults_data (node, **kw):
    defs = {}
    for obj in node.childNodes:
        if obj.nodeType == obj.ELEMENT_NODE:
            defs[obj.nodeName] = data = utils.odict()
            for el in obj.childNodes:
                if el.nodeType == el.ELEMENT_NODE:
                    key = el.nodeName
                    if el.getAttribute ('id'):
                        data.setdefault (key, {})
                        ndata = get_node_data (el, apply_defaults=False, **kw)
                        data[key][ndata['id']] = ndata
                    elif el.getAttribute ('idref'):
                        data.setdefault (key, [])
                        data[key].append (el.getAttribute ('idref'))
                    else:
                        data[key] = keyvalue (el)
    return defs

def get_node_data (node, **kw):
    if kw.has_key ('data'):
        data = kw['data']
        del (kw['data'])
    else:
        data = utils.odict()
    defaults = kw.get ('defaults', ())

    data['__type__'] = node.nodeName
    if node.getAttribute ('id'): data['id'] = node.getAttribute ('id')

    for i in range (node.attributes.length):
        attr = node.attributes.item(i).nodeName
        if attr not in ['id', 'idref', 'lang']:
            data[attr] = node.getAttribute (attr)
    for el in node.childNodes:
        if el.nodeType == el.ELEMENT_NODE:
            key = el.nodeName
            if key == 'defaults':
                kw['defaults'] = (get_defaults_data (el, **kw),) + defaults
            elif key == 'group':
                # FIXME: they probably should be
                utils.warn ('Groups are not allowed in element nodes.')
            elif el.getAttribute ('id'):
                # Insert a dummy element, which we'll process
                # after we apply defaults
                data.setdefault (key, {})
                data[key][el.getAttribute('id')] = utils.odict ({'__node__': el})
            elif el.getAttribute ('idref'):
                data.setdefault (key, [])
                data[key].append (el.getAttribute ('idref'))
            else:
                data[key] = keyvalue (el)

    if kw.get ('apply_defaults', True):
        apply_defaults_list (data, **kw)

    for key in data.keys():
        if not key.startswith ('__') and isinstance (data[key], dict):
            for id in data[key].keys():
                ndata = data[key][id]
                if ndata.has_key ('__node__'):
                    ndata['__parent__'] = data
                    get_node_data (ndata['__node__'], data=ndata, **kw)
                    del (ndata['__node__'])

    return data

def apply_defaults_list (data, **kw):
    ndatas = []
    data.setdefault ('__defaults__', {})
    for defs in kw.get ('defaults', ()):
        if defs.has_key (data['__type__']):
            # String and list values are merged into data['__defaults__'],
            # which we then handle with the big block below.  Subthings
            # are inserted, but they don't have the default list applied
            # to them yet.  Instead, merge_defaults_data appends them to
            # ndatas, and we take care of them further below.
            merge_defaults_data (data, defs[data['__type__']], ndatas, **kw)

    # This is a little complicated, but less so than it looks.
    # The defaults properties (simple string and idref/list)
    # are placed temporarily into data['__defaults__'] by
    # merge_defaults_data, and we now have to move them into
    # data, resolving cross references.  Rather than try to
    # construct a graph of cross reference dependencies, we
    # just iterate over data['__defaults__'] as many times as
    # needed, keeping track of whether we managed to merge a
    # property on each pass.
    res = CrossReferenceResolver (data, **kw)
    while len (data['__defaults__']) > 0:
        trim = False
        for key in data['__defaults__'].keys():
            try:
                if isinstance (data['__defaults__'][key], list):
                    # We set trim to True if we were able to merge any
                    # of the values in the list.  We remove the list
                    # itself only if we've merged everything from it.
                    # It might take multiple iterations to get all the
                    # list elements merged.
                    data.setdefault (key, [])
                    i = 0
                    while i < len (data['__defaults__'][key]):
                        try:
                            val = res.resolve (key, data['__defaults__'][key][i])
                            if val not in data[key]:
                                data[key].append (val)
                            data['__defaults__'][key].pop (i)
                            trim = True
                        except CrossReferenceError:
                            i += 1
                    if len (data['__defaults__'][key]) == 0:
                        del (data['__defaults__'][key])
                elif not data.has_key (key):
                    # The value is a simple string.  We try to merge
                    # it in, setting trim to True if we succeed.
                    val = res.resolve (key, data['__defaults__'][key])
                    data[key] = val
                    del (data['__defaults__'][key])
                    trim = True
                else:
                    # This property was explicitly set, so we don't
                    # even bother with the default.
                    del (data['__defaults__'][key])
                    trim = True
            except CrossReferenceError:
                # We usually let the error pass, because this key might
                # be resolved on a later iteration.  But if this is the
                # last key and we haven't merged any oter keys on this
                # iteration, then we have a problem and we re-raise.
                if key == data['__defaults__'].keys()[-1] and not trim:
                    raise
    del (data['__defaults__'])

    for ndata in ndatas:
        apply_defaults_list (ndata, **kw)

def merge_defaults_data (data, defs, ndatas, **kw):
    data.setdefault ('__defaults__', {})
    for key in defs.keys():
        val = defs[key]
        if isinstance (val, basestring):
            data['__defaults__'].setdefault (key, val)
        elif isinstance (val, dict):
            data.setdefault (key, {})
            for i in defs[key].keys():
                # Create a new sub-element, applying all defaults to it
                # The values set here are merged into ndata['__defaults__'],
                # but additional defaults from other definitions aren't yet
                # merged.  Instead, we append ndata to ndatas, which was
                # handed to us by apply_defaults_list.  It will then iterate
                # over ndatas with apply_defaults_list.  This way, the cross
                # references are not resolved until after all the parents
                # have had all their defaults applied.

                # FIXME: resolve id from i
                # id = pat.sub (subsFunc, i)
                id = i
                ndata = data[key].setdefault (id, {})
                ndefs = defs[key][i]

                ndata['__type__'] = key
                ndata['__parent__'] = data
                merge_defaults_data (ndata, ndefs, ndatas, **kw)
                ndatas.append (ndata)
        elif isinstance (val, list):
            data['__defaults__'].setdefault (key, [])
            data['__defaults__'][key].extend (val)
        else:
            #FIXME: be stricter
            pass

def keyvalue(node, allow_item=True):
    s = []
    l = []
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE:
            s.append (child.data)
        elif allow_item and child.nodeType == child.ELEMENT_NODE and child.tagName == 'item':
            l.append (keyvalue (child, allow_item=False))
    if len(l) > 0:
        return l
    else:
        return ''.join (s)

class CrossReferenceError (utils.PulseException):
    def __init__ (self, str):
        utils.PulseException.__init__ (self, str)

class CrossReferenceResolver:
    pat = re.compile ('%\(([^)]*)\)')
    err = ('Error when trying to set the "%s" property for the ' +
           '%s "%s":  There is no %s containing the key "%s".')
    def __init__ (self, data, **kw):
        self.data = data
        pass
    # FIXME: if we ever get a list on a cross-reference (which we do),
    # then return a list of value strings, one for each value in the
    # cross product of all list-returning references.  Currently, we
    # just take the first.  This will require changes above whenever
    # resolve is called.
    def resolve (self, key, val):
        def subsFunc(match):
            str = match.group (1)
            if str.find ('/') == -1:
                (keyt, keyi) = (self.data['__type__'], str)
            else:
                (keyt, keyi) = str.split('/', 1)
            this = self.data
            while this != None:
                if this['__type__'] == keyt and this.has_key (keyi):
                    if isinstance (this[keyi], list):
                        return this[keyi][0]
                    else:
                        return this[keyi]
                this = this.get ('__parent__', None)
            raise CrossReferenceError (self.err %
                                       (key,
                                        self.data.get('__type__', 'None'),
                                        self.data.get('id', '-'),
                                        keyt, keyi))
            return this
        return self.pat.sub (subsFunc, val)
