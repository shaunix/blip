#!/usr/bin/env python

import getopt
import os
import sys
import cgi

import pulse.config
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
    for (opt, arg) in opts:
        if opt in ('-o', '--output'):
            fd = file (arg, 'w')
        elif opt == '--debug-db':
            pulse.config.debug_db = True
        elif opt == '--webroot':
            pulse.config.web_root = arg

    # If we're not using the debugging, just turn off Django's DEBUG
    # setting.  This is set to True in pulse.config, because logging
    # in Pulse piggybacks off Django's debug system.  But that's just
    # wasted CPU cycles when we're making pages for the outside world.
    if not getattr (pulse.config, 'debug_db', False):
        pulse.config.DEBUG = False

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

    # It's important that we don't do this at the top, because this
    # will cause pulse.models to be imported, and we have to be able
    # to set pulse.config.DEBUG to False before that.
    import pulse.html as html
    retcode = 0
    if len (path) == 0:
        page = html.Page (http=http)
        page.set_title (pulse.utils.gettext ('Pulse'))
        cont = html.PaddingBox ()
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
        page.output (fd=fd)
    else:
        if not http:
            mod = pulse.utils.import_ ('pulse.pages.' + path[0])
            retcode = mod.main (path, query, http=http, fd=fd)
        else:
            try:
                mod = pulse.utils.import_ ('pulse.pages.' + path[0])
                retcode =  mod.main (path, query, http=http, fd=fd)
            except:
                kw = {'http': http}
                kw['title'] = pulse.utils.gettext ('Bad Monkeys')
                page = html.PageError (pulse.utils.gettext (
                    'Pulse does not know how to construct this page.  This is' +
                    ' probably because some naughty little monkeys didn\'t finish' +
                    ' their programming assignment.'))
                page.output(fd=fd)
                retcode = 500
    if getattr (pulse.config, 'debug_db', False):
        print ('%i SELECT statements in %.3f seconds' %
               (pulse.models.PulseDebugCursor.debug_select_count,
                pulse.models.PulseDebugCursor.debug_select_time))
    return retcode


if __name__ == "__main__":
    main ()
