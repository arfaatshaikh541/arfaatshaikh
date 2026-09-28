"""Generic application-form detection and filling on the real DOM."""
from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import Locator, Page

from ..questions.engine import FormField

_EXTRACT_JS = r"""
() => {
  const out = [];
  let n = 0;
  const txt = (el) => (el ? (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim() : '');
  const visible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const labelFor = (el) => {
    const ids = (el.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean);
    if (ids.length) { const t = ids.map(i => txt(document.getElementById(i))).join(' ').trim(); if (t) return t; }
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l && txt(l)) return txt(l); }
    const wrap = el.closest('label'); if (wrap && txt(wrap)) return txt(wrap);
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label').trim();
    let p = el.parentElement;
    for (let i = 0; i < 4 && p; i++, p = p.parentElement) {
      const l = p.querySelector(':scope > label, :scope > legend, :scope > .label, :scope > [class*="label" i]');
      if (l && l !== el && txt(l) && !l.contains(el)) return txt(l);
    }
    return (el.getAttribute('placeholder') || el.getAttribute('name') || '').trim();
  };
  const requiredOf = (el, label) => el.required || el.getAttribute('aria-required') === 'true' || /\*\s*$/.test(label || '');
  const mark = (el) => { const id = 'f' + (n++); el.setAttribute('data-jap-id', id); return id; };
  const seenGroups = new Set();
  const els = document.querySelectorAll('input, textarea, select');
  for (const el of els) {
    const type = (el.getAttribute('type') || el.tagName).toLowerCase();
    if (['hidden', 'submit', 'button', 'image', 'reset', 'search'].includes(type)) continue;
    if (el.disabled || el.readOnly && type !== 'file') continue;
    if (type !== 'file' && !visible(el) && !(type === 'radio' || type === 'checkbox')) continue;
    if (type === 'radio' || (type === 'checkbox' && el.name && document.querySelectorAll(`input[type=checkbox][name="${CSS.escape(el.name)}"]`).length > 1)) {
      const key = type + ':' + (el.name || el.id);
      if (seenGroups.has(key)) continue; seenGroups.add(key);
      const members = el.name ? document.querySelectorAll(`input[type=${type}][name="${CSS.escape(el.name)}"]`) : [el];
      const fs = el.closest('fieldset, [role=radiogroup], [role=group]');
      let glabel = fs ? txt(fs.querySelector('legend, [class*="label" i], label')) : '';
      if (!glabel) { let p = el.parentElement; for (let i = 0; i < 5 && p && !glabel; i++, p = p.parentElement) {
          const l = p.querySelector(':scope > label, :scope > legend, :scope > [class*="label" i], :scope > [class*="question" i]');
          if (l && !l.querySelector('input')) glabel = txt(l); } }
      const opts = []; const ids = [];
      for (const m of members) { opts.push(labelFor(m) || m.value); ids.push(mark(m)); }
      out.push({kind: type === 'radio' ? 'radio' : 'checkbox_group', label: glabel || el.name || '', required: [...members].some(m => m.required) || /\*\s*$/.test(glabel),
                options: opts, ids, name: el.name || null, maxlength: null});
      continue;
    }
    const label = labelFor(el);
    let kind = el.tagName === 'SELECT' ? 'select' : el.tagName === 'TEXTAREA' ? 'textarea' : type;
    if (el.getAttribute('role') === 'combobox' && el.tagName === 'INPUT') kind = 'combobox';
    const opts = el.tagName === 'SELECT' ? [...el.options].filter(o => o.value !== '' && !/^\s*(select|choose|please select)\b/i.test(o.text)).map(o => o.text.trim()) : [];
    out.push({kind, label, required: requiredOf(el, label), options: opts, ids: [mark(el)], name: el.name || el.id || null,
              maxlength: el.maxLength > 0 ? el.maxLength : null});
  }
  return out;
}
"""

_TYPE_MAP = {"text": "text", "email": "email", "tel": "tel", "url": "url", "number": "number", "date": "date",
             "textarea": "textarea", "select": "select", "radio": "radio", "checkbox": "checkbox",
             "checkbox_group": "checkbox_group", "file": "file", "combobox": "combobox", "password": "password"}


@dataclass
class DetectedField:
    field: FormField
    ids: list[str]

    def locator(self, page: Page, i: int = 0) -> Locator:
        return page.locator(f"[data-jap-id='{self.ids[i]}']")


def clean_label(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s[:500]


def extract_fields(page: Page) -> list[DetectedField]:
    raw = page.evaluate(_EXTRACT_JS)
    out = []
    for r in raw:
        kind = _TYPE_MAP.get(r["kind"], "text")
        if kind == "password":
            continue  # application forms never need our password; login is handled separately
        ff = FormField(label=clean_label(r["label"]), field_type=kind, required=bool(r["required"]),
                       options=[clean_label(o) for o in r.get("options") or []], name=r.get("name"),
                       max_length=r.get("maxlength"))
        out.append(DetectedField(ff, r["ids"]))
    return out


def combobox_options(page: Page, df: DetectedField) -> list[str]:
    """Open a custom (react-select style) combobox and read its real options."""
    loc = df.locator(page)
    try:
        loc.click()
        page.wait_for_timeout(400)
        opts = page.locator("[role='option']")
        texts = [clean_label(opts.nth(i).inner_text()) for i in range(min(opts.count(), 200))]
        page.keyboard.press("Escape")
        return [t for t in texts if t]
    except Exception:
        return []


class FillError(Exception):
    pass


def fill_field(page: Page, df: DetectedField, value, file_path: str | None = None) -> None:
    f = df.field
    t = f.field_type
    if t == "file":
        if not file_path:
            raise FillError("No file path for upload")
        df.locator(page).set_input_files(file_path)
        return
    if t in {"text", "email", "tel", "url", "number", "date", "textarea"}:
        loc = df.locator(page)
        loc.fill(str(value))
        if loc.input_value() != str(value):
            raise FillError(f"Field '{f.label}' did not accept the value")
        return
    if t == "select":
        df.locator(page).select_option(label=str(value))
        return
    if t == "radio":
        idx = f.options.index(value)
        loc = df.locator(page, idx)
        try:
            loc.check()
        except Exception:
            loc.check(force=True)  # custom-styled radios hide the native input behind a label
        if not loc.is_checked():
            raise FillError(f"Radio '{value}' not checked")
        return
    if t == "checkbox":
        loc = df.locator(page)
        (loc.check if value else loc.uncheck)(force=True)
        if loc.is_checked() != bool(value):
            raise FillError(f"Checkbox '{f.label}' state mismatch")
        return
    if t == "checkbox_group":
        values = value if isinstance(value, list) else [value]
        for v in values:
            df.locator(page, f.options.index(v)).check(force=True)
        return
    if t == "combobox":
        loc = df.locator(page)
        loc.click()
        loc.fill(str(value))
        page.wait_for_timeout(500)
        opt = page.locator("[role='option']", has_text=re.compile(rf"^\s*{re.escape(str(value))}\s*$"))
        if opt.count() == 0:
            raise FillError(f"Option '{value}' not offered by combobox '{f.label}'")
        opt.first.click()
        return
    raise FillError(f"Unsupported field type {t}")


SUBMIT_SELECTORS = [
    "button[type=submit]:visible",
    "input[type=submit]:visible",
    "button:visible:text-matches('^\\s*(submit( application)?|send application|apply( now)?)\\s*$', 'i')",
]


def find_submit(page: Page) -> Locator | None:
    for sel in SUBMIT_SELECTORS:
        loc = page.locator(sel)
        if loc.count() == 1:
            return loc
        if loc.count() > 1:
            named = loc.filter(has_text=re.compile(r"submit|apply|send", re.I))
            if named.count() >= 1:
                return named.last
    return None
