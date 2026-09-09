"""QR pairing payload encoding (Section 30's automatic-pairing
requirement). What's genuinely verifiable here on Linux, with no camera
or phone: the payload format round-trips exactly, and the PNG bytes are
a real, correctly structured image produced by the qrcode library, not a
stub. Whether a real camera can actually scan the result is NOT_TESTED
here -- see qr.py's module docstring for why that's an honest limitation
rather than an oversight, the same class of caveat this project already
uses for real microphone/mouse-movement claims.
"""
from __future__ import annotations

import pytest

from aura_core.identity.qr import build_pairing_qr_payload, parse_pairing_qr_payload, render_qr_png


def test_payload_round_trips_exactly():
    payload = build_pairing_qr_payload("K7M4QX2P", "http://192.168.1.14:8756")

    code, server_url = parse_pairing_qr_payload(payload)

    assert code == "K7M4QX2P"
    assert server_url == "http://192.168.1.14:8756"


def test_payload_strips_a_trailing_slash_from_the_server_url_before_encoding():
    payload = build_pairing_qr_payload("ABCD1234", "http://192.168.1.14:8756/")

    _code, server_url = parse_pairing_qr_payload(payload)

    assert server_url == "http://192.168.1.14:8756"


def test_parsing_rejects_a_payload_from_a_different_scheme():
    with pytest.raises(ValueError):
        parse_pairing_qr_payload("https://not-an-aura-pairing-code")


@pytest.mark.parametrize("malformed", ["aura-pair://", "aura-pair://onlycode", "aura-pair://@http://host"])
def test_parsing_rejects_malformed_payloads(malformed):
    with pytest.raises(ValueError):
        parse_pairing_qr_payload(malformed)


def test_render_qr_png_produces_a_real_png():
    png = render_qr_png(build_pairing_qr_payload("K7M4QX2P", "http://192.168.1.14:8756"))

    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 200  # a real encoded matrix, not an empty/stub image


def test_render_qr_png_is_deterministic_for_the_same_payload():
    payload = build_pairing_qr_payload("K7M4QX2P", "http://192.168.1.14:8756")

    assert render_qr_png(payload) == render_qr_png(payload)


def test_different_codes_produce_different_qr_images():
    a = render_qr_png(build_pairing_qr_payload("K7M4QX2P", "http://192.168.1.14:8756"))
    b = render_qr_png(build_pairing_qr_payload("ZZZZ9999", "http://192.168.1.14:8756"))

    assert a != b
