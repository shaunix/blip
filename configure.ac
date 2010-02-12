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

AC_CONFIG_FILES([
Makefile
blip.pc
blip-admin
blip/Makefile
blip/config.py
blip/plugins/Makefile
blip/plugins/commits/Makefile
blip/plugins/cvs/Makefile
blip/plugins/git/Makefile
blip/plugins/index/Makefile
blip/plugins/modules/Makefile
blip/plugins/people/Makefile
blip/plugins/sets/Makefile
blip/plugins/svn/Makefile
web/Makefile
web/data/Makefile
])

AC_OUTPUT

echo "
blip-$VERSION:

	Prefix:     ${prefix}
	Modules:    ${BLIP_MODULES_DIR}
	Plugins:    ${BLIP_PLUGINS_DIR}
	Data files: ${BLIP_DATA_DIR}
	Site data:  ${BLIP_SITE_DIR}
"
