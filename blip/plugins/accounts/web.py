# Copyright (c) 2006-2010  Shaun McCance  <shaunm@gnome.org>
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

import cgi
import crypt
import datetime
import os
import random
import re

import blinq.config
import blinq.reqs.web

import blip.db
import blip.html
import blip.utils
import blip.web

################################################################################
## Basic Account Handler

class BasicAccountHandler (blip.web.AccountHandler, blip.html.HeaderLinksProvider):
    account_handler = 'basic'
    can_register = True

    @classmethod
    def locate_account (cls, request):
        token = request.cookies.get ('blip_auth')
        if token:
            token = blip.utils.utf8dec (token.value)
            try:
                login = blip.db.Login.get_login (token, request.getenv('REMOTE_ADDR'))
                request.account = login.account
                return True
            except:
                pass
        return False

    @classmethod
    def add_header_links (cls, page, request):
        if len(request.path) > 0 and request.path[0] == 'account':
            pass
        elif request.account is None:
            page.add_header_link (blinq.config.web_root_url + 'account/login',
                                  blip.utils.gettext ('Log in'))
            page.add_header_link (blinq.config.web_root_url + 'account/register',
                                  blip.utils.gettext ('Register'))
        else:
            page.add_header_link (blinq.config.web_root_url + 'account/logout',
                                  blip.utils.gettext ('Log out'))

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] != 'account':
            return None

        response = None
        if len(request.path) < 2:
            if request.query.get('q') == 'watch':
                response = cls.respond_watch (request)
            elif request.query.get('q') == 'unwatch':
                response = cls.respond_unwatch (request)
        elif request.path[1] == 'login':
            if request.query.get('q') == 'submit':
                response = cls.respond_login_submit (request)
            else:
                response = cls.respond_login (request)
        elif request.path[1] == 'register':
            if request.query.get('q') == 'submit':
                response = cls.respond_register_submit (request)
            else:
                response = cls.respond_register (request)
        elif request.path[1] == 'auth':
            if request.query.get('q') == 'resend':
                response = cls.respond_auth_resend (request)
            else:
                response = cls.respond_auth (request)
        elif request.path[1] == 'logout':
            response = cls.respond_logout (request)

        return response

    @classmethod
    def respond_login (cls, request, admon=None):
        response = blip.web.WebResponse (request)
        page = blip.html.Page (request=request)
        page.set_title (blip.utils.gettext ('Log In'))
        response.payload = page

        pad = blip.html.PaddingBox ()
        page.add_content (pad)

        if admon is not None:
            pad.add_content (admon)

        section = blip.html.Div(html_id='accountform')
        pad.add_content (section)

        form = blip.html.Form ('GET', 'javascript:account_login()')
        section.add_content (form)

        table = blip.html.Table ()
        form.add_content (table)

        table.add_row (
            blip.utils.gettext ('Username:'),
            blip.html.TextInput ('username') )
        table.add_row (
            blip.utils.gettext ('Password:'),
            blip.html.TextInput ('password', password=True) )
        span = blip.html.Span ()
        span.add_content (blip.html.SubmitButton ('login', 'Log In'))
        if cls.can_register:
            span.add_content (blip.utils.gettext (' or '))
            span.add_content (blip.html.Link (blinq.config.web_root_url + 'account/register',
                                              blip.utils.gettext ('create an account')))
        table.add_row ('', span)

        return response

    @classmethod
    def respond_login_submit (cls, request):
        response = blip.web.WebResponse (request)
        username = request.post_data.get ('username', u'')
        password = request.post_data.get ('password', u'')
        admon = None
        if username == u'' or password == u'':
            admon = blip.html.AdmonBox (blip.html.AdmonBox.error,
                                        blip.utils.gettext('Please enter your username and password.'))
            response.payload = admon
            return response
        account = blip.db.Account.get (username)
        try:
            if account is None:
                raise blip.utils.BlipException('No account found')
            if account.check_type == 'new':
                span = blip.html.Span(divider=blip.html.SPACE)
                span.add_content (blip.utils.gettext('You have not yet verified your email address.'))
                lnk = blinq.config.web_root_url + 'account/auth?q=resend&email=' + account.email
                lnk = 'javascript:replace("accountform", "%s")' % lnk
                lnk = blip.html.Link (lnk,
                                      blip.utils.gettext('Request new authorization token.'))
                span.add_content (lnk)
                admon = blip.html.AdmonBox (blip.html.AdmonBox.error, span)
                raise blip.utils.BlipException()
            if account.password != crypt.crypt (password, 'pu'):
                raise blip.utils.BlipException()
            token = blip.utils.get_token ()
            login = blip.db.Login.set_login (account, token, os.getenv ('REMOTE_ADDR'))
            json = blinq.reqs.web.JsonPayload ()
            json.set_data ({'location': blinq.config.web_root_url + 'home',
                            'token': token
                            })
            response.payload = json
        except Exception, err:
            blip.db.rollback (blip.db.Account)
            if admon is None:
                admon = blip.html.AdmonBox (blip.html.AdmonBox.error,
                                            blip.utils.gettext('Invalid username or password.'))
            response.payload = admon
            return response
        else:
            blip.db.flush (blip.db.Account)
            blip.db.commit (blip.db.Account)
        return response

    @classmethod
    def respond_register (cls, request):
        response = blip.web.WebResponse (request)
        page = blip.html.Page (request=request)
        page.set_title (blip.utils.gettext ('Create New Account'))
        response.payload = page

        pad = blip.html.PaddingBox ()
        page.add_content (pad)

        section = blip.html.Div(html_id='accountform')
        pad.add_content (section)

        form = blip.html.Form ('GET', 'javascript:account_register()')
        section.add_content (form)

        table = blip.html.Table ()
        form.add_content (table)

        table.add_row (
            blip.utils.gettext ('Name:'),
            blip.html.TextInput ('realname') )
        table.add_row (
            blip.utils.gettext ('Username:'),
            blip.html.TextInput ('username') )
        table.add_row (
            blip.utils.gettext ('Email:'),
            blip.html.TextInput ('email') )
        table.add_row (
            blip.utils.gettext ('Password:'),
            blip.html.TextInput ('password1', password=True) )
        table.add_row (
            blip.utils.gettext ('Confirm:'),
            blip.html.TextInput ('password2', password=True) )
        span = blip.html.Span ()
        span.add_content (blip.html.SubmitButton ('create', 'Create'))
        span.add_content (blip.utils.gettext (' or '))
        span.add_content (blip.html.Link (blinq.config.web_root_url + 'account/login',
                                          blip.utils.gettext ('log in')))
        table.add_row ('', span)

        return response

    @classmethod
    def send_authorization_token (cls, user, request):
        # Uncomment *ONLY* for testing on non-production systems without
        # a mail server. Do not do this on a production server. Ever.
        #div = blip.html.Div('%saccount/auth/%s' % (blinq.config.web_root_url, user.check_hash))
        #blip.db.flush (blip.db.Account)
        #blip.db.commit (blip.db.Account)
        #return div

        from blip.mail import Mail
        mail = Mail (blip.utils.gettext ('Confirm New Blip Account'))
        mail.add_recipient (user.email)
        mail.add_content (blip.utils.gettext ('Hello %s') % user.data.get('realname', user.email))
        mail.add_content (blip.utils.gettext (
                'You have registered a Blip account. To complete your account registration,\n' +
                'you need to verify your email address. Please visit the URL below.'))
        mail.add_content ('%saccount/auth/%s' % (blinq.config.web_root_url, user.check_hash))
        mail.send ()
        div = blip.html.Div (blip.utils.gettext (
                'Blip has sent you a confirmation email.  Please visit the link' +
                ' in that email to complete your registration.'
                ))
        return div

    @classmethod
    def respond_register_submit (cls, request):
        response = blip.web.WebResponse (request)
        realname = request.post_data.get ('realname', '')
        if realname == '':
            admon = blip.html.AdmonBox (blip.html.AdmonBox.error,
                                        blip.utils.gettext('Please enter your name.'))
            response.payload = admon
            return response
        username = request.post_data.get ('username', '')
        if not re.match ('[a-zA-Z0-9_-]{4,20}$', username):
            admon = blip.html.AdmonBox (blip.html.AdmonBox.error,
                                        blip.utils.gettext(
                    'Please enter a valid username. Usernames must be at least four characters' +
                    ' long, and may only contain alphanumeric characters (a-z, A-Z, 0-9), underscores' +
                    ' (_), and hyphens (-).'
                    ))
            response.payload = admon
            return response
        email = request.post_data.get ('email', '')
        # Regular expression more or less from bugzilla
        if not re.match ('[\w.+=-]+@[\w.-]+\.[\w-]+', email):
            admon = blip.html.AdmonBox (blip.html.AdmonBox.error,
                                        blip.utils.gettext('Please enter a valid email address.'))
            response.payload = admon
            return response
        password = request.post_data.get ('password', '')
        if len(password) < 8:
            admon = blip.html.AdmonBox (blip.html.AdmonBox.error,
                                        blip.utils.gettext(
                    'Please enter a valid password. Passwords must be at least eight characters long.'
                    ))
            response.payload = admon
            return response
        try:
            ident = u'/person/' + username
            if (blip.db.Account.select (username=username).count() > 0 or
                blip.db.Entity.select (ident=ident).count() > 0):
                admon = blip.html.AdmonBox (blip.html.AdmonBox.error,
                                            blip.utils.gettext(
                        'Username already in use.  Please choose another username.'))
                response.payload = admon
                return response
            if (blip.db.Account.select (email=email).count() > 0):
                admon = blip.html.AdmonBox (blip.html.AdmonBox.error,
                                            blip.utils.gettext(
                        'Email address already in use.'))
                response.payload = admon
                return response
            person = blip.db.Entity (ident, u'Person', __blip_store__=blip.db.Account)
            token = blip.utils.get_token ()
            blip.db.rollback ()
            user = blip.db.Account (username=username,
                                    password=crypt.crypt(password, 'pu'),
                                    person_ident=person.ident,
                                    email=email,
                                    check_time=datetime.datetime.utcnow(),
                                    check_type='new',
                                    check_hash=token)
            user.data['realname'] = realname
            response.payload = cls.send_authorization_token (user, request)
        except Exception, err:
            blip.db.rollback (blip.db.Account)
            admon = blip.html.AdmonBox (blip.html.AdmonBox.error,
                                        blip.utils.gettext('There was a problem processing the request.'))
            response.payload = admon
            return response
        else:
            blip.db.flush (blip.db.Account)
            blip.db.commit (blip.db.Account)
        return response

    @classmethod
    def respond_auth_resend (cls, request):
        response = blip.web.WebResponse (request)
        try:
            email = blip.utils.utf8dec (request.query.get('email'))
            user = blip.db.Account.select_one (email=email)
            if user is None or user.check_type != u'new':
                raise blip.utils.BlipException()
            user.check_time = datetime.datetime.utcnow()
            user.check_hash = blip.utils.get_token()
            response.payload = cls.send_authorization_token (user, request)
        except Exception, err:
            blip.db.rollback (blip.db.Account)
            admon = blip.html.AdmonBox (blip.html.AdmonBox.error,
                                        blip.utils.gettext('There was a problem processing the request.'))
            response.payload = admon
            return response
        else:
            blip.db.flush (blip.db.Account)
            blip.db.commit (blip.db.Account)
        return response

    @classmethod
    def respond_auth (cls, request):
        response = blip.web.WebResponse (request)
        if (len(request.path) != 3):
            page = blip.html.PageError (
                blip.utils.gettext('No authorization token.'))
            response.payload = page
            return response
        token = blip.utils.utf8dec (request.path[2])
        try:
            account = blip.db.Account.select (check_hash=token, check_type=u'new')
            account = account[0]
        except:
            page = blip.html.PageError (
                blip.utils.gettext ('The authorization token %s was not found.') % token)
            response.payload = page
            return response
        try:
            account.check_time = None
            account.check_type = None
            account.check_hash = None
            token = blip.utils.get_token ()
            login = blip.db.Login.set_login (account, token, os.getenv ('REMOTE_ADDR'))
            realname = account.data.pop ('realname', None)
            if realname is not None:
                account.person.update (name=realname)
            response.set_cookie ('blip_auth', token)
            response.redirect (blinq.config.web_root_url + 'home')
        except:
            blip.db.rollback (blip.db.Account)
            page = blip.html.PageError (
                blip.utils.gettext('There was a problem processing the request.'))
            response.payload = page
            return response
        else:
            blip.db.flush (blip.db.Account)
            blip.db.commit (blip.db.Account)
        return response

    @classmethod
    def respond_logout (cls, request):
        response = blip.web.WebResponse (request)
        token = request.cookies.get ('blip_auth')
        try:
            token = blip.utils.utf8dec (token.value)
            login = blip.db.Login.get_login (token, request.getenv('REMOTE_ADDR'))
            login.delete ()
        except:
            blip.db.rollback (blip.db.Account)
        else:
            blip.db.flush (blip.db.Account)
            blip.db.commit (blip.db.Account)
        response.redirect (blinq.config.web_root_url)
        response.set_cookie ('blip_auth', '')
        return response

    @classmethod
    def respond_watch (cls, request):
        response = blip.web.WebResponse (request)
        ident = request.query.get('ident')
        if ident is None:
            raise blip.utils.BlipException()
        try:
            blip.db.AccountWatch.add_watch (request.account.username,
                                            blip.utils.utf8dec (ident))
            json = blinq.reqs.web.JsonPayload ()
            json.set_data ({'watch': 'ident'})
            response.payload = json
            blip.db.flush (blip.db.Account)
            blip.db.commit (blip.db.Account)
        except Exception, err:
            blip.db.rollback (blip.db.Account)
            raise
        return response

    @classmethod
    def respond_unwatch (cls, request):
        response = blip.web.WebResponse (request)
        ident = request.query.get('ident')
        if ident is None:
            raise blip.utils.BlipException()
        try:
            blip.db.AccountWatch.remove_watch (request.account.username,
                                            blip.utils.utf8dec (ident))
            json = blinq.reqs.web.JsonPayload ()
            json.set_data ({'watch': 'ident'})
            response.payload = json
            blip.db.flush (blip.db.Account)
            blip.db.commit (blip.db.Account)
        except Exception, err:
            blip.db.rollback (blip.db.Account)
            raise
        return response


################################################################################
## Private Account Handler

class PrivateAccountHandler (BasicAccountHandler):
    account_handler='private'
    can_register = False

    @classmethod
    def add_header_links (cls, page, request):
        if len(request.path) > 0 and request.path[0] == 'account':
            pass
        elif request.account is None:
            page.add_header_link (blinq.config.web_root_url + 'account/login',
                                  blip.utils.gettext ('Log in'))
        else:
            page.add_header_link (blinq.config.web_root_url + 'account/logout',
                                  blip.utils.gettext ('Log out'))

    @classmethod
    def respond_register (cls, request):
        raise blip.web.WebException ('Open registration is not allowed.')

    @classmethod
    def respond_register_submit (cls, request):
        raise blip.web.WebException ('Open registration is not allowed.')
