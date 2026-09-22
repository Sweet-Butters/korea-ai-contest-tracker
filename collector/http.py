"""Polite HTTP client: identifies itself, honours robots.txt, retries, rate-limits per host."""
import threading
import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

UA = "KoreaAIContestTracker/1.0 (+https://github.com/Sweet-Butters/korea-ai-contest-tracker)"
# Some sites serve an empty shell to unknown agents; send a browser-like UA but keep our
# identifier in it so site owners can still recognise and block us.
BROWSER_UA = f"Mozilla/5.0 (compatible; {UA})"
MIN_INTERVAL = 0.7  # seconds between requests to the same host


class RobotsDisallowed(Exception):
    pass


_session = requests.Session()
_session.headers["User-Agent"] = BROWSER_UA
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_last_hit: dict[str, float] = {}
_lock = threading.Lock()


def _robots_for(origin: str):
    if origin not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = _session.get(origin + "/robots.txt", timeout=15)
            # A missing robots.txt, or an HTML page served in its place, means no rules.
            if r.status_code == 200 and "<html" not in r.text[:500].lower():
                rp.parse(r.text.splitlines())
            else:
                rp = None
        except requests.RequestException:
            rp = None
        _robots[origin] = rp
    return _robots[origin]


def allowed(url: str) -> bool:
    p = urlsplit(url)
    rp = _robots_for(f"{p.scheme}://{p.netloc}")
    return rp is None or rp.can_fetch(UA, url)


def _throttle(host: str):
    with _lock:
        wait = _last_hit.get(host, 0) + MIN_INTERVAL - time.monotonic()
        _last_hit[host] = time.monotonic() + max(wait, 0)
    if wait > 0:
        time.sleep(wait)


def request(method: str, url: str, *, check_robots=True, retries=3, **kw) -> requests.Response:
    if check_robots and not allowed(url):
        raise RobotsDisallowed(url)
    kw.setdefault("timeout", 40)
    host = urlsplit(url).netloc
    for attempt in range(retries):
        _throttle(host)
        try:
            r = _session.request(method, url, **kw)
            if r.status_code < 500 and r.status_code != 429:
                r.raise_for_status()
                return r
        except requests.HTTPError:
            raise
        except requests.RequestException:
            if attempt == retries - 1:
                raise
        time.sleep(2 * (attempt + 1))
    r.raise_for_status()
    return r


def get(url, **kw):
    return request("GET", url, **kw)


def post(url, **kw):
    return request("POST", url, **kw)
