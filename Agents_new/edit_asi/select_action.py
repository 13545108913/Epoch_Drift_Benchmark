import ast
import json
import logging
import re
from urllib.parse import urlparse
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import base64
import io

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# =========================
# Action taxonomy
# =========================

ELEMENT_ACTIONS = {
    "click",
    "hover",
    "focus",
    "fill",
    "type",
    "select_option",
    "check",
    "uncheck",
    "dblclick",
    "tap",
}

KEYBOARD_ACTIONS = {
    "press",
    "keyboard_press",
    "hotkey",
}

NAVIGATION_ACTIONS = {
    "goto",
    "open_url",
    "navigate",
    "go_back",
    "go_forward",
}

SCROLL_ACTIONS = {
    "scroll",
    "scroll_to",
    "scroll_into_view",
    "scroll_by",
}

TAB_ACTIONS = {
    "new_tab",
    "tab_focus",
    "tab_close",
}

CONTROL_ACTIONS = {
    "noop",
    "send_msg_to_user",
    "report_infeasible",
}

BASE_ACTIONS = (
    ELEMENT_ACTIONS
    | KEYBOARD_ACTIONS
    | NAVIGATION_ACTIONS
    | SCROLL_ACTIONS
    | TAB_ACTIONS
    | CONTROL_ACTIONS
)

POTENTIALLY_DESTRUCTIVE = {}

ROLE_PRIORS = {
    "button": 0.06,
    "link": 0.07,
    "menuitem": 0.05,
    "tab": 0.07,
    "textbox": 0.04,
    "searchbox": 0.05,
    "combobox": 0.05,
    "grid": 0.02,
    "table": 0.02,
}

def _image_to_jpg_base64_url(image: np.ndarray | Image.Image):
    if isinstance(image, np.ndarray):
        image = Image.fromarray(image)
    if image.mode in ("RGBA", "LA"):
        image = image.convert("RGB")

    with io.BytesIO() as buffer:
        image.save(buffer, format="JPEG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/jpeg;base64,{image_base64}"

# =========================
# Data classes
# =========================

@dataclass
class CandidateFeatures:
    stability: float = 0.5
    visibility: float = 0.5
    availability: float = 0.5
    task_relevance: float = 0.5
    progress_likelihood: float = 0.5
    answer_exposure: float = 0.5
    risk_level: float = 0.5
    readiness: float = 0.5
    region: str = "unknown"
    readiness_label: str = "unknown"


@dataclass
class LLMStats:
    total_pairs: int = 0
    llm_success: int = 0
    llm_tie: int = 0
    llm_parse_fallback: int = 0
    llm_exception_fallback: int = 0
    llm_unavailable_fallback: int = 0


@dataclass
class SkillSpec:
    name: str
    signature: str
    description: str
    examples: List[str] = field(default_factory=list)
    source: Optional[str] = None


@dataclass
class ActionRegistry:
    base_actions: Dict[str, dict] = field(default_factory=dict)
    skills: Dict[str, SkillSpec] = field(default_factory=dict)
    describe_text: str = ""


# =========================
# Public entrypoint
# =========================

def select_best_action(env, agent, current_obs: dict, candidates: List[dict]):
    selection_info: Dict[str, Any] = {
        "n_candidates": len(candidates or []),
        "raw_candidates": candidates or [],
        "filtered_out": [],
        "kept_candidates": [],
        "pairwise_trace": [],
        "used_model": False,
        "fallback_used": False,
        "winner_index": None,
        "llm_stats": asdict(LLMStats()),
    }

    if not candidates:
        selection_info["error"] = "empty candidates"
        return None, selection_info

    registry = _get_or_build_action_registry(agent)
    selection_info["registry"] = {
        "n_base_actions": len(registry.base_actions),
        "n_skills": len(registry.skills),
        "skill_names": sorted(list(registry.skills.keys()))[:200],
    }

    page = _safe_get_page(env)
    enriched: List[Dict[str, Any]] = []

    for idx, cand in enumerate(candidates):
        action = cand.get("action", "")
        reason = cand.get("reason", "")
        parsed = _parse_action(action, registry=registry)
        parsed["goal"] = _goal_text(current_obs)

        live = _probe_live_page(page, parsed)
        obs_meta = _probe_obs_candidate(current_obs, parsed, live)
        prereq = _infer_prerequisites(parsed, live, obs_meta, current_obs)

        candidate = {
            "idx": idx,
            "action": action,
            "reason": reason,
            "parsed": parsed,
            "live": live,
            "obs_meta": obs_meta,
            "prereq": prereq,
        }

        feats = _extract_features(agent, candidate, current_obs=current_obs)
        candidate["features"] = feats
        candidate["heuristic_score"] = _heuristic_score(feats)
        enriched.append(candidate)
    
    print(f"Candidate actions:\n {[(can['action'], can['heuristic_score']) for can in enriched]}")

    selection_info["kept_candidates"] = [_serialize_candidate(c) for c in enriched]

    if not enriched:
        fallback = _fallback_from_raw(candidates, current_obs)
        selection_info["fallback_used"] = True
        selection_info["winner_action"] = fallback
        selection_info["error"] = "all candidates filtered out"
        return fallback, selection_info

    if len(enriched) == 1:
        winner = enriched[0]
        selection_info["winner_index"] = winner["idx"]
        selection_info["winner_action"] = winner["action"]
        return winner["action"], selection_info

    winner, used_model, trace, llm_stats = _rank_candidates(agent, registry, current_obs, enriched)
    selection_info["pairwise_trace"] = trace
    selection_info["used_model"] = used_model
    selection_info["winner_index"] = winner["idx"]
    selection_info["winner_action"] = winner["action"]
    selection_info["llm_stats"] = asdict(llm_stats)
    return winner["action"], selection_info


# =========================
# Registry / skill parsing
# =========================

def _get_or_build_action_registry(agent) -> ActionRegistry:
    cached = getattr(agent, "_action_registry_cache", None)
    if cached is not None:
        return cached

    registry = build_action_registry(agent)
    try:
        setattr(agent, "_action_registry_cache", registry)
    except Exception:
        pass
    return registry


def build_action_registry(agent) -> ActionRegistry:
    registry = ActionRegistry()
    for name in sorted(BASE_ACTIONS):
        registry.base_actions[name] = {"name": name, "kind": _action_kind(name, None)}

    describe_text = ""
    try:
        describe_text = agent.action_set.describe(
            with_long_description=True,
            with_examples=True,
        )
    except Exception as e:
        logger.warning("failed to read action_set.describe(...): %s", e)

    registry.describe_text = describe_text or ""

    if registry.describe_text:
        for skill in _parse_describe_text(registry.describe_text):
            if skill.name not in registry.base_actions:
                registry.skills[skill.name] = skill

    return registry


def _parse_describe_text(text: str) -> List[SkillSpec]:
    """
    Parse action_set.describe(with_long_description=True, with_examples=True) output.

    We only extract custom callable definitions shown as:
        def some_skill(...):
            \"\"\"...\"\"\"
            ...
    """
    skills: List[SkillSpec] = []
    if not text:
        return skills

    blocks = re.split(r"\n(?=def\s+\w+\()", text, flags=re.S)
    for block in blocks:
        block = block.strip()
        if not block.startswith("def "):
            continue

        sig_match = re.match(r"def\s+(\w+)\((.*?)\):", block, flags=re.S)
        if not sig_match:
            continue

        name = sig_match.group(1).strip()
        signature = f"{name}({sig_match.group(2).strip()})"

        desc_match = re.search(r'"""(.*?)"""', block, flags=re.S)
        description = desc_match.group(1).strip() if desc_match else ""

        examples: List[str] = []
        ex_match = re.search(r"Examples:\s*(.*)", description, flags=re.S)
        if ex_match:
            for line in ex_match.group(1).splitlines():
                line = line.strip()
                if line:
                    examples.append(line)

        skills.append(
            SkillSpec(
                name=name,
                signature=signature,
                description=description,
                examples=examples,
                source=block,
            )
        )

    return skills


# =========================
# Candidate serialization
# =========================

def _serialize_candidate(c: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "idx": c["idx"],
        "action": c["action"],
        "reason": c["reason"],
        "parsed": c["parsed"],
        "live": c["live"],
        "obs_meta": c["obs_meta"],
        "prereq": c.get("prereq"),
        "features": asdict(c["features"]),
        "heuristic_score": c["heuristic_score"],
    }


# =========================
# Feature extraction / scoring
# =========================

def _extract_features(agent, candidate: dict, current_obs: dict) -> CandidateFeatures:
    parsed = candidate["parsed"]
    action = candidate.get("action", "")
    reason = candidate.get("reason", "")
    live = candidate.get("live") or {}
    obs_meta = candidate.get("obs_meta") or {}
    prereq = candidate.get("prereq") or {}

    stability = _estimate_stability(parsed, reason, live, obs_meta)
    visibility = _estimate_visibility(parsed, live, obs_meta)
    availability = _estimate_availability(parsed, live, obs_meta)
    task_relevance = _estimate_task_relevance(reason, current_obs, action, obs_meta)
    progress_likelihood = _estimate_progress_likelihood(parsed, reason, current_obs, obs_meta, prereq)
    answer_exposure = _estimate_answer_exposure(parsed, reason, current_obs, obs_meta, live)
    risk_level = _estimate_risk(parsed, action, reason, live, obs_meta, current_obs)
    readiness, readiness_label = _estimate_readiness(parsed, live, obs_meta, prereq)
    region = live.get("region") or obs_meta.get("region") or _infer_region(agent, reason, current_obs)

    return CandidateFeatures(
        stability=stability,
        visibility=visibility,
        availability=availability,
        task_relevance=task_relevance,
        progress_likelihood=progress_likelihood,
        answer_exposure=answer_exposure,
        risk_level=risk_level,
        readiness=readiness,
        region=region,
        readiness_label=readiness_label,
    )


def _heuristic_score(feats: CandidateFeatures) -> float:
    region_bonus = {
        "main": 0.07,
        "nav": 0.05,
        "sidebar": 0.03,
        "modal": 0.01,
        "header": 0.00,
        "footer": -0.03,
        "form": 0.02,
        "unknown": 0.0,
    }.get(feats.region, 0.0)

    readiness_bonus = {
        "ready_now": 0.06,
        "needs_scroll": 0.02,
        "needs_expand": 0.01,
        "needs_focus": 0.00,
        "needs_navigation": -0.01,
        "blocked": -0.08,
        "unknown": 0.0,
    }.get(feats.readiness_label, 0.0)

    score = (
        0.16 * feats.stability
        + 0.12 * feats.visibility
        + 0.12 * feats.availability
        + 0.18 * feats.task_relevance
        + 0.17 * feats.progress_likelihood
        + 0.11 * feats.answer_exposure
        + 0.16 * feats.readiness
        - 0.18 * feats.risk_level
        + region_bonus
        + readiness_bonus
    )
    return _clip01(score)


# =========================
# Ranking
# =========================

def _rank_candidates(agent, registry: ActionRegistry, current_obs: dict, enriched: List[dict]):
    trace: List[Dict[str, Any]] = []
    llm_handle = _find_llm(agent)
    llm_stats = LLMStats()

    # Keep heuristics for coarse shortlist only.
    # Skills are NOT expanded for heuristic scoring.
    enriched = sorted(
        enriched,
        key=lambda c: (
            c["heuristic_score"],
            c["features"].task_relevance,
            c["features"].readiness,
        ),
        reverse=True,
    )

    top_k = min(5, len(enriched))
    shortlist = enriched[:top_k]
    used_model = llm_handle is not None and len(shortlist) >= 2

    if not used_model:
        winner = shortlist[0]
        trace.append(
            {
                "mode": "heuristic_only",
                "shortlist": [c["idx"] for c in shortlist],
                "winner_idx": winner["idx"],
                "winner_action": winner["action"],
            }
        )
        if llm_handle is None:
            llm_stats.llm_unavailable_fallback += 1
        return winner, False, trace, llm_stats

    # Round-robin pairwise voting
    wins = {c["idx"]: 0 for c in shortlist}
    pair_modes: Dict[str, int] = {}

    for i in range(len(shortlist)):
        for j in range(i + 1, len(shortlist)):
            a = shortlist[i]
            b = shortlist[j]

            llm_stats.total_pairs += 1
            winner_side, why, mode = _llm_compare_pair(agent, llm_handle, registry, current_obs, a, b)

            if mode == "llm_success":
                llm_stats.llm_success += 1
            elif mode == "llm_tie":
                llm_stats.llm_tie += 1
            elif mode == "llm_parse_fallback":
                llm_stats.llm_parse_fallback += 1
            elif mode == "llm_exception_fallback":
                llm_stats.llm_exception_fallback += 1
            elif mode == "llm_unavailable_fallback":
                llm_stats.llm_unavailable_fallback += 1

            if winner_side == "a":
                chosen = a
                wins[a["idx"]] += 1
            elif winner_side == "b":
                chosen = b
                wins[b["idx"]] += 1
            else:
                # Defensive fallback; _llm_compare_pair normally already resolves ties/fallbacks
                print("Using heuristic score!!!")
                chosen = a if a["heuristic_score"] >= b["heuristic_score"] else b
                wins[chosen["idx"]] += 1

            pair_modes[mode] = pair_modes.get(mode, 0) + 1

            trace.append(
                {
                    "mode": mode,
                    "a_idx": a["idx"],
                    "b_idx": b["idx"],
                    "winner_side": winner_side,
                    "winner_idx": chosen["idx"],
                    "winner_action": chosen["action"],
                    "why": why,
                }
            )

    # Final winner:
    # 1) most pairwise wins
    # 2) higher heuristic_score
    # 3) higher task_relevance
    # 4) higher readiness
    winner = max(
        shortlist,
        key=lambda c: (
            wins[c["idx"]],
            c["heuristic_score"],
            c["features"].task_relevance,
            c["features"].readiness,
        ),
    )

    trace.append(
        {
            "mode": "round_robin",
            "shortlist": [c["idx"] for c in shortlist],
            "wins": wins,
            "pair_mode_counts": pair_modes,
            "winner_idx": winner["idx"],
            "winner_action": winner["action"],
        }
    )

    return winner, True, trace, llm_stats


# =========================
# Page probes
# =========================

def _safe_get_page(env):
    try:
        return env.unwrapped.page
    except Exception:
        return None


def _probe_live_page(page, parsed: dict) -> Dict[str, Any]:
    info = {
        "exists": None,
        "visible": None,
        "enabled": None,
        "editable": None,
        "occluded": None,
        "bbox": None,
        "center": None,
        "viewport": None,
        "tag": None,
        "text": None,
        "aria": None,
        "role": None,
        "region": None,
        "matches": [],
        "url_relevance": None,
        "probe_mode": parsed.get("kind", "unknown"),
        "probe_error": None,
    }

    if page is None:
        info["probe_error"] = "page_unavailable"
        return info

    kind = parsed.get("kind")
    try:
        if kind == "element":
            result = _probe_element_target(page, parsed)
        elif kind == "navigation":
            result = _probe_navigation_target(page, parsed)
        elif kind == "keyboard":
            result = _probe_keyboard_target(page, parsed)
        elif kind == "scroll":
            result = _probe_scroll_target(page, parsed)
        elif kind == "tab":
            result = _probe_tab_target(page, parsed)
        elif kind == "control":
            result = _probe_control_target(page, parsed)
        elif kind == "skill":
            result = _probe_skill_target(page, parsed)
        else:
            result = {"probe_error": "unsupported_probe_kind"}
        if isinstance(result, dict):
            info.update(result)
        else:
            info["probe_error"] = f"unexpected_probe_result:{type(result).__name__}"
    except Exception as e:
        info["probe_error"] = f"page_probe_error:{type(e).__name__}:{e}"

    return info


ELEMENT_PROBE_JS = r'''
(target) => {
  const out = {
    exists: false,
    visible: null,
    enabled: null,
    editable: null,
    occluded: null,
    bbox: null,
    center: null,
    viewport: null,
    tag: null,
    text: null,
    aria: null,
    role: null,
    region: null,
    matches: [],
    candidate_count: 0,
    unique_elements_count: 0,
    best_source: null,
    exact_selector_match_count: 0,
    text_filtered_count: 0,
  };

  const vw = window.innerWidth || document.documentElement.clientWidth || 0;
  const vh = window.innerHeight || document.documentElement.clientHeight || 0;
  out.viewport = { width: vw, height: vh };

  const selectors = [];
  const add = (sel, source, opts = {}) => {
    if (!sel || selectors.some(x => x.sel === sel && x.source === source)) return;
    selectors.push({ sel, source, textFilter: opts.textFilter || null });
  };

  const safe = (v) => String(v || '').trim();
  const bid = safe(target.bid);
  const selector = safe(target.selector);
  const text = safe(target.text);
  const targetId = safe(target.id);
  const role = safe(target.role);
  const aria = safe(target.aria);
  const normalizedTargetText = text.toLowerCase();

  if (bid) {
    add(`[bid="${CSS.escape(bid)}"]`, 'bid');
    add(`[data-bid="${CSS.escape(bid)}"]`, 'data-bid');
    add(`[id="${CSS.escape(bid)}"]`, 'id-from-bid');
  }
  if (targetId) add(`#${CSS.escape(targetId)}`, 'id');
  if (selector) add(selector, 'selector');
  if (aria) add(`[aria-label="${CSS.escape(aria)}"]`, 'aria');
  if (role) add(`[role="${CSS.escape(role)}"]`, text ? 'role+text-filter' : 'role', { textFilter: text || null });

  const rawCandidates = [];
  for (const entry of selectors) {
    try {
      const nodes = Array.from(document.querySelectorAll(entry.sel)).slice(0, 12);
      for (const el of nodes) {
        if (entry.textFilter) {
          const t = ((el.innerText || el.textContent || el.value || '') + ' ' + (el.getAttribute('aria-label') || '')).trim().toLowerCase();
          if (!t || !t.includes(entry.textFilter.toLowerCase())) continue;
          out.text_filtered_count += 1;
        }
        rawCandidates.push({ el, source: entry.source, selector: entry.sel });
      }
    } catch (e) {
      continue;
    }
  }

  if (!rawCandidates.length && normalizedTargetText) {
    const nodes = Array.from(document.querySelectorAll('button, a, input, textarea, select, option, label, [role], [tabindex], td, th, span, div')).slice(0, 400);
    for (const el of nodes) {
      const t = ((el.innerText || el.textContent || el.value || '') + ' ' + (el.getAttribute('aria-label') || '')).trim().toLowerCase();
      if (t && t.includes(normalizedTargetText)) {
        rawCandidates.push({ el, source: 'text-search', selector: null });
        if (rawCandidates.length >= 12) break;
      }
    }
  }

  out.candidate_count = rawCandidates.length;
  if (!rawCandidates.length) return out;

  const deduped = [];
  const byEl = new Map();
  const priority = ['selector', 'bid', 'data-bid', 'id', 'id-from-bid', 'aria', 'role+text-filter', 'role', 'text-search'];
  for (const entry of rawCandidates) {
    const existing = byEl.get(entry.el);
    if (!existing) {
      const merged = {
        el: entry.el,
        selector: entry.selector,
        bestSource: entry.source,
        sources: [entry.source],
        selectors: entry.selector ? [entry.selector] : [],
      };
      byEl.set(entry.el, merged);
      deduped.push(merged);
    } else {
      if (!existing.sources.includes(entry.source)) existing.sources.push(entry.source);
      if (entry.selector && !existing.selectors.includes(entry.selector)) existing.selectors.push(entry.selector);
      const curr = priority.indexOf(existing.bestSource);
      const nxt = priority.indexOf(entry.source);
      if (curr == -1 || (nxt != -1 && nxt < curr)) {
        existing.bestSource = entry.source;
        existing.selector = entry.selector || existing.selector;
      }
    }
  }

  out.unique_elements_count = deduped.length;
  if (selector) {
    out.exact_selector_match_count = deduped.filter((x) => x.selectors.includes(selector)).length;
  }

  const scoreEl = (entry) => {
    const el = entry.el;
    let score = 0;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    const visible = !!(
      rect && rect.width > 0 && rect.height > 0 &&
      style.visibility !== 'hidden' &&
      style.display !== 'none' &&
      parseFloat(style.opacity || '1') > 0.01
    );
    if (visible) score += 4;
    if (rect.top >= 0 && rect.left >= 0 && rect.bottom <= vh && rect.right <= vw) score += 2;
    if (['selector', 'bid', 'data-bid', 'id', 'id-from-bid'].includes(entry.bestSource)) score += 4;
    if (entry.bestSource === 'aria' || entry.bestSource === 'role+text-filter') score += 3;
    if (entry.bestSource === 'role') score += 1;
    if (entry.bestSource === 'text-search') score += 1;
    const tag = (el.tagName || '').toLowerCase();
    if (['button', 'a', 'input', 'select', 'textarea', 'option'].includes(tag)) score += 2;
    if (normalizedTargetText) {
      const t = ((el.innerText || el.textContent || el.value || '') + ' ' + (el.getAttribute('aria-label') || '')).trim().toLowerCase();
      if (t && t.includes(normalizedTargetText)) score += 2;
    }
    return score;
  };

  deduped.sort((a, b) => scoreEl(b) - scoreEl(a));
  const entry = deduped[0];
  const el = entry.el;
  const rect = el.getBoundingClientRect();
  const style = window.getComputedStyle(el);
  const hasBox = rect && rect.width > 0 && rect.height > 0;
  const visible = !!(
    hasBox &&
    style.visibility !== 'hidden' &&
    style.display !== 'none' &&
    parseFloat(style.opacity || '1') > 0.01 &&
    rect.bottom >= 0 &&
    rect.right >= 0 &&
    rect.top <= vh &&
    rect.left <= vw
  );

  out.exists = true;
  out.best_source = entry.bestSource;
  out.tag = (el.tagName || '').toLowerCase();
  out.text = (el.innerText || el.textContent || el.value || '').trim().slice(0, 240);
  out.aria = el.getAttribute('aria-label') || el.getAttribute('name') || '';
  out.role = (el.getAttribute('role') || '').toLowerCase() || null;
  out.visible = visible;

  const disabled = el.disabled === true || el.getAttribute('disabled') !== null || el.getAttribute('aria-disabled') === 'true';
  out.enabled = !disabled;
  out.editable = !!(el.isContentEditable || ['input', 'textarea', 'select'].includes(out.tag));

  if (hasBox) {
    out.bbox = {
      x: rect.x,
      y: rect.y,
      width: rect.width,
      height: rect.height,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      left: rect.left,
    };
    const cx = Math.min(Math.max(rect.left + rect.width / 2, 0), Math.max(vw - 1, 0));
    const cy = Math.min(Math.max(rect.top + rect.height / 2, 0), Math.max(vh - 1, 0));
    out.center = { x: cx, y: cy };
    const topEl = document.elementFromPoint(cx, cy);
    out.occluded = !!(topEl && topEl !== el && !el.contains(topEl) && !topEl.contains(el));
  }

  const regionEl = el.closest('main, nav, aside, header, footer, form, dialog, [role="main"], [role="navigation"], [role="dialog"], [role="search"]');
  if (regionEl) {
    const tag = (regionEl.tagName || '').toLowerCase();
    const role = (regionEl.getAttribute('role') || '').toLowerCase();
    if (role === 'main' || tag === 'main') out.region = 'main';
    else if (role === 'navigation' || tag === 'nav') out.region = 'nav';
    else if (tag === 'aside') out.region = 'sidebar';
    else if (role === 'dialog' || tag === 'dialog') out.region = 'modal';
    else if (tag === 'header') out.region = 'header';
    else if (tag === 'footer') out.region = 'footer';
    else if (tag === 'form') out.region = 'form';
  }

  out.matches = deduped.slice(0, 5).map((x) => ({
    source: x.bestSource,
    all_sources: x.sources,
    selector: x.selector,
    selector_count: x.selectors.length,
    tag: (x.el.tagName || '').toLowerCase(),
    text: (x.el.innerText || x.el.textContent || x.el.value || '').trim().slice(0, 100),
  }));
  return out;
}
'''


def _probe_element_target(page, parsed: dict) -> Dict[str, Any]:
    target = {
        "bid": parsed.get("bid"),
        "id": parsed.get("dom_id"),
        "selector": parsed.get("selector"),
        "text": parsed.get("text_hint"),
        "aria": parsed.get("aria_hint"),
        "role": parsed.get("role_hint"),
    }
    return page.evaluate(ELEMENT_PROBE_JS, target)


def _probe_navigation_target(page, parsed: dict) -> Dict[str, Any]:
    current_url = ""
    try:
        current_url = page.url or ""
    except Exception:
        current_url = ""

    target_url = str(parsed.get("url") or "")
    goal = str(parsed.get("goal") or "")
    same_domain = None
    if target_url and current_url:
        current_host = _host_of(current_url)
        target_host = _host_of(target_url)
        same_domain = bool(current_host and target_host and current_host == target_host)

    path_overlap = _url_keyword_overlap(goal, target_url)
    evidence = "guessed"
    matching_links = 0
    if page is not None and target_url:
        try:
            nav_meta = page.evaluate(
                r"""
(targetUrl) => {
  const norm = (u) => {
    try { return new URL(u, window.location.href).toString(); } catch (e) { return String(u || ''); }
  };
  const target = norm(targetUrl);
  const anchors = Array.from(document.querySelectorAll('a[href]')).slice(0, 500);
  let exact = 0;
  let samePath = 0;
  let bestHref = null;
  for (const a of anchors) {
    const href = a.getAttribute('href');
    const abs = norm(href);
    if (!abs) continue;
    if (abs === target) {
      exact += 1;
      bestHref = abs;
      continue;
    }
    try {
      const au = new URL(abs);
      const tu = new URL(target);
      if (au.origin === tu.origin && au.pathname === tu.pathname) {
        samePath += 1;
        if (!bestHref) bestHref = abs;
      }
    } catch (e) {}
  }
  return { exact, samePath, bestHref };
}
""",
                target_url,
            )
        except Exception:
            nav_meta = {}
        if isinstance(nav_meta, dict):
            exact = int(nav_meta.get("exact") or 0)
            same_path = int(nav_meta.get("samePath") or 0)
            matching_links = exact + same_path
            if exact > 0:
                evidence = "exact_link"
            elif same_path > 0:
                evidence = "same_page_href"

    relevance = 0.18
    if same_domain:
        relevance += 0.10
    relevance += 0.30 * path_overlap
    if evidence == "exact_link":
        relevance += 0.28
    elif evidence == "same_page_href":
        relevance += 0.16
    elif evidence == "guessed":
        relevance -= 0.10
    if target_url and target_url == current_url:
        relevance -= 0.25

    return {
        "exists": True,
        "visible": True,
        "enabled": True,
        "url_relevance": _clip01(relevance),
        "same_domain": same_domain,
        "current_url": current_url,
        "target_url": target_url,
        "navigation_evidence": evidence,
        "path_keyword_overlap": path_overlap,
        "matching_link_count": matching_links,
    }


KEYBOARD_PROBE_JS = r'''
(_) => {
  const el = document.activeElement;
  if (!el) return { exists: false, visible: null, enabled: null, focused_tag: null, region: null };
  const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
  const style = window.getComputedStyle ? window.getComputedStyle(el) : null;
  const visible = !!(
    rect && rect.width > 0 && rect.height > 0 && style &&
    style.visibility !== 'hidden' && style.display !== 'none' && parseFloat(style.opacity || '1') > 0.01
  );
  const tag = (el.tagName || '').toLowerCase();
  const role = (el.getAttribute && el.getAttribute('role') || '').toLowerCase();
  let region = null;
  const regionEl = el.closest && el.closest('main, nav, aside, header, footer, form, dialog, [role="main"], [role="navigation"], [role="dialog"], [role="search"]');
  if (regionEl) {
    const rtag = (regionEl.tagName || '').toLowerCase();
    const rrole = (regionEl.getAttribute('role') || '').toLowerCase();
    if (rrole === 'main' || rtag === 'main') region = 'main';
    else if (rrole === 'navigation' || rtag === 'nav') region = 'nav';
    else if (rtag === 'aside') region = 'sidebar';
    else if (rrole === 'dialog' || rtag === 'dialog') region = 'modal';
    else if (rtag === 'header') region = 'header';
    else if (rtag === 'footer') region = 'footer';
    else if (rtag === 'form') region = 'form';
  }
  const disabled = el.disabled === true || el.getAttribute('disabled') !== null || el.getAttribute('aria-disabled') === 'true';
  return {
    exists: true,
    visible,
    enabled: !disabled,
    editable: !!(el.isContentEditable || ['input', 'textarea', 'select'].includes(tag)),
    focused_tag: tag,
    focused_role: role || null,
    focused_text: (el.innerText || el.textContent || el.value || '').trim().slice(0, 120),
    region,
  };
}
'''


def _probe_keyboard_target(page, parsed: dict) -> Dict[str, Any]:
    out = page.evaluate(KEYBOARD_PROBE_JS, None)
    out["key"] = parsed.get("key")
    return out


SCROLL_PROBE_JS = r'''
(_) => {
  const vw = window.innerWidth || document.documentElement.clientWidth || 0;
  const vh = window.innerHeight || document.documentElement.clientHeight || 0;
  return {
    exists: true,
    visible: true,
    enabled: true,
    viewport: { width: vw, height: vh },
    region: 'main',
    scroll_y: window.scrollY || window.pageYOffset || 0,
    scroll_height: document.documentElement.scrollHeight || document.body.scrollHeight || 0,
  };
}
'''


def _probe_scroll_target(page, parsed: dict) -> Dict[str, Any]:
    out = page.evaluate(SCROLL_PROBE_JS, None)
    dy = parsed.get("scroll_dy")
    if isinstance(dy, (int, float)):
        out["scroll_direction"] = "down" if dy > 0 else "up" if dy < 0 else "none"
    else:
        out["scroll_direction"] = "unknown"
    return out


TAB_PROBE_JS = r'''
(_) => {
  return {
    exists: true,
    visible: true,
    enabled: true,
    region: 'header',
  };
}
'''


def _probe_tab_target(page, parsed: dict) -> Dict[str, Any]:
    out = page.evaluate(TAB_PROBE_JS, None)
    out["tab_action"] = parsed.get("name")
    out["tab_index"] = parsed.get("tab_index")
    return out


CONTROL_PROBE_JS = r'''
(_) => {
  return {
    exists: true,
    visible: true,
    enabled: true,
    region: 'unknown',
  };
}
'''


def _probe_control_target(page, parsed: dict) -> Dict[str, Any]:
    out = page.evaluate(CONTROL_PROBE_JS, None)
    out["control_action"] = parsed.get("name")
    out["message"] = parsed.get("message")
    out["wait_ms"] = parsed.get("wait_ms")
    return out


def _probe_skill_target(page, parsed: dict) -> Dict[str, Any]:
    # No expansion. Only minimal probe so skills remain a first-class action kind
    # and can participate in coarse heuristic shortlist before LLM pairwise compare.
    return {
        "exists": True,
        "visible": True,
        "enabled": True,
        "region": "unknown",
        "skill_name": parsed.get("name"),
        "probe_mode": "skill_no_expand",
    }


# =========================
# Observation probe
# =========================

def _probe_obs_candidate(current_obs: dict, parsed: dict, live: dict) -> Dict[str, Any]:
    out = {
        "bid": None,
        "obs_exists": None,
        "obs_visible": None,
        "obs_enabled": None,
        "role": None,
        "text": None,
        "region": None,
        "focused_match": None,
        "focused_role": None,
        "focused_text": None,
    }
    if not isinstance(current_obs, dict):
        return out

    kind = parsed.get("kind")
    bid = str(parsed.get("bid") or parsed.get("target") or "").strip()
    if bid:
        out["bid"] = bid

    props = current_obs.get("extra_element_properties")
    elem = None
    if kind == "element" and isinstance(props, dict) and bid:
        elem = props.get(bid)
        if elem is None and bid.isdigit():
            elem = props.get(int(bid))

    if isinstance(elem, dict):
        out["obs_exists"] = True
        for k in ["text", "innerText", "value", "label", "name", "aria_label", "placeholder", "title"]:
            v = elem.get(k)
            if isinstance(v, str) and v.strip():
                out["text"] = v.strip()[:240]
                break

        for k in ["visible", "is_visible", "in_viewport", "clickable"]:
            if k in elem and isinstance(elem.get(k), bool):
                out["obs_visible"] = elem.get(k)
                break

        for k in ["enabled", "is_enabled"]:
            if k in elem and isinstance(elem.get(k), bool):
                out["obs_enabled"] = elem.get(k)
                break
        if out["obs_enabled"] is None:
            disabled = elem.get("disabled")
            if isinstance(disabled, bool):
                out["obs_enabled"] = not disabled

        for k in ["role", "tag", "tag_name", "node_type", "type"]:
            v = elem.get(k)
            if isinstance(v, str) and v.strip():
                out["role"] = v.strip().lower()
                break

        for k in ["region", "section", "container", "area"]:
            v = elem.get(k)
            if isinstance(v, str) and v.strip():
                out["region"] = _normalize_region(v)
                break

    focused = current_obs.get("focused_element_bid")
    if focused is not None and bid:
        out["focused_match"] = str(focused) == bid

    focused_props = None
    if isinstance(props, dict) and focused is not None:
        focused_props = props.get(str(focused)) or props.get(focused)
    if isinstance(focused_props, dict):
        out["focused_role"] = str(focused_props.get("role") or focused_props.get("tag") or "").lower() or None
        for k in ["text", "innerText", "value", "label", "name", "aria_label", "placeholder", "title"]:
            v = focused_props.get(k)
            if isinstance(v, str) and v.strip():
                out["focused_text"] = v.strip()[:160]
                break

    if live.get("region") and not out.get("region"):
        out["region"] = live["region"]
    if live.get("text") and not out.get("text"):
        out["text"] = str(live["text"])[:240]
    if live.get("role") and not out.get("role"):
        out["role"] = str(live["role"]).lower()
    if live.get("tag") and not out.get("role"):
        out["role"] = str(live["tag"]).lower()

    return out


# =========================
# Action parsing
# =========================

def _parse_action(action: str, registry: Optional[ActionRegistry] = None) -> Dict[str, Any]:
    raw = action or ""
    text = _strip_code_fence(raw)
    text = _strip_wrapping_semicolon(text)

    locator = _parse_playwright_chain(text, registry=registry)
    if locator:
        return locator

    func = _parse_function_style(text, registry=registry)
    if func:
        return func

    return {
        "raw": raw,
        "normalized": text,
        "name": "unknown",
        "kind": "unknown",
        "args": [],
        "kwargs": {},
        "target": None,
        "bid": None,
        "selector": None,
        "text_hint": None,
        "aria_hint": None,
        "role_hint": None,
        "dom_id": None,
        "url": None,
        "key": None,
        "scroll_dx": None,
        "scroll_dy": None,
        "tab_index": None,
        "wait_ms": None,
        "message": None,
        "skill_source": None,
    }


def _parse_playwright_chain(text: str, registry: Optional[ActionRegistry] = None) -> Optional[Dict[str, Any]]:
    if not text or ".locator(" not in text:
        return None

    m = re.search(r"\.locator\((.+?)\)(?:\.filter\((.+?)\))?\.([a-zA-Z_][a-zA-Z0-9_]*)\((.*)\)\s*$", text, flags=re.S)
    if not m:
        return None

    selector_expr = m.group(1).strip()
    action_name = m.group(3).strip().lower()
    action_args_str = m.group(4).strip()
    selector = _literal_eval_or_text(selector_expr)
    args, kwargs = _parse_call_args(action_args_str)

    text_hint = None
    dom_id = None
    if isinstance(selector, str):
        text_hint = _selector_text_hint(selector)
        dom_id = _selector_dom_id(selector)

    parsed = {
        "raw": text,
        "normalized": text,
        "name": action_name,
        "kind": _action_kind(action_name, registry),
        "args": args,
        "kwargs": kwargs,
        "target": selector,
        "bid": None,
        "selector": selector if isinstance(selector, str) else None,
        "text_hint": text_hint,
        "aria_hint": None,
        "role_hint": None,
        "dom_id": dom_id,
        "url": None,
        "key": None,
        "scroll_dx": None,
        "scroll_dy": None,
        "tab_index": None,
        "wait_ms": None,
        "message": None,
        "skill_source": None,
    }

    if action_name in NAVIGATION_ACTIONS and args:
        parsed["url"] = _strip_quotes(args[0])
    if action_name in KEYBOARD_ACTIONS and args:
        parsed["key"] = _strip_quotes(args[0])
    if action_name in TAB_ACTIONS:
        if action_name == "tab_focus" and args:
            try:
                parsed["tab_index"] = int(_strip_quotes(args[0]))
            except Exception:
                parsed["tab_index"] = None
    if action_name in CONTROL_ACTIONS:
        if action_name == "noop":
            wait_ms = args[0] if args else kwargs.get("wait_ms")
            parsed["wait_ms"] = _coerce_number(wait_ms)
        elif action_name in {"send_msg_to_user", "report_infeasible"}:
            msg = args[0] if args else kwargs.get("text") or kwargs.get("reason")
            parsed["message"] = _strip_quotes(msg) if isinstance(msg, str) else msg

    if parsed["kind"] == "skill" and registry is not None:
        spec = registry.skills.get(action_name)
        if spec:
            parsed["skill_source"] = spec.source

    return parsed


def _parse_function_style(text: str, registry: Optional[ActionRegistry] = None) -> Optional[Dict[str, Any]]:
    m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\((.*)\)\s*$", text, flags=re.S)
    if not m:
        return None

    name = m.group(1).lower()
    args_str = m.group(2).strip()
    args, kwargs = _parse_call_args(args_str)
    kind = _action_kind(name, registry)

    parsed = {
        "raw": text,
        "normalized": text,
        "name": name,
        "kind": kind,
        "args": args,
        "kwargs": kwargs,
        "target": None,
        "bid": None,
        "selector": None,
        "text_hint": None,
        "aria_hint": None,
        "role_hint": None,
        "dom_id": None,
        "url": None,
        "key": None,
        "scroll_dx": None,
        "scroll_dy": None,
        "tab_index": None,
        "wait_ms": None,
        "message": None,
        "skill_source": None,
    }

    if kind == "element":
        first = kwargs.get("target") if "target" in kwargs else (args[0] if args else None)
        second = args[1] if len(args) > 1 else None
        target = _strip_quotes(first) if isinstance(first, str) else first
        parsed["target"] = target
        if isinstance(target, str):
            if _looks_selector(target):
                parsed["selector"] = target
                parsed["dom_id"] = _selector_dom_id(target)
                parsed["text_hint"] = _selector_text_hint(target)
            elif target.isdigit():
                parsed["bid"] = target
            else:
                parsed["selector"] = target if any(x in target for x in ["#", ".", "[", ">", ":"]) else None
                parsed["text_hint"] = None if parsed["selector"] else target
                parsed["dom_id"] = _selector_dom_id(target) if parsed["selector"] else None
        if name in {"fill", "type", "select_option"} and second is not None:
            parsed["value"] = _strip_quotes(second) if isinstance(second, str) else second

    elif kind == "navigation":
        if name in {"go_back", "go_forward"}:
            parsed["target"] = name
        else:
            first = kwargs.get("url") if "url" in kwargs else (args[0] if args else None)
            parsed["url"] = _strip_quotes(first) if isinstance(first, str) else first
            parsed["target"] = parsed["url"]

    elif kind == "keyboard":
        first = kwargs.get("key") if "key" in kwargs else (args[0] if args else None)
        parsed["key"] = _strip_quotes(first) if isinstance(first, str) else first
        parsed["target"] = parsed["key"]

    elif kind == "scroll":
        dx = kwargs.get("x") if "x" in kwargs else (args[0] if len(args) > 0 else None)
        dy = kwargs.get("y") if "y" in kwargs else (args[1] if len(args) > 1 else None)
        parsed["scroll_dx"] = _coerce_number(dx)
        parsed["scroll_dy"] = _coerce_number(dy)
        parsed["target"] = f"{parsed['scroll_dx']},{parsed['scroll_dy']}"

    elif kind == "tab":
        if name == "tab_focus":
            idx = kwargs.get("index") if "index" in kwargs else (args[0] if args else None)
            try:
                parsed["tab_index"] = int(_strip_quotes(idx))
            except Exception:
                parsed["tab_index"] = None
            parsed["target"] = parsed["tab_index"]
        else:
            parsed["target"] = name

    elif kind == "control":
        if name == "noop":
            wait_ms = kwargs.get("wait_ms") if "wait_ms" in kwargs else (args[0] if args else 1000)
            parsed["wait_ms"] = _coerce_number(wait_ms) or 1000.0
            parsed["target"] = parsed["wait_ms"]
        elif name in {"send_msg_to_user", "report_infeasible"}:
            msg = kwargs.get("text") or kwargs.get("reason") or (args[0] if args else "")
            parsed["message"] = _strip_quotes(msg) if isinstance(msg, str) else msg
            parsed["target"] = parsed["message"]

    elif kind == "skill":
        parsed["target"] = name
        if registry is not None:
            spec = registry.skills.get(name)
            if spec:
                parsed["skill_source"] = spec.source

    return parsed


def _parse_call_args(args_str: str) -> Tuple[List[Any], Dict[str, Any]]:
    if not args_str:
        return [], {}

    try:
        call = ast.parse(f"f({args_str})", mode="eval")
        if not isinstance(call.body, ast.Call):
            return _split_args(args_str), {}
        args = [_ast_literal_or_source(arg, args_str) for arg in call.body.args]
        kwargs = {}
        for kw in call.body.keywords:
            if kw.arg:
                kwargs[kw.arg] = _ast_literal_or_source(kw.value, args_str)
        return args, kwargs
    except Exception:
        return _split_args(args_str), {}


def _ast_literal_or_source(node: ast.AST, source: str) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        segment = ast.get_source_segment(f"f({source})", node)
        if segment is None:
            return None
        return segment


def _split_args(args_str: str) -> List[str]:
    if not args_str:
        return []
    parts = []
    cur = []
    depth = 0
    quote = None
    escape = False
    for ch in args_str:
        if escape:
            cur.append(ch)
            escape = False
            continue
        if ch == "\\":
            cur.append(ch)
            escape = True
            continue
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ('"', "'"):
            cur.append(ch)
            quote = ch
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return parts


# =========================
# Prerequisites / readiness
# =========================

def _infer_prerequisites(parsed: dict, live: dict, obs_meta: dict, current_obs: dict) -> Dict[str, Any]:
    kind = parsed.get("kind")
    exists = _coalesce_bool(live.get("exists"), obs_meta.get("obs_exists"))
    visible = _coalesce_bool(live.get("visible"), obs_meta.get("obs_visible"))
    enabled = _coalesce_bool(live.get("enabled"), obs_meta.get("obs_enabled"))
    focused_match = obs_meta.get("focused_match")
    last_error = str(current_obs.get("last_action_error") or "").lower()

    status = "unknown"
    why = ""

    if kind in {"navigation", "scroll", "tab", "control", "skill"}:
        status = "ready_now"
    elif kind == "keyboard":
        if focused_match is True or live.get("editable") is True:
            status = "ready_now"
        elif live.get("exists") is True:
            status = "needs_focus"
            why = "keyboard action likely needs focus first"
        else:
            status = "needs_focus"
            why = "no active input context"
    elif kind == "element":
        if exists is False:
            status = "blocked"
            why = "target does not exist"
        elif visible is True and enabled is True:
            status = "ready_now"
        elif visible is False and exists is True:
            status = "needs_scroll"
            why = "target exists but is not visible"
        elif enabled is False and exists is True:
            status = "needs_expand"
            why = "target exists but is disabled or gated"
        else:
            status = "unknown"
    else:
        status = "unknown"

    if "intercept" in last_error or "occluded" in last_error:
        if status == "ready_now":
            status = "needs_scroll"
            why = why or "previous click was intercepted/occluded"
    return {"status": status, "why": why}


# =========================
# Estimators
# =========================

def _estimate_stability(parsed: dict, reason: str, live: dict, obs_meta: dict) -> float:
    score = 0.48
    selector = parsed.get("selector")
    bid = parsed.get("bid")
    kind = parsed.get("kind")

    if kind == "navigation":
        score = 0.42
        evidence = str(live.get("navigation_evidence") or "")
        overlap = float(live.get("path_keyword_overlap") or 0.0)
        if live.get("same_domain") is True:
            score += 0.06
        if evidence == "exact_link":
            score += 0.18
        elif evidence == "same_page_href":
            score += 0.10
        elif evidence == "guessed":
            score -= 0.08
        score += min(0.10, 0.10 * overlap)
        return _clip01(score)

    if kind == "scroll":
        return 0.68
    if kind == "keyboard":
        return 0.58 if live.get("editable") is True or obs_meta.get("focused_match") is True else 0.42
    if kind == "tab":
        return 0.78
    if kind == "control":
        if parsed.get("name") == "noop":
            return 0.90
        return 0.85
    if kind == "skill":
        # We do not expand skills or infer internal structure heuristically.
        # Keep a neutral value and defer pairwise preference to the LLM.
        return 0.50

    if live.get("exists") is True or obs_meta.get("obs_exists") is True:
        score += 0.12
    if selector:
        score += 0.08
        if isinstance(selector, str) and (selector.startswith("#") or "[aria-" in selector or "[role=" in selector):
            score += 0.05
    if bid:
        score += 0.02

    unique_count = live.get("unique_elements_count")
    exact_selector_match_count = live.get("exact_selector_match_count")
    best_source = str(live.get("best_source") or "")
    if unique_count == 1:
        score += 0.08
    elif isinstance(unique_count, int) and unique_count > 1:
        score -= 0.04
    if isinstance(exact_selector_match_count, int):
        if exact_selector_match_count == 1:
            score += 0.06
        elif exact_selector_match_count > 1:
            score -= 0.04
    if best_source in {"selector", "bid", "data-bid", "id", "id-from-bid", "aria", "role+text-filter"}:
        score += 0.03
    elif best_source in {"role", "text-search"}:
        score -= 0.02

    role = obs_meta.get("role") or live.get("role") or live.get("tag")
    if isinstance(role, str):
        score += ROLE_PRIORS.get(role.lower(), 0.0)
    if obs_meta.get("focused_match") is True:
        score += 0.04
    if parsed.get("text_hint") and isinstance(parsed.get("text_hint"), str) and len(parsed.get("text_hint")) >= 3:
        score += 0.03
    if isinstance(reason, str) and any(k in reason.lower() for k in ["exact", "specific", "tab", "menu"]):
        score += 0.02
    return _clip01(score)


def _estimate_visibility(parsed: dict, live: dict, obs_meta: dict) -> float:
    kind = parsed.get("kind")
    if kind in {"navigation", "scroll", "tab", "control", "skill"}:
        if kind == "control" and parsed.get("name") in {"send_msg_to_user", "report_infeasible"}:
            return 0.95
        return 0.65

    if kind == "keyboard" and live.get("visible") is False:
        return 0.35

    score = 0.5
    visible = _coalesce_bool(live.get("visible"), obs_meta.get("obs_visible"))
    if visible is True:
        score += 0.35
    elif visible is False:
        score -= 0.30
    if live.get("occluded") is True:
        score -= 0.22
    return _clip01(score)


def _estimate_availability(parsed: dict, live: dict, obs_meta: dict) -> float:
    kind = parsed.get("kind")
    if kind == "navigation":
        score = 0.40
        relevance = live.get("url_relevance")
        evidence = str(live.get("navigation_evidence") or "")
        if isinstance(relevance, (int, float)):
            score += 0.30 * float(relevance)
        if evidence == "exact_link":
            score += 0.14
        elif evidence == "same_page_href":
            score += 0.08
        elif evidence == "guessed":
            score -= 0.06
        return _clip01(score)

    if kind == "scroll":
        return 0.78
    if kind == "keyboard":
        return 0.72 if live.get("editable") is True or obs_meta.get("focused_match") is True else 0.45
    if kind == "tab":
        return 0.85
    if kind == "control":
        return 0.95
    if kind == "skill":
        return 0.55

    score = 0.5
    exists = _coalesce_bool(live.get("exists"), obs_meta.get("obs_exists"))
    enabled = _coalesce_bool(live.get("enabled"), obs_meta.get("obs_enabled"))
    if exists is True:
        score += 0.18
    elif exists is False:
        score -= 0.38
    if enabled is True:
        score += 0.24
    elif enabled is False:
        score -= 0.30
    if parsed.get("name") in {"fill", "type", "select_option"} and live.get("editable") is True:
        score += 0.05
    return _clip01(score)


def _estimate_task_relevance(reason: str, current_obs: dict, action: str, obs_meta: dict) -> float:
    goal = _goal_text(current_obs).lower()
    txt = f"{reason} {action}".lower()
    if obs_meta.get("text"):
        txt += " " + str(obs_meta["text"]).lower()

    if not goal:
        return 0.55

    goal_terms = [w for w in re.findall(r"[a-zA-Z0-9_\-]+", goal) if len(w) >= 4]
    overlap = sum(1 for t in set(goal_terms) if t in txt)
    score = 0.42 + min(0.34, overlap * 0.06)

    strong_markers = [
        "customer", "customers", "report", "reports", "orders", "completed",
        "top", "rank", "sort", "filter", "grid", "table", "search",
    ]
    score += min(0.18, sum(1 for k in strong_markers if k in txt and k in goal) * 0.04)
    if obs_meta.get("role") in {"tab", "link", "button", "menuitem"} and any(k in txt for k in ["open", "view", "show"]):
        score += 0.05

    nav_overlap = _url_keyword_overlap(goal, action)
    if any(tok in txt for tok in ["goto(", "open_url(", "navigate("]):
        score += 0.08 * nav_overlap
        if nav_overlap == 0.0:
            score -= 0.04
    return _clip01(score)


def _estimate_progress_likelihood(parsed: dict, reason: str, current_obs: dict, obs_meta: dict, prereq: dict) -> float:
    txt = f"{reason} {parsed.get('name', '')}".lower()
    goal = _goal_text(current_obs).lower()
    score = 0.45
    kind = parsed.get("kind")

    if prereq.get("status") == "ready_now":
        score += 0.18
    elif prereq.get("status") in {"needs_scroll", "needs_expand", "needs_focus"}:
        score += 0.02
    elif prereq.get("status") == "blocked":
        score -= 0.25

    if kind == "navigation":
        nav_overlap = _url_keyword_overlap(goal, parsed.get("url") or "")
        score += 0.02 + 0.10 * nav_overlap
        if nav_overlap == 0.0 and parsed.get("name") not in {"go_back", "go_forward"}:
            score -= 0.08
    if kind == "scroll":
        if any(k in goal for k in ["find", "locate", "below", "next", "more"]):
            score += 0.10
        else:
            score -= 0.05
    if kind == "tab":
        score += 0.05
    if kind == "control":
        if parsed.get("name") == "noop":
            score -= 0.12
        elif parsed.get("name") in {"send_msg_to_user", "report_infeasible"}:
            score -= 0.18
    if kind == "skill":
        # Keep neutral-ish. Final decision between skill and non-skill
        # is delegated to LLM pairwise compare with the skill code attached.
        score += 0.03

    if any(k in txt for k in ["open", "view", "show", "tab", "filter", "sort", "search"]):
        score += 0.12
    if obs_meta.get("role") in {"tab", "grid", "table", "row", "link"}:
        score += 0.05
    if any(k in txt for k in ["maybe", "might", "if unavailable", "fallback"]):
        score -= 0.08
    return _clip01(score)


def _estimate_answer_exposure(parsed: dict, reason: str, current_obs: dict, obs_meta: dict, live: dict) -> float:
    txt = f"{reason} {parsed.get('name', '')}".lower()
    goal = _goal_text(current_obs).lower()
    label_text = f"{obs_meta.get('text') or ''} {live.get('text') or ''}".lower()
    region = live.get("region") or obs_meta.get("region") or "unknown"
    kind = parsed.get("kind")

    score = 0.40
    if any(k in txt or k in label_text for k in ["report", "results", "grid", "table", "customers", "orders", "details"]):
        score += 0.18
    if region in {"main", "nav"}:
        score += 0.07
    if obs_meta.get("role") in {"grid", "table", "tab", "link"}:
        score += 0.08
    if kind == "navigation" and any(k in goal for k in ["open", "show", "view", "report"]):
        score += 0.08
    if kind == "skill":
        score += 0.03
    return _clip01(score)


def _estimate_risk(parsed: dict, action: str, reason: str, live: dict, obs_meta: dict, current_obs: dict) -> float:
    txt = f"{action} {reason}".lower()
    score = 0.16
    kind = parsed.get("kind")
    name = parsed.get("name")

    if _looks_destructive(txt):
        score += 0.35
    if kind == "navigation":
        url_relevance = live.get("url_relevance")
        if isinstance(url_relevance, (int, float)):
            score += max(0.0, 0.20 - 0.15 * float(url_relevance))
    if kind == "element" and live.get("occluded") is True:
        score += 0.12
    enabled = _coalesce_bool(live.get("enabled"), obs_meta.get("obs_enabled"))
    if kind == "element" and enabled is False:
        score += 0.12
    if current_obs.get("last_action_error") and current_obs.get("last_action") == action:
        score += 0.20
    if any(k in txt for k in ["logout", "sign out"]):
        score += 0.18
    if kind == "scroll":
        score = max(0.08, score - 0.05)
    if kind == "tab":
        if name == "tab_close":
            score += 0.25
        elif name == "new_tab":
            score += 0.05
        elif name == "tab_focus":
            score += 0.03
    if kind == "control":
        if name == "noop":
            score = 0.04
        elif name == "send_msg_to_user":
            score += 0.08
        elif name == "report_infeasible":
            score += 0.22
    if kind == "skill":
        # We do not inspect / expand the skill heuristically.
        # Keep moderate uncertainty and let the LLM compare pairwise
        # with the concrete skill source.
        score += 0.08
    return _clip01(score)


def _estimate_readiness(parsed: dict, live: dict, obs_meta: dict, prereq: dict) -> Tuple[float, str]:
    status = prereq.get("status") or "unknown"
    mapping = {
        "ready_now": 0.90,
        "needs_scroll": 0.58,
        "needs_expand": 0.45,
        "needs_focus": 0.48,
        "needs_navigation": 0.42,
        "blocked": 0.10,
        "unknown": 0.50,
    }
    return mapping.get(status, 0.50), status


# =========================
# Fallback
# =========================

def _fallback_from_raw(candidates: List[dict], current_obs: dict) -> Optional[str]:
    if not candidates:
        return None

    goal = _goal_text(current_obs).lower()
    best = None
    best_score = -1e9
    for cand in candidates:
        action = str(cand.get("action") or "")
        reason = str(cand.get("reason") or "")
        txt = f"{action} {reason}".lower()
        score = 0.0
        score += 0.5 if not _looks_destructive(txt) else -1.0
        score += 0.2 if reason.strip() else 0.0
        score += 0.3 * _goal_overlap(goal, txt)
        parsed = _parse_action(action, registry=None)
        if parsed.get("kind") in {"navigation", "element", "scroll", "keyboard", "tab", "control", "skill"}:
            score += 0.1
        if best is None or score > best_score:
            best = action
            best_score = score
    return best or candidates[0].get("action")


# =========================
# Goal / obs text
# =========================

def _goal_text(current_obs: dict) -> str:
    if not isinstance(current_obs, dict):
        return ""

    goal_object = current_obs.get("goal_object")
    if isinstance(goal_object, list):
        parts = []
        for msg in goal_object:
            if isinstance(msg, dict):
                content = msg.get("text")
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                            parts.append(str(item["text"]))
            elif isinstance(msg, str):
                parts.append(msg)
        joined = "\n".join(p.strip() for p in parts if str(p).strip())
        if joined.strip():
            return joined.strip()

    return ""


def _to_jsonable(obj):
    try:
        import numpy as np
    except Exception:
        np = None

    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(x) for x in obj]

    if np is not None:
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()

    if hasattr(obj, "__dict__"):
        try:
            return _to_jsonable(vars(obj))
        except Exception:
            pass

    return repr(obj)

def _obs_text(obs: dict, agent) -> str:
    data = {
        "last_action": _to_jsonable(obs.get("last_action", "")),
        "action_history": _to_jsonable(agent.action_history),
        "last_action_error": _to_jsonable(obs.get("last_action_error", "")),
        "open_pages_urls": _to_jsonable(obs.get("open_pages_urls", [])),
        "open_pages_titles": _to_jsonable(obs.get("open_pages_titles", [])),
        "active_page_index": _to_jsonable(obs.get("active_page_index", None)),
        "axtree_txt": _to_jsonable(obs.get("axtree_txt", "") or ""),
        "goal_object": _to_jsonable(obs.get("goal_object", [])),
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# =========================
# LLM selection
# =========================

def _find_llm(agent):
    selection_model = getattr(agent, "selection_model", None)
    if selection_model is not None:
        return {"type": "selection_model", "llm": selection_model}

    client = getattr(agent, "client", None)
    model_name = getattr(agent, "model_name", None)
    if client is not None and model_name:
        return {
            "type": "openai_client",
            "client": client,
            "model_name": model_name,
        }

    for attr in ["llm", "chat_model", "model"]:
        obj = getattr(agent, attr, None)
        if obj is not None:
            return {"type": "generic_llm", "llm": obj}
    return None


def _llm_compare_pair(agent, llm_handle, registry: ActionRegistry, current_obs: dict, a: dict, b: dict) -> Tuple[str, str, str]:
    prompt, screenshot_url = _build_pairwise_prompt(agent, registry, current_obs, a, b)
    with open('./prompt.txt', 'w', encoding='utf-8') as f:
        f.write(prompt)
    try:
        if not llm_handle:
            return _heuristic_tiebreak(a, b, "missing_llm_handle", "llm_unavailable_fallback")

        if llm_handle.get("type") == "openai_client":
            client = llm_handle["client"]
            model_name = llm_handle["model_name"]
            user_content = [{"type": "text", "text": prompt}]
            if screenshot_url:
                print("Using Screenshot!!!")
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": screenshot_url,
                            "detail": "auto",
                        },
                    }
                )
            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a careful web-agent action ranker. "
                            "Return strict JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": user_content,
                    },
                ],
                temperature=0.0,
            )
            text = _extract_openai_chat_text(resp)
        else:
            llm = llm_handle.get("llm")
            if callable(llm):
                resp = llm(prompt)
            elif hasattr(llm, "invoke"):
                resp = llm.invoke(prompt)
            elif hasattr(llm, "complete"):
                resp = llm.complete(prompt)
            elif hasattr(llm, "generate"):
                resp = llm.generate(prompt)
            elif hasattr(llm, "chat"):
                resp = llm.chat(prompt)
            else:
                return _heuristic_tiebreak(a, b, "unsupported_llm_interface", "llm_parse_fallback")
            text = _coerce_model_text(resp)

        parsed = _extract_json(text)
        winner = parsed.get("winner", "tie")
        why = parsed.get("why", text[:300])
        if winner in {"a", "b"}:
            print("Using LLM judge!!!")
            return winner, why, "llm_success"
        if winner == "tie":
            print('Using heuristic score!!!')
            return _heuristic_tiebreak(a, b, f"llm_tie:{why}", "llm_tie")
        return _heuristic_tiebreak(a, b, f"invalid_winner:{winner}", "llm_parse_fallback")
    except Exception as e:
        return _heuristic_tiebreak(a, b, f"llm_compare_error:{type(e).__name__}:{e}", "llm_exception_fallback")


def _heuristic_tiebreak(a: dict, b: dict, why: str, mode: str) -> Tuple[str, str, str]:
    chosen = "a" if a["heuristic_score"] >= b["heuristic_score"] else "b"
    return chosen, why, mode


def _build_pairwise_prompt(agent, registry: ActionRegistry, current_obs: dict, a: dict, b: dict):
    goal = _goal_text(current_obs)
    obs_text = _obs_text(current_obs, agent)

    def fmt(c: dict) -> dict:
        feats = c["features"]
        return {
            "idx": c["idx"],
            "action": c["action"],
            "kind": c["parsed"].get("kind"),
            "target": c["parsed"].get("target"),
            "prereq_status": c["prereq"].get("status"),
            "prereq_why": c["prereq"].get("why"),
            "exists": c["live"].get("exists"),
            "visible": c["live"].get("visible"),
            "enabled": c["live"].get("enabled"),
            "editable": c["live"].get("editable"),
            "occluded": c["live"].get("occluded"),
        }

    skill_snippets = _collect_pair_skill_code(registry, a, b)
    skill_code_section = ""
    if skill_snippets:
        rendered = []
        for name, source in skill_snippets.items():
            rendered.append(f"[SKILL {name}]\n{source.strip()}")
        skill_code_section = "\n\nRelevant skill definitions for this pair only:\n\n" + "\n\n".join(rendered)

    prompt = f"""# Role
You are a strict pairwise ranker for web-agent actions.

Your job is to compare exactly two candidate actions and choose the one that is more likely to advance the task immediately from the current state.

# Core Objective
Choose the action that is the best next single step right now.
Prefer actions that are immediately executable, reduce blockers, and move the agent closer to completing or confidently resolving the task.

# Decision Rules
Prefer the candidate that is:
1. More directly useful for accomplishing the task goal from the current state.
2. More executable right now on the current page/state.
3. More likely to unblock progress, reveal needed information, verify needed information, or finalize the task.
4. Lower risk, less speculative, and less likely to waste a step.

# Popup / Overlay Rule
If the page appears to be blocked or hindered by a popup, modal, cookie banner, login prompt, newsletter prompt, consent banner, or overlay, prefer the action that dismisses or closes the blocker first, as long as the blocker is not necessary for completing the task.
Examples of dismiss actions include clicking “X”, “✖”, “Close”, “Dismiss”, “Not now”, “Cancel”, or a consent/accept button that removes the obstruction.

# Executability Rules
Treat a candidate as weaker if:
- its target does not exist,
- its target is not visible,
- its target is disabled,
- its target is occluded by another element,
- its prerequisites are unsatisfied,
- it depends on assumptions not supported by the current context.

Interpret fields conservatively:
- `exists=false` means the target is likely unavailable now.
- `visible=false` means the target is likely not actionable now.
- `enabled=false` means interaction is likely to fail.
- `occluded=true` means the target may be blocked by another element and is less preferable unless the action itself is intended to remove that blocker.
- `editable=true` matters mainly for text-entry actions.
- `prereq_status` and `prereq_why` indicate whether the action is actually ready to be executed now.

# Terminal Action Rules
Treat `send_msg_to_user` and `report_infeasible` as terminal user-facing actions.
Prefer one of them only if it already resolves the task appropriately using concrete information available in the current context.
Do NOT prefer a terminal action if more UI interaction is still clearly needed to obtain, verify, or complete the answer.
Do NOT end early with `report_infeasible` unless the current context already provides strong evidence that the task cannot be completed.

# Skill Rules
- Judge only from the current context provided below.
- Do NOT prefer an action merely because its argument looks like a bid, score, or confidence value.
- Do NOT invent hidden capabilities for skills.
- If a candidate is a custom skill, use only the provided skill code for that skill in this pair.
- Do NOT assume extra steps or side effects for a skill beyond the provided code.

# Tie Rule
Return `"tie"` only when neither candidate clearly dominates after applying the rules above.
If one action is even moderately better in immediate usefulness or executability, choose it instead of `"tie"`.

# Allowed Evidence
You may use only:
- task goal
- current page context
- current page screenshot
- candidate A
- candidate B
- relevant skill definitions shown below

# Task Goal
{goal}

# Current Page Context

A current page screenshot may be attached after this text. Use it as additional grounding for visibility, popup/overlay detection, occlusion, and whether an action is executable right now.

```json
{obs_text}
```

# Candidate A

```json
{json.dumps(fmt(a), ensure_ascii=False, indent=2)}
```

# Candidate B

```json
{json.dumps(fmt(b), ensure_ascii=False, indent=2)}
```

# Relevant Skill Definitions (for this pair only)

{skill_code_section}

# Output Contract

Return strict JSON only.
Do not output markdown.
Do not output extra text.

Schema:
{{"winner":"a"|"b"|"tie", "why":"<=80 words"}}
"""
    screenshot_url = None
    screenshot = current_obs.get("screenshot")
    if screenshot is not None:
        try:
            screenshot_url = _image_to_jpg_base64_url(screenshot)
        except Exception:
            screenshot_url = None

    return prompt, screenshot_url


def _collect_pair_skill_code(registry: ActionRegistry, a: dict, b: dict) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for c in (a, b):
        parsed = c.get("parsed") or {}
        if parsed.get("kind") == "skill":
            name = parsed.get("name")
            source = parsed.get("skill_source")
            if not source and registry is not None:
                spec = registry.skills.get(name)
                source = spec.source if spec else None
            if name and source:
                out[name] = source
    return out


def _extract_openai_chat_text(resp) -> str:
    try:
        choices = getattr(resp, "choices", None) or []
        if not choices:
            return ""
        msg = getattr(choices[0], "message", None)
        if msg is None:
            return ""
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text" and item.get("text"):
                        parts.append(item["text"])
                else:
                    text_val = getattr(item, "text", None)
                    if text_val:
                        parts.append(text_val)
            return "\n".join(parts)
        return str(content or "")
    except Exception:
        return _coerce_model_text(resp)


def _coerce_model_text(resp: Any) -> str:
    if isinstance(resp, str):
        return resp
    for attr in ["content", "text", "output_text"]:
        val = getattr(resp, attr, None)
        if isinstance(val, str):
            return val
    if isinstance(resp, dict):
        for key in ["content", "text", "output_text"]:
            if isinstance(resp.get(key), str):
                return resp[key]
    return str(resp)


def _extract_json(text: str) -> dict:
    if not text:
        return {}
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
    return {}


# =========================
# Parsing helpers
# =========================

def _strip_code_fence(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```") and text.endswith("```"):
        text = re.sub(r"^```(?:python)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return text


def _strip_wrapping_semicolon(text: str) -> str:
    return text[:-1].strip() if text.endswith(";") else text.strip()


def _action_kind(name: str, registry: Optional[ActionRegistry]) -> str:
    if name in ELEMENT_ACTIONS:
        return "element"
    if name in NAVIGATION_ACTIONS:
        return "navigation"
    if name in KEYBOARD_ACTIONS:
        return "keyboard"
    if name in SCROLL_ACTIONS:
        return "scroll"
    if name in TAB_ACTIONS:
        return "tab"
    if name in CONTROL_ACTIONS:
        return "control"
    if registry is not None and name in registry.skills:
        return "skill"
    if name.isidentifier():
        # Unknown callable; if registry wasn't available yet we still keep a distinct category
        # only when it is explicitly recognized as a custom skill.
        return "unknown"
    return "unknown"


def _literal_eval_or_text(expr: str) -> Any:
    try:
        return ast.literal_eval(expr)
    except Exception:
        return expr


def _strip_quotes(value: Any) -> Any:
    if isinstance(value, str) and len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _coerce_number(value: Any) -> Optional[float]:
    value = _strip_quotes(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except Exception:
            return None
    return None


def _looks_selector(target: str) -> bool:
    if not isinstance(target, str):
        return False
    return any(tok in target for tok in ["#", ".", "[", "]", ">", ":", "//", "text="])


def _selector_dom_id(selector: Optional[str]) -> Optional[str]:
    if not isinstance(selector, str):
        return None
    m = re.search(r"#([a-zA-Z_][a-zA-Z0-9_\-:]*)", selector)
    return m.group(1) if m else None


def _selector_text_hint(selector: Optional[str]) -> Optional[str]:
    if not isinstance(selector, str):
        return None
    m = re.search(r'text\s*=\s*["\']([^"\']+)["\']', selector)
    if m:
        return m.group(1)
    m = re.search(r'has_text\s*=\s*["\']([^"\']+)["\']', selector)
    if m:
        return m.group(1)
    return None


def _normalize_region(v: str) -> str:
    txt = str(v).strip().lower()
    if txt in {"main", "content"}:
        return "main"
    if txt in {"nav", "navigation", "left nav"}:
        return "nav"
    if txt in {"sidebar", "aside"}:
        return "sidebar"
    if txt in {"modal", "dialog", "popup"}:
        return "modal"
    if txt in {"header", "top", "topbar"}:
        return "header"
    if txt in {"footer"}:
        return "footer"
    if txt in {"form"}:
        return "form"
    return txt or "unknown"


def _infer_region(agent, reason: str, current_obs: dict) -> str:
    txt = f"{reason} {_obs_text(current_obs, agent)}".lower()
    if any(k in txt for k in ["sidebar", "left nav", "navigation"]):
        return "nav"
    if any(k in txt for k in ["modal", "dialog", "popup"]):
        return "modal"
    if any(k in txt for k in ["header", "top bar"]):
        return "header"
    if any(k in txt for k in ["footer"]):
        return "footer"
    if any(k in txt for k in ["table", "grid", "report", "content"]):
        return "main"
    return "unknown"


def _goal_overlap(goal: str, txt: str) -> float:
    if not goal or not txt:
        return 0.0
    goal_terms = [w for w in re.findall(r"[a-zA-Z0-9_\-]+", goal) if len(w) >= 4]
    if not goal_terms:
        return 0.0
    overlap = sum(1 for t in set(goal_terms[:20]) if t in txt)
    return min(1.0, overlap / max(1.0, min(len(set(goal_terms[:20])), 6)))


def _looks_destructive(txt: str) -> bool:
    return any(k in txt for k in POTENTIALLY_DESTRUCTIVE)


def _goal_allows_destructive(current_obs: dict) -> bool:
    goal = _goal_text(current_obs).lower()
    return any(k in goal for k in ["submit", "save", "confirm", "pay", "purchase", "checkout", "delete", "remove"])


def _coalesce_bool(*vals):
    for v in vals:
        if isinstance(v, bool):
            return v
    return None


def _host_of(url: str) -> str:
    m = re.match(r"^[a-zA-Z]+://([^/]+)", url or "")
    return m.group(1).lower() if m else ""


def _url_path_terms(url: str) -> List[str]:
    if not isinstance(url, str) or not url.strip():
        return []
    try:
        parsed = urlparse(url)
        txt = f"{parsed.path} {parsed.query} {parsed.fragment}"
    except Exception:
        txt = url
    return [w.lower() for w in re.findall(r"[a-zA-Z0-9_\-]+", txt) if len(w) >= 3]


def _url_keyword_overlap(goal: str, url: str) -> float:
    goal_terms = [w.lower() for w in re.findall(r"[a-zA-Z0-9_\-]+", goal or "") if len(w) >= 4]
    url_terms = set(_url_path_terms(url))
    if not goal_terms or not url_terms:
        return 0.0
    hits = sum(1 for term in set(goal_terms[:20]) if term in url_terms)
    return min(1.0, hits / max(1.0, min(len(set(goal_terms[:20])), 6)))


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))