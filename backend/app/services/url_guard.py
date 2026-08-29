"""SSRF guard for user-supplied video URLs.

``validate_public_url`` is the single choke point every submitted URL must pass
before any worker touches it:

* scheme allow-list (``http`` / ``https`` only),
* reject raw IP literals (v4 and v6),
* resolve the host and reject if *any* resolved address is private, loopback,
  link-local, reserved, multicast, unspecified - i.e. not globally routable.

On any failure a :class:`app.exceptions.ValidationError` (HTTP 422) is raised.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

from app.exceptions import ValidationError
from app.logging_config import get_logger

__all__ = ["validate_public_url"]

logger = get_logger("services.url_guard")

_ALLOWED_SCHEMES = {"http", "https"}


def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True when ``ip`` must not be reachable from server-side code."""
    return (
        not ip.is_global
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_public_url(url: str) -> str:
    """Validate ``url`` is safe to fetch server-side and return it normalised.

    Args:
        url: The raw, user-supplied URL.

    Returns:
        The normalised URL (lower-cased scheme + host, fragment stripped).

    Raises:
        ValidationError: If the URL is malformed, uses a disallowed scheme, is a
            raw IP literal, or resolves to a non-public address.
    """
    if not url or not url.strip():
        raise ValidationError("A video URL is required")

    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()

    if scheme not in _ALLOWED_SCHEMES:
        raise ValidationError("URL scheme must be http or https")

    host = parsed.hostname
    if not host:
        raise ValidationError("URL is missing a host")

    # Reject raw IP literals outright - callers must use hostnames.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValidationError("Raw IP addresses are not allowed; use a hostname")

    # Resolve and vet every address the host maps to.
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if scheme == "https" else 80))
    except socket.gaierror as exc:
        logger.info("SSRF guard: could not resolve host %r: %s", host, exc)
        raise ValidationError(f"Could not resolve host: {host}") from exc

    resolved: set[str] = set()
    for _family, _type, _proto, _canon, sockaddr in infos:
        addr = sockaddr[0]
        resolved.add(addr)
        try:
            ip_obj = ipaddress.ip_address(addr.split("%")[0])
        except ValueError:
            logger.warning("SSRF guard: un-parseable resolved address %r", addr)
            raise ValidationError("Host resolved to an invalid address") from None
        if _is_disallowed_ip(ip_obj):
            logger.warning(
                "SSRF guard: host %r resolved to non-public address %s", host, addr
            )
            raise ValidationError("URL host resolves to a non-public address")

    logger.debug("SSRF guard: %s -> %s (allowed)", host, sorted(resolved))

    normalised = urlunparse(
        (
            scheme,
            parsed.netloc.lower(),
            parsed.path or "/",
            parsed.params,
            parsed.query,
            "",  # drop fragment
        )
    )
    return normalised
