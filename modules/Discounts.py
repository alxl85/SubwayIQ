import string
import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import messagebox, filedialog, Toplevel, StringVar
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
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

ENDPOINT_NAME = "Transaction Details"
MAX_DAYS = 7
SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def generate_unique_filename(ext):
    """Generate unique filename in reports/ dir (Discounts-XXXX.ext, alphanumeric)."""
    reports_dir = os.path.join(SCRIPT_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=4))
        fname = os.path.join(reports_dir, f"Discounts-{code}.{ext.lower()}")
        if not os.path.exists(fname):
            return fname

def create_toolbar(window, txt, title, discounts_data, store_summary, daily_breakdown, start_date, end_date, selected_stores, daily_items, config_emails, config_smtp):
    """Create revamped toolbar with Export .PDF/.JSON/.TXT/.CSV, Email, Copy."""
    toolbar = tk.Frame(window, bg="#f0f0f0")
    toolbar.pack(fill="x", pady=(8, 0), padx=8)
    copy_btn = tk.Button(toolbar, text="Copy", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    copy_btn.pack(side="right", padx=4)
    print_btn = tk.Button(toolbar, text="Print", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    print_btn.pack(side="right", padx=4)
    email_btn = tk.Button(toolbar, text="Email", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                          command=lambda: open_email_dialog(window, txt, discounts_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores, daily_items, config_emails, config_smtp))
    email_btn.pack(side="right", padx=4)
    csv_btn = tk.Button(toolbar, text="Export .CSV", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    csv_btn.pack(side="right", padx=4)
    txt_btn = tk.Button(toolbar, text="Export .TXT", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    txt_btn.pack(side="right", padx=4)
    json_btn = tk.Button(toolbar, text="Export .JSON", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    json_btn.pack(side="right", padx=4)
    pdf_btn = tk.Button(toolbar, text="Export .PDF", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    pdf_btn.pack(side="right", padx=4)

    def enable_toolbar():
        copy_btn.config(state=tk.NORMAL, command=lambda: (
            window.clipboard_clear(),
            window.clipboard_append(txt.get("1.0", "end-1c"))
        ))
        email_btn.config(state=tk.NORMAL)
        csv_btn.config(state=tk.NORMAL, command=lambda: export_file("CSV"))
        txt_btn.config(state=tk.NORMAL, command=lambda: export_file("TXT"))
        json_btn.config(state=tk.NORMAL, command=lambda: export_file("JSON"))
        if REPORTLAB_AVAILABLE:
            pdf_btn.config(state=tk.NORMAL, command=lambda: export_file("PDF"))

    def export_file(fmt):
        fname = generate_unique_filename(fmt)
        if fmt == "CSV":
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([title])
                writer.writerow(["Generated on", datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                writer.writerow(["Date Range", f"{start_date} to {end_date}"])
                writer.writerow(["Stores", ', '.join(sorted(selected_stores))])
                writer.writerow([])
                writer.writerow(["Discount Summaries"])
                writer.writerow(["Code", "Desc", "Count", "Orig", "Adj", "Disc", "Total"])
                for d in discounts_data:
                    avg_orig = d["orig"]/d["count"] if d["count"] > 0 else 0
                    avg_adj = d["adj"]/d["count"] if d["count"] > 0 else 0
                    disc = avg_orig - avg_adj
                    total = disc * d["count"]
                    writer.writerow([d["code"], d["desc"], d["count"], avg_orig, avg_adj, disc, total])
                    writer.writerow(["Per Store"])
                    writer.writerow(["Store", "Count", "Orig", "Adj", "Disc"])
                    for sid in sorted(d["stores"]):
                        se = d["stores"][sid]
                        avg_orig = se["orig"]/se["count"] if se["count"] > 0 else 0
                        avg_adj = se["adj"]/se["count"] if se["count"] > 0 else 0
                        disc = avg_orig - avg_adj
                        writer.writerow([sid, se["count"], avg_orig, avg_adj, disc])
                    writer.writerow([])
                writer.writerow(["Per-Discount Totals"])
                writer.writerow(["Code", "Count", "Total"])
                for d in discounts_data:
                    writer.writerow([d["code"], d["count"], d["save"]])
                if start_date != end_date:
                    writer.writerow([])
                    writer.writerow(["Daily Breakdown"])
                    writer.writerow(["Date", "Code", "Desc", "Count", "Orig", "Adj", "Disc", "Total"])
                    for date_str in sorted(daily_breakdown):
                        writer.writerow([f"Date: {date_str}"])
                        for d in daily_breakdown[date_str]:
                            avg_orig = d["orig"]/d["count"] if d["count"] > 0 else 0
                            avg_adj = d["adj"]/d["count"] if d["count"] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * d["count"]
                            writer.writerow([date_str, d["code"], d["desc"], d["count"], avg_orig, avg_adj, disc, total])
                        writer.writerow([])
                writer.writerow([])
                writer.writerow(["Per-Store Breakdown"])
                for sid in sorted(selected_stores, key=int):
                    if len(daily_items[sid]) > 0:
                        writer.writerow([f"Store {sid}"])
                        writer.writerow(["Code", "Desc", "Count", "Orig", "Adj", "Disc", "Total"])
                        for (code, desc), se in sorted(daily_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                            avg_orig = se["orig"]/se["count"] if se["count"] > 0 else 0
                            avg_adj = se["adj"]/se["count"] if se["count"] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * se["count"]
                            writer.writerow([code, desc, se["count"], avg_orig, avg_adj, disc, total])
                        writer.writerow([])
                writer.writerow(["Store Summary"])
                writer.writerow(["Store", "Count", "Total"])
                total_count = sum(ss["count"] for ss in store_summary.values())
                total_save = sum(ss["save"] for ss in store_summary.values())
                for sid in sorted(store_summary):
                    ss = store_summary[sid]
                    writer.writerow([sid, ss["count"], ss["save"]])
                writer.writerow(["All Stores", total_count, total_save])
        elif fmt == "JSON":
            export_data = {
                "title": title,
                "generated_on": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "date_range": f"{start_date} to {end_date}",
                "stores": sorted(selected_stores),
                "discounts": [
                    {
                        **d,
                        "stores": [
                            {
                                "store": sid,
                                "count": se["count"],
                                "orig": se["orig"]/se["count"] if se["count"] > 0 else 0,
                                "adj": se["adj"]/se["count"] if se["count"] > 0 else 0,
                                "disc": (se["orig"]/se["count"] - se["adj"]/se["count"]) if se["count"] > 0 else 0
                            } for sid, se in d["stores"].items()
                        ]
                    } for d in discounts_data
                ],
                "per_discount_averages": [
                    {
                        "Code": d["code"],
                        "Count": d["count"],
                        "Total": d["save"]
                    } for d in discounts_data
                ],
                "per_store_breakdown": {
                    sid: [
                        {
                            "Code": code,
                            "Desc": desc,
                            "Count": se["count"],
                            "Orig": se["orig"]/se["count"] if se["count"] > 0 else 0,
                            "Adj": se["adj"]/se["count"] if se["count"] > 0 else 0,
                            "Disc": (se["orig"]/se["count"] - se["adj"]/se["count"]) if se["count"] > 0 else 0,
                            "Total": ((se["orig"]/se["count"] - se["adj"]/se["count"]) * se["count"]) if se["count"] > 0 else 0
                        } for (code, desc), se in sorted(daily_items[sid].items(), key=lambda x: x[1]["count"], reverse=True)
                    ] for sid in sorted(selected_stores, key=int) if len(daily_items[sid]) > 0
                },
                "store_summary": [
                    {"store": sid, **ss} for sid, ss in store_summary.items()
                ] + [{"store": "All Stores", "count": sum(ss["count"] for ss in store_summary.values()), "save": sum(ss["save"] for ss in store_summary.values())}]
            }
            if start_date != end_date:
                export_data["daily_breakdown"] = {
                    date_str: [
                        {
                            "Code": d["code"],
                            "Desc": d["desc"],
                            "Count": d["count"],
                            "Orig": d["orig"]/d["count"] if d["count"] > 0 else 0,
                            "Adj": d["adj"]/d["count"] if d["count"] > 0 else 0,
                            "Disc": (d["orig"]/d["count"] - d["adj"]/d["count"]) if d["count"] > 0 else 0,
                            "Total": ((d["orig"]/d["count"] - d["adj"]/d["count"]) * d["count"]) if d["count"] > 0 else 0
                        } for d in entries
                    ] for date_str, entries in daily_breakdown.items()
                }
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
        elif fmt == "TXT":
            data = txt.get("1.0", "end-1c")
            with open(fname, "w", encoding="utf-8") as f:
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
                elements.append(Paragraph(f"Stores: {', '.join(sorted(selected_stores))}", styles["Normal"]))
                elements.append(Spacer(1, 12))
                elements.append(Paragraph("Discount Summaries", styles["Heading2"]))
                for d in discounts_data:
                    avg_orig = d['orig'] / d['count'] if d['count'] > 0 else 0
                    avg_adj = d['adj'] / d['count'] if d['count'] > 0 else 0
                    disc = avg_orig - avg_adj
                    total = disc * d['count']
                    text = f"Discount: {d['desc']} ({d['code']})<br/>Count: {d['count']}<br/>Orig: {avg_orig:.2f}<br/>Adj: {avg_adj:.2f}<br/>Disc: {disc:.2f}<br/>Total: {total:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Paragraph("Per Store:", style))
                    for sid, se in sorted(d['stores'].items()):
                        avg_orig = se['orig'] / se['count'] if se['count'] > 0 else 0
                        avg_adj = se['adj'] / se['count'] if se['count'] > 0 else 0
                        disc = avg_orig - avg_adj
                        subtext = f"Store {sid}: Count {se['count']}, Orig {avg_orig:.2f}, Adj {avg_adj:.2f}, Disc {disc:.2f}<br/>"
                        elements.append(Paragraph(subtext, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Per-Discount Averages", styles["Heading2"]))
                for d in discounts_data:
                    text = f"Code: {d['code']}<br/>Count: {d['count']}<br/>Total: {d['save']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                if start_date != end_date:
                    elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                    for date_str in sorted(daily_breakdown):
                        elements.append(Paragraph(f"Date: {date_str}", styles["Heading3"]))
                        for d in daily_breakdown[date_str]:
                            avg_orig = d['orig'] / d['count'] if d['count'] > 0 else 0
                            avg_adj = d['adj'] / d['count'] if d['count'] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * d['count']
                            text = f"Discount: {d['desc']} ({d['code']})<br/>Count: {d['count']}<br/>Orig: {avg_orig:.2f}<br/>Adj: {avg_adj:.2f}<br/>Disc: {disc:.2f}<br/>Total: {total:.2f}<br/>"
                            elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
                elements.append(Paragraph("Per-Store Breakdown", styles["Heading2"]))
                for sid in sorted(selected_stores, key=int):
                    if len(daily_items[sid]) > 0:
                        elements.append(Paragraph(f"Store {sid}", styles["Heading3"]))
                        for (code, desc), se in sorted(daily_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                            avg_orig = se["orig"]/se["count"] if se["count"] > 0 else 0
                            avg_adj = se["adj"]/se["count"] if se["count"] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * se["count"]
                            text = f"Discount: {desc} ({code})<br/>Count: {se['count']}<br/>Orig: {avg_orig:.2f}<br/>Adj: {avg_adj:.2f}<br/>Disc: {disc:.2f}<br/>Total: {total:.2f}<br/>"
                            elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                total_count = sum(ss["count"] for ss in store_summary.values())
                total_save = sum(ss["save"] for ss in store_summary.values())
                for sid, ss in sorted(store_summary.items()):
                    text = f"Store: {sid}<br/>Count: {ss['count']}<br/>Total: {ss['save']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                elements.append(Paragraph(f"All Stores: Count {total_count}, Total {total_save:.2f}<br/>", style))
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
                except Exception as sub_e:
                    messagebox.showerror("Open Error", f"Failed to open {fname} in Notepad: {sub_e}. File saved.", parent=window)
            else:
                messagebox.showinfo("Open Info", f"File saved to {fname}. Open manually (error: {e}).", parent=window)

    return enable_toolbar

def open_email_dialog(window, txt, discounts_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores, daily_items, config_emails, config_smtp):
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
        fname = generate_unique_filename(fmt)
        if fmt == "CSV":
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([title])
                writer.writerow(["Generated on", datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                writer.writerow(["Date Range", f"{start_date} to {end_date}"])
                writer.writerow(["Stores", ', '.join(sorted(selected_stores))])
                writer.writerow([])
                writer.writerow(["Discount Summaries"])
                writer.writerow(["Code", "Desc", "Count", "Orig", "Adj", "Disc", "Total"])
                for d in discounts_data:
                    avg_orig = d["orig"]/d["count"] if d["count"] > 0 else 0
                    avg_adj = d["adj"]/d["count"] if d["count"] > 0 else 0
                    disc = avg_orig - avg_adj
                    total = disc * d["count"]
                    writer.writerow([d["code"], d["desc"], d["count"], avg_orig, avg_adj, disc, total])
                    writer.writerow(["Per Store"])
                    writer.writerow(["Store", "Count", "Orig", "Adj", "Disc"])
                    for sid in sorted(d["stores"]):
                        se = d["stores"][sid]
                        avg_orig = se["orig"]/se["count"] if se["count"] > 0 else 0
                        avg_adj = se["adj"]/se["count"] if se["count"] > 0 else 0
                        disc = avg_orig - avg_adj
                        writer.writerow([sid, se["count"], avg_orig, avg_adj, disc])
                    writer.writerow([])
                writer.writerow(["Per-Discount Averages"])
                writer.writerow(["Code", "Count", "Total"])
                for d in discounts_data:
                    writer.writerow([d["code"], d["count"], d["save"]])
                if start_date != end_date:
                    writer.writerow([])
                    writer.writerow(["Daily Breakdown"])
                    writer.writerow(["Date", "Code", "Desc", "Count", "Orig", "Adj", "Disc", "Total"])
                    for date_str in sorted(daily_breakdown):
                        writer.writerow([f"Date: {date_str}"])
                        for d in daily_breakdown[date_str]:
                            avg_orig = d["orig"]/d["count"] if d["count"] > 0 else 0
                            avg_adj = d["adj"]/d["count"] if d["count"] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * d["count"]
                            writer.writerow([date_str, d["code"], d["desc"], d["count"], avg_orig, avg_adj, disc, total])
                        writer.writerow([])
                writer.writerow([])
                writer.writerow(["Per-Store Breakdown"])
                for sid in sorted(selected_stores, key=int):
                    if len(daily_items[sid]) > 0:
                        writer.writerow([f"Store {sid}"])
                        writer.writerow(["Code", "Desc", "Count", "Orig", "Adj", "Disc", "Total"])
                        for (code, desc), se in sorted(daily_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                            avg_orig = se["orig"]/se["count"] if se["count"] > 0 else 0
                            avg_adj = se["adj"]/se["count"] if se["count"] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * se["count"]
                            writer.writerow([code, desc, se["count"], avg_orig, avg_adj, disc, total])
                        writer.writerow([])
                writer.writerow(["Store Summary"])
                writer.writerow(["Store", "Count", "Total"])
                total_count = sum(ss["count"] for ss in store_summary.values())
                total_save = sum(ss["save"] for ss in store_summary.values())
                for sid in sorted(store_summary):
                    ss = store_summary[sid]
                    writer.writerow([sid, ss["count"], ss["save"]])
                writer.writerow(["All Stores", total_count, total_save])
        elif fmt == "JSON":
            export_data = {
                "title": title,
                "generated_on": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "date_range": f"{start_date} to {end_date}",
                "stores": sorted(selected_stores),
                "discounts": [
                    {
                        **d,
                        "stores": [
                            {
                                "store": sid,
                                "count": se["count"],
                                "orig": se["orig"]/se["count"] if se["count"] > 0 else 0,
                                "adj": se["adj"]/se["count"] if se["count"] > 0 else 0,
                                "disc": (se["orig"]/se["count"] - se["adj"]/se["count"]) if se["count"] > 0 else 0
                            } for sid, se in d["stores"].items()
                        ]
                    } for d in discounts_data
                ],
                "per_discount_averages": [
                    {
                        "Code": d["code"],
                        "Count": d["count"],
                        "Total": d["save"]
                    } for d in discounts_data
                ],
                "per_store_breakdown": {
                    sid: [
                        {
                            "Code": code,
                            "Desc": desc,
                            "Count": se["count"],
                            "Orig": se["orig"]/se["count"] if se["count"] > 0 else 0,
                            "Adj": se["adj"]/se["count"] if se["count"] > 0 else 0,
                            "Disc": (se["orig"]/se["count"] - se["adj"]/se["count"]) if se["count"] > 0 else 0,
                            "Total": ((se["orig"]/se["count"] - se["adj"]/se["count"]) * se["count"]) if se["count"] > 0 else 0
                        } for (code, desc), se in sorted(daily_items[sid].items(), key=lambda x: x[1]["count"], reverse=True)
                    ] for sid in sorted(selected_stores, key=int) if len(daily_items[sid]) > 0
                },
                "store_summary": [
                    {"store": sid, **ss} for sid, ss in store_summary.items()
                ] + [{"store": "All Stores", "count": sum(ss["count"] for ss in store_summary.values()), "save": sum(ss["save"] for ss in store_summary.values())}]
            }
            if start_date != end_date:
                export_data["daily_breakdown"] = {
                    date_str: [
                        {
                            "Code": d["code"],
                            "Desc": d["desc"],
                            "Count": d["count"],
                            "Orig": d["orig"]/d["count"] if d["count"] > 0 else 0,
                            "Adj": d["adj"]/d["count"] if d["count"] > 0 else 0,
                            "Disc": (d["orig"]/d["count"] - d["adj"]/d["count"]) if d["count"] > 0 else 0,
                            "Total": ((d["orig"]/d["count"] - d["adj"]/d["count"]) * d["count"]) if d["count"] > 0 else 0
                        } for d in entries
                    ] for date_str, entries in daily_breakdown.items()
                }
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
        elif fmt == "TXT":
            data = txt.get("1.0", "end-1c")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(data)
        elif fmt == "PDF":
            if not REPORTLAB_AVAILABLE:
                messagebox.showerror("PDF Error", "reportlab not available.", parent=dialog)
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
                elements.append(Paragraph(f"Stores: {', '.join(sorted(selected_stores))}", styles["Normal"]))
                elements.append(Spacer(1, 12))
                elements.append(Paragraph("Discount Summaries", styles["Heading2"]))
                for d in discounts_data:
                    avg_orig = d['orig'] / d['count'] if d['count'] > 0 else 0
                    avg_adj = d['adj'] / d['count'] if d['count'] > 0 else 0
                    disc = avg_orig - avg_adj
                    total = disc * d['count']
                    text = f"Discount: {d['desc']} ({d['code']})<br/>Count: {d['count']}<br/>Orig: {avg_orig:.2f}<br/>Adj: {avg_adj:.2f}<br/>Disc: {disc:.2f}<br/>Total: {total:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Paragraph("Per Store:", style))
                    for sid, se in sorted(d['stores'].items()):
                        avg_orig = se['orig'] / se['count'] if se['count'] > 0 else 0
                        avg_adj = se['adj'] / se['count'] if se['count'] > 0 else 0
                        disc = avg_orig - avg_adj
                        subtext = f"Store {sid}: Count {se['count']}, Orig {avg_orig:.2f}, Adj {avg_adj:.2f}, Disc {disc:.2f}<br/>"
                        elements.append(Paragraph(subtext, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Per-Discount Averages", styles["Heading2"]))
                for d in discounts_data:
                    text = f"Code: {d['code']}<br/>Count: {d['count']}<br/>Total: {d['save']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                if start_date != end_date:
                    elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                    for date_str in sorted(daily_breakdown):
                        elements.append(Paragraph(f"Date: {date_str}", styles["Heading3"]))
                        for d in daily_breakdown[date_str]:
                            avg_orig = d['orig'] / d['count'] if d['count'] > 0 else 0
                            avg_adj = d['adj'] / d['count'] if d['count'] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * d['count']
                            text = f"Discount: {d['desc']} ({d['code']})<br/>Count: {d['count']}<br/>Orig: {avg_orig:.2f}<br/>Adj: {avg_adj:.2f}<br/>Disc: {disc:.2f}<br/>Total: {total:.2f}<br/>"
                            elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
                elements.append(Paragraph("Per-Store Breakdown", styles["Heading2"]))
                for sid in sorted(selected_stores, key=int):
                    if len(daily_items[sid]) > 0:
                        elements.append(Paragraph(f"Store {sid}", styles["Heading3"]))
                        for (code, desc), se in sorted(daily_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                            avg_orig = se["orig"]/se["count"] if se["count"] > 0 else 0
                            avg_adj = se["adj"]/se["count"] if se["count"] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * se["count"]
                            text = f"Discount: {desc} ({code})<br/>Count: {se['count']}<br/>Orig: {avg_orig:.2f}<br/>Adj: {avg_adj:.2f}<br/>Disc: {disc:.2f}<br/>Total: {total:.2f}<br/>"
                            elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                total_count = sum(ss["count"] for ss in store_summary.values())
                total_save = sum(ss["save"] for ss in store_summary.values())
                for sid, ss in sorted(store_summary.items()):
                    text = f"Store: {sid}<br/>Count: {ss['count']}<br/>Total: {ss['save']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                elements.append(Paragraph(f"All Stores: Count {total_count}, Total {total_save:.2f}<br/>", style))
                doc.build(elements)
            except Exception as e:
                messagebox.showerror("PDF Error", f"Failed to generate PDF: {e}", parent=dialog)
                return
        lines = txt.get("1.0", "end-1c").splitlines()
        subj = "Discounts Report"
        if lines and "Discounts: " in lines[0]:
            subj += " – " + lines[0].split(": ", 1)[1]
        subj = urllib.parse.quote(subj)
        body = urllib.parse.quote("Please see the attached discounts report.")
        to = ",".join(selected)
        messagebox.showinfo("Email Report", f"Attachment saved to {fname}. Attach it manually to your email.", parent=dialog)
        webbrowser.open(f"mailto:{to}?subject={subj}&body={body}")
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
        if fmt == "CSV":
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([title])
                writer.writerow(["Generated on", datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                writer.writerow(["Date Range", f"{start_date} to {end_date}"])
                writer.writerow(["Stores", ', '.join(sorted(selected_stores))])
                writer.writerow([])
                writer.writerow(["Discount Summaries"])
                writer.writerow(["Code", "Desc", "Count", "Orig", "Adj", "Disc", "Total"])
                for d in discounts_data:
                    avg_orig = d["orig"]/d["count"] if d["count"] > 0 else 0
                    avg_adj = d["adj"]/d["count"] if d["count"] > 0 else 0
                    disc = avg_orig - avg_adj
                    total = disc * d["count"]
                    writer.writerow([d["code"], d["desc"], d["count"], avg_orig, avg_adj, disc, total])
                    writer.writerow(["Per Store"])
                    writer.writerow(["Store", "Count", "Orig", "Adj", "Disc"])
                    for sid in sorted(d["stores"]):
                        se = d["stores"][sid]
                        avg_orig = se["orig"]/se["count"] if se["count"] > 0 else 0
                        avg_adj = se["adj"]/se["count"] if se["count"] > 0 else 0
                        disc = avg_orig - avg_adj
                        writer.writerow([sid, se["count"], avg_orig, avg_adj, disc])
                    writer.writerow([])
                writer.writerow(["Per-Discount Averages"])
                writer.writerow(["Code", "Count", "Total"])
                for d in discounts_data:
                    writer.writerow([d["code"], d["count"], d["save"]])
                if start_date != end_date:
                    writer.writerow([])
                    writer.writerow(["Daily Breakdown"])
                    writer.writerow(["Date", "Code", "Desc", "Count", "Orig", "Adj", "Disc", "Total"])
                    for date_str in sorted(daily_breakdown):
                        writer.writerow([f"Date: {date_str}"])
                        for d in daily_breakdown[date_str]:
                            avg_orig = d["orig"]/d["count"] if d["count"] > 0 else 0
                            avg_adj = d["adj"]/d["count"] if d["count"] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * d["count"]
                            writer.writerow([date_str, d["code"], d["desc"], d["count"], avg_orig, avg_adj, disc, total])
                        writer.writerow([])
                writer.writerow([])
                writer.writerow(["Per-Store Breakdown"])
                for sid in sorted(selected_stores, key=int):
                    if len(daily_items[sid]) > 0:
                        writer.writerow([f"Store {sid}"])
                        writer.writerow(["Code", "Desc", "Count", "Orig", "Adj", "Disc", "Total"])
                        for (code, desc), se in sorted(daily_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                            avg_orig = se["orig"]/se["count"] if se["count"] > 0 else 0
                            avg_adj = se["adj"]/se["count"] if se["count"] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * se["count"]
                            writer.writerow([code, desc, se["count"], avg_orig, avg_adj, disc, total])
                        writer.writerow([])
                writer.writerow(["Store Summary"])
                writer.writerow(["Store", "Count", "Total"])
                total_count = sum(ss["count"] for ss in store_summary.values())
                total_save = sum(ss["save"] for ss in store_summary.values())
                for sid in sorted(store_summary):
                    ss = store_summary[sid]
                    writer.writerow([sid, ss["count"], ss["save"]])
                writer.writerow(["All Stores", total_count, total_save])
        elif fmt == "JSON":
            export_data = {
                "title": title,
                "generated_on": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "date_range": f"{start_date} to {end_date}",
                "stores": sorted(selected_stores),
                "discounts": [
                    {
                        **d,
                        "stores": [
                            {
                                "store": sid,
                                "count": se["count"],
                                "orig": se["orig"]/se["count"] if se["count"] > 0 else 0,
                                "adj": se["adj"]/se["count"] if se["count"] > 0 else 0,
                                "disc": (se["orig"]/se["count"] - se["adj"]/se["count"]) if se["count"] > 0 else 0
                            } for sid, se in d["stores"].items()
                        ]
                    } for d in discounts_data
                ],
                "per_discount_averages": [
                    {
                        "Code": d["code"],
                        "Count": d["count"],
                        "Total": d["save"]
                    } for d in discounts_data
                ],
                "per_store_breakdown": {
                    sid: [
                        {
                            "Code": code,
                            "Desc": desc,
                            "Count": se["count"],
                            "Orig": se["orig"]/se["count"] if se["count"] > 0 else 0,
                            "Adj": se["adj"]/se["count"] if se["count"] > 0 else 0,
                            "Disc": (se["orig"]/se["count"] - se["adj"]/se["count"]) if se["count"] > 0 else 0,
                            "Total": ((se["orig"]/se["count"] - se["adj"]/se["count"]) * se["count"]) if se["count"] > 0 else 0
                        } for (code, desc), se in sorted(daily_items[sid].items(), key=lambda x: x[1]["count"], reverse=True)
                    ] for sid in sorted(selected_stores, key=int) if len(daily_items[sid]) > 0
                },
                "store_summary": [
                    {"store": sid, **ss} for sid, ss in store_summary.items()
                ] + [{"store": "All Stores", "count": sum(ss["count"] for ss in store_summary.values()), "save": sum(ss["save"] for ss in store_summary.values())}]
            }
            if start_date != end_date:
                export_data["daily_breakdown"] = {
                    date_str: [
                        {
                            "Code": d["code"],
                            "Desc": d["desc"],
                            "Count": d["count"],
                            "Orig": d["orig"]/d["count"] if d["count"] > 0 else 0,
                            "Adj": d["adj"]/d["count"] if d["count"] > 0 else 0,
                            "Disc": (d["orig"]/d["count"] - d["adj"]/d["count"]) if d["count"] > 0 else 0,
                            "Total": ((d["orig"]/d["count"] - d["adj"]/d["count"]) * d["count"]) if d["count"] > 0 else 0
                        } for d in entries
                    ] for date_str, entries in daily_breakdown.items()
                }
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
        elif fmt == "TXT":
            data = txt.get("1.0", "end-1c")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(data)
        elif fmt == "PDF":
            if not REPORTLAB_AVAILABLE:
                messagebox.showerror("PDF Error", "reportlab not available.", parent=dialog)
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
                elements.append(Paragraph(f"Stores: {', '.join(sorted(selected_stores))}", styles["Normal"]))
                elements.append(Spacer(1, 12))
                elements.append(Paragraph("Discount Summaries", styles["Heading2"]))
                for d in discounts_data:
                    avg_orig = d['orig'] / d['count'] if d['count'] > 0 else 0
                    avg_adj = d['adj'] / d['count'] if d['count'] > 0 else 0
                    disc = avg_orig - avg_adj
                    total = disc * d['count']
                    text = f"Discount: {d['desc']} ({d['code']})<br/>Count: {d['count']}<br/>Orig: {avg_orig:.2f}<br/>Adj: {avg_adj:.2f}<br/>Disc: {disc:.2f}<br/>Total: {total:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Paragraph("Per Store:", style))
                    for sid, se in sorted(d['stores'].items()):
                        avg_orig = se['orig'] / se['count'] if se['count'] > 0 else 0
                        avg_adj = se['adj'] / se['count'] if se['count'] > 0 else 0
                        disc = avg_orig - avg_adj
                        subtext = f"Store {sid}: Count {se['count']}, Orig {avg_orig:.2f}, Adj {avg_adj:.2f}, Disc {disc:.2f}<br/>"
                        elements.append(Paragraph(subtext, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Per-Discount Averages", styles["Heading2"]))
                for d in discounts_data:
                    text = f"Code: {d['code']}<br/>Count: {d['count']}<br/>Total: {d['save']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                if start_date != end_date:
                    elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                    for date_str in sorted(daily_breakdown):
                        elements.append(Paragraph(f"Date: {date_str}", styles["Heading3"]))
                        for d in daily_breakdown[date_str]:
                            avg_orig = d['orig'] / d['count'] if d['count'] > 0 else 0
                            avg_adj = d['adj'] / d['count'] if d['count'] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * d['count']
                            text = f"Discount: {d['desc']} ({d['code']})<br/>Count: {d['count']}<br/>Orig: {avg_orig:.2f}<br/>Adj: {avg_adj:.2f}<br/>Disc: {disc:.2f}<br/>Total: {total:.2f}<br/>"
                            elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
                elements.append(Paragraph("Per-Store Breakdown", styles["Heading2"]))
                for sid in sorted(selected_stores, key=int):
                    if len(daily_items[sid]) > 0:
                        elements.append(Paragraph(f"Store {sid}", styles["Heading3"]))
                        for (code, desc), se in sorted(daily_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                            avg_orig = se["orig"]/se["count"] if se["count"] > 0 else 0
                            avg_adj = se["adj"]/se["count"] if se["count"] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * se["count"]
                            text = f"Discount: {desc} ({code})<br/>Count: {se['count']}<br/>Orig: {avg_orig:.2f}<br/>Adj: {avg_adj:.2f}<br/>Disc: {disc:.2f}<br/>Total: {total:.2f}<br/>"
                            elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                total_count = sum(ss["count"] for ss in store_summary.values())
                total_save = sum(ss["save"] for ss in store_summary.values())
                for sid, ss in sorted(store_summary.items()):
                    text = f"Store: {sid}<br/>Count: {ss['count']}<br/>Total: {ss['save']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                elements.append(Paragraph(f"All Stores: Count {total_count}, Total {total_save:.2f}<br/>", style))
                doc.build(elements)
            except Exception as e:
                messagebox.showerror("PDF Error", f"Failed to generate PDF: {e}", parent=dialog)
                return
        try:
            os.startfile(fname)
        except Exception as e:
            if fmt == "JSON":
                try:
                    subprocess.call([r'C:\Windows\System32\notepad.exe', fname])
                    messagebox.showinfo("Opened", f"JSON opened in Notepad: {fname}.", parent=dialog)
                except Exception as sub_e:
                    messagebox.showerror("Open Error", f"Failed to open {fname} in Notepad: {sub_e}. File saved.", parent=dialog)
            else:
                messagebox.showinfo("Open Info", f"File saved to {fname}. Open manually (error: {e}).", parent=dialog)

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(fill="x", pady=5)
    tk.Button(btn_frame, text="Select All", command=select_all, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    tk.Button(btn_frame, text="Unselect All", command=unselect_all, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    tk.Button(btn_frame, text="Send to Selected", command=send_selected, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    if all(k in config_smtp for k in ["server", "port", "username", "password", "from"]):
        tk.Button(btn_frame, text="Send Now", command=send_now, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
    tk.Button(btn_frame, text="Close", command=dialog.destroy, bg="#005228", fg="#ecc10c").pack(side="right", padx=5)

def run(window):
    """Run the Discounts report for selected stores and date range."""
    from __main__ import get_selected_start_date, get_selected_end_date, fetch_data, store_vars, config_accounts, handle_rate_limit, log_error, config_max_workers, _password_validated, RateLimitError, config_emails, config_smtp, SCRIPT_DIR

    if not _password_validated:
        messagebox.showerror("Access Denied", "Password validation required.", parent=window)
        window.destroy()
        return

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

    window.title("Discounts Report")
    parent = window.master
    parent.update_idletasks()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    window.geometry(f"{int(window.winfo_screenwidth()*0.6)}x{int(window.winfo_screenheight()*0.6)}+{px}+{py}")
    window.resizable(True, True)
    window.minsize(800, 600)
    window.protocol("WM_DELETE_WINDOW", lambda: [parent.focus_force(), window.destroy()])

    txt = ScrolledText(window, wrap="none", font=("Courier New", 11), fg="black", state="normal")

    selected_stores = [s for s, v in store_vars.items() if v.get()]
    start_date_str = start.isoformat()
    end_date_str = end.isoformat()

    discounts_data = []
    store_summary = defaultdict(lambda: {"count": 0, "save": 0.0})
    daily_breakdown = defaultdict(list)
    global daily_items
    daily_items = {sid: defaultdict(lambda: {"count": 0, "orig": 0.0, "adj": 0.0, "save": 0.0}) for sid in selected_stores}
    enable_toolbar = create_toolbar(window, txt, "Discounts Report", discounts_data, store_summary, daily_breakdown, start_date_str, end_date_str, selected_stores, daily_items, config_emails, config_smtp)
    log_error("Toolbar created", endpoint=ENDPOINT_NAME)

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

    def flatten(items):
        out = []
        for it in items or []:
            out.append(it)
            out += flatten(it.get("modifiers", []) + it.get("addons", []) + it.get("extras", []))
        return out

    def scan_item(it, dmap, smap, dimap, sid, day_str):
        code = (it.get("discountCode") or "").strip()
        desc = (it.get("discount") or it.get("description", "")).strip()
        orig = float(it.get("originalPrice") or 0)
        adj = float(it.get("adjustedPrice") or orig)
        save = orig - adj
        if code and save > 0:
            key = f"{code}|{desc}"
            e = dmap.setdefault(key, {
                "code": code, "desc": desc,
                "count": 0, "orig": 0.0, "adj": 0.0, "save": 0.0,
                "stores": {}
            })
            e["count"] += 1
            e["orig"] += orig
            e["adj"] += adj
            e["save"] += save

            se = e["stores"].setdefault(sid, {
                "count": 0, "orig": 0.0, "adj": 0.0, "save": 0.0
            })
            se["count"] += 1
            se["orig"] += orig
            se["adj"] += adj
            se["save"] += save

            sm = smap.setdefault(sid, {"count": 0, "save": 0.0})
            sm["count"] += 1
            sm["save"] += save

            de = dimap.setdefault(day_str, {}).setdefault(key, {
                "code": code, "desc": desc,
                "count": 0, "orig": 0.0, "adj": 0.0, "save": 0.0
            })
            de["count"] += 1
            de["orig"] += orig
            de["adj"] += adj
            de["save"] += save

            pe = daily_items[sid].setdefault((code, desc), {
                "count": 0, "orig": 0.0, "adj": 0.0, "save": 0.0
            })
            pe["count"] += 1
            pe["orig"] += orig
            pe["adj"] += adj
            pe["save"] += save

        for sub in it.get("modifiers", []) + it.get("addons", []) + it.get("extras", []):
            scan_item(sub, dmap, smap, dimap, sid, day_str)

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

            s_str, e_str = start.isoformat(), end.isoformat()
            log(f"Discounts: {s_str} → {e_str}", "title")
            log(f"Fetching data for {len(store_map)} stores...", "sep")
            log("", None)

            discount_map = {}
            store_sum = defaultdict(lambda: {"count": 0, "save": 0.0})
            daily_discounts = defaultdict(lambda: defaultdict(lambda: {"count": 0, "orig": 0.0, "adj": 0.0, "save": 0.0}))
            global daily_items

            days = []
            current = start
            while current <= end:
                days.append(current)
                current += timedelta(days=1)

            futures = {}
            lock = threading.Lock()
            with ThreadPoolExecutor(max_workers=config_max_workers) as ex:
                for sid, (name, cid, ckey) in store_map.items():
                    for day in days:
                        day_str = day.isoformat()
                        fut = ex.submit(fetch_data, ENDPOINT_NAME, sid, day_str, day_str, cid, ckey)
                        futures[fut] = (sid, day_str, cid, ckey)

                for fut in as_completed(futures):
                    sid, day_str, cid, ckey = futures[fut]
                    try:
                        res = fut.result()
                        log_error(f"API response for store {sid} on {day_str}: {json.dumps(res, indent=2)}", endpoint=ENDPOINT_NAME)
                    except RateLimitError as ex:
                        log_error(f"Rate limit for store {sid} on {day_str}: {ex}", endpoint=ENDPOINT_NAME)
                        log(f"⚠️ Store {sid} on {day_str}: Rate limit hit; skipping.", "sep")
                        continue
                    except Exception as ex:
                        log_error(f"Fetch failed for store {sid} on {day_str}: {ex}", endpoint=ENDPOINT_NAME)
                        log(f"❌ Store {sid} on {day_str}: Exception: {ex}", "sep")
                        continue

                    err = res.get("error")
                    if err:
                        log_error(f"API error for store {sid} on {day_str}: {err}", endpoint=ENDPOINT_NAME)
                        log(f"❌ Store {sid} on {day_str}: {err}", "sep")
                        continue

                    items = []
                    for txn in res.get("data", []):
                        items += flatten(txn.get("items", []))
                    with lock:
                        for it in items:
                            scan_item(it, discount_map, store_sum, daily_discounts, sid, day_str)

            if not discount_map:
                log("No discounts found.", "sep")
                log_error("No discounts found", endpoint=ENDPOINT_NAME)
            else:
                discounts_data.clear()
                discounts_data.extend(sorted(discount_map.values(), key=lambda x: x["count"], reverse=True))

                for sid in sorted(store_sum):
                    store_summary[sid] = store_sum[sid]

                daily_breakdown.clear()
                for date_str in daily_discounts:
                    daily_breakdown[date_str] = [{"code": d["code"], "desc": d["desc"], "count": d["count"], "orig": d["orig"], "adj": d["adj"], "save": d["save"]} for d in sorted(daily_discounts[date_str].values(), key=lambda x: x["count"], reverse=True)]

                for d in discounts_data:
                    header = f"{d['desc'][:25]}  ({d['code']})"
                    log(header, "title")
                    sub = f"{'Store':>6} | {'Count':>7} | {'Orig':>7} | {'Adj':>7} | {'Disc':>7} | {'Total':>7}"
                    log(sub, "heading")
                    log("─" * len(sub), "sep")
                    for sid, se in sorted(d["stores"].items()):
                        count = se["count"]
                        total_orig = se["orig"]
                        total_adj = se["adj"]
                        avg_orig = total_orig / count
                        avg_adj = total_adj / count
                        unit_save = round(avg_orig - avg_adj, 2)
                        total = unit_save * count
                        row = f"{sid:>6} | {count:>7} | {avg_orig:>7.2f} | {avg_adj:>7.2f} | {unit_save:>7.2f} | {total:>7.2f}"
                        log(row)
                    log("", None)

                log("Per-Discount Averages", "title")
                log(f"{'Code':<6} | {'Count':>7} | {'Total':>7}", "heading")
                log("─" * 28, "sep")
                for d in discounts_data:
                    log(f"{d['code']:<6} | {d['count']:>7} | {d['save']:>7.2f}")

                if start != end:
                    log("", None)
                    log("Daily Breakdown", "title")
                    hdr = f"{'Code':<6} | {'Desc':<25} | {'Count':>7} | {'Orig':>7} | {'Adj':>7} | {'Disc':>7} | {'Total':>7}"
                    log(hdr, "heading")
                    log("─" * len(hdr), "sep")
                    for date_str in sorted(daily_breakdown):
                        log(f"Date: {date_str}", "title")
                        for d in daily_breakdown[date_str]:
                            avg_orig = d["orig"]/d["count"] if d["count"] > 0 else 0
                            avg_adj = d["adj"]/d["count"] if d["count"] > 0 else 0
                            disc = avg_orig - avg_adj
                            total = disc * d["count"]
                            log(f"{d['code']:<6} | {d['desc'][:25]:<25} | {d['count']:>7} | {avg_orig:>7.2f} | {avg_adj:>7.2f} | {disc:>7.2f} | {total:>7.2f}")
                        log("", None)

                if any(len(daily_items[sid]) > 0 for sid in daily_items):
                    log("", None)
                    log("Per-Store Breakdown", "title")
                    for sid in sorted(daily_items.keys()):
                        if len(daily_items[sid]) > 0:
                            log(f"Store {sid}", "title")
                            sub = f"{'Code':<6} | {'Desc':<25} | {'Count':>7} | {'Orig':>7} | {'Adj':>7} | {'Disc':>7} | {'Total':>7}"
                            log(sub, "heading")
                            log("─" * len(sub), "sep")
                            for (code, desc), se in sorted(daily_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                                avg_orig = se["orig"]/se["count"] if se["count"] > 0 else 0
                                avg_adj = se["adj"]/se["count"] if se["count"] > 0 else 0
                                disc = avg_orig - avg_adj
                                total = disc * se["count"]
                                log(f"{code:<6} | {desc[:25]:<25} | {se['count']:>7} | {avg_orig:>7.2f} | {avg_adj:>7.2f} | {disc:>7.2f} | {total:>7.2f}")
                            log("", None)

                log("", None)
                log("Store Summary", "title")
                log(f"{'Store':>6} | {'Count':>7} | {'Total':>7}", "heading")
                log("─" * 28, "sep")
                total_count = sum(ss["count"] for ss in store_summary.values())
                total_save = sum(ss["save"] for ss in store_summary.values())
                for sid in sorted(store_summary):
                    ss = store_summary[sid]
                    log(f"{sid:>6} | {ss['count']:>7} | {ss['save']:>7.2f}")
                log(f"{'All':>6} | {total_count:>7} | {total_save:>7.2f}")

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