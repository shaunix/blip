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

from django.core import mail
from django.db import transaction

import pulse.config
import pulse.html
import pulse.models as db
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


@transaction.commit_manually
def output_account_create (response, **kw):
    data = cgi.parse ()
    for key in data.keys():
        data[key] = data[key][0]
    realname = data.get ('realname', '')
    if realname == '':
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('Please enter your name'))
        response.set_contents (admon)
        return
    username = data.get ('username', '')
    if username == '':
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('Please enter a username'))
        response.set_contents (admon)
        return
    email = data.get ('email', '')
    if email == '':
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('Please enter a valid email address'))
        response.set_contents (admon)
        return
    password = data.get ('password', '')
    if password == '':
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('Please enter a password'))
        response.set_contents (admon)
        return
    try:
        ident = '/person/' + username
        if (db.Account.objects.filter (username=username).count() > 0 or
            db.Entity.objects.filter (ident=ident).count() > 0):
            admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                         pulse.utils.gettext('Username already in use'))
            response.set_contents (admon)
            return
        person = db.Entity.get_record (ident, 'Person')
        person.save ()
        token = pulse.utils.get_token ()
        user = db.Account (username=username,
                           password=crypt.crypt(password, 'pu'),
                           person=person,
                           realname=realname,
                           email=email,
                           check_time=datetime.datetime.now(),
                           check_type='new',
                           check_hash=token,
                           data={})
        user.save ()
        subject = pulse.utils.gettext ('Confirm New Pulse Account')
        message = ((
            'Hello %s\n\n' +
            'You have registered a Pulse account. To complete your account registration,\n' +
            'you need to verify your email address. Please visit the URL below.\n\n' +
            '%saccount/auth/%s')
                   % (realname, pulse.config.web_root, token))
        mail.send_mail (subject, message, pulse.config.server_email, [email])
        div = pulse.html.Div (pulse.utils.gettext (
            'Pulse has sent you a confirmation email.  Please visit the link' +
            ' in that email to complete your registration.'
            ))
        response.set_contents (div)
    except:
        transaction.rollback ()
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('There was a problem processing the request'))
        response.set_contents (admon)
        return
    else:
        transaction.commit ()


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
    dl.add_entry (pulse.utils.gettext (
        'Every day, Pulse finds people identified only by their email addresses or' +
        ' usernames on various systems.  You can claim to be these unknown people,' +
        ' giving you the recognition you deserve and helping Pulse create more' +
        ' meaningful statistics.  Claims are reviewed by an actual human being;' +
        ' sorry, we can\'t all be Federico.'
        ))
    dl.add_bold_term (pulse.utils.gettext ('Watch the ones you love'))
    dl.add_entry (pulse.utils.gettext (
        'As a registered user, you can watch people, projects, and anything else' +
        ' with a pulse.  Updates to things you watch will show up in the Ticker' +
        ' on your personal start page.'
        ))
    dl.add_bold_term (pulse.utils.gettext ('Make Pulse smarter'))
    dl.add_entry (pulse.utils.gettext (
        'Pulse knows a lot, but you can help it know more about you by telling it' +
        ' things about yourself.  Better yet, you can point Pulse to places that' +
        ' already know about you, and we\'ll take care of the rest.'
        ))


@transaction.commit_manually
def output_account_auth (response, token, **kw):
    try:
        account = db.Account.objects.get (check_hash=token, check_type='new')
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
        account.save ()
        token = pulse.utils.get_token ()
        login = db.Login.set_login (account, token, os.getenv ('REMOTE_ADDR'))
        response.redirect (pulse.config.web_root + 'home')
        response.set_cookie ('pulse_auth', token)
    except:
        transaction.rollback ()
        page = pulse.html.PageError (pulse.utils.gettext('There was a problem processing the request:'),
                                     **kw)
        response.set_contents (page)
    else:
        transaction.commit ()


@transaction.commit_manually
def output_account_login (response, **kw):
    data = cgi.parse ()
    for key in data.keys():
        data[key] = data[key][0]
    username = data.get ('username', '')
    password = data.get ('password', '')
    admon = None
    if username != '' and password != '':
        try:
            account = db.Account.objects.get (username=username)
            if account.check_type == 'new':
                admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                             pulse.utils.gettext('You have not yet verified your email address'))
                raise
            if account.password != crypt.crypt (password, 'pu'):
                raise
            token = pulse.utils.get_token ()
            login = db.Login.set_login (account, token, os.getenv ('REMOTE_ADDR'))
            response.redirect (pulse.config.web_root + 'home')
            response.set_cookie ('pulse_auth', token)
        except:
            transaction.rollback ()
            if admon == None:
                admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                             pulse.utils.gettext('Invalid username or password'))
        else:
            transaction.commit ()
            return
        
    page = pulse.html.Page (url=(pulse.config.web_root + 'account/login'))
    page.set_title (pulse.utils.gettext ('Log In'))
    response.set_contents (page)

    section = pulse.html.SectionBox (pulse.utils.gettext ('Log In'),
                                     widget_id='loginform')
    page.add_content (section)

    if admon != None:
        section.add_content (admon)

    form = pulse.html.Form ('POST', pulse.config.web_root + 'account/login')
    section.add_content (form)

    table = pulse.html.Table ()
    form.add_content (table)

    table.add_row (
        pulse.utils.gettext ('Username:'),
        pulse.html.TextInput ('username') )
    table.add_row (
        pulse.utils.gettext ('Password:'),
        pulse.html.TextInput ('password', password=True) )
    table.add_row ('', pulse.html.SubmitButton ('login', 'Log In'))


@transaction.commit_manually
def output_account_logout (response, **kw):
    login = response.http_login
    if login:
        login.delete ()
    response.redirect (pulse.config.web_root)
    response.set_cookie ('pulse_auth', '')


@transaction.commit_manually
def output_account_watch (response, **kw):
    query = kw.get ('query', {})
    ident = query.get('ident', None)
    if response.http_account != None and ident != None:
        try:
            db.AccountWatch.add_watch (response.http_account, ident)
        except:
            transaction.rollback ()
            admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                         pulse.utils.gettext('Could not add watch'))
            response.set_contents (admon)
        else:
            transaction.commit ()
            response.set_contents (pulse.html.Div ())
            return
