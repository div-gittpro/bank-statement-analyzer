import streamlit as st
import pdfplumber
import re
import pandas as pd
import matplotlib.pyplot as plt
import sqlite3
import os
import hashlib
from datetime import datetime
from difflib import get_close_matches
import plotly.express as px
import plotly.graph_objects as go

# ──────────────────────────────────────────────────────────────────────────────
# Page Configuration
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Bank Statement Analyzer",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
    <style>
    /* Main theme colors */
    :root {
        --primary-color: #4CAF50;
        --secondary-color: #2196F3;
        --danger-color: #f44336;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Better card styling */
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: 600;
    }
    
    /* Improved buttons */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* Better tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
    }
    
    /* Improved expander */
    .streamlit-expanderHeader {
        font-weight: 600;
        border-radius: 8px;
    }
    
    /* Better dataframe styling */
    div[data-testid="stDataFrame"] {
        border-radius: 8px;
    }
    
    /* Sidebar dark theme */
    section[data-testid="stSidebar"] {
        background-color: #1e1e1e !important;
    }
    
    section[data-testid="stSidebar"] > div {
        background-color: #1e1e1e !important;
    }
    
    /* Sidebar text colors for dark theme */
    section[data-testid="stSidebar"] .stMarkdown {
        color: #e0e0e0;
    }
    
    section[data-testid="stSidebar"] h3 {
        color: #4CAF50 !important;
    }
    
    section[data-testid="stSidebar"] p, 
    section[data-testid="stSidebar"] label {
        color: #b0b0b0 !important;
    }
    
    /* Sidebar expander styling */
    section[data-testid="stSidebar"] .streamlit-expanderHeader {
        background-color: #2d2d2d !important;
        color: #e0e0e0 !important;
        border-radius: 8px;
    }
    
    section[data-testid="stSidebar"] .streamlit-expanderHeader:hover {
        background-color: #3d3d3d !important;
    }
    
    section[data-testid="stSidebar"] .streamlit-expanderContent {
        background-color: #252525 !important;
        border: 1px solid #3d3d3d;
    }
    
    /* Sidebar input fields */
    section[data-testid="stSidebar"] input {
        background-color: #2d2d2d !important;
        color: #e0e0e0 !important;
        border: 1px solid #3d3d3d !important;
    }
    
    section[data-testid="stSidebar"] input:focus {
        border-color: #4CAF50 !important;
    }
    
    /* Sidebar buttons */
    section[data-testid="stSidebar"] .stButton>button {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
    }
    
    section[data-testid="stSidebar"] .stButton>button:hover {
        background-color: #3d3d3d;
        border-color: #4CAF50;
    }
    
    /* Sidebar checkbox */
    section[data-testid="stSidebar"] .stCheckbox {
        color: #e0e0e0 !important;
    }
    
    /* Sidebar info boxes */
    section[data-testid="stSidebar"] .stInfo {
        background-color: #2d2d2d !important;
        color: #b0b0b0 !important;
        border: 1px solid #3d3d3d !important;
    }
    
    /* File uploader styling */
    div[data-testid="stFileUploader"] {
        border: 2px dashed #4d4d4d;
        border-radius: 8px;
        padding: 20px;
        background: #2d2d2d;
    }
    
    /* Success/Warning/Error boxes */
    .stSuccess, .stWarning, .stError, .stInfo {
        border-radius: 8px;
        padding: 12px;
    }
    </style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "user_data")
UPLOAD_ROOT = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "bank_app.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_ROOT, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ──────────────────────────────────────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            account_number TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pdf_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            uploaded_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def register_user_db(account_number: str, password: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE account_number=?", (account_number,))
    if cur.fetchone():
        conn.close()
        return False, "Account already exists!"
    cur.execute("INSERT INTO users (account_number, password) VALUES (?, ?)", (account_number, hash_pw(password)))
    conn.commit()
    conn.close()
    return True, "Registration successful!"

def login_user_db(account_number: str, password: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE account_number=?", (account_number,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False, "User not found!"
    if row[0] != hash_pw(password):
        return False, "Incorrect password!"
    return True, "Login successful!"

def save_uploaded_files(account_number: str, files):
    user_dir = os.path.join(UPLOAD_ROOT, account_number)
    os.makedirs(user_dir, exist_ok=True)
    saved_paths = []
    conn = get_db()
    for f in files:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        fname = f"{ts}__{f.name}"
        fpath = os.path.join(user_dir, fname)
        with open(fpath, "wb") as out:
            out.write(f.getbuffer())
        conn.execute(
            "INSERT INTO pdf_files (account_number, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
            (account_number, f.name, fpath, datetime.now().isoformat(timespec="seconds"))
        )
        saved_paths.append(fpath)
    conn.commit()
    conn.close()
    return saved_paths

def get_saved_pdfs(account_number: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, filename, filepath, uploaded_at FROM pdf_files WHERE account_number=? ORDER BY uploaded_at DESC",
        (account_number,)
    )
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "filename": r[1], "filepath": r[2], "uploaded_at": r[3]} for r in rows]

def delete_pdf(pdf_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT filepath FROM pdf_files WHERE id=?", (pdf_id,))
    row = cur.fetchone()
    if row:
        try:
            os.remove(row[0])
        except FileNotFoundError:
            pass
        cur.execute("DELETE FROM pdf_files WHERE id=?", (pdf_id,))
    conn.commit()
    conn.close()

# ──────────────────────────────────────────────────────────────────────────────
# PDF parsing
# ──────────────────────────────────────────────────────────────────────────────

# Helper regexes for delta-based HDFC parsing
DATE_LINE_RE = re.compile(r"^\s*(\d{2}/\d{2}/\d{2}(?:\d{2})?|\d{2}/\d{2}/\d{4})\b")
NUM_RE = re.compile(r"[\d,]+\.\d{2}")

def extract_pages_text(pdf_path: str, account_password: str = None) -> list:
    text_pages = []
    try:
        if account_password:
            with pdfplumber.open(pdf_path, password=account_password) as pdf:
                for p in pdf.pages:
                    text_pages.append(p.extract_text() or "")
        else:
            with pdfplumber.open(pdf_path) as pdf:
                for p in pdf.pages:
                    text_pages.append(p.extract_text() or "")
    except Exception as e:
        # try without password if initial failed
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for p in pdf.pages:
                    text_pages.append(p.extract_text() or "")
        except Exception as e2:
            raise e2
    return text_pages

def parse_amount_and_balance_from_line(line: str):
    nums = NUM_RE.findall(line)
    if not nums:
        return None, None
    closing = float(nums[-1].replace(",", ""))
    amount = float(nums[-2].replace(",", "")) if len(nums) >= 2 else None
    return amount, closing

def infer_types_by_delta(tx_records: list, opening_balance: float, tolerance: float = 0.6):
    """
    Infer Type for each tx_record using opening_balance and closing balances.
    Returns list of dicts with inference_reason.
    """
    recs = []
    prev_bal = opening_balance
    for t in tx_records:
        amt = float(t['Amount']) if t['Amount'] is not None else 0.0
        new_bal = float(t['Balance'])
        delta = round(new_bal - prev_bal, 2)
        reason = None

        # If delta equals +amount -> credit, if delta equals -amount -> debit
        if abs(delta - amt) <= tolerance:
            typ = "CR"
            reason = "delta_matches_plus_amount"
        elif abs(delta + amt) <= tolerance:
            typ = "DR"
            reason = "delta_matches_minus_amount"
        else:
            # fallback to textual tokens
            if re.search(r"\b(CR|NEFT CR|NEFTCR|CREDIT|DEPOSIT|REFUND|INTEREST)\b", t['Remarks'], flags=re.I):
                typ = "CR"; reason = "text_credit_token"
            elif re.search(r"\b(ATW|POS|IMPS|UPI|WITHDRAWAL|ATM|DEBIT)\b", t['Remarks'], flags=re.I):
                typ = "DR"; reason = "text_debit_token"
            else:
                typ = "CR" if delta > 0 else "DR"
                reason = "delta_sign_fallback"

        rec = {
            "Date": t.get('Date', ''),
            "Remarks": t.get('Remarks', ''),
            "Amount": amt,
            "Type": typ,
            "Balance": new_bal,
            "Page": t.get('Page', None),
            "inference_reason": reason,
            "delta": delta
        }
        recs.append(rec)
        prev_bal = new_bal
    return recs

def _score_opening_for_records(opening, tx_records, tolerance=0.6, sample_size=6):
    """
    Runs infer_types_by_delta on a small sample and returns a score:
    count of records where inference_reason indicates delta match.
    """
    sample = tx_records[:min(sample_size, len(tx_records))]
    recs = infer_types_by_delta(sample, opening, tolerance=tolerance)
    score = sum(1 for r in recs if r.get("inference_reason", "").startswith("delta_matches"))
    return score

def extract_statement_summary(full_text: str):
    # Try to extract the opening balance & printed summary values (best-effort)
    opening = None
    printed_debits = None
    printed_credits = None
    printed_closing = None

    m = re.search(
        r"STATEMENTSUMMARY\s*[:\-]?\s*[\r\n]+(?:OpeningBalance\s+DrCount\s+CrCount\s+Debits\s+Credits\s+ClosingBal)[\r\n]+([0-9\.,\s]+)\s+\d+\s+\d+\s+([0-9\.,]+)\s+([0-9\.,]+)\s+([0-9\.,]+)",
        full_text,
        flags=re.IGNORECASE
    )
    if m:
        try:
            opening = float(m.group(1).replace(",", "").strip())
            printed_debits = float(m.group(2).replace(",", "").strip())
            printed_credits = float(m.group(3).replace(",", "").strip())
            printed_closing = float(m.group(4).replace(",", "").strip())
            return opening, printed_debits, printed_credits, printed_closing
        except Exception:
            pass

    m2 = re.search(r"OpeningBalance[:\s]*([\d,]+\.\d{2})", full_text, flags=re.IGNORECASE)
    if m2:
        try:
            opening = float(m2.group(1).replace(",", ""))
            nums = NUM_RE.findall(full_text)
            if len(nums) >= 3:
                printed_debits = float(nums[-3].replace(",", ""))
                printed_credits = float(nums[-2].replace(",", ""))
                printed_closing = float(nums[-1].replace(",", ""))
            return opening, printed_debits, printed_credits, printed_closing
        except Exception:
            pass

    # HDFC sometimes lists "Debits" and "Credits" in a table - try to capture more generically
    m3 = re.search(r"Debits[:\s]*([\d,]+\.\d{2})\s+Credits[:\s]*([\d,]+\.\d{2})", full_text, flags=re.IGNORECASE)
    if m3:
        try:
            printed_debits = float(m3.group(1).replace(",", ""))
            printed_credits = float(m3.group(2).replace(",", ""))
            nums = NUM_RE.findall(full_text)
            if nums:
                printed_closing = float(nums[-1].replace(",", ""))
            return opening, printed_debits, printed_credits, printed_closing
        except Exception:
            pass

    return opening, printed_debits, printed_credits, printed_closing

# parse_pdf_file now returns (rows_list, printed_totals_dict)
def parse_pdf_file(filepath: str, account_password: str):
    """
    Updated parser:
    - Returns tuple: (rows_list, printed_totals_dict)
      printed_totals_dict: {"printed_credits": float or None, "printed_debits": float or None, "printed_closing": float or None}
    - For HDFC-style statements it extracts printed totals from summary when possible.
    - For other banks it falls back to legacy parser but still attempts to extract printed totals.
    """
    try:
        pages = extract_pages_text(filepath, account_password)
    except Exception as e:
        # original fallback to try opening without password
        try:
            pages = extract_pages_text(filepath, None)
        except Exception as e2:
            st.error(f"Failed to open PDF: {os.path.basename(filepath)} — {e2}")
            return [], {"printed_credits": None, "printed_debits": None, "printed_closing": None, "opening_balance": None}

    full_text = "\n\n".join(pages)
    if not full_text.strip():
        st.warning(f"Could not extract text from {os.path.basename(filepath)}")
        return [], {"printed_credits": None, "printed_debits": None, "printed_closing": None, "opening_balance": None}

    # Attempt to extract printed totals regardless (best-effort)
    opening_balance, printed_debits, printed_credits, printed_closing = extract_statement_summary(full_text)
    printed_totals = {
        "printed_credits": printed_credits,
        "printed_debits": printed_debits,
        "printed_closing": printed_closing,
        "opening_balance": opening_balance
    }

    # Quick check: if file appears HDFC-like (header has 'ClosingBalance' or 'StatementSummary'), prefer delta approach
    if ("ClosingBalance" in full_text or "STATEMENTSUMMARY" in full_text or "WithdrawalAmt." in full_text or "Debits" in full_text and "Credits" in full_text):
        # Build transaction-like lines: lines starting with date token
        tx_lines = []
        for p_idx, pg in enumerate(pages, start=1):
            for ln in (pg.splitlines() if pg else []):
                ln_s = ln.strip()
                if DATE_LINE_RE.match(ln_s):
                    tx_lines.append((p_idx, ln_s))

        # If no tx_lines found, fallback to legacy parser
        if not tx_lines:
            rows = _legacy_parse_pdf_file_return_only_rows(filepath, account_password)
            return rows, printed_totals

        # Build tx_records with amount & closing
        tx_records = []
        for idx, (page_num, raw_line) in enumerate(tx_lines):
            amt, closing = parse_amount_and_balance_from_line(raw_line)
            if closing is None:
                # Could be a header/footer line; skip
                continue
            # date string
            date_match = DATE_LINE_RE.match(raw_line)
            date_str = date_match.group(1) if date_match else ""
            # try parse date to datetime if possible (handle dd/mm/yy and dd/mm/yyyy)
            dt_val = None
            for fmt in ("%d/%m/%y", "%d/%m/%Y"):
                try:
                    dt_val = pd.to_datetime(date_str, format=fmt, errors='coerce')
                    if not pd.isna(dt_val):
                        break
                except Exception:
                    dt_val = pd.to_datetime(date_str, errors='coerce')
            tx_records.append({
                "Date": dt_val,
                "Remarks": raw_line,
                "Amount": float(amt) if amt is not None else 0.0,
                "Balance": float(closing),
                "Page": page_num
            })

        if not tx_records:
            rows = _legacy_parse_pdf_file_return_only_rows(filepath, account_password)
            return rows, printed_totals

        # If opening_balance not present, try to estimate robustly:
        # Try both possible openings for first transaction:
        # opening_a = first_closing + first_amount  (assumes first tx was debit)
        # opening_b = first_closing - first_amount  (assumes first tx was credit)
        first = tx_records[0]
        first_closing = float(first['Balance'])
        first_amt = float(first['Amount'])
        candidate_openings = []
        # Candidate A: assume first tx is debit -> opening = closing + amt
        candidate_openings.append(("debit_assumption", first_closing + first_amt))
        # Candidate B: assume first tx is credit -> opening = closing - amt
        candidate_openings.append(("credit_assumption", first_closing - first_amt))

        # if there is some externally extracted opening_balance, include as candidate
        if opening_balance is not None:
            candidate_openings.insert(0, ("extracted_opening", opening_balance))

        # Score each candidate using first few records
        best_opening = None
        best_score = -1
        for name, op in candidate_openings:
            try:
                score = _score_opening_for_records(op, tx_records, tolerance=0.6, sample_size=8)
            except Exception:
                score = -1
            if score > best_score:
                best_score = score
                best_opening = op

        # If none produced a positive score, fallback to debit_assumption
        if best_opening is None:
            best_opening = first_closing + first_amt

        # Now infer full recs using best_opening
        recs = infer_types_by_delta(tx_records, best_opening, tolerance=0.6)

        # Convert recs to expected output format
        out = []
        for r in recs:
            dt = r.get("Date")
            if isinstance(dt, pd.Timestamp):
                date_val = dt
            else:
                try:
                    date_val = pd.to_datetime(r.get("Date"), errors="coerce")
                except Exception:
                    date_val = pd.NaT
            out.append({
                "Date": date_val,
                "Amount": float(r.get("Amount", 0.0)),
                "Type": r.get("Type"),
                "Balance": float(r.get("Balance", 0.0)),
                "Remarks": r.get("Remarks", ""),
                "Source File": os.path.basename(filepath),
                "inference_reason": r.get("inference_reason", "")
            })
        return out, printed_totals

    else:
        # If not HDFC-like, use legacy parser (keeps previous regex behavior for IDBI/Axis/ADCB)
        rows = _legacy_parse_pdf_file_return_only_rows(filepath, account_password)
        return rows, printed_totals

# Helper wrapper: return only rows (used by parse_pdf_file to call legacy)
def _legacy_parse_pdf_file_return_only_rows(filepath: str, account_password: str):
    rows = _legacy_parse_pdf_file(filepath, account_password)
    return rows

# Original legacy parsing logic returns rows (kept mostly as-is; used as fallback)
def _legacy_parse_pdf_file(filepath: str, account_password: str):
    text = ""
    try:
        if account_password:
            with pdfplumber.open(filepath, password=account_password) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        else:
            with pdfplumber.open(filepath) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages])
    except Exception as e:
        try:
            with pdfplumber.open(filepath) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        except Exception as e:
            st.error(f"Failed to open PDF: {os.path.basename(filepath)} — {e}")
            return []

    if not text.strip():
        st.warning(f"Could not extract text from {os.path.basename(filepath)}")

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    data = []
    last_balance = None

    TX_PATTERN = r"^(\d{2}/\d{2}/\d{2})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
    IDBI_PATTERN = r"^\d+\s+(\d{2}/\d{2}/\d{2})\s+\d{2}/\d{2}/\d{2}\s+(.+?)\s+(CR|DR)\s+INR\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
    AXIS_PATTERN = r"^(\d{2}-\d{2}-\d{4})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+(\d+)$"
    ADCB_PATTERN = r"^(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([A-Z0-9\-/]+)\s+([\d,]+\.\d{1,2})\s+([\d,]+\.\d{1,2})\s+([\d,]+\.\d{1,2})$"

    def clean_amt(s: str) -> float:
        if not s:
            return 0.0
        s = re.sub(r"[^\d\.,\-]", "", s)
        s = s.replace(",", "")
        try:
            return float(s)
        except:
            return 0.0

    i = 0
    while i < len(lines):
        line = lines[i]

        m1 = re.match(TX_PATTERN, line)
        if m1:
            date, remarks, amt_str, bal_str = m1.groups()
            try:
                amt_val = float(amt_str.replace(",", ""))
            except:
                amt_val = 0.0
            try:
                bal_val = float(bal_str.replace(",", ""))
            except:
                bal_val = None
            tx_type = "DR"
            if any(kw in remarks.upper() for kw in ["NEFT CR", "IMPS", "UPI", "CREDIT", "REFUND", "INTEREST"]):
                tx_type = "CR"
            data.append({
                "Date": pd.to_datetime(date, format="%d/%m/%y", errors="coerce"),
                "Amount": amt_val,
                "Type": tx_type,
                "Balance": bal_val,
                "Remarks": remarks,
                "Source File": os.path.basename(filepath)
            })
            last_balance = bal_val
            i += 1
            continue

        m2 = re.match(IDBI_PATTERN, line)
        if m2:
            date, remarks, tx_type, amt_str, bal_str = m2.groups()
            amt_val = float(amt_str.replace(",", ""))
            bal_val = float(bal_str.replace(",", ""))
            data.append({
                "Date": pd.to_datetime(date, format="%d/%m/%y", errors="coerce"),
                "Amount": amt_val,
                "Type": tx_type,
                "Balance": bal_val,
                "Remarks": remarks,
                "Source File": os.path.basename(filepath)
            })
            last_balance = bal_val
            i += 1
            continue

        if (i + 1) < len(lines):
            nxt = lines[i + 1]
            m3 = re.match(AXIS_PATTERN, nxt)
            if m3:
                date, part2, amt_str, bal_str, br = m3.groups()
                remarks = (line + " " + part2).strip()
                amt_val = float(amt_str.replace(",", ""))
                bal_val = float(bal_str.replace(",", ""))
                tx_type = "CR" if bal_val > (last_balance or 0) else "DR"
                data.append({
                    "Date": pd.to_datetime(date, format="%d-%m-%Y", errors="coerce"),
                    "Amount": amt_val,
                    "Type": tx_type,
                    "Balance": bal_val,
                    "Remarks": remarks,
                    "Source File": os.path.basename(filepath)
                })
                last_balance = bal_val
                i += 2
                continue

        m4 = re.match(ADCB_PATTERN, line)
        if m4:
            post_date, value_date, desc, ref, debit_str, credit_str, bal_str = m4.groups()
            debit_val = clean_amt(debit_str)
            credit_val = clean_amt(credit_str)
            bal_val = clean_amt(bal_str)

            if credit_val > 0 and debit_val == 0:
                amt_val = credit_val
                tx_type = "CR"
            elif debit_val > 0 and credit_val == 0:
                amt_val = debit_val
                tx_type = "DR"
            else:
                if credit_val >= debit_val:
                    amt_val = credit_val
                    tx_type = "CR"
                else:
                    amt_val = debit_val
                    tx_type = "DR"

            remarks = f"{desc} {ref}".strip()
            data.append({
                "Date": pd.to_datetime(post_date, format="%d/%m/%Y", errors="coerce"),
                "Amount": amt_val,
                "Type": tx_type,
                "Balance": bal_val,
                "Remarks": remarks,
                "Source File": os.path.basename(filepath)
            })
            last_balance = bal_val
            i += 1
            continue

        i += 1

    return data

def parse_many_pdfs(filepaths, account_password: str):
    """
    Now returns tuple: (all_rows_list, aggregated_printed_totals)
    aggregated_printed_totals = {"printed_credits": sum or None, "printed_debits": sum or None}
    If none of the files contain printed totals, values will be None.
    """
    all_rows = []
    total_printed_credits = 0.0
    total_printed_debits = 0.0
    any_printed = False
    for p in filepaths:
        rows, printed = parse_pdf_file(p, account_password)
        if rows:
            all_rows.extend(rows)
        # printed could be None values
        pc = printed.get("printed_credits") if printed else None
        pd_ = printed.get("printed_debits") if printed else None
        if pc is not None:
            any_printed = True
            total_printed_credits += float(pc)
        if pd_ is not None:
            any_printed = True
            total_printed_debits += float(pd_)
    aggregated = {
        "printed_credits": total_printed_credits if any_printed else None,
        "printed_debits": total_printed_debits if any_printed else None
    }
    return all_rows, aggregated

# ──────────────────────────────────────────────────────────────────────────────
# Category detection
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_CATEGORIES = [
    "Restaurant", "Hospital", "Taxi", "Misc", "Grocery",
    "Credit card payment", "Subscription", "Sutherland",
    "Rent", "Electricity", "Cashback", "Travel"
]

DEFAULT_CATEGORY_KEYWORDS = {
    "Restaurant": ["restaurant","resto","restuarant","dine","dining","cafe","coffee","bar","zomato","swiggy","dominos","pizza","mcdonald","burger","kfc","food","eatery"],
    "Hospital": ["hospital","hostpital","clinic","medical","care","apollo","fortis","manipal","health"],
    "Taxi": ["uber","ola","cab","taxi","ride","auto","ola cabs","uber auto","olaauto","transport"],
    "Grocery": ["grocery","grosery","supermarket","bigbasket","dmart","reliance fresh","spencer","store","mart","super","vegetables","provision"],
    "Credit card payment": ["credit card","card payment","visa","mastercard","amex","creditcard","cardpayment","credit","billdesk"],
    "Subscription": ["subscription","subscrption","netflix","spotify","prime","hotstar","disney","youtube premium","zee5","sony liv"],
    "Sutherland": ["sutherland"],
    "Rent": ["rent","rental","house rent","flat rent","pg","lease"],
    "Electricity": ["electricity","power","electric bill","tneb","mahavitaran","bill payment","bills","current"],
    "Cashback": ["cashback","reward","rewards","referral","cash back"],
    "Travel": ["flight","air","indigo","spicejet","goair","air india","train","irctc","hotel","booking","travel","trip","journey"],
}

def detect_category(remarks: str, categories):
    if remarks is None:
        return "Misc"
    text = str(remarks).lower()
    if not text.strip():
        return "Misc"

    for cat in categories:
        kws = DEFAULT_CATEGORY_KEYWORDS.get(cat, [])
        for kw in kws:
            if kw in text:
                return cat

    words = text.split()
    for word in words:
        for cat, kws in DEFAULT_CATEGORY_KEYWORDS.items():
            match = get_close_matches(word, kws, n=1, cutoff=0.8)
            if match:
                return cat

    for cat in categories:
        if cat.lower() in text:
            return cat

    return "Misc"

# ──────────────────────────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "categories" not in st.session_state:
    st.session_state.categories = DEFAULT_CATEGORIES.copy()

# ──────────────────────────────────────────────────────────────────────────────
# Auth UI
# ──────────────────────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    # Glassmorphism design with dark theme
    st.markdown("""
        <style>
        .stApp {
            background: #0a0a0a;
            background-image: 
                radial-gradient(circle at 20% 20%, rgba(0, 255, 200, 0.2) 0%, transparent 60%),
                radial-gradient(circle at 80% 20%, rgba(0, 200, 255, 0.2) 0%, transparent 60%);
            background-attachment: fixed;
        }
        .main .block-container {
            padding-top: 3rem;
            padding-bottom: 3rem;
            max-width: 480px;
        }
        /* Ensure the column container forms a complete glass cube */
        .main .block-container > div[data-testid="column-container"] {
            display: flex;
            gap: 1rem;
        }
        .glass-card-wrapper {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 
                0 8px 32px rgba(0, 0, 0, 0.4),
                inset 0 1px 0 rgba(255, 255, 255, 0.1);
            padding: 2rem 2rem;
            width: 100%;
            animation: slideUp 0.6s ease-out;
            position: relative;
            overflow: hidden;
        }
        .glass-card {
            position: relative;
            z-index: 1;
        }
        .glass-card::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(0, 255, 200, 0.1) 0%, transparent 70%);
            animation: rotate 20s linear infinite;
            pointer-events: none;
        }
        .glass-card::after {
            content: '';
            position: absolute;
            top: -30%;
            right: -30%;
            width: 150%;
            height: 150%;
            background: radial-gradient(circle, rgba(0, 200, 255, 0.1) 0%, transparent 70%);
            animation: rotate 15s linear infinite reverse;
            pointer-events: none;
        }
        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        .auth-content {
            position: relative;
            z-index: 1;
        }
        .auth-header {
            text-align: left;
            margin-bottom: 2rem;
        }
        .auth-header h1 {
            font-size: 2rem;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 0.5rem;
            letter-spacing: -0.3px;
            line-height: 1.2;
        }
        .auth-header p {
            color: rgba(255, 255, 255, 0.65);
            font-size: 0.95rem;
            font-weight: 400;
            margin: 0;
            line-height: 1.4;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0;
            background: transparent;
            border-radius: 0;
            padding: 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            margin-bottom: 2rem;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 0;
            padding: 0.875rem 0;
            font-weight: 500;
            transition: all 0.3s ease;
            color: rgba(255, 255, 255, 0.5);
            background: transparent;
            border-bottom: 2px solid transparent;
            margin-right: 2.5rem;
            font-size: 0.95rem;
        }
        .stTabs [aria-selected="true"] {
            color: #ffffff;
            border-bottom-color: #ff6b6b;
            background: transparent;
            font-weight: 600;
        }
        .stTabs [aria-selected="false"]:hover {
            color: rgba(255, 255, 255, 0.8);
        }
        .stTextInput {
            margin-bottom: 1.25rem;
        }
        .stTextInput>div>div>input {
            border-radius: 14px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 0.875rem 1.25rem;
            font-size: 0.95rem;
            transition: all 0.3s ease;
            background-color: rgba(255, 255, 255, 0.04);
            color: #ffffff;
        }
        .stTextInput>div>div>input::placeholder {
            color: rgba(255, 255, 255, 0.35);
        }
        .stTextInput>div>div>input:focus {
            border-color: rgba(0, 255, 200, 0.4);
            box-shadow: 0 0 0 3px rgba(0, 255, 200, 0.08);
            background-color: rgba(255, 255, 255, 0.06);
            outline: none;
        }
        .stTextInput>div>div>input:hover {
            border-color: rgba(255, 255, 255, 0.15);
            background-color: rgba(255, 255, 255, 0.05);
        }
        .stTextInput label {
            font-weight: 500;
            color: rgba(255, 255, 255, 0.95);
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
        }
        .stButton {
            margin-top: 0.75rem;
        }
        .stButton>button {
            background: linear-gradient(135deg, #00d4ff 0%, #00ffc8 100%);
            color: #0a0a0a;
            border: none;
            border-radius: 14px;
            padding: 0.875rem 2rem;
            font-weight: 600;
            font-size: 0.95rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px rgba(0, 255, 200, 0.25);
            width: 100%;
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 30px rgba(0, 255, 200, 0.35);
            background: linear-gradient(135deg, #00c4ef 0%, #00e6b8 100%);
        }
        .auth-link {
            text-align: center;
            color: rgba(255, 255, 255, 0.6);
            font-size: 0.8rem;
        }
        .auth-link a {
            color: #00ffc8;
            text-decoration: none;
            font-weight: 500;
        }
        .auth-link a:hover {
            text-decoration: underline;
        }
        .stSuccess, .stError, .stWarning, .stInfo {
            background-color: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            color: #ffffff;
            margin-top: 0.5rem;
            margin-bottom: 0.5rem;
        }
        .element-container {
            margin-bottom: 0.5rem;
        }
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column"] > [data-testid="stVerticalBlock"] {
            gap: 0.5rem;
        }
        /* Glass cube wrapper - matches Dribbble design exactly */
        .glass-cube-wrapper {
            background: rgba(255, 255, 255, 0.03) !important;
            backdrop-filter: blur(30px) !important;
            -webkit-backdrop-filter: blur(30px) !important;
            border-radius: 24px !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            box-shadow: 
                0 8px 32px rgba(0, 0, 0, 0.5),
                inset 0 1px 0 rgba(255, 255, 255, 0.08),
                inset 0 -1px 0 rgba(255, 255, 255, 0.03) !important;
            padding: 2.5rem 2.5rem !important;
            position: relative !important;
            overflow: hidden !important;
            margin: 0 auto !important;
            width: 100% !important;
            min-height: 400px !important;
        }
        .glass-cube-wrapper::before {
            content: '';
            position: absolute;
            top: -40%;
            left: -40%;
            width: 180%;
            height: 180%;
            background: radial-gradient(circle, rgba(0, 255, 200, 0.15) 0%, transparent 65%);
            animation: rotate 25s linear infinite;
            pointer-events: none;
            z-index: 0;
        }
        .glass-cube-wrapper::after {
            content: '';
            position: absolute;
            top: -40%;
            right: -40%;
            width: 180%;
            height: 180%;
            background: radial-gradient(circle, rgba(0, 200, 255, 0.15) 0%, transparent 65%);
            animation: rotate 20s linear infinite reverse;
            pointer-events: none;
            z-index: 0;
        }
        .glass-cube-wrapper > * {
            position: relative;
            z-index: 1;
        }
        /* Target the middle column and apply glass cube styling - matches Dribbble exactly */
        .main .block-container > div[data-testid="column-container"] > div:nth-child(2),
        .main .block-container > div > div:nth-child(2),
        .main .block-container > div[data-testid="column-container"] > div:nth-of-type(2),
        div.glass-cube-applied,
        div[data-testid="column"]:nth-of-type(2),
        .glass-cube-wrapper {
            background: rgba(255, 255, 255, 0.03) !important;
            backdrop-filter: blur(30px) !important;
            -webkit-backdrop-filter: blur(30px) !important;
            border-radius: 24px !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            box-shadow: 
                0 8px 32px rgba(0, 0, 0, 0.5),
                inset 0 1px 0 rgba(255, 255, 255, 0.08),
                inset 0 -1px 0 rgba(255, 255, 255, 0.03) !important;
            padding: 2.5rem 2.5rem !important;
            position: relative !important;
            overflow: hidden !important;
            margin: 0 !important;
            box-sizing: border-box !important;
            width: 100% !important;
        }
        /* Animated backgrounds via CSS pseudo-elements - matches Dribbble design */
        .main .block-container > div[data-testid="column-container"] > div:nth-child(2)::before,
        .main .block-container > div > div:nth-child(2)::before,
        div.glass-cube-applied::before,
        div[data-testid="column"]:nth-of-type(2)::before,
        .glass-cube-wrapper::before {
            content: '';
            position: absolute;
            top: -40%;
            left: -40%;
            width: 180%;
            height: 180%;
            background: radial-gradient(circle, rgba(0, 255, 200, 0.15) 0%, transparent 65%);
            animation: rotate 25s linear infinite;
            pointer-events: none;
            z-index: 0;
        }
        .main .block-container > div[data-testid="column-container"] > div:nth-child(2)::after,
        .main .block-container > div > div:nth-child(2)::after,
        div.glass-cube-applied::after,
        div[data-testid="column"]:nth-of-type(2)::after,
        .glass-cube-wrapper::after {
            content: '';
            position: absolute;
            top: -40%;
            right: -40%;
            width: 180%;
            height: 180%;
            background: radial-gradient(circle, rgba(0, 200, 255, 0.15) 0%, transparent 65%);
            animation: rotate 20s linear infinite reverse;
            pointer-events: none;
            z-index: 0;
        }
        /* Ensure all content is above animated backgrounds */
        .main .block-container > div[data-testid="column-container"] > div:nth-child(2) > *:not(.glass-bg-before):not(.glass-bg-after),
        .main .block-container > div > div:nth-child(2) > *:not(.glass-bg-before):not(.glass-bg-after),
        div.glass-cube-applied > *:not(.glass-bg-before):not(.glass-bg-after),
        div[data-testid="column"]:nth-of-type(2) > *:not(.glass-bg-before):not(.glass-bg-after) {
            position: relative !important;
            z-index: 1 !important;
        }
        </style>
        <script>
        // Enhanced function to create glass cube around ALL content
        function createGlassCube() {
            // First, try to find and style the glass-cube-wrapper
            let targetContainer = document.querySelector('.glass-cube-wrapper');
            
            // If wrapper exists, style it to match Dribbble design exactly
            if (targetContainer) {
                if (!targetContainer.classList.contains('glass-cube-applied')) {
                    targetContainer.classList.add('glass-cube-applied');
                }
                
                // Apply exact Dribbble styling
                Object.assign(targetContainer.style, {
                    background: 'rgba(255, 255, 255, 0.03)',
                    backdropFilter: 'blur(30px)',
                    WebkitBackdropFilter: 'blur(30px)',
                    borderRadius: '24px',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08), inset 0 -1px 0 rgba(255, 255, 255, 0.03)',
                    padding: '2.5rem 2.5rem',
                    position: 'relative',
                    overflow: 'hidden',
                    margin: '0 auto',
                    width: '100%',
                    boxSizing: 'border-box',
                    minHeight: '400px'
                });
                
                // Add animated backgrounds matching Dribbble
                let bgBefore = targetContainer.querySelector('.glass-bg-before');
                let bgAfter = targetContainer.querySelector('.glass-bg-after');
                
                if (!bgBefore) {
                    bgBefore = document.createElement('div');
                    bgBefore.className = 'glass-bg-before';
                    Object.assign(bgBefore.style, {
                        position: 'absolute',
                        top: '-40%',
                        left: '-40%',
                        width: '180%',
                        height: '180%',
                        background: 'radial-gradient(circle, rgba(0, 255, 200, 0.15) 0%, transparent 65%)',
                        animation: 'rotate 25s linear infinite',
                        pointerEvents: 'none',
                        zIndex: '0'
                    });
                    targetContainer.insertBefore(bgBefore, targetContainer.firstChild);
                }
                
                if (!bgAfter) {
                    bgAfter = document.createElement('div');
                    bgAfter.className = 'glass-bg-after';
                    Object.assign(bgAfter.style, {
                        position: 'absolute',
                        top: '-40%',
                        right: '-40%',
                        width: '180%',
                        height: '180%',
                        background: 'radial-gradient(circle, rgba(0, 200, 255, 0.15) 0%, transparent 65%)',
                        animation: 'rotate 20s linear infinite reverse',
                        pointerEvents: 'none',
                        zIndex: '0'
                    });
                    targetContainer.appendChild(bgAfter);
                }
                
                // Ensure all content is above backgrounds
                Array.from(targetContainer.children).forEach(child => {
                    if (child !== bgBefore && child !== bgAfter) {
                        if (child.style) {
                            child.style.position = 'relative';
                            child.style.zIndex = '1';
                        }
                    }
                });
                
                return; // Exit early if wrapper was found and styled
            }
            
            // Fallback: Find and style the middle column container directly
            if (!targetContainer) {
                // Method 1: Find column container
                const columnContainer = document.querySelector('.main .block-container > div[data-testid="column-container"]');
                if (columnContainer) {
                    const cols = columnContainer.children;
                    if (cols.length >= 2) {
                        targetContainer = cols[1]; // Middle column
                    }
                }
                
                // Method 2: Find by structure
                if (!targetContainer) {
                    const blockContainer = document.querySelector('.main .block-container');
                    if (blockContainer) {
                        const row = blockContainer.querySelector('div[data-testid="column-container"]') || blockContainer.children[0];
                        if (row && row.children.length >= 2) {
                            targetContainer = row.children[1];
                        }
                    }
                }
                
                // Method 3: Find by content
                if (!targetContainer) {
                    const tabs = document.querySelector('.stTabs');
                    if (tabs) {
                        targetContainer = tabs.closest('div[data-testid="column"]') || tabs.parentElement.parentElement;
                    }
                }
            }
            
            if (targetContainer) {
                if (!targetContainer.classList.contains('glass-cube-applied')) {
                    targetContainer.classList.add('glass-cube-applied');
                }
                
                // Apply exact Dribbble styling
                Object.assign(targetContainer.style, {
                    background: 'rgba(255, 255, 255, 0.03)',
                    backdropFilter: 'blur(30px)',
                    WebkitBackdropFilter: 'blur(30px)',
                    borderRadius: '24px',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08), inset 0 -1px 0 rgba(255, 255, 255, 0.03)',
                    padding: '2.5rem 2.5rem',
                    position: 'relative',
                    overflow: 'hidden',
                    margin: '0',
                    width: '100%',
                    boxSizing: 'border-box',
                    minHeight: '400px'
                });
                
                // Add animated backgrounds matching Dribbble
                let bgBefore = targetContainer.querySelector('.glass-bg-before');
                let bgAfter = targetContainer.querySelector('.glass-bg-after');
                
                if (!bgBefore) {
                    bgBefore = document.createElement('div');
                    bgBefore.className = 'glass-bg-before';
                    Object.assign(bgBefore.style, {
                        position: 'absolute',
                        top: '-40%',
                        left: '-40%',
                        width: '180%',
                        height: '180%',
                        background: 'radial-gradient(circle, rgba(0, 255, 200, 0.15) 0%, transparent 65%)',
                        animation: 'rotate 25s linear infinite',
                        pointerEvents: 'none',
                        zIndex: '0'
                    });
                    targetContainer.insertBefore(bgBefore, targetContainer.firstChild);
                }
                
                if (!bgAfter) {
                    bgAfter = document.createElement('div');
                    bgAfter.className = 'glass-bg-after';
                    Object.assign(bgAfter.style, {
                        position: 'absolute',
                        top: '-40%',
                        right: '-40%',
                        width: '180%',
                        height: '180%',
                        background: 'radial-gradient(circle, rgba(0, 200, 255, 0.15) 0%, transparent 65%)',
                        animation: 'rotate 20s linear infinite reverse',
                        pointerEvents: 'none',
                        zIndex: '0'
                    });
                    targetContainer.appendChild(bgAfter);
                }
                
                // Ensure all content is above backgrounds
                Array.from(targetContainer.children).forEach(child => {
                    if (child !== bgBefore && child !== bgAfter) {
                        if (child.style) {
                            child.style.position = 'relative';
                            child.style.zIndex = '1';
                        }
                    }
                });
            }
        }
        
        // More aggressive function to ensure glass cube wraps everything
        function initGlassCube() {
            createGlassCube();
            // Try multiple times with delays
            setTimeout(createGlassCube, 50);
            setTimeout(createGlassCube, 150);
            setTimeout(createGlassCube, 300);
            setTimeout(createGlassCube, 500);
            setTimeout(createGlassCube, 800);
            setTimeout(createGlassCube, 1200);
        }
        
        // Run immediately
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                initGlassCube();
                // Keep trying
                setInterval(createGlassCube, 2000);
            });
        } else {
            initGlassCube();
            // Keep trying
            setInterval(createGlassCube, 2000);
        }
        
        // Watch for any DOM changes
        const observer = new MutationObserver(function(mutations) {
            let shouldUpdate = false;
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes.length > 0 || mutation.removedNodes.length > 0) {
                    shouldUpdate = true;
                }
            });
            if (shouldUpdate) {
                setTimeout(createGlassCube, 100);
            }
        });
        
        // Observe the entire document
        observer.observe(document.body, { 
            childList: true, 
            subtree: true,
            attributes: false
        });
        
        // Also listen for Streamlit events
        window.addEventListener('load', initGlassCube);
        document.addEventListener('streamlit:render', initGlassCube);
        </script>
    """, unsafe_allow_html=True)
    
    # Main container with centered glass card
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        # Glass cube wrapper - will be styled by JavaScript
        st.markdown("""
            <div class="glass-cube-wrapper">
                <div class="auth-content">
                    <div class="auth-header">
                        <h1>Welcome back</h1>
                        <p>Sign in to your account</p>
                    </div>
        """, unsafe_allow_html=True)
        
        auth_tab1, auth_tab2 = st.tabs(["Login", "Register"])
        
        with auth_tab1:
            log_user = st.text_input(
                "Account Number", 
                key="login_user", 
                placeholder="Enter your account number"
            )
            
            log_pass = st.text_input(
                "Password", 
                type="password", 
                key="login_pass", 
                placeholder="Enter your password"
            )
            
            if st.button("Sign In", use_container_width=True, type="primary"):
                if not log_user or not log_pass:
                    st.warning("⚠️ Please enter both account number and password.")
                else:
                    ok, msg = login_user_db(log_user.strip(), log_pass.strip())
                    if ok:
                        st.session_state.authenticated = True
                        st.session_state.username = log_user.strip()
                        st.success(f"✅ {msg}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
            
            st.markdown("""
                <div class="auth-link" style="margin-top: 1rem;">
                    Don't have an account? Switch to the Register tab above
                </div>
            """, unsafe_allow_html=True)
        
        with auth_tab2:
            reg_user = st.text_input(
                "Account Number", 
                key="reg_user", 
                placeholder="Create your account number"
            )
            
            reg_pass = st.text_input(
                "Password", 
                type="password", 
                key="reg_pass", 
                placeholder="Create a strong password"
            )
            
            if st.button("Create Account", use_container_width=True, type="primary"):
                if not reg_user or not reg_pass:
                    st.warning("⚠️ Please enter both account number and password.")
                else:
                    ok, msg = register_user_db(reg_user.strip(), reg_pass.strip())
                    if ok:
                        st.success(f"✅ {msg}")
                        st.info("👉 Please switch to the Login tab to access your account.")
                    else:
                        st.error(f"❌ {msg}")
            
            st.markdown("""
                <div class="auth-link" style="margin-top: 1rem;">
                    Already have an account? Switch to the Login tab above
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("""
                </div>
            </div>
        """, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Main App
# ──────────────────────────────────────────────────────────────────────────────
if st.session_state.authenticated:
    user = st.session_state.username
    
    # Header with user info and logout
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("💰 Bank Statement Analyzer")
    with col2:
        st.markdown(f"""
            <div style='text-align: right; padding-top: 10px;'>
                <p style='color: #888; margin: 0; font-size: 12px;'>Logged in as</p>
                <p style='font-weight: 600; margin: 0; font-size: 16px; color: #4CAF50;'>👤 {user}</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True, key="header_logout"):
            st.session_state.authenticated = False
            st.session_state.username = ""
            st.rerun()
    
    st.markdown("---")
    
    # ────────────────────────────────────────────────
    # Sidebar - File Manager and Category Management
    # ────────────────────────────────────────────────
    saved_items = get_saved_pdfs(user)
    selected_paths = []

    # Initialize or update pdf_names to include all saved PDFs
    if "pdf_names" not in st.session_state:
        st.session_state.pdf_names = {}
    
    # Sync pdf_names with saved_items to include any new PDFs
    for item in saved_items:
        if item['id'] not in st.session_state.pdf_names:
            st.session_state.pdf_names[item['id']] = item['filename']

    with st.sidebar:
        st.markdown("### 📂 File Manager")
      
        if saved_items:
            st.markdown(f"**{len(saved_items)} file(s) in library**")
            st.markdown("<br>", unsafe_allow_html=True)
            
            for i in saved_items:
                with st.expander(f"📄 {st.session_state.pdf_names.get(i['id'], i['filename'])}", expanded=False):
                    upload_date = i['uploaded_at'].split('T')[0]
                    st.caption(f"📅 Uploaded: {upload_date}")
                    
                    if st.checkbox("Select for analysis", key=f"chk_{i['id']}"):
                        selected_paths.append(i["filepath"])
                    
                    key_name = f"rename_{i['id']}"
                    pdf_display_name = st.session_state.pdf_names.get(i['id'], i['filename'])
                    if key_name not in st.session_state:
                        st.session_state[key_name] = pdf_display_name

                    def rename_callback(file_id=i['id'], key_name=key_name):
                        new_name = st.session_state[key_name].strip()
                        if new_name and new_name != st.session_state.pdf_names.get(file_id, new_name):
                            st.session_state.pdf_names[file_id] = new_name
                            conn = get_db()
                            cur = conn.cursor()
                            cur.execute("UPDATE pdf_files SET filename=? WHERE id=?", (new_name, file_id))
                            conn.commit()
                            conn.close()
                            if "last_df" in st.session_state:
                                old_name = [item for item in saved_items if item['id'] == file_id][0]['filename']
                                st.session_state.last_df.loc[
                                    st.session_state.last_df["Source File"] == old_name, "Source File"
                                ] = new_name

                    st.text_input(
                        "Rename file",
                        value=pdf_display_name,
                        key=key_name,
                        on_change=rename_callback
                    )

                    if st.button("🗑️ Delete", key=f"del_{i['id']}", use_container_width=True):
                        delete_pdf(i['id'])
                        st.success(f"✅ Deleted {pdf_display_name}")
                        st.session_state.pdf_names.pop(i['id'], None)
                        if key_name in st.session_state:
                            st.session_state.pop(key_name)
                        st.rerun()
        else:
            st.info("📭 No PDFs in library yet.\n\nUpload some files to get started!")
        
        st.markdown("---")
        
        # Category Explorer
        if "last_df" in st.session_state:
            st.markdown("### 🏷️ Category Explorer")
            df = st.session_state.last_df

            for cat in st.session_state.categories:
                cat_df = df[df["Category"] == cat]
                if not cat_df.empty:
                    total_amt = cat_df["Amount"].sum()
                    with st.expander(f"{cat} • ₹{total_amt:,.0f} ({len(cat_df)})", expanded=False):
                        st.dataframe(
                            cat_df[["Date", "Amount", "Type", "Remarks"]].head(10), 
                            use_container_width=True, 
                            height=200
                        )
                        if len(cat_df) > 10:
                            st.caption(f"Showing 10 of {len(cat_df)} transactions")

            st.markdown("---")
            st.markdown("### ➕ Manage Categories")
            new_cat = st.text_input("New Category", placeholder="e.g., Entertainment")
            new_kw = st.text_input("Keyword", placeholder="e.g., cinema")
            if st.button("💾 Add Category/Keyword", use_container_width=True):
                if new_cat and new_kw:
                    if new_cat not in st.session_state.categories:
                        st.session_state.categories.append(new_cat)
                    DEFAULT_CATEGORY_KEYWORDS.setdefault(new_cat, []).append(new_kw.lower())
                    st.success(f"✅ Added '{new_kw}' to '{new_cat}'")
                else:
                    st.warning("⚠️ Please enter both fields.")
        
        st.markdown("---")
        st.markdown("""
            <div style='text-align: center; padding: 12px; background: rgba(33, 150, 243, 0.1); border-radius: 8px;'>
                <div style='font-size: 11px; color: #888;'>Need help?</div>
                <div style='font-size: 10px; color: #666; margin-top: 4px;'>Supported: HDFC • IDBI • Axis • ADCB</div>
            </div>
        """, unsafe_allow_html=True)
    
    # ────────────────────────────────────────────────────────────────
    # Main content area
    
    # Upload section with better styling
    st.markdown("### 📤 Upload Bank Statements")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded_files = st.file_uploader(
            "Drop your PDF files here or click to browse",
            type=["pdf"],
            accept_multiple_files=True,
            key="uploader_key",
            help="Upload one or more bank statement PDFs. Supported formats: HDFC, IDBI, Axis, ADCB and more"
        )
    with col2:
        st.markdown("""
            <div style='padding: 20px; background: rgba(76, 175, 80, 0.1); border-radius: 8px; margin-top: 8px;'>
                <div style='text-align: center;'>
                    <div style='font-size: 24px; font-weight: 600; color: #4CAF50;'>📁</div>
                    <div style='font-size: 12px; color: #888; margin-top: 8px;'>Supported Banks</div>
                    <div style='font-size: 11px; color: #666; margin-top: 4px;'>HDFC • IDBI<br/>Axis • ADCB</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Show success message if files were just uploaded (persists after rerun)
    if "just_uploaded_files" in st.session_state and st.session_state.just_uploaded_files:
        file_list = "\n".join([f"• {fname}" for fname in st.session_state.just_uploaded_files])
        st.success(f"""
            ✅ **Successfully saved {len(st.session_state.just_uploaded_files)} file(s)!**
            
            {file_list}
            
            👉 Files are now available in the File Manager (left sidebar)
        """)
        st.balloons()
        # Clear the flag after showing the message
        st.session_state.just_uploaded_files = None

    new_uploaded_paths = []
    if uploaded_files:
        if "saved_file_names" not in st.session_state:
            st.session_state.saved_file_names = set()
        unsaved_files = [f for f in uploaded_files if f.name not in st.session_state.saved_file_names]
        if unsaved_files:
            with st.spinner("💾 Saving files to your library..."):
                new_uploaded_paths = save_uploaded_files(user, unsaved_files)
                for f in unsaved_files:
                    st.session_state.saved_file_names.add(f.name)
            
            # Store uploaded file names in session state for display after rerun
            st.session_state.just_uploaded_files = [f.name for f in unsaved_files]
            # Refresh the page to show uploaded PDFs in sidebar automatically
            st.rerun()
   

    if not selected_paths and new_uploaded_paths:
        selected_paths = new_uploaded_paths

    st.markdown("---")
    
    # Analysis section with better empty state
    st.markdown("### 🔍 Analysis")
    
    if not selected_paths and "last_df" not in st.session_state:
        st.info("""
            ### 👋 Welcome to Bank Statement Analyzer!
            
            **Get started in 3 easy steps:**
            
            1. 📤 **Upload** your bank statement PDFs using the section above
            2. 📂 **Select** files from the sidebar File Manager (they'll be checked automatically after upload)
            3. ▶️ **Click** the Run Analysis button below
            
            Your financial insights are just a click away! 🚀
        """)
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if selected_paths:
            st.success(f"✅ {len(selected_paths)} file(s) ready for analysis")
        elif "last_df" in st.session_state:
            st.info("💡 Select files from the sidebar to analyze")
    with col2:
        pass  # Empty space
    with col3:
        run_btn = st.button("▶️ Run Analysis", use_container_width=True, type="primary", disabled=(not selected_paths))

    if run_btn:
        if not selected_paths:
            st.warning("⚠️ Please select PDFs from the sidebar or upload new files.")
        else:
            with st.spinner("🔄 Parsing statements... This may take a moment."):
                rows, printed_totals = parse_many_pdfs(selected_paths, account_password=user)
            
            if rows:
                df = pd.DataFrame(rows)

                # Use printed totals if available; otherwise fall back to computed totals
                printed_credits = printed_totals.get("printed_credits")
                printed_debits = printed_totals.get("printed_debits")

                # Compute fallback totals
                computed_credit = df[df["Type"] == "CR"]["Amount"].sum() if not df.empty else 0.0
                computed_debit = df[df["Type"] == "DR"]["Amount"].sum() if not df.empty else 0.0

                # Choose totals to display: prefer printed values when present
                total_credit = float(printed_credits) if printed_credits is not None else float(computed_credit)
                total_debit = float(printed_debits) if printed_debits is not None else float(computed_debit)

                df["Category"] = df["Remarks"].apply(lambda r: detect_category(r, st.session_state.categories))
                st.session_state.last_df = df

                # Quick stats at the top
                st.markdown("### 📈 Summary")
                col1, col2, col3, col4 = st.columns(4)
                
                net_flow = total_credit - total_debit
                transaction_count = len(df)
                
                with col1:
                    st.metric("💰 Total Credit", f"₹{total_credit:,.2f}", delta=None)
                with col2:
                    st.metric("💸 Total Debit", f"₹{total_debit:,.2f}", delta=None)
                with col3:
                    delta_color = "normal" if net_flow >= 0 else "inverse"
                    st.metric("📊 Net Flow", f"₹{net_flow:,.2f}", delta=f"{'Positive' if net_flow >= 0 else 'Negative'}")
                with col4:
                    st.metric("🧾 Transactions", f"{transaction_count:,}")

                st.markdown("---")

                # Detailed tabs
                tab1, tab2, tab3, tab4, tab5 = st.tabs([
                    "📋 All Transactions", 
                    "📂 By File", 
                    "📆 Monthly Trends",
                    "📊 Category Analysis",
                    "🏆 Top Transactions"
                ])
                
                with tab1:
                    st.markdown("#### Transaction History")
                    
                    # Search and Filters
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        search_term = st.text_input("🔍 Search transactions", placeholder="Search by remarks...")
                    with col2:
                        st.write("")  # Spacer
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        filter_type = st.selectbox("Transaction Type", ["All", "Credit", "Debit"])
                    with col2:
                        categories_list = ["All"] + sorted(df["Category"].unique().tolist())
                        filter_category = st.selectbox("Category", categories_list)
                    with col3:
                        filter_file = st.selectbox("Source File", ["All"] + df["Source File"].unique().tolist())
                    
                    # Apply filters
                    filtered_df = df.copy()
                    
                    # Search filter
                    if search_term:
                        filtered_df = filtered_df[
                            filtered_df["Remarks"].str.contains(search_term, case=False, na=False)
                        ]
                    
                    if filter_type != "All":
                        filtered_df = filtered_df[filtered_df["Type"] == ("CR" if filter_type == "Credit" else "DR")]
                    if filter_category != "All":
                        filtered_df = filtered_df[filtered_df["Category"] == filter_category]
                    if filter_file != "All":
                        filtered_df = filtered_df[filtered_df["Source File"] == filter_file]
                    
                    # -------------------------
                    # Format display dataframe (robust)
                    # -------------------------
                    display_df = filtered_df.copy()

                    # Ensure Date is a datetime — safe conversion
                    display_df["Date"] = pd.to_datetime(display_df["Date"], errors="coerce")

                    # If Date conversion succeeded, format as string; otherwise keep original
                    display_df["Date_display"] = display_df["Date"].dt.strftime("%d %b %Y")
                    display_df.loc[display_df["Date"].isna(), "Date_display"] = display_df.loc[display_df["Date"].isna(), "Date"].astype(str)

                    # Keep the existing columns but use the safe Date_display
                    display_df = display_df.assign(Amount=display_df["Amount"].apply(lambda x: f"₹{x:,.2f}"))
                    display_df = display_df.sort_values("Date", ascending=False)

                    # Show simple message if no records
                    if display_df.empty:
                        st.info("No transactions to show for the selected filters.")
                    else:
                        # Use st.dataframe as primary; fallback to st.table if any issue
                        try:
                            st.dataframe(
                                display_df[["Date_display", "Amount", "Type", "Category", "Remarks", "Source File"]],
                                use_container_width=True,
                                height=500
                            )
                        except Exception:
                            st.table(display_df[["Date_display", "Amount", "Type", "Category", "Remarks", "Source File"]].head(200))
                    
                    # Summary of filtered results
                    if len(filtered_df) > 0:
                        filtered_credit = filtered_df[filtered_df["Type"] == "CR"]["Amount"].sum()
                        filtered_debit = filtered_df[filtered_df["Type"] == "DR"]["Amount"].sum()
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.caption(f"📊 Showing {len(filtered_df)} of {len(df)} transactions")
                        with col2:
                            st.caption(f"💰 Filtered Credit: ₹{filtered_credit:,.2f}")
                        with col3:
                            st.caption(f"💸 Filtered Debit: ₹{filtered_debit:,.2f}")
                    else:
                        st.info("No transactions match your filters.")
                
                with tab2:
                    st.markdown("#### Summary by File")
                    file_summary = df.groupby("Source File").agg(
                        Total_Credit=("Amount", lambda x: x[df.loc[x.index, "Type"] == "CR"].sum()),
                        Total_Debit=("Amount", lambda x: x[df.loc[x.index, "Type"] == "DR"].sum()),
                        Transactions=("Amount", "count")
                    )
                    file_summary["Net_Flow"] = file_summary["Total_Credit"] - file_summary["Total_Debit"]
                    
                    # Format for display
                    file_summary_display = file_summary.copy()
                    for col in ["Total_Credit", "Total_Debit", "Net_Flow"]:
                        file_summary_display[col] = file_summary_display[col].apply(lambda x: f"₹{x:,.2f}")
                    
                    st.dataframe(file_summary_display, use_container_width=True)
                    
                    # Visual chart
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        name='Credit',
                        x=file_summary.index,
                        y=file_summary['Total_Credit'],
                        marker_color='#4CAF50'
                    ))
                    fig.add_trace(go.Bar(
                        name='Debit',
                        x=file_summary.index,
                        y=file_summary['Total_Debit'],
                        marker_color='#f44336'
                    ))
                    fig.update_layout(
                        barmode='group',
                        title="Credit vs Debit by File",
                        xaxis_title="File",
                        yaxis_title="Amount (₹)",
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with tab3:
                    st.markdown("#### Monthly Trends")
                    df["Month"] = df["Date"].dt.to_period("M")
                    monthly_summary = df.groupby(["Month", "Type"])["Amount"].sum().unstack(fill_value=0)
                    monthly_summary["Net"] = monthly_summary.get("CR", 0) - monthly_summary.get("DR", 0)
                    
                    # Display table
                    monthly_display = monthly_summary.copy()
                    monthly_display.index = monthly_display.index.astype(str)
                    for col in monthly_display.columns:
                        monthly_display[col] = monthly_display[col].apply(lambda x: f"₹{x:,.2f}")
                    st.dataframe(monthly_display, use_container_width=True)
                    
                    # Line chart
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=[str(idx) for idx in monthly_summary.index],
                        y=monthly_summary.get("CR", [0]*len(monthly_summary)),
                        name='Credit',
                        line=dict(color='#4CAF50', width=3),
                        mode='lines+markers'
                    ))
                    fig.add_trace(go.Scatter(
                        x=[str(idx) for idx in monthly_summary.index],
                        y=monthly_summary.get("DR", [0]*len(monthly_summary)),
                        name='Debit',
                        line=dict(color='#f44336', width=3),
                        mode='lines+markers'
                    ))
                    fig.update_layout(
                        title="Monthly Credit & Debit Trends",
                        xaxis_title="Month",
                        yaxis_title="Amount (₹)",
                        height=400,
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with tab4:
                    st.markdown("#### Spending by Category")
                    
                    # Category breakdown
                    category_summary = df.groupby("Category").agg(
                        Total=("Amount", "sum"),
                        Count=("Amount", "count")
                    ).sort_values("Total", ascending=False)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Pie chart
                        fig = px.pie(
                            values=category_summary["Total"],
                            names=category_summary.index,
                            title="Spending Distribution by Category",
                            hole=0.4
                        )
                        fig.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        # Bar chart
                        fig = px.bar(
                            category_summary.reset_index(),
                            x="Category",
                            y="Total",
                            title="Total Amount by Category",
                            color="Total",
                            color_continuous_scale="Viridis"
                        )
                        fig.update_layout(xaxis_tickangle=-45, height=400)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Detailed category table
                    st.markdown("##### Category Details")
                    category_display = category_summary.copy()
                    category_display["Total"] = category_display["Total"].apply(lambda x: f"₹{x:,.2f}")
                    category_display["Avg_Per_Transaction"] = (
                        category_summary["Total"] / category_summary["Count"]
                    ).apply(lambda x: f"₹{x:,.2f}")
                    st.dataframe(category_display, use_container_width=True)
                
                with tab5:
                    st.markdown("#### Top 5 Largest Transactions")
                    top5 = df.nlargest(5, "Amount")
                    
                    for idx, row in top5.iterrows():
                        # Create a card-like appearance for each transaction
                        bg_color = "rgba(76, 175, 80, 0.1)" if row['Type'] == "CR" else "rgba(244, 67, 54, 0.1)"
                        border_color = "#4CAF50" if row['Type'] == "CR" else "#f44336"
                        
                        st.markdown(f"""
                        <div style='
                            background-color: {bg_color};
                            border-left: 4px solid {border_color};
                            border-radius: 8px;
                            padding: 16px;
                            margin-bottom: 12px;
                        '>
                            <div style='display: flex; justify-content: space-between; align-items: center;'>
                                <div style='flex: 1;'>
                                    <div style='font-size: 14px; color: #888; margin-bottom: 4px;'>
                                        {row['Date'].strftime('%d %B %Y') if not pd.isna(row['Date']) else ''}
                                    </div>
                                    <div style='font-size: 18px; font-weight: 600; margin-bottom: 8px;'>
                                        {"🟢" if row['Type'] == "CR" else "🔴"} ₹{row['Amount']:,.2f}
                                    </div>
                                    <div style='font-size: 12px; background: rgba(0,0,0,0.1); 
                                        display: inline-block; padding: 4px 8px; border-radius: 4px; margin-bottom: 8px;'>
                                        {row['Category']}
                                    </div>
                                    <div style='font-size: 14px; color: #666; margin-top: 8px;'>
                                        {row['Remarks']}
                                    </div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                st.markdown("---")
                
                # Download section
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.download_button(
                        label="⬇️ Download Complete Analysis (CSV)",
                        data=df.to_csv(index=False).encode("utf-8"),
                        file_name=f"bank_analysis_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
            else:
                st.error("❌ No valid transactions found. Please check your PDF format.")
    
    # Show helpful message when no files selected
    elif not selected_paths and "last_df" not in st.session_state:
        st.markdown("""
            <div style='text-align: center; padding: 60px 20px; background: linear-gradient(135deg, rgba(76, 175, 80, 0.1) 0%, rgba(33, 150, 243, 0.1) 100%); border-radius: 12px; margin-top: 30px;'>
                <div style='font-size: 48px; margin-bottom: 20px;'>📊</div>
                <h3 style='color: #4CAF50; margin-bottom: 10px;'>Ready to Analyze Your Finances?</h3>
                <p style='color: #666; font-size: 16px; max-width: 600px; margin: 0 auto;'>
                    Upload your bank statements above and click "Run Analysis" to get started with detailed insights into your spending patterns, income sources, and financial trends.
                </p>
                <div style='margin-top: 30px; display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;'>
                    <div style='background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); min-width: 150px;'>
                        <div style='font-size: 24px;'>💰</div>
                        <div style='font-size: 12px; color: #888; margin-top: 5px;'>Track Income</div>
                    </div>
                    <div style='background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); min-width: 150px;'>
                        <div style='font-size: 24px;'>📈</div>
                        <div style='font-size: 12px; color: #888; margin-top: 5px;'>View Trends</div>
                    </div>
                    <div style='background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); min-width: 150px;'>
                        <div style='font-size: 24px;'>🏷️</div>
                        <div style='font-size: 12px; color: #888; margin-top: 5px;'>Categorize Spending</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    # Show previous analysis if available but no new files selected
    elif "last_df" in st.session_state:
        st.info("💡 Your previous analysis is shown below. Select files from the sidebar and click 'Run Analysis' to update.") 
