"""Browser interaction agent: semantic, verified actions on the real page.

* Targets are resolved by role + accessible name, label, or CSS - never by bare coordinates.
* Before an action the target is verified: exactly one match, attached, visible, enabled,
  scrolled into view with a non-empty bounding box.
* Every action is reported through ``on_action`` (values that may be personal are not reported).
Coordinate input exists only in the human verification session, where *you* are the one tapping.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from playwright.sync_api import BrowserContext, Locator, Page

FINAL_SUBMIT_RE = re.compile(r"^\s*(submit( (my )?application)?|send application|apply( now)?|finish( and submit)?|"
                             r"complete application)\s*$", re.I)
NEXT_RE = re.compile(r"^\s*(next|continue|save (and|&) continue|proceed|next step)\s*(›|>|→)?\s*$", re.I)
APPLY_OPEN_RE = re.compile(r"^\s*(apply( for this (job|position|role))?( now)?|apply to this job|i'?m interested)\s*$", re.I)


class TargetError(Exception):
    pass


@dataclass
class BrowserAgent:
    page: Page
    on_action: Callable[[str, dict], None] | None = None
    actions: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------------ targeting
    def find(self, *, role: str | None = None, name: str | re.Pattern | None = None, label: str | None = None,
             css: str | None = None) -> Locator:
        if role:
            return self.page.get_by_role(role, name=name) if name is not None else self.page.get_by_role(role)
        if label:
            return self.page.get_by_label(label)
        if css:
            return self.page.locator(css)
        raise TargetError("No target description given")

    def verify(self, loc: Locator, what: str, allow_first_visible: bool = False) -> Locator:
        n = loc.count()
        if n == 0:
            raise TargetError(f"{what}: no matching element")
        if n > 1:
            vis = [loc.nth(i) for i in range(min(n, 20)) if loc.nth(i).is_visible()]
            if len(vis) == 1 or (vis and allow_first_visible):
                loc = vis[0]
            else:
                raise TargetError(f"{what}: {n} matching elements; refusing an ambiguous action")
        loc.scroll_into_view_if_needed(timeout=5000)
        if not loc.is_visible():
            raise TargetError(f"{what}: element not visible")
        if not loc.is_enabled():
            raise TargetError(f"{what}: element disabled")
        box = loc.bounding_box()
        if not box or box["width"] <= 0 or box["height"] <= 0:
            raise TargetError(f"{what}: element has no clickable area")
        return loc

    def _log(self, action: str, **d) -> None:
        rec = {"action": action, **d}
        self.actions.append(rec)
        if self.on_action:
            self.on_action(action, rec)

    # ------------------------------------------------------------------ actions
    def click(self, loc: Locator, what: str) -> None:
        loc = self.verify(loc, what)
        loc.hover(timeout=5000)
        loc.click(timeout=10000)
        self._log("click", target=what)

    def dblclick(self, loc: Locator, what: str) -> None:
        self.verify(loc, what).dblclick(timeout=10000)
        self._log("dblclick", target=what)

    def hover(self, loc: Locator, what: str) -> None:
        self.verify(loc, what).hover(timeout=5000)
        self._log("hover", target=what)

    def type(self, loc: Locator, what: str, text: str) -> None:
        loc = self.verify(loc, what)
        loc.fill("")
        loc.press_sequentially(text, delay=15)
        self._log("type", target=what, chars=len(text))

    def select(self, loc: Locator, what: str, label: str) -> None:
        self.verify(loc, what).select_option(label=label)
        self._log("select", target=what)

    def check(self, loc: Locator, what: str, on: bool = True) -> None:
        loc = self.verify(loc, what) if loc.is_visible() else loc
        (loc.check if on else loc.uncheck)(force=not loc.is_visible())
        self._log("check" if on else "uncheck", target=what)

    def upload(self, loc: Locator, what: str, path: str) -> None:
        if loc.count() != 1:
            raise TargetError(f"{what}: expected exactly one file input")
        loc.set_input_files(path)
        self._log("upload", target=what)

    def scroll(self, dy: int = 600) -> None:
        self.page.mouse.wheel(0, dy)
        self._log("scroll", dy=dy)

    def drag(self, src: Locator, dst: Locator, what: str) -> None:
        self.verify(src, f"{what} (source)").drag_to(self.verify(dst, f"{what} (target)"))
        self._log("drag", target=what)

    # ------------------------------------------------------------------ flow helpers
    def step_buttons(self) -> tuple[Locator | None, Locator | None]:
        """(final_submit, next_step) buttons visible on the current page."""
        btns = self.page.locator("button:visible, input[type=submit]:visible, [role=button]:visible")
        final = nxt = None
        for i in range(min(btns.count(), 60)):
            b = btns.nth(i)
            label = (b.inner_text(timeout=1000) if b.evaluate("e => e.tagName") != "INPUT"
                     else b.get_attribute("value") or "").strip()
            if FINAL_SUBMIT_RE.match(label) and final is None:
                final = b
            elif NEXT_RE.match(label) and nxt is None:
                nxt = b
        return final, nxt

    def open_application(self, context: BrowserContext) -> Page:
        """Click a visible 'Apply' control if the form is not on the page; follows a new tab if one opens."""
        btn = self.page.locator("a:visible, button:visible").filter(has_text=APPLY_OPEN_RE)
        if btn.count() == 0:
            return self.page
        before = len(context.pages)
        self.click(btn.first, "Apply button")
        self.page.wait_for_timeout(2500)
        if len(context.pages) > before:
            new = context.pages[-1]
            new.wait_for_load_state("domcontentloaded", timeout=30000)
            self._log("follow_popup", url=new.url.split("?")[0])
            self.page = new
        return self.page


FIELD_VALUE_JS = r"""
(ids) => ids.map(id => {
  const el = document.querySelector(`[data-jap-id="${id}"]`);
  if (!el) return null;
  if (el.type === 'file') return el.files && el.files.length > 0;
  if (el.type === 'radio' || el.type === 'checkbox') return el.checked;
  return (el.value || '').trim().length > 0;
})
"""


def field_has_value(page: Page, ids: list[str]) -> bool:
    vals = page.evaluate(FIELD_VALUE_JS, ids)
    return any(v for v in vals if v)
