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

import os


## Pulse Settings

basedir = '/home/shaunm/Projects/pulse/'

datadir = os.path.join (basedir, 'data')
vardir = os.path.join (basedir, 'var')
potdir = os.path.join (vardir, 'pot')
scmdir = os.path.join (vardir, 'scm')
webdir = os.path.join (basedir, 'web')
icondir = os.path.join (webdir, 'var', 'icons')

webroot = 'http://localhost/'
dataroot = webroot + 'data/'
varroot = webroot + 'var/'
iconroot = varroot + 'icons/'


## Django Settings

DATABASE_ENGINE = 'sqlite3'
DATABASE_NAME = os.path.join (vardir, 'pulse.db')

# Uncomment these lines to use MySQL
# DATABASE_ENGINE = 'mysql'
# DATABASE_HOST = '/var/run/mysql'
# DATABASE_NAME = 'Pulse'
# DATABASE_USER = ''
# DATABASE_PASSWORD = ''

INSTALLED_APPS = 'pulse'

# Do not change this.  We hook into Django's debugging stuff to do logging.
DEBUG = True
