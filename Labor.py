import string
import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import messagebox, simpledialog, filedialog, Toplevel, StringVar
from datetime import datetime
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
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

ENDPOINT_NAME = "Daily Timeclock"
MAX_DAYS = 30
SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def generate_unique_filename(ext):
    """Generate unique filename in reports/ dir (Labor-XXXX.ext, alphanumeric)."""
    reports_dir = os.path.join(SCRIPT_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=4))
        fname = os.path.join(reports_dir, f"Labor-{code}.{ext.lower()}")
        if not os.path.exists(fname):
            return fname

def create_toolbar(window, txt, title, labor_data, emp_summary, store_summary, start_date, end_date, selected_stores):
    """Create revamped toolbar with Export .PDF/.JSON/.TXT/.CSV, Email, Print, Copy."""
    toolbar = tk.Frame(window, bg="#f0f0f0")
    toolbar.pack(fill="x", pady=(8, 0), padx=8)
    copy_btn = tk.Button(toolbar, text="Copy", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    copy_btn.pack(side="right", padx=4)
    #print_btn = tk.Button(toolbar, text="Print", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    #print_btn.pack(side="right", padx=4)
    email_btn = tk.Button(toolbar, text="Email", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10),
                          command=lambda: open_email_dialog(window, txt, labor_data, emp_summary, store_summary, title, start_date, end_date, selected_stores))
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
        #print_btn.config(state=tk.NORMAL, command=print_content)
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
            for entry in labor_data:
                text = f"Store: {entry['Store']}<br/>Employee: {entry['Employee']}<br/>In: {entry['In']}<br/>Out: {entry['Out']}<br/>Hours: {entry['Hours']:.2f}<br/>"
                elements.append(Paragraph(text, style))
                elements.append(Spacer(1, 12))
            elements.append(Paragraph("Employee Summary", styles["Heading2"]))
            for v in emp_summary.values():
                text = f"Employee: {v['name']}<br/>Hours: {v['hours']:.2f}<br/>Shifts: {v['shifts']}<br/>"
                elements.append(Paragraph(text, style))
                elements.append(Spacer(1, 12))
            elements.append(Paragraph("Store Summary", styles["Heading2"]))
            for sid, ss in store_summary.items():
                text = f"Store: {sid}<br/>Hours: {ss['hours']:.2f}<br/>Employees: {len(ss['emps'])}<br/>Shifts: {ss['shifts']}<br/>"
                elements.append(Paragraph(text, style))
                elements.append(Spacer(1, 12))
            doc.build(elements)
        except Exception as e:
            messagebox.showerror("PDF Error", f"Failed to generate PDF for printing: {e}", parent=window)
            return
        try:
            printer = win32print.GetDefaultPrinter()
            hPr = win32print.OpenPrinter(printer)
            win32print.StartDocPrinter(hPr, 1, (title, None, "RAW"))
            win32print.StartPagePrinter(hPr)
            with open(fname, "rb") as f:
                win32print.WritePrinter(hPr, f.read())
            win32print.EndPagePrinter(hPr)
            win32print.EndDocPrinter(hPr)
            win32print.ClosePrinter(hPr)
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to print PDF: {e}", parent=window)
        finally:
            if os.path.exists(fname):
                os.unlink(fname)

    def export_file(fmt):
        fname = generate_unique_filename(fmt)
        if fmt == "CSV":
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # Individual Entries
                writer.writerow(["Store", "Employee", "In", "Out", "Hours"])
                for entry in labor_data:
                    writer.writerow([entry["Store"], entry["Employee"], entry["In"], entry["Out"], entry["Hours"]])
                writer.writerow([""] * 5)  # Blank row
                # Employee Summary
                writer.writerow(["Employee Summary"] + [""] * 4)
                writer.writerow(["Employee", "Hours", "Shifts"] + [""] * 2)
                for k in sorted(emp_summary, key=lambda x: emp_summary[x]["name"]):
                    v = emp_summary[k]
                    writer.writerow([v["name"], v["hours"], v["shifts"]] + [""] * 2)
                writer.writerow([""] * 5)  # Blank row
                # Store Summary
                writer.writerow(["Store Summary"] + [""] * 4)
                writer.writerow(["Store", "Hours", "Employees", "Shifts", ""])
                for sid in sorted(store_summary):
                    ss = store_summary[sid]
                    writer.writerow([sid, ss["hours"], len(ss["emps"]), ss["shifts"], ""])
        elif fmt == "JSON":
            export_data = {
                "entries": labor_data,
                "employee_summary": [{"Employee": v["name"], "Hours": v["hours"], "Shifts": v["shifts"]} for v in emp_summary.values()],
                "store_summary": [{"Store": sid, "Hours": ss["hours"], "Employees": len(ss["emps"]), "Shifts": ss["shifts"]} for sid, ss in store_summary.items()]
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
                for entry in labor_data:
                    text = f"Store: {entry['Store']}<br/>Employee: {entry['Employee']}<br/>In: {entry['In']}<br/>Out: {entry['Out']}<br/>Hours: {entry['Hours']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Employee Summary", styles["Heading2"]))
                for v in emp_summary.values():
                    text = f"Employee: {v['name']}<br/>Hours: {v['hours']:.2f}<br/>Shifts: {v['shifts']}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                for sid, ss in store_summary.items():
                    text = f"Store: {sid}<br/>Hours: {ss['hours']:.2f}<br/>Employees: {len(ss['emps'])}<br/>Shifts: {ss['shifts']}<br/>"
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

def open_email_dialog(window, txt, labor_data, emp_summary, store_summary, title, start_date, end_date, selected_stores):
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
        # Generate file content (similar to export_file logic)
        if fmt == "CSV":
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # Individual Entries
                writer.writerow(["Store", "Employee", "In", "Out", "Hours"])
                for entry in labor_data:
                    writer.writerow([entry["Store"], entry["Employee"], entry["In"], entry["Out"], entry["Hours"]])
                writer.writerow([""] * 5)  # Blank row
                # Employee Summary
                writer.writerow(["Employee Summary"] + [""] * 4)
                writer.writerow(["Employee", "Hours", "Shifts"] + [""] * 2)
                for k in sorted(emp_summary, key=lambda x: emp_summary[x]["name"]):
                    v = emp_summary[k]
                    writer.writerow([v["name"], v["hours"], v["shifts"]] + [""] * 2)
                writer.writerow([""] * 5)  # Blank row
                # Store Summary
                writer.writerow(["Store Summary"] + [""] * 4)
                writer.writerow(["Store", "Hours", "Employees", "Shifts", ""])
                for sid in sorted(store_summary):
                    ss = store_summary[sid]
                    writer.writerow([sid, ss["hours"], len(ss["emps"]), ss["shifts"], ""])
        elif fmt == "JSON":
            export_data = {
                "entries": labor_data,
                "employee_summary": [{"Employee": v["name"], "Hours": v["hours"], "Shifts": v["shifts"]} for v in emp_summary.values()],
                "store_summary": [{"Store": sid, "Hours": ss["hours"], "Employees": len(ss["emps"]), "Shifts": ss["shifts"]} for sid, ss in store_summary.items()]
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
                for entry in labor_data:
                    text = f"Store: {entry['Store']}<br/>Employee: {entry['Employee']}<br/>In: {entry['In']}<br/>Out: {entry['Out']}<br/>Hours: {entry['Hours']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Employee Summary", styles["Heading2"]))
                for v in emp_summary.values():
                    text = f"Employee: {v['name']}<br/>Hours: {v['hours']:.2f}<br/>Shifts: {v['shifts']}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                for sid, ss in store_summary.items():
                    text = f"Store: {sid}<br/>Hours: {ss['hours']:.2f}<br/>Employees: {len(ss['emps'])}<br/>Shifts: {ss['shifts']}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                doc.build(elements)
            except Exception as e:
                messagebox.showerror("PDF Error", f"Failed to generate PDF: {e}", parent=dialog)
                return
        lines = txt.get("1.0", "end-1c").splitlines()
        subj = "Labor Report"
        if lines and "Labor Hours: " in lines[0]:
            subj += " – " + lines[0].split(": ", 1)[1]
        subj = urllib.parse.quote(subj)
        body = urllib.parse.quote("Please see the attached labor report.")
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
        # Generate file content (similar to above)
        if fmt == "CSV":
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # Individual Entries
                writer.writerow(["Store", "Employee", "In", "Out", "Hours"])
                for entry in labor_data:
                    writer.writerow([entry["Store"], entry["Employee"], entry["In"], entry["Out"], entry["Hours"]])
                writer.writerow([""] * 5)  # Blank row
                # Employee Summary
                writer.writerow(["Employee Summary"] + [""] * 4)
                writer.writerow(["Employee", "Hours", "Shifts"] + [""] * 2)
                for k in sorted(emp_summary, key=lambda x: emp_summary[x]["name"]):
                    v = emp_summary[k]
                    writer.writerow([v["name"], v["hours"], v["shifts"]] + [""] * 2)
                writer.writerow([""] * 5)  # Blank row
                # Store Summary
                writer.writerow(["Store Summary"] + [""] * 4)
                writer.writerow(["Store", "Hours", "Employees", "Shifts", ""])
                for sid in sorted(store_summary):
                    ss = store_summary[sid]
                    writer.writerow([sid, ss["hours"], len(ss["emps"]), ss["shifts"], ""])
        elif fmt == "JSON":
            export_data = {
                "entries": labor_data,
                "employee_summary": [{"Employee": v["name"], "Hours": v["hours"], "Shifts": v["shifts"]} for v in emp_summary.values()],
                "store_summary": [{"Store": sid, "Hours": ss["hours"], "Employees": len(ss["emps"]), "Shifts": ss["shifts"]} for sid, ss in store_summary.items()]
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
                for entry in labor_data:
                    text = f"Store: {entry['Store']}<br/>Employee: {entry['Employee']}<br/>In: {entry['In']}<br/>Out: {entry['Out']}<br/>Hours: {entry['Hours']:.2f}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Employee Summary", styles["Heading2"]))
                for v in emp_summary.values():
                    text = f"Employee: {v['name']}<br/>Hours: {v['hours']:.2f}<br/>Shifts: {v['shifts']}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                elements.append(Paragraph("Store Summary", styles["Heading2"]))
                for sid, ss in store_summary.items():
                    text = f"Store: {sid}<br/>Hours: {ss['hours']:.2f}<br/>Employees: {len(ss['emps'])}<br/>Shifts: {ss['shifts']}<br/>"
                    elements.append(Paragraph(text, style))
                    elements.append(Spacer(1, 12))
                doc.build(elements)
            except Exception as e:
                messagebox.showerror("PDF Error", f"Failed to generate PDF: {e}", parent=dialog)
                return
        lines = txt.get("1.0", "end-1c").splitlines()
        subj = "Labor Report"
        if lines and "Labor Hours: " in lines[0]:
            subj += " – " + lines[0].split(": ", 1)[1]
        try:
            smtp = config_smtp
            msg = MIMEMultipart()
            msg["Subject"] = subj
            msg["From"] = smtp["from"]
            msg["To"] = ", ".join(selected)
            msg.attach(MIMEText("Please see the attached labor report."))
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
    """Run the Labor report for selected stores and date range.
    
    Args:
        window: Tk window to display the report.
    """
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
    window.title("Labor Report")
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
    labor_data = []  # Structured data for individual entries
    emp_summary = {}  # Employee summary
    store_summary = {}  # Store summary
    enable_toolbar = create_toolbar(window, txt, "Labor Report", labor_data, emp_summary, store_summary, start_date_str, end_date_str, selected_stores)
    log_error("Toolbar created", endpoint=ENDPOINT_NAME)  # Debug log

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
        log_error(f"Log: {line}", endpoint=ENDPOINT_NAME)  # Debug log

    def worker():
        try:
            # Check store selection
            if not selected_stores:
                log("No stores selected.", "sep")
                log_error("No stores selected", endpoint=ENDPOINT_NAME)
                window.after(0, enable_toolbar)
                return

            # Build store map, prioritizing accounts with fewer stores to avoid duplicates
            store_map = {}
            account_store_lists = {}
            for acct in sorted(config_accounts, key=lambda x: len(x.get("StoreIDs", [])), reverse=False):
                name = acct.get("Name", "")
                cid = acct.get("ClientID", "")
                ckey = acct.get("ClientKEY", "")
                if not all([name, cid, ckey]):
                    log(f"Skipping invalid account: {name or 'Unknown'}", "sep")
                    log_error(f"Invalid account: Name={name}, ClientID={cid}", endpoint=ENDPOINT_NAME)
                    continue
                valid_stores = [sid for sid in acct.get("StoreIDs", []) if sid in selected_stores and sid not in store_map]
                if valid_stores:
                    account_store_lists[name] = (valid_stores, cid, ckey)
                    for sid in valid_stores:
                        store_map[sid] = name

            if not store_map:
                log("No valid accounts with selected stores found.", "sep")
                log_error("No valid accounts with selected stores", endpoint=ENDPOINT_NAME)
                window.after(0, enable_toolbar)
                return

            # Start report
            s_str, e_str = start.isoformat(), end.isoformat()
            log(f"Labor Hours: {s_str} → {e_str}", "title")
            log(f"Fetching data for {len(store_map)} stores across {len(account_store_lists)} account(s)…", "sep")
            log("", None)  # Blank line for readability

            # Fetch data with comma-separated store IDs per account
            futures = {}
            with ThreadPoolExecutor(max_workers=min(config_max_workers, len(account_store_lists))) as ex:
                for name, (store_ids, cid, ckey) in account_store_lists.items():
                    if store_ids:
                        restaurant_numbers = ",".join(store_ids)
                        futures[ex.submit(fetch_data, ENDPOINT_NAME, restaurant_numbers, s_str, e_str, cid, ckey)] = (name, store_ids, cid, ckey)

                for fut in as_completed(futures):
                    name, store_ids, cid, ckey = futures[fut]
                    try:
                        res = fut.result()
                        log_error(f"API response for account {name} (stores {store_ids}): {json.dumps(res, indent=2)}", endpoint=ENDPOINT_NAME)
                    except RateLimitError as ex:
                        log_error(f"Rate limit for account {name} (stores {store_ids}): {ex}", endpoint=ENDPOINT_NAME)
                        log(f"⚠️ Account {name} (Stores {', '.join(store_ids)}): Rate limit hit; skipping.", "sep")
                        continue
                    except Exception as ex:
                        log_error(f"Fetch failed for account {name} (stores {store_ids}): {ex}", endpoint=ENDPOINT_NAME)
                        log(f"❌ Account {name} (Stores {', '.join(store_ids)}): Exception: {ex}", "sep")
                        continue

                    err = res.get("error")
                    if err:
                        log_error(f"API error for account {name} (stores {store_ids}): {err}", endpoint=ENDPOINT_NAME)
                        log(f"❌ Account {name} (Stores {', '.join(store_ids)}): {err}", "sep")
                        continue

                    data = res.get("data", res) or []
                    if isinstance(data, dict):
                        data = [data]
                    if not data:
                        msg = "clock-in data for today" if start == end == datetime.now().date() else "data available"
                        log(f"Account {name} (Stores {', '.join(store_ids)}): No {msg}.", "sep")
                        log_error(f"No data for account {name} (stores {store_ids})", endpoint=ENDPOINT_NAME)
                        continue

                    for sid in sorted(store_ids):  # Sort for consistent order
                        store_data = [rec for rec in data if rec.get("restaurantNumber") == sid]
                        log(f"Store {sid} (Acct: {name})", "heading")
                        if not store_data:
                            msg = "clock-in data for today" if start == end == datetime.now().date() else "data available"
                            log(f"No {msg} for store {sid}.", "sep")
                            log("", None)  # Blank line for readability
                            continue

                        log(f"{'Employee':<30}  {'In':<20}  {'Out':<20}  {'Hrs':>5}", "heading")
                        log("─" * 80, "sep")

                        for rec in store_data:
                            emp = rec.get("employeeName", "Unknown").strip().title()
                            cin = rec.get("clockInDateTime") or rec.get("clockIn")
                            cout = rec.get("clockOutDateTime") or rec.get("clockOut")
                            fmt = "%Y-%m-%dT%H:%M:%S"
                            try:
                                t0 = datetime.strptime(cin, fmt)
                                t1 = datetime.strptime(cout, fmt) if cout else None
                                in_s = t0.strftime("%m/%d %I:%M %p")
                                out_s = t1.strftime("%m/%d %I:%M %p") if t1 else "(in)"
                                hrs = (t1 - t0).total_seconds() / 3600 if t1 else 0
                            except ValueError:
                                log_error(f"Bad timestamp for {emp} in store {sid}: {cin}, {cout}", sid, ENDPOINT_NAME)
                                log(f"⚠️ Bad timestamp for {emp}", "sep")
                                continue
                            log(f"{emp:<30}  {in_s:<20}  {out_s:<20}  {hrs:>5.2f}")
                            labor_data.append({"Store": sid, "Employee": emp, "In": in_s, "Out": out_s, "Hours": hrs})
                            ss = store_summary.setdefault(sid, {"hours": 0.0, "emps": set(), "shifts": 0})
                            ss["hours"] += hrs
                            ss["shifts"] += 1
                            ss["emps"].add(emp)
                            es = emp_summary.setdefault(emp.lower(), {"name": emp, "hours": 0.0, "shifts": 0})
                            es["hours"] += hrs
                            es["shifts"] += 1
                        log("", None)  # Blank line after store section

            # Summaries
            if emp_summary:
                log("", None)  # Blank line before summaries
                log("Summary of Hours per Employee", "title")
                maxw = max(len(v["name"]) for v in emp_summary.values()) + 2
                hdr = f"{'Employee':<{maxw}}  {'Hrs':>5}  {'Shifts':>6}"
                log(hdr, "heading")
                log("─" * len(hdr), "sep")
                for k in sorted(emp_summary, key=lambda x: emp_summary[x]["name"]):
                    v = emp_summary[k]
                    log(f"{v['name']:<{maxw}}  {v['hours']:>5.2f}  {v['shifts']:>6}")
                log("", None)  # Blank line after employee summary

                log("Summary of Hours per Store", "title")
                log(f"{'Store':<9}  {'Hrs':>8}  {'Emps':>8}  {'Shifts':>8}", "heading")
                log("─" * 35, "sep")
                for sid in sorted(store_summary):
                    ss = store_summary[sid]
                    log(f"{sid:<9}  {ss['hours']:>8.2f}  {len(ss['emps']):>8}  {ss['shifts']:>8}")
                log("", None)  # Blank line after store summary

            # Clean up
            idx = txt.search("Fetching data for ", "1.0", tk.END)
            if idx:
                txt.delete(idx, f"{idx} lineend +1c")
            window.after(0, enable_toolbar)
        except Exception as ex:
            log_error(f"Worker thread error: {ex}", endpoint=ENDPOINT_NAME)
            log(f"❌ Report error: {ex}", "sep")
            window.after(0, enable_toolbar)

    # Start initial report
    threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    config_emails = []
    config_smtp = {}
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    root = tk.Tk()
    run(root)
    root.mainloop()