#!/usr/bin/env python

import getopt
import os
import sys
sys.path.append ('/home/shaunm/Projects/pulse')
import cgi

import pulse.config
import pulse.html
import pulse.pages
import pulse.utils

def usage ():
    print >>sys.stderr, ('Usage: %s [options] [PATHINFO [QUERYSTRING]]' % sys.argv[0])

def main ():
    fd = None
    try:
        (opts, args) = getopt.gnu_getopt (sys.argv[1:], 'o:', ['output=', 'debug-db', 'webroot='])
    except getopt.GetoptError:
        usage ()
        sys.exit (1)
    debugger = None
    for (opt, arg) in opts:
        if opt in ('-o', '--output'):
            fd = file (arg, 'w')
        elif opt == '--debug-db':
            pulse.config.debug_db = True
        elif opt == '--webroot':
            pulse.config.webroot = arg
    if len(args) > 0:
        http = False
        pathInfo = args[0]
        if len(args) > 1:
            queryString = args[1]
        else:
            queryString = os.getenv ('QUERY_STRING')
    else:
        http = True
        pathInfo = os.getenv ('PATH_INFO')
        queryString = os.getenv ('QUERY_STRING')

    if pathInfo != None:
        path = pathInfo.split ('/')
        i = 0
        while (i < len (path)):
            if path[i] == '':
                path.pop (i)
            else:
                i += 1
    else:
        path = []

    if queryString != None:
        query = cgi.parse_qs (queryString, True)
        for key in query.keys():
            query[key] = query[key][0]
    else:
        query = {}

    retcode = 0
    if len (path) == 0:
        page = pulse.html.Page (http=http)
        page.set_title (pulse.utils.gettext ('Pulse'))
        lcont = pulse.html.LinkBoxContainer()
        page.add_content (lcont)
        for type in pulse.pages.__all__:
            mod = pulse.utils.import_ ('pulse.pages.' + type)
            if hasattr (mod, 'main'):
                lcont.add_link_box (pulse.config.webroot + type, type)
        page.output (fd=fd)
    else:
        if not http:
            mod = pulse.utils.import_ ('pulse.pages.' + path[0])
            retcode = mod.main (path=path, query=query, http=http, fd=fd)
        else:
            try:
                mod = pulse.utils.import_ ('pulse.pages.' + path[0])
                retcode =  mod.main (path=path, query=query, http=http, fd=fd)
            except:
                kw = {'http': http}
                kw['title'] = pulse.utils.gettext ('Bad Monkeys')
                page = pulse.html.PageError (pulse.utils.gettext (
                    'Pulse does not know how to construct this page.  This is' +
                    ' probably because some naughty little monkeys didn\'t finish' +
                    ' their programming assignment.'))
                page.output(fd=fd)
                retcode = 500
    if debugger != None:
        print '%i SELECTS, %i UPDATES' % (debugger.selects, debugger.updates)
    return retcode


if __name__ == "__main__":
    main ()
