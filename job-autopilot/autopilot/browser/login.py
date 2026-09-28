"""Real login test for a user-configured employer portal.

CONNECTED is recorded only when the configured success indicator is observed
on the live site after submitting the stored credentials. MFA / CAPTCHA /
OTP => VERIFICATION_REQUIRED. Nothing is bypassed.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from playwright.sync_api import TimeoutError as PWTimeout
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from ..audit import record_error
from ..models import Platform, PlatformSession, PlatformStatus, utcnow
from ..security.credentials import use_credential
from ..security.vault import get_vault
from .detect import detect_challenge, visible_errors
from .engine import BrowserManager


class PortalLoginConfig(BaseModel):
    login_url: HttpUrl
    username_selector: str
    password_selector: str
    submit_selector: str
    # At least one success indicator is required.
    success_selector: str | None = None
    success_url_regex: str | None = None


@dataclass
class LoginResult:
    status: str
    reason: str


def run_login_test(s: Session, user_id: int, platform_key: str, browsers: BrowserManager) -> LoginResult:
    p = s.get(Platform, platform_key)
    if p is None:
        return LoginResult(PlatformStatus.NOT_CONFIGURED.value, "Unknown platform")
    if not p.automatable:
        return LoginResult(PlatformStatus.NOT_AUTOMATABLE.value, p.notes or "")
    if not p.requires_login:
        return LoginResult(PlatformStatus.NO_LOGIN_REQUIRED.value, "Platform needs no login")
    try:
        cfg = PortalLoginConfig.model_validate(p.config or {})
    except Exception as e:
        return _set(s, p, PlatformStatus.NOT_CONFIGURED, f"Login configuration incomplete: {e}")
    if not (cfg.success_selector or cfg.success_url_regex):
        return _set(s, p, PlatformStatus.NOT_CONFIGURED, "A success indicator (selector or URL regex) is required")
    try:
        with use_credential(s, user_id, platform_key) as (username, secret), browsers.context() as (ctx, _sid):
            page = ctx.new_page()
            page.goto(str(cfg.login_url), wait_until="domcontentloaded", timeout=45000)
            if ch := detect_challenge(page):
                return _set(s, p, PlatformStatus.VERIFICATION_REQUIRED, f"{ch.kind}: {ch.detail}")
            page.fill(cfg.username_selector, username or "")
            page.fill(cfg.password_selector, secret)
            page.click(cfg.submit_selector)
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except PWTimeout:
                pass
            ok = False
            if cfg.success_selector:
                try:
                    page.wait_for_selector(cfg.success_selector, timeout=10000, state="visible")
                    ok = True
                except PWTimeout:
                    ok = False
            if not ok and cfg.success_url_regex and re.search(cfg.success_url_regex, page.url):
                ok = True
            if ok:
                state = ctx.storage_state()
                ps = PlatformSession(platform_key=platform_key, storage_state_blob=b"", key_id="", valid=True)
                s.add(ps)
                s.flush()
                v = get_vault()
                ps.storage_state_blob = v.encrypt(json.dumps(state).encode(), f"platform_session:{platform_key}:{ps.id}".encode())
                ps.key_id = v.current_key_id
                ps.last_validated_at = utcnow()
                return _set(s, p, PlatformStatus.CONNECTED, f"Success indicator observed at {page.url.split('?')[0]}")
            if ch := detect_challenge(page):
                return _set(s, p, PlatformStatus.VERIFICATION_REQUIRED, f"{ch.kind}: {ch.detail}")
            errs = visible_errors(page)
            return _set(s, p, PlatformStatus.LOGIN_FAILED,
                        "Success indicator not observed" + (f"; site says: {' | '.join(errs)[:300]}" if errs else ""))
    except LookupError as e:
        return _set(s, p, PlatformStatus.NOT_CONFIGURED, str(e))
    except Exception as e:
        record_error(s, "login_test", e, platform=platform_key)
        return _set(s, p, PlatformStatus.LOGIN_FAILED, f"{type(e).__name__}: {str(e)[:300]}")


def _set(s: Session, p: Platform, st: PlatformStatus, reason: str) -> LoginResult:
    p.status = st.value
    p.status_reason = reason
    p.last_tested_at = utcnow()
    return LoginResult(st.value, reason)
