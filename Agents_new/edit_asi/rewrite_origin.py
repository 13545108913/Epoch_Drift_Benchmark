import json
import re
from typing import Optional


def rewrite_bid_action_to_selector(action: str, env=None, page=None) -> str | None:
    """
    Rewrite bid-based action into a stable selector-based Python action.

    Supported:
      click("189")
      hover("189")
      fill("189", "abc")
      press("189", "Enter")
      select_option("189", "foo")

    Strategy:
      1) parse bid action
      2) locate the original target element on the real page by bid
      3) generate multiple selector candidates
      4) validate candidates on the real page
      5) choose the best validated selector
      6) rebuild action code with that selector
    """
    parsed = _parse_bid_action(action)
    if not parsed:
        return None

    if page is None:
        if env is None:
            return None
        page = env.unwrapped.page

    bid = parsed["bid"]
    op = parsed["op"]
    args = parsed["args"]

    sig = _extract_element_signature_by_bid(page, bid)
    if not sig:
        return None

    selector_code = _choose_best_selector(page, sig)
    if not selector_code:
        return None

    return _build_rewritten_action_code(op, selector_code, args)


def _strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```") and s.endswith("```"):
        s = s[3:-3].strip()
    return s


def _parse_bid_action(action: str):
    s = _strip_code_fence(action)

    m = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\((.*)\)\s*$', s, flags=re.DOTALL)
    if not m:
        return None

    op = m.group(1)
    raw_args = m.group(2).strip()

    supported = {"click", "hover", "fill", "press", "select_option"}
    if op not in supported:
        return None

    m2 = re.match(r'^\s*"([^"]+)"\s*(?:,\s*(.*))?$', raw_args, flags=re.DOTALL)
    if not m2:
        return None

    first = m2.group(1)
    rest = m2.group(2)

    if not first.isdigit():
        return None

    extra_args = []
    if rest is not None:
        extra_args = _parse_remaining_python_like_args(rest)

    return {
        "op": op,
        "bid": first,
        "args": extra_args,
        "raw": s,
    }


def _parse_remaining_python_like_args(rest: str):
    rest = rest.strip()
    if not rest:
        return []

    parts = []
    current = []
    depth = 0
    in_str = False
    quote = None
    escape = False

    for ch in rest:
        if in_str:
            current.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_str = False
                quote = None
            continue

        if ch in ("'", '"'):
            in_str = True
            quote = ch
            current.append(ch)
            continue

        if ch in "([{":
            depth += 1
            current.append(ch)
            continue

        if ch in ")]}":
            depth -= 1
            current.append(ch)
            continue

        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue

        current.append(ch)

    if current:
        parts.append("".join(current).strip())

    return [p for p in parts if p]


def _extract_element_signature_by_bid(page, bid: str):
    """
    Extract identifying features from the real page element corresponding to bid.
    """
    js = """
(bid) => {
  let el = null;
  const selectors = [
    `[bid="${bid}"]`,
    `[data-bid="${bid}"]`,
    `[browsergym_bid="${bid}"]`,
    `[data-browsergym-bid="${bid}"]`
  ];

  for (const sel of selectors) {
    el = document.querySelector(sel);
    if (el) break;
  }

  if (!el) return null;

  const norm = (s) => (s || "").trim().replace(/\\s+/g, " ");
  const tag = (el.tagName || "").toLowerCase();
  const role = el.getAttribute("role") || "";
  const id = el.id || "";
  const name = el.getAttribute("name") || "";
  const ariaLabel = el.getAttribute("aria-label") || "";
  const placeholder = el.getAttribute("placeholder") || "";
  const href = el.getAttribute("href") || "";
  const title = el.getAttribute("title") || "";
  const type = el.getAttribute("type") || "";
  const value = el.getAttribute("value") || "";
  const text = norm(el.innerText || el.textContent || "").slice(0, 120);

  const attrs = {};
  for (const k of ["data-testid", "data-test", "data-qa", "data-cy"]) {
    const v = el.getAttribute(k);
    if (v) attrs[k] = v;
  }

  return {
    bid,
    tag,
    role,
    id,
    name,
    ariaLabel,
    placeholder,
    href,
    title,
    type,
    value,
    text,
    attrs
  };
}
"""
    try:
        return page.evaluate(js, bid)
    except Exception:
        return None


def _choose_best_selector(page, sig: dict) -> Optional[str]:
    """
    Generate multiple candidate selectors and validate them against the real page.

    Priority:
      1) unique + points to original element
      2) non-unique but contains original element
    """
    candidates = _build_selector_candidates(sig)
    if not candidates:
        return None

    best_contains = None

    for candidate in candidates:
        result = _validate_selector_candidate(page, sig["bid"], candidate["code"])

        if not result["ok"]:
            continue

        if result["count"] == 1 and result["matches_original"]:
            return candidate["code"]

        if result["contains_original"] and best_contains is None:
            best_contains = candidate["code"]

    return best_contains


def _build_selector_candidates(sig: dict):
    """
    Returns ordered selector candidates from strongest to weakest.
    Each item: {"kind": ..., "code": ...}
    """
    tag = (sig.get("tag") or "").strip()
    role = (sig.get("role") or "").strip()
    el_id = (sig.get("id") or "").strip()
    name = (sig.get("name") or "").strip()
    aria_label = (sig.get("ariaLabel") or "").strip()
    placeholder = (sig.get("placeholder") or "").strip()
    href = (sig.get("href") or "").strip()
    title = (sig.get("title") or "").strip()
    text = (sig.get("text") or "").strip()
    attrs = sig.get("attrs") or {}

    candidates = []

    def add(kind: str, code: str):
        if code not in {x["code"] for x in candidates}:
            candidates.append({"kind": kind, "code": code})

    # 1) Strong unique attributes
    if el_id:
        add("id", f'page.locator("#{_css_escape_for_id_literal(el_id)}")')

    for k in ("data-testid", "data-test", "data-qa", "data-cy"):
        v = attrs.get(k)
        if v:
            add(k, f'page.locator(\'[{k}="{_css_escape_for_attr(v)}"]\')')

    # 2) Role-based selectors
    inferred_role = role or _infer_role_from_tag(tag, sig.get("type", ""))
    accessible_name = aria_label or text or title or name
    if inferred_role and accessible_name:
        add(
            "role_name",
            f'page.get_by_role({_py_str(inferred_role)}, name={_py_str(accessible_name)})'
        )

    if inferred_role and text:
        add(
            "role_text",
            f'page.get_by_role({_py_str(inferred_role)}, name={_py_str(text)})'
        )

    # 3) Specific attribute selectors
    if aria_label and tag:
        add(
            "tag_aria",
            f'page.locator(\'{tag}[aria-label="{_css_escape_for_attr(aria_label)}"]\')'
        )
    if aria_label:
        add(
            "aria",
            f'page.locator(\'[aria-label="{_css_escape_for_attr(aria_label)}"]\')'
        )

    if name and tag:
        add(
            "tag_name",
            f'page.locator(\'{tag}[name="{_css_escape_for_attr(name)}"]\')'
        )
    if name:
        add(
            "name",
            f'page.locator(\'[name="{_css_escape_for_attr(name)}"]\')'
        )

    if placeholder:
        add("placeholder", f'page.get_by_placeholder({_py_str(placeholder)})')
        if tag:
            add(
                "tag_placeholder",
                f'page.locator(\'{tag}[placeholder="{_css_escape_for_attr(placeholder)}"]\')'
            )

    if href and tag == "a":
        add(
            "href",
            f'page.locator(\'a[href="{_css_escape_for_attr(href)}"]\')'
        )

    if title and tag:
        add(
            "tag_title",
            f'page.locator(\'{tag}[title="{_css_escape_for_attr(title)}"]\')'
        )

    # 4) Text-based with tag restriction
    if tag and text:
        add(
            "tag_text",
            f'page.locator({_py_str(f"{tag}:has-text({json.dumps(text, ensure_ascii=False)})")})'
        )

    # 5) Generic text fallback
    if text:
        add("text_exact", f'page.get_by_text({_py_str(text)}, exact=True)')
        add("text_loose", f'page.get_by_text({_py_str(text)})')

    return candidates


def _validate_selector_candidate(page, original_bid: str, selector_code: str):
    """
    Validate selector on the real page.

    Returns:
      {
        "ok": bool,
        "count": int,
        "contains_original": bool,
        "matches_original": bool,
      }
    """
    try:
        locator = eval(selector_code, {"page": page})
        count = locator.count()

        if count == 0:
            return {
                "ok": True,
                "count": 0,
                "contains_original": False,
                "matches_original": False,
            }

        handle = None
        try:
            handle = _find_matching_handle_by_bid(locator, original_bid)
        except Exception:
            handle = None

        contains_original = handle is not None
        matches_original = contains_original and count == 1

        return {
            "ok": True,
            "count": count,
            "contains_original": contains_original,
            "matches_original": matches_original,
        }
    except Exception:
        return {
            "ok": False,
            "count": 0,
            "contains_original": False,
            "matches_original": False,
        }


def _find_matching_handle_by_bid(locator, bid: str):
    """
    Find whether a locator result set contains the original bid-tagged element.
    """
    for i in range(locator.count()):
        h = locator.nth(i).element_handle()
        if h is None:
            continue
        try:
            matched = h.evaluate(
                """
(el, bid) => {
  const attrs = ["bid", "data-bid", "browsergym_bid", "data-browsergym-bid"];
  for (const k of attrs) {
    if ((el.getAttribute(k) || "") === bid) return true;
  }
  return false;
}
""",
                bid,
            )
            if matched:
                return h
        except Exception:
            continue
    return None


def _infer_role_from_tag(tag: str, input_type: str = "") -> str:
    tag = (tag or "").lower()
    input_type = (input_type or "").lower()

    if tag == "a":
        return "link"
    if tag == "button":
        return "button"
    if tag == "textarea":
        return "textbox"
    if tag == "select":
        return "combobox"
    if tag == "input":
        if input_type in ("button", "submit", "reset"):
            return "button"
        if input_type in ("checkbox",):
            return "checkbox"
        if input_type in ("radio",):
            return "radio"
        return "textbox"
    return ""


def _py_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _css_escape_for_id_literal(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace(" ", "\\ ")
         .replace(".", "\\.")
         .replace(":", "\\:")
         .replace("[", "\\[")
         .replace("]", "\\]")
         .replace("#", "\\#")
    )


def _css_escape_for_attr(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _build_rewritten_action_code(op: str, selector_code: str, args: list[str]) -> str | None:
    if op == "click":
        return f"{selector_code}.click()"

    if op == "hover":
        return f"{selector_code}.hover()"

    if op == "fill":
        if len(args) < 1:
            return None
        return f"{selector_code}.fill({args[0]})"

    if op == "press":
        if len(args) < 1:
            return None
        return f"{selector_code}.press({args[0]})"

    if op == "select_option":
        if len(args) < 1:
            return None
        return f"{selector_code}.select_option({args[0]})"

    return None