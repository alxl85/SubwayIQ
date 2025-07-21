import string
import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import messagebox, filedialog, Toplevel, StringVar
from datetime import datetime, date, timedelta
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

ENDPOINT_NAME = "Transaction Summary"
MAX_DAYS = 7
SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def generate_unique_filename(ext):
    """Generate unique filename in reports/ dir (Transactions-XXXX.ext, alphanumeric)."""
    reports_dir = os.path.join(SCRIPT_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=4))
        fname = os.path.join(reports_dir, f"Transactions-{code}.{ext.lower()}")
        if not os.path.exists(fname):
            return fname

def export_file(fmt, window, txt, transactions_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores):
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
            writer.writerow(["Transaction Entries"])
            writer.writerow(["Store", "Date", "Time", "Type", "Receipt", "Clerk", "Channel", "Sale Type", "Units", "Order Source", "Delivery Provider", "Delivery Partner", "Total", "Net Total", "Tax"])
            for entry in transactions_data:
                writer.writerow([entry["Store"], entry["Date"], entry["Time"], entry["Type"], entry["Receipt"], entry["Clerk"], entry["Channel"], entry["Sale Type"], entry["Units"], entry["Order Source"], entry["Delivery Provider"], entry["Delivery Partner"], f"{entry['Total']:.2f}", f"{entry['Net Total']:.2f}", f"{entry['Tax']:.2f}"])
            writer.writerow([])
            writer.writerow(["Store Summaries"])
            writer.writerow(["Store", "Total Sales", "Total Net", "Total Tax", "Total Units", "Total Txns", "EatIn", "ToGo", "Deliv", "Avg Tx $", "Void #", "Void $", "Refund #", "Refund $"])
            for sid in selected_stores:
                ss = store_summary.get(sid, {"total_sales": 0.0, "total_net": 0.0, "total_tax": 0.0, "total_units": 0, "total_txns": 0, "eatin": 0, "togo": 0, "delivery": 0, "avg_tx": 0.0, "void_count": 0, "void_total": 0.0, "refund_count": 0, "refund_total": 0.0})
                writer.writerow([sid, f"{ss['total_sales']:.2f}", f"{ss['total_net']:.2f}", f"{ss['total_tax']:.2f}", ss["total_units"], ss["total_txns"], ss["eatin"], ss["togo"], ss["delivery"], f"{ss['avg_tx']:.2f}", ss["void_count"], f"{ss['void_total']:.2f}", ss["refund_count"], f"{ss['refund_total']:.2f}"])
            if not is_single_day:
                writer.writerow([])
                writer.writerow(["Per-Day Transaction Summary"])
                writer.writerow(["Date", "Store", "Total Sales", "Total Net", "Total Tax", "Total Units", "Total Txns", "EatIn", "ToGo", "Deliv", "Avg Tx $", "Void #", "Void $", "Refund #", "Refund $"])
                for date in sorted(daily_breakdown):
                    for sid in selected_stores:
                        for entry in daily_breakdown[date]:
                            if entry["Store"] == sid:
                                writer.writerow([date, entry["Store"], f"{entry['total_sales']:.2f}", f"{entry['total_net']:.2f}", 
                                                f"{entry['total_tax']:.2f}", entry["total_units"], entry["total_txns"], 
                                                entry["eatin"], entry["togo"], entry["delivery"], f"{entry['avg_tx']:.2f}", 
                                                entry["void_count"], f"{entry['void_total']:.2f}", entry["refund_count"], 
                                                f"{entry['refund_total']:.2f}"])
                writer.writerow([])
                writer.writerow(["Per-Store Breakdown"])
                writer.writerow(["Store", "Date", "Total Sales", "Total Net", "Total Tax", "Total Units", "Total Txns", "EatIn", "ToGo", "Deliv", "Avg Tx $", "Void #", "Void $", "Refund #", "Refund $"])
                for sid in selected_stores:
                    for date in sorted(daily_breakdown):
                        for entry in daily_breakdown[date]:
                            if entry["Store"] == sid:
                                writer.writerow([entry["Store"], date, f"{entry['total_sales']:.2f}", f"{entry['total_net']:.2f}", 
                                                f"{entry['total_tax']:.2f}", entry["total_units"], entry["total_txns"], 
                                                entry["eatin"], entry["togo"], entry["delivery"], f"{entry['avg_tx']:.2f}", 
                                                entry["void_count"], f"{entry['void_total']:.2f}", entry["refund_count"], 
                                                f"{entry['refund_total']:.2f}"])
            writer.writerow([])
            writer.writerow(["Void/Refund Summary"])
            writer.writerow(["Store", "Void #", "Void $", "Refund #", "Refund $"])
            for sid in selected_stores:
                ss = store_summary.get(sid, {"void_count": 0, "void_total": 0.0, "refund_count": 0, "refund_total": 0.0})
                writer.writerow([sid, ss["void_count"], f"{ss['void_total']:.2f}", ss["refund_count"], f"{ss['refund_total']:.2f}"])
            writer.writerow([])
            writer.writerow(["Voided/Refunded Transactions"])
            writer.writerow(["Store", "Date", "Time", "Type", "Receipt #", "Clerk", "Amount $"])
            vr_list = [entry for entry in transactions_data if entry["Type"].lower() in ["void", "refund"]]
            for entry in sorted(vr_list, key=lambda x: (x["Store"], x["Date"], x["Time"])):
                writer.writerow([entry["Store"], entry["Date"], entry["Time"], entry["Type"], entry["Receipt"], entry["Clerk"][:15], f"{entry['Total']:.2f}"])
    elif fmt == "JSON":
        export_data = {
            "generated_on": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "date_range": f"{start_date} to {end_date}",
            "stores": selected_stores,
            "transaction_entries": transactions_data,
            "store_summaries": [{"Store": sid, "Total Sales": ss["total_sales"], "Total Net": ss["total_net"], "Total Tax": ss["total_tax"], 
                                "Total Units": ss["total_units"], "Total Txns": ss["total_txns"], "EatIn": ss["eatin"], "ToGo": ss["togo"], 
                                "Deliv": ss["delivery"], "Avg Tx $": ss["avg_tx"], "Void #": ss["void_count"], "Void $": ss["void_total"], 
                                "Refund #": ss["refund_count"], "Refund $": ss["refund_total"]} 
                               for sid in selected_stores 
                               for ss in [store_summary.get(sid, {"total_sales": 0.0, "total_net": 0.0, "total_tax": 0.0, "total_units": 0, 
                                                                  "total_txns": 0, "eatin": 0, "togo": 0, "delivery": 0, "avg_tx": 0.0, 
                                                                  "void_count": 0, "void_total": 0.0, "refund_count": 0, "refund_total": 0.0})]],
            "void_refund_summary": [{"Store": sid, "Void #": ss["void_count"], "Void $": ss["void_total"], 
                                     "Refund #": ss["refund_count"], "Refund $": ss["refund_total"]} 
                                    for sid in selected_stores 
                                    for ss in [store_summary.get(sid, {"void_count": 0, "void_total": 0.0, "refund_count": 0, "refund_total": 0.0})]],
            "voided_refunded_transactions": [{"Store": entry["Store"], "Date": entry["Date"], "Time": entry["Time"], 
                                              "Type": entry["Type"], "Receipt": entry["Receipt"], "Clerk": entry["Clerk"], 
                                              "Amount $": entry["Total"]} 
                                             for entry in sorted([entry for entry in transactions_data if entry["Type"].lower() in ["void", "refund"]], 
                                                                key=lambda x: (x["Store"], x["Date"], x["Time"]))]
        }
        if not is_single_day:
            export_data["per_day_summary"] = {date: [{"Store": entry["Store"], "Total Sales": entry["total_sales"], "Total Net": entry["total_net"], 
                                                     "Total Tax": entry["total_tax"], "Total Units": entry["total_units"], "Total Txns": entry["total_txns"], 
                                                     "EatIn": entry["eatin"], "ToGo": entry["togo"], "Deliv": entry["delivery"], 
                                                     "Avg Tx $": entry["avg_tx"], "Void #": entry["void_count"], "Void $": entry["void_total"], 
                                                     "Refund #": entry["refund_count"], "Refund $": entry["refund_total"]} 
                                                    for sid in selected_stores for entry in entries if entry["Store"] == sid] 
                                                   for date, entries in sorted(daily_breakdown.items())}
            export_data["per_store_breakdown"] = {sid: [{"Date": date, "Total Sales": entry["total_sales"], "Total Net": entry["total_net"], 
                                                        "Total Tax": entry["total_tax"], "Total Units": entry["total_units"], "Total Txns": entry["total_txns"], 
                                                        "EatIn": entry["eatin"], "ToGo": entry["togo"], "Deliv": entry["delivery"], 
                                                        "Avg Tx $": entry["avg_tx"], "Void #": entry["void_count"], "Void $": entry["void_total"], 
                                                        "Refund #": entry["refund_count"], "Refund $": entry["refund_total"]} 
                                                       for date in sorted(daily_breakdown) for entry in daily_breakdown[date] if entry["Store"] == sid] 
                                                      for sid in selected_stores}
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)
    elif fmt == "TXT":
        data = txt.get("1.0", "end-1c")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(f"Transactions Report: {start_date} to {end_date}\n")
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
            elements.append(Paragraph("Transaction Entries", styles["Heading2"]))
            elements.append(Paragraph(f"{'Store':<6} {'Date':<10} {'Time':<8} {'Type':<5} {'Receipt':<10} {'Clerk':<20} {'Channel':<20} {'Sale Type':<10} {'Units':>5} {'Order Source':<20} {'Delivery Provider':<15} {'Delivery Partner':<15} {'Total':>10} {'Net Total':>10} {'Tax':>8}", style))
            elements.append(Paragraph("─" * 120, style))
            for entry in transactions_data:
                text = (f"{entry['Store']:<6} {entry['Date']:<10} {entry['Time']:<8} {entry['Type']:<5} {entry['Receipt']:<10} {entry['Clerk'][:20]:<20} "
                        f"{entry['Channel'][:20]:<20} {entry['Sale Type'][:10]:<10} {entry['Units']:>5} {entry['Order Source'][:20]:<20} "
                        f"{entry['Delivery Provider'][:15]:<15} {entry['Delivery Partner'][:15]:<15} ${entry['Total']:>9.2f} ${entry['Net Total']:>9.2f} ${entry['Tax']:>8.2f}")
                elements.append(Paragraph(text, style))
                elements.append(Spacer(1, 12))
            elements.append(Paragraph("Store Summaries", styles["Heading2"]))
            elements.append(Paragraph(f"{'Store':<6} {'TotSales':>10} {'TotNet':>8} {'TotTax':>8} {'TotUnits':>8} {'TotTxns':>8} {'EatIn':>5} {'ToGo':>5} {'Deliv':>5} {'AvgTx$':>8} {'Void#':>5} {'Void$':>8} {'Rfund#':>6} {'Rfund$':>8}", style))
            elements.append(Paragraph("─" * 75, style))
            for sid in selected_stores:
                ss = store_summary.get(sid, {"total_sales": 0.0, "total_net": 0.0, "total_tax": 0.0, "total_units": 0, "total_txns": 0, 
                                            "eatin": 0, "togo": 0, "delivery": 0, "avg_tx": 0.0, "void_count": 0, "void_total": 0.0, 
                                            "refund_count": 0, "refund_total": 0.0})
                text = (f"{sid:<6} {ss['total_sales']:>10.2f} {ss['total_net']:>8.2f} {ss['total_tax']:>8.2f} {ss['total_units']:>8} {ss['total_txns']:>8} "
                        f"{ss['eatin']:>5} {ss['togo']:>5} {ss['delivery']:>5} {ss['avg_tx']:>8.2f} {ss['void_count']:>5} {ss['void_total']:>8.2f} "
                        f"{ss['refund_count']:>6} {ss['refund_total']:>8.2f}")
                elements.append(Paragraph(text, style))
                elements.append(Spacer(1, 12))
            if not is_single_day:
                elements.append(Paragraph("Per-Day Transaction Summary", styles["Heading2"]))
                elements.append(Paragraph(f"{'Date':<10} {'Store':<6} {'TotSales':>10} {'TotNet':>8} {'TotTax':>8} {'TotUnits':>8} {'TotTxns':>8} {'EatIn':>5} {'ToGo':>5} {'Deliv':>5} {'AvgTx$':>8} {'Void#':>5} {'Void$':>8} {'Rfund#':>6} {'Rfund$':>8}", style))
                elements.append(Paragraph("─" * 75, style))
                for date in sorted(daily_breakdown):
                    for sid in selected_stores:
                        for entry in daily_breakdown[date]:
                            if entry["Store"] == sid:
                                text = (f"{date:<10} {entry['Store']:<6} {entry['total_sales']:>10.2f} {entry['total_net']:>8.2f} {entry['total_tax']:>8.2f} "
                                        f"{entry['total_units']:>8} {entry['total_txns']:>8} {entry['eatin']:>5} {entry['togo']:>5} {entry['delivery']:>5} "
                                        f"{entry['avg_tx']:>8.2f} {entry['void_count']:>5} {entry['void_total']:>8.2f} {entry['refund_count']:>6} {entry['refund_total']:>8.2f}")
                                elements.append(Paragraph(text, style))
                                elements.append(Spacer(1, 12))
                elements.append(Paragraph("Per-Store Breakdown", styles["Heading2"]))
                elements.append(Paragraph(f"{'Store':<6} {'Date':<10} {'TotSales':>10} {'TotNet':>8} {'TotTax':>8} {'TotUnits':>8} {'TotTxns':>8} {'EatIn':>5} {'ToGo':>5} {'Deliv':>5} {'AvgTx$':>8} {'Void#':>5} {'Void$':>8} {'Rfund#':>6} {'Rfund$':>8}", style))
                elements.append(Paragraph("─" * 75, style))
                for sid in selected_stores:
                    for date in sorted(daily_breakdown):
                        for entry in daily_breakdown[date]:
                            if entry["Store"] == sid:
                                text = (f"{entry['Store']:<6} {date:<10} {entry['total_sales']:>10.2f} {entry['total_net']:>8.2f} {entry['total_tax']:>8.2f} "
                                        f"{entry['total_units']:>8} {entry['total_txns']:>8} {entry['eatin']:>5} {entry['togo']:>5} {entry['delivery']:>5} "
                                        f"{entry['avg_tx']:>8.2f} {entry['void_count']:>5} {entry['void_total']:>8.2f} {entry['refund_count']:>6} {entry['refund_total']:>8.2f}")
                                elements.append(Paragraph(text, style))
                                elements.append(Spacer(1, 12))
            elements.append(Paragraph("Void/Refund Summary", styles["Heading2"]))
            elements.append(Paragraph(f"{'Store':<6} {'Void #':>6} {'Void $':>8} {'Refund #':>8} {'Refund $':>8}", style))
            elements.append(Paragraph("─" * 37, style))
            for sid in selected_stores:
                ss = store_summary.get(sid, {"void_count": 0, "void_total": 0.0, "refund_count": 0, "refund_total": 0.0})
                text = (f"{sid:<6} {ss['void_count']:>6} {ss['void_total']:>8.2f} {ss['refund_count']:>8} {ss['refund_total']:>8.2f}")
                elements.append(Paragraph(text, style))
                elements.append(Spacer(1, 12))
            elements.append(Paragraph("Voided/Refunded Transactions", styles["Heading2"]))
            elements.append(Paragraph(f"{'Store':<6} {'Date':<10} {'Time':<8} {'Type':<5} {'Receipt #':<9} {'Clerk':<15} {'Amount $':>8}", style))
            elements.append(Paragraph("─" * 63, style))
            vr_list = [entry for entry in transactions_data if entry["Type"].lower() in ["void", "refund"]]
            for entry in sorted(vr_list, key=lambda x: (x["Store"], x["Date"], x["Time"])):
                text = (f"{entry['Store']:<6} {entry['Date']:<10} {entry['Time']:<8} {entry['Type']:<5} {entry['Receipt']:<9} {entry['Clerk'][:15]:<15} {entry['Total']:>8.2f}")
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

def open_email_dialog(window, txt, transactions_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores, config_emails, config_smtp):
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
        export_file(fmt, dialog, txt, transactions_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores)
        fname = generate_unique_filename(fmt)
        lines = txt.get("1.0", "end-1c").splitlines()
        subj = f"Transactions Report: {start_date} to {end_date}"
        body = urllib.parse.quote(f"Please see the attached transactions report for {start_date} to {end_date}.")
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
        export_file(fmt, dialog, txt, transactions_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores)
        try:
            smtp = config_smtp
            msg = MIMEMultipart()
            msg["Subject"] = f"Transactions Report: {start_date} to {end_date}"
            msg["From"] = smtp["from"]
            msg["To"] = ", ".join(selected)
            msg.attach(MIMEText(f"Please see the attached transactions report for {start_date} to {end_date}."))
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

def create_toolbar(window, txt, title, transactions_data, store_summary, daily_breakdown, start_date, end_date, selected_stores):
    """Create revamped toolbar with Export .PDF/.JSON/.TXT/.CSV, Email, Print, Copy."""
    toolbar = tk.Frame(window, bg="#f0f0f0")
    toolbar.pack(fill="x", pady=(8, 0), padx=8)
    copy_btn = tk.Button(toolbar, text="Copy", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    copy_btn.pack(side="right", padx=4)
    print_btn = tk.Button(toolbar, text="Print", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    print_btn.pack(side="right", padx=4)
    email_btn = tk.Button(toolbar, text="Email", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                          command=lambda: open_email_dialog(window, txt, transactions_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores, config_emails, config_smtp))
    email_btn.pack(side="right", padx=4)
    csv_btn = tk.Button(toolbar, text="Export .CSV", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                        command=lambda: export_file("CSV", window, txt, transactions_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores))
    csv_btn.pack(side="right", padx=4)
    txt_btn = tk.Button(toolbar, text="Export .TXT", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                        command=lambda: export_file("TXT", window, txt, transactions_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores))
    txt_btn.pack(side="right", padx=4)
    json_btn = tk.Button(toolbar, text="Export .JSON", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                         command=lambda: export_file("JSON", window, txt, transactions_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores))
    json_btn.pack(side="right", padx=4)
    pdf_btn = tk.Button(toolbar, text="Export .PDF", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                        command=lambda: export_file("PDF", window, txt, transactions_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores))
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
            elements.append(Paragraph("Transaction Entries", styles["Heading2"]))
            elements.append(Paragraph(f"{'Store':<6} {'Date':<10} {'Time':<8} {'Type':<5} {'Receipt':<10} {'Clerk':<20} {'Channel':<20} {'Sale Type':<10} {'Units':>5} {'Order Source':<20} {'Delivery Provider':<15} {'Delivery Partner':<15} {'Total':>10} {'Net Total':>10} {'Tax':>8}", style))
            elements.append(Paragraph("─" * 120, style))
            for entry in transactions_data:
                text = (f"{entry['Store']:<6} {entry['Date']:<10} {entry['Time']:<8} {entry['Type']:<5} {entry['Receipt']:<10} {entry['Clerk'][:20]:<20} "
                        f"{entry['Channel'][:20]:<20} {entry['Sale Type'][:10]:<10} {entry['Units']:>5} {entry['Order Source'][:20]:<20} "
                        f"{entry['Delivery Provider'][:15]:<15} {entry['Delivery Partner'][:15]:<15} ${entry['Total']:>9.2f} ${entry['Net Total']:>9.2f} ${entry['Tax']:>8.2f}")
                elements.append(Paragraph(text, style))
                elements.append(Spacer(1, 12))
            elements.append(Paragraph("Store Summaries", styles["Heading2"]))
            elements.append(Paragraph(f"{'Store':<6} {'TotSales':>10} {'TotNet':>8} {'TotTax':>8} {'TotUnits':>8} {'TotTxns':>8} {'EatIn':>5} {'ToGo':>5} {'Deliv':>5} {'AvgTx$':>8} {'Void#':>5} {'Void$':>8} {'Rfund#':>6} {'Rfund$':>8}", style))
            elements.append(Paragraph("─" * 75, style))
            for sid in selected_stores:
                ss = store_summary.get(sid, {"total_sales": 0.0, "total_net": 0.0, "total_tax": 0.0, "total_units": 0, "total_txns": 0, 
                                            "eatin": 0, "togo": 0, "delivery": 0, "avg_tx": 0.0, "void_count": 0, "void_total": 0.0, 
                                            "refund_count": 0, "refund_total": 0.0})
                text = (f"{sid:<6} {ss['total_sales']:>10.2f} {ss['total_net']:>8.2f} {ss['total_tax']:>8.2f} {ss['total_units']:>8} {ss['total_txns']:>8} "
                        f"{ss['eatin']:>5} {ss['togo']:>5} {ss['delivery']:>5} {ss['avg_tx']:>8.2f} {ss['void_count']:>5} {ss['void_total']:>8.2f} "
                        f"{ss['refund_count']:>6} {ss['refund_total']:>8.2f}")
                elements.append(Paragraph(text, style))
                elements.append(Spacer(1, 12))
            if not (start_date == end_date):
                elements.append(Paragraph("Per-Day Transaction Summary", styles["Heading2"]))
                elements.append(Paragraph(f"{'Date':<10} {'Store':<6} {'TotSales':>10} {'TotNet':>8} {'TotTax':>8} {'TotUnits':>8} {'TotTxns':>8} {'EatIn':>5} {'ToGo':>5} {'Deliv':>5} {'AvgTx$':>8} {'Void#':>5} {'Void$':>8} {'Rfund#':>6} {'Rfund$':>8}", style))
                elements.append(Paragraph("─" * 75, style))
                for date in sorted(daily_breakdown):
                    for sid in selected_stores:
                        for entry in daily_breakdown[date]:
                            if entry["Store"] == sid:
                                text = (f"{date:<10} {entry['Store']:<6} {entry['total_sales']:>10.2f} {entry['total_net']:>8.2f} {entry['total_tax']:>8.2f} "
                                        f"{entry['total_units']:>8} {entry['total_txns']:>8} {entry['eatin']:>5} {entry['togo']:>5} {entry['delivery']:>5} "
                                        f"{entry['avg_tx']:>8.2f} {entry['void_count']:>5} {entry['void_total']:>8.2f} {entry['refund_count']:>6} {entry['refund_total']:>8.2f}")
                                elements.append(Paragraph(text, style))
                                elements.append(Spacer(1, 12))
                elements.append(Paragraph("Per-Store Breakdown", styles["Heading2"]))
                elements.append(Paragraph(f"{'Store':<6} {'Date':<10} {'TotSales':>10} {'TotNet':>8} {'TotTax':>8} {'TotUnits':>8} {'TotTxns':>8} {'EatIn':>5} {'ToGo':>5} {'Deliv':>5} {'AvgTx$':>8} {'Void#':>5} {'Void$':>8} {'Rfund#':>6} {'Rfund$':>8}", style))
                elements.append(Paragraph("─" * 75, style))
                for sid in selected_stores:
                    for date in sorted(daily_breakdown):
                        for entry in daily_breakdown[date]:
                            if entry["Store"] == sid:
                                text = (f"{entry['Store']:<6} {date:<10} {entry['total_sales']:>10.2f} {entry['total_net']:>8.2f} {entry['total_tax']:>8.2f} "
                                        f"{entry['total_units']:>8} {entry['total_txns']:>8} {entry['eatin']:>5} {entry['togo']:>5} {entry['delivery']:>5} "
                                        f"{entry['avg_tx']:>8.2f} {entry['void_count']:>5} {entry['void_total']:>8.2f} {entry['refund_count']:>6} {entry['refund_total']:>8.2f}")
                                elements.append(Paragraph(text, style))
                                elements.append(Spacer(1, 12))
            elements.append(Paragraph("Void/Refund Summary", styles["Heading2"]))
            elements.append(Paragraph(f"{'Store':<6} {'Void #':>6} {'Void $':>8} {'Refund #':>8} {'Refund $':>8}", style))
            elements.append(Paragraph("─" * 37, style))
            for sid in selected_stores:
                ss = store_summary.get(sid, {"void_count": 0, "void_total": 0.0, "refund_count": 0, "refund_total": 0.0})
                text = (f"{sid:<6} {ss['void_count']:>6} {ss['void_total']:>8.2f} {ss['refund_count']:>8} {ss['refund_total']:>8.2f}")
                elements.append(Paragraph(text, style))
                elements.append(Spacer(1, 12))
            elements.append(Paragraph("Voided/Refunded Transactions", styles["Heading2"]))
            elements.append(Paragraph(f"{'Store':<6} {'Date':<10} {'Time':<8} {'Type':<5} {'Receipt #':<9} {'Clerk':<15} {'Amount $':>8}", style))
            elements.append(Paragraph("─" * 63, style))
            vr_list = [entry for entry in transactions_data if entry["Type"].lower() in ["void", "refund"]]
            for entry in sorted(vr_list, key=lambda x: (x["Store"], x["Date"], x["Time"])):
                text = (f"{entry['Store']:<6} {entry['Date']:<10} {entry['Time']:<8} {entry['Type']:<5} {entry['Receipt']:<9} {entry['Clerk'][:15]:<15} {entry['Total']:>8.2f}")
                elements.append(Paragraph(text, style))
                elements.append(Spacer(1, 12))
            doc.build(elements)
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
    """Run the Transactions report for selected stores and date range."""
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
        log_error(f"Date parsing error: {e}", endpoint=ENDPOINT_NAME)
        messagebox.showerror("Bad Date", "Could not parse your start/end dates.", parent=window)
        return

    # Set up window
    window.title("Transactions Report")
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
    transactions_data = []
    store_summary = defaultdict(lambda: {"total_sales": 0.0, "total_net": 0.0, "total_tax": 0.0, "total_units": 0, "total_txns": 0, 
                                        "eatin": 0, "togo": 0, "delivery": 0, "avg_tx": 0.0, "void_count": 0, "void_total": 0.0, 
                                        "refund_count": 0, "refund_total": 0.0})
    daily_breakdown = defaultdict(list)
    enable_toolbar = create_toolbar(window, txt, f"Transactions Report: {start_date_str} to {end_date_str}", transactions_data, store_summary, daily_breakdown, start_date_str, end_date_str, selected_stores)
    log_error("Toolbar created", endpoint=ENDPOINT_NAME)

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
        log_error(f"Log: {line}", endpoint=ENDPOINT_NAME)

    def worker():
        try:
            if not selected_stores:
                log("No stores selected.", "sep")
                log_error("No stores selected", endpoint=ENDPOINT_NAME)
                window.after(0, enable_toolbar)
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
                window.after(0, enable_toolbar)
                return

            # Start report
            log(f"Transactions Report: {start_date_str} to {end_date_str}", "title")
            log(f"Fetching data for {len(store_map)} stores...", "sep")
            log("", None)

            # Header for transaction entries
            hdr_txn = f"{'Store':<6} {'Date':<10} {'Time':<8} {'Type':<5} {'Receipt':<10} {'Clerk':<20} {'Channel':<20} {'Sale Type':<10} {'Units':>5} {'Order Source':<20} {'Delivery Provider':<15} {'Delivery Partner':<15} {'Total':>10} {'Net Total':>10} {'Tax':>8}"

            # Header for summary views
            hdr_sum = f"{'Store':<6} {'TotSales':>10} {'TotNet':>8} {'TotTax':>8} {'TotUnits':>8} {'TotTxns':>8} {'EatIn':>5} {'ToGo':>5} {'Deliv':>5} {'AvgTx$':>8} {'Void#':>5} {'Void$':>8} {'Rfund#':>6} {'Rfund$':>8}"

            # Fetch transaction data per store
            futures = {}
            with ThreadPoolExecutor(max_workers=min(config_max_workers, len(selected_stores))) as ex:
                for sid, (aname, cid, ckey) in store_map.items():
                    fut = ex.submit(fetch_data, ENDPOINT_NAME, sid, start_date_str, end_date_str, cid, ckey)
                    futures[fut] = (sid, aname, cid, ckey)

                for fut in as_completed(futures):
                    sid, aname, cid, ckey = futures[fut]
                    try:
                        res = fut.result()
                        log_error(f"API response for store {sid}: {json.dumps(res, indent=2)}", endpoint=ENDPOINT_NAME)
                    except RateLimitError as ex:
                        log_error(f"Rate limit for store {sid}: {ex}", endpoint=ENDPOINT_NAME)
                        log(f"⚠️ Store {sid}: Rate limit hit; skipping.", "sep")
                        continue
                    except Exception as ex:
                        log_error(f"Fetch failed for store {sid}: {ex}", sid, ENDPOINT_NAME)
                        log(f"❌ Store {sid}: Exception: {ex}", "sep")
                        continue

                    err = res.get("error")
                    if err:
                        log_error(f"API error for store {sid}: {err}", sid, ENDPOINT_NAME)
                        log(f"❌ Store {sid}: {err}", "sep")
                        continue

                    data = res.get("data", []) or []
                    if isinstance(data, dict):
                        data = [data]
                    for txn in data:
                        date_key = next((k for k in txn if "date" in k.lower()), None)
                        raw_date = txn.get(date_key, start_date_str)
                        date = raw_date.split("T")[0] if "T" in str(raw_date) else str(raw_date)
                        try:
                            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
                            date = parsed_date.strftime("%Y-%m-%d")
                        except ValueError:
                            log_error(f"Invalid date format for store {sid}: {raw_date}", endpoint=ENDPOINT_NAME)
                            continue
                        time_str = txn.get("time", "").split("T")[1].split(".")[0] if "T" in str(txn.get("time", "")) else txn.get("time", "")
                        txn_type = txn.get("type", "Unknown")
                        receipt = txn.get("receiptNumber", "N/A")
                        clerk = txn.get("clerkName", "Unknown")
                        channel = txn.get("channel", "")
                        sale_type = txn.get("saleType", "")
                        units = int(txn.get("units", 0))
                        order_source = txn.get("orderSource", "")
                        delivery_provider = txn.get("deliveryProvider", "")
                        delivery_partner = txn.get("deliveryPartner", "")
                        total = float(txn.get("total", 0.0))
                        net_total = float(txn.get("netTotal", 0.0))
                        tax = float(txn.get("tax", 0.0))
                        entry = {
                            "Store": sid,
                            "Date": date,
                            "Time": time_str,
                            "Type": txn_type,
                            "Receipt": receipt,
                            "Clerk": clerk,
                            "Channel": channel,
                            "Sale Type": sale_type,
                            "Units": units,
                            "Order Source": order_source,
                            "Delivery Provider": delivery_provider,
                            "Delivery Partner": delivery_partner,
                            "Total": total,
                            "Net Total": net_total,
                            "Tax": tax
                        }
                        transactions_data.append(entry)
                        ss = store_summary[sid]
                        ss["total_sales"] += total
                        ss["total_net"] += net_total
                        ss["total_tax"] += tax
                        ss["total_units"] += units
                        ss["total_txns"] += 1
                        lower_sale_type = sale_type.lower()
                        if lower_sale_type == "eatin":
                            ss["eatin"] += 1
                        elif lower_sale_type == "togo":
                            ss["togo"] += 1
                        elif lower_sale_type == "delivery":
                            ss["delivery"] += 1
                        lower_type = txn_type.lower()
                        if lower_type == "void":
                            ss["void_count"] += 1
                            ss["void_total"] += total
                        elif lower_type == "refund":
                            ss["refund_count"] += 1
                            ss["refund_total"] += total

            # Update avg_tx in store_summary
            for sid in store_summary:
                ss = store_summary[sid]
                if ss["total_txns"] > 0:
                    ss["avg_tx"] = ss["total_sales"] / ss["total_txns"]

            # Log individual transactions per store
            for sid in selected_stores:
                log("", None)
                log(f"Transactions for Store {sid}", "title")
                log("─" * 120, "sep")
                log(hdr_txn, "heading")
                log("─" * 120, "sep")
                has_txn = False
                for entry in sorted(transactions_data, key=lambda x: (x["Date"], x["Time"])):
                    if entry["Store"] == sid:
                        has_txn = True
                        log(f"{entry['Store']:<6} {entry['Date']:<10} {entry['Time']:<8} {entry['Type']:<5} {entry['Receipt']:<10} {entry['Clerk'][:20]:<20} "
                            f"{entry['Channel'][:20]:<20} {entry['Sale Type'][:10]:<10} {entry['Units']:>5} {entry['Order Source'][:20]:<20} "
                            f"{entry['Delivery Provider'][:15]:<15} {entry['Delivery Partner'][:15]:<15} ${entry['Total']:>9.2f} ${entry['Net Total']:>9.2f} ${entry['Tax']:>8.2f}")
                if not has_txn:
                    log("No transactions for this store.")
                log("─" * 120, "sep")

            # Log store summaries
            log("", None)
            log("Store Summaries", "title")
            log("─" * 75, "sep")
            log(hdr_sum, "heading")
            log("─" * 75, "sep")
            for sid in selected_stores:
                ss = store_summary.get(sid, {"total_sales": 0.0, "total_net": 0.0, "total_tax": 0.0, "total_units": 0, "total_txns": 0, 
                                            "eatin": 0, "togo": 0, "delivery": 0, "avg_tx": 0.0, "void_count": 0, "void_total": 0.0, 
                                            "refund_count": 0, "refund_total": 0.0})
                log(f"{sid:<6} {ss['total_sales']:>10.2f} {ss['total_net']:>8.2f} {ss['total_tax']:>8.2f} {ss['total_units']:>8} {ss['total_txns']:>8} "
                    f"{ss['eatin']:>5} {ss['togo']:>5} {ss['delivery']:>5} {ss['avg_tx']:>8.2f} {ss['void_count']:>5} {ss['void_total']:>8.2f} "
                    f"{ss['refund_count']:>6} {ss['refund_total']:>8.2f}")
            log("─" * 75, "sep")

            # Fetch daily breakdown per store
            days = [start + timedelta(days=x) for x in range((end - start).days + 1)]
            for day in days:
                dstr = day.strftime("%Y-%m-%d")
                futures = {}
                with ThreadPoolExecutor(max_workers=min(config_max_workers, len(selected_stores))) as ex:
                    for sid, (aname, cid, ckey) in store_map.items():
                        fut = ex.submit(fetch_data, ENDPOINT_NAME, sid, dstr, dstr, cid, ckey)
                        futures[fut] = (sid, cid, ckey)

                    for fut in as_completed(futures):
                        sid, cid, ckey = futures[fut]
                        try:
                            res = fut.result()
                            log_error(f"API response for store {sid} on {dstr}: {json.dumps(res, indent=2)}", endpoint=ENDPOINT_NAME)
                        except RateLimitError as ex:
                            log_error(f"Rate limit for store {sid} on {dstr}: {ex}", endpoint=ENDPOINT_NAME)
                            log(f"⚠️ Store {sid} on {dstr}: Rate limit hit; skipping.", "sep")
                            continue
                        except Exception as ex:
                            log_error(f"Fetch failed for store {sid} on {dstr}: {ex}", sid, ENDPOINT_NAME)
                            log(f"❌ Store {sid} on {dstr}: Exception: {ex}", "sep")
                            continue

                        err = res.get("error")
                        if err:
                            log_error(f"API error for store {sid} on {dstr}: {err}", sid, ENDPOINT_NAME)
                            log(f"❌ Store {sid} on {dstr}: {err}", "sep")
                            continue

                        data = res.get("data", []) or []
                        if isinstance(data, dict):
                            data = [data]
                        total_sales = 0.0
                        total_net = 0.0
                        total_tax = 0.0
                        total_units = 0
                        total_txns = 0
                        eatin = 0
                        togo = 0
                        delivery = 0
                        void_count = 0
                        void_total = 0.0
                        refund_count = 0
                        refund_total = 0.0
                        for txn in data:
                            date_key = next((k for k in txn if "date" in k.lower()), None)
                            raw_date = txn.get(date_key, dstr)
                            date = raw_date.split("T")[0] if "T" in str(raw_date) else str(raw_date)
                            try:
                                parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
                                date = parsed_date.strftime("%Y-%m-%d")
                            except ValueError:
                                log_error(f"Invalid date format for store {sid} on {dstr}: {raw_date}", endpoint=ENDPOINT_NAME)
                                continue
                            total = float(txn.get("total", 0.0))
                            net_total = float(txn.get("netTotal", 0.0))
                            tax = float(txn.get("tax", 0.0))
                            units = int(txn.get("units", 0))
                            txn_type = txn.get("type", "Unknown").lower()
                            sale_type = txn.get("saleType", "").lower()
                            total_sales += total
                            total_net += net_total
                            total_tax += tax
                            total_units += units
                            total_txns += 1
                            if sale_type == "eatin":
                                eatin += 1
                            elif sale_type == "togo":
                                togo += 1
                            elif sale_type == "delivery":
                                delivery += 1
                            if txn_type == "void":
                                void_count += 1
                                void_total += total
                            elif txn_type == "refund":
                                refund_count += 1
                                refund_total += total
                        avg_tx = total_sales / total_txns if total_txns > 0 else 0.0
                        daily_breakdown[dstr].append({
                            "Store": sid,
                            "total_sales": total_sales,
                            "total_net": total_net,
                            "total_tax": total_tax,
                            "total_units": total_units,
                            "total_txns": total_txns,
                            "eatin": eatin,
                            "togo": togo,
                            "delivery": delivery,
                            "avg_tx": avg_tx,
                            "void_count": void_count,
                            "void_total": void_total,
                            "refund_count": refund_count,
                            "refund_total": refund_total
                        })

                # Log per-day summaries only for multi-day
                if not is_single_day:
                    log("", None)
                    log(f"Per-Day Transaction Summary ({dstr})", "title")
                    log("─" * 75, "sep")
                    log(hdr_sum, "heading")
                    log("─" * 75, "sep")
                    for sid in selected_stores:
                        found = False
                        for entry in daily_breakdown[dstr]:
                            if entry["Store"] == sid:
                                found = True
                                log(f"{entry['Store']:<6} {entry['total_sales']:>10.2f} {entry['total_net']:>8.2f} {entry['total_tax']:>8.2f} {entry['total_units']:>8} {entry['total_txns']:>8} "
                                    f"{entry['eatin']:>5} {entry['togo']:>5} {entry['delivery']:>5} {entry['avg_tx']:>8.2f} {entry['void_count']:>5} {entry['void_total']:>8.2f} "
                                    f"{entry['refund_count']:>6} {entry['refund_total']:>8.2f}")
                        if not found:
                            log(f"{sid:<6} {0.0:>10.2f} {0.0:>8.2f} {0.0:>8.2f} {0:>8} {0:>8} {0:>5} {0:>5} {0:>5} {0.0:>8.2f} {0:>5} {0.0:>8.2f} {0:>6} {0.0:>8.2f}")
                    log("─" * 75, "sep")

            # Log per-store daily breakdown only for multi-day
            if not is_single_day:
                for sid in selected_stores:
                    log("", None)
                    log(f"Per-Store Breakdown for {sid}", "title")
                    log("─" * 75, "sep")
                    log(f"{'Date':<10} {'TotSales':>10} {'TotNet':>8} {'TotTax':>8} {'TotUnits':>8} {'TotTxns':>8} {'EatIn':>5} {'ToGo':>5} {'Deliv':>5} {'AvgTx$':>8} {'Void#':>5} {'Void$':>8} {'Rfund#':>6} {'Rfund$':>8}", "heading")
                    log("─" * 75, "sep")
                    has_data = False
                    for date in sorted(daily_breakdown):
                        for entry in daily_breakdown[date]:
                            if entry["Store"] == sid:
                                has_data = True
                                log(f"{date:<10} {entry['total_sales']:>10.2f} {entry['total_net']:>8.2f} {entry['total_tax']:>8.2f} {entry['total_units']:>8} {entry['total_txns']:>8} "
                                    f"{entry['eatin']:>5} {entry['togo']:>5} {entry['delivery']:>5} {entry['avg_tx']:>8.2f} {entry['void_count']:>5} {entry['void_total']:>8.2f} "
                                    f"{entry['refund_count']:>6} {entry['refund_total']:>8.2f}")
                    if not has_data:
                        log(f"No data for this store.")
                    log("─" * 75, "sep")

            # Log void/refund summary
            log("", None)
            log("Void/Refund Summary", "title")
            log("─" * 37, "sep")
            log(f"{'Store':<6} {'Void #':>6} {'Void $':>8} {'Refund #':>8} {'Refund $':>8}", "heading")
            log("─" * 37, "sep")
            for sid in selected_stores:
                ss = store_summary.get(sid, {"void_count": 0, "void_total": 0.0, "refund_count": 0, "refund_total": 0.0})
                log(f"{sid:<6} {ss['void_count']:>6} {ss['void_total']:>8.2f} {ss['refund_count']:>8} {ss['refund_total']:>8.2f}")
            log("─" * 37, "sep")

            # Log voided/refunded transactions
            log("", None)
            log("Voided/Refunded Transactions", "title")
            log("─" * 63, "sep")
            log(f"{'Store':<6} {'Date':<10} {'Time':<8} {'Type':<5} {'Receipt #':<9} {'Clerk':<15} {'Amount $':>8}", "heading")
            log("─" * 63, "sep")
            vr_list = [entry for entry in transactions_data if entry["Type"].lower() in ["void", "refund"]]
            if vr_list:
                for entry in sorted(vr_list, key=lambda x: (x["Store"], x["Date"], x["Time"])):
                    log(f"{entry['Store']:<6} {entry['Date']:<10} {entry['Time']:<8} {entry['Type']:<5} {entry['Receipt']:<9} {entry['Clerk'][:15]:<15} {entry['Total']:>8.2f}")
            else:
                log("No voided or refunded transactions.")
            log("─" * 63, "sep")

            # Clean up
            idx = txt.search("Fetching data for ", "1.0", tk.END)
            if idx:
                txt.delete(idx, f"{idx} lineend +1c")
            window.after(0, enable_toolbar)
        except Exception as ex:
            log_error(f"Worker thread error: {ex}", endpoint=ENDPOINT_NAME)
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