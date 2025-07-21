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
    """Generate unique filename in reports/ dir (Items-Sold-XXXX.ext, alphanumeric)."""
    reports_dir = os.path.join(SCRIPT_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=4))
        fname = os.path.join(reports_dir, f"Items-Sold-{code}.{ext.lower()}")
        if not os.path.exists(fname):
            return fname

def create_toolbar(window, txt, title, items_data, store_summary, daily_breakdown, start_date, end_date, selected_stores):
    """Create revamped toolbar with Export .PDF/.JSON/.TXT/.CSV, Email, Copy."""
    toolbar = tk.Frame(window, bg="#f0f0f0")
    toolbar.pack(fill="x", pady=(8, 0), padx=8)
    copy_btn = tk.Button(toolbar, text="Copy", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    copy_btn.pack(side="right", padx=4)
    print_btn = tk.Button(toolbar, text="Print", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    print_btn.pack(side="right", padx=4)
    email_btn = tk.Button(toolbar, text="Email", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                          command=lambda: open_email_dialog(window, txt, items_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores))
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
                writer.writerow(["All Items Sold"])
                writer.writerow(["Description", "PLU", "Count", "Total"])
                for entry in items_data:
                    writer.writerow([entry["Description"], entry["PLU"], entry["Count"], entry["Total"]])
                writer.writerow([])
                writer.writerow(["Store Summary"])
                writer.writerow(["Store", "Total Count", "Total Sales"])
                for sid in sorted(store_summary):
                    ss = store_summary[sid]
                    writer.writerow([sid, ss["total_count"], ss["total_sales"]])
                if start_date != end_date:
                    writer.writerow([])
                    writer.writerow(["Daily Breakdown"])
                    writer.writerow(["Date", "Description", "PLU", "Count", "Total"])
                    for date in sorted(daily_breakdown):
                        writer.writerow([f"Date: {date}"])
                        for entry in daily_breakdown[date]:
                            writer.writerow([date, entry["Description"], entry["PLU"], entry["Count"], entry["Total"]])
                writer.writerow([])
                writer.writerow(["Per-Store Breakdown"])
                for sid in sorted(selected_stores, key=int):
                    writer.writerow([f"Store {sid}"])
                    writer.writerow(["Description", "PLU", "Count", "Total"])
                    for (desc, plu), d in sorted(store_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                        writer.writerow([sid, desc, plu, d["count"], d["total"]])
                    writer.writerow([])
        elif fmt == "JSON":
            export_data = {
                "title": title,
                "generated_on": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "date_range": f"{start_date} to {end_date}",
                "stores": sorted(selected_stores),
                "items": items_data,
                "store_summary": [{"Store": sid, "Total Count": ss["total_count"], "Total Sales": ss["total_sales"]} for sid, ss in store_summary.items()],
            }
            if start_date != end_date:
                export_data["daily_breakdown"] = {date: entries for date, entries in daily_breakdown.items()}
            export_data["per_store_breakdown"] = {
                sid: [{"Description": desc, "PLU": plu, "Count": d["count"], "Total": d["total"]} for (desc, plu), d in sorted(store_items[sid].items(), key=lambda x: x[1]["count"], reverse=True)]
                for sid in sorted(selected_stores, key=int)
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
                elements.append(Paragraph("All Items Sold", styles["Heading2"]))
                for entry in items_data:
                    text = f"Description: {entry['Description']}<br/>PLU: {entry['PLU']}<br/>Count: {entry['Count']}<br/>Total: {entry['Total']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                for sid, ss in store_summary.items():
                    text = f"Store: {sid}<br/>Total Count: {ss['total_count']}<br/>Total Sales: {ss['total_sales']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                if start_date != end_date:
                    elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                    for date in sorted(daily_breakdown):
                        elements.append(Paragraph(f"Date: {date}", styles["Heading3"]))
                        for entry in daily_breakdown[date]:
                            text = f"Description: {entry['Description']}<br/>PLU: {entry['PLU']}<br/>Count: {entry['Count']}<br/>Total: {entry['Total']:.2f}<br/>"
                            elements.append(Paragraph(text, style))
                            elements.append(Spacer(1, 12))
                elements.append(Paragraph("Per-Store Breakdown", styles["Heading2"]))
                for sid in sorted(selected_stores, key=int):
                    elements.append(Paragraph(f"Store {sid}", styles["Heading3"]))
                    for (desc, plu), d in sorted(store_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                        text = f"Description: {desc}<br/>PLU: {plu}<br/>Count: {d['count']}<br/>Total: {d['total']:.2f}<br/>"
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
                except Exception as sub_e:
                    messagebox.showerror("Open Error", f"Failed to open {fname} in Notepad: {sub_e}. File saved.", parent=window)
            else:
                messagebox.showinfo("Open Info", f"File saved to {fname}. Open manually (error: {e}).", parent=window)

    return enable_toolbar

def open_email_dialog(window, txt, items_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores):
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
                writer.writerow(["All Items Sold"])
                writer.writerow(["Description", "PLU", "Count", "Total"])
                for entry in items_data:
                    writer.writerow([entry["Description"], entry["PLU"], entry["Count"], entry["Total"]])
                writer.writerow([])
                writer.writerow(["Store Summary"])
                writer.writerow(["Store", "Total Count", "Total Sales"])
                for sid in sorted(store_summary):
                    ss = store_summary[sid]
                    writer.writerow([sid, ss["total_count"], ss["total_sales"]])
                if start_date != end_date:
                    writer.writerow([])
                    writer.writerow(["Daily Breakdown"])
                    writer.writerow(["Date", "Description", "PLU", "Count", "Total"])
                    for date in sorted(daily_breakdown):
                        writer.writerow([f"Date: {date}"])
                        for entry in daily_breakdown[date]:
                            writer.writerow([date, entry["Description"], entry["PLU"], entry["Count"], entry["Total"]])
                writer.writerow([])
                writer.writerow(["Per-Store Breakdown"])
                for sid in sorted(selected_stores, key=int):
                    writer.writerow([f"Store {sid}"])
                    writer.writerow(["Description", "PLU", "Count", "Total"])
                    for (desc, plu), d in sorted(store_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                        writer.writerow([sid, desc, plu, d["count"], d["total"]])
                    writer.writerow([])
        elif fmt == "JSON":
            export_data = {
                "title": title,
                "generated_on": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "date_range": f"{start_date} to {end_date}",
                "stores": sorted(selected_stores),
                "items": items_data,
                "store_summary": [{"Store": sid, "Total Count": ss["total_count"], "Total Sales": ss["total_sales"]} for sid, ss in store_summary.items()],
            }
            if start_date != end_date:
                export_data["daily_breakdown"] = {date: entries for date, entries in daily_breakdown.items()}
            export_data["per_store_breakdown"] = {
                sid: [{"Description": desc, "PLU": plu, "Count": d["count"], "Total": d["total"]} for (desc, plu), d in sorted(store_items[sid].items(), key=lambda x: x[1]["count"], reverse=True)]
                for sid in sorted(selected_stores, key=int)
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
                elements.append(Paragraph("All Items Sold", styles["Heading2"]))
                for entry in items_data:
                    text = f"Description: {entry['Description']}<br/>PLU: {entry['PLU']}<br/>Count: {entry['Count']}<br/>Total: {entry['Total']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                for sid, ss in store_summary.items():
                    text = f"Store: {sid}<br/>Total Count: {ss['total_count']}<br/>Total Sales: {ss['total_sales']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                if start_date != end_date:
                    elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                    for date in sorted(daily_breakdown):
                        elements.append(Paragraph(f"Date: {date}", styles["Heading3"]))
                        for entry in daily_breakdown[date]:
                            text = f"Description: {entry['Description']}<br/>PLU: {entry['PLU']}<br/>Count: {entry['Count']}<br/>Total: {entry['Total']:.2f}<br/>"
                            elements.append(Paragraph(text, style))
                            elements.append(Spacer(1, 12))
                elements.append(Paragraph("Per-Store Breakdown", styles["Heading2"]))
                for sid in sorted(selected_stores, key=int):
                    elements.append(Paragraph(f"Store {sid}", styles["Heading3"]))
                    for (desc, plu), d in sorted(store_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                        text = f"Description: {desc}<br/>PLU: {plu}<br/>Count: {d['count']}<br/>Total: {d['total']:.2f}<br/>"
                        elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
                doc.build(elements)
            except Exception as e:
                messagebox.showerror("PDF Error", f"Failed to generate PDF: {e}", parent=dialog)
                return
        lines = txt.get("1.0", "end-1c").splitlines()
        subj = "Items-Sold Report"
        if lines and "Items-Sold Report: " in lines[0]:
            subj += " – " + lines[0].split(": ", 1)[1]
        subj = urllib.parse.quote(subj)
        body = urllib.parse.quote("Please see the attached items-sold report.")
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
                writer.writerow(["All Items Sold"])
                writer.writerow(["Description", "PLU", "Count", "Total"])
                for entry in items_data:
                    writer.writerow([entry["Description"], entry["PLU"], entry["Count"], entry["Total"]])
                writer.writerow([])
                writer.writerow(["Store Summary"])
                writer.writerow(["Store", "Total Count", "Total Sales"])
                for sid in sorted(store_summary):
                    ss = store_summary[sid]
                    writer.writerow([sid, ss["total_count"], ss["total_sales"]])
                if start_date != end_date:
                    writer.writerow([])
                    writer.writerow(["Daily Breakdown"])
                    writer.writerow(["Date", "Description", "PLU", "Count", "Total"])
                    for date in sorted(daily_breakdown):
                        writer.writerow([f"Date: {date}"])
                        for entry in daily_breakdown[date]:
                            writer.writerow([date, entry["Description"], entry["PLU"], entry["Count"], entry["Total"]])
                writer.writerow([])
                writer.writerow(["Per-Store Breakdown"])
                for sid in sorted(selected_stores, key=int):
                    writer.writerow([f"Store {sid}"])
                    writer.writerow(["Description", "PLU", "Count", "Total"])
                    for (desc, plu), d in sorted(store_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                        writer.writerow([sid, desc, plu, d["count"], d["total"]])
                    writer.writerow([])
        elif fmt == "JSON":
            export_data = {
                "title": title,
                "generated_on": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "date_range": f"{start_date} to {end_date}",
                "stores": sorted(selected_stores),
                "items": items_data,
                "store_summary": [{"Store": sid, "Total Count": ss["total_count"], "Total Sales": ss["total_sales"]} for sid, ss in store_summary.items()],
            }
            if start_date != end_date:
                export_data["daily_breakdown"] = {date: entries for date, entries in daily_breakdown.items()}
            export_data["per_store_breakdown"] = {
                sid: [{"Description": desc, "PLU": plu, "Count": d["count"], "Total": d["total"]} for (desc, plu), d in sorted(store_items[sid].items(), key=lambda x: x[1]["count"], reverse=True)]
                for sid in sorted(selected_stores, key=int)
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
                elements.append(Paragraph("All Items Sold", styles["Heading2"]))
                for entry in items_data:
                    text = f"Description: {entry['Description']}<br/>PLU: {entry['PLU']}<br/>Count: {entry['Count']}<br/>Total: {entry['Total']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                for sid, ss in store_summary.items():
                    text = f"Store: {sid}<br/>Total Count: {ss['total_count']}<br/>Total Sales: {ss['total_sales']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                if start_date != end_date:
                    elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                    for date in sorted(daily_breakdown):
                        elements.append(Paragraph(f"Date: {date}", styles["Heading3"]))
                        for entry in daily_breakdown[date]:
                            text = f"Description: {entry['Description']}<br/>PLU: {entry['PLU']}<br/>Count: {entry['Count']}<br/>Total: {entry['Total']:.2f}<br/>"
                            elements.append(Paragraph(text, style))
                            elements.append(Spacer(1, 12))
                elements.append(Paragraph("Per-Store Breakdown", styles["Heading2"]))
                for sid in sorted(selected_stores, key=int):
                    elements.append(Paragraph(f"Store {sid}", styles["Heading3"]))
                    for (desc, plu), d in sorted(store_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                        text = f"Description: {desc}<br/>PLU: {plu}<br/>Count: {d['count']}<br/>Total: {d['total']:.2f}<br/>"
                        elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
                doc.build(elements)
            except Exception as e:
                messagebox.showerror("PDF Error", f"Failed to generate PDF: {e}", parent=dialog)
                return
        lines = txt.get("1.0", "end-1c").splitlines()
        subj = "Items-Sold Report"
        if lines and "Items-Sold Report: " in lines[0]:
            subj += " – " + lines[0].split(": ", 1)[1]
        try:
            smtp = config_smtp
            msg = MIMEMultipart()
            msg["Subject"] = subj
            msg["From"] = smtp["from"]
            msg["To"] = ", ".join(selected)
            msg.attach(MIMEText("Please see the attached items-sold report."))
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

def run(window):
    """Run the Items-Sold report for selected stores and date range."""
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

    window.title("Items-Sold Report")
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

    items_data = []
    store_summary = defaultdict(lambda: {"total_count": 0, "total_sales": 0.0})
    daily_breakdown = defaultdict(list)
    global store_items
    store_items = {sid: defaultdict(lambda: {"count": 0, "total": 0.0}) for sid in selected_stores}
    enable_toolbar = create_toolbar(window, txt, "Items-Sold Report", items_data, store_summary, daily_breakdown, start_date_str, end_date_str, selected_stores)
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

    def flatten_items(items):
        flattened = []
        for item in items or []:
            flattened.append(item)
            for key in ['modifiers', 'addons', 'extras']:
                if key in item and isinstance(item[key], list):
                    flattened.extend(flatten_items(item[key]))
        return flattened

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
            log(f"Items-Sold Report: {s_str} to {e_str}", "title")
            log(f"Fetching data for {len(store_map)} stores...", "sep")
            log("", None)

            all_items = defaultdict(lambda: {"count": 0, "total": 0.0})
            global store_items
            daily_items = defaultdict(lambda: defaultdict(lambda: {"count": 0, "total": 0.0}))

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

                    data = res.get("data", []) or []
                    for txn in data:
                        items = flatten_items(txn.get("items", []))
                        for item in items:
                            if item.get("type", "").lower() == "sale":
                                desc = item.get("description", "Unknown")
                                plu = item.get("plu", "N/A")
                                key = (desc, plu)
                                qty = item.get("quantity", 1)
                                price = float(item.get("adjustedPrice", 0.0)) * qty
                                with lock:
                                    all_items[key]["count"] += qty
                                    all_items[key]["total"] += price
                                    store_items[sid][key]["count"] += qty
                                    store_items[sid][key]["total"] += price
                                    daily_items[day_str][key]["count"] += qty
                                    daily_items[day_str][key]["total"] += price

            items_data.clear()
            items_data.extend([{"Description": desc, "PLU": plu, "Count": all_items[(desc, plu)]["count"], "Total": all_items[(desc, plu)]["total"]} for (desc, plu) in sorted(all_items, key=lambda k: all_items[k]["count"], reverse=True)])

            for sid in store_items:
                total_count = sum(d["count"] for d in store_items[sid].values())
                total_sales = sum(d["total"] for d in store_items[sid].values())
                store_summary[sid] = {"total_count": total_count, "total_sales": total_sales}

            daily_breakdown.clear()
            for date in daily_items:
                daily_breakdown[date] = [{"Description": desc, "PLU": plu, "Count": daily_items[date][(desc, plu)]["count"], "Total": daily_items[date][(desc, plu)]["total"]} for (desc, plu) in sorted(daily_items[date], key=lambda k: daily_items[date][k]["count"], reverse=True)]

            log("", None)
            log("All Items Sold" if start == end else "All Items Sold (Aggregated)", "title")
            hdr = f"{'Description':<25} | {'PLU':>6} | {'Count':>10} | {'Total':>10}"
            log(hdr, "heading")
            log("─" * len(hdr), "sep")
            for entry in items_data:
                log(f"{entry['Description'][:25]:<25} | {entry['PLU']:>6} | {entry['Count']:>10} | {entry['Total']:>10.2f}")

            if start != end:
                for date in sorted(daily_breakdown):
                    log("", None)
                    log(f"Items Sold on {date}", "title")
                    log(hdr, "heading")
                    log("─" * len(hdr), "sep")
                    for entry in daily_breakdown[date]:
                        log(f"{entry['Description'][:25]:<25} | {entry['PLU']:>6} | {entry['Count']:>10} | {entry['Total']:>10.2f}")

            log("", None)
            log("Store Summary", "title")
            log(f"{'Store':>6} | {'Total Count':>12} | {'Total Sales':>12}", "heading")
            log("─" * 37, "sep")
            for sid in sorted(store_summary.keys()):
                ss = store_summary[sid]
                log(f"{sid:>6} | {ss['total_count']:>12} | {ss['total_sales']:>12.2f}")

            log("", None)
            log("Per-Store Item Summaries", "title")
            for sid in sorted(store_items.keys()):
                log("", None)
                log(f"Items Sold at Store {sid}", "title")
                log(hdr, "heading")
                log("─" * len(hdr), "sep")
                for (desc, plu), d in sorted(store_items[sid].items(), key=lambda x: x[1]["count"], reverse=True):
                    log(f"{desc[:25]:<25} | {plu:>6} | {d['count']:>10} | {d['total']:>10.2f}")

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