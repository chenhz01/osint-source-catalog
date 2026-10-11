#!/usr/bin/env python3
"""osint-source-catalog CLI.

Subcommands:
  list [--category C] [--level A|B|C] [--auth none|api_key|registration]
  show <source-id>
  preaudit <plan.json>        check an aggregation plan against the catalog
  validate                    schema-check the shipped catalog
Plan JSON: {"sources": ["open-meteo", "usgs-earthquakes"], "use": "aggregate-public"}
"""

import argparse
import json
import sys

import catalog

HERE = __import__("os").path.dirname(__file__)
DEFAULT_CATALOG = catalog.__file__.replace("catalog.py", "data/sources.json")


def _load(path):
    try:
        return catalog.load_catalog(path)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)


def cmd_list(args) -> int:
    rows = catalog.filter_sources(_load(args.catalog), args.category, args.level, args.auth)
    if not rows:
        print("(no sources match filters)")
        return 0
    for e in rows:
        rl = e["rate_limit"]
        print(f"{e['id']:18s} {e['category']:10s} L{e['compliance_level']} "
              f"auth={e['auth']:12s} {rl['requests']}/{rl['per']}  {e['name']}")
    return 0


def cmd_show(args) -> int:
    for e in _load(args.catalog):
        if e["id"] == args.source_id:
            print(json.dumps(e, indent=2))
            return 0
    print(f"error: source id not found: {args.source_id}", file=sys.stderr)
    return 2


def cmd_preaudit(args) -> int:
    try:
        with open(args.plan, "r", encoding="utf-8") as fh:
            plan = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read plan: {exc}", file=sys.stderr)
        return 2
    result = catalog.preaudit(_load(args.catalog), plan)
    print(json.dumps(result, indent=2))
    return 0 if result["verdict"] == "PASS" else 1


def cmd_validate(args) -> int:
    data = _load(args.catalog)
    print(f"OK: {len(data)} sources, schema valid, ids unique")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="osint-catalog", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_catalog_arg(sp):
        sp.add_argument("--catalog", default=DEFAULT_CATALOG)

    l = sub.add_parser("list", help="list/filter sources")
    add_catalog_arg(l)
    l.add_argument("--category", choices=catalog.CATEGORIES)
    l.add_argument("--level", choices=catalog.COMPLIANCE_LEVELS)
    l.add_argument("--auth", choices=catalog.AUTH_MODES)
    l.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="show one source")
    add_catalog_arg(s)
    s.add_argument("source_id")
    s.set_defaults(func=cmd_show)

    pa = sub.add_parser("preaudit", help="pre-audit an aggregation plan")
    add_catalog_arg(pa)
    pa.add_argument("plan")
    pa.set_defaults(func=cmd_preaudit)

    v = sub.add_parser("validate", help="schema-check a catalog")
    add_catalog_arg(v)
    v.set_defaults(func=cmd_validate)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
