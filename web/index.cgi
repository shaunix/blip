#!/usr/bin/env python

import Cookie
import getopt
import os
import sys
import cgi

import pulse.config
import pulse.db
import pulse.html
import pulse.pages
import pulse.response
import pulse.utils

def usage ():
    print >>sys.stderr, ('Usage: %s [options] [PATHINFO [QUERYSTRING]]' % sys.argv[0])

def main ():
    fd = None
    pulse.utils.set_log_level (None)
    try:
        (opts, args) = getopt.gnu_getopt (sys.argv[1:], 'o:',
                                          ['output=', 'debug-db', 'log-level=', 'webroot='])
    except getopt.GetoptError:
        usage ()
        sys.exit (1)
    debug = False
    for (opt, arg) in opts:
        if opt in ('-o', '--output'):
            fd = file (arg, 'w')
        elif opt == '--debug-db':
            debug = True
            pulse.db.debug ()
        elif opt == '--log-level':
            pulse.utils.set_log_level (arg)
        elif opt == '--webroot':
            pulse.config.web_root = arg

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
        path = pulse.utils.utf8dec (pathInfo).split ('/')
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
            query[key] = pulse.utils.utf8dec (query[key][0])
    else:
        query = {}

    retcode = 0

    response = pulse.response.HttpResponse (http=http)

    try:
        ck = Cookie.SimpleCookie ()
        ck.load (os.getenv ('HTTP_COOKIE') or '')
        token = ck.get('pulse_auth')
        token = token.value
        response.http_login = pulse.db.Login.get_login (token, os.getenv ('REMOTE_ADDR'))
        response.http_account = response.http_login.account
    except:
        pass

    if len (path) == 0:
        page = pulse.html.Page ()
        page.set_title (pulse.utils.gettext ('Pulse'))
        cont = pulse.html.PaddingBox ()
        page.add_content (cont)
        types = pulse.pages.__all__
        mods = [pulse.utils.import_ ('pulse.pages.' + t) for t in types]
        for mod in mods:
            if not hasattr(mod, 'synopsis_sort'):
                setattr (mod, 'synopsis_sort', 0)
        for mod in sorted (mods,
                           cmp=(lambda x, y:
                                cmp(x.synopsis_sort, y.synopsis_sort) or
                                cmp(x.__name__, y.__name__))):
            if hasattr (mod, 'synopsis'):
                box = mod.synopsis ()
                if isinstance (box, pulse.html.SidebarBox):
                    page.add_sidebar_content (box)
                else:
                    cont.add_content (box)
        response.set_contents (page)
    else:
        try:
            mod = pulse.utils.import_ ('pulse.pages.' + path[0])
            mod.main (response, path, query)
        except:
            if not http:
                raise
            if query.has_key ('ajax'):
                page = pulse.html.AdmonBox (
                    pulse.html.AdmonBox.error,
                    pulse.utils.gettext (
                    'Pulse does not know how to construct this page.  This is' +
                    ' probably because some naughty little monkeys didn\'t finish' +
                    ' their programming assignment.'))
            else:
                page = pulse.html.PageError (pulse.utils.gettext (
                    'Pulse does not know how to construct this page.  This is' +
                    ' probably because some naughty little monkeys didn\'t finish' +
                    ' their programming assignment.'))
            response.set_contents (page)

    if debug:
        pulse.db.debug_summary ()

    status = response.http_status
    response.output (fd=fd)
    pulse.db.rollback ()
    if status == 200:
        return 0
    else:
        return status


if __name__ == "__main__":
    main ()
