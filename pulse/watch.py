################################################################################
## FIXME

def output_account_watch (response, **kw):
    query = kw.get ('query', {})
    ident = query.get('ident', None)
    if response.http_account is not None and ident is not None:
        username = response.http_account.username
        try:
            pulse.db.AccountWatch.add_watch (username, ident)
        except:
            pulse.db.rollback (pulse.db.Account)
            admon = pulse.html.AdmonBox (pulse.html.AdmonBox.error,
                                         pulse.utils.gettext('Could not add watch'))
            response.set_contents (admon)
        else:
            pulse.db.flush (pulse.db.Account)
            pulse.db.commit (pulse.db.Account)
            response.set_contents (pulse.html.Div ())
            return
