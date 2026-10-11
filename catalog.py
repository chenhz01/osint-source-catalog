"""osint-source-catalog: schema, compliance grading and aggregation pre-audit.

Each catalog entry documents one *publicly accessible, legally servable*
data source: license, rate limits, field overview, and a compliance grade.
`preaudit` checks a proposed aggregation plan against the catalog so that
projects discover licensing/redistribution conflicts before writing code.
"""

from __future__ import annotations

import json

SOURCE_FIELDS = ("id", "name", "category", "base_url", "auth", "license",
                 "rate_limit", "compliance_level", "tos_url", "notes")
CATEGORIES = ("geospatial", "weather", "seismic", "finance", "news", "web", "gov", "science")
COMPLIANCE_LEVELS = ("A", "B", "C")
# C = public but ToS treats bulk/aggregated reuse as gray zone: allowed to query,
# NOT allowed to redistribute aggregated output without legal review.

AUTH_MODES = ("none", "api_key", "registration")

_LEVEL_RULES = {
    "A": {"max_auth": "none", "redistribute": True, "label": "open license, documented ToS, redistribution OK"},
    "B": {"max_auth": "registration", "redistribute": True, "label": "open with attribution / rate etiquette"},
    "C": {"max_auth": "registration", "redistribute": False, "label": "public but aggregation/redistribution is ToS-gray"},
}


def validate_source(entry: dict) -> list:
    """Validate one catalog entry. Returns list of error strings."""
    errs = []
    for f in SOURCE_FIELDS:
        if f not in entry:
            errs.append(f"missing field: {f}")
    sid = entry.get("id")
    if not isinstance(sid, str) or not sid.replace("-", "").replace("_", "").isalnum():
        errs.append(f"id must be a non-empty slug: {sid!r}")
    if entry.get("category") not in CATEGORIES:
        errs.append(f"unknown category: {entry.get('category')} (allowed: {CATEGORIES})")
    if entry.get("compliance_level") not in COMPLIANCE_LEVELS:
        errs.append(f"compliance_level must be A/B/C, got: {entry.get('compliance_level')}")
    if entry.get("auth") not in AUTH_MODES:
        errs.append(f"auth must be one of {AUTH_MODES}")
    rl = entry.get("rate_limit")
    if not isinstance(rl, dict) or not {"requests", "per"} <= set(rl):
        errs.append("rate_limit must be {'requests': int, 'per': 'second|minute|hour|day'}")
    elif not isinstance(rl["requests"], int) or rl["requests"] <= 0:
        errs.append("rate_limit.requests must be a positive int")
    return errs


def load_catalog(path: str) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list) or not data:
        raise ValueError("catalog must be a non-empty JSON list")
    problems = []
    seen = set()
    for i, entry in enumerate(data):
        problems += [f"entry[{i}] ({entry.get('id', '?')}): {e}" for e in validate_source(entry)]
        sid = entry.get("id")
        if sid in seen:
            problems.append(f"entry[{i}]: duplicate id {sid}")
        seen.add(sid)
    if problems:
        raise ValueError("invalid catalog:\n" + "\n".join(problems))
    return data


def preaudit(catalog: list, plan: dict) -> dict:
    """Pre-audit an aggregation plan.

    plan = {"sources": ["id1", "id2"], "use": "internal|aggregate-public|redistribute"}
    Returns per-source verdicts and an overall verdict.
    """
    use = plan.get("use")
    if use not in ("internal", "aggregate-public", "redistribute"):
        return {"verdict": "REJECT", "reason": f"unknown use: {use!r} "
                "(allowed: internal | aggregate-public | redistribute)"}
    by_id = {e["id"]: e for e in catalog}
    verdicts, blockers = [], []
    for sid in plan.get("sources", []):
        entry = by_id.get(sid)
        if entry is None:
            verdicts.append({"id": sid, "verdict": "UNKNOWN", "reason": "not in catalog"})
            blockers.append(sid)
            continue
        level = entry["compliance_level"]
        rule = _LEVEL_RULES[level]
        if use == "redistribute" and not rule["redistribute"]:
            verdicts.append({"id": sid, "verdict": "BLOCK", "level": level,
                             "reason": f"level {level}: {rule['label']}"})
            blockers.append(sid)
        elif use == "aggregate-public" and level == "C":
            verdicts.append({"id": sid, "verdict": "REVIEW", "level": level,
                             "reason": "level C source in public aggregation: needs ToS review"})
            blockers.append(sid)
        else:
            verdicts.append({"id": sid, "verdict": "OK", "level": level, "reason": rule["label"]})
    overall = "REJECT" if any(v["verdict"] in ("BLOCK", "UNKNOWN") for v in verdicts) \
        else "REVIEW" if blockers else "PASS"
    return {"verdict": overall, "use": use, "sources": verdicts,
            "ethics_note": "passing this audit does not exempt you from honoring "
                           "rate limits, attribution, and each source's ToS"}


def filter_sources(catalog: list, category=None, level=None, auth=None) -> list:
    out = catalog
    if category:
        out = [e for e in out if e["category"] == category]
    if level:
        out = [e for e in out if e["compliance_level"] == level]
    if auth:
        out = [e for e in out if e["auth"] == auth]
    return out
