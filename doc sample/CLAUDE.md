# CLAUDE.md — R-Port

See **ARCHITECTURE.md** for layered design, **CONVENTIONS.md** for coding standards,
**AUDIT.md** for full version history (v3 through v6).

---

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Comments

**Why, not what. If the code is clear, skip it.**

- English only.
- Inline comments for non-obvious logic only — not for readable operations.
- No docstrings on self-evident functions.
- One short sentence. No filler, no trailing period on inline comments.
- If a workaround or constraint isn't obvious from the code, explain the reason.

```python
# BRA requires PDF decryption before CSV extraction  ✓
# iterate over countries and process each one         ✗
```

---

## Overview

R-Port is an internal tool for processing and aggregating HR data
(employees, payroll, cost centers) for an international group.
It exposes a Python CLI and a FastAPI API with an HTML/JS web interface.

---

## Project structure

```
Allshare_admin/          ← project root, all commands run from here
├── scripts/             ← admin tools (outside src/)
│   └── create_user.py
├── data/                ← CLI use only, never committed
│   └── admin/
│       ├── excel/       ← Excel input for the admin processor (.xlsx files)
│       ├── processed/   ← encrypted .bin output from the admin processor
│       └── ww/          ← aggregated CSV output from AdminAggregator
├── src/
│   ├── main.py          ← CLI entry point
│   ├── admin/           ← employee data module (Excel → .bin processor + aggregator)
│   ├── payroll/         ← payroll data module (CSV + per-country processors)
│   ├── cost_center/     ← cost center module (CSV + DEU processor)
│   ├── services/        ← layer between CLI/API and aggregators
│   ├── utils/           ← shared helpers
│   ├── api/             ← FastAPI (JWT auth, routes, Pydantic schemas)
│   └── static/          ← HTML/JS UI (login.html, index.html, favicon.png)
├── ARCHITECTURE.md
├── CONVENTIONS.md
├── .env                 ← secrets (never committed)
├── config.json          ← nomenclatures and paths (never committed)
└── rport.db          ← SQLite DB: users + processing history (never committed)
```

---

## Essential commands

All commands run from the **project root**.

```powershell
# Start the web server (PowerShell)
$env:PYTHONPATH="src"; uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

# Admin: process Excel → .bin (place .xlsx in data/admin/excel/)
# key path from PUBLIC_KEY_INTEGRITY_CHECKER_PATH in .env, or override with --public-key
python src/main.py process --module admin --period 202504
python src/main.py process --module admin --period 202504 --public-key /path/to/public.pem

# Admin: aggregate .bin → consolidated CSV
# key path from PRIVATE_KEY_INTEGRITY_CHECKER_PATH in .env, or override with --private-key
python src/main.py aggregate --module admin --period 202504
python src/main.py aggregate --module admin --period 202504 --private-key /path/to/private.pem

# Payroll / cost center
python src/main.py aggregate --module payroll --period 202504
python src/main.py aggregate --module cost_center --period 202504
python src/main.py process --module payroll --country BRA --period 202504
python src/main.py process --module cost_center --country DEU --period 202504

# SFTP
python src/main.py sftp --function list --input /remote/path

# Web user management
python scripts/create_user.py add <username>
python scripts/create_user.py list
python scripts/create_user.py remove <username>

# Tests
pytest tests/ -v
```

---

## Must-know rules

- **Aggregators** never call `print()`, `input()`, `getpass()`, or `os.makedirs()`.
  All output goes through `self.logger`.
- **Services** are the only layer allowed to touch the filesystem, env vars, and `getpass()`.
  Routes call services only — never aggregators directly.
- **No `getpass()` fallback in services.** A `getpass()` call inside a service method
  hangs silently in API mode.
- **Never expose `str(e)` in HTTP responses.** Log server-side; return a generic message.
  See CONVENTIONS.md §Error handling.
- **Job ownership.** Every `Job` must store its creator's `username`. `GET /api/jobs/{id}`,
  download, and log endpoints must reject other users with HTTP 403.
- `payroll/file_format.py` and `cost_center/file_format.py` use intentionally different
  separator detection algorithms. Do not merge them into `utils/`.

---

## Sensitive files — never modify or commit

| File | Sensitive content |
|---|---|
| `.env` | `SECRET_KEY`, `BRA_PAYROLL_PASSWORD`, `PRIVATE_KEY_INTEGRITY_CHECKER_PATH`, `PUBLIC_KEY_INTEGRITY_CHECKER_PATH` |
| `config.json` | Company nomenclatures, company codes, internal network paths |
| `rport.db` | bcrypt password hashes + full processing history |
| `data/` | CSV files with real HR data (identity, salaries, dates of birth) |

---

## Known points of attention

**Admin passphrase:** never log it, even in DEBUG. It travels
`API body → admin_service → AdminConfig → BinFileDecryptor`.

**Admin RSA keys:** never stored on the server.
- Web UI: user uploads the PEM file per request; it is read into memory and discarded.
- CLI: key path resolved from `--private-key` / `--public-key` arg, falling back to
  `PRIVATE_KEY_INTEGRITY_CHECKER_PATH` / `PUBLIC_KEY_INTEGRITY_CHECKER_PATH` in `.env`.
  Either way the file is read into bytes in `main.py` and passed to the service as `bytes`.

**Admin processor public key:** used only by `AdminConfig.build()` (processor path) and
`BinEncryptor`. Never passed to the aggregator path. If absent,
`AdminProcessor._run_pipeline()` raises `EnvironmentError` before encrypting.

**`admin/excel_reader.py` sheet detection:** a sheet qualifies when col A header contains
`"* mandatory field"` (case-insensitive). Fuzzy matching uses Levenshtein ratio ≥ 0.85
against `HEADERS_MAPPING` canonical names.

**`admin/validators.py`:** 8+ `pass` placeholder validations at lines 290-297, 370-372,
413-426 — do not mistake them for implemented logic.

**`EXCLUDED_COUNTRY_FOLDERS`** in `payroll/constants.py`: countries excluded from the WW
aggregator scan. When adding a new country processor, update **all four** of:
1. `EXCLUDED_COUNTRY_FOLDERS` in `payroll/constants.py`
2. `COUNTRY_PROCESSOR_PATHS` in `payroll/constants.py`
3. `_VALID_PROCESS_COUNTRIES` in `api/schemas.py`
4. `PROCESS_COUNTRIES` in `src/static/index.js`

Omitting the schema update silently blocks all API requests for that country with HTTP 422.
Omitting the index.js update prevents admins from assigning that country to users via the UI.

**`GBR _fiscal_to_calendar`** in `payroll/processors/gbr.py`: converts the Moorepay fiscal
period (`CURRENT PAY`, `YYYYMM`) to a calendar period by adding 3 months, wrapping the year
past December. No hardcoded table — nothing to update each year.

**`src/api/routes/jobs.py:61`** — `output_filename` must be sanitized (strip `\r`, `\n`, `"`)
before insertion in `Content-Disposition`. Unsanitized filename → HTTP header injection.

**`src/api/auth.py`:** every failed login attempt emits `logger.warning(...)` with the username.

**`utils/db.py`:** SQLite persistence layer (no ORM). Migrates legacy `users.json` /
`history.json` automatically on first startup. Override DB path with `DB_PATH` env var in tests.