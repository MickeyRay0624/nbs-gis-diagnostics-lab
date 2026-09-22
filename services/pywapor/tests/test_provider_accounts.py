from types import SimpleNamespace

import pytest

from online.config import configure_accounts
from online.providers import configure_laads, TOKEN_URL


def test_copernicus_direct_import_uses_server_credentials_without_prompt(monkeypatch):
    def interactive_get(_):
        raise AssertionError('Interactive credential lookup reached a server job')

    accounts = SimpleNamespace(get=interactive_get)
    copernicus = SimpleNamespace(get=accounts.get)
    monkeypatch.setenv('NBS_CDSE_USERNAME', 'fixture-user')
    monkeypatch.setenv('NBS_CDSE_PASSWORD', 'fixture-password')
    monkeypatch.delenv('NBS_CDS_TOKEN', raising=False)
    configure_accounts(accounts, copernicus, 'custom')
    assert copernicus.get('COPERNICUS_DATA_SPACE') == ('fixture-user', 'fixture-password')
    with pytest.raises(RuntimeError, match='not configured'):
        accounts.get('CDS')
    with pytest.raises(RuntimeError, match='not configured'):
        copernicus.get('UNCONFIGURED_PROVIDER')

    configure_accounts(accounts, copernicus, 'sample')
    with pytest.raises(RuntimeError, match='public sample'):
        copernicus.get('COPERNICUS_DATA_SPACE')


def test_laads_uses_one_official_token_and_restricts_credential_destination(monkeypatch):
    import requests

    calls = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def json(self): return {'access_token': 'fixture-token'}

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(requests, 'post', post)
    viirs = SimpleNamespace()
    accounts = SimpleNamespace(get=lambda name: ('fixture-nasa', 'fixture-password'))
    configure_laads(viirs, accounts)
    data_url = 'https://ladsweb.modaps.eosdis.nasa.gov/opendap/test.nc'
    first = viirs.setup_session('https://urs.earthdata.nasa.gov', check_url=data_url)
    second = viirs.setup_session('https://urs.earthdata.nasa.gov', check_url=data_url)
    assert first.headers['Authorization'] == second.headers['Authorization'] == 'Bearer fixture-token'
    assert calls == [(TOKEN_URL, {'auth': ('fixture-nasa', 'fixture-password'), 'timeout': (15, 45)})]
    assert first.trust_env is False
    for url in ('http://ladsweb.modaps.eosdis.nasa.gov/test', 'https://example.org/test', 'https://ladsweb.modaps.eosdis.nasa.gov:444/test'):
        with pytest.raises(ValueError, match='HTTPS data host'):
            first.get(url)
        redirected = requests.Request('GET', url).prepare()
        with pytest.raises(ValueError, match='HTTPS data host'):
            first.rebuild_auth(redirected, None)
    with pytest.raises(ValueError, match='verified HTTPS'):
        viirs.setup_session('https://urs.earthdata.nasa.gov', verify=False)


def test_laads_does_not_accept_missing_token(monkeypatch):
    import requests
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def json(self): return {}
    monkeypatch.setattr(requests, 'post', lambda *a, **kw: Response())
    viirs = SimpleNamespace()
    configure_laads(viirs, SimpleNamespace(get=lambda _: ('fixture-user', 'fixture-password')))
    with pytest.raises(RuntimeError, match='did not return'):
        viirs.setup_session('https://urs.earthdata.nasa.gov')
