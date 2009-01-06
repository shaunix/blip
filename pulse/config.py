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

"""
Confinguration settings for Pulse
"""

import os


################################################################################
## Directories for local stuff
# These are the local directories where stuff can be found.
# You probably only need to change base_dir.

base_dir = '/home/shaunm/Projects/pulse/'

# The directory containing input files that are stored in git with Pulse
input_dir = os.path.join (base_dir, 'input')

# The directory where Pulse puts stuff it's working on
scratch_dir = os.path.join (base_dir, 'scratch')

# The directory where Pulse checks stuff out from SCM systems
scm_dir = os.path.join (scratch_dir, 'scm')


################################################################################
## Directores for web stuff
# These are the local directories where web-available stuff is
# located.  You probably don't need to change any of these.

# The directory that contains index.cgi, among other things
web_dir = os.path.join (base_dir, 'web')

# The directory where Pulse puts web-available files it creates
web_files_dir = os.path.join (web_dir, 'files')

# The directory where Pulse puts figures
web_figures_dir = os.path.join (web_files_dir, 'figures')

# The directory where Pulse puts graphs
web_graphs_dir = os.path.join (web_files_dir, 'graphs')

# The directory where Pulse puts icons
web_icons_dir = os.path.join (web_files_dir, 'icons')

# The directory where Pulse puts POT files
web_l10n_dir = os.path.join (web_files_dir, 'l10n')


################################################################################
## Web roots
# These are the root URLs for various things in Pulse.  You probably
# only need to change web_root, but see the comment below about using
# Pulse without mod_rewrite.

# The root URL for all things Pulse
web_root = 'http://localhost/'

# The root URL for Pulse's CSS, JavaScript, images, etc.
data_root = web_root + 'data/'

# The root URL for web-available files Pulse creates.
files_root = web_root + 'files/'

# If you don't want to use mod_rewrite or something similar, then
# web_root needs to end with 'index.cgi/'.  But then data_root and
# file_root won't work, so do something like this:
# web_root = 'http://localhost/index.cgi/'
# data_root = 'http://localhost/data/'
# files_root = 'http://localhost/files/'

# The root URL for figures
figures_root = files_root + 'figures/'

# The root URL for generated graphs
graphs_root = files_root + 'graphs/'

# The root URL for generated icons
icons_root = files_root + 'icons/'

# The root URL for generated POT files
l10n_root = files_root + 'l10n/'


################################################################################
## Django settings
# These settings are used by Django to connect to the Pulse database.
# This file is imported by Django as a settings file.  You may need
# to change the DATABASE settings below.

DATABASE_ENGINE = 'sqlite3'
DATABASE_NAME = os.path.join (scratch_dir, 'pulse.db')

# If you want to use MySQL, use lines like these:
# DATABASE_ENGINE = 'mysql'
# DATABASE_HOST = '/var/run/mysql'
# DATABASE_NAME = 'Pulse'
# DATABASE_USER = ''
# DATABASE_PASSWORD = ''

# Do not change this.  It makes Django recognize Pulse.
INSTALLED_APPS = 'pulse'

# Do not change this.  We hook into Django's debugging stuff to do logging.
DEBUG = True


################################################################################
## Local config
# You can create a file called localconfig.py alongside config.py with any of
# the above settings defined, rather than editing them here.  This is useful
# for running Pulse directly from a Git clone where you want to make changes
# and submit them back to master.
try:
    from localconfig import *
except:
    pass
