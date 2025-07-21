




SubwayIQ
Subway LiveIQ API Viewer & Custom Report Building Tool

















Table of Contents





Why This Exists



Features Overview



Screenshots



Module Details



Prerequisites



Quick Start



Packaging to .exe



Working with config.dat



Folder Map



API Usage



Security Considerations



Troubleshooting



LiveIQ API Quirks & Pitfalls



Developing Custom Modules



Contributing



License



Why This Exists

Managing multiple Subway® stores often involves juggling multiple LiveIQ logins, navigating a clunky web interface, and exporting cumbersome CSVs for analysis. SubwayIQ simplifies this by providing a desktop application that connects directly to the Subway LiveIQ franchisee API. It consolidates all accounts and stores into a single, intuitive GUI, offering raw data views, customizable reports, and export options. Whether you're a franchisee needing quick insights or a developer building tailored analytics, SubwayIQ streamlines access to LiveIQ data, saving time and reducing manual work.



Features Overview







🛠 Feature



Detail





Multi-Account Login



Manages unlimited ClientID/ClientKEY pairs stored in an encrypted config.dat, auto-discovering associated stores.





Store & Account Filters



Hierarchical Treeview with search, Select All, and Unselect All for accounts and stores.





Date Range Selection



Presets (Today, Yesterday, Past 2/3/7/14/30 Days) or custom dates via DateEntry widgets.





API Endpoint Viewer



Access seven LiveIQ endpoints with raw JSON or flattened views, plus Copy, Print, and Export CSV options.





Modular Reporting



Plug-in system loads .py files from modules/ as report buttons, with six pre-built modules.





Pre-Built Modules



- Sales: Sales summaries with daily breakdowns.
- 3rd-Party: Third-party sales (DoorDash, GrubHub, etc.) with summaries.
- Labor: Employee hours and shifts.
- Transactions: Transaction summaries.
- Items-Sold: Item sales details.
- Discounts: Discount usage summaries.
- _CUSTOM: Template for custom modules.





Export Options



Export reports as CSV, JSON, TXT, or PDF (if reportlab installed); print to default printer.





Email Integration



Send reports via mailto or SMTP with configurable email lists and settings.





Error Handling



Robust error logging to error.log with UTC timestamps; handles rate limits and connectivity issues.





Security



Encrypts config.dat with Fernet using a user-provided password; validates credentials on startup.





Cross-Platform



Runs as a Python script or packaged EXE, compatible with Windows, Linux, and macOS.



Screenshots





Left: Main UI with account/store selection and date controls. Right: Sample Third-Party Sales Report with export options.



Module Details

SubwayIQ includes six pre-built modules in the modules/ folder, each generating a specific report from LiveIQ API data. Modules share a consistent UI with a toolbar (Copy, Print, Email, Export CSV/JSON/TXT/PDF) and a resizable ScrolledText area for formatted reports. Below are detailed descriptions of each module.

Sales.py





Purpose: Aggregates sales data across selected stores and date ranges, with daily breakdowns.



API Endpoints: Sales Summary (multi-day), Daily Sales Summary (single-day).



Functionality:





Fetches net sales, tax, units, transactions, cash/card totals, and third-party sales/transactions.



Displays a top-level summary for the entire range, daily summaries, and per-store daily breakdowns (multi-day only).



Supports up to 30 days; handles rate limits, invalid dates, and field variations (e.g., netSales vs. netSalesTotal).



Exports to CSV, JSON, TXT, or PDF; supports email via mailto or SMTP.



Report Format:





Columns: Store (6 chars), Sales (10.2f), Tax (8.2f), Units (7 chars), Txns (7 chars), Cash/Card (11.2f), 3rd $ (8.2f), 3rd Txns (10 chars).



Tags: title (Courier New, 12, bold), heading (Courier New, 11, bold), sep (gray).



Example Output:

Sales Report: 2025-07-01 → 2025-07-02
=== Sales Summary (2025-07-01 to 2025-07-02) ===
Store   Sales      Tax    Units   Txns  Cash/Card   3rd $   3rd Txns
───────────────────────────────────────────────────────────────────
12345   1500.25   120.50    200    180    1300.75   200.50       20
───────────────────────────────────────────────────────────────────
Per-Day Sales Summary (2025-07-01)
Store   Sales      Tax    Units   Txns  Cash/Card   3rd $   3rd Txns
───────────────────────────────────────────────────────────────────
12345    800.10    64.25    100     90     700.50   100.25       10
───────────────────────────────────────────────────────────────────
12345
Date        Sales      Tax    Units   Txns  Cash/Card   3rd $   3rd Txns
───────────────────────────────────────────────────────────────────
2025-07-01   800.10    64.25    100     90     700.50   100.25       10
2025-07-02   700.15    56.25    100     90     600.25   100.25       10
───────────────────────────────────────────────────────────────────

3rd-Party.py





Purpose: Summarizes third-party sales (DoorDash, GrubHub, Uber Eats, EzCater) for selected stores.



API Endpoint: Third Party Sales Summary.



Functionality:





Fetches total sales, net sales, and transactions per provider.



Displays an all-days summary (multi-day), daily summaries, and per-store daily breakdowns (multi-day).



Supports up to 7 days; handles rate limits and missing data.



Exports to CSV, JSON, TXT, or PDF; supports email via mailto or SMTP.



Report Format:





Columns: Store (6 chars), TotSales (10.2f), TotNet (8.2f), TotTxns (7 chars), followed by DD-T/DD-N/DD-S, GH-T/GH-N/GH-S, UE-T/UE-N/UE-S, EC-T/EC-N/EC-S (transactions, net sales, sales).



Tags: title (Courier New, 12, bold), heading (Courier New, 11, bold), sep (gray).



Example Output:

3rd-Party Sales Report: 2025-07-01 → 2025-07-02
=== Third-Party Summary (2025-07-01 to 2025-07-02) ===
Store  TotSales  TotNet  TotTxns  DD-T DD-N DD-S  GH-T GH-N GH-S  UE-T UE-N UE-S  EC-T EC-N EC-S
────────────────────────────────────────────────────────────────────────────────────────────────
12345   500.75  450.25      50     20 200.50 220.75  15 150.25 160.50  10  80.50  90.25   5  20.00  30.00
────────────────────────────────────────────────────────────────────────────────────────────────
Per-Day Third-Party Summary (2025-07-01)
Store  TotSales  TotNet  TotTxns  DD-T DD-N DD-S  GH-T GH-N GH-S  UE-T UE-N UE-S  EC-T EC-N EC-S
────────────────────────────────────────────────────────────────────────────────────────────────
12345   300.50  270.75      30     12 120.25 130.50   9  90.50  95.75   6  50.00  55.50   3  10.00  15.00
────────────────────────────────────────────────────────────────────────────────────────────────
Per-Store Breakdown for 12345
Date        TotSales  TotNet  TotTxns  DD-T DD-N DD-S  GH-T GH-N GH-S  UE-T UE-N UE-S  EC-T EC-N EC-S
────────────────────────────────────────────────────────────────────────────────────────────────
2025-07-01   300.50  270.75      30     12 120.25 130.50   9  90.50  95.75   6  50.00  55.50   3  10.00  15.00
2025-07-02   200.25  180.50      20      8  80.25  90.25   6  60.75  65.75   4  30.50  35.75   2  10.00  15.00
────────────────────────────────────────────────────────────────────────────────────────────────

Labor.py





Purpose: Tracks employee work hours and shifts across selected stores and date ranges.



API Endpoint: Daily Timeclock.



Functionality:





Fetches clock-in and clock-out data, calculating hours worked per shift.



Displays per-store details (employee, times, hours) and summaries (per-employee and per-store).



Supports up to 30 days; handles rate limits, invalid timestamps, and missing data.



Exports to CSV, JSON, TXT, or PDF; supports email via mailto or SMTP.



Report Format:





Per-Store Details: Employee (30 chars), In (20 chars), Out (20 chars), Hrs (5.2f).



Per-Employee Summary: Employee (dynamic width), Hrs (5.2f), Shifts (6 chars).



Store Summary: Store (9 chars), Hrs (8.2f), Emps (8 chars), Shifts (8 chars).



Tags: title (Courier New, 12, bold), heading (Courier New, 11, bold), sep (gray).



Example Output:

Labor Hours: 2025-07-01 → 2025-07-01
Store 12345 (Acct: Franchisee A)
Employee                        In                   Out                  Hrs
────────────────────────────────────────────────────────────────────────────────
John Doe                       07/01 08:00 AM       07/01 04:00 PM        8.00
Jane Smith                     07/01 09:00 AM       (in)                  0.00
────────────────────────────────────────────────────────────────────────────────
Summary of Hours per Employee
Employee    Hrs    Shifts
────────────────────────────
Jane Smith   0.00      1
John Doe     8.00      1
Summary of Hours per Store
Store        Hrs     Emps  Shifts
───────────────────────────────────
12345       8.00        2      2

Transactions.py





Purpose: Summarizes transaction details (sales, voids, refunds) for selected stores.



API Endpoint: Transaction Summary.



Functionality:





Fetches transaction data including type, receipt, clerk, channel, and financials.



Displays per-store transaction lists, store summaries, daily summaries, and void/refund details.



Supports up to 7 days; handles rate limits and data errors.



Exports to CSV, JSON, TXT, or PDF; supports email via mailto or SMTP.



Report Format:





Transaction Entries: Store (6 chars), Date (10 chars), Time (8 chars), Type (5 chars), Receipt (10 chars), Clerk (20 chars), Channel (20 chars), Sale Type (10 chars), Units (5 chars), Order Source (20 chars), Delivery Provider (15 chars), Delivery Partner (15 chars), Total (10.2f), Net Total (10.2f), Tax (8.2f).



Summaries: Store (6 chars), TotSales (10.2f), TotNet (8.2f), TotTax (8.2f), TotUnits (8 chars), TotTxns (8 chars), EatIn (5 chars), ToGo (5 chars), Deliv (5 chars), AvgTx$ (8.2f), Void# (5 chars), Void$ (8.2f), Rfund# (6 chars), Rfund$ (8.2f).



Tags: title (Courier New, 12, bold), heading (Courier New, 11, bold), sep (gray).



Example Output:

Transactions Report: 2025-07-01 → 2025-07-01
Transactions for Store 12345
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Store  Date        Time      Type   Receipt    Clerk                Channel              Sale Type  Units  Order Source         Delivery Provider  Delivery Partner  Total      Net Total  Tax
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
12345  2025-07-01  10:00:00  Sale   1001       John Doe            POS                  EatIn       2     In-Store             None              None              15.50      14.00     1.50
12345  2025-07-01  10:05:00  Void   1002       Jane Smith          Online               ToGo        1     Online               DoorDash          None               8.00       7.20     0.80
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Store Summaries
───────────────────────────────────────────────────────────────────────────────────────────
Store  TotSales  TotNet  TotTax  TotUnits  TotTxns  EatIn  ToGo  Deliv  AvgTx$  Void#  Void$  Rfund#  Rfund$
───────────────────────────────────────────────────────────────────────────────────────────
12345    15.50   14.00    1.50        2        2      1     1      0    7.75      1   8.00      0    0.00
───────────────────────────────────────────────────────────────────────────────────────────

Items-Sold.py





Purpose: Tracks items sold across selected stores and date ranges.



API Endpoint: Transaction Details.



Functionality:





Fetches item-level sales data (description, PLU, quantity, price).



Displays aggregated item summaries, store summaries, daily breakdowns, and per-store item details.



Supports up to 7 days; handles rate limits and data errors.



Exports to CSV, JSON, TXT, or PDF; supports email via mailto or SMTP.



Report Format:





Columns: Description (25 chars), PLU (6 chars), Count (10 chars), Total (10.2f).



Store Summary: Store (6 chars), Total Count (12 chars), Total Sales (12.2f).



Tags: title (Courier New, 12, bold), heading (Courier New, 11, bold), sep (gray).



Example Output:

Items-Sold Report: 2025-07-01 → 2025-07-01
All Items Sold
Description                   |   PLU |     Count |     Total
─────────────────────────────────────────────────────────────
Turkey Sub                   |  1001 |        50 |    300.00
Veggie Sub                   |  1002 |        30 |    150.00
─────────────────────────────────────────────────────────────
Store Summary
Store  | Total Count | Total Sales
────────────────────────────────────
12345 |          80 |      450.00

Discounts.py





Purpose: Analyzes discount usage across transactions for selected stores.



API Endpoint: Transaction Details.



Functionality:





Scans transactions for discount codes, calculating original and adjusted prices.



Displays per-discount details, per-store breakdowns, daily summaries, and store totals.



Supports up to 7 days; handles rate limits and data errors.



Exports to CSV, JSON, TXT, or PDF; supports email via mailto or SMTP.



Report Format:





Per-Discount Details: Desc (25 chars), Code (in header), Count (7 chars), Orig$ (7.2f), Adj$ (7.2f), Disc$ (7.2f), Total$ (7.2f).



Per-Discount Totals: Code (6 chars), Count (7 chars), Total (7.2f).



Store Summary: Store (6 chars), Count (7 chars), Total (7.2f).



Tags: title (Courier New, 12, bold), heading (Courier New, 11, bold), sep (gray).



Example Output:

Discounts: 2025-07-01 → 2025-07-01
BOGO50 (BOGO)
Store | Count |  Orig$ |   Adj$ |  Disc$ |  Total$
───────────────────────────────────────────────────
12345    10    15.00     7.50     7.50    75.00
───────────────────────────────────────────────────
Per-Discount Averages
Code  | Count |  Total
───────────────────────
BOGO  |    10 |   75.00
Store Summary
Store | Count |  Total
───────────────────────
12345 |    10 |   75.00
All   |    10 |   75.00

_CUSTOM.py





Purpose: Template for custom module development.



API Endpoint: Configurable (set ENDPOINT_NAME).



Functionality:





Provides a stub run(window) function with basic data fetching and display logic.



Matches other modules’ UI (toolbar, text area) and error handling.



Supports up to 30 days; customizable for any LiveIQ endpoint.



Report Format:





Customizable; default shows Store (6 chars), Value (7 chars).



Tags: title (Courier New, 12, bold), heading (Courier New, 11, bold), sep (gray).



Example Output:

Custom Report: 2025-07-01 → 2025-07-01
Sample Data Summary
Store  | Value
───────────────────
12345     100



Prerequisites





Python: Version 3.8–3.12.



Dependencies (listed in requirements.txt):





tkinter (usually included with Python).



tkcalendar for date picker widgets.



requests for API calls.



pywin32 (Windows only) for printing.



Pillow for logo/icon handling.



cryptography for config encryption.



tenacity for retry logic.



reportlab (optional) for PDF exports.



Subway LiveIQ API Access:





Obtain ClientID and ClientKEY from Subway Fresh Connect.



System:





Windows, Linux, or macOS.



Internet connection for API calls and module downloads.



Optional:





PyInstaller for building executables.



pre-commit for development (linting/formatting).

Install dependencies:

pip install -r requirements.txt



Quick Start





Clone the repository:

git clone https://github.com/alxl85/SubwayIQ.git
cd SubwayIQ



Set up a virtual environment:

python -m venv .venv
. .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate  # Windows



Install dependencies:

pip install -r requirements.txt



Run the application:

python SubwayIQ.py



On first launch:





Enter a password to encrypt config.dat.



Use the Manage Accounts dialog to add ClientID/ClientKEY pairs.



Configure email addresses and SMTP settings via the Emails dialog (optional).



Select stores, date ranges, and run reports via the GUI.

The first launch creates config.dat and a modules/ folder with Sales.py, 3rd-Party.py, Labor.py, Transactions.py, Items-Sold.py, Discounts.py, and _CUSTOM.py.



Packaging to .exe

A pre-packaged SubwayIQ.exe is available, but you can build your own:

pyinstaller --onefile --noconsole `
  --name "SubwayIQ" `
  --icon="SubwayIQ.ico" `
  --add-data "modules;modules" `
  --add-data "SubwayIQ.png;." `
  --add-data "SubwayIQ.ico;." `
  SubwayIQ.py





Use : instead of ; in --add-data on macOS/Linux.



Remove --noconsole for debugging to view tracebacks.



Ensure SubwayIQ.png and SubwayIQ.ico are included for logo/icon support.



Output is in dist/SubwayIQ.exe.



Working with config.dat

The config.dat file is an encrypted binary file storing account credentials, email lists, SMTP settings, and selected stores/accounts. It is managed via the GUI’s Manage Accounts and Emails dialogs.

Example Structure (decrypted for illustration):

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

How to Manage:





Launch SubwayIQ.py and enter your password.



Use Manage Accounts to add/edit/delete accounts (Name, ClientID, ClientKEY).



Use Emails to manage email addresses and SMTP settings for report distribution.



The app auto-discovers store IDs via the /api/Restaurants endpoint.



Reset config.dat via Reset Config (backs up existing file).

Obtaining API Keys:





Log in to Subway Fresh Connect.



Navigate to Fresh Connect ▸ Instructions ▸ Generate Keys.



Copy ClientID and ClientKEY into the Manage Accounts dialog.









Do not edit config.dat directly; it’s encrypted with Fernet using a password-derived key.



Duplicate store IDs are deduplicated automatically.



Folder Map

SubwayIQ/
├ SubwayIQ.py
├ requirements.txt
├ SubwayIQ.ico
├ SubwayIQ.png
├ config.dat
├ error.log
└ modules/
    ├ Sales.py
    ├ 3rd-Party.py
    ├ Labor.py
    ├ Transactions.py
    ├ Items-Sold.py
    ├ Discounts.py
    ├ _CUSTOM.py
└ img/
    ├ ss-1.png
    ├ ss-2.png
    ├ ss-3.png
    ├ ss-4.png

Packaged layout:

Release/
├ SubwayIQ.exe
├ SubwayIQ.ico
├ SubwayIQ.png
├ config.dat
└ modules/
    ├ Sales.py
    ├ 3rd-Party.py
    ├ Labor.py
    ├ Transactions.py
    ├ Items-Sold.py
    ├ Discounts.py
    ├ _CUSTOM.py



API Usage

SubwayIQ interacts with the Subway LiveIQ franchisee API (documented at SwaggerHub). The app uses the following endpoints:







Endpoint



fetch_data Value



Description





Sales Summary



Sales Summary



Aggregated sales data across a date range.





Daily Sales Summary



Daily Sales Summary



Daily sales data for specific dates.





Daily Timeclock



Daily Timeclock



Employee clock-in/out data.





Third Party Sales Summary



Third Party Sales Summary



Third-party provider sales (e.g., DoorDash).





Third Party Transaction Summary



Third Party Transaction Summary



Detailed third-party transaction data.





Transaction Summary



Transaction Summary



Transaction-level summaries.





Transaction Details



Transaction Details



Detailed transaction data with items.





Authentication: Uses ClientID and ClientKEY in HTTP headers (api-client, api-key).



Base URL: https://liveiqfranchiseeapi.subway.com.



Rate Limits: ~60 requests/min; handled with retries (tenacity) and handle_rate_limit.



Data Latency: 30–60 minutes; recent data may be incomplete.



Security Considerations





Config Encryption: config.dat is encrypted using Fernet with a password-derived key (PBKDF2HMAC, SHA256, fixed salt). Store the password securely.



Password Validation: Required on startup; incorrect passwords prevent access and exit the app.



API Credentials: Stored encrypted in config.dat; never logged or exposed in error.log.



SMTP Credentials: Stored encrypted; tested via the Emails dialog’s Test button.



File Permissions: Modules are written with writable permissions (non-Windows) to ensure updates via Reset Modules.



Network Security: Requires internet for API calls and module downloads; uses HTTPS with timeout (10s).

Best Practices:





Use a strong, unique password for config.dat.



Avoid sharing config.dat or API keys.



Regularly update modules via Reset Modules to ensure compatibility and security.



Troubleshooting







😖 Symptom



🩹 Fix





EXE does nothing



Build with --console and run in a terminal to view tracebacks.





No plugin buttons



Ensure modules/ exists and is included via --add-data.





"Invalid password" error



Verify the password; reset via Reset Config (creates backup).





Icon/logo missing



Include SubwayIQ.ico and SubwayIQ.png in --add-data. Use 256×256, 32-bit ICO.





Report text invisible



Check error.log for rendering errors; ensure ScrolledText is in normal state.





Rate limit errors (429)



Reduce max_workers via Manage Accounts or wait (check error.log for reset times).





"No data" in reports



Verify date range (data latency: 30–60 min); ensure stores are selected.





Module download fails



Check internet connection; retry Reset Modules.



LiveIQ API Quirks & Pitfalls







Issue



Impact



Mitigation





Undocumented rate limit (~60 req/min)



429 errors



Set config_max_workers ≤ 8; use handle_rate_limit with retries.





30–60 min data latency



Incomplete “Today” data



Pull data after store close or note in reports.





Field drift (e.g., netSale vs. netSales)



KeyError



Use .get() with defaults in module code.





Inconsistent timestamps



Timezone mismatches



Convert with pytz (not currently implemented).





Random 500/502 errors



Module crashes



Wrap API calls in try/except; log via log_error.





Empty API responses



Missing data



Check for data key; display “No data” messages.



Developing Custom Modules

Create custom reports by adding a .py file to modules/. The app dynamically loads it as a button calling run(window).

Minimal Module Example:

# modules/MyModule.py
import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

ENDPOINT_NAME = "Transaction Summary"
MAX_DAYS = 30

def create_toolbar(window, txt, title):
    toolbar = tk.Frame(window, bg="#f0f0f0")
    toolbar.pack(fill="x", pady=(8, 0), padx=8)
    copy_btn = tk.Button(toolbar, text="Copy", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    copy_btn.pack(side="right", padx=4)

    def enable_copy():
        copy_btn.config(state=tk.NORMAL, command=lambda: (
            window.clipboard_clear(),
            window.clipboard_append(txt.get("1.0", "end-1c"))
        ))

    return enable_copy

def run(window):
    from __main__ import get_selected_start_date, get_selected_end_date, fetch_data, store_vars, config_accounts, handle_rate_limit, log_error, config_max_workers, _password_validated

    if not _password_validated:
        tk.messagebox.showerror("Access Denied", "Password validation required.", parent=window)
        window.destroy()
        return

    try:
        start = datetime.strptime(get_selected_start_date(), "%Y-%m-%d").date()
        end = datetime.strptime(get_selected_end_date(), "%Y-%m-%d").date()
        if end < start:
            tk.messagebox.showerror("Invalid Date Range", "End date cannot be before start date.", parent=window)
            window.destroy()
            return
        if (end - start).days + 1 > MAX_DAYS:
            tk.messagebox.showerror("Date Range Too Large", f"Please select a range of at most {MAX_DAYS} days.", parent=window)
            window.destroy()
            return
    except ValueError as e:
        log_error(f"Date parsing error: {e}", endpoint=ENDPOINT_NAME)
        tk.messagebox.showerror("Bad Date", "Could not parse your start/end dates.", parent=window)
        return

    window.title("Custom Report")
    parent = window.master
    parent.update_idletasks()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    window.geometry(f"{int(window.winfo_screenwidth()*0.6)}x{int(window.winfo_screenheight()*0.6)}+{px}+{py}")
    window.resizable(True, True)
    window.minsize(800, 600)

    txt = ScrolledText(window, wrap="none", font=("Courier New", 11), fg="black", state="normal")
    enable_copy = create_toolbar(window, txt, "Custom Report")
    log_error("Toolbar created", endpoint=ENDPOINT_NAME)

    txt.pack(fill="both", expand=True, padx=8, pady=(4, 8))
    hbar = tk.Scrollbar(window, orient="horizontal", command=txt.xview)
    hbar.pack(fill="x", padx=8)
    txt.configure(xscrollcommand=hbar.set)
    txt.tag_configure("title", font=("Courier New", 12, "bold"), foreground="black")
    txt.tag_configure("heading", font=("Courier New", 11, "bold"), foreground="black")
    txt.tag_configure("sep", foreground="#888888")
    selected_stores = [s for s, v in store_vars.items() if v.get()]

    def log(line="", tag=None):
        txt.configure(state="normal")
        txt.insert("end", line + "\n", tag or ())
        txt.see("end")
        txt.update()
        txt.configure(state="normal")
        log_error(f"Log: {line}", endpoint=ENDPOINT_NAME)

    def worker():
        try:
            if not selected_stores:
                log("No stores selected.", "sep")
                log_error("No stores selected", endpoint=ENDPOINT_NAME)
                window.after(0, enable_copy)
                return

            store_map = {}
            for acct in config_accounts:
                name = acct.get("Name", "")
                cid = acct.get("ClientID", "")
                ckey = acct.get("ClientKEY", "")
                if not all([name, cid, ckey]):
                    log(f"Skipping invalid account: {name or 'Unknown'}", "sep")
                    log_error(f"Invalid account: Name={name}, ClientID={cid}", endpoint=ENDPOINT_NAME)
                    continue
                for sid in acct.get("StoreIDs", []):
                    if sid in selected_stores and sid not in store_map:
                        store_map[sid] = (name, cid, ckey)

            if not store_map:
                log("No valid accounts with selected stores found.", "sep")
                log_error("No valid accounts with selected stores", endpoint=ENDPOINT_NAME)
                window.after(0, enable_copy)
                return

            s_str, e_str = start.isoformat(), end.isoformat()
            log(f"Custom Report: {s_str} → {e_str}", "title")
            log(f"Fetching data for {len(store_map)} stores…", "sep")

            log("", None)
            log("Sample Data Summary", "title")
            log("Store  | Value", "heading")
            log("─" * 20, "sep")
            with ThreadPoolExecutor(max_workers=min(config_max_workers, len(selected_stores))) as ex:
                futures = {}
                for sid, (aname, cid, ckey) in store_map.items():
                    fut = ex.submit(fetch_data, ENDPOINT_NAME, sid, s_str, e_str, cid, ckey)
                    futures[fut] = (sid, aname, cid, ckey)
                for fut in as_completed(futures):
                    sid, aname, cid, ckey = futures[fut]
                    try:
                        res = fut.result() or {}
                        log_error(f"API response for store {sid}: {json.dumps(res, indent=2)}", endpoint=ENDPOINT_NAME)
                    except Exception as ex:
                        log_error(f"Fetch failed for store {sid}: {ex}", sid, ENDPOINT_NAME)
                        log(f"❌ Store {sid}: Exception: {ex}", "sep")
                        continue
                    err = res.get("error")
                    if err:
                        if "429" in err.lower() or "rate limit" in err.lower():
                            log(f"⚠️ Store {sid}: Rate limit hit; skipping.", "sep")
                            handle_rate_limit(cid, ckey, window)
                        else:
                            log_error(f"API error for store {sid}: {err}", sid, ENDPOINT_NAME)
                            log(f"❌ Store {sid}: {err}", "sep")
                        continue
                    data = res.get("data", []) or []
                    if isinstance(data, dict):
                        data = [data]
                    if not data:
                        log(f"Store {sid} (Acct: {aname}): No data available.", "sep")
                        log_error(f"No data for store {sid}", sid, ENDPOINT_NAME)
                        continue
                    for rec in data:
                        value = rec.get("total", 0)  # Example field
                        log(f"{sid:>6}  {value:>7}")

            idx = txt.search("Fetching data for ", "1.0", tk.END)
            if idx:
                txt.delete(idx, f"{idx} lineend +1c")
            window.after(0, enable_copy)
        except Exception as ex:
            log_error(f"Worker thread error: {ex}", endpoint=ENDPOINT_NAME)
            log(f"❌ Report error: {ex}", "sep")
            tk.messagebox.showerror("Report Error", f"Failed to generate report: {ex}", parent=window)
            window.after(0, enable_copy)

    threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    run(root)
    root.mainloop()

Available Host Helpers:







Helper



Purpose





fetch_data(ep, sid, start, end, cid, ckey)



Makes API requests with retries.





store_vars



Dictionary of selected stores ({store_id: BooleanVar}).





config_accounts



List of account configs (Name, ClientID, ClientKEY, StoreIDs, Status).





handle_rate_limit(cid, ckey, root)



Handles 429 errors, disables accounts, and saves config.





log_error(msg, sid=None, endpoint=None)



Logs to error.log with UTC timestamp.





config_max_workers



Max threads for ThreadPoolExecutor (default: 8).





flatten_json(obj, parent="", sep=".")



Flattens nested JSON to key-value pairs.





get_selected_start_date()



Returns start date as YYYY-MM-DD.





get_selected_end_date()



Returns end date as YYYY-MM-DD.





config_emails



List of configured email addresses.





config_smtp



SMTP settings (server, port, username, password, from).





_password_validated



Boolean for password validation status.

Common Patterns:







Goal



Snippet





Background thread



threading.Thread(target=worker, daemon=True).start()





Log to UI



log("Message", "tag") (tags: title, heading, sep)





Parallel API calls



with ThreadPoolExecutor(max_workers=config_max_workers) as ex: ...





Export reports



Adapt export_file() from Sales.py or 3rd-Party.py.





Email reports



Use open_email_dialog() from Sales.py or 3rd-Party.py.

Debugging Tips:





Run with --console to view print() output.



Use try/except around API calls and log via log_error.



Import heavy libraries (e.g., reportlab) inside run() for PyInstaller compatibility.



Check error.log for detailed error messages.

LiveIQ Endpoints:







Dropdown Label



fetch_data Value





Sales Summary



Sales Summary





Daily Sales Summary



Daily Sales Summary





Daily Timeclock



Daily Timeclock





Third Party Sales Summary



Third Party Sales Summary





Third Party Transaction Summary



Third Party Transaction Summary





Transaction Summary



Transaction Summary





Transaction Details



Transaction Details



Contributing

Contributions are welcome! To contribute:





Fork the repository and create a feature branch.



Install development dependencies: pip install -r requirements-dev.txt.



Set up pre-commit hooks: pre-commit install.



Follow the Developing Custom Modules guidelines for new reports.



Submit a pull request with:





Clear description of changes.



Screenshots/GIFs for UI changes.



Tests or validation steps for API-related changes.



License

MIT License—use, modify, and distribute freely, but we’re not responsible if your sandwich shop catches fire.



Built for franchisees who want data insights without the ha
