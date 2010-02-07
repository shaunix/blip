AC_INIT([blip], [0.9], [])
AM_INIT_AUTOMAKE([1.9])

AC_CONFIG_MACRO_DIR([m4])

AM_PATH_PYTHON([2.3])

BLIP_SITE_DIR="${localstatedir}/blip"
AC_SUBST(BLIP_SITE_DIR)

BLIP_PLUGINS_DIR="${pkgpythondir}/plugins"

AC_CONFIG_FILES([
Makefile
blip-admin
blip/Makefile
blip/config.py
blip/plugins/Makefile
blip/plugins/cvs/Makefile
blip/plugins/git/Makefile
blip/plugins/sets/Makefile
blip/plugins/svn/Makefile
web/Makefile
web/data/Makefile
])

AC_OUTPUT

echo "
blip-$VERSION:

	Prefix:           ${prefix}
	Python modules:   ${pkgpythondir}
	Local site data:  ${BLIP_SITE_DIR}
"
