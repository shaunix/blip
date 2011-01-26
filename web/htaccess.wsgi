DirectoryIndex index.wsgi

RewriteEngine on
RewriteRule ^data/.* - [L]
RewriteRule ^files/.* - [L]
RewriteRule ^index.wsgi([/?].*)?$ - [L]
RewriteRule (.*) index.wsgi/$1 [L]
