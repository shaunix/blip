#!/usr/bin/env python

import getopt
import os
import sys
sys.path.append ('/shaunm/Projects/pulse')
import cgi

import pulse.html
import pulse.utils

def usage ():
    print >>sys.stderr, ('Usage: %s [options] [PATHINFO [QUERYSTRING]]' % sys.argv[0])

def main ():
    fd = None
    try:
        (opts, args) = getopt.gnu_getopt (sys.argv[1:], 'o:', ['output='])
    except getopt.GetoptError:
        usage ()
        sys.exit (1)
    for (opt, arg) in opts:
        if opt in ('-o', '--output'):
            fd = file (arg, 'w')
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

    if len (path) == 0:
        # FIXME: show index
        pass
    else:
        try:
            mod = pulse.utils.import_ ('pulse.pages.' + path[0])
            return mod.main (path=path, query=query, http=http, fd=fd)
        except:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Bad Monkeys')
            page = pulse.html.PageError (pulse.utils.gettext (
                'Pulse does not know how to construct this page.  This is' +
                ' probably because some naughty little monkeys didn\'t finish' +
                ' their programming assignment.'))
            page.output(fd=fd)
            return 500

if __name__ == "__main__":
    main ()
