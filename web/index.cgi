#!/usr/bin/env python

import Cookie
import getopt
import os
import sys
import cgi

from pulse import config, db, html, pages, utils
import pulse.response as core

def usage ():
    print >>sys.stderr, ('Usage: %s [options] [PATHINFO [QUERYSTRING]]' % sys.argv[0])

def main ():
    fd = None
    db.block_implicit_flushes ()
    utils.set_log_level (None)
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
            db.debug ()
        elif opt == '--log-level':
            utils.set_log_level (arg)
        elif opt == '--webroot':
            config.web_root = arg

    kw = {}
    http = True
    if len(args) > 0:
        http = False
        kw['path_info'] = args[0]
        if len(args) > 1:
            kw['query_string'] = args[1]

    request = core.HttpRequest (**kw)
    response = core.HttpResponse (http=http)

    try:
        token = request.cookies.get ('pulse_auth')
        token = utils.utf8dec (token.value)
        response.http_login = db.Login.get_login (token, os.getenv ('REMOTE_ADDR'))
        response.http_account = response.http_login.account
    except:
        pass

    try:
        if len (request.path) == 0:
            # FIXME
            page = html.Page ()
            page.set_title (utils.gettext ('Pulse'))
            cont = html.PaddingBox ()
            page.add_content (cont)
            types = pages.__all__
            mods = [utils.import_ ('pulse.pages.' + t) for t in types]
            for mod in mods:
                if not hasattr(mod, 'synopsis_sort'):
                    setattr (mod, 'synopsis_sort', 0)
            for mod in sorted (mods,
                               cmp=(lambda x, y:
                                    cmp(x.synopsis_sort, y.synopsis_sort) or
                                    cmp(x.__name__, y.__name__))):
                if hasattr (mod, 'synopsis'):
                    box = mod.synopsis ()
                    if isinstance (box, html.SidebarBox):
                        page.add_sidebar_content (box)
                    else:
                        cont.add_content (box)
            response.set_contents (page)
        else:
            mod = utils.import_ ('pulse.pages.' + request.path[0])
            handler = mod.get_request_handler (request, response)
            import pulse.applications
            for app in pulse.applications.__all__:
                app = pulse.utils.import_ ('pulse.applications.' + app)
                if hasattr (app, 'initialize'):
                    app.initialize (handler)
            app = request.query.get ('application')
            if app is not None:
                app = handler.applications[app]
                app.handle_request ()
            else:
                handler.handle_request ()
    except Exception, err:
        if not http:
            raise
        if request.query.has_key ('action'):
            page = html.AdmonBox (
                html.AdmonBox.error,
                utils.gettext (
                'Pulse does not know how to construct this page.  This is' +
                ' probably because some naughty little monkeys didn\'t finish' +
                ' their programming assignment.'))
        else:
            page = html.PageError (utils.gettext (
                'Pulse does not know how to construct this page.  This is' +
                ' probably because some naughty little monkeys didn\'t finish' +
                ' their programming assignment.'))
        response.set_contents (page)

    if debug:
        db.debug_summary ()

    status = response.http_status
    response.output (fd=fd)
    db.rollback ()
    if status == 200:
        return 0
    else:
        return status


if __name__ == "__main__":
    main ()
