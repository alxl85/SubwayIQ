import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from tkinter.scrolledtext import ScrolledText
import json
import csv
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
import tempfile
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# Custom exception defined in SubwayIQ.py
class NoInternetError(Exception):
    pass

# Define the API endpoint globally (modify as needed)
ENDPOINT = "Daily Timeclock"  # Example endpoint; change to any key in ENDPOINTS (e.g., "Sales Summary", "Transaction Details")

def run(window):
    """Main entry point for the Custom module. Fetches and displays data from the LiveIQ API.

    This module mirrors the Endpoint Viewer from SubwayIQ.py, displaying raw JSON data with a
    'Flatten' checkbox, and supports all export options (PDF, CSV, JSON, TXT, Email, Print, Copy).
    Modify the ENDPOINT variable and customize the process_data function to transform API data.

    Parameters:
        window (tk.Toplevel): The module window provided by SubwayIQ.
    """
    # Import required globals from SubwayIQ.py
    from __main__ import get_selected_start_date, get_selected_end_date, fetch_data, store_vars, config_accounts, handle_rate_limit, log_error, _password_validated, RateLimitError, config_emails, config_smtp, SCRIPT_DIR

    if not _password_validated:
        messagebox.showerror("Access Denied", "Password validation required.", parent=window)
        window.destroy()
        return

    # Get selected stores and date range
    selected_stores = [sid for sid, var in store_vars.items() if var.get()]
    start_date = get_selected_start_date()
    end_date = get_selected_end_date()

    if not selected_stores:
        messagebox.showwarning("No Stores", "Please select at least one store.", parent=window)
        window.destroy()
        return

    # Create GUI elements
    toolbar = tk.Frame(window)
    toolbar.pack(fill="x", pady=4)
    flat_var = tk.BooleanVar(value=False)
    tk.Checkbutton(toolbar, text="Flatten", variable=flat_var).pack(side="left", padx=6)
    txt = ScrolledText(window, wrap="word", font=("Consolas", 10))
    txt.pack(expand=True, fill="both", padx=10, pady=10)
    progress = ttk.Progressbar(window, mode="determinate", maximum=len(selected_stores))
    progress.pack(fill="x", padx=10)

    # Create toolbar with export buttons
    enable_toolbar = create_toolbar(window, txt, f"Custom Report - {ENDPOINT}", selected_stores, start_date, end_date, toolbar)

    # Fetch data from API
    fetched_data = []
    try:
        with ThreadPoolExecutor(max_workers=min(8, len(selected_stores))) as ex:
            futures = {}
            fetched_ids = set()
            for acct in config_accounts:
                cid, ckey, aname = acct["ClientID"], acct["ClientKEY"], acct["Name"]
                for sid in acct.get("StoreIDs", []):
                    if sid in selected_stores and sid not in fetched_ids:
                        futures[ex.submit(fetch_data, ENDPOINT, sid, start_date, end_date, cid, ckey)] = (aname, sid)
                        fetched_ids.add(sid)
            for fut in as_completed(futures):
                aname, sid = futures[fut]
                try:
                    res = fut.result()
                    fetched_data.append((aname, sid, res))
                except NoInternetError as exc:
                    log_error(f"No internet connection for store {sid}: {exc}", sid, ENDPOINT)  # type: ignore
                    messagebox.showerror("No Internet", str(exc), parent=window)
                    window.destroy()
                    return
                except RateLimitError as exc:
                    log_error(f"Rate limit for store {sid}: {exc}", sid, ENDPOINT)  # type: ignore
                    fetched_data.append((aname, sid, {"error": str(exc)}))
                except Exception as exc:
                    log_error(f"Fetch failed for store {sid}: {exc}", sid, ENDPOINT)  # type: ignore
                    fetched_data.append((aname, sid, {"error": str(exc)}))
                progress.step()
                progress.update()
    except Exception as exc:
        log_error(f"Error in custom module: {exc}", endpoint=ENDPOINT)  # type: ignore
        messagebox.showerror("Error", f"Failed to fetch data: {exc}", parent=window)
        window.destroy()
        return

    # Process and render data
    processed_data = process_data(fetched_data)  # Customize this function below
    def render():
        """Render data to the ScrolledText widget, mirroring Endpoint Viewer."""
        txt.delete("1.0", "end")
        def write(line=""):
            txt.insert("end", line + "\n")
        write(f"Endpoint: {ENDPOINT}")
        write(f"Range   : {start_date} → {end_date}")
        write(f"Stores  : {', '.join(selected_stores)}\n")
        for aname, sid, res in processed_data:
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
    render()

    # Enable toolbar after data is fetched
    progress.destroy()
    enable_toolbar()

def flatten_json(obj, parent="", sep="."):
    """Flatten a nested JSON object into a key-value dictionary.

    Copied from SubwayIQ.py to mirror Endpoint Viewer functionality.

    Parameters:
        obj: The JSON object to flatten.
        parent (str): The parent key for nested structures.
        sep (str): Separator for nested keys.

    Returns:
        dict: Flattened key-value dictionary.
    """
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

def process_data(fetched_data):
    """Process raw API data into a format suitable for display and export.

    Customize this function to transform the API response data as needed.
    The default implementation passes through raw data to mirror Endpoint Viewer.
    Each entry in fetched_data is a tuple: (account_name, store_id, data).

    Parameters:
        fetched_data (list): List of tuples containing (account_name, store_id, data).

    Returns:
        list: Processed data entries in a format suitable for display/export.
    """
    processed = []
    for aname, sid, data in fetched_data:
        if "error" in data:
            processed.append((aname, sid, {"error": data["error"]}))
            continue
        # Pass through raw data to mimic Endpoint Viewer
        # Customize this to extract specific fields or compute summaries
        processed.append((aname, sid, {"data": data}))
    return processed

def create_toolbar(window, txt, title, selected_stores, start_date, end_date, toolbar):
    """Create toolbar with export buttons (PDF, CSV, JSON, TXT, Email, Print, Copy).

    Parameters:
        window (tk.Toplevel): The module window.
        txt (ScrolledText): The text widget containing displayed data.
        title (str): Title for the report.
        selected_stores (list): List of selected store IDs.
        start_date (str): Start date (YYYY-MM-DD).
        end_date (str): End date (YYYY-MM-DD).
        toolbar (tk.Frame): The toolbar frame to add buttons to.

    Returns:
        function: The enable_toolbar function to activate buttons after data fetch.
    """
    copy_btn = tk.Button(toolbar, text="Copy", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    copy_btn.pack(side="right", padx=4)
    print_btn = tk.Button(toolbar, text="Print", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
    print_btn.pack(side="right", padx=4)
    email_btn = tk.Button(toolbar, text="Email", state=tk.DISABLED, bg="#005228", fg="#ecc10c", font=("Arial", 10))
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
        """Enable toolbar buttons after data is fetched."""
        copy_btn.config(state=tk.NORMAL, command=lambda: (
            window.clipboard_clear(),
            window.clipboard_append(txt.get("1.0", "end-1c"))
        ))
        print_btn.config(state=tk.NORMAL, command=print_content)
        email_btn.config(state=tk.NORMAL, command=lambda: open_email_dialog(window, txt, title, selected_stores, start_date, end_date))
        csv_btn.config(state=tk.NORMAL, command=lambda: export_file("CSV"))
        txt_btn.config(state=tk.NORMAL, command=lambda: export_file("TXT"))
        json_btn.config(state=tk.NORMAL, command=lambda: export_file("JSON"))
        if REPORTLAB_AVAILABLE:
            pdf_btn.config(state=tk.NORMAL, command=lambda: export_file("PDF"))
        else:
            messagebox.showwarning("PDF Unavailable", "PDF export is disabled because the 'reportlab' library is not installed. Install it using 'pip install reportlab'.", parent=window)

    def print_content():
        """Print the displayed data as a PDF."""
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
            data = txt.get("1.0", "end-1c").splitlines()
            for line in data:
                elements.append(Paragraph(line, style))
                elements.append(Spacer(1, 6))
            doc.build(elements)
            os.startfile(fname, "print")
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to generate/print PDF: {e}", parent=window)
        finally:
            if os.path.exists(fname):
                os.unlink(fname)

    def export_file(fmt):
        """Export data to the specified format (CSV, TXT, JSON, PDF)."""
        data = txt.get("1.0", "end-1c")
        ext = f".{fmt.lower()}"
        filename = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(f"{fmt} files", f"*{ext}"), ("All files", "*.*")],
            title=f"Save {fmt} Report",
            initialfile=f"custom_{ENDPOINT.lower().replace(' ', '_')}_{datetime.now():%Y%m%d}{ext}",
            parent=window
        )
        if not filename:
            return
        try:
            if fmt == "CSV":
                with open(filename, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    for line in data.splitlines():
                        writer.writerow(line.split())
            elif fmt == "TXT":
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(data)
            elif fmt == "JSON":
                # Example JSON export; customize based on processed_data if needed
                json_data = [{"store": sid, "data": txt.get("1.0", "end-1c")} for sid in selected_stores]
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False)
            elif fmt == "PDF":
                if not REPORTLAB_AVAILABLE:
                    messagebox.showerror("PDF Error", "reportlab not available.", parent=window)
                    return
                doc = SimpleDocTemplate(filename, pagesize=letter)
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
                for line in data.splitlines():
                    elements.append(Paragraph(line, style))
                    elements.append(Spacer(1, 6))
                doc.build(elements)
            messagebox.showinfo("Export", f"Report exported to {filename}.", parent=window)
        except Exception as e:
            messagebox.showerror(f"Export Error", f"Failed to export {fmt}: {e}", parent=window)

    def open_email_dialog(window, txt, title, selected_stores, start_date, end_date):
        """Open a dialog to send the report via email."""
        from __main__ import config_emails, config_smtp
        if not config_emails:
            messagebox.showwarning("No Emails", "No email addresses configured. Add them in the Emails menu.", parent=window)
            return
        if not all(k in config_smtp for k in ["server", "port", "username", "password", "from"]):
            messagebox.showwarning("SMTP Error", "SMTP settings incomplete. Configure them in the Emails menu.", parent=window)
            return

        email_win = tk.Toplevel(window)
        email_win.title("Send Report via Email")
        email_win.geometry("400x300")
        x = (window.winfo_screenwidth() - 400) // 2
        y = (window.winfo_screenheight() - 300) // 2
        email_win.geometry(f"+{x}+{y}")
        email_win.resizable(False, False)
        email_win.transient(window)
        email_win.grab_set()

        tk.Label(email_win, text="Select Recipients:", font=("Arial", 12, "bold")).pack(pady=5)
        email_listbox = tk.Listbox(email_win, selectmode=tk.MULTIPLE, height=8)
        email_listbox.pack(fill="both", expand=True, padx=10, pady=5)
        for email in config_emails:
            email_listbox.insert(tk.END, email)

        def send_email():
            selected_indices = email_listbox.curselection()
            if not selected_indices:
                messagebox.showwarning("No Recipients", "Please select at least one recipient.", parent=email_win)
                return
            recipients = [config_emails[i] for i in selected_indices]
            data = txt.get("1.0", "end-1c")
            msg = MIMEMultipart()
            msg["From"] = config_smtp["from"]
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = f"{title} ({start_date} to {end_date})"
            msg.attach(MIMEText(data, "plain", "utf-8"))

            # Attach PDF if reportlab is available
            if REPORTLAB_AVAILABLE:
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
                    for line in data.splitlines():
                        elements.append(Paragraph(line, style))
                        elements.append(Spacer(1, 6))
                    doc.build(elements)
                    with open(fname, "rb") as f:
                        attachment = MIMEApplication(f.read(), _subtype="pdf")
                        attachment.add_header("Content-Disposition", "attachment", filename=f"{title}.pdf")
                        msg.attach(attachment)
                except Exception as e:
                    log_error(f"Failed to generate PDF attachment: {e}")  # type: ignore
                finally:
                    if os.path.exists(fname):
                        os.unlink(fname)

            try:
                server = config_smtp["server"]
                port = config_smtp["port"]
                if port == 465:
                    smtp = smtplib.SMTP_SSL(server, port, timeout=10)
                else:
                    smtp = smtplib.SMTP(server, port, timeout=10)
                smtp.ehlo()
                if port != 465:
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(config_smtp["username"], config_smtp["password"])
                smtp.send_message(msg)
                smtp.quit()
                messagebox.showinfo("Success", "Report emailed successfully.", parent=email_win)
                email_win.destroy()
            except Exception as e:
                messagebox.showerror("Email Error", f"Failed to send email: {e}", parent=email_win)
                log_error(f"Email error: {e}")  # type: ignore

        btn_frame = tk.Frame(email_win)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Send", command=send_email, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=email_win.destroy, bg="#005228", fg="#ecc10c").pack(side="left", padx=5)
        email_win.bind("<Return>", lambda e: send_email())

    return enable_toolbar