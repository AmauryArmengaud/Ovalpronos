# ARCHITECTURE.md — R-Port

---

## Layer diagram

```
Browser (login.html / index.html)
        │  HTTP — Bearer JWT
        ▼
┌─────────────────────────────┐
│  API  (api/routes/)         │  Validates HTTP input, delegates to service, returns JSON
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  Services  (services/)      │  Owns filesystem I/O, env vars, directory creation
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  Aggregators / Processors   │  Pure data transformation — no I/O, no side effects
│  (admin/, payroll/,         │
│   cost_center/)             │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  Utils  (utils/)            │  Shared stateless helpers
└─────────────────────────────┘

CLI entry point (main.py) → Services → Aggregators → Utils
```

---

## Layer boundaries

| Layer | Allowed | Forbidden |
|---|---|---|
| **API routes** | Call services; validate HTTP input; raise HTTPException; use `CurrentUser` dependency | Call aggregators directly; business logic; filesystem access |
| **Services** | Call aggregators; read env vars; `os.makedirs()`; `getpass()`; write files | Data transformation; logging aggregator-level detail |
| **Aggregators** | `self.logger.*`; call utils; build and transform DataFrames; write output CSV | `print()`; `input()`; `getpass()`; `os.makedirs()`; read env vars |
| **Utils** | Stateless helper functions; no project-level imports | Call services or aggregators |
| **main.py** | Parse CLI args; call services; display result | Business logic of any kind |

---

## Aggregator contract (hard rules)

Every aggregator (`admin/aggregator.py`, `payroll/aggregator.py`, `cost_center/aggregator.py`)
must respect these rules without exception:

1. **No `print()`** — use `self.logger.error/warning/info` instead, including inside `except` blocks.
2. **No `input()` or `getpass()`** — passphrases are injected via `Config.from_env()`.
3. **No `os.makedirs()`** — directory creation belongs in the service layer.
4. **No env var reads** — configuration comes from the `Config` dataclass.
5. **No bare `except Exception`** — catch specific expected types first; re-raise unexpected ones.
6. **No string-based exception detection** (`if str(e) == "..."`) — use typed exceptions.

The aggregator's public interface is `.process() → Path` (disk) or
`.process_to_bytes(in_memory_files) → bytes` (in-memory, for API download).
These are intentionally separate methods with distinct return types — do not merge them into a
single `Path | bytes` union. Both are abstract in `BaseAggregator`; each module provides its own
implementation.

---

## Module pattern

Each module (`admin`, `payroll`, `cost_center`) follows the same file structure:

```
{module}/
├── __init__.py        — exposes Aggregator + Config only
├── config.py          — dataclass Config with .from_env(period) classmethod
├── constants.py       — COLUMN_DEFAULTS, COLUMN_MAPPINGS, COUNTRY_PROCESSOR_PATHS, …
├── aggregator.py      — Aggregator class: .process() → Path
├── postprocessing.py  — finalize_consolidation(), convert_types_for_export()
└── validators.py      — normalize_field_types(), validate_fields()
```

`payroll` and `cost_center` also have `file_format.py` (encoding/separator detection).
`payroll` and `cost_center` also have `processors/` (per-country processing).
`admin` also has `processor.py` (Excel → `.bin`) and `excel_reader.py` (sheet parsing).

`admin/parsers.py` is a re-export alias from `utils/parsers.py` — do not modify it directly.

### Admin module specifics

`admin` is the only module with **two distinct Config factory methods**:

| Factory | Used by | Requires |
|---|---|---|
| `AdminConfig.from_env(period, passphrase)` | `AdminAggregator` | `PRIVATE_KEY_INTEGRITY_CHECKER_PATH` |
| `AdminConfig.from_env_processor(period)` | `AdminProcessor` | `PUBLIC_KEY_INTEGRITY_CHECKER_PATH` |

This avoids requiring the private key on machines that only encrypt (upload Excel), and the
public key on machines that only decrypt (aggregate `.bin` files).

---

## Shared utils catalog

Check here before writing a new helper anywhere in the codebase.

**`utils/parsers.py`**
- `parse_integer(v)` — safe int conversion
- `parse_decimal(v)` — safe float conversion with , or . support
- `check_convert_date(v)` — canonical date parser: accepts Excel serial int/float, `datetime`/`Timestamp`, or a date string (`d/m/Y`, `m/d/Y`, `Y/m/d`, `Y-m-d`); returns `datetime | None`
- `check_and_adjust_percentage(v)` — validates 0–100 range
- `check_and_adjust_decimal(v)` — handles , and . decimal formats
- `check_and_adjust_integer(v)` — converts to int
- `is_nan(v)` — NaN-safe check

**`utils/logging_utils.py`**
- `init_logger(name, log_temp_file) → Logger` — creates a named logger writing to a temp file
- `rename_log(logger, log_temp_file, output_path)` — closes handler, renames temp → final log
- `load_json_config(config_file) → dict` — loads `config.json`
- `purge_old_output_files(folder, logger)` — deletes CSV/LOG files older than `DATA_RETENTION_DAYS` (default: 30)

**`utils/file_format.py`**
- `FileFormat` dataclass — `encoding`, `separator`, `decimal_separator`, `thousand_separator`
  (shared between payroll and cost_center)

**`utils/file_finder.py`**
- `find_module_files(folder_path, period, extension, module_keyword, excluded_folders, test_folder) → list[str]`
  — discovers source files matching the period and module keyword under "Allshare WW"

**`utils/base_aggregator.py`**
- `BaseAggregator(ABC)` — abstract base for all three aggregators
- `_load_json_config() → dict` — delegates to `logging_utils.load_json_config`
- `_rename_log(log_temp_file, output_path)` — delegates to `logging_utils.rename_log`
- `_filter_paths_by_countries(paths, included, excluded, pattern) → list[str]`
  — shared country-filter logic using the module's regex pattern
- Abstract: `process() → Path`, `process_to_bytes(in_memory_files) → bytes`, `_init_logger()`

**`utils/bin_decryptor.py`**
- `BinFileDecryptor(private_key_path, passphrase)` — RSA+AES decryption of `.bin` files
- `.decrypt_file(bin_file_path) → bytes`
- `.decrypt_bytes(content) → bytes`
- Auto-detects format version: `0x02` → AES-256-GCM (v2), `0x01` → AES-256-CFB (v1), no marker → legacy

**`utils/bin_encryptor.py`**
- `BinEncryptor(public_key_path)` — RSA-OAEP + AES-256-GCM encryption (symmetric counterpart)
- `.encrypt_gcm(data) → bytes` — primary method; produces `0x02` version-tagged output
- `.encrypt_bytes(data) → bytes` — legacy CFB, kept for compatibility; do not use for new files
- Binary format (GCM): `[0x02] + [RSA-encrypted AES key (256 B)] + [IV (16 B)] + [GCM tag (16 B)] + [ciphertext]`

**`utils/db.py`**
- `init_db()` — idempotent SQLite table creation; auto-migrates legacy `users.json` and `history.json` on first startup
- `get_user_hash(username) → str | None`, `upsert_user(username, hashed_password)`, `delete_user(username) → bool`, `list_users() → list[str]`
- DB path defaults to `rport.db` at project root; overridable via `DB_PATH` env var (used in tests)

**`utils/sftp_client.py`**
- `SFTPConfig.from_env()` — reads SFTP credentials from env vars; `SFTP_UPLOAD_PATH` sets the deposit directory (default `/`)
- `SFTPClient`:
  - `.deposit(files, remote_dir)` — primary web-UI method: uploads `(filename, bytes)` pairs from memory then deposits `go_recup.txt`, all in one connection; each file is transferred atomically as `.tmp` then renamed
  - `.upload(local_path, remote_path)` — CLI: uploads a server-side local file to the exact remote path (atomic `.tmp` → rename)
  - `.download(remote_path, local_path)` — CLI: downloads a remote file or directory
  - `.delete(remote_path)` — CLI: deletes a remote file
  - `.list_contents(remote_path)` — lists recursively; `.tmp` files are silently skipped
  - `.upload_trigger(remote_dir)` — CLI: deposits `go_recup.txt` standalone (uses `_put_trigger` internally)

---

## CSV format detection — intentional divergence

`payroll/file_format.py` and `cost_center/file_format.py` both produce a `FileFormat` object
but use different algorithms for numeric separator detection:

- **Payroll — first consensus:** samples numeric fields; aborts if two fields disagree.
  Conservative: fails fast on ambiguous files.
- **Cost center — majority vote:** counts separator occurrences across all fields; picks the
  most common. Robust on large volumes with occasional inconsistent cells.

These algorithms were chosen for their respective data characteristics. **Do not merge them
into `utils/`.** The shared `FileFormat` dataclass in `utils/file_format.py` is the only
shared component.

---

## Job ownership model

Every `Job` object (in the in-memory job registry) must carry the `username` of the user
who created it. Route handlers for `GET /api/jobs/{id}`, `GET /api/jobs/{id}/download`,
and `GET /api/jobs/{id}/logs` must check `job.username == current_user.username` and raise
HTTP 403 on mismatch. The `GET /api/history` endpoint must filter results to the requesting
user's own records only.

This prevents IDOR: user A cannot read, download, or inspect user B's HR output files.

---

## Custom exception types

Module-specific errors must be raised as typed exceptions, not bare `Exception` or
string-compared messages.

| Exception | Module | Purpose |
|---|---|---|
| `DecryptionError` | `src/admin/exceptions.py` | Raised by `AdminAggregator._decrypt_single_file` when `BinFileDecryptor` fails; caught by type in `_decrypt_and_consolidate` |

Define each custom exception in the module where it originates (`exceptions.py`).
Catch by type, never by inspecting the message string.

---

## Admin data flow

```
Excel files (.xlsx)  ←  user places in data/admin/excel/
                         or uploads via POST /api/admin/process
        │
        ▼
  admin/excel_reader.py
    • Sheet detection: col A header contains "* mandatory field"
    • Fuzzy column matching (Levenshtein ≥ 0.85 vs HEADERS_MAPPING keys)
    • Remove test rows (DOE/John), placeholder rows (Period="Date (YYYYMM)")
        │
        ▼  English-named DataFrame + Line/Country/Path tracking cols
  admin/validators.py (normalize_field_types → validate_fields)
    • Same validators as the aggregator — logic is shared, not duplicated
        │
        ▼  Validated DataFrame
  admin/postprocessing.py (convert_types_for_export)
    • Column rename: English → French (HEADERS_MAPPING)
    • Sort by Période, Entité, Matricule paie locale
        │
        ▼  French-named DataFrame → CSV bytes (sep=";", decimal=",")
  utils/bin_encryptor.py (BinEncryptor)
    • AES-256-GCM encrypt CSV bytes (authenticated)
    • RSA-OAEP-SHA256 encrypt AES key with public key
        │
        ▼
  .bin file  →  data/admin/processed/  or browser download
        │
        ▼  (later, via aggregate --module admin)
  utils/bin_decryptor.py (BinFileDecryptor)
    • Decrypt .bin → CSV bytes → DataFrame
        │
        ▼
  ADMIN_checked_{timestamp}.csv  →  data/admin/ww/  or browser download
```

---

## Key design decisions

**Why services own `mkdir` and not aggregators.**
Aggregators are pure data transformers; filesystem side effects belong one layer up. This
makes aggregators easier to reason about and test in isolation.

**Why `Config.from_env()` is the only constructor.**
Hard-coded paths in aggregators would make the code environment-specific and fragile. The
`Config` dataclass centralizes all path resolution, and `from_env()` reads from `.env` via
`python-dotenv`, keeping secrets out of code.

**Why `COUNTRY_PROCESSOR_PATHS` lives in `constants.py`.**
Processor input/output folder paths are business configuration, not service logic. Keeping
them in `constants.py` makes it easy to add a new country without touching service code.

**Why `admin/parsers.py` re-exports `utils/parsers.py`.**
The admin module needs the same parsing functions as other modules. Re-exporting through
`admin/parsers.py` keeps the module's import namespace clean without duplicating logic.
Do not add any admin-specific logic to `admin/parsers.py`.

**Why the processor dispatch chain lives in a factory (`_make_payroll_processor`).**
`payroll_service.py` previously contained the same country→processor mapping twice (disk and
in-memory paths). The `_make_payroll_processor(country, ...) → (processor, prefix)` factory
in `payroll_service.py` eliminates drift: adding a new country requires updating only the
factory, not two separate call sites.

**Why `BaseAggregator` is in `utils/` and not a separate `base/` package.**
The shared methods (`_load_json_config`, `_rename_log`, `_filter_paths_by_countries`) depend
only on `utils/logging_utils.py` — already a utils module. Placing `BaseAggregator` in
`utils/base_aggregator.py` avoids introducing a new package layer and keeps all stateless
helpers in one place. Module-specific aggregators import from it as they do other utils.

**Why `AdminProcessor` extends `BaseAggregator` even though its return type is `.bin` bytes.**
`BaseAggregator` defines `process_to_bytes → bytes` in the abstract contract — the content
(CSV or `.bin`) is deliberately opaque at the base level. `AdminProcessor` satisfies the
contract and inherits `_load_json_config`, `_rename_log`, and `_init_logger` for free.
The docstring on each concrete implementation clarifies what the bytes represent.

**Why `AdminProcessor` validators are not duplicated from `AdminAggregator`.**
Both call the same `normalize_field_types()` and `validate_fields()` from `admin/validators.py`.
The processor runs validation on English-named columns (from Excel), then `convert_types_for_export`
translates to French before encrypting. The aggregator reverses the mapping after decryption, then
applies the same two-pass validation. No duplication, one source of truth for business rules.

**Why two `AdminConfig` factory methods instead of one.**
`from_env()` mandates `PRIVATE_KEY_INTEGRITY_CHECKER_PATH` (aggregation path — decrypt).
`from_env_processor()` reads `PUBLIC_KEY_INTEGRITY_CHECKER_PATH` only (processor path — encrypt).
Keeping them separate avoids requiring both keys on every deployment and makes the intent explicit.
