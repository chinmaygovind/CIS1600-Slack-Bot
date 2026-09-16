"""Minimal Ed Discussion API client.

Replaces the `edapi` package for the notification path. Two things `edapi`
gets wrong against Ed's current API:

  * Ed no longer accepts the `X-Token` header and answers 401 "Invalid token".
    Credentials must be sent as `Authorization: Bearer <token>`.
  * Ed sits behind Cloudflare, which rejects Python's default User-Agent with
    an opaque HTML `error code: 1010` before the request ever reaches the API.

Both are handled here. `ed_stats/` still uses `edapi` and is untouched.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

REGION = os.getenv("ED_REGION", "us")
COURSE_ID = os.getenv("ED_COURSE_ID")
API_TOKEN = os.getenv("ED_API_TOKEN")

BASE = f"https://{REGION}.edstem.org/api"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class EdError(RuntimeError):
    pass


class EdClient:
    def __init__(self, token=None, region=None, course_id=None):
        self.token = token or API_TOKEN
        self.region = region or REGION
        self.course_id = course_id or COURSE_ID
        self.base = f"https://{self.region}.edstem.org/api"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })

    def _get(self, path, **params):
        try:
            r = self.session.get(self.base + path, params=params, timeout=30)
        except requests.RequestException as e:
            raise EdError(f"network error calling {path}: {e}") from e
        if r.status_code == 401:
            raise EdError("Ed rejected the API token (401). Regenerate ED_API_TOKEN.")
        if r.status_code == 403:
            raise EdError(
                "Ed returned 403 -- usually Cloudflare blocking the request, "
                "not an auth problem."
            )
        if not r.ok:
            raise EdError(f"Ed returned HTTP {r.status_code} for {path}")
        return r.json()

    def whoami(self):
        return self._get("/user").get("user", {}).get("name")

    def list_threads(self, limit=30, offset=0, sort="new"):
        data = self._get(
            f"/courses/{self.course_id}/threads",
            limit=limit, offset=offset, sort=sort,
        )
        return data.get("threads", [])

    def get_thread(self, thread_id):
        return self._get(f"/threads/{thread_id}").get("thread", {})

    def thread_url(self, thread_id):
        return (
            f"https://edstem.org/{self.region}/courses/"
            f"{self.course_id}/discussion/{thread_id}"
        )
