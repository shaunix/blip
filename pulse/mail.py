# Copyright (c) 2009  Shaun McCance  <shaunm@gnome.org>
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

import smtplib
from email.MIMEText import MIMEText

from pulse import config, utils

class MailException (utils.PulseException):
    pass

class Mail (object):
    def __init__ (self, subject):
        self._subject = subject
        self._recipients = []
        self._content = []

    def add_content (self, txt):
        self._content.append (txt)

    def add_recipient (self, address):
        self._recipients.append (address)

    def send (self):
        if len(self._recipients) == 0:
            raise MailException ('No recipients')
        if len(self._content) == 0:
            raise MailException ('No content')
        message = MIMEText ('\n\n'.join (self._content))
        message['Subject'] = self._subject
        message['From'] = config.mail_from
        message['To'] = ','.join (self._recipients)

        session = smtplib.SMTP ()
        session.connect (config.mail_host)
        if config.mail_username is not None:
            session.login (config.mail_username, config.mail_password)

        result = session.sendmail (config.mail_from,
                                   self._recipients,
                                   message.as_string())
        session.close
