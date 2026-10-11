#!/usr/bin/env python3
"""self_test for osint-source-catalog.
Families: A functional / B error paths / C extreme edges.  Run: python self_test.py
"""

import copy
import json
import os
import shutil
import sys
import tempfile

import catalog
import cli

PASS = 0
FAIL = 0
RESULTS = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        RESULTS.append(f"PASS  {name}")
    else:
        FAIL += 1
        RESULTS.append(f"FAIL  {name}  {detail}")


HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(HERE, "data", "sources.json")
PLAN_DIR = os.path.join(HERE, "examples")


def base_source():
    return {"id": "demo-src", "name": "Demo", "category": "weather",
            "base_url": "https://example.invalid", "auth": "none",
            "license": "CC0", "rate_limit": {"requests": 10, "per": "minute"},
            "compliance_level": "A", "tos_url": "https://example.invalid/tos",
            "notes": "demo"}


# --- A. functional ---------------------------------------------------------------
def test_shipped_catalog_valid():
    data = catalog.load_catalog(CATALOG_PATH)
    check("A1 shipped catalog valid & >=12 sources", len(data) >= 12, str(len(data)))


def test_grades_present():
    data = catalog.load_catalog(CATALOG_PATH)
    levels = {e["compliance_level"] for e in data}
    check("A2 catalog covers levels A, B and C", levels == {"A", "B", "C"}, str(levels))


def test_preaudit_pass_internal():
    data = catalog.load_catalog(CATALOG_PATH)
    r = catalog.preaudit(data, {"sources": ["open-meteo", "usgs-earthquakes"], "use": "internal"})
    check("A3 internal use of A-level sources -> PASS", r["verdict"] == "PASS", str(r["verdict"]))


def test_preaudit_review_aggregate():
    data = catalog.load_catalog(CATALOG_PATH)
    r = catalog.preaudit(data, {"sources": ["open-meteo", "adsb-exchange"], "use": "aggregate-public"})
    check("A4 level-C in public aggregation -> REVIEW",
          r["verdict"] == "REVIEW" and r["sources"][1]["verdict"] == "REVIEW", str(r))


def test_preaudit_redistribute_blocks_c():
    data = catalog.load_catalog(CATALOG_PATH)
    r = catalog.preaudit(data, {"sources": ["hn-firebase"], "use": "redistribute"})
    check("A5 redistribute of level-C -> REJECT", r["verdict"] == "REJECT", str(r))


def test_filter():
    data = catalog.load_catalog(CATALOG_PATH)
    rows = catalog.filter_sources(data, category="weather", level="A")
    check("A6 filter weather+levelA finds open-meteo",
          any(e["id"] == "open-meteo" for e in rows) and all(e["category"] == "weather" for e in rows))


def test_cli_list_and_validate():
    check("A7 CLI list works", cli.main(["list"]) == 0)
    check("A8 CLI validate works", cli.main(["validate"]) == 0)


def test_cli_preaudit_plan_file():
    rc = cli.main(["preaudit", os.path.join(PLAN_DIR, "plan_clean.json")])
    check("A9 CLI preaudit clean plan exit 0", rc == 0)
    rc = cli.main(["preaudit", os.path.join(PLAN_DIR, "plan_risky.json")])
    check("A10 CLI preaudit risky plan exit 1", rc == 1)


# --- B. error paths ----------------------------------------------------------------
def test_missing_fields():
    errs = catalog.validate_source({"id": "x"})
    check("B1 missing fields detected", len(errs) >= 8, str(errs))


def test_bad_category_and_level():
    s = base_source(); s["category"] = "crypto"
    s["compliance_level"] = "S"
    errs = catalog.validate_source(s)
    check("B2 bad category+level flagged", len(errs) == 2, str(errs))


def test_bad_rate_limit():
    s = base_source(); s["rate_limit"] = {"requests": -1, "per": "minute"}
    check("B3 negative rate flagged", any("positive int" in e for e in catalog.validate_source(s)))
    s["rate_limit"] = "10/min"
    check("B4 non-dict rate flagged", any("rate_limit must be" in e for e in catalog.validate_source(s)))


def test_duplicate_ids_rejected():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "c.json")
    dup = base_source()
    with open(p, "w", encoding="utf-8") as fh:
        json.dump([dup, copy.deepcopy(dup)], fh)
    try:
        catalog.load_catalog(p)
        check("B5 duplicate ids rejected", False)
    except ValueError as e:
        check("B5 duplicate ids rejected", "duplicate id" in str(e))
    shutil.rmtree(tmp, ignore_errors=True)


def test_unknown_source_in_plan():
    data = catalog.load_catalog(CATALOG_PATH)
    r = catalog.preaudit(data, {"sources": ["no-such-source"], "use": "internal"})
    check("B6 unknown source -> UNKNOWN + overall REJECT",
          r["verdict"] == "REJECT" and r["sources"][0]["verdict"] == "UNKNOWN", str(r))


def test_unknown_use():
    data = catalog.load_catalog(CATALOG_PATH)
    r = catalog.preaudit(data, {"sources": [], "use": "sell-data"})
    check("B7 unknown use -> REJECT", r["verdict"] == "REJECT")


def test_cli_show_missing_id():
    check("B8 CLI show missing id exits 2", cli.main(["show", "ghost"]) == 2)


def test_cli_preaudit_bad_plan_file():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "p.json")
    open(p, "w", encoding="utf-8").write("not json")
    check("B9 CLI preaudit corrupt plan exits 2", cli.main(["preaudit", p]) == 2)
    shutil.rmtree(tmp, ignore_errors=True)


# --- C. extreme edges ---------------------------------------------------------------
def test_empty_plan():
    data = catalog.load_catalog(CATALOG_PATH)
    r = catalog.preaudit(data, {"sources": [], "use": "internal"})
    check("C1 empty plan -> PASS (vacuous)", r["verdict"] == "PASS", str(r))


def test_huge_plan():
    data = catalog.load_catalog(CATALOG_PATH)
    ids = [e["id"] for e in data] * 50
    r = catalog.preaudit(data, {"sources": ids, "use": "internal"})
    check("C2 600-source plan handled", r["verdict"] in ("PASS", "REVIEW"), str(r["verdict"]))


def test_unicode_and_empty_strings():
    s = base_source(); s["id"] = ""
    errs = catalog.validate_source(s)
    check("C3 empty id rejected", len(errs) == 1, str(errs))


def test_oversized_notes():
    s = base_source(); s["notes"] = "x" * 10_000_000
    check("C4 10MB notes field tolerated", catalog.validate_source(s) == [])


def main():
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        fn()
    print("\n".join(RESULTS))
    print(f"\nself_test: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
