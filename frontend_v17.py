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

# ──────────────────────────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Bank Statement Analyzer (v20 + Category Explorer)", layout="wide")
st.title("📄 Bank Statement Analyzer — v20 (Category Explorer Added)")

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
        return False, "⚠️ Account already exists!"
    cur.execute("INSERT INTO users (account_number, password) VALUES (?, ?)", (account_number, hash_pw(password)))
    conn.commit()
    conn.close()
    return True, "✅ Registration successful!"

def login_user_db(account_number: str, password: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE account_number=?", (account_number,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False, "❌ User not found!"
    if row[0] != hash_pw(password):
        return False, "❌ Incorrect password!"
    return True, "✅ Login successful!"

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
# PDF parsing (HDFC fix)
# ──────────────────────────────────────────────────────────────────────────────
TX_PATTERN = r"^(\d{2}/\d{2}/\d{2})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"

def parse_pdf_file(filepath: str, account_password: str):
    text = ""
    try:
        with pdfplumber.open(filepath, password=account_password) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])
    except Exception:
        try:
            with pdfplumber.open(filepath) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        except Exception as e:
            st.error(f"❌ Failed to open PDF: {os.path.basename(filepath)} — {e}")
            return []

    if not text.strip():
        st.warning(f"⚠️ Could not unlock or extract text from {os.path.basename(filepath)}")

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    data = []

    for line in lines:
        m = re.match(TX_PATTERN, line)
        if m:
            date, remarks, amt_str, bal_str = m.groups()
            try:
                amt_val = float(amt_str.replace(",", ""))
                bal_val = float(bal_str.replace(",", ""))

                tx_type = "DR"
                if any(kw in remarks.upper() for kw in ["NEFT CR", "IMPS", "UPI", "CREDIT", "REFUND", "INTEREST"]):
                    tx_type = "CR"

                data.append({
                    "Date": pd.to_datetime(date, format="%d/%m/%y", errors="coerce"),
                    "Amount": amt_val,
                    "Type": tx_type,
                    "Balance": bal_val,
                    "Remarks": remarks.strip(),
                    "Source File": os.path.basename(filepath)
                })
            except Exception:
                pass
    return data

def parse_many_pdfs(filepaths, account_password: str):
    all_rows = []
    for p in filepaths:
        rows = parse_pdf_file(p, account_password)
        if rows:
            all_rows.extend(rows)
    return all_rows

# ──────────────────────────────────────────────────────────────────────────────
# Category detection (Improved)
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_CATEGORIES = [
    "Restaurant", "Hospital", "Taxi", "Misc", "Grocery",
    "Credit card payment", "Subscription", "Sutherland",
    "Rent", "Electricity", "Cashback", "Travel"
]

DEFAULT_CATEGORY_KEYWORDS = {
    "Restaurant": ["restaurant", "resto", "restuarant", "dine", "dining", "cafe", "coffee", "bar", "zomato", "swiggy", "dominos", "pizza", "mcdonald", "burger", "kfc", "food", "eatery"],
    "Hospital": ["hospital", "hostpital", "clinic", "medical", "care", "apollo", "fortis", "manipal", "health"],
    "Taxi": ["uber", "ola", "cab", "taxi", "ride", "auto", "ola cabs", "uber auto", "olaauto", "transport"],
    "Grocery": ["grocery", "grosery", "supermarket", "bigbasket", "dmart", "reliance fresh", "spencer", "store", "mart", "super", "vegetables", "provision"],
    "Credit card payment": ["credit card", "card payment", "visa", "mastercard", "amex", "creditcard", "cardpayment", "credit", "billdesk"],
    "Subscription": ["subscription", "subscrption", "netflix", "spotify", "prime", "hotstar", "disney", "youtube premium", "zee5", "sony liv"],
    "Sutherland": ["sutherland"],
    "Rent": ["rent", "rental", "house rent", "flat rent", "pg", "lease"],
    "Electricity": ["electricity", "power", "electric bill", "tneb", "mahavitaran", "bill payment", "bills", "current"],
    "Cashback": ["cashback", "reward", "rewards", "referral", "cash back"],
    "Travel": ["flight", "air", "indigo", "spicejet", "goair", "air india", "train", "irctc", "hotel", "booking", "travel", "trip", "journey"],
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
auth_choice = st.sidebar.radio("Authentication", ["Login", "Register"])

if not st.session_state.authenticated:
    if auth_choice == "Register":
        st.subheader("📝 Register")
        reg_user = st.text_input("Choose Username (Account Number)")
        reg_pass = st.text_input("Choose Password", type="password")
        if st.button("Register"):
            if not reg_user or not reg_pass:
                st.warning("Please enter both account number and password.")
            else:
                ok, msg = register_user_db(reg_user.strip(), reg_pass.strip())
                st.success(msg) if ok else st.error(msg)

    elif auth_choice == "Login":
        st.subheader("🔑 Login")
        log_user = st.text_input("Username (Account Number)")
        log_pass = st.text_input("Password", type="password")
        if st.button("Login"):
            if not log_user or not log_pass:
                st.warning("Please enter both username and password.")
            else:
                ok, msg = login_user_db(log_user.strip(), log_pass.strip())
                if ok:
                    st.session_state.authenticated = True
                    st.session_state.username = log_user.strip()
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

# ──────────────────────────────────────────────────────────────────────────────
# Main App
# ──────────────────────────────────────────────────────────────────────────────
if st.session_state.authenticated:
    user = st.session_state.username
    st.success(f"Welcome {user} 🎉")

    st.subheader("📤 Upload new bank statement PDFs")
    uploaded_files = st.file_uploader(
        "Upload one or more PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key="uploader_key"
    )

    new_uploaded_paths = []
    if uploaded_files:
        if "saved_file_names" not in st.session_state:
            st.session_state.saved_file_names = set()
        unsaved_files = [f for f in uploaded_files if f.name not in st.session_state.saved_file_names]
        if unsaved_files:
            new_uploaded_paths = save_uploaded_files(user, unsaved_files)
            for f in unsaved_files:
                st.session_state.saved_file_names.add(f.name)
            st.success(f"✅ Saved {len(new_uploaded_paths)} new file(s) to your library.")

    # Sidebar File Manager
    st.sidebar.subheader("📂 File Manager")
    saved_items = get_saved_pdfs(user)
    selected_paths = []
    if saved_items:
        for i in saved_items:
            col1, col2 = st.sidebar.columns([4, 1])
            with col1:
                if st.checkbox(f"{i['filename']} ({i['uploaded_at'].split('T')[0]})", key=f"chk_{i['id']}"):
                    selected_paths.append(i["filepath"])
            with col2:
                if st.button("🗑️", key=f"del_{i['id']}"):
                    delete_pdf(i['id'])
                    st.sidebar.success(f"Deleted {i['filename']}")
                    st.rerun()
    else:
        st.sidebar.info("No PDFs saved yet. Upload some above.")

    if not selected_paths and new_uploaded_paths:
        selected_paths = new_uploaded_paths

    st.markdown("---")
    st.subheader("🔍 Analyze")
    run_btn = st.button("▶️ Run Analysis")

    if run_btn:
        if not selected_paths:
            st.warning("Please select saved PDFs or upload some to analyze.")
        else:
            with st.spinner("Parsing statements..."):
                rows = parse_many_pdfs(selected_paths, account_password=user)
            if rows:
                df = pd.DataFrame(rows)
                df["Category"] = df["Remarks"].apply(lambda r: detect_category(r, st.session_state.categories))
                st.session_state.last_df = df

                tab1, tab2, tab3, tab4 = st.tabs(["📊 Transactions", "📂 File Summary", "📆 Monthly Trends", "🏆 Top 5"])
                with tab1:
                    st.dataframe(df, use_container_width=True)
                    total_credit = df[df["Type"] == "CR"]["Amount"].sum()
                    total_debit = df[df["Type"] == "DR"]["Amount"].sum()
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("🟢 Total Credit", f"₹ {total_credit:,.2f}")
                    with col2:
                        st.metric("🔴 Total Debit", f"₹ {total_debit:,.2f}")
                with tab2:
                    file_summary = df.groupby("Source File").agg(
                        Total_Credit=("Amount", lambda x: x[df.loc[x.index, "Type"] == "CR"].sum()),
                        Total_Debit=("Amount", lambda x: x[df.loc[x.index, "Type"] == "DR"].sum()),
                        Transactions=("Amount", "count")
                    )
                    st.dataframe(file_summary, use_container_width=True)
                with tab3:
                    df["Month"] = df["Date"].dt.to_period("M")
                    monthly_summary = df.groupby(["Month", "Type"])["Amount"].sum().unstack(fill_value=0)
                    monthly_summary["Net"] = monthly_summary.get("CR", 0) - monthly_summary.get("DR", 0)
                    st.dataframe(monthly_summary, use_container_width=True)
                    # (charts removed)
                with tab4:
                    top5 = df.nlargest(5, "Amount")
                    st.table(top5[["Date", "Amount", "Type", "Remarks", "Category"]])
                st.download_button(
                    label="⬇️ Download Combined Data as CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name="combined_transactions.csv",
                    mime="text/csv"
                )
            else:
                st.warning("⚠️ No valid transactions matched the expected format.")

    # ──────────────────────────────────────────────────────────────────────────────
    # Sidebar Category Explorer + Manager
    # (➡️ NOW appears only after analysis has run)
    # ──────────────────────────────────────────────────────────────────────────────
    if "last_df" in st.session_state:
        st.sidebar.subheader("📂 Category Explorer")
        df = st.session_state.last_df

        for cat in st.session_state.categories:
            cat_df = df[df["Category"] == cat]
            if not cat_df.empty:
                with st.sidebar.expander(f"{cat} ({len(cat_df)})", expanded=False):
                    st.dataframe(cat_df[["Date", "Amount", "Type", "Remarks"]], use_container_width=True, height=200)

        # 🔹 Category Manager (new section)
        st.sidebar.markdown("---")
        st.sidebar.subheader("➕ Add Category / Keyword")
        new_cat = st.sidebar.text_input("New Category")
        new_kw = st.sidebar.text_input("Keyword for that Category")
        if st.sidebar.button("Add"):
            if new_cat and new_kw:
                if new_cat not in st.session_state.categories:
                    st.session_state.categories.append(new_cat)
                DEFAULT_CATEGORY_KEYWORDS.setdefault(new_cat, []).append(new_kw.lower())
                st.sidebar.success(f"Added keyword '{new_kw}' to category '{new_cat}'")
            else:
                st.sidebar.warning("Please enter both category and keyword.")

    st.markdown("---")
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.rerun()
