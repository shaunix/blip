AC_INIT([blip], [0.9], [])
AM_INIT_AUTOMAKE([1.9])

AC_CONFIG_MACRO_DIR([m4])

AM_PATH_PYTHON

BLIP_SITE_DIR="${localstatedir}/blip"
AC_SUBST(BLIP_SITE_DIR)

AC_CONFIG_FILES([
Makefile
blip-admin
blip/Makefile
blip/config.py
])

AC_OUTPUT

echo "
blip-$VERSION:

	Prefix:           ${prefix}
	Python modules:   ${pkgpythondir}
	Local site data:  ${BLIP_SITE_DIR}
"
