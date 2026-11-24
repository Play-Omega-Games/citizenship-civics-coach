# Citizenship Civics Coach

Study data and engine for the 🗽 Citizenship Civics Coach Grok Bot template by Omega Games (Omega Home Library, Scholar Shelf): daily spaced-repetition drills on the official USCIS naturalization civics questions, a weekly mock test in the official format, and a readiness Page.

Study aid only. Not legal advice. Not affiliated with or endorsed by USCIS or any government agency.

## What is here

- `data/questions.json`: all 128 questions of the 2025 civics test (M-1778, 09/25) and all 100 of the 2008 test (rev. 08/21), copied verbatim from the USCIS PDFs with every listed answer and USCIS's bracketed notes. Each question carries `senior_65_20` (USCIS asterisk), `changes_over_time` (listed on USCIS's Check for Test Updates page) and `state_specific` flags.
- `data/capitals.json`: state and territory capitals (stable facts, fixed table).
- `data/standards.json`: C3 Framework (NCSS) tags with the exact code text, band, the activity that practices it, source and date verified. Each question in `questions.json` lists its tags. The bot supports practice toward these standards; it never claims to meet or cover them. Symbols, holidays, geography and most history recall questions carry no tag on purpose.
- `scripts/civics.py`: which test applies by N-400 filing date, Leitner boxes, daily sets, mock tests with the official stop rules, Library Card numbers (days, minutes, standards practiced), a printable report, memory snapshot and restore, and live lookups of answers that change.
- `scripts/build_data.py`: rebuilds `questions.json` from the USCIS PDFs (`pdftotext -layout`).
- `scripts/check_links.py`: checks every source link live.
- `tests/test_civics.py`: offline checks (set `CIVICS_SRC` to also check the text is verbatim).

## Answers that change

Officeholder answers (President, Vice President, Speaker, Chief Justice, and on the 2008 test the President's party and the number of justices) are never stored here. The data says what USCIS prints: "Visit uscis.gov/citizenship/testupdates". `civics.py current federal` reads that page live. Senators come live from senate.gov, governors from usa.gov, and representatives from the Clerk of the House member list. Applicants must answer with the official serving at the time of their interview.

## Test rules (from USCIS)

| Test | Who takes it | Asked | Pass | Officer stops at |
|---|---|---|---|---|
| 2025 | N-400 filed on or after Oct 20, 2025 | up to 20 of 128 | 12 right | 12 right or 9 wrong |
| 2008 | N-400 filed before Oct 20, 2025 | up to 10 of 100 | 6 right | 6 right or 5 wrong |
| 65/20 (either version) | 65 or older with 20+ years as a permanent resident, at filing | 10 of the 20 starred | 6 right | 6 right or 5 wrong (implied) |

Sources: https://www.uscis.gov/citizenship/testupdates , https://www.uscis.gov/citizenship/find-study-materials-and-resources/study-for-the-test , https://www.uscis.gov/policy-manual/volume-12-part-e-chapter-2

## Quick start

```
python3 scripts/civics.py validate
python3 scripts/civics.py version --filed 2025-11-03
python3 scripts/civics.py init --version 2025 --daily 10 --start 2026-11-25 --out state/progress.json
python3 scripts/civics.py today --progress state/progress.json --date 2026-11-25
python3 scripts/civics.py current federal --version 2025
python3 tests/test_civics.py
python3 scripts/check_links.py
```

A bot loads every file listed in `MANIFEST.txt` and checks each SHA-256.

## Roadmap

- v1.1: classroom mode (one teacher, many students). Planned, not built.
- Later: English reading and writing test practice (USCIS vocabulary lists).

## License

The question text is a work of the U.S. government and is in the public domain (17 U.S.C. 105). Omega Games' code is MIT. See `LICENSE`.

Questions or ideas? Contact Omega Games at john@playomega.games.
