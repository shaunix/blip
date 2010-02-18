SUBDIRS = blip web

bin_SCRIPTS = blip-admin blip-sweep

pkgconfigdir = $(libdir)/pkgconfig
pkgconfig_DATA = blip.pc

EXTRA_DIST =			\
	blip.pc.in		\
	blip-admin		\
	blip-admin.in		\
	blip-sweep		\
	blip-sweep.in		\
	ChangeLog

ChangeLog:
	@if test -f $(top_srcdir)/.git/HEAD; then \
	  git log --stat > $@; \
	fi

dist: ChangeLog
.PHONY: ChangeLog
