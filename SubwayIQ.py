from __future__ import annotations
import collections
import smtplib
import tkinter as tk
from tkinter import Toplevel, messagebox, ttk, simpledialog
from tkinter import filedialog
from tkinter.scrolledtext import ScrolledText
from tkcalendar import DateEntry
import json
import os
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import glob
import importlib.util
import tempfile
import win32print
import csv
from tenacity import retry, stop_after_attempt, wait_exponential
from PIL import Image, ImageTk
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import socket
from requests.exceptions import HTTPError

# ── Constants ─────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.dat")
LOG_FILE = os.path.join(SCRIPT_DIR, "error.log")
BASE_URL = "https://liveiqfranchiseeapi.subway.com"

ENDPOINTS = {
    "Sales Summary": "/api/SalesSummary/{restaurantNumbers}/startDate/{startDate}/endDate/{endDate}",
    "Daily Sales Summary": "/api/DailySalesSummary/{restaurantNumbers}/startDate/{startDate}/endDate/{endDate}",
    "Daily Timeclock": "/api/DailyTimeclock/{restaurantNumbers}/startDate/{startDate}/endDate/{endDate}",
    "Third Party Sales Summary": "/api/ThirdPartySalesSummary/{restaurantNumbers}/startDate/{startDate}/endDate/{endDate}",
    "Third Party Transaction Summary": "/api/ThirdPartyTransactionSummary/{restaurantNumbers}/startDate/{startDate}/endDate/{endDate}",
    "Transaction Summary": "/api/TransactionSummary/{restaurantNumbers}/startDate/{startDate}/endDate/{endDate}",
    "Transaction Details": "/api/TransactionDetails/{restaurantNumbers}/startDate/{startDate}/endDate/{endDate}",
}

# Default modules shipped with the program
DEFAULT_MODULE_CONTENT = {
    "3rd-Party.py": """# 3rd-Party Module
def run(window):
    pass
""",
    "Transactions.py": """# Transactions Module
def run(window):
    pass
""",
    "Items-Sold.py": """# Items-Sold Module
def run(window):
    pass
""",
    "Discounts.py": """# Discounts Module
def run(window):
    pass
""",
    "Labor.py": """# Labor Module
def run(window):
    pass
""",
    "Sales.py": """# Sales Module
def run(window):
    pass
""",
    "_CUSTOM.py": """# Custom Module
def run(window):
    pass
"""
}

# ── Globals ───────────────────────────────────────────────────────────────
all_stores = set()
store_vars = {}
account_vars = {}
account_store_map = {}
config_accounts = []
config_emails = []
config_smtp = {}
start_entry = None
end_entry = None
config_max_workers = 8
_treeview = None
search_var = None
_account_iids = {}
_fernet = None
_password_validated = False
_module_buttons = []  # Store module buttons for enabling/disabling

# Custom exception for no internet connection
class NoInternetError(Exception):
    pass

# Custom exception for rate limit
class RateLimitError(Exception):
    pass

def check_internet_connection():
    """Check internet connectivity by attempting DNS resolution for google.com."""
    try:
        socket.getaddrinfo("google.com", 80)
        return True
    except socket.gaierror:
        return False

def derive_key(password: str) -> bytes:
    """Derive a Fernet key from the password using PBKDF2HMAC."""
    salt = b'subwayiq_salt'  # Fixed salt for simplicity; in production, store securely
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def encrypt_config(config: dict, password: str) -> bytes:
    """Encrypt the config dictionary and return the ciphertext."""
    fernet = Fernet(derive_key(password))
    return fernet.encrypt(json.dumps(config).encode())

def decrypt_config(ciphertext: bytes, password: str) -> dict:
    """Decrypt the ciphertext and return the config dictionary."""
    try:
        fernet = Fernet(derive_key(password))
        return json.loads(fernet.decrypt(ciphertext).decode())
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")

def save_config():
    """Save the current config using the existing Fernet key."""
    if _fernet is None:
        raise ValueError("Cannot save config without encryption key")
    config = {
        "accounts": config_accounts,
        "max_workers": config_max_workers,
        "emails": config_emails,
        "smtp": config_smtp,
        "selected_accounts": [name for name, var in account_vars.items() if var.get()],
        "selected_stores": [sid for sid, var in store_vars.items() if var.get()]
    }
    ciphertext = _fernet.encrypt(json.dumps(config).encode())
    with open(CONFIG_FILE, "wb") as fh:
        fh.write(ciphertext)

def get_selected_start_date():
    """Return the selected start date as YYYY-MM-DD."""
    return start_entry.get_date().strftime("%Y-%m-%d")

def get_selected_end_date():
    """Return the selected end date as YYYY-MM-DD."""
    return end_entry.get_date().strftime("%Y-%m-%d")

def log_error(msg, sid=None, endpoint=None):
    """Log an error message to error.log with context."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    context = f"[sid={sid or 'N/A'}][{endpoint or 'N/A'}] {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {context}\n")

def handle_rate_limit(cid, ckey, root=None):
    """Set account status to RATE LIMITED, disable, and persist changes."""
    for acct in config_accounts:
        if acct["ClientID"] == cid and acct["ClientKEY"] == ckey:
            if acct["Status"] == "RATE LIMITED":
                return  # Avoid redundant updates
            acct["Status"] = "RATE LIMITED"
            save_config()
            name = acct["Name"]
            if name in account_vars:
                account_vars[name].set(False)
                _treeview.item(_account_iids[name], values=(name, "RATE LIMITED", "☐"), tags=("account", "error"))
                for sid in acct.get("StoreIDs", []):
                    if sid in store_vars:
                        store_vars[sid].set(False)
                        _treeview.item(f"{name}_{sid}", values=(sid.rjust(10), "", "☐"))
            if root is None:
                root = tk._get_default_root()
            messagebox.showwarning(
                "Rate Limit Hit",
                f"Account {name} disabled due to rate limits. Clear via Check Rate Limits.",
                parent=root
            )
            break

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def fetch_data(ep, sid, start, end, cid, ckey):
    """Fetch data from LiveIQ API for a given endpoint, store(s), and date range."""
    if not check_internet_connection():
        raise NoInternetError("No internet connection. Please check your network and try again.")
    path = ENDPOINTS[ep].format(restaurantNumbers=sid, startDate=start, endDate=end)
    try:
        r = requests.get(
            BASE_URL + path,
            headers={"api-client": cid, "api-key": ckey, "Accept": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except HTTPError as exc:
        if exc.response.status_code == 429:
            handle_rate_limit(cid, ckey)
            raise RateLimitError("Rate limit exceeded")
        else:
            log_error(f"Fetch error: {exc}", sid, ep)
            raise
    except Exception as exc:
        log_error(f"Fetch error: {exc}", sid, ep)
        raise

def flatten_json(obj, parent="", sep="."):
    """Flatten a nested JSON object into a key-value dictionary."""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten_json(v, f"{parent}{sep}{k}" if parent else k, sep))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten_json(v, f"{parent}[{i}]", sep))
    else:
        out[parent] = obj
    return out

def validate_credentials(cid: str, ckey: str, accounts: List[Dict], current_name: str = None) -> tuple[bool, str]:
    """Check if ClientID/ClientKEY pair is unique and valid via API ping."""
    # Check for duplicate ClientID/ClientKEY pair
    for acct in accounts:
        if acct["Name"] != current_name and acct["ClientID"] == cid and acct["ClientKEY"] == ckey:
            return False, "Client ID and Client Key pair already used in another account."

    # Ping the API to validate credentials
    if not check_internet_connection():
        return False, "No internet connection. Please check your network and try again."
    try:
        res = requests.get(
            BASE_URL + "/api/Restaurants",
            headers={"api-client": cid, "api-key": ckey, "Accept": "application/json"},
            timeout=10,
        )
        if res.status_code == 429:  # Rate limit is considered valid
            return True, ""
        res.raise_for_status()
        return True, ""
    except requests.exceptions.RequestException as exc:
        log_error(f"Credential validation failed: {exc}", endpoint="validate_credentials")
        return False, f"Invalid credentials: {exc}"

def load_config_and_stores(root, password: str):
    """Load or create config.dat, decrypting it with the provided password. Set PENDING if no status."""
    global config_accounts, config_max_workers, _fernet, _password_validated, all_stores, account_vars, store_vars, account_store_map, config_emails, config_smtp
    default_cfg = {
        "accounts": [],
        "max_workers": 8,
        "emails": [],
        "smtp": {}
    }

    if not os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, "wb") as fh:
            fh.write(encrypt_config(default_cfg, password))
        messagebox.showinfo(
            "Config Created",
            f"A starter {os.path.basename(CONFIG_FILE)} has been created. Please add accounts using the Manage Accounts dialog.",
            parent=root
        )

    try:
        with open(CONFIG_FILE, "rb") as fh:
            ciphertext = fh.read()
        cfg = decrypt_config(ciphertext, password)
        _fernet = Fernet(derive_key(password))
        _password_validated = True
    except Exception as exc:
        log_error(f"Failed to decrypt config: {exc}", endpoint="load_config")
        messagebox.showerror("Config Error", "Invalid password or corrupted config file.", parent=root)
        root.destroy()
        raise SystemExit

    config_max_workers = cfg.get("max_workers", 8)
    config_emails = cfg.get("emails", [])
    config_smtp = cfg.get("smtp", {})

    # Clear existing global variables
    all_stores.clear()
    account_vars.clear()
    store_vars.clear()
    account_store_map.clear()
    config_accounts.clear()

    for acct in cfg.get("accounts", []):
        if not all(k in acct for k in ["Name", "ClientID", "ClientKEY"]):
            log_error("Malformed account entry: missing Name, ClientID, or ClientKEY", endpoint="load_config")
            acct["Status"] = "ERROR"
            continue
        name = acct["Name"]
        cid = acct["ClientID"]
        ckey = acct["ClientKEY"]
        if not cid or not ckey:
            log_error(f"Account {name}: Empty ClientID or ClientKEY", endpoint="load_config")
            acct["Status"] = "ERROR"
            continue
        acct["Status"] = acct.get("Status", "PENDING")
        acct["StoreIDs"] = acct.get("StoreIDs", [])
        account_store_map[name] = acct["StoreIDs"]
        all_stores.update(acct["StoreIDs"])
    config_accounts[:] = cfg.get("accounts", [])

    selected_accounts = cfg.get("selected_accounts", None)
    selected_stores = cfg.get("selected_stores", None)

    # Update account_vars and store_vars
    for acct in config_accounts:
        name = acct["Name"]
        status_ok = acct["Status"] == "OK"
        if selected_accounts is None:
            value = status_ok
        else:
            value = status_ok and name in selected_accounts
        account_vars[name] = tk.BooleanVar(root, value=value)
    for sid in sorted(all_stores, key=int):
        if selected_stores is None:
            value = True
        else:
            value = sid in selected_stores
        store_vars[sid] = tk.BooleanVar(root, value=value)

    return cfg.get("accounts", [])

def load_external_modules(root, disable_buttons: bool = False):
    """Load external modules from modules/ and create buttons for them."""
    global _module_buttons
    _module_buttons.clear()  # Clear previous module buttons
    mod_dir = os.path.join(SCRIPT_DIR, "modules")
    os.makedirs(mod_dir, exist_ok=True)
    frame = tk.Frame(root)
    frame.grid(row=2, column=0, columnspan=3, pady=10, padx=10, sticky="ew")
    frame.grid_columnconfigure((0,1,2,3,4), weight=1)
    tk.Label(frame, text="Modules", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=5, pady=5)
    row = 1
    col = 0
    for path in glob.glob(os.path.join(mod_dir, "*.py")):
        base = os.path.splitext(os.path.basename(path))[0]
        if base == "_CUSTOM":
            continue
        display_name = ' '.join(w.capitalize() for w in base.replace('-', ' ').split())

        def _cb(p=path, n=display_name):
            def _():
                if not check_internet_connection():
                    messagebox.showerror("No Internet", "No internet connection. Please check your network and try again.", parent=root)
                    return
                win = Toplevel(root)
                win.title(n.capitalize())
                win.update_idletasks()  # Ensure dimensions are calculated
                win_width = int(root.winfo_screenwidth() * 0.6)
                win_height = int(root.winfo_screenheight() * 0.6)
                x = (root.winfo_screenwidth() - win_width) // 2
                y = (root.winfo_screenheight() - win_height) // 2
                win.geometry(f"{win_width}x{win_height}+{x}+{y}")
                win.resizable(True, True)
                spec = importlib.util.spec_from_file_location(n.replace(' ', '-'), p)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                for sym in ("fetch_data", "store_vars", "config_accounts",
                            "get_selected_start_date", "get_selected_end_date",
                            "handle_rate_limit", "log_error", "_password_validated",
                            "config_emails", "config_smtp"):
                    setattr(mod, sym, globals()[sym])
                if hasattr(mod, "run") and callable(mod.run):
                    mod.run(win)
                else:
                    tk.Label(win, text=f"{n} lacks a run(window) entry point", fg="red").pack(pady=40)
            return _
        btn = tk.Button(frame, text=display_name, command=_cb(), font=("Arial", 10),
                        bg="#005228", fg="#ecc10c", width=15)
        btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
        if disable_buttons:
            btn.config(state="disabled")
        _module_buttons.append(btn)  # Store the button for state updates
        col += 1
        if col == 5:
            col = 0
            row += 1

def open_view_window(endpoint, stores, start, end, root):
    """Open a window to display raw API data for selected stores and endpoint."""
    if not _password_validated:
        messagebox.showerror("Access Denied", "Password validation required.", parent=root)
        return
    if not check_internet_connection():
        messagebox.showerror("No Internet", "No internet connection. Please check your network and try again.", parent=root)
        return
    win = Toplevel(root)
    win.title(f"View – {endpoint}")
    win.geometry(f"{int(root.winfo_screenwidth()*0.6)}x{int(root.winfo_screenheight()*0.6)}")
    win.resizable(True, True)
    toolbar = tk.Frame(win)
    toolbar.pack(fill="x", pady=4)
    flat_var = tk.BooleanVar(value=False)
    tk.Checkbutton(toolbar, text="Flatten", variable=flat_var).pack(side="left", padx=6)
    copy_btn = tk.Button(toolbar, text="Copy", state=tk.DISABLED)
    copy_btn.pack(side="right", padx=6)
    txt = ScrolledText(win, wrap="word", font=("Consolas", 10))
    txt.pack(expand=True, fill="both", padx=10, pady=10)
    progress = ttk.Progressbar(win, mode="determinate", maximum=len(stores))
    progress.pack(fill="x", padx=10)
    fetched_payloads = []

    def render():
        txt.delete("1.0", "end")
        def write(line=""):
            txt.insert("end", line + "\n")
        write(f"Endpoint: {endpoint}")
        write(f"Range   : {start} → {end}")
        write(f"Stores  : {', '.join(stores)}\n")
        for aname, sid, res in fetched_payloads:
            write(f"\n### {aname} ({sid}) ###")
            if "error" in res:
                write(f"ERROR: {res['error']}")
                continue
            payload = res.get("data", res)
            if flat_var.get():
                iterable = payload if isinstance(payload, list) else [payload]
                for idx, entry in enumerate(iterable, 1):
                    write(f"— Entry {idx} —")
                    for k, v in flatten_json(entry).items():
                        write(f"{k:40} : {v}")
            else:
                write(json.dumps(payload, indent=2, ensure_ascii=False))

    flat_var.trace_add("write", lambda *args: render())

    try:
        futures = {}
        with ThreadPoolExecutor(max_workers=min(config_max_workers, len(stores))) as ex:
            fetched_ids = set()
            for acct in config_accounts:
                cid, ckey, aname = acct["ClientID"], acct["ClientKEY"], acct["Name"]
                for sid in acct.get("StoreIDs", []):
                    if sid in stores and sid not in fetched_ids:
                        futures[ex.submit(fetch_data, endpoint, sid, start, end, cid, ckey)] = (aname, sid)
                        fetched_ids.add(sid)
            for fut in as_completed(futures):
                aname, sid = futures[fut]
                try:
                    res = fut.result()
                except NoInternetError as exc:
                    log_error(f"No internet connection for store {sid}: {exc}", sid, endpoint)
                    messagebox.showerror("No Internet", str(exc), parent=win)
                    win.destroy()
                    return
                except RateLimitError as exc:
                    log_error(f"Rate limit for store {sid}: {exc}", sid, endpoint)
                    res = {"error": str(exc)}
                except Exception as exc:
                    log_error(f"Fetch failed for store {sid}: {exc}", sid, endpoint)
                    res = {"error": str(exc)}
                fetched_payloads.append((aname, sid, res))
                progress.step()
                progress.update()
    except Exception as exc:
        log_error(f"Error in open_view_window: {exc}", endpoint=endpoint)
        messagebox.showerror("Error", f"Failed to fetch data: {exc}", parent=win)
        win.destroy()
        return

    render()
    progress.destroy()

    def print_content():
        data = txt.get("1.0", "end-1c")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as tf:
            tf.write(data)
            tmpname = tf.name
        try:
            printer_name = win32print.GetDefaultPrinter()
            hPrinter = win32print.OpenPrinter(printer_name)
            hJob = win32print.StartDocPrinter(hPrinter, 1, ("LiveIQ Report", None, "RAW"))
            win32print.StartPagePrinter(hPrinter)
            with open(tmpname, "rb") as f:
                win32print.WritePrinter(hPrinter, f.read())
            win32print.EndPagePrinter(hPrinter)
            win32print.EndDocPrinter(hPrinter)
            win32print.ClosePrinter(hPrinter)
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to print: {e}", parent=win)
        finally:
            if os.path.exists(tmpname):
                os.unlink(tmpname)

    def export_csv():
        data = txt.get("1.0", "end-1c").splitlines()
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save CSV Report",
            initialfile=f"api_viewer_{endpoint.lower().replace(' ', '_')}_{datetime.now():%Y%m%d}.csv",
            parent=win
        )
        if not filename:
            return
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for line in data:
                    writer.writerow(line.split())
            messagebox.showinfo("Export", f"Report exported to {filename}.", parent=win)
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV: {e}", parent=win)

    tk.Button(toolbar, text="Print", command=print_content, bg="#005228", fg="#ecc10c").pack(side="right", padx=6)
    tk.Button(toolbar, text="Export CSV", command=export_csv, bg="#005228", fg="#ecc10c").pack(side="right", padx=6)
    copy_btn.config(state=tk.NORMAL, command=lambda: win.clipboard_append(txt.get("1.0", "end-1c")))

def update_dates(option, start_e, end_e):
    """Update date entries based on preset selection."""
    today = datetime.now().date()
    if option == "Custom":
        return
    if option == "Today":
        start = end = today
    elif option == "Yesterday":
        start = end = today - timedelta(days=1)
    elif option.startswith("Past"):
        days = int(option.split()[1])
        end = today - timedelta(days=1)
        start = end - timedelta(days=days - 1)
    else:
        return
    start_e.set_date(start)
    end_e.set_date(end)

def check_date_preset(start_e, end_e, range_var):
    """Check if selected dates match a preset and update the dropdown."""
    today = datetime.now().date()
    start = start_e.get_date()
    end = end_e.get_date()
    
    if start == end == today:
        range_var.set("Today")
    elif start == end == today - timedelta(days=1):
        range_var.set("Yesterday")
    elif end == today - timedelta(days=1):
        days = (end - start).days + 1
        if days in (2, 3, 7, 14, 30):
            range_var.set(f"Past {days} Days")
        else:
            range_var.set("Custom")
    else:
        range_var.set("Custom")

def update_treeview():
    """Update the Treeview based on search and selection state."""
    if _treeview is None:
        return
    _treeview.delete(*_treeview.get_children())
    _account_iids.clear()  # Clear existing account IDs to prevent duplicates
    search = search_var.get().lower() if search_var else ""
    for acct in config_accounts:
        name = acct["Name"]
        status = acct["Status"]
        if search in name.lower() or any(search in sid for sid in acct.get("StoreIDs", [])):
            tag = "account" if status == "OK" else ("account", "error")
            select = "☑" if account_vars.get(name, tk.BooleanVar(value=False)).get() else "☐"
            iid = _treeview.insert("", "end", values=(name, status, select), tags=tag)
            _account_iids[name] = iid
            if status == "OK":
                for sid in sorted(acct.get("StoreIDs", []), key=int):
                    if search in sid or search in name.lower():
                        store_iid = f"{name}_{sid}"  # Prefix store ID with account name
                        select = "☑" if store_vars.get(sid, tk.BooleanVar(value=False)).get() else "☐"
                        _treeview.insert(iid, "end", iid=store_iid, values=(sid.rjust(10), "", select))
                _treeview.item(iid, open=True)
    _treeview.bind("<Button-1>", handle_tree_click)

def select_all():
    """Select all accounts and stores, preserving expanded state."""
    expanded_accounts = {name: _treeview.item(_account_iids[name], "open") for name in _account_iids if _treeview.item(_account_iids[name], "open") is not None}
    for acct in config_accounts:
        name = acct["Name"]
        if acct["Status"] == "OK":
            account_vars[name].set(True)
            for sid in account_store_map.get(name, []):
                if sid in store_vars:
                    store_vars[sid].set(True)
    update_treeview()
    save_config()
    for name, is_open in expanded_accounts.items():
        if name in _account_iids:
            _treeview.item(_account_iids[name], open=is_open)

def unselect_all():
    """Unselect all accounts and stores, preserving expanded state."""
    expanded_accounts = {name: _treeview.item(_account_iids[name], "open") for name in _account_iids if _treeview.item(_account_iids[name], "open") is not None}
    for v in account_vars.values():
        v.set(False)
    for v in store_vars.values():
        v.set(False)
    update_treeview()
    save_config()
    for name, is_open in expanded_accounts.items():
        if name in _account_iids:
            _treeview.item(_account_iids[name], open=is_open)

def handle_tree_click(event):
    """Handle clicks on the Treeview to toggle selections."""
    region = _treeview.identify("region", event.x, event.y)
    if region != "cell":
        return
    column = _treeview.identify_column(event.x)
    if column != "#3":
        return
    iid = _treeview.identify_row(event.y)
    if not iid:
        return
    item_values = _treeview.item(iid, "values")
    if not item_values:
        return
    if iid in _account_iids.values():
        name = next(n for n, i in _account_iids.items() if i == iid)
        if next((a["Status"] for a in config_accounts if a["Name"] == name), "ERROR") != "OK":
            return
        new_state = not account_vars[name].get()
        account_vars[name].set(new_state)
        _treeview.item(iid, values=(item_values[0], item_values[1], "☑" if new_state else "☐"))
        for sid in account_store_map.get(name, []):
            if sid in store_vars:
                store_vars[sid].set(new_state)
                _treeview.item(f"{name}_{sid}", values=(sid.rjust(10), "", "☑" if new_state else "☐"))
    else:
        sid = item_values[0].strip()  # The displayed store ID
        if sid in store_vars:
            new_state = not store_vars[sid].get()
            store_vars[sid].set(new_state)
            parent_iid = _treeview.parent(iid)
            if parent_iid and parent_iid in _account_iids.values():
                parent_name = next(n for n, i in _account_iids.items() if i == parent_iid)
                if not account_vars[parent_name].get() and new_state:
                    account_vars[parent_name].set(True)
                    parent_status = next(a["Status"] for a in config_accounts if a["Name"] == parent_name)
                    _treeview.item(parent_iid, values=(parent_name, parent_status, "☑"))
            _treeview.item(iid, values=(sid.rjust(10), "", "☑" if new_state else "☐"))
    save_config()

def check_rate_limits(root):
    """Verify all accounts, update Status/StoreIDs, and refresh UI."""
    if not _password_validated:
        messagebox.showerror("Access Denied", "Password validation required.", parent=root)
        return
    if not check_internet_connection():
        messagebox.showerror("No Internet", "No internet connection. Please check your network and try again.", parent=root)
        return
    for acct in config_accounts:
        name = acct["Name"]
        cid = acct["ClientID"]
        ckey = acct["ClientKEY"]
        try:
            res = requests.get(
                BASE_URL + "/api/Restaurants",
                headers={"api-client": cid, "api-key": ckey, "Accept": "application/json"},
                timeout=10,
            )
            if res.status_code == 429:
                acct["Status"] = "RATE LIMITED"
            else:
                res.raise_for_status()
                stores = [r.get("restaurantNumber", "") for r in res.json() if "restaurantNumber" in r]
                acct["StoreIDs"] = stores
                acct["Status"] = "OK" if stores else "EMPTY"
        except requests.exceptions.RequestException as exc:
            if exc.response and exc.response.status_code == 429:
                acct["Status"] = "RATE LIMITED"
            else:
                acct["Status"] = "ERROR"
            log_error(f"Check failed for {name}: {exc}", endpoint="check_rate_limits")
    save_config()
    # Rebuild globals with updated stores
    all_stores.clear()
    account_store_map.clear()
    account_vars.clear()
    store_vars.clear()
    for acct in config_accounts:
        name = acct["Name"]
        account_store_map[name] = acct.get("StoreIDs", [])
        all_stores.update(acct["StoreIDs"])
        account_vars[name] = tk.BooleanVar(root, value=acct["Status"] == "OK")
    for sid in sorted(all_stores, key=int):
        store_vars[sid] = tk.BooleanVar(root, value=True)
    update_treeview()
    update_button_states()

def reset_config(root):
    """Reset config file to default, backing up the existing one with a timestamp."""
    password = simpledialog.askstring("Password", "Enter password to reset config:", parent=root, show="*")
    if not password:
        messagebox.showwarning("Password Required", "Password is required to reset the config.", parent=root)
        return

    try:
        with open(CONFIG_FILE, "rb") as fh:
            ciphertext = fh.read()
        decrypt_config(ciphertext, password)  # Validate password
    except Exception as exc:
        log_error(f"Failed to decrypt config for reset: {exc}", endpoint="reset_config")
        messagebox.showerror("Invalid Password", "Invalid password for config decryption.", parent=root)
        return

    if not messagebox.askyesno("Confirm Reset", "This will overwrite the current config.dat with a default version and back up the existing file. Proceed?", parent=root):
        return
    if os.path.isfile(CONFIG_FILE):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{CONFIG_FILE}.{timestamp}.bak"
        os.rename(CONFIG_FILE, backup_file)
        log_error(f"Backed up existing config to {backup_file}")
    default_cfg = {
        "accounts": [],
        "max_workers": 8,
        "emails": [],
        "smtp": {}
    }
    with open(CONFIG_FILE, "wb") as fh:
        fh.write(encrypt_config(default_cfg, password))
    messagebox.showinfo("Config Reset", f"Config reset to default. Backup saved as {backup_file}.", parent=root)
    load_config_and_stores(root, password)
    update_treeview()
    update_button_states()

def reset_modules(root):
    """Reset modules to default set and remove others, downloading from GitHub if online."""
    if not _password_validated:
        messagebox.showerror("Access Denied", "Password validation required.", parent=root)
        return
    if not messagebox.askyesno("Confirm Reset", "This will reset modules to the default set and remove any others. Proceed?", parent=root):
        return
    mod_dir = os.path.join(SCRIPT_DIR, "modules")
    os.makedirs(mod_dir, exist_ok=True)
    current_files = set(os.listdir(mod_dir))
    default_modules = {"3rd-Party.py", "Transactions.py", "Items-Sold.py", "Discounts.py", "Labor.py", "Sales.py", "_CUSTOM.py"}
    deleted_files = []
    failed_deletions = []
    
    # Remove non-default .py files
    for file in current_files:
        if file.endswith(".py") and file not in default_modules:
            try:
                file_path = os.path.join(mod_dir, file)
                # Ensure file is writable before deletion
                os.chmod(file_path, 0o666)  # Set permissions to allow deletion
                os.remove(file_path)
                deleted_files.append(file)
                log_error(f"Removed non-default module: {file}")
            except Exception as e:
                failed_deletions.append(file)
                log_error(f"Failed to remove module {file}: {e}")

    # Report deletion status
    if failed_deletions:
        messagebox.showwarning("Deletion Warning", f"Failed to delete some non-default modules: {', '.join(failed_deletions)}. Continuing with downloads.", parent=root)

    # Attempt GitHub download if online
    if check_internet_connection():
        failed_downloads = []
        successful_downloads = []
        try:
            github_base = "https://raw.githubusercontent.com/alex85/subwayiq/main/modules/"
            for mod_name in default_modules:
                url = github_base + mod_name
                try:
                    res = requests.get(url, timeout=5)
                    res.raise_for_status()  # Raise exception for non-200 status codes
                    content = res.text
                    # Verify content is not empty and looks like Python code
                    if not content.strip():
                        raise ValueError("Downloaded content is empty")
                    if not content.startswith("#") and not content.startswith("import") and not content.startswith("from"):
                        raise ValueError("Downloaded content does not appear to be valid Python code")
                    mod_path = os.path.join(mod_dir, mod_name)
                    # Ensure file is writable
                    if os.path.exists(mod_path):
                        os.chmod(mod_path, 0o666)
                    with open(mod_path, "w", encoding="utf-8") as fh:
                        fh.write(content)
                    successful_downloads.append(mod_name)
                    log_error(f"Downloaded and restored module from GitHub: {mod_name}")
                    time.sleep(2)  # Sleep for 2 seconds between downloads
                except Exception as e:
                    failed_downloads.append(mod_name)
                    log_error(f"Failed to download module {mod_name}: {e} (HTTP Status: {res.status_code if 'res' in locals() else 'N/A'})")
            
            # Report download status
            if failed_downloads:
                messagebox.showerror("Reset Error", f"Failed to download modules from GitHub: {', '.join(failed_downloads)}. Successfully downloaded: {', '.join(successful_downloads) if successful_downloads else 'none'}. Modules partially reset.", parent=root)
            else:
                messagebox.showinfo("Modules Reset", f"Modules reset to latest defaults from GitHub. Successfully downloaded: {', '.join(successful_downloads)}.", parent=root)
        except Exception as e:
            log_error(f"GitHub download failed: {e}")
            messagebox.showerror("Reset Error", f"Failed to download modules from GitHub: {e}. Successfully downloaded: {', '.join(successful_downloads) if successful_downloads else 'none'}. Modules partially reset.", parent=root)
    else:
        messagebox.showerror("No Internet", "No internet connection. Cannot download modules from GitHub.", parent=root)

    # Reload modules
    load_external_modules(root)

def validate_and_view(endpoint, stores, start, end, root):
    """Validate dates and open a window to display raw API data."""
    if not _password_validated:
        messagebox.showerror("Access Denied", "Password validation required.", parent=root)
        return
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end, "%Y-%m-%d").date()
        if end_dt < start_dt:
            messagebox.showerror("Invalid Date Range", "End date cannot be before start date.", parent=root)
            return
        open_view_window(endpoint, stores, start, end, root)
    except ValueError:
        messagebox.showerror("Invalid Date", "Please enter valid dates.", parent=root)

def update_button_states():
    """Update the state of buttons and controls based on the number of accounts."""
    has_valid_accounts = any(acct.get("Status") == "OK" for acct in config_accounts)
    state = "normal" if has_valid_accounts else "disabled"
    preset_menu.config(state=state)
    start_entry.config(state=state)
    end_entry.config(state=state)
    endpoint_menu.config(state=state)
    view_btn.config(state=state)
    search_entry.config(state=state)
    select_all_btn.config(state=state)
    unselect_all_btn.config(state=state)
    check_rate_btn.config(state=state)
    reset_modules_btn.config(state=state)
    for btn in _module_buttons:
        btn.config(state=state)

def manage_accounts(root, password: str):
    """Open a dialog to manage accounts (add/edit/delete)."""
    if not check_internet_connection():
        messagebox.showerror("No Internet", "No internet connection. Please check your network and try again.", parent=root)
        return
    try:
        with open(CONFIG_FILE, "rb") as fh:
            ciphertext = fh.read()
        cfg = decrypt_config(ciphertext, password)
    except Exception as exc:
        log_error(f"Failed to decrypt config for account management: {exc}", endpoint="manage_accounts")
        messagebox.showerror("Invalid Password", "Invalid password for config decryption.", parent=root)
        return

    win = Toplevel(root)
    win.title("Manage Accounts")
    win_width, win_height = 400, 300
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - win_width) // 2
    y = (screen_height - win_height) // 2
    win.geometry(f"{win_width}x{win_height}+{x}+{y}")
    win.resizable(False, False)
    win.transient(root)
    win.grab_set()

    tk.Label(win, text="Manage Accounts", font=("Arial", 12, "bold")).pack(pady=5)
    listbox = tk.Listbox(win, height=10)
    listbox.pack(fill="both", expand=True, padx=10, pady=5)

    accounts = cfg.get("accounts", [])
    for acct in accounts:
        listbox.insert(tk.END, acct["Name"])

    def add_account():
        if not check_internet_connection():
            messagebox.showerror("No Internet", "No internet connection. Please check your network and try again.", parent=win)
            return
        name_dialog = Toplevel(win)
        name_dialog.title("Add Account")
        name_dialog.geometry("350x250")
        x = (screen_width - 350) // 2
        y = (screen_height - 250) // 2
        name_dialog.geometry(f"350x250+{x}+{y}")
        name_dialog.resizable(False, False)
        tk.Label(name_dialog, text="Account Name:").pack(pady=5)
        name_entry = tk.Entry(name_dialog)
        name_entry.pack(pady=5)
        name_entry.focus_set()
        tk.Label(name_dialog, text="Client ID:").pack(pady=5)
        cid_entry = tk.Entry(name_dialog)
        cid_entry.pack(pady=5)
        tk.Label(name_dialog, text="Client Key:").pack(pady=5)
        ckey_entry = tk.Entry(name_dialog, show="*")
        ckey_entry.pack(pady=5)
        
        def submit(event=None):
            name = name_entry.get().strip()
            cid = cid_entry.get().strip()
            ckey = ckey_entry.get().strip()
            if not (name and cid and ckey):
                messagebox.showerror("Invalid Input", "All fields are required.", parent=name_dialog)
                return
            is_valid, error_msg = validate_credentials(cid, ckey, accounts)
            if not is_valid:
                messagebox.showerror("Invalid Credentials", error_msg, parent=name_dialog)
                return
            try:
                res = requests.get(
                    BASE_URL + "/api/Restaurants",
                    headers={"api-client": cid, "api-key": ckey, "Accept": "application/json"},
                    timeout=10,
                )
                if res.status_code == 429:
                    messagebox.showerror("Rate Limited", "Account is rate limited. Try later.", parent=name_dialog)
                    return
                res.raise_for_status()
                stores = [r.get("restaurantNumber", "") for r in res.json() if "restaurantNumber" in r]
                status = "OK" if stores else "EMPTY"
            except Exception as exc:
                messagebox.showerror("Fetch Error", f"Failed to fetch stores: {exc}", parent=name_dialog)
                return
            accounts.append({"Name": name, "ClientID": cid, "ClientKEY": ckey, "StoreIDs": stores, "Status": status})
            listbox.insert(tk.END, name)
            ciphertext = encrypt_config(cfg, password)
            with open(CONFIG_FILE, "wb") as fh:
                fh.write(ciphertext)
            messagebox.showinfo("Success", "Account added.", parent=win)
            load_config_and_stores(root, password)
            update_treeview()
            update_button_states()
            name_dialog.destroy()
        
        btn_frame = tk.Frame(name_dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Submit", command=submit, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=name_dialog.destroy, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        name_dialog.bind("<Return>", submit)
        name_dialog.transient(win)
        name_dialog.grab_set()

    def edit_account():
        if not check_internet_connection():
            messagebox.showerror("No Internet", "No internet connection. Please check your network and try again.", parent=win)
            return
        sel = listbox.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an account to edit.", parent=win)
            return
        idx = sel[0]
        acct = accounts[idx]
        edit_dialog = Toplevel(win)
        edit_dialog.title("Edit Account")
        edit_dialog.geometry("350x250")
        x = (screen_width - 350) // 2
        y = (screen_height - 250) // 2
        edit_dialog.geometry(f"350x250+{x}+{y}")
        edit_dialog.resizable(False, False)
        tk.Label(edit_dialog, text="Account Name:").pack(pady=5)
        name_entry = tk.Entry(edit_dialog)
        name_entry.insert(0, acct["Name"])
        name_entry.pack(pady=5)
        name_entry.focus_set()
        tk.Label(edit_dialog, text="Client ID:").pack(pady=5)
        cid_entry = tk.Entry(edit_dialog)
        cid_entry.insert(0, acct["ClientID"])
        cid_entry.pack(pady=5)
        tk.Label(edit_dialog, text="Client Key:").pack(pady=5)
        ckey_entry = tk.Entry(edit_dialog, show="*")
        ckey_entry.insert(0, acct["ClientKEY"])
        ckey_entry.pack(pady=5)
        
        def submit(event=None):
            name = name_entry.get().strip()
            cid = cid_entry.get().strip()
            ckey = ckey_entry.get().strip()
            if not (name and cid and ckey):
                messagebox.showerror("Invalid Input", "All fields are required.", parent=edit_dialog)
                return
            is_valid, error_msg = validate_credentials(cid, ckey, accounts, current_name=acct["Name"])
            if not is_valid:
                messagebox.showerror("Invalid Credentials", error_msg, parent=edit_dialog)
                return
            try:
                res = requests.get(
                    BASE_URL + "/api/Restaurants",
                    headers={"api-client": cid, "api-key": ckey, "Accept": "application/json"},
                    timeout=10,
                )
                if res.status_code == 429:
                    messagebox.showerror("Rate Limited", "Account is rate limited. Try later.", parent=edit_dialog)
                    return
                res.raise_for_status()
                stores = [r.get("restaurantNumber", "") for r in res.json() if "restaurantNumber" in r]
                status = "OK" if stores else "EMPTY"
            except Exception as exc:
                messagebox.showerror("Fetch Error", f"Failed to fetch stores: {exc}", parent=edit_dialog)
                return
            accounts[idx] = {"Name": name, "ClientID": cid, "ClientKEY": ckey, "StoreIDs": stores, "Status": status}
            listbox.delete(idx)
            listbox.insert(idx, name)
            ciphertext = encrypt_config(cfg, password)
            with open(CONFIG_FILE, "wb") as fh:
                fh.write(ciphertext)
            messagebox.showinfo("Success", "Account updated.", parent=win)
            load_config_and_stores(root, password)
            update_treeview()
            update_button_states()
            edit_dialog.destroy()
        
        btn_frame = tk.Frame(edit_dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Submit", command=submit, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=edit_dialog.destroy, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        edit_dialog.bind("<Return>", submit)
        edit_dialog.transient(win)
        edit_dialog.grab_set()

    def delete_account():
        sel = listbox.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an account to delete.", parent=win)
            return
        idx = sel[0]
        if messagebox.askyesno("Confirm Delete", f"Delete account {accounts[idx]['Name']}?", parent=win):
            accounts.pop(idx)
            listbox.delete(idx)
            ciphertext = encrypt_config(cfg, password)
            with open(CONFIG_FILE, "wb") as fh:
                fh.write(ciphertext)
            messagebox.showinfo("Success", "Account deleted.", parent=win)
            load_config_and_stores(root, password)
            update_treeview()
            update_button_states()

    btn_frame = tk.Frame(win)
    btn_frame.pack(fill="x", pady=5)
    tk.Button(btn_frame, text="Add", command=add_account, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    tk.Button(btn_frame, text="Edit", command=edit_account, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    tk.Button(btn_frame, text="Delete", command=delete_account, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    tk.Button(btn_frame, text="Close", command=lambda: [win.destroy(), root.focus_force()], bg="#005228", fg="#ecc10c").pack(side="right", padx=5)
    win.transient(root)
    win.grab_set()

def manage_emails(root, password: str):
    """Open a dialog to manage emails."""
    if not check_internet_connection():
        messagebox.showerror("No Internet", "No internet connection. Please check your network and try again.", parent=root)
        return
    try:
        with open(CONFIG_FILE, "rb") as fh:
            ciphertext = fh.read()
        cfg = decrypt_config(ciphertext, password)
    except Exception as exc:
        log_error(f"Failed to decrypt config for email management: {exc}", endpoint="manage_emails")
        messagebox.showerror("Invalid Password", "Invalid password for config decryption.", parent=root)
        return

    win = Toplevel(root)
    win.title("Manage Emails")
    win_width, win_height = 400, 300
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - win_width) // 2
    y = (screen_height - win_height) // 2
    win.geometry(f"{win_width}x{win_height}+{x}+{y}")
    win.resizable(False, False)
    win.transient(root)
    win.grab_set()

    tk.Label(win, text="Manage Emails", font=("Arial", 12, "bold")).pack(pady=5)
    listbox = tk.Listbox(win, height=10)
    listbox.pack(fill="both", expand=True, padx=10, pady=5)

    emails = cfg.get("emails", [])
    for email in emails:
        listbox.insert(tk.END, email)

    def add_email():
        email_dialog = Toplevel(win)
        email_dialog.title("Add Email")
        email_dialog.geometry("350x150")
        x = (screen_width - 350) // 2
        y = (screen_height - 150) // 2
        email_dialog.geometry(f"350x150+{x}+{y}")
        email_dialog.resizable(False, False)
        tk.Label(email_dialog, text="Email Address:").pack(pady=5)
        email_entry = tk.Entry(email_dialog)
        email_entry.pack(pady=5)
        email_entry.focus_set()
        
        def submit(event=None):
            email = email_entry.get().strip()
            if not email:
                messagebox.showerror("Invalid Input", "Email is required.", parent=email_dialog)
                return
            if email in emails:
                messagebox.showerror("Duplicate", "Email already exists.", parent=email_dialog)
                return
            emails.append(email)
            listbox.insert(tk.END, email)
            ciphertext = encrypt_config(cfg, password)
            with open(CONFIG_FILE, "wb") as fh:
                fh.write(ciphertext)
            messagebox.showinfo("Success", "Email added.", parent=win)
            email_dialog.destroy()
        
        btn_frame = tk.Frame(email_dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Submit", command=submit, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=email_dialog.destroy, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        email_dialog.bind("<Return>", submit)
        email_dialog.transient(win)
        email_dialog.grab_set()

    def edit_email():
        sel = listbox.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an email to edit.", parent=win)
            return
        idx = sel[0]
        old_email = emails[idx]
        email_dialog = Toplevel(win)
        email_dialog.title("Edit Email")
        email_dialog.geometry("350x150")
        x = (screen_width - 350) // 2
        y = (screen_height - 150) // 2
        email_dialog.geometry(f"350x150+{x}+{y}")
        email_dialog.resizable(False, False)
        tk.Label(email_dialog, text="Email Address:").pack(pady=5)
        email_entry = tk.Entry(email_dialog)
        email_entry.insert(0, old_email)
        email_entry.pack(pady=5)
        email_entry.focus_set()
        
        def submit(event=None):
            email = email_entry.get().strip()
            if not email:
                messagebox.showerror("Invalid Input", "Email is required.", parent=email_dialog)
                return
            if email in emails and email != old_email:
                messagebox.showerror("Duplicate", "Email already exists.", parent=email_dialog)
                return
            emails[idx] = email
            listbox.delete(idx)
            listbox.insert(idx, email)
            ciphertext = encrypt_config(cfg, password)
            with open(CONFIG_FILE, "wb") as fh:
                fh.write(ciphertext)
            messagebox.showinfo("Success", "Email updated.", parent=win)
            email_dialog.destroy()
        
        btn_frame = tk.Frame(email_dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Submit", command=submit, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=email_dialog.destroy, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        email_dialog.bind("<Return>", submit)
        email_dialog.transient(win)
        email_dialog.grab_set()

    def delete_email():
        sel = listbox.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an email to delete.", parent=win)
            return
        idx = sel[0]
        if messagebox.askyesno("Confirm Delete", f"Delete email {emails[idx]}?", parent=win):
            emails.pop(idx)
            listbox.delete(idx)
            ciphertext = encrypt_config(cfg, password)
            with open(CONFIG_FILE, "wb") as fh:
                fh.write(ciphertext)
            messagebox.showinfo("Success", "Email deleted.", parent=win)

    def smtp_settings():
        smtp = cfg.get("smtp", {})
        smtp_dialog = Toplevel(win)
        smtp_dialog.title("SMTP Settings")
        smtp_dialog.geometry("350x400")
        x = (screen_width - 350) // 2
        y = (screen_height - 400) // 2
        smtp_dialog.geometry(f"350x400+{x}+{y}")
        smtp_dialog.resizable(False, False)
        tk.Label(smtp_dialog, text="Server:").pack(pady=5)
        server_entry = tk.Entry(smtp_dialog)
        server_entry.insert(0, smtp.get("server", ""))
        server_entry.pack(pady=5)
        tk.Label(smtp_dialog, text="Port:").pack(pady=5)
        port_entry = tk.Entry(smtp_dialog)
        port_entry.insert(0, smtp.get("port", 587))
        port_entry.pack(pady=5)
        tk.Label(smtp_dialog, text="Username:").pack(pady=5)
        username_entry = tk.Entry(smtp_dialog)
        username_entry.insert(0, smtp.get("username", ""))
        username_entry.pack(pady=5)
        tk.Label(smtp_dialog, text="Password:").pack(pady=5)
        password_entry = tk.Entry(smtp_dialog, show="*")
        password_entry.insert(0, smtp.get("password", ""))
        password_entry.pack(pady=5)
        tk.Label(smtp_dialog, text="From Email:").pack(pady=5)
        from_entry = tk.Entry(smtp_dialog)
        from_entry.insert(0, smtp.get("from", ""))
        from_entry.pack(pady=5)
        
        def test_connection():
            server = server_entry.get().strip()
            try:
                port = int(port_entry.get().strip())
            except ValueError:
                messagebox.showerror("Invalid Input", "Port must be an integer.", parent=smtp_dialog)
                return
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            if not (server and port and username and password):
                messagebox.showerror("Invalid Input", "Server, port, username, and password are required for testing.", parent=smtp_dialog)
                return
            try:
                if port == 465:  # SSL
                    smtp_conn = smtplib.SMTP_SSL(server, port, timeout=10)
                else:  # Plain or TLS
                    smtp_conn = smtplib.SMTP(server, port, timeout=10)
                smtp_conn.ehlo()
                if port != 465:  # Attempt STARTTLS for non-SSL ports
                    smtp_conn.starttls()
                    smtp_conn.ehlo()
                smtp_conn.login(username, password)
                smtp_conn.quit()
                messagebox.showinfo("Success", "SMTP connection and login successful.", parent=smtp_dialog)
            except smtplib.SMTPAuthenticationError:
                messagebox.showerror("Auth Error", "Authentication failed. Check username/password.", parent=smtp_dialog)
            except smtplib.SMTPConnectError:
                messagebox.showerror("Connect Error", "Failed to connect to server. Check server/port.", parent=smtp_dialog)
            except smtplib.SMTPException as e:
                messagebox.showerror("SMTP Error", f"SMTP error: {e}", parent=smtp_dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Unexpected error: {e}", parent=smtp_dialog)
        
        def submit(event=None):
            server = server_entry.get().strip()
            try:
                port = int(port_entry.get().strip())
            except ValueError:
                messagebox.showerror("Invalid Input", "Port must be an integer.", parent=smtp_dialog)
                return
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            from_email = from_entry.get().strip()
            cfg["smtp"] = {"server": server, "port": port, "username": username, "password": password, "from": from_email}
            ciphertext = encrypt_config(cfg, password)
            with open(CONFIG_FILE, "wb") as fh:
                fh.write(ciphertext)
            messagebox.showinfo("Success", "SMTP settings updated.", parent=win)
            smtp_dialog.destroy()
        
        btn_frame = tk.Frame(smtp_dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Test", command=test_connection, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Submit", command=submit, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=smtp_dialog.destroy, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        smtp_dialog.bind("<Return>", submit)
        smtp_dialog.transient(win)
        smtp_dialog.grab_set()

    btn_frame = tk.Frame(win)
    btn_frame.pack(fill="x", pady=5)
    tk.Button(btn_frame, text="Add", command=add_email, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    tk.Button(btn_frame, text="Edit", command=edit_email, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    tk.Button(btn_frame, text="Delete", command=delete_email, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    tk.Button(btn_frame, text="SMTP", command=smtp_settings, bg="#005228", fg="#ecc10c").pack(side="left", padx=20)
    tk.Button(btn_frame, text="Close", command=lambda: [win.destroy(), root.focus_force()], bg="#005228", fg="#ecc10c").pack(side="right", padx=5)
    win.transient(root)
    win.grab_set()

def build_gui():
    """Build and launch the main GUI with a hierarchical Treeview and controls."""
    global start_entry, end_entry, _treeview, search_var, preset_menu, endpoint_menu, view_btn, search_entry, select_all_btn, unselect_all_btn, check_rate_btn, reset_modules_btn
    root = tk.Tk()
    root.title("SubwayIQ")
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    # Set fixed window size
    win_width = 800
    win_height = 600
    # Calculate centered position
    x = (screen_width - win_width) // 2
    y = (screen_height - win_height) // 2
    root.geometry(f"{win_width}x{win_height}+{x}+{y}")
    root.resizable(False, False)
    root.minsize(800, 600)
    root.grid_columnconfigure(0, weight=0)
    root.grid_columnconfigure(1, weight=1)
    root.grid_columnconfigure(2, weight=0)
    root.grid_rowconfigure(0, weight=0)
    root.grid_rowconfigure(1, weight=1)
    root.grid_rowconfigure(2, weight=0)

    # Prompt for password
    password = simpledialog.askstring("Password", "Enter password:", parent=root, show="*")
    if not password:
        messagebox.showwarning("Password Required", "A password is required to access SubwayIQ.", parent=root)
        root.destroy()
        return

    # Load and set logo and icon
    logo_png_path = os.path.join(SCRIPT_DIR, "SubwayIQ.png")
    logo_ico_path = os.path.join(SCRIPT_DIR, "SubwayIQ.ico")
    logo_photo = None
    if os.path.exists(logo_png_path):
        logo_img = Image.open(logo_png_path)
        logo_img = logo_img.resize((100, 100), Image.Resampling.LANCZOS)
        logo_photo = ImageTk.PhotoImage(logo_img)
    if os.path.exists(logo_ico_path):
        try:
            root.iconbitmap(logo_ico_path)
        except tk.TclError:
            pass

    try:
        accounts = load_config_and_stores(root, password)
        root.focus_force()  # Bring focus back to main window after password dialog
    except SystemExit:
        return

    has_valid_accounts = any(acct.get("Status") == "OK" for acct in accounts)

    # Left Column: Controls
    control_frame = tk.Frame(root, width=300)
    control_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsw")
    control_frame.grid_propagate(False)
    control_frame.grid_columnconfigure(0, weight=1)

    if logo_photo:
        logo_label = tk.Label(control_frame, image=logo_photo)
        logo_label.pack(pady=(25, 0))

    # Date Range Section
    date_frame = tk.Frame(control_frame)
    date_frame.pack(fill="x", pady=10)
    tk.Label(date_frame, text="Date Range", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=5, sticky="ew")
    tk.Label(date_frame, text="Start:").grid(row=1, column=0, padx=5, sticky="e")
    start_entry = DateEntry(date_frame, date_pattern="yyyy-mm-dd")
    start_entry.grid(row=1, column=1, padx=5, sticky="w")
    tk.Label(date_frame, text="End:").grid(row=2, column=0, padx=5, sticky="e")
    end_entry = DateEntry(date_frame, date_pattern="yyyy-mm-dd")
    end_entry.grid(row=2, column=1, padx=5, sticky="w")
    today = datetime.now().date()
    start_entry.set_date(today)
    end_entry.set_date(today)
    tk.Label(date_frame, text="Preset:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
    range_var = tk.StringVar(value="Today")
    opts = ["Custom", "Today", "Yesterday", "Past 2 Days", "Past 3 Days", "Past 7 Days", "Past 14 Days", "Past 30 Days"]
    preset_menu = tk.OptionMenu(date_frame, range_var, *opts, command=lambda v: update_dates(v, start_entry, end_entry))
    preset_menu.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
    if not has_valid_accounts:
        preset_menu.config(state="disabled")
        start_entry.config(state="disabled")
        end_entry.config(state="disabled")
    start_entry.bind("<KeyRelease>", lambda e: check_date_preset(start_entry, end_entry, range_var))
    start_entry.bind("<<DateEntrySelected>>", lambda e: check_date_preset(start_entry, end_entry, range_var))
    end_entry.bind("<KeyRelease>", lambda e: check_date_preset(start_entry, end_entry, range_var))
    end_entry.bind("<<DateEntrySelected>>", lambda e: check_date_preset(start_entry, end_entry, range_var))
    date_frame.grid_columnconfigure((0,1), weight=1)

    # API Viewer Section
    api_frame = tk.Frame(control_frame)
    api_frame.pack(fill="x", pady=10)
    tk.Label(api_frame, text="API Viewer", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=3, pady=5, sticky="ew")
    endpoint_var = tk.StringVar(value=list(ENDPOINTS.keys())[0])
    endpoint_menu = tk.OptionMenu(api_frame, endpoint_var, *ENDPOINTS.keys())
    endpoint_menu.config(width=25)
    endpoint_menu.grid(row=1, column=1, padx=5, sticky="w")
    view_btn = tk.Button(api_frame, text="View", font=("Arial", 10), bg="#005228", fg="#ecc10c",
            command=lambda: validate_and_view(
                endpoint_var.get(),
                [s for s, v in store_vars.items() if v.get()],
                get_selected_start_date(),
                get_selected_end_date(),
                root)
    )
    view_btn.grid(row=2, column=1, pady=(4, 0), sticky="n")
    if not has_valid_accounts:
        endpoint_menu.config(state="disabled")
        view_btn.config(state="disabled")
    api_frame.grid_columnconfigure((0, 1, 2), weight=1)

    # Center Column: Treeview and Search
    tree_frame = tk.Frame(root, width=500)
    tree_frame.grid(row=0, column=1, rowspan=2, padx=10, pady=10, sticky="nsew")
    tree_frame.grid_propagate(False)
    tree_frame.grid_columnconfigure(0, weight=1)
    search_frame = tk.Frame(tree_frame)
    search_frame.pack(fill="x", pady=5)
    tk.Label(search_frame, text="Search Stores:").pack(side="left", padx=5)
    search_var = tk.StringVar()
    search_var.trace_add("write", lambda *args: update_treeview())
    search_entry = tk.Entry(search_frame, textvariable=search_var)
    search_entry.pack(side="left", fill="x", expand=False, padx=5)
    select_all_btn = tk.Button(search_frame, text="Select All", command=select_all, bg="#005228", fg="#ecc10c")
    select_all_btn.pack(side="left", padx=5)
    unselect_all_btn = tk.Button(search_frame, text="Unselect All", command=unselect_all, bg="#005228", fg="#ecc10c")
    unselect_all_btn.pack(side="left", padx=5)
    if not has_valid_accounts:
        search_entry.config(state="disabled")
        select_all_btn.config(state="disabled")
        unselect_all_btn.config(state="disabled")
    tree_container = tk.Frame(tree_frame)
    tree_container.pack(fill="both", expand=True)
    _treeview = ttk.Treeview(tree_container, columns=("Name", "Status", "Select"), show="tree headings", height=12)
    _treeview.pack(side="left", fill="both", expand=True)
    vsb = ttk.Scrollbar(tree_container, orient="vertical", command=_treeview.yview)
    vsb.pack(side="right", fill="y")
    _treeview.configure(yscrollcommand=vsb.set)
    _treeview.heading("Name", text="Account/Store")
    _treeview.heading("Status", text="Status")
    _treeview.heading("Select", text="Select")
    _treeview.column("#0", width=20)
    _treeview.column("Name", width=120, anchor="w")
    _treeview.column("Status", width=50)
    _treeview.column("Select", width=50, anchor="center")
    _treeview.tag_configure("account", font=("Arial", 12, "bold"))
    _treeview.tag_configure("disabled", foreground="gray")
    _treeview.tag_configure("error", foreground="red")

    # Right Column: Vertical Toolbar
    toolbar_frame = tk.Frame(root, width=100, bg="#f0f0f0")
    toolbar_height = 5  # Increased for new button
    toolbar_start_row = max(0, 0 + (2 - toolbar_height) // 2)
    toolbar_frame.grid(row=toolbar_start_row, column=2, rowspan=toolbar_height, padx=5, pady=50, sticky="ns")
    toolbar_frame.grid_propagate(False)
    accounts_btn = tk.Button(toolbar_frame, text="Accounts", 
                            command=lambda: manage_accounts(root, password), 
                            bg="#005228", fg="#ecc10c", width=15)
    accounts_btn.pack(pady=5)
    emails_btn = tk.Button(toolbar_frame, text="Emails", 
                          command=lambda: manage_emails(root, password), 
                          bg="#005228", fg="#ecc10c", width=15)
    emails_btn.pack(pady=5)
    reset_config_btn = tk.Button(toolbar_frame, text="Reset Config", command=lambda: reset_config(root), bg="#005228", fg="#ecc10c", width=15)
    reset_config_btn.pack(pady=5)
    check_rate_btn = tk.Button(toolbar_frame, text="Check Rate Limits", command=lambda: check_rate_limits(root), bg="#005228", fg="#ecc10c", width=15)
    check_rate_btn.pack(pady=5)
    reset_modules_btn = tk.Button(toolbar_frame, text="Reset Modules", command=lambda: reset_modules(root), bg="#005228", fg="#ecc10c", width=15)
    reset_modules_btn.pack(pady=5)
    if not has_valid_accounts:
        check_rate_btn.config(state="disabled")
        reset_modules_btn.config(state="disabled")

    update_treeview()

    # If no accounts are configured, open the manage_accounts dialog
    if not config_accounts:
        manage_accounts(root, password)

    load_external_modules(root, disable_buttons=not has_valid_accounts)

    if check_internet_connection():
        check_rate_limits(root)
    else:
        messagebox.showwarning("No Internet", "No internet connection detected. Account statuses may be outdated.", parent=root)

    root.mainloop()

if __name__ == "__main__":
    build_gui()