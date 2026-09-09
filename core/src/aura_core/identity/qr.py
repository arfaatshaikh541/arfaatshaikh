"""QR encoding for the "Add Device" pairing flow (Section 30's automatic
pairing requirement).

The 8-character pairing code (identity/pairing.py) is already enough to
pair a device by hand: type it into the joining device, which already
knows (or is told) which aura_core server to talk to. A QR code adds one
real thing on top of that: it can carry the *server's own address* too,
so a phone scanning it does not also need to be told an IP and port by
some other channel. It is a convenience encoding of the same two facts a
human would otherwise type in separately -- it is not a separate
credential and it grants nothing the plain code doesn't already grant;
scanning it still ends up calling the same, already-secured
`POST /devices/pairing/claim`.

What this module does NOT claim: that a real camera can actually scan the
PNG this produces. That needs real hardware to verify (a phone, good
lighting, focus) exactly like this project's other real-device-only
claims (see desktop_connector's mouse-movement caveats, the voice
pipeline's microphone caveats) -- NOT_TESTED here, honestly. What IS real
and tested here: the payload format round-trips exactly, and the PNG
bytes this produces are a genuine, correctly structured QR code (built by
the `qrcode` library, not a stub).
"""
from __future__ import annotations

import io

import qrcode

_SCHEME = "aura-pair"


def build_pairing_qr_payload(code: str, server_url: str) -> str:
    """`server_url` is whatever base URL the joining device should POST
    its claim to (e.g. "http://192.168.1.14:8756") -- supplied by the
    caller (the API layer, which knows its own bind address), never
    guessed here."""
    server_url = server_url.rstrip("/")
    return f"{_SCHEME}://{code}@{server_url}"


def parse_pairing_qr_payload(payload: str) -> tuple[str, str]:
    """Returns (code, server_url). Raises ValueError for anything that
    doesn't match build_pairing_qr_payload's own format -- this is only
    ever meant to parse a payload this module itself produced."""
    prefix = f"{_SCHEME}://"
    if not payload.startswith(prefix):
        raise ValueError(f"not an {_SCHEME} payload")
    rest = payload[len(prefix):]
    code, sep, server_url = rest.partition("@")
    if not sep or not code or not server_url:
        raise ValueError(f"malformed {_SCHEME} payload")
    return code, server_url


def render_qr_png(payload: str) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
