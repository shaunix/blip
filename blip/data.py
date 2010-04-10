# Copyright (c) 2006, 2010  Shaun McCance  <shaunm@gnome.org>
#
# This file is part of Blip, a program for displaying various statistics
# of questionable relevance about software and the people who make it.
#
# Blip is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# Blip is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along
# with Blip; if not, write to the Free Software Foundation, 59 Temple Place,
# Suite 330, Boston, MA  0211-1307  USA.
#

import libxml2
import re

import blip.utils

BLIP_DATA_NS = 'http://blip-monitor.com/xmlns/ddl/1.0/'

class Data (object):
    def __init__ (self, filename):
        ctxt = libxml2.newParserCtxt ()
        self._doc = ctxt.ctxtReadFile (filename, None, 0)
        self._defaults = ()
        self.data = self._read_group (self._doc.getRootElement ())

    def print_data (self):
        self._print_data (self.data)

    def _print_data (self, data, indent=0):
        if isinstance (data, dict):
            for key in data.keys():
                if key.startswith ('__') or key.startswith ('blip:'):
                    continue
                val = data[key]
                if isinstance (val, basestring):
                    print (('  ' * indent) + '%s: %s') % (key, val)
                else:
                    print (('  ' * indent) + '%s:') % key
                    self._print_data (val, indent=(indent+1))
        elif isinstance (data, basestring):
            print data
        elif data is None:
            print ('  ' * indent) + '?'
        else:
            for item in data:
                print ('  ' * indent) + item

    def _read_group (self, node, data=None):
        if data is None:
            data = blip.utils.odict()
        olddefaults = self._defaults
        for el in xmliter(node):
            if el.type != 'element':
                continue
            if _get_ns(el) == BLIP_DATA_NS and el.name == 'defaults':
                self._defaults = (self._read_defaults (el),) + self._defaults
            elif _get_ns(el) == BLIP_DATA_NS and el.name == 'group':
                self._read_group (el, data=data)
            elif el.hasNsProp ('id', BLIP_DATA_NS):
                ndata = self._read_node (el)
                data[ndata['blip:id']] = ndata
            else:
                blip.utils.warn ('A node (%s) without an id was encountered while getting group data.'
                                 % el.name)
        self._defaults = olddefaults
        return data

    def _read_defaults (self, node):
        defs = {}
        for obj in xmliter(node):
            if obj.type != 'element':
                continue
            defs[obj.name] = data = blip.utils.odict()
            for el in xmliter(obj):
                if el.type != 'element':
                    continue
                key = el.name
                if el.hasNsProp ('id', BLIP_DATA_NS):
                    data.setdefault (key, {})
                    ndata = self._read_node (el, defaults=False)
                    data[key][ndata['blip:id']] = ndata
                elif el.hasNsProp ('idref', BLIP_DATA_NS):
                    data.setdefault (key, [])
                    data[key].append (el.nsProp ('idref', BLIP_DATA_NS))
                else:
                    data[key] = self._keyvalue (el)
        return defs

    def _read_node (self, node, data=None, defaults=True):
        if data is None:
            data = blip.utils.odict()

        data['blip:type'] = node.name
        if node.hasNsProp ('id', BLIP_DATA_NS):
            data['blip:id'] = node.nsProp ('id', BLIP_DATA_NS)

        # FIXME: this is giving crap, and we're not using it now anyway
        #for attr in node.get_properties ():
        #    if _get_ns(attr) is None:
        #        data[attr.name] = node.prop (attr.name)

        olddefaults = self._defaults

        for el in xmliter(node):
            if el.type != 'element':
                continue
            key = el.name
            if _get_ns(el) == BLIP_DATA_NS and key == 'defaults':
                self._defaults = (self._read_defaults (el),) + self._defaults
            elif _get_ns(el) == BLIP_DATA_NS and key == 'group':
                # FIXME: they probably should be
                blip.utils.warn ('Groups are not allowed in element nodes.')
            elif el.hasNsProp ('id', BLIP_DATA_NS):
                # Insert a dummy element, which we'll process
                # after we apply defaults
                data.setdefault (key, {})
                data[key][el.nsProp('id', BLIP_DATA_NS)] = blip.utils.odict ({'__node__': el})
            elif el.hasNsProp ('idref', BLIP_DATA_NS):
                data.setdefault (key, [])
                data[key].append (el.nsProp ('idref', BLIP_DATA_NS))
            else:
                data[key] = self._keyvalue (el)

        if defaults:
            self._apply_defaults (data)

        for key in data.keys():
            if not key.startswith ('__') and isinstance (data[key], dict):
                for id in data[key].keys():
                    ndata = data[key][id]
                    if ndata.has_key ('__node__'):
                        ndata['__parent__'] = data
                        self._read_node (ndata['__node__'], data=ndata)
                        del (ndata['__node__'])

        self._defaults = olddefaults
        return data

    def _apply_defaults (self, data):
        ndatas = []
        data.setdefault ('__defaults__', {})
        for defs in self._defaults:
            if defs.has_key (data['blip:type']):
                # String and list values are merged into data['__defaults__'],
                # which we then handle with the big block below.  Subthings
                # are inserted, but they don't have the default list applied
                # to them yet.  Instead, _merge_defaults appends them to
                # ndatas, and we take care of them further below.
                self._merge_defaults (data, defs[data['blip:type']], ndatas)

        # This is a little complicated, but less so than it looks.
        # The defaults properties (simple string and idref/list)
        # are placed temporarily into data['__defaults__'] by
        # _merge_defaults, and we now have to move them into
        # data, resolving cross references.  Rather than try to
        # construct a graph of cross reference dependencies, we
        # just iterate over data['__defaults__'] as many times as
        # needed, keeping track of whether we managed to merge a
        # property on each pass.
        res = CrossReferenceResolver (data)
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
            self._apply_defaults (ndata)

    def _merge_defaults (self, data, defs, ndatas):
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

                    ndata['blip:type'] = key
                    ndata['__parent__'] = data
                    self._merge_defaults (ndata, ndefs, ndatas)
                    ndatas.append (ndata)
            elif isinstance (val, list):
                data['__defaults__'].setdefault (key, [])
                data['__defaults__'][key].extend (val)
            else:
                #FIXME: be stricter
                pass

    def _keyvalue(self, node, allow_item=True):
        s = []
        l = []
        for child in xmliter(node):
            if child.isText ():
                s.append (child.getContent ())
            elif (allow_item and child.type == 'element' and
                  _get_ns(child) == BLIP_DATA_NS and child.name == 'item'):
                l.append (self._keyvalue (child, allow_item=False))
        if len(l) > 0:
            return l
        else:
            return ''.join (s)


class CrossReferenceError (blip.utils.BlipException):
    def __init__ (self, str):
        blip.utils.BlipException.__init__ (self, str)


class CrossReferenceResolver:
    pat = re.compile ('%\(([^)]*)\)')
    err = ('Error when trying to set the "%s" property for the ' +
           '%s "%s":  There is no %s containing the key "%s".')
    def __init__ (self, data):
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
                (keyt, keyi) = (self.data['blip:type'], str)
            else:
                (keyt, keyi) = str.split('/', 1)
            this = self.data
            while this != None:
                if this['blip:type'] == keyt and this.has_key (keyi):
                    if isinstance (this[keyi], list):
                        return this[keyi][0]
                    else:
                        return this[keyi]
                this = this.get ('__parent__', None)
            raise CrossReferenceError (self.err %
                                       (key,
                                        self.data.get('blip:type', 'None'),
                                        self.data.get('blip:id', '-'),
                                        keyt, keyi))
            return this
        return self.pat.sub (subsFunc, val)

def _get_ns (node):
    ns = node.ns()
    if ns is not None:
        return ns.getContent ()
    return None

def xmliter (node):
    """
    An iterator for libxml2 child nodes
    """
    child = node.children
    while child:
        yield child
        child = child.next
