import re
from urllib.parse import urlsplit

# Same rules as the Django project's websites/domains.py so both sides
# compare identical hostnames.
HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$")

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def normalize_domain(value):
    """
    Reduce a domain or URL to a comparable hostname:
    "https://WWW.Example.com:443/page" -> "example.com".
    Returns "" if the value is not a valid public hostname.
    """
    value = (value or "").strip()
    if not value:
        return ""

    if "://" not in value:
        value = "//" + value
    try:
        host = urlsplit(value).hostname or ""
    except ValueError:
        return ""

    host = host.rstrip(".")
    if host.startswith("www."):
        host = host[4:]

    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return ""

    return host if HOSTNAME_RE.match(host) else ""


def local_domain(host, port):
    """
    Domain string for a local development origin, in the same format the
    Django project stores for local sites when DEBUG is on (port kept):
    ("127.0.0.1", 8012) -> "127.0.0.1:8012", ("::1", 8012) -> "[::1]:8012".
    """
    if host == "::1":
        host = "[::1]"
    return f"{host}:{port}" if port else host


def parse_origin(origin):
    """
    Split a browser Origin header ("https://example.com:8443") into
    (scheme, hostname, port). Returns None for anything that is not exactly
    an origin: missing, "null", paths, credentials, or unsupported schemes.
    """
    if not origin or origin == "null":
        return None

    try:
        parts = urlsplit(origin)
        port = parts.port  # raises ValueError for a malformed port
    except ValueError:
        return None

    if parts.scheme not in ("http", "https"):
        return None
    if parts.path or parts.query or parts.fragment or parts.username or parts.password:
        return None
    if not parts.hostname:
        return None

    return parts.scheme, parts.hostname.lower(), port
