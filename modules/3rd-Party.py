import string
import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import messagebox, simpledialog, filedialog, Toplevel, StringVar
from datetime import datetime, timedelta
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

TP_ENDPOINT = "Third Party Sales Summary"
MAX_DAYS = 7
SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def generate_unique_filename(ext):
    """Generate unique filename in reports/ dir (3rd-Party-XXXX.ext, alphanumeric)."""
    reports_dir = os.path.join(SCRIPT_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=4))
        fname = os.path.join(reports_dir, f"3rd-Party-{code}.{ext.lower()}")
        if not os.path.exists(fname):
            return fname

def create_toolbar(window, txt, title, tp_data, store_summary, daily_breakdown, start_date, end_date, selected_stores):
    """Create revamped toolbar with Export .PDF/.JSON/.TXT/.CSV, Email, Print, Copy."""
    toolbar = tk.Frame(window, bg="#f0f0f0")
    toolbar.pack(fill="x", pady=(8, 0), padx=8)
    copy_btn = tk.Button(toolbar, text="Copy", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    copy_btn.pack(side="right", padx=4)
    print_btn = tk.Button(toolbar, text="Print", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    print_btn.pack(side="right", padx=4)
    email_btn = tk.Button(toolbar, text="Email", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                          command=lambda: open_email_dialog(window, txt, tp_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores))
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
        print_btn.config(state=tk.NORMAL, command=print_content)
        email_btn.config(state=tk.NORMAL)
        csv_btn.config(state=tk.NORMAL, command=lambda: export_file("CSV"))
        txt_btn.config(state=tk.NORMAL, command=lambda: export_file("TXT"))
        json_btn.config(state=tk.NORMAL, command=lambda: export_file("JSON"))
        if REPORTLAB_AVAILABLE:
            pdf_btn.config(state=tk.NORMAL, command=lambda: export_file("PDF"))

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
            elements.append(Paragraph(f"Stores: {', '.join(sorted(selected_stores))}", styles["Normal"]))
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Individual Entries", styles["Heading2"]))
            for entry in tp_data:
                text = f"Store: {entry['Store']}<br/>TotSales: {entry['TotSales']:.2f}<br/>TotNet: {entry['TotNet']:.2f}<br/>TotTxns: {entry['TotTxns']}<br/>DD-T: {entry['DD-T']}<br/>DD-N: {entry['DD-N']:.2f}<br/>DD-S: {entry['DD-S']:.2f}<br/>GH-T: {entry['GH-T']}<br/>GH-N: {entry['GH-N']:.2f}<br/>GH-S: {entry['GH-S']:.2f}<br/>UE-T: {entry['UE-T']}<br/>UE-N: {entry['UE-N']:.2f}<br/>UE-S: {entry['UE-S']:.2f}<br/>EC-T: {entry['EC-T']}<br/>EC-N: {entry['EC-N']:.2f}<br/>EC-S: {entry['EC-S']:.2f}<br/>"
                elements.append(Paragraph(text, style))
                elements.append(Spacer(1, 12))
            elements.append(Paragraph("Store Summary", styles["Heading2"]))
            for ss in store_summary.values():
                text = f"Store: {ss['Store']}<br/>TotSales: {ss['TotSales']:.2f}<br/>TotNet: {ss['TotNet']:.2f}<br/>TotTxns: {ss['TotTxns']}<br/>DD-T: {ss['DD-T']}<br/>DD-N: {ss['DD-N']:.2f}<br/>DD-S: {ss['DD-S']:.2f}<br/>GH-T: {ss['GH-T']}<br/>GH-N: {ss['GH-N']:.2f}<br/>GH-S: {ss['GH-S']:.2f}<br/>UE-T: {ss['UE-T']}<br/>UE-N: {ss['UE-N']:.2f}<br/>UE-S: {ss['UE-S']:.2f}<br/>EC-T: {ss['EC-T']}<br/>EC-N: {ss['EC-N']:.2f}<br/>EC-S: {ss['EC-S']:.2f}<br/>"
                elements.append(Paragraph(text, style))
                elements.append(Spacer(1, 12))
            elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
            for date, entries in daily_breakdown.items():
                elements.append(Paragraph(f"Date: {date}", styles["Heading3"]))
                for entry in entries:
                    text = f"Store: {entry['Store']}<br/>TotSales: {entry['TotSales']:.2f}<br/>TotNet: {entry['TotNet']:.2f}<br/>TotTxns: {entry['TotTxns']}<br/>DD-T: {entry['DD-T']}<br/>DD-N: {entry['DD-N']:.2f}<br/>DD-S: {entry['DD-S']:.2f}<br/>GH-T: {entry['GH-T']}<br/>GH-N: {entry['GH-N']:.2f}<br/>GH-S: {entry['GH-S']:.2f}<br/>UE-T: {entry['UE-T']}<br/>UE-N: {entry['UE-N']:.2f}<br/>UE-S: {entry['UE-S']:.2f}<br/>EC-T: {entry['EC-T']}<br/>EC-N: {entry['EC-N']:.2f}<br/>EC-S: {entry['EC-S']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
            doc.build(elements)
            os.startfile(fname, "print")
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to generate/print PDF: {e}", parent=window)
        finally:
            if os.path.exists(fname):
                os.unlink(fname)

    def export_file(fmt):
        fname = generate_unique_filename(fmt)
        if fmt == "CSV":
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                writer.writeheader()
                writer.writerows(tp_data)
                f.write("\nStore Summary\n")
                store_writer = csv.DictWriter(f, fieldnames=["Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                store_writer.writeheader()
                for sid, ss in store_summary.items():
                    store_writer.writerow(ss)
                f.write("\nDaily Breakdown\n")
                daily_writer = csv.DictWriter(f, fieldnames=["Date", "Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                daily_writer.writeheader()
                for date in sorted(daily_breakdown):
                    for entry in daily_breakdown[date]:
                        entry["Date"] = date
                        daily_writer.writerow(entry)
        elif fmt == "JSON":
            export_data = {
                "entries": tp_data,
                "store_summary": [ss for ss in store_summary.values()],
                "daily_breakdown": {date: entries for date, entries in daily_breakdown.items()}
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
                elements.append(Paragraph("Individual Entries", styles["Heading2"]))
                for entry in tp_data:
                    text = f"Store: {entry['Store']}<br/>TotSales: {entry['TotSales']:.2f}<br/>TotNet: {entry['TotNet']:.2f}<br/>TotTxns: {entry['TotTxns']}<br/>DD-T: {entry['DD-T']}<br/>DD-N: {entry['DD-N']:.2f}<br/>DD-S: {entry['DD-S']:.2f}<br/>GH-T: {entry['GH-T']}<br/>GH-N: {entry['GH-N']:.2f}<br/>GH-S: {entry['GH-S']:.2f}<br/>UE-T: {entry['UE-T']}<br/>UE-N: {entry['UE-N']:.2f}<br/>UE-S: {entry['UE-S']:.2f}<br/>EC-T: {entry['EC-T']}<br/>EC-N: {entry['EC-N']:.2f}<br/>EC-S: {entry['EC-S']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                for ss in store_summary.values():
                    text = f"Store: {ss['Store']}<br/>TotSales: {ss['TotSales']:.2f}<br/>TotNet: {ss['TotNet']:.2f}<br/>TotTxns: {ss['TotTxns']}<br/>DD-T: {ss['DD-T']}<br/>DD-N: {ss['DD-N']:.2f}<br/>DD-S: {ss['DD-S']:.2f}<br/>GH-T: {ss['GH-T']}<br/>GH-N: {ss['GH-N']:.2f}<br/>GH-S: {ss['GH-S']:.2f}<br/>UE-T: {ss['UE-T']}<br/>UE-N: {ss['UE-N']:.2f}<br/>UE-S: {ss['UE-S']:.2f}<br/>EC-T: {ss['EC-T']}<br/>EC-N: {ss['EC-N']:.2f}<br/>EC-S: {ss['EC-S']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                for date, entries in daily_breakdown.items():
                    elements.append(Paragraph(f"Date: {date}", styles["Heading3"]))
                    for entry in entries:
                        text = f"Store: {entry['Store']}<br/>TotSales: {entry['TotSales']:.2f}<br/>TotNet: {entry['TotNet']:.2f}<br/>TotTxns: {entry['TotTxns']}<br/>DD-T: {entry['DD-T']}<br/>DD-N: {entry['DD-N']:.2f}<br/>DD-S: {entry['DD-S']:.2f}<br/>GH-T: {entry['GH-T']}<br/>GH-N: {entry['GH-N']:.2f}<br/>GH-S: {entry['GH-S']:.2f}<br/>UE-T: {entry['UE-T']}<br/>UE-N: {entry['UE-N']:.2f}<br/>UE-S: {entry['UE-S']:.2f}<br/>EC-T: {entry['EC-T']}<br/>EC-N: {entry['EC-N']:.2f}<br/>EC-S: {entry['EC-S']:.2f}<br/>"
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

def open_email_dialog(window, txt, tp_data, store_summary, daily_breakdown, title, start_date, end_date, selected_stores):
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
        # Generate file content
        if fmt == "CSV":
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                writer.writeheader()
                writer.writerows(tp_data)
                f.write("\nStore Summary\n")
                store_writer = csv.DictWriter(f, fieldnames=["Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                store_writer.writeheader()
                for sid, ss in store_summary.items():
                    store_writer.writerow(ss)
                f.write("\nDaily Breakdown\n")
                daily_writer = csv.DictWriter(f, fieldnames=["Date", "Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                daily_writer.writeheader()
                for date in sorted(daily_breakdown):
                    for entry in daily_breakdown[date]:
                        entry["Date"] = date
                        daily_writer.writerow(entry)
        elif fmt == "JSON":
            export_data = {
                "entries": tp_data,
                "store_summary": [ss for ss in store_summary.values()],
                "daily_breakdown": {date: entries for date, entries in daily_breakdown.items()}
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
                elements.append(Paragraph("Individual Entries", styles["Heading2"]))
                for entry in tp_data:
                    text = f"Store: {entry['Store']}<br/>TotSales: {entry['TotSales']:.2f}<br/>TotNet: {entry['TotNet']:.2f}<br/>TotTxns: {entry['TotTxns']}<br/>DD-T: {entry['DD-T']}<br/>DD-N: {entry['DD-N']:.2f}<br/>DD-S: {entry['DD-S']:.2f}<br/>GH-T: {entry['GH-T']}<br/>GH-N: {entry['GH-N']:.2f}<br/>GH-S: {entry['GH-S']:.2f}<br/>UE-T: {entry['UE-T']}<br/>UE-N: {entry['UE-N']:.2f}<br/>UE-S: {entry['UE-S']:.2f}<br/>EC-T: {entry['EC-T']}<br/>EC-N: {entry['EC-N']:.2f}<br/>EC-S: {entry['EC-S']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                for ss in store_summary.values():
                    text = f"Store: {ss['Store']}<br/>TotSales: {ss['TotSales']:.2f}<br/>TotNet: {ss['TotNet']:.2f}<br/>TotTxns: {ss['TotTxns']}<br/>DD-T: {ss['DD-T']}<br/>DD-N: {ss['DD-N']:.2f}<br/>DD-S: {ss['DD-S']:.2f}<br/>GH-T: {ss['GH-T']}<br/>GH-N: {ss['GH-N']:.2f}<br/>GH-S: {ss['GH-S']:.2f}<br/>UE-T: {ss['UE-T']}<br/>UE-N: {ss['UE-N']:.2f}<br/>UE-S: {ss['UE-S']:.2f}<br/>EC-T: {ss['EC-T']}<br/>EC-N: {ss['EC-N']:.2f}<br/>EC-S: {ss['EC-S']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                for date, entries in daily_breakdown.items():
                    elements.append(Paragraph(f"Date: {date}", styles["Heading3"]))
                    for entry in entries:
                        text = f"Store: {entry['Store']}<br/>TotSales: {entry['TotSales']:.2f}<br/>TotNet: {entry['TotNet']:.2f}<br/>TotTxns: {entry['TotTxns']}<br/>DD-T: {entry['DD-T']}<br/>DD-N: {entry['DD-N']:.2f}<br/>DD-S: {entry['DD-S']:.2f}<br/>GH-T: {entry['GH-T']}<br/>GH-N: {entry['GH-N']:.2f}<br/>GH-S: {entry['GH-S']:.2f}<br/>UE-T: {entry['UE-T']}<br/>UE-N: {entry['UE-N']:.2f}<br/>UE-S: {entry['UE-S']:.2f}<br/>EC-T: {entry['EC-T']}<br/>EC-N: {entry['EC-N']:.2f}<br/>EC-S: {entry['EC-S']:.2f}<br/>"
                        elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
                doc.build(elements)
            except Exception as e:
                messagebox.showerror("PDF Error", f"Failed to generate PDF: {e}", parent=dialog)
                return
        lines = txt.get("1.0", "end-1c").splitlines()
        subj = "3rd-Party Report"
        if lines and "3rd-Party Sales: " in lines[0]:
            subj += " – " + lines[0].split(": ", 1)[1]
        subj = urllib.parse.quote(subj)
        body = urllib.parse.quote("Please see the attached 3rd-party report.")
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
        # Generate file content
        if fmt == "CSV":
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                writer.writeheader()
                writer.writerows(tp_data)
                f.write("\nStore Summary\n")
                store_writer = csv.DictWriter(f, fieldnames=["Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                store_writer.writeheader()
                for sid, ss in store_summary.items():
                    store_writer.writerow(ss)
                f.write("\nDaily Breakdown\n")
                daily_writer = csv.DictWriter(f, fieldnames=["Date", "Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                daily_writer.writeheader()
                for date in sorted(daily_breakdown):
                    for entry in daily_breakdown[date]:
                        entry["Date"] = date
                        daily_writer.writerow(entry)
        elif fmt == "JSON":
            export_data = {
                "entries": tp_data,
                "store_summary": [ss for ss in store_summary.values()],
                "daily_breakdown": {date: entries for date, entries in daily_breakdown.items()}
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
                elements.append(Paragraph("Individual Entries", styles["Heading2"]))
                for entry in tp_data:
                    text = f"Store: {entry['Store']}<br/>TotSales: {entry['TotSales']:.2f}<br/>TotNet: {entry['TotNet']:.2f}<br/>TotTxns: {entry['TotTxns']}<br/>DD-T: {entry['DD-T']}<br/>DD-N: {entry['DD-N']:.2f}<br/>DD-S: {entry['DD-S']:.2f}<br/>GH-T: {entry['GH-T']}<br/>GH-N: {entry['GH-N']:.2f}<br/>GH-S: {entry['GH-S']:.2f}<br/>UE-T: {entry['UE-T']}<br/>UE-N: {entry['UE-N']:.2f}<br/>UE-S: {entry['UE-S']:.2f}<br/>EC-T: {entry['EC-T']}<br/>EC-N: {entry['EC-N']:.2f}<br/>EC-S: {entry['EC-S']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                for ss in store_summary.values():
                    text = f"Store: {ss['Store']}<br/>TotSales: {ss['TotSales']:.2f}<br/>TotNet: {ss['TotNet']:.2f}<br/>TotTxns: {ss['TotTxns']}<br/>DD-T: {ss['DD-T']}<br/>DD-N: {ss['DD-N']:.2f}<br/>DD-S: {ss['DD-S']:.2f}<br/>GH-T: {ss['GH-T']}<br/>GH-N: {ss['GH-N']:.2f}<br/>GH-S: {ss['GH-S']:.2f}<br/>UE-T: {ss['UE-T']}<br/>UE-N: {ss['UE-N']:.2f}<br/>UE-S: {ss['UE-S']:.2f}<br/>EC-T: {ss['EC-T']}<br/>EC-N: {ss['EC-N']:.2f}<br/>EC-S: {ss['EC-S']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                for date, entries in daily_breakdown.items():
                    elements.append(Paragraph(f"Date: {date}", styles["Heading3"]))
                    for entry in entries:
                        text = f"Store: {entry['Store']}<br/>TotSales: {entry['TotSales']:.2f}<br/>TotNet: {entry['TotNet']:.2f}<br/>TotTxns: {entry['TotTxns']}<br/>DD-T: {entry['DD-T']}<br/>DD-N: {entry['DD-N']:.2f}<br/>DD-S: {entry['DD-S']:.2f}<br/>GH-T: {entry['GH-T']}<br/>GH-N: {entry['GH-N']:.2f}<br/>GH-S: {entry['GH-S']:.2f}<br/>UE-T: {entry['UE-T']}<br/>UE-N: {entry['UE-N']:.2f}<br/>UE-S: {entry['UE-S']:.2f}<br/>EC-T: {entry['EC-T']}<br/>EC-N: {entry['EC-N']:.2f}<br/>EC-S: {entry['EC-S']:.2f}<br/>"
                        elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
                doc.build(elements)
            except Exception as e:
                messagebox.showerror("PDF Error", f"Failed to generate PDF: {e}", parent=dialog)
                return
        lines = txt.get("1.0", "end-1c").splitlines()
        subj = "3rd-Party Report"
        if lines and "3rd-Party Sales: " in lines[0]:
            subj += " – " + lines[0].split(": ", 1)[1]
        subj = urllib.parse.quote(subj)
        body = urllib.parse.quote("Please see the attached 3rd-party report.")
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
        # Generate file content
        if fmt == "CSV":
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                writer.writeheader()
                writer.writerows(tp_data)
                f.write("\nStore Summary\n")
                store_writer = csv.DictWriter(f, fieldnames=["Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                store_writer.writeheader()
                for sid, ss in store_summary.items():
                    store_writer.writerow(ss)
                f.write("\nDaily Breakdown\n")
                daily_writer = csv.DictWriter(f, fieldnames=["Date", "Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                daily_writer.writeheader()
                for date in sorted(daily_breakdown):
                    for entry in daily_breakdown[date]:
                        entry["Date"] = date
                        daily_writer.writerow(entry)
        elif fmt == "JSON":
            export_data = {
                "entries": tp_data,
                "store_summary": [ss for ss in store_summary.values()],
                "daily_breakdown": {date: entries for date, entries in daily_breakdown.items()}
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
                elements.append(Paragraph("Individual Entries", styles["Heading2"]))
                for entry in tp_data:
                    text = f"Store: {entry['Store']}<br/>TotSales: {entry['TotSales']:.2f}<br/>TotNet: {entry['TotNet']:.2f}<br/>TotTxns: {entry['TotTxns']}<br/>DD-T: {entry['DD-T']}<br/>DD-N: {entry['DD-N']:.2f}<br/>DD-S: {entry['DD-S']:.2f}<br/>GH-T: {entry['GH-T']}<br/>GH-N: {entry['GH-N']:.2f}<br/>GH-S: {entry['GH-S']:.2f}<br/>UE-T: {entry['UE-T']}<br/>UE-N: {entry['UE-N']:.2f}<br/>UE-S: {entry['UE-S']:.2f}<br/>EC-T: {entry['EC-T']}<br/>EC-N: {entry['EC-N']:.2f}<br/>EC-S: {entry['EC-S']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                for ss in store_summary.values():
                    text = f"Store: {ss['Store']}<br/>TotSales: {ss['TotSales']:.2f}<br/>TotNet: {ss['TotNet']:.2f}<br/>TotTxns: {ss['TotTxns']}<br/>DD-T: {ss['DD-T']}<br/>DD-N: {ss['DD-N']:.2f}<br/>DD-S: {ss['DD-S']:.2f}<br/>GH-T: {ss['GH-T']}<br/>GH-N: {ss['GH-N']:.2f}<br/>GH-S: {ss['GH-S']:.2f}<br/>UE-T: {ss['UE-T']}<br/>UE-N: {ss['UE-N']:.2f}<br/>UE-S: {ss['UE-S']:.2f}<br/>EC-T: {ss['EC-T']}<br/>EC-N: {ss['EC-N']:.2f}<br/>EC-S: {ss['EC-S']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                for date, entries in daily_breakdown.items():
                    elements.append(Paragraph(f"Date: {date}", styles["Heading3"]))
                    for entry in entries:
                        text = f"Store: {entry['Store']}<br/>TotSales: {entry['TotSales']:.2f}<br/>TotNet: {entry['TotNet']:.2f}<br/>TotTxns: {entry['TotTxns']}<br/>DD-T: {entry['DD-T']}<br/>DD-N: {entry['DD-N']:.2f}<br/>DD-S: {entry['DD-S']:.2f}<br/>GH-T: {entry['GH-T']}<br/>GH-N: {entry['GH-N']:.2f}<br/>GH-S: {entry['GH-S']:.2f}<br/>UE-T: {entry['UE-T']}<br/>UE-N: {entry['UE-N']:.2f}<br/>UE-S: {entry['UE-S']:.2f}<br/>EC-T: {entry['EC-T']}<br/>EC-N: {entry['EC-N']:.2f}<br/>EC-S: {entry['EC-S']:.2f}<br/>"
                        elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
                doc.build(elements)
            except Exception as e:
                messagebox.showerror("PDF Error", f"Failed to generate PDF: {e}", parent=dialog)
                return
        lines = txt.get("1.0", "end-1c").splitlines()
        subj = "3rd-Party Report"
        if lines and "3rd-Party Sales: " in lines[0]:
            subj += " – " + lines[0].split(": ", 1)[1]
        subj = urllib.parse.quote(subj)
        body = urllib.parse.quote("Please see the attached 3rd-party report.")
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
        # Generate file content
        if fmt == "CSV":
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                writer.writeheader()
                writer.writerows(tp_data)
                f.write("\nStore Summary\n")
                store_writer = csv.DictWriter(f, fieldnames=["Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                store_writer.writeheader()
                for sid, ss in store_summary.items():
                    store_writer.writerow(ss)
                f.write("\nDaily Breakdown\n")
                daily_writer = csv.DictWriter(f, fieldnames=["Date", "Store", "TotSales", "TotNet", "TotTxns", "DD-T", "DD-N", "DD-S", "GH-T", "GH-N", "GH-S", "UE-T", "UE-N", "UE-S", "EC-T", "EC-N", "EC-S"])
                daily_writer.writeheader()
                for date in sorted(daily_breakdown):
                    for entry in daily_breakdown[date]:
                        entry["Date"] = date
                        daily_writer.writerow(entry)
        elif fmt == "JSON":
            export_data = {
                "entries": tp_data,
                "store_summary": [ss for ss in store_summary.values()],
                "daily_breakdown": {date: entries for date, entries in daily_breakdown.items()}
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
                elements.append(Paragraph("Individual Entries", styles["Heading2"]))
                for entry in tp_data:
                    text = f"Store: {entry['Store']}<br/>TotSales: {entry['TotSales']:.2f}<br/>TotNet: {entry['TotNet']:.2f}<br/>TotTxns: {entry['TotTxns']}<br/>DD-T: {entry['DD-T']}<br/>DD-N: {entry['DD-N']:.2f}<br/>DD-S: {entry['DD-S']:.2f}<br/>GH-T: {entry['GH-T']}<br/>GH-N: {entry['GH-N']:.2f}<br/>GH-S: {entry['GH-S']:.2f}<br/>UE-T: {entry['UE-T']}<br/>UE-N: {entry['UE-N']:.2f}<br/>UE-S: {entry['UE-S']:.2f}<br/>EC-T: {entry['EC-T']}<br/>EC-N: {entry['EC-N']:.2f}<br/>EC-S: {entry['EC-S']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                for ss in store_summary.values():
                    text = f"Store: {ss['Store']}<br/>TotSales: {ss['TotSales']:.2f}<br/>TotNet: {ss['TotNet']:.2f}<br/>TotTxns: {ss['TotTxns']}<br/>DD-T: {ss['DD-T']}<br/>DD-N: {ss['DD-N']:.2f}<br/>DD-S: {ss['DD-S']:.2f}<br/>GH-T: {ss['GH-T']}<br/>GH-N: {ss['GH-N']:.2f}<br/>GH-S: {ss['GH-S']:.2f}<br/>UE-T: {ss['UE-T']}<br/>UE-N: {ss['UE-N']:.2f}<br/>UE-S: {ss['UE-S']:.2f}<br/>EC-T: {ss['EC-T']}<br/>EC-N: {ss['EC-N']:.2f}<br/>EC-S: {ss['EC-S']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Daily Breakdown", styles["Heading2"]))
                for date, entries in daily_breakdown.items():
                    elements.append(Paragraph(f"Date: {date}", styles["Heading3"]))
                    for entry in entries:
                        text = f"Store: {entry['Store']}<br/>TotSales: {entry['TotSales']:.2f}<br/>TotNet: {entry['TotNet']:.2f}<br/>TotTxns: {entry['TotTxns']}<br/>DD-T: {entry['DD-T']}<br/>DD-N: {entry['DD-N']:.2f}<br/>DD-S: {entry['DD-S']:.2f}<br/>GH-T: {entry['GH-T']}<br/>GH-N: {entry['GH-N']:.2f}<br/>GH-S: {entry['GH-S']:.2f}<br/>UE-T: {entry['UE-T']}<br/>UE-N: {entry['UE-N']:.2f}<br/>UE-S: {entry['UE-S']:.2f}<br/>EC-T: {entry['EC-T']}<br/>EC-N: {entry['EC-N']:.2f}<br/>EC-S: {entry['EC-S']:.2f}<br/>"
                        elements.append(Paragraph(text, style))
                        elements.append(Spacer(1, 12))
                doc.build(elements)
            except Exception as e:
                messagebox.showerror("PDF Error", f"Failed to generate PDF: {e}", parent=dialog)
                return
        lines = txt.get("1.0", "end-1c").splitlines()
        subj = "3rd-Party Report"
        if lines and "3rd-Party Sales: " in lines[0]:
            subj += " – " + lines[0].split(": ", 1)[1]
        try:
            smtp = config_smtp
            msg = MIMEMultipart()
            msg["Subject"] = subj
            msg["From"] = smtp["from"]
            msg["To"] = ", ".join(selected)
            msg.attach(MIMEText("Please see the attached 3rd-party report."))
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
                os.unlink(fname)  # Clean up after SMTP send
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
    """Run the 3rd-Party report for selected stores and date range.
    
    Args:
        window: Tk window to display the report.
    """
    from __main__ import get_selected_start_date, get_selected_end_date, fetch_data, store_vars, config_accounts, handle_rate_limit, log_error, config_max_workers, _password_validated, RateLimitError, config_emails, config_smtp

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
        log_error(f"Date parsing error: {e}", endpoint=TP_ENDPOINT)
        messagebox.showerror("Bad Date", "Could not parse your start/end dates.", parent=window)
        return

    # Set up window
    window.title("3rd-Party Report")
    parent = window.master
    parent.update_idletasks()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    window.geometry(f"{int(window.winfo_screenwidth()*0.6)}x{int(window.winfo_screenheight()*0.6)}+{px}+{py}")
    window.resizable(True, True)
    window.minsize(800, 600)

    # Create ScrolledText but don't pack yet
    txt = ScrolledText(window, wrap="none", font=("Courier New", 11), fg="black", state="normal")

    selected_stores = [s for s, v in store_vars.items() if v.get()]
    start_date_str = start.isoformat()
    end_date_str = end.isoformat()

    # Create toolbar at the top with additional params
    tp_data = []  # Structured data for individual entries
    store_summary = defaultdict(lambda: {"Store": "", "TotSales": 0.0, "TotNet": 0.0, "TotTxns": 0, "DD-T": 0, "DD-N": 0.0, "DD-S": 0.0, "GH-T": 0, "GH-N": 0.0, "GH-S": 0.0, "UE-T": 0, "UE-N": 0.0, "UE-S": 0.0, "EC-T": 0, "EC-N": 0.0, "EC-S": 0.0})
    daily_breakdown = defaultdict(list)  # Date -> list of daily entries
    enable_toolbar = create_toolbar(window, txt, "3rd-Party Report", tp_data, store_summary, daily_breakdown, start_date_str, end_date_str, selected_stores)
    log_error("Toolbar created", endpoint=TP_ENDPOINT)  # Debug log

    # Now pack txt below toolbar
    txt.pack(fill="both", expand=True, padx=8, pady=(4, 8))
    hbar = tk.Scrollbar(window, orient="horizontal", command=txt.xview)
    hbar.pack(fill="x", padx=8)
    txt.configure(xscrollcommand=hbar.set)
    txt.tag_configure("title", font=("Courier New", 12, "bold"), foreground="black")
    txt.tag_configure("heading", font=("Courier New", 11, "bold"), foreground="black")
    txt.tag_configure("sep", foreground="#888888")

    def log(line="", tag=None):
        txt.configure(state="normal")  # Ensure widget is writable
        txt.insert("end", line + "\n", tag or ())
        txt.see("end")
        txt.update()
        txt.configure(state="normal")  # Keep widget in normal state
        log_error(f"Log: {line}", endpoint=TP_ENDPOINT)  # Debug log

    def worker():
        try:
            # Check store selection
            if not selected_stores:
                log("No stores selected.", "sep")
                log_error("No stores selected", endpoint=TP_ENDPOINT)
                window.after(0, enable_toolbar)
                return

            # Build store map
            store_map = {}
            for acct in config_accounts:
                name = acct.get("Name", "")
                cid = acct.get("ClientID", "")
                ckey = acct.get("ClientKEY", "")
                if not all([name, cid, ckey]):
                    log(f"Skipping invalid account: {name or 'Unknown'}", "sep")
                    log_error(f"Invalid account: Name={name}, ClientID={cid}", endpoint=TP_ENDPOINT)
                    continue
                for sid in acct.get("StoreIDs", []):
                    if sid in selected_stores and sid not in store_map:
                        store_map[sid] = (name, cid, ckey)

            if not store_map:
                log("No valid accounts with selected stores found.", "sep")
                log_error("No valid accounts with selected stores", endpoint=TP_ENDPOINT)
                window.after(0, enable_toolbar)
                return

            # Start report
            s_str, e_str = start.isoformat(), end.isoformat()
            log(f"3rd-Party Sales: {s_str} → {e_str}", "title")
            log(f"Fetching data for {len(store_map)} stores…", "sep")
            log("", None)  # Blank line for readability

            # Header for store/day views
            hdr = f"{'Store':>6}  {'TotSales':>10}  {'TotNet':>10}  {'TotTxns':>8}  " \
                  f"{'DD-T':>6} {'DD-N':>8} {'DD-S':>8}  " \
                  f"{'GH-T':>6} {'GH-N':>8} {'GH-S':>8}  " \
                  f"{'UE-T':>6} {'UE-N':>8} {'UE-S':>8}  " \
                  f"{'EC-T':>6} {'EC-N':>8} {'EC-S':>8}"

            # Header for per-store views
            hdr2 = f"{'Date':10}  {'TotSales':>10}  {'TotNet':>10}  {'TotTxns':>8}  " \
                   f"{'DD-T':>6} {'DD-N':>8} {'DD-S':>8}  " \
                   f"{'GH-T':>6} {'GH-N':>8} {'GH-S':>8}  " \
                   f"{'UE-T':>6} {'UE-N':>8} {'UE-S':>8}  " \
                   f"{'EC-T':>6} {'EC-N':>8} {'EC-S':>8}"

            # Generate list of days
            days = []
            current = start
            while current <= end:
                days.append(current)
                current += timedelta(days=1)

            # Fetch data per day per store
            futures = {}
            lock = threading.Lock()
            store_aggregates = defaultdict(lambda: {"TotSales": 0.0, "TotNet": 0.0, "TotTxns": 0, "DD-T": 0, "DD-N": 0.0, "DD-S": 0.0, "GH-T": 0, "GH-N": 0.0, "GH-S": 0.0, "UE-T": 0, "UE-N": 0.0, "UE-S": 0.0, "EC-T": 0, "EC-N": 0.0, "EC-S": 0.0})
            with ThreadPoolExecutor(max_workers=config_max_workers) as ex:
                for sid, (name, cid, ckey) in store_map.items():
                    for day in days:
                        day_str = day.isoformat()
                        fut = ex.submit(fetch_data, TP_ENDPOINT, sid, day_str, day_str, cid, ckey)
                        futures[fut] = (sid, day_str, cid, ckey)

                for fut in as_completed(futures):
                    sid, day_str, cid, ckey = futures[fut]
                    try:
                        res = fut.result()
                        log_error(f"API response for store {sid} on {day_str}: {json.dumps(res, indent=2)}", endpoint=TP_ENDPOINT)
                    except RateLimitError as ex:
                        log_error(f"Rate limit for store {sid} on {day_str}: {ex}", endpoint=TP_ENDPOINT)
                        log(f"⚠️ Store {sid} on {day_str}: Rate limit hit; skipping.", "sep")
                        continue
                    except Exception as ex:
                        log_error(f"Fetch failed for store {sid} on {day_str}: {ex}", endpoint=TP_ENDPOINT)
                        log(f"❌ Store {sid} on {day_str}: Exception: {ex}", "sep")
                        continue

                    err = res.get("error")
                    if err:
                        log_error(f"API error for store {sid} on {day_str}: {err}", endpoint=TP_ENDPOINT)
                        log(f"❌ Store {sid} on {day_str}: {err}", "sep")
                        continue

                    data = res.get("data", res) or []
                    if not data:
                        continue
                    if isinstance(data, dict):
                        data = [data]
                    rec = data[0] if data else {}

                    ts = rec.get("totalSales", 0.0)
                    n = rec.get("totalNetSales", 0.0)
                    tt = rec.get("totalTransactions", 0)
                    provs = rec.get("providers", [])
                    pm = {p.get("provider", "").lower(): p for p in provs}
                    def g(p, k, d=0):
                        return pm.get(p, {}).get(k, d)
                    dd_t = g('doordash', 'transactions')
                    dd_n = g('doordash', 'netSales', 0.0)
                    dd_s = g('doordash', 'sales', 0.0)
                    gh_t = g('grubhub', 'transactions')
                    gh_n = g('grubhub', 'netSales', 0.0)
                    gh_s = g('grubhub', 'sales', 0.0)
                    ue_t = g('uber', 'transactions')
                    ue_n = g('uber', 'netSales', 0.0)
                    ue_s = g('uber', 'sales', 0.0)
                    ec_t = g('ezcater', 'transactions')
                    ec_n = g('ezcater', 'netSales', 0.0)
                    ec_s = g('ezcater', 'sales', 0.0)

                    date = day_str
                    daily_breakdown[date].append({"Store": sid, "TotSales": ts, "TotNet": n, "TotTxns": tt, "DD-T": dd_t, "DD-N": dd_n, "DD-S": dd_s, "GH-T": gh_t, "GH-N": gh_n, "GH-S": gh_s, "UE-T": ue_t, "UE-N": ue_n, "UE-S": ue_s, "EC-T": ec_t, "EC-N": ec_n, "EC-S": ec_s})

                    with lock:
                        agg = store_aggregates[sid]
                        agg["TotSales"] += ts
                        agg["TotNet"] += n
                        agg["TotTxns"] += tt
                        agg["DD-T"] += dd_t
                        agg["DD-N"] += dd_n
                        agg["DD-S"] += dd_s
                        agg["GH-T"] += gh_t
                        agg["GH-N"] += gh_n
                        agg["GH-S"] += gh_s
                        agg["UE-T"] += ue_t
                        agg["UE-N"] += ue_n
                        agg["UE-S"] += ue_s
                        agg["EC-T"] += ec_t
                        agg["EC-N"] += ec_n
                        agg["EC-S"] += ec_s

            # Add aggregates to tp_data and store_summary
            for sid in sorted(store_map.keys(), key=int):
                agg = store_aggregates[sid]
                if agg["TotSales"] > 0 or agg["TotTxns"] > 0:  # Only add if there is data
                    agg["Store"] = sid
                    tp_data.append(agg)
                    store_summary[sid] = agg.copy()

            # Log summary (always, as aggregate)
            log("", None)
            log("Third-Party Summary (All Days)" if start != end else "Third-Party Summary", "title")
            log(hdr, "heading")
            log("─" * len(hdr), "sep")
            grand_tot_sales = 0.0
            grand_tot_net = 0.0
            grand_tot_txns = 0
            grand_dd_t = 0
            grand_dd_n = 0.0
            grand_dd_s = 0.0
            grand_gh_t = 0
            grand_gh_n = 0.0
            grand_gh_s = 0.0
            grand_ue_t = 0
            grand_ue_n = 0.0
            grand_ue_s = 0.0
            grand_ec_t = 0
            grand_ec_n = 0.0
            grand_ec_s = 0.0
            for entry in sorted(tp_data, key=lambda x: int(x["Store"])):
                log(f"{entry['Store']:>6}  {entry['TotSales']:>10.2f}  {entry['TotNet']:>10.2f}  {entry['TotTxns']:>8}  "
                    f"{entry['DD-T']:>6} {entry['DD-N']:>8.2f} {entry['DD-S']:>8.2f}  "
                    f"{entry['GH-T']:>6} {entry['GH-N']:>8.2f} {entry['GH-S']:>8.2f}  "
                    f"{entry['UE-T']:>6} {entry['UE-N']:>8.2f} {entry['UE-S']:>8.2f}  "
                    f"{entry['EC-T']:>6} {entry['EC-N']:>8.2f} {entry['EC-S']:>8.2f}")
                grand_tot_sales += entry['TotSales']
                grand_tot_net += entry['TotNet']
                grand_tot_txns += entry['TotTxns']
                grand_dd_t += entry['DD-T']
                grand_dd_n += entry['DD-N']
                grand_dd_s += entry['DD-S']
                grand_gh_t += entry['GH-T']
                grand_gh_n += entry['GH-N']
                grand_gh_s += entry['GH-S']
                grand_ue_t += entry['UE-T']
                grand_ue_n += entry['UE-N']
                grand_ue_s += entry['UE-S']
                grand_ec_t += entry['EC-T']
                grand_ec_n += entry['EC-N']
                grand_ec_s += entry['EC-S']
            log("─" * len(hdr), "sep")
            log(f"{'Total':>6}  {grand_tot_sales:>10.2f}  {grand_tot_net:>10.2f}  {grand_tot_txns:>8}  "
                f"{grand_dd_t:>6} {grand_dd_n:>8.2f} {grand_dd_s:>8.2f}  "
                f"{grand_gh_t:>6} {grand_gh_n:>8.2f} {grand_gh_s:>8.2f}  "
                f"{grand_ue_t:>6} {grand_ue_n:>8.2f} {grand_ue_s:>8.2f}  "
                f"{grand_ec_t:>6} {grand_ec_n:>8.2f} {grand_ec_s:>8.2f}")

            # Log daily sections only if multi-day
            if start != end:
                for date in sorted(daily_breakdown):
                    log("", None)
                    log(f"Per-Day Third-Party Summary ({date})", "title")
                    log(hdr, "heading")
                    log("─" * len(hdr), "sep")
                    day_tot_sales = 0.0
                    day_tot_net = 0.0
                    day_tot_txns = 0
                    day_dd_t = 0
                    day_dd_n = 0.0
                    day_dd_s = 0.0
                    day_gh_t = 0
                    day_gh_n = 0.0
                    day_gh_s = 0.0
                    day_ue_t = 0
                    day_ue_n = 0.0
                    day_ue_s = 0.0
                    day_ec_t = 0
                    day_ec_n = 0.0
                    day_ec_s = 0.0
                    entries = sorted(daily_breakdown[date], key=lambda x: int(x["Store"]))
                    for entry in entries:
                        log(f"{entry['Store']:>6}  {entry['TotSales']:>10.2f}  {entry['TotNet']:>10.2f}  {entry['TotTxns']:>8}  "
                            f"{entry['DD-T']:>6} {entry['DD-N']:>8.2f} {entry['DD-S']:>8.2f}  "
                            f"{entry['GH-T']:>6} {entry['GH-N']:>8.2f} {entry['GH-S']:>8.2f}  "
                            f"{entry['UE-T']:>6} {entry['UE-N']:>8.2f} {entry['UE-S']:>8.2f}  "
                            f"{entry['EC-T']:>6} {entry['EC-N']:>8.2f} {entry['EC-S']:>8.2f}")
                        day_tot_sales += entry['TotSales']
                        day_tot_net += entry['TotNet']
                        day_tot_txns += entry['TotTxns']
                        day_dd_t += entry['DD-T']
                        day_dd_n += entry['DD-N']
                        day_dd_s += entry['DD-S']
                        day_gh_t += entry['GH-T']
                        day_gh_n += entry['GH-N']
                        day_gh_s += entry['GH-S']
                        day_ue_t += entry['UE-T']
                        day_ue_n += entry['UE-N']
                        day_ue_s += entry['UE-S']
                        day_ec_t += entry['EC-T']
                        day_ec_n += entry['EC-N']
                        day_ec_s += entry['EC-S']
                    log("─" * len(hdr), "sep")
                    log(f"{'Total':>6}  {day_tot_sales:>10.2f}  {day_tot_net:>10.2f}  {day_tot_txns:>8}  "
                        f"{day_dd_t:>6} {day_dd_n:>8.2f} {day_dd_s:>8.2f}  "
                        f"{day_gh_t:>6} {day_gh_n:>8.2f} {day_gh_s:>8.2f}  "
                        f"{day_ue_t:>6} {day_ue_n:>8.2f} {day_ue_s:>8.2f}  "
                        f"{day_ec_t:>6} {day_ec_n:>8.2f} {day_ec_s:>8.2f}")

            # Log per-store daily breakdown
            for sid in sorted(selected_stores, key=int):
                log("", None)
                log(f"Per-Store Breakdown for {sid}", "title")
                log(hdr2, "heading")
                log("─" * len(hdr2), "sep")
                has_data = False
                store_tot_sales = 0.0
                store_tot_net = 0.0
                store_tot_txns = 0
                store_dd_t = 0
                store_dd_n = 0.0
                store_dd_s = 0.0
                store_gh_t = 0
                store_gh_n = 0.0
                store_gh_s = 0.0
                store_ue_t = 0
                store_ue_n = 0.0
                store_ue_s = 0.0
                store_ec_t = 0
                store_ec_n = 0.0
                store_ec_s = 0.0
                for date in sorted(daily_breakdown):
                    for entry in daily_breakdown[date]:
                        if entry["Store"] == sid:
                            has_data = True
                            log(f"{date:10}  {entry['TotSales']:>10.2f}  {entry['TotNet']:>10.2f}  {entry['TotTxns']:>8}  "
                                f"{entry['DD-T']:>6} {entry['DD-N']:>8.2f} {entry['DD-S']:>8.2f}  "
                                f"{entry['GH-T']:>6} {entry['GH-N']:>8.2f} {entry['GH-S']:>8.2f}  "
                                f"{entry['UE-T']:>6} {entry['UE-N']:>8.2f} {entry['UE-S']:>8.2f}  "
                                f"{entry['EC-T']:>6} {entry['EC-N']:>8.2f} {entry['EC-S']:>8.2f}")
                            store_tot_sales += entry['TotSales']
                            store_tot_net += entry['TotNet']
                            store_tot_txns += entry['TotTxns']
                            store_dd_t += entry['DD-T']
                            store_dd_n += entry['DD-N']
                            store_dd_s += entry['DD-S']
                            store_gh_t += entry['GH-T']
                            store_gh_n += entry['GH-N']
                            store_gh_s += entry['GH-S']
                            store_ue_t += entry['UE-T']
                            store_ue_n += entry['UE-N']
                            store_ue_s += entry['UE-S']
                            store_ec_t += entry['EC-T']
                            store_ec_n += entry['EC-N']
                            store_ec_s += entry['EC-S']
                if not has_data:
                    log("No data for this store.")
                else:
                    log("─" * len(hdr2), "sep")
                    log(f"{'Total':10}  {store_tot_sales:>10.2f}  {store_tot_net:>10.2f}  {store_tot_txns:>8}  "
                        f"{store_dd_t:>6} {store_dd_n:>8.2f} {store_dd_s:>8.2f}  "
                        f"{store_gh_t:>6} {store_gh_n:>8.2f} {store_gh_s:>8.2f}  "
                        f"{store_ue_t:>6} {store_ue_n:>8.2f} {store_ue_s:>8.2f}  "
                        f"{store_ec_t:>6} {store_ec_n:>8.2f} {store_ec_s:>8.2f}")
                log("─" * len(hdr2), "sep")

            # Clean up
            idx = txt.search("Fetching data for ", "1.0", tk.END)
            if idx:
                txt.delete(idx, f"{idx} lineend +1c")
            window.after(0, enable_toolbar)
        except Exception as ex:
            log_error(f"Worker thread error: {ex}", endpoint=TP_ENDPOINT)
            log(f"❌ Report error: {ex}", "sep")
            window.after(0, enable_toolbar)

    # Start worker thread
    threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    config_emails = []
    config_smtp = {}
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    root = tk.Tk()
    run(root)
    root.mainloop()