<p align="center">
  <img src="img/SubwayIQ.png" width="120" alt="SubwayIQ logo" />
</p>

<h1 align="center">SubwayIQ</h1>
<p align="center"><strong>Subway LiveIQ API Viewer & Custom Report Building Tool</strong></p>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8–3.12-blue?logo=python&logoColor=white" alt="Python versions">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License">
</p>

---

## Table of Contents

* [Why This Exists](#why-this-exists)
* [Screenshots](#screenshots)
* [What This App Does](#what-this-app-does)
* [Module Details](#module-details)

  * [Sales.py](#salespy)
  * [3rd-Party.py](#3rd-partypy)
  * [Labor.py](#laborpy)
  * [Transactions.py](#transactionspy)
  * [Items-Sold.py](#items-soldpy)
  * [Discounts.py](#discountspy)
  * [\_CUSTOM.py](#custompy-template)
* [Quick Start](#quick-start)
* [Packaging to EXE](#packaging-to-exe)
* [Working With `config.dat`](#working-with-configdat)

  * [How to Obtain API Keys](#how-to-obtain-api-keys)
* [Folder Map](#folder-map)
* [Troubleshooting](#troubleshooting)
* [LiveIQ API Quirks & Pitfalls](#liveiq-api-quirks--pitfalls)
* [Developing Custom Modules](#developing-custom-modules)

  * [Minimal Module Example](#minimal-module-example)
  * [Host Helpers Exposed to Modules](#host-helpers-exposed-to-modules)
  * [Common Patterns](#common-patterns)
  * [LiveIQ Endpoint Names](#liveiq-endpoint-names)
  * [Debugging Tips](#debugging-tips)
* [Contributing](#contributing)
* [License](#license)

---

## Why This Exists

Running multiple Subway® stores typically means juggling multiple LiveIQ logins and exporting clumsy CSVs one account at a time. **SubwayIQ** connects directly to the **LiveIQ Franchisee API**, consolidates all of your accounts and stores into a single interface, and gives you:

* Fast JSON inspection of any supported API endpoint.
* Clean, printable, exportable reports (CSV / JSON / TXT / PDF\*).
* A plug‑in style **modules/** folder where each Python file becomes a report button.
* Encrypted credentials storage (`config.dat`).

<sub>\*PDF export available when `reportlab` is installed.</sub>

---

## Screenshots

<p>
  <img src="img/ss-3.png" width="300" alt="Main UI with account and store selection" />
  <img src="img/ss-4.png" width="300" alt="Third-Party Sales Report" />
</p>

<p align="center"><em>Main UI (left) and a sample Third‑Party Sales Report (right).</em></p>

---

## What This App Does

| 🛠 Feature                  | Detail                                                                                                         |
| --------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Multi-account login**     | Reads unlimited ClientID / ClientKEY pairs from encrypted `config.dat`, auto-discovers all stores per account. |
| **Store & account filters** | Hierarchical Treeview with Select All / Unselect All, per-store toggles, and search box.                       |
| **Date presets**            | Today · Yesterday · Past N Days (2–30) · Custom via `DateEntry` widgets.                                       |
| **Endpoint picker**         | Seven built-in LiveIQ endpoints (extensible).                                                                  |
| **Viewer**                  | Raw JSON or flattened dotted-path key/value view; Copy, Print, CSV export.                                     |
| **Plug‑in system**          | Drop a `.py` file in `modules/` to add a custom report button.                                                 |
| **Pre-built modules**       | Sales · 3rd-Party · Labor · Transactions · Items-Sold · Discounts · `_CUSTOM` template.                        |
| **Report actions**          | Copy, print, email (mailto or SMTP), export CSV/JSON/TXT/PDF\*.                                                |
| **Error logging**           | UTC‑stamped `error.log` for debugging.                                                                         |
| **Security**                | Config encrypted with user password (Fernet).                                                                  |
| **Packaging-ready**         | Runs as `python SubwayIQ.py` or single‑file EXE (PyInstaller).                                                 |

---

## Module Details

Each Python file in `modules/` produces a button in the main UI. Clicking a module opens a report window pre-wired with toolbar actions (Copy, Print, Email, Export) and a scrollable text report area. Modules receive helper functions & globals from the host app (see [Host Helpers](#host-helpers-exposed-to-modules)).

### Sales.py

**Purpose:** Sales summaries and daily breakdowns for selected stores & date range.
**API Endpoints:** `Sales Summary` (multi‑day), `Daily Sales Summary` (single‑day).
**Key Data:** Net sales, tax, units, transactions, cash/card, 3rd‑party sales & txns.
**Behavior:** Uses multi‑day endpoint when range >1 day; falls back to daily endpoint otherwise. Validates range (≤30 days). Handles rate limits & errors.
**Exports:** CSV / JSON / TXT / PDF\* / Email.

**Report Layout:**

```
Sales Report: 2025-07-01 → 2025-07-02
=== Sales Summary (2025-07-01 to 2025-07-02) ===
Store   Sales      Tax    Units   Txns  Cash/Card   3rd $   3rd Txns
... rows ...
```

(Then per‑day sections and per‑store detail tables.)

---

### 3rd-Party.py

**Purpose:** Third‑party provider sales (DoorDash, Grubhub, Uber Eats, EzCater) by store & day.
**API Endpoint:** `Third Party Sales Summary`.
**Range:** ≤7 days recommended (API heavy).
**Outputs:** All‑days summary, daily summaries, and per‑store breakdowns.
**Exports:** CSV / JSON / TXT / PDF\* / Email.

**Report Layout:**

```
3rd-Party Sales Report: 2025-07-01 → 2025-07-02
Store  TotSales  TotNet  TotTxns  DD-T DD-N DD-S  GH-T ...
```

---

### Labor.py

**Purpose:** Employee labor hours & shift detail.
**API Endpoint:** `Daily Timeclock`.
**Outputs:** Per‑employee clock‑in/out lines, per‑employee hours summary, per‑store totals (hrs, employees, shifts).
**Range:** ≤30 days.
**Exports:** CSV / JSON / TXT / PDF\* / Email.

---

### Transactions.py

**Purpose:** Transaction-level summaries (totals, counts, method mix, TBD).
**API Endpoint:** `Transaction Summary`.
**Status:** Stub module — extend to match your reporting needs.
**Exports:** Standard toolbar; implement formatting inside module.

---

### Items-Sold.py

**Purpose:** Item-level sales aggregation.
**Likely Endpoint:** `Transaction Details` (or other SKU-capable endpoint).
**Status:** Stub — wire up parsing and output columns (Item, Qty, Net, Discounts, etc.).

---

### Discounts.py

**Purpose:** Discount usage across transactions, including nested modifiers/add‑ons where discounts hide.
**API Endpoint:** `Transaction Details`.
**Outputs:** Per‑discount per‑store table, discount totals, and store summary.
**Exports:** CSV / JSON / TXT / PDF\* / Email.

**Example Row Fields:** Code · Count · Orig\$ · Adj\$ · Disc\$ · Total\$.

---

### \_CUSTOM.py (Template)

Use this as a starting point for your own report. Copy, rename, edit logic, and relaunch SubwayIQ — the button appears automatically.

**Provides:** Boilerplate UI, toolbar actions, error handling hooks, and access to host helpers.
**Max Range:** Set your own; 30 days typical.

---

## Quick Start

```bash
# Clone
git clone https://github.com/alxl85/SubwayIQ.git
cd SubwayIQ

# Create & activate venv
python -m venv .venv
# POSIX shells
source .venv/bin/activate || . .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

# Install deps
pip install -r requirements.txt

# Run
python SubwayIQ.py
```

**First Launch Behavior:**

* Prompts for password.
* Creates encrypted `config.dat` (empty).
* Creates `modules/` with sample modules (Sales.py, 3rd-Party.py, Labor.py, Transactions.py, Items-Sold.py, Discounts.py, \_CUSTOM.py).
* Use **Accounts** button to add API credentials.

---

## Packaging to EXE

A prebuilt binary may be provided in Releases. To build your own with PyInstaller:

```powershell
pyinstaller --onefile --noconsole `
  --name "SubwayIQ" `
  --icon="SubwayIQ.ico" `
  --add-data "modules;modules" `
  --add-data "SubwayIQ.png;." `
  --add-data "SubwayIQ.ico;." `
  SubwayIQ.py
```

**macOS/Linux:** Use a colon (`:`) instead of semicolon in `--add-data` values.

**Debug Build:** Omit `--noconsole` to see stderr/tracebacks.

**Assets:** Ensure `SubwayIQ.png` and `SubwayIQ.ico` exist so branding loads in the UI.

---

## Working With `config.dat`

`config.dat` stores all credentials, email targets, SMTP settings, selected accounts/stores, and worker thread limits. The file is **encrypted using Fernet** with a key derived from the password you enter at launch.

> Do **not** edit `config.dat` by hand. Use the in-app **Accounts** and **Emails** dialogs.

**Structure (decrypted example):**

```json
{
  "accounts": [
    {
      "Name": "Franchisee A",
      "ClientID": "xxxxxxxx",
      "ClientKEY": "yyyyyyyy",
      "StoreIDs": ["12345", "67890"],
      "Status": "OK"
    }
  ],
  "max_workers": 8,
  "emails": ["user@example.com"],
  "smtp": {
    "server": "smtp.example.com",
    "port": 587,
    "username": "user",
    "password": "pass",
    "from": "user@example.com"
  },
  "selected_accounts": ["Franchisee A"],
  "selected_stores": ["12345", "67890"]
}
```

### How to Obtain API Keys

1. Open SubwayIQ → **Accounts**.
2. Add one entry per franchisee (ClientID + ClientKEY).
3. SubwayIQ pings `/api/Restaurants` to auto-discover store numbers.
4. Stores are deduplicated across accounts.

---

## Folder Map

```
SubwayIQ/
├─ SubwayIQ.py
├─ requirements.txt
├─ SubwayIQ.ico
├─ SubwayIQ.png
├─ config.dat
├─ error.log
└─ modules/
   ├─ Sales.py
   ├─ 3rd-Party.py
   ├─ Labor.py
   ├─ Transactions.py
   ├─ Items-Sold.py
   ├─ Discounts.py
   └─ _CUSTOM.py
```

**Packaged Layout (example Release build):**

```
Release/
├─ SubwayIQ.exe
├─ SubwayIQ.ico
├─ SubwayIQ.png
├─ config.dat
└─ modules/
   ├─ Sales.py
   ├─ 3rd-Party.py
   ├─ Labor.py
   ├─ Transactions.py
   ├─ Items-Sold.py
   ├─ Discounts.py
   └─ _CUSTOM.py
```

---

## Troubleshooting

| 😖 Symptom         | 🩹 Fix                                                                                        |
| ------------------ | --------------------------------------------------------------------------------------------- |
| EXE does nothing   | Rebuild without `--noconsole`; run from cmd/PowerShell to view tracebacks.                    |
| No module buttons  | Ensure `modules/` exists and was included in PyInstaller `--add-data`.                        |
| "Invalid password" | Password must match the one used to encrypt `config.dat`; use **Reset Config** to start over. |
| Icon/logo missing  | Confirm `SubwayIQ.ico` / `.png` bundled in build. Use 256×256 ICO.                            |
| Blank report text  | Check `error.log`; ensure ScrolledText widget is active.                                      |
| Rate limit (429)   | Lower `max_workers` (via GUI), wait for API cooldown. Logged automatically.                   |

---

## LiveIQ API Quirks & Pitfalls

| Issue                                       | Impact                    | Mitigation                                                        |
| ------------------------------------------- | ------------------------- | ----------------------------------------------------------------- |
| Undocumented \~60 req/min throttle          | 429 errors                | Use `config_max_workers` ≤8; built-in retry & rate-limit handler. |
| 30–60 min data latency                      | "Today" may be incomplete | Pull after store close; surface warnings in reports.              |
| Schema drift (e.g., `netSale` → `netSales`) | KeyErrors                 | Always `.get()` with defaults in parsing code.                    |
| Store-local timestamps                      | TZ math weird             | Normalize if you care (pytz/zoneinfo; not yet built in).          |
| Occasional 500/502s                         | Module crash              | Wrap loops in try/except; log via `log_error()`.                  |

---

## Developing Custom Modules

SubwayIQ dynamically loads any `.py` file in `modules/` (except names starting with `_` unless `_CUSTOM.py`). Each module must expose a `run(window)` function; the host passes in a prepared `tk.Toplevel` to render your UI.

### Minimal Module Example

```python
# my_module.py

def run(window):
    import tkinter as tk
    from tkinter.scrolledtext import ScrolledText

    # Helpers injected by host at import time:
    #   fetch_data(endpoint, store_id, start, end, cid, ckey)
    #   store_vars, config_accounts, get_selected_start_date, ...

    txt = ScrolledText(window, wrap="word", font=("Consolas", 10))
    txt.pack(expand=True, fill="both", padx=10, pady=10)

    start = get_selected_start_date()
    end   = get_selected_end_date()
    stores = [sid for sid, v in store_vars.items() if v.get()]

    txt.insert("end", f"Custom Report: {start} → {end}\n")
    txt.insert("end", f"Stores: {', '.join(stores)}\n\n")

    # Simple demo – call a LiveIQ endpoint for the first store that is selected
    if stores:
        first_sid = stores[0]
        # Find account with that store
        for acct in config_accounts:
            if first_sid in acct.get("StoreIDs", []):
                data = fetch_data("Sales Summary", first_sid, start, end, acct["ClientID"], acct["ClientKEY"])
                txt.insert("end", f"Raw JSON for {first_sid}:\n{data}\n")
                break
```

---

### Host Helpers Exposed to Modules

| Helper                                                  | Purpose                                                                   |
| ------------------------------------------------------- | ------------------------------------------------------------------------- |
| `fetch_data()`                                          | Wrapped LiveIQ API call with retry + error logging + rate limit handling. |
| `store_vars`                                            | `{store_id: tk.BooleanVar}` selection map.                                |
| `config_accounts`                                       | List of configured accounts; contains ClientID/KEY & StoreIDs.            |
| `get_selected_start_date()` / `get_selected_end_date()` | Return YYYY-MM-DD strings from main UI date pickers.                      |
| `handle_rate_limit()`                                   | Central 429 handler; disables affected account and alerts user.           |
| `log_error()`                                           | Append to UTC‑stamped `error.log`.                                        |
| `config_emails`                                         | List of email addresses configured in UI.                                 |
| `config_smtp`                                           | SMTP settings dict.                                                       |
| `_password_validated`                                   | True once password accepted at launch.                                    |
| `flatten_json()`                                        | Utility to explode nested JSON into dotted keys.                          |
| `config_max_workers`                                    | Thread pool size hint for parallel fetches.                               |

---

### Common Patterns

| Goal                | Snippet                                                              |
| ------------------- | -------------------------------------------------------------------- |
| Background thread   | `threading.Thread(target=fn, daemon=True).start()`                   |
| Log to ScrolledText | `log("Message", "tag")` (tags: title, heading, sep)                  |
| Parallel fetch      | `with ThreadPoolExecutor(max_workers=config_max_workers) as ex: ...` |
| Flatten payload     | `flat = flatten_json(obj)`                                           |
| Export file         | Use helper patterns in `Sales.py` / `3rd-Party.py`.                  |
| Email report        | Reuse `open_email_dialog()` pattern in modules.                      |

---

### LiveIQ Endpoint Names

| Dropdown Label                  | Value to `fetch_data()`           |
| ------------------------------- | --------------------------------- |
| Sales Summary                   | "Sales Summary"                   |
| Daily Sales Summary             | "Daily Sales Summary"             |
| Daily Timeclock                 | "Daily Timeclock"                 |
| Third Party Sales Summary       | "Third Party Sales Summary"       |
| Third Party Transaction Summary | "Third Party Transaction Summary" |
| Transaction Summary             | "Transaction Summary"             |
| Transaction Details             | "Transaction Details"             |

---

### Debugging Tips

* Run without `--noconsole` to see stdout/stderr & tracebacks.
* Use `log_error()` liberally — writes to `error.log` w/ UTC timestamp + context.
* Lazy‑import heavy libs (e.g., `reportlab`) inside module `run()` to avoid PyInstaller bloat.
* Check API response codes; LiveIQ sometimes returns HTML error blobs.

---

## Contributing

Pull requests welcome! To contribute:

1. Fork the repo.
2. Create a feature branch.
3. Install dev deps: `pip install -r requirements-dev.txt`.
4. (Optional) `pre-commit install` for lint/format hooks.
5. Include screenshots / GIFs for UI changes.
6. Submit PR — describe the change & testing.

---

## License

**MIT License** – Use, fork, adapt. No warranty. If your sandwich shop catches fire, that’s on the toaster, not this code.

---

<p align="center"><sub>Built for franchisees who would rather read numbers than copy‑paste them.</sub></p>
