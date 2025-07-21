import string
import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import messagebox, filedialog, Toplevel, StringVar
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
import win32print
import urllib.parse
import webbrowser
import csv
import json
import os
import subprocess
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from collections import defaultdict
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

SALES_ENDPOINT = "Sales Summary"
DAILY_ENDPOINT = "Daily Sales Summary"
MAX_DAYS = 30
SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def generate_unique_filename(ext):
    """Generate unique filename in reports/ dir (Sales-XXXX.ext, alphanumeric)."""
    reports_dir = os.path.join(SCRIPT_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=4))
        fname = os.path.join(reports_dir, f"Sales-{code}.{ext.lower()}")
        if not os.path.exists(fname):
            return fname

def export_file(fmt, window, txt, sales_data, daily_breakdown, title, start_date, end_date, selected_stores):
    """Export report to specified format (PDF, JSON, CSV, TXT)."""
    fname = generate_unique_filename(fmt)
    is_single_day = start_date == end_date
    if fmt == "CSV":
        with open(fname, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([title])
            writer.writerow(["Generated on", datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow(["Date Range", f"{start_date} to {end_date}"])
            writer.writerow(["Stores", ', '.join(selected_stores)])
            writer.writerow([])
            writer.writerow(["Sales Summary"])
            writer.writerow(["Store", "Sales", "Tax", "Units", "Txns", "Cash/Card", "3rd $", "3rd Txns"])
            for sid in selected_stores:
                for entry in sales_data:
                    if entry["Store"] == sid:
                        writer.writerow([entry["Store"], f"{entry['Sales']:.2f}", f"{entry['Tax']:.2f}", 
                                        entry["Units"], entry["Txns"], f"{entry['Cash/Card']:.2f}", 
                                        f"{entry['3rd $']:.2f}", entry["3rd Txns"]])
            if not is_single_day:
                writer.writerow([])
                writer.writerow(["Daily Breakdown"])
                writer.writerow(["Date", "Store", "Sales", "Tax", "Units", "Txns", "Cash/Card", "3rd $", "3rd Txns"])
                for date in sorted(daily_breakdown):
                    for sid in selected_stores:
                        for entry in daily_breakdown[date]:
                            if entry["Store"] == sid:
                                writer.writerow([date, entry["Store"], f"{entry['Sales']:.2f}", f"{entry['Tax']:.2f}", 
                                                entry["Units"], entry["Txns"], f"{entry['Cash/Card']:.2f}", 
                                                f"{entry['3rd $']:.2f}", entry["3rd Txns"]])
    elif fmt == "JSON":
        export_data = {
            "generated_on": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "date_range": f"{start_date} to {end_date}",
            "stores": selected_stores,
            "sales_summary": [entry for sid in selected_stores for entry in sales_data if entry["Store"] == sid]
        }
        if not is_single_day:
            export_data["daily_breakdown"] = {date: [entry for sid in selected_stores for entry in entries if entry["Store"] == sid] 
                                             for date, entries in sorted(daily_breakdown.items())}
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)
    elif fmt == "TXT":
        data = txt.get("1.0", "end-1c")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(f"Sales Report: {start_date} to {end_date}\n")
            f.write(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Stores: {', '.join(selected_stores)}\n\n")
            f.write(data)
    elif fmt == "PDF":
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("PDF Error", "reportlab not available.", parent=window)
            return
        try:
            doc = SimpleDocTemplate(fname, pagesize=letter)
            styles = getSampleStyleSheet()
            style = styles["Normal"]
            style.fontName = "Courier"
            style.fontSize = 10
            elements = []
            elements.append(Paragraph(title, styles["Title"]))
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
            elements.append(Paragraph(f"Date Range: {start_date} to {end_date}", styles["Normal"]))
            elements.append(Paragraph(f"Stores: {', '.join(selected_stores)}", styles["Normal"]))
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Sales Summary", styles["Heading2"]))
            for sid in selected_stores:
                for entry in sales_data:
                    if entry["Store"] == sid:
                        text = (f"Store: {entry['Store']:<6}<br/>"
                                f"Sales: ${entry['Sales']:>10.2f}<br/>"
                                f"Tax: ${entry['Tax']:>8.2f}<br/>"
                                f"Units: {entry['Units']:>5}<br/>"
                                f"Txns: {entry['Txns']:>5}<br/>"
                                f"Cash/Card: ${entry['Cash/Card']:>10.2f}<br/>"
                                f"3rd $: ${entry['3rd $']:>8.2f}<br/>"
                                f"3rd Txns: {entry['3rd Txns']:>9}<br/>")
                        elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
            if not is_single_day:
                elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                for date in sorted(daily_breakdown):
                    elements.append(Paragraph(f"Date: {date}", styles["Heading3"]))
                    for sid in selected_stores:
                        for entry in daily_breakdown[date]:
                            if entry["Store"] == sid:
                                text = (f"Store: {entry['Store']:<6}<br/>"
                                        f"Sales: ${entry['Sales']:>10.2f}<br/>"
                                        f"Tax: ${entry['Tax']:>8.2f}<br/>"
                                        f"Units: {entry['Units']:>5}<br/>"
                                        f"Txns: {entry['Txns']:>5}<br/>"
                                        f"Cash/Card: ${entry['Cash/Card']:>10.2f}<br/>"
                                        f"3rd $: ${entry['3rd $']:>8.2f}<br/>"
                                        f"3rd Txns: {entry['3rd Txns']:>9}<br/>")
                                elements.append(Paragraph(text, style))
                                elements.append(Spacer(1, 12))
            doc.build(elements)
        except Exception as e:
            messagebox.showerror("PDF Error", f"Failed to generate PDF: {e}", parent=window)
            return
    try:
        os.startfile(fname)
    except Exception as e:
        if fmt == "JSON":
            try:
                subprocess.call([r'C:\Windows\System32\notepad.exe', fname])
                messagebox.showinfo("Opened", f"JSON opened in Notepad: {fname}.", parent=window)
            except Exception as e2:
                messagebox.showerror("Open Error", f"Failed to open {fname} in Notepad: {e2}. File saved.", parent=window)
        else:
            messagebox.showinfo("Open Info", f"File saved to {fname}. Open manually (error: {e}).", parent=window)

def open_email_dialog(window, txt, sales_data, daily_breakdown, title, start_date, end_date, selected_stores, config_emails, config_smtp):
    """Open dialog to select emails, format, and send report as attachment via mailto or SMTP."""
    if not config_emails:
        messagebox.showwarning("No Emails", "No emails configured. Add via Emails button.", parent=window)
        return
    dialog = Toplevel(window)
    dialog.title("Email Report")
    win_width, win_height = 400, 350
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    x = (screen_width - win_width) // 2
    y = (screen_height - win_height) // 2
    dialog.geometry(f"{win_width}x{win_height}+{x}+{y}")
    dialog.resizable(False, False)
    dialog.transient(window)
    dialog.grab_set()
    tk.Label(dialog, text="Select Emails and Format", font=("Arial", 12, "bold")).pack(pady=5)
    listbox = tk.Listbox(dialog, selectmode="multiple", height=10)
    listbox.pack(fill="both", expand=True, padx=10, pady=5)
    for email in config_emails:
        listbox.insert(tk.END, email)
    tk.Label(dialog, text="Attachment Format:").pack(pady=5)
    format_var = StringVar(value="PDF" if REPORTLAB_AVAILABLE else "TXT")
    format_menu = tk.OptionMenu(dialog, format_var, *["PDF" if REPORTLAB_AVAILABLE else "", "JSON", "CSV", "TXT"])
    format_menu.pack(pady=5)

    def select_all():
        listbox.select_set(0, tk.END)

    def unselect_all():
        listbox.select_clear(0, tk.END)

    def send_selected():
        selected = [config_emails[i] for i in listbox.curselection()]
        if not selected:
            messagebox.showwarning("No Selection", "Select at least one email.", parent=dialog)
            return
        fmt = format_var.get()
        export_file(fmt, dialog, txt, sales_data, daily_breakdown, title, start_date, end_date, selected_stores)
        fname = generate_unique_filename(fmt)
        lines = txt.get("1.0", "end-1c").splitlines()
        subj = f"Sales Report: {start_date} to {end_date}"
        body = urllib.parse.quote(f"Please see the attached sales report for {start_date} to {end_date}.")
        to = ",".join(selected)
        messagebox.showinfo("Email Report", f"Attachment saved to {fname}. Attach it manually to your email.", parent=dialog)
        webbrowser.open(f"mailto:{to}?subject={urllib.parse.quote(subj)}&body={body}")
        dialog.destroy()

    def send_now():
        if not all(k in config_smtp for k in ["server", "port", "username", "password", "from"]):
            messagebox.showerror("SMTP Incomplete", "SMTP settings not fully configured.", parent=dialog)
            return
        selected = [config_emails[i] for i in listbox.curselection()]
        if not selected:
            messagebox.showwarning("No Selection", "Select at least one email.", parent=dialog)
            return
        fmt = format_var.get()
        fname = generate_unique_filename(fmt)
        export_file(fmt, dialog, txt, sales_data, daily_breakdown, title, start_date, end_date, selected_stores)
        try:
            smtp = config_smtp
            msg = MIMEMultipart()
            msg["Subject"] = f"Sales Report: {start_date} to {end_date}"
            msg["From"] = smtp["from"]
            msg["To"] = ", ".join(selected)
            msg.attach(MIMEText(f"Please see the attached sales report for {start_date} to {end_date}."))
            with open(fname, "rb") as f:
                attach = MIMEApplication(f.read(), _subtype=fmt.lower())
                attach.add_header("Content-Disposition", "attachment", filename=os.path.basename(fname))
                msg.attach(attach)
            if smtp["port"] == 465:
                conn = smtplib.SMTP_SSL(smtp["server"], smtp["port"], timeout=10)
            else:
                conn = smtplib.SMTP(smtp["server"], smtp["port"], timeout=10)
                conn.starttls()
            conn.login(smtp["username"], smtp["password"])
            conn.send_message(msg)
            conn.quit()
            messagebox.showinfo("Sent", "Email sent with attachment successfully.", parent=dialog)
        except Exception as e:
            messagebox.showerror("Send Error", f"Failed to send: {e}", parent=dialog)
        finally:
            if os.path.exists(fname):
                os.unlink(fname)
        dialog.destroy()

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(fill="x", pady=5)
    tk.Button(btn_frame, text="Select All", command=select_all, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    tk.Button(btn_frame, text="Unselect All", command=unselect_all, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    tk.Button(btn_frame, text="Send to Selected", command=send_selected, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    if all(k in config_smtp for k in ["server", "port", "username", "password", "from"]):
        tk.Button(btn_frame, text="Send Now", command=send_now, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    tk.Button(btn_frame, text="Close", command=dialog.destroy, bg="#005228", fg="#ecc10c").pack(side="right", padx=5)

def create_toolbar(window, txt, title, sales_data, daily_breakdown, start_date, end_date, selected_stores):
    """Create revamped toolbar with Export .PDF/.JSON/.TXT/.CSV, Email, Print, Copy."""
    toolbar = tk.Frame(window, bg="#f0f0f0")
    toolbar.pack(fill="x", pady=(8, 0), padx=8)
    copy_btn = tk.Button(toolbar, text="Copy", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    copy_btn.pack(side="right", padx=4)
    print_btn = tk.Button(toolbar, text="Print", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    print_btn.pack(side="right", padx=4)
    email_btn = tk.Button(toolbar, text="Email", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                          command=lambda: open_email_dialog(window, txt, sales_data, daily_breakdown, title, start_date, end_date, selected_stores, config_emails, config_smtp))
    email_btn.pack(side="right", padx=4)
    csv_btn = tk.Button(toolbar, text="Export .CSV", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                        command=lambda: export_file("CSV", window, txt, sales_data, daily_breakdown, title, start_date, end_date, selected_stores))
    csv_btn.pack(side="right", padx=4)
    txt_btn = tk.Button(toolbar, text="Export .TXT", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                        command=lambda: export_file("TXT", window, txt, sales_data, daily_breakdown, title, start_date, end_date, selected_stores))
    txt_btn.pack(side="right", padx=4)
    json_btn = tk.Button(toolbar, text="Export .JSON", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                         command=lambda: export_file("JSON", window, txt, sales_data, daily_breakdown, title, start_date, end_date, selected_stores))
    json_btn.pack(side="right", padx=4)
    pdf_btn = tk.Button(toolbar, text="Export .PDF", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                        command=lambda: export_file("PDF", window, txt, sales_data, daily_breakdown, title, start_date, end_date, selected_stores))
    pdf_btn.pack(side="right", padx=4)

    def print_content():
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("PDF Error", "reportlab not available. Cannot print PDF.", parent=window)
            return
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
            fname = tf.name
        try:
            doc = SimpleDocTemplate(fname, pagesize=letter)
            styles = getSampleStyleSheet()
            style = styles["Normal"]
            style.fontName = "Courier"
            style.fontSize = 10
            elements = []
            elements.append(Paragraph(title, styles["Title"]))
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
            elements.append(Paragraph(f"Date Range: {start_date} to {end_date}", styles["Normal"]))
            elements.append(Paragraph(f"Stores: {', '.join(selected_stores)}", styles["Normal"]))
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Sales Summary", styles["Heading2"]))
            for sid in selected_stores:
                for entry in sales_data:
                    if entry["Store"] == sid:
                        text = (f"Store: {entry['Store']:<6}<br/>"
                                f"Sales: ${entry['Sales']:>10.2f}<br/>"
                                f"Tax: ${entry['Tax']:>8.2f}<br/>"
                                f"Units: {entry['Units']:>5}<br/>"
                                f"Txns: {entry['Txns']:>5}<br/>"
                                f"Cash/Card: ${entry['Cash/Card']:>10.2f}<br/>"
                                f"3rd $: ${entry['3rd $']:>8.2f}<br/>"
                                f"3rd Txns: {entry['3rd Txns']:>9}<br/>")
                        elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
            if not (start_date == end_date):
                elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                for date in sorted(daily_breakdown):
                    elements.append(Paragraph(f"Date: {date}", styles["Heading3"]))
                    for sid in selected_stores:
                        for entry in daily_breakdown[date]:
                            if entry["Store"] == sid:
                                text = (f"Store: {entry['Store']:<6}<br/>"
                                        f"Sales: ${entry['Sales']:>10.2f}<br/>"
                                        f"Tax: ${entry['Tax']:>8.2f}<br/>"
                                        f"Units: {entry['Units']:>5}<br/>"
                                        f"Txns: {entry['Txns']:>5}<br/>"
                                        f"Cash/Card: ${entry['Cash/Card']:>10.2f}<br/>"
                                        f"3rd $: ${entry['3rd $']:>8.2f}<br/>"
                                        f"3rd Txns: {entry['3rd Txns']:>9}<br/>")
                                elements.append(Paragraph(text, style))
                                elements.append(Spacer(1, 12))
            doc.build(elements)
            os.startfile(fname, "print")
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to generate/print PDF: {e}", parent=window)
        finally:
            if os.path.exists(fname):
                os.unlink(fname)

    def enable_toolbar():
        copy_btn.config(state=tk.NORMAL, command=lambda: (
            window.clipboard_clear(),
            window.clipboard_append(txt.get("1.0", "end-1c"))
        ))
        print_btn.config(state=tk.NORMAL, command=print_content)
        email_btn.config(state=tk.NORMAL)
        csv_btn.config(state=tk.NORMAL)
        txt_btn.config(state=tk.NORMAL)
        json_btn.config(state=tk.NORMAL)
        if REPORTLAB_AVAILABLE:
            pdf_btn.config(state=tk.NORMAL)
    return enable_toolbar

def run(window):
    """Run the Sales report for selected stores and date range."""
    from __main__ import get_selected_start_date, get_selected_end_date, fetch_data, store_vars, config_accounts, handle_rate_limit, log_error, config_max_workers, _password_validated, RateLimitError, config_emails, config_smtp, SCRIPT_DIR

    if not _password_validated:
        messagebox.showerror("Access Denied", "Password validation required.", parent=window)
        window.destroy()
        return

    # Validate date range
    try:
        start = datetime.strptime(get_selected_start_date(), "%Y-%m-%d").date()
        end = datetime.strptime(get_selected_end_date(), "%Y-%m-%d").date()
        if end < start:
            messagebox.showerror("Invalid Date Range", "End date cannot be before start date.", parent=window)
            window.destroy()
            return
        if (end - start).days + 1 > MAX_DAYS:
            messagebox.showerror("Date Range Too Large", f"Please select a range of at most {MAX_DAYS} days.", parent=window)
            window.destroy()
            return
    except ValueError as e:
        log_error(f"Date parsing error: {e}", endpoint=SALES_ENDPOINT)
        messagebox.showerror("Bad Date", "Could not parse your start/end dates.", parent=window)
        return

    # Set up window
    window.title("Sales Report")
    parent = window.master
    parent.update_idletasks()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    window.geometry(f"{int(window.winfo_screenwidth()*0.6)}x{int(window.winfo_screenheight()*0.6)}+{px}+{py}")
    window.resizable(True, True)
    window.minsize(800, 600)

    # Create ScrolledText but don't pack yet
    txt = ScrolledText(window, wrap="none", font=("Courier New", 11), fg="black", state="normal")

    selected_stores = [s for s, v in store_vars.items() if v.get()]
    start_date_str = start.strftime("%Y-%m-%d")
    end_date_str = end.strftime("%Y-%m-%d")
    is_single_day = start == end

    # Create toolbar at the top with additional params
    sales_data = []
    store_summary = defaultdict(lambda: {"total_sales": 0.0, "total_tax": 0.0, "total_units": 0, "total_txns": 0, "total_cashcard": 0.0, "total_tp_sales": 0.0, "total_tp_txns": 0})
    daily_breakdown = defaultdict(list)
    enable_toolbar = create_toolbar(window, txt, f"Sales Report: {start_date_str} to {end_date_str}", sales_data, daily_breakdown, start_date_str, end_date_str, selected_stores)
    log_error("Toolbar created", endpoint=SALES_ENDPOINT)

    # Now pack txt below toolbar
    txt.pack(fill="both", expand=True, padx=8, pady=(4, 8))
    hbar = tk.Scrollbar(window, orient="horizontal", command=txt.xview)
    hbar.pack(fill="x", padx=8)
    txt.configure(xscrollcommand=hbar.set)
    txt.tag_configure("title", font=("Courier New", 12, "bold"), foreground="black")
    txt.tag_configure("heading", font=("Courier New", 11, "bold"), foreground="black")
    txt.tag_configure("sep", foreground="#888888")

    def log(line="", tag=None):
        txt.configure(state="normal")
        txt.insert("end", line + "\n", tag or ())
        txt.see("end")
        txt.update()
        txt.configure(state="normal")
        log_error(f"Log: {line}", endpoint=SALES_ENDPOINT)

    def worker():
        try:
            if not selected_stores:
                log("No stores selected.", "sep")
                log_error("No stores selected", endpoint=SALES_ENDPOINT)
                window.after(0, enable_toolbar)
                return

            store_map = {}
            for acct in config_accounts:
                name = acct.get("Name", "")
                cid = acct.get("ClientID", "")
                ckey = acct.get("ClientKEY", "")
                if not all([name, cid, ckey]):
                    log(f"Skipping invalid account: {name or 'Unknown'}", "sep")
                    log_error(f"Invalid account: Name={name}, ClientID={cid}", endpoint=SALES_ENDPOINT)
                    continue
                for sid in acct.get("StoreIDs", []):
                    if sid in selected_stores and sid not in store_map:
                        store_map[sid] = (name, cid, ckey)

            if not store_map:
                log("No valid accounts with selected stores found.", "sep")
                log_error("No valid accounts with selected stores", endpoint=SALES_ENDPOINT)
                window.after(0, enable_toolbar)
                return

            # Start report
            log(f"Sales Report: {start_date_str} to {end_date_str}", "title")
            log(f"Fetching data for {len(store_map)} stores...", "sep")
            log("", None)

            # Choose endpoint based on date range
            top_ep = DAILY_ENDPOINT if is_single_day else SALES_ENDPOINT
            top_title = f"{'Daily' if is_single_day else 'Sales'} Summary ({start_date_str})" if is_single_day else f"Sales Summary ({start_date_str} to {end_date_str})"

            # Log top section header with aligned columns
            log(f"\n=== {top_title} ===", "title")
            hdr = f"{'Store':<6} {'Sales':>10} {'Tax':>8} {'Units':>7} {'Txns':>7} {'Cash/Card':>11} {'3rd $':>8} {'3rd Txns':>10}"
            log(hdr, "heading")
            log("─" * 75, "sep")

            # Fetch top summary per store
            futures = {}
            with ThreadPoolExecutor(max_workers=min(config_max_workers, len(selected_stores))) as ex:
                for sid, (aname, cid, ckey) in store_map.items():
                    fut = ex.submit(fetch_data, top_ep, sid, start_date_str, end_date_str, cid, ckey)
                    futures[fut] = (sid, cid, ckey)

                for fut in as_completed(futures):
                    sid, cid, ckey = futures[fut]
                    try:
                        res = fut.result()
                        log_error(f"API response for store {sid}: {json.dumps(res, indent=2)}", endpoint=top_ep)
                    except RateLimitError as ex:
                        log_error(f"Rate limit for store {sid}: {ex}", endpoint=top_ep)
                        log(f"⚠️ Store {sid}: Rate limit hit; skipping.", "sep")
                        continue
                    except Exception as ex:
                        log_error(f"Fetch failed for store {sid}: {ex}", sid, top_ep)
                        log(f"❌ Store {sid}: Exception: {ex}", "sep")
                        continue

                    err = res.get("error")
                    if err:
                        log_error(f"API error for store {sid}: {err}", sid, top_ep)
                        log(f"❌ Store {sid}: {err}", "sep")
                        continue

                    payload = res.get("data", res) or {}
                    if isinstance(payload, list):
                        payload = payload[0] if payload else {}
                    sales = float(payload.get("netSales", payload.get("netSalesTotal", 0.0)))
                    tax = float(payload.get("tax", 0.0))
                    units = int(payload.get("units", payload.get("unitCount", 0)))
                    txns = int(payload.get("transactions", payload.get("transactionCount", 0)))
                    cashcard = float(payload.get("cashCardTotal", 0.0))
                    tp_sales = float(payload.get("thirdPartySales", payload.get("thirdPartySaleTotal", 0.0)))
                    tp_txns = int(payload.get("thirdPartyTransactions", payload.get("thirdPartyTransactionCount", 0)))
                    sales_data.append({"Store": sid, "Sales": sales, "Tax": tax, "Units": units, "Txns": txns, "Cash/Card": cashcard, "3rd $": tp_sales, "3rd Txns": tp_txns})
                    ss = store_summary[sid]
                    ss["total_sales"] += sales
                    ss["total_tax"] += tax
                    ss["total_units"] += units
                    ss["total_txns"] += txns
                    ss["total_cashcard"] += cashcard
                    ss["total_tp_sales"] += tp_sales
                    ss["total_tp_txns"] += tp_txns

            # Log Sales Summary in selected_stores order
            for sid in selected_stores:
                found = False
                for entry in sales_data:
                    if entry["Store"] == sid:
                        found = True
                        log(f"{sid:<6} {entry['Sales']:>10.2f} {entry['Tax']:>8.2f} {entry['Units']:>7} {entry['Txns']:>7} {entry['Cash/Card']:>11.2f} {entry['3rd $']:>8.2f} {entry['3rd Txns']:>10}")
                if not found:
                    log(f"Store {sid}: No data available.", "sep")

            # Fetch daily breakdown per store
            futures = {}
            with ThreadPoolExecutor(max_workers=min(config_max_workers, len(selected_stores))) as ex:
                for sid, (aname, cid, ckey) in store_map.items():
                    fut = ex.submit(fetch_data, DAILY_ENDPOINT, sid, start_date_str, end_date_str, cid, ckey)
                    futures[fut] = (sid, cid, ckey)

                for fut in as_completed(futures):
                    sid, cid, ckey = futures[fut]
                    try:
                        res = fut.result()
                        log_error(f"API response for store {sid}: {json.dumps(res, indent=2)}", endpoint=DAILY_ENDPOINT)
                    except RateLimitError as ex:
                        log_error(f"Rate limit for store {sid}: {ex}", endpoint=DAILY_ENDPOINT)
                        log(f"⚠️ Store {sid}: Rate limit hit; skipping.", "sep")
                        continue
                    except Exception as ex:
                        log_error(f"Fetch failed for store {sid}: {ex}", sid, DAILY_ENDPOINT)
                        log(f"❌ Store {sid}: Exception: {ex}", "sep")
                        continue

                    err = res.get("error")
                    if err:
                        log_error(f"API error for store {sid}: {err}", sid, DAILY_ENDPOINT)
                        log(f"❌ Store {sid}: {err}", "sep")
                        continue

                    data = res.get("data", res) or []
                    if isinstance(data, dict):
                        data = [data]
                    if not data:
                        msg = "sales data for today" if is_single_day else "data available"
                        log(f"Store {sid}: No {msg}.", "sep")
                        log_error(f"No data for store {sid}", endpoint=DAILY_ENDPOINT)
                        continue

                    for rec in data:
                        date_key = next((k for k in rec if "date" in k.lower()), None)
                        raw = rec.get(date_key, "")
                        date = raw.split("T")[0] if "T" in str(raw) else str(raw)
                        try:
                            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
                            date = parsed_date.strftime("%Y-%m-%d")
                        except ValueError:
                            log_error(f"Invalid date format for store {sid}: {raw}", endpoint=DAILY_ENDPOINT)
                            continue
                        sales = float(rec.get("netSales", rec.get("netSalesTotal", 0.0)))
                        tax = float(rec.get("tax", 0.0))
                        units = int(rec.get("units", rec.get("unitCount", 0)))
                        txns = int(rec.get("transactions", rec.get("transactionCount", 0)))
                        cashcard = float(rec.get("cashCardTotal", 0.0))
                        tp_sales = float(rec.get("thirdPartySales", rec.get("thirdPartySaleTotal", 0.0)))
                        tp_txns = int(rec.get("thirdPartyTransactions", rec.get("thirdPartyTransactionCount", 0)))
                        daily_breakdown[date].append({"Store": sid, "Sales": sales, "Tax": tax, "Units": units, "Txns": txns, "Cash/Card": cashcard, "3rd $": tp_sales, "3rd Txns": tp_txns})

            # Log per-day summaries only for multi-day
            if not is_single_day:
                for date in sorted(daily_breakdown):
                    log("", None)
                    log(f"Per-Day Sales Summary ({date})", "title")
                    log("─" * 75, "sep")
                    log(f"{'Store':<6} {'Sales':>10} {'Tax':>8} {'Units':>7} {'Txns':>7} {'Cash/Card':>11} {'3rd $':>8} {'3rd Txns':>10}", "heading")
                    log("─" * 75, "sep")
                    for sid in selected_stores:
                        found = False
                        for entry in daily_breakdown[date]:
                            if entry["Store"] == sid:
                                found = True
                                log(f"{entry['Store']:<6} {entry['Sales']:>10.2f} {entry['Tax']:>8.2f} {entry['Units']:>7} {entry['Txns']:>7} {entry['Cash/Card']:>11.2f} {entry['3rd $']:>8.2f} {entry['3rd Txns']:>10}")
                        if not found:
                            log(f"{sid:<6} {0.0:>10.2f} {0.0:>8.2f} {0:>7} {0:>7} {0.0:>11.2f} {0.0:>8.2f} {0:>10}")
                    log("─" * 75, "sep")

            # Log per-store daily breakdown only for multi-day
            if not is_single_day:
                for sid in selected_stores:
                    log("", None)
                    log(f"{sid}", "title")
                    log("─" * 75, "sep")
                    log(f"{'Date':<10} {'Sales':>10} {'Tax':>8} {'Units':>7} {'Txns':>7} {'Cash/Card':>11} {'3rd $':>8} {'3rd Txns':>10}", "heading")
                    log("─" * 75, "sep")
                    has_data = False
                    for date in sorted(daily_breakdown):
                        for entry in daily_breakdown[date]:
                            if entry["Store"] == sid:
                                has_data = True
                                log(f"{date:<10} {entry['Sales']:>10.2f} {entry['Tax']:>8.2f} {entry['Units']:>7} {entry['Txns']:>7} {entry['Cash/Card']:>11.2f} {entry['3rd $']:>8.2f} {entry['3rd Txns']:>10}")
                    if not has_data:
                        log(f"No data for this store.")
                    log("─" * 75, "sep")

            # Clean up
            idx = txt.search("Fetching data for ", "1.0", tk.END)
            if idx:
                txt.delete(idx, f"{idx} lineend +1c")
            window.after(0, enable_toolbar)
        except Exception as ex:
            log_error(f"Worker thread error: {ex}", endpoint=SALES_ENDPOINT)
            log(f"❌ Report error: {ex}", "sep")
            window.after(0, enable_toolbar)

    threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    config_emails = []
    config_smtp = {}
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    root = tk.Tk()
    run(root)
    root.mainloop()