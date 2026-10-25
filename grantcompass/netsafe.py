"""Safe web fetching: the app only reads public websites.

Links come from users and from AI-read funder pages, so a link could point at
this computer (localhost), the home or office network, or a cloud provider's
internal metadata address. Every address is resolved and checked before
connecting, and redirects are followed one hop at a time so each hop is
checked too."""

import ipaddress
import socket
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests

MAX_REDIRECTS = 5


def check_public(url: str) -> None:
    """Raise ValueError unless the URL is http(s) and every address its host resolves to is public."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("Enter a full web address starting with https://")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80),
                                   type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise ValueError(f"Couldn't find the website {p.hostname}. Check the address.") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise ValueError("Grant Compass only reads public websites, not addresses on this computer or a "
                             "private network.")


def safe_get(url: str, timeout: float, headers: dict | None = None, stream: bool = False,
             allow: Callable[[str], bool] | None = None) -> requests.Response:
    """requests.get that refuses private addresses, on the first request and on every redirect.
    `allow` (optional) is checked on every hop too, e.g. to stay on approved sites."""
    for _ in range(MAX_REDIRECTS + 1):
        check_public(url)
        if allow and not allow(url):
            raise ValueError("That link redirects to a site that is not approved yet.")
        resp = requests.get(url, timeout=timeout, headers=headers, stream=stream, allow_redirects=False)
        if resp.is_redirect and resp.headers.get("location"):
            url = urljoin(url, resp.headers["location"])
            resp.close()
            continue
        return resp
    raise ValueError("That link redirects too many times.")
