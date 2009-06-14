#!/usr/bin/env python

import Cookie
import getopt
import os
import sys
import StringIO

from pulse import config, core, db, html, pages, utils

def app(environ, start_response):
    mfile = StringIO.StringIO()

    mapping = {}
    for key, value in environ.items():
        mapping[key.lower()] = value
    request = core.HttpRequest (**mapping)
    response = core.HttpResponse (http=False)

    token = request.cookies.get ('pulse_auth')
    if token:
        token = utils.utf8dec (token.value)
        response.http_login = db.Login.get_login (token, environ['REMOTE_ADDR'])
        response.http_account = response.http_login.account


    if len (request.path) == 0:
        mod = utils.import_ ('pulse.pages.__index__')
    else:
        mod = utils.import_ ('pulse.pages.' + request.path[0])
    handler = mod.get_request_handler (request, response)
    import pulse.applications
    appreq = request.query.get ('application')
    for app in pulse.applications.__all__:
        app = pulse.utils.import_ ('pulse.applications.' + app)
        if appreq is None:
            if hasattr (app, 'initialize'):
                app.initialize (handler)
        else:
            if hasattr (app, 'initialize_application'):
                app.initialize_application (handler, appreq)
    app = None
    if appreq is not None:
        app = handler.get_application (appreq)
    if app is not None:
        app.handle_request ()
    else:
        handler.handle_request ()
    if not response.has_contents ():
        raise utils.PulseException ('No response contents')


    status = response.http_status
    response.output (fd=mfile)

    db.rollback ()

    start_response('200 OK', [('Content-Type', response.http_content_type)])
    data = mfile.getvalue()

    return [data]


if __name__ == '__main__':
    from werkzeug import DebuggedApplication

    root = DebuggedApplication(app, evalex=True)
    root.root = '/'

    from werkzeug import run_simple
    run_simple('localhost', 4000, root)


