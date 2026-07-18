"""Tests for `worker.crawler.detectors` - pure functions over static HTML,
no network involved. Each asserts a detector extracts real data present in
the fixture HTML and nothing else, and that absence detectors only fire
when the thing they check for is genuinely missing from that page.
"""

from bs4 import BeautifulSoup
from worker.crawler.detectors import (
    detect_booking,
    detect_contact_email,
    detect_missing_contact_form,
    detect_missing_mobile_viewport,
    detect_ordering,
    detect_outdated_copyright_year,
    detect_phone,
    detect_social_links,
    detect_weak_page_metadata,
    detect_whatsapp,
    run_all_detectors,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_detect_contact_email_prefers_mailto_over_plain_text():
    html = """
    <html><body>
    <a href="mailto:sales@example.com?subject=hi">Email sales</a>
    <p>Or reach support@example.com directly.</p>
    </body></html>
    """
    signals = detect_contact_email(_soup(html))
    by_email = {s.structured_result["email"].lower(): s for s in signals}
    assert by_email["sales@example.com"].confidence == 0.95
    assert by_email["support@example.com"].confidence == 0.7


def test_detect_contact_email_deduplicates_case_insensitively():
    html = """<a href="mailto:Sales@Example.com">Email</a><p>sales@example.com</p>"""
    signals = detect_contact_email(_soup(html))
    assert len(signals) == 1


def test_detect_contact_email_returns_nothing_when_absent():
    assert detect_contact_email(_soup("<html><body>No contact here.</body></html>")) == []


def test_detect_phone_extracts_tel_links_only():
    html = """
    <a href="tel:+15551234567">Call</a>
    <p>Or find us at 555-1234 (not a tel: link, not extracted)</p>
    """
    signals = detect_phone(_soup(html))
    assert len(signals) == 1
    assert signals[0].structured_result["phone"] == "+15551234567"
    assert signals[0].confidence == 0.95


def test_detect_whatsapp_matches_wa_me_and_api_whatsapp():
    html = """
    <a href="https://wa.me/15551234567">WhatsApp us</a>
    <a href="https://api.whatsapp.com/send?phone=15559998888">Chat</a>
    <a href="https://example.com/not-whatsapp">Other</a>
    """
    signals = detect_whatsapp(_soup(html))
    assert len(signals) == 2
    assert all(s.detector_type == "whatsapp" for s in signals)


def test_detect_booking_matches_known_platform_domains():
    html = """
    <a href="https://calendly.com/joespizza/consult">Book a call</a>
    <a href="https://example.com/booking">Not a real booking platform link</a>
    """
    signals = detect_booking(_soup(html))
    assert len(signals) == 1
    assert signals[0].structured_result["platform"] == "calendly.com"


def test_detect_ordering_matches_known_platform_domains():
    html = '<a href="https://www.ubereats.com/store/joes-pizza">Order now</a>'
    signals = detect_ordering(_soup(html))
    assert len(signals) == 1
    assert signals[0].structured_result["platform"] == "ubereats.com"


def test_detect_social_links_extracts_facebook_instagram_linkedin():
    html = """
    <a href="https://facebook.com/joespizza">FB</a>
    <a href="https://www.instagram.com/joespizza">IG</a>
    <a href="https://linkedin.com/company/joespizza">LI</a>
    <a href="https://twitter.com/joespizza">Twitter (not extracted)</a>
    """
    signals = detect_social_links(_soup(html))
    types_found = {s.detector_type for s in signals}
    assert types_found == {"social_facebook", "social_instagram", "social_linkedin"}


def test_detect_missing_mobile_viewport_true_when_tag_absent():
    signals = detect_missing_mobile_viewport(_soup("<html><head></head><body></body></html>"))
    assert len(signals) == 1
    assert signals[0].detector_type == "missing_mobile_viewport"


def test_detect_missing_mobile_viewport_empty_when_tag_present():
    html = '<html><head><meta name="viewport" content="width=device-width"></head></html>'
    assert detect_missing_mobile_viewport(_soup(html)) == []


def test_detect_weak_page_metadata_flags_short_title_and_missing_description():
    signals = detect_weak_page_metadata(_soup("<html><head><title>Hi</title></head></html>"))
    assert len(signals) == 1
    assert signals[0].structured_result["has_description"] is False


def test_detect_weak_page_metadata_empty_when_strong():
    html = """
    <html><head><title>Joe's Pizza - Best Pizza in Town</title>
    <meta name="description" content="Family owned pizza restaurant since 1990"></head></html>
    """
    assert detect_weak_page_metadata(_soup(html)) == []


def test_detect_outdated_copyright_year_flags_stale_year():
    html = "<footer>&copy; 2019 Joe's Pizza</footer>"
    signals = detect_outdated_copyright_year(_soup(html), current_year=2026)
    assert len(signals) == 1
    assert signals[0].structured_result["year"] == 2019


def test_detect_outdated_copyright_year_ignores_recent_year():
    html = "<footer>&copy; 2025 Joe's Pizza</footer>"
    assert detect_outdated_copyright_year(_soup(html), current_year=2026) == []


def test_detect_outdated_copyright_year_ignores_future_year_typo():
    html = "<footer>Copyright 2099 Joe's Pizza</footer>"
    assert detect_outdated_copyright_year(_soup(html), current_year=2026) == []


def test_detect_missing_contact_form_true_when_no_form_tag():
    signals = detect_missing_contact_form(_soup("<html><body>No form here.</body></html>"))
    assert len(signals) == 1


def test_detect_missing_contact_form_empty_when_form_present():
    html = "<form><input name='email'></form>"
    assert detect_missing_contact_form(_soup(html)) == []


def test_run_all_detectors_combines_every_detector_on_one_page():
    html = """
    <html><head><title>Joe's Pizza - Best Pizza in Town</title>
    <meta name="description" content="Family owned pizza restaurant since 1990">
    <meta name="viewport" content="width=device-width"></head>
    <body>
    <footer>&copy; 2019 Joe's Pizza</footer>
    <a href="mailto:contact@joespizza.example">Email</a>
    <a href="tel:+15551234567">Call</a>
    <a href="https://facebook.com/joespizza">Facebook</a>
    <form><input name="message"></form>
    </body></html>
    """
    signals = run_all_detectors(html, current_year=2026)
    types_found = {s.detector_type for s in signals}
    assert types_found == {
        "contact_email",
        "phone",
        "social_facebook",
        "outdated_copyright_year",
    }
    # Absence detectors correctly did not fire since their targets are present.
    assert "missing_mobile_viewport" not in types_found
    assert "weak_page_metadata" not in types_found
    assert "missing_contact_form" not in types_found


def test_run_all_detectors_defaults_current_year_to_now():
    # No explicit current_year - must not raise, and a very old copyright
    # year must still be flagged relative to whatever "now" resolves to.
    html = "<footer>&copy; 2000 Old Co</footer>"
    signals = run_all_detectors(html)
    assert any(s.detector_type == "outdated_copyright_year" for s in signals)
