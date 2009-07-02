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
p = os.path
base_dir = p.dirname(p.dirname(p.abspath(__file__)))
del p


# The directory containing input files that are stored in git with Pulse
input_dir = os.path.join (base_dir, 'input')

# The directory where Pulse puts stuff it's working on
scratch_dir = os.path.join (base_dir, 'scratch')

# The directory where Pulse checks stuff out from SCM systems
scm_dir = os.path.join (scratch_dir, 'scm')

# The directory where Pulse puts temporary files
tmp_dir = os.path.join (scratch_dir, 'tmp')


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
web_root = 'http://127.0.0.1/'

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
## Database settings

database = 'sqlite:%s/pulse.db' % scratch_dir

# Larger values will result in fewer queries and faster crawl
# times, but will use more memory.  Note that, unless you set
# this ridiculously low, the web app won't be affected.
database_cache_size = 5000


################################################################################
## Other Stuff

mail_host = 'localhost'

# Username and password for hosts that require authentication.
# Set mail_username to None if no authentication is required.
mail_username = None
mail_password = None

# The email address from which Pulse sends email
mail_from = 'gnomeweb@gnome.org'


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
