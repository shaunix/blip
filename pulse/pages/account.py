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

def main (path, query, http=True, fd=None):
    kw = {'path' : path, 'query' : query, 'http' : http, 'fd' : fd}

    if query.get('action', None) == 'create':
        return output_account_create (**kw)
    elif path[1] == 'new':
        return output_account_new (**kw)
    elif path[1] == 'auth' and len(path) > 2:
        return output_account_auth (path[2], **kw)


@transaction.commit_manually
def output_account_create (**kw):
    data = cgi.parse ()
    for key in data.keys():
        data[key] = data[key][0]
    realname = data.get ('realname', '')
    if realname == '':
        page = pulse.html.Fragment (http=kw.get('http', True), status=500)
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('Please enter your name'))
        page.add_content (admon)
        page.output(fd=kw.get('fd'))
        return
    username = data.get ('username', '')
    if username == '':
        page = pulse.html.Fragment (http=kw.get('http', True), status=500)
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('Please enter a username'))
        page.add_content (admon)
        page.output(fd=kw.get('fd'))
        return
    email = data.get ('email', '')
    if email == '':
        page = pulse.html.Fragment (http=kw.get('http', True), status=500)
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('Please enter a valid email address'))
        page.add_content (admon)
        page.output(fd=kw.get('fd'))
        return
    password = data.get ('password', '')
    if password == '':
        page = pulse.html.Fragment (http=kw.get('http', True), status=500)
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('Please enter a password'))
        page.add_content (admon)
        page.output(fd=kw.get('fd'))
        return
    try:
        ident = '/person/' + username
        if (db.Account.objects.filter (username=username).count() > 0 or
            db.Entity.objects.filter (ident=ident).count() > 0):
            page = pulse.html.Fragment (http=kw.get('http', True), status=500)
            admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                         pulse.utils.gettext('Username already in use'))
            page.add_content (admon)
            page.output(fd=kw.get('fd'))
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
        page = pulse.html.Fragment (http=kw.get('http', True))
        div = pulse.html.Div (pulse.utils.gettext (
            'Pulse has sent you a confirmation email.  Please visit the link' +
            ' in that email to complete your registration.'
            ))
        page.add_content (div)
        page.output (fd=kw.get('fd'))
    except:
        transaction.rollback ()
        page = pulse.html.Fragment (http=kw.get('http', True), status=500)
        admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                     pulse.utils.gettext('There was a problem processing the request'))
        page.add_content (admon)
        page.output(fd=kw.get('fd'))
        return
    else:
        transaction.commit ()


def output_account_new (**kw):
    page = pulse.html.Page (http=kw.get('http', True),
                            url=(pulse.config.web_root + 'account/new'))
    page.set_title (pulse.utils.gettext ('Create New Account'))

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

    page.output (fd=kw.get('fd'))


@transaction.commit_manually
def output_account_auth (token, **kw):
    try:
        account = db.Account.objects.get (check_hash=token, check_type='new')
    except:
        page = pulse.html.PageError (
            pulse.utils.gettext ('The authorization token %s was not found.') % token,
            **kw)
        page.output (fd=kw.get('fd'))
        return
    try:
        ipaddress = os.getenv ('REMOTE_ADDR')
        ipaddress = '127.0.0.1'
        if ipaddress == None:
            raise
        account.check_time = None
        account.check_type = None
        account.check_hash = None
        account.save ()
        token = pulse.utils.get_token ()
        login = db.Login.set_login (account, token, ipaddress)
        page = pulse.html.HttpRedirect (pulse.config.web_root + 'home')
        page.set_cookie ('pulse_auth', token)
        page.output (fd=kw.get('fd'))
    except:
        transaction.rollback ()
        page = pulse.html.PageError (pulse.utils.gettext('There was a problem processing the request:'),
                                     **kw)
        page.output(fd=kw.get('fd'))
        return
    else:
        transaction.commit ()
