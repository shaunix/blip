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

import cgi
import crypt
import datetime
import os
import random
import re

import pulse.config
import pulse.db
import pulse.html
import pulse.utils

def main (response, path, query):
    kw = {'path' : path, 'query' : query}

    if query.get('action', None) == 'create':
        output_account_create (response, **kw)
    elif query.get('action', None) == 'watch':
        output_account_watch (response, **kw)
    elif path[1] == 'new':
        output_account_new (response, **kw)
    elif path[1] == 'auth' and len(path) > 2:
        output_account_auth (response, path[2], **kw)
    elif path[1] == 'login':
        output_account_login (response, **kw)
    elif path[1] == 'logout':
        output_account_logout (response, **kw)


def output_account_create (response, **kw):
    data = cgi.parse ()
    for key in data.keys():
        data[key] = pulse.utils.utf8dec (data[key][0])
    realname = data.get ('realname', '')
    if realname == '':
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('Please enter your name.'))
        response.set_contents (admon)
        return
    username = data.get ('username', '')
    if not re.match ('[a-zA-Z0-9_-]{4,20}$', username):
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext(
            'Please enter a valid username. Usernames must be at least four characters' +
            ' long, and may only contain alphanumeric characters (a-z, A-Z, 0-9), underscores' +
            ' (_), and hyphens (-).'
            ))
        response.set_contents (admon)
        return
    email = data.get ('email', '')
    # Regular expression more or less from bugzilla
    if not re.match ('[\w.+=-]+@[\w.-]+\.[\w-]+', email):
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('Please enter a valid email address.'))
        response.set_contents (admon)
        return
    password = data.get ('password', '')
    if len(password) < 8:
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext(
            'Please enter a valid password. Passwords must be at least eight characters long.'
            ))
        response.set_contents (admon)
        return
    try:
        ident = u'/person/' + username
        if (pulse.db.Account.select (username=username).count() > 0 or
            pulse.db.Entity.select (ident=ident).count() > 0):
            admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                         pulse.utils.gettext(
                'Username already in use.  Please choose another username.'))
            response.set_contents (admon)
            return
        person = pulse.db.Entity (ident, u'Person',
                                  __pulse_store__=pulse.db.Account)
        token = pulse.utils.get_token ()
        pulse.db.rollback ()
        user = pulse.db.Account (username=username,
                                 password=crypt.crypt(password, 'pu'),
                                 person_ident=person.ident,
                                 email=email,
                                 check_time=datetime.datetime.utcnow(),
                                 check_type='new',
                                 check_hash=token)
        user.data['realname'] = realname
        from pulse.mail import Mail
        mail = Mail (pulse.utils.gettext ('Confirm New Pulse Account'))
        mail.add_recipient (email)
        mail.add_content (pulse.utils.gettext ('Hello %s') % realname)
        mail.add_content (pulse.utils.gettext (
            'You have registered a Pulse account. To complete your account registration,\n' +
            'you need to verify your email address. Please visit the URL below.'))
        mail.add_content ('%saccount/auth/%s' % (pulse.config.web_root, token))
        mail.send ()
        div = pulse.html.Div (pulse.utils.gettext (
            'Pulse has sent you a confirmation email.  Please visit the link' +
            ' in that email to complete your registration.'
            ))
        response.set_contents (div)
    except Exception, e:
        pulse.db.rollback (pulse.db.Account)
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('There was a problem processing the request.'))
        response.set_contents (admon)
        return
    else:
        pulse.db.flush (pulse.db.Account)
        pulse.db.commit (pulse.db.Account)


def output_account_new (response, **kw):
    page = pulse.html.Page (url=(pulse.config.web_root + 'account/new'))
    page.set_title (pulse.utils.gettext ('Create New Account'))
    response.set_contents (page)

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    section = pulse.html.SectionBox (pulse.utils.gettext ('Create an Account'),
                                     widget_id='accountform')
    columns.add_to_column (0, section)

    form = pulse.html.Form ('GET', 'javascript:createaccount()')
    section.add_content (form)

    table = pulse.html.Table ()
    form.add_content (table)

    table.add_row (
        pulse.utils.gettext ('Name:'),
        pulse.html.TextInput ('realname') )
    table.add_row (
        pulse.utils.gettext ('Username:'),
        pulse.html.TextInput ('username') )
    table.add_row (
        pulse.utils.gettext ('Email:'),
        pulse.html.TextInput ('email') )
    table.add_row (
        pulse.utils.gettext ('Password:'),
        pulse.html.TextInput ('password1', password=True) )
    table.add_row (
        pulse.utils.gettext ('Confirm:'),
        pulse.html.TextInput ('password2', password=True) )
    table.add_row ('', pulse.html.SubmitButton ('create', 'Create'))

    section = pulse.html.SectionBox (pulse.utils.gettext ('Why Create an Account?'))
    columns.add_to_column (1, section)

    section.add_content (pulse.html.Div (pulse.utils.gettext (
        'Pulse automatically collects publicly-available information, ponders it,' +
        ' and outputs it in ways that are useful to human beings.  All of the' +
        ' information on Pulse is available to everybody.  You don\'t need an' +
        ' account to access any super-secret members-only content.  But creating' +
        ' an account on Pulse has other great advantages:'
        )))
    dl = pulse.html.DefinitionList ()
    section.add_content (dl)
    dl.add_bold_term (pulse.utils.gettext ('Mark your territory'))
    txt = pulse.utils.gettext (
        'Every day, Pulse finds people identified only by their email addresses or' +
        ' usernames on various systems.  You can claim to be these unknown people,' +
        ' giving you the recognition you deserve and helping Pulse create more' +
        ' meaningful statistics.')
    rockstar = pulse.db.Entity.select (type=u'Person')
    rockstar.order_by (pulse.db.Desc (pulse.db.Entity.mod_score))
    try:
        i = random.randint (0, 41)
        rockstar = rockstar[i]
        txt += pulse.utils.gettext (
            ' Claims are reviewed by an actual human being;' +
            ' sorry, we can\'t all be %s.') % rockstar.title
    except:
        pass
    dl.add_entry (txt)
    dl.add_bold_term (pulse.utils.gettext ('Watch the ones you love'))
    dl.add_entry (pulse.utils.gettext (
        'As a registered user, you can watch people, projects, and anything else' +
        ' with a pulse.  Updates to things you watch will show up in the Ticker' +
        ' on your personal home page.'
        ))
    dl.add_bold_term (pulse.utils.gettext ('Make Pulse smarter'))
    dl.add_entry (pulse.utils.gettext (
        'Pulse knows a lot, but you can help it know more about you by telling it' +
        ' things about yourself.  Better yet, you can point Pulse to places that' +
        ' already know about you, and we\'ll take care of the rest.'
        ))


def output_account_auth (response, token, **kw):
    token = pulse.utils.utf8dec (token)
    try:
        account = pulse.db.Account.select (check_hash=token, check_type=u'new')
        account = account[0]
    except:
        page = pulse.html.PageError (
            pulse.utils.gettext ('The authorization token %s was not found.') % token,
            **kw)
        response.set_contents (page)
        return
    try:
        account.check_time = None
        account.check_type = None
        account.check_hash = None
        token = pulse.utils.get_token ()
        login = pulse.db.Login.set_login (account, token, os.getenv ('REMOTE_ADDR'))
        realname = account.data.pop ('realname', None)
        if realname is not None:
            account.person.update (name=realname)
        response.redirect (pulse.config.web_root + 'home')
        response.set_cookie ('pulse_auth', token)
    except:
        pulse.db.rollback (pulse.db.Account)
        page = pulse.html.PageError (pulse.utils.gettext('There was a problem processing the request.'),
                                     **kw)
        response.set_contents (page)
    else:
        pulse.db.flush (pulse.db.Account)
        pulse.db.commit (pulse.db.Account)


def output_account_login (response, **kw):
    data = cgi.parse ()
    for key in data.keys():
        data[key] = pulse.utils.utf8dec (data[key][0])
    username = data.get ('username', u'')
    password = data.get ('password', u'')
    admon = None
    if username != u'' and password != u'':
        account = pulse.db.Account.get (username)
        try:
            if account is None:
                raise pulse.utils.PulseException()
            if account.check_type == 'new':
                admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                             pulse.utils.gettext('You have not yet verified your email address'))
                raise pulse.utils.PulseException()
            if account.password != crypt.crypt (password, 'pu'):
                raise pulse.utils.PulseException()
            token = pulse.utils.get_token ()
            login = pulse.db.Login.set_login (account, token, os.getenv ('REMOTE_ADDR'))
            response.redirect (pulse.config.web_root + 'home')
            response.set_cookie ('pulse_auth', token)
        except:
            pulse.db.rollback (pulse.db.Account)
            if admon == None:
                admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                             pulse.utils.gettext('Invalid username or password'))
        else:
            pulse.db.flush (pulse.db.Account)
            pulse.db.commit (pulse.db.Account)
            return
        
    page = pulse.html.Page (url=(pulse.config.web_root + 'account/login'))
    page.set_title (pulse.utils.gettext ('Log In'))
    response.set_contents (page)

    if admon != None:
        page.add_content (admon)

    form = pulse.html.Form ('POST', pulse.config.web_root + 'account/login')
    page.add_content (form)

    table = pulse.html.Table ()
    form.add_content (table)

    table.add_row (
        pulse.utils.gettext ('Username:'),
        pulse.html.TextInput ('username') )
    table.add_row (
        pulse.utils.gettext ('Password:'),
        pulse.html.TextInput ('password', password=True) )
    span = pulse.html.Span ()
    span.add_content (pulse.html.SubmitButton ('login', 'Log In'))
    span.add_content (pulse.utils.gettext (' or '))
    span.add_content (pulse.html.Link (pulse.config.web_root + 'account/new',
                                      pulse.utils.gettext ('create an account')))
    table.add_row ('', span)


def output_account_logout (response, **kw):
    login = response.http_login
    try:
        if login:
            login.delete ()
    except:
        pulse.db.rollback (pulse.db.Account)
    else:
        pulse.db.flush (pulse.db.Account)
        pulse.db.commit (pulse.db.Account)
    response.redirect (pulse.config.web_root)
    response.set_cookie ('pulse_auth', '')


def output_account_watch (response, **kw):
    query = kw.get ('query', {})
    ident = query.get('ident', None)
    if response.http_account is not None and ident is not None:
        try:
            pulse.db.AccountWatch.add_watch (response.http_account, ident)
        except:
            pulse.db.rollback (pulse.db.Account)
            admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                         pulse.utils.gettext('Could not add watch'))
            response.set_contents (admon)
        else:
            pulse.db.flush (pulse.db.Account)
            pulse.db.commit (pulse.db.Account)
            response.set_contents (pulse.html.Div ())
            return
