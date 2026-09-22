"""Noninteractive provider authentication for the isolated pyWaPOR process."""
from functools import lru_cache
from urllib.parse import urlsplit

import requests

from .viirs_download import configure_geolocation_download


LAADS_HOST = "ladsweb.modaps.eosdis.nasa.gov"
TOKEN_URL = "https://urs.earthdata.nasa.gov/api/users/find_or_create_token"


def configure_laads(viirs, accounts):
    # LAADS accepts EDL user tokens directly. The upstream interactive OAuth
    # callback can stall even after the user has authorized the application.
    # Reuse the official token API; keep the returned token only in this job's
    # memory. Do not persist it or replace a user's existing token.
    @lru_cache(maxsize=1)
    def token():
        with requests.post(TOKEN_URL, auth=accounts.get("NASA"), timeout=(15, 45)) as response:
            response.raise_for_status()
            value = response.json().get("access_token")
        if not isinstance(value, str) or not value:
            raise RuntimeError("NASA did not return a data-access token.")
        return value

    class LAADSSession(requests.Session):
        def __init__(self):
            super().__init__()
            self.trust_env = False
            self.max_redirects = 5
            self.headers["Authorization"] = f"Bearer {token()}"

        def request(self, method, url, **kwargs):
            self.check_url(url)
            kwargs.setdefault("timeout", (15, 120))
            return super().request(method, url, **kwargs)

        @staticmethod
        def check_url(url):
            parts = urlsplit(url)
            if parts.scheme != "https" or parts.hostname != LAADS_HOST or parts.port not in (None, 443) or parts.username or parts.password:
                raise ValueError("The LAADS data session only supports its HTTPS data host.")

        def rebuild_auth(self, prepared_request, response):
            # Redirects are processed in Session.send, bypassing request().
            # Reject a changed host before the bearer token could be forwarded.
            self.check_url(prepared_request.url)
            super().rebuild_auth(prepared_request, response)

    def setup_session(uri, *, username=None, password=None, check_url=None, verify=True):
        if uri != "https://urs.earthdata.nasa.gov" or not verify:
            raise ValueError("NASA data authentication requires verified HTTPS.")
        if check_url is not None:
            LAADSSession.check_url(check_url)
        return LAADSSession()

    def authorize_session(session, url, verify=True, max_hops=4):
        # The upstream OAuth check reads the entire geolocation response into
        # memory, then downloads it again. With token authentication, checking
        # the status/type while streaming is sufficient; the normal downloader
        # fetches and verifies the actual NetCDF next.
        with session.get(url, stream=True, verify=verify) as response:
            response.raise_for_status()
            if "netcdf" not in response.headers.get("Content-Type", "").lower():
                raise RuntimeError("NASA did not return the requested VIIRS data.")

    # Patch only VIIRS's direct import. Its geolocation selection, thermal and
    # cloud-mask downloads, quality filtering and all model calculations stay
    # in pyWaPOR. The public sample never calls this configuration.
    viirs.setup_session = setup_session
    viirs._authorize_urs_session = authorize_session
    configure_geolocation_download(viirs, LAADSSession)
