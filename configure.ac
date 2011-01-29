AC_INIT([blip], [0.9.1], [])
AM_INIT_AUTOMAKE([1.9])

AC_CONFIG_MACRO_DIR([m4])

AM_PATH_PYTHON([2.4])

BLIP_SITE_DIR=`(
	case $prefix in
	     NONE) prefix=$ac_default_prefix ;;
	     *) ;;
	esac
	eval echo $(eval echo $localstatedir)/blip
)`
AC_SUBST(BLIP_SITE_DIR)

BLIP_PYTHON_DIR=`(
	case $prefix in
	     NONE) prefix=$ac_default_prefix ;;
	     *) ;;
	esac
	eval echo $(eval echo $pythondir)
)`
AC_SUBST(BLIP_PYTHON_DIR)

BLIP_MODULES_DIR=`(
	case $prefix in
	     NONE) prefix=$ac_default_prefix ;;
	     *) ;;
	esac
	eval echo $(eval echo $pkgpythondir)
)`
AC_SUBST(BLIP_MODULES_DIR)

BLIP_DATA_DIR=`(
	case $prefix in
	     NONE) prefix=$ac_default_prefix ;;
	     *) ;;
	esac
	eval echo $(eval echo $datadir)/blip
)`
AC_SUBST(BLIP_DATA_DIR)

BLIP_PLUGINS_DIR="${BLIP_MODULES_DIR}/plugins"
AC_SUBST(BLIP_PLUGINS_DIR)

AC_CHECK_PYTHON_MODULE([blinq])
if test x$PYTHON_blinq != x1 ; then
  AC_MSG_ERROR([blinq not found])
fi

AC_CHECK_PYTHON_MODULE([cairo])
if test x$PYTHON_cairo != x1 ; then
  AC_MSG_ERROR([cairo not found])
fi

AC_CHECK_PYTHON_MODULE([libxml2])
if test x$PYTHON_libxml2 != x1 ; then
  AC_MSG_ERROR([libxml2 not found])
fi

AC_CHECK_PYTHON_MODULE([storm])
if test x$PYTHON_storm != x1 ; then
  AC_MSG_ERROR([storm not found])
fi

AC_CONFIG_FILES([
Makefile
blip.pc
blip-admin
blip-sweep
blip/Makefile
blip/config.py
blip/parsers/Makefile
blip/plugins/Makefile
blip/plugins/accounts/Makefile
blip/plugins/autoconf/Makefile
blip/plugins/apps/Makefile
blip/plugins/commits/Makefile
blip/plugins/cvs/Makefile
blip/plugins/doap/Makefile
blip/plugins/docs/Makefile
blip/plugins/entities/Makefile
blip/plugins/error/Makefile
blip/plugins/git/Makefile
blip/plugins/home/Makefile
blip/plugins/i18n/Makefile
blip/plugins/index/Makefile
blip/plugins/lists/Makefile
blip/plugins/modules/Makefile
blip/plugins/queue/Makefile
blip/plugins/scores/Makefile
blip/plugins/sets/Makefile
blip/plugins/svn/Makefile
web/Makefile
web/index.cgi
web/data/Makefile
])

AC_OUTPUT

echo "
blip-$VERSION:

	Prefix:     ${prefix}
	Python:     ${BLIP_PYTHON_DIR}
	Modules:    ${BLIP_MODULES_DIR}
	Plugins:    ${BLIP_PLUGINS_DIR}
	Data files: ${BLIP_DATA_DIR}
	Site data:  ${BLIP_SITE_DIR}
"
