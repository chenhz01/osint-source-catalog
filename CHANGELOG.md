# Changelog

## [0.1.1] - 2026-09-20

### Changed (round-2 iteration after 16-item self-audit)

- **Correctness:** fixed `validate_source` accepting an empty-string `id`; slug rule now rejects empty/non-string ids (caught by new extreme-edge test C3).
- **Completeness (+~25%):** README gained the compliance-grade table with per-level aggregation/redistribution semantics, two shipped preaudit example plans (`examples/plan_clean.json`, `plan_risky.json`), and an explicit "intended use" clause in Ethics.
- **Safety:** fail-closed stance documented in FAQ (unknown sources REJECT, not warn).

## [0.1.0] - 2026-09-20

### Added

- `catalog.py`: source schema validator, three-level compliance model (A/B/C), aggregation plan pre-audit (PASS/REVIEW/REJECT, fail-closed), category/level/auth filters.
- `cli.py`: `list` / `show` / `preaudit` / `validate` subcommands.
- `self_test.py`: 23 checks across functional / error-path / extreme-edge families.
- `data/sources.json`: 12 public data sources with license, rate limit, auth, compliance grade, ToS links, as of 2026-09-20.
- Ethics & Legal Boundaries section (privacy-paradox first-class); MIT LICENSE (zhengming contributors).
