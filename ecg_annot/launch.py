import streamlit as st
import sqlite3
from datetime import datetime
import uuid
import json
import pandas as pd

st.set_page_config(
    page_title="Minimal Q&A",
    page_icon="⬡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

QUESTION = "In one sentence, describe what you see in this ECG."

if "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())

if "role" not in st.session_state:
    st.session_state["role"] = None


@st.cache_resource
def get_connection():
    conn = sqlite3.connect("responses.db", check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            created_at TEXT,
            data TEXT
        )
        """
    )
    conn.commit()
    return conn


def save_response(question: str, answer: str, filename: str | None):
    conn = get_connection()
    user_id = st.session_state["user_id"]

    cur = conn.execute("SELECT data FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row is None or row[0] is None:
        payload = {}
    else:
        payload = json.loads(row[0])

    payload[question] = {
        "answer": answer,
        "filename": filename,
        "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
    }

    data_str = json.dumps(payload)

    if row is None:
        conn.execute(
            "INSERT INTO users (user_id, created_at, data) VALUES (?, ?, ?)",
            (
                user_id,
                datetime.utcnow().isoformat(timespec="seconds"),
                data_str,
            ),
        )
    else:
        conn.execute(
            "UPDATE users SET data = ? WHERE user_id = ?",
            (data_str, user_id),
        )

    conn.commit()


def load_all_users():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM users", conn)
    return df


st.markdown(
    """
    <style>
    .main {
        max-width: 600px;
        margin: 0 auto;
        padding-top: 4rem;
        padding-bottom: 4rem;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    }
    .stButton>button {
        width: 100%;
        border-radius: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_guest_page():
    st.title("Minimal ECG Q&A")

    uploaded_file = st.file_uploader("Upload a file", accept_multiple_files=False)

    st.markdown("### Question")
    st.write(QUESTION)

    answer = st.text_area("Your answer", placeholder="Type your answer here...", height=120)

    if st.button("Submit"):
        if not answer.strip():
            st.error("Please enter an answer before submitting.")
        else:
            filename = uploaded_file.name if uploaded_file is not None else None
            save_response(QUESTION, answer.strip(), filename)
            st.success("Submitted. Thank you!")


def render_admin_login():
    st.title("Admin Login")

    password = st.text_input("Enter admin password", type="password")
    if st.button("Login"):
        try:
            admin_pw = st.secrets["ADMIN_PASSWORD"]
        except Exception:
            st.error("ADMIN_PASSWORD not set in secrets.")
            return

        if password == admin_pw:
            st.session_state["role"] = "admin"
            st.experimental_rerun()
        else:
            st.error("Incorrect password.")


def render_admin_page():
    st.title("Admin Panel")

    df = load_all_users()

    if df.empty:
        st.info("No responses yet.")
        return

    st.subheader("All user data")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV",
        csv,
        "responses.csv",
        "text/csv",
    )


def render_landing():
    st.title("ECG Annotation Portal")
    st.write("Choose mode:")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Guest"):
            st.session_state["role"] = "guest"
            st.experimental_rerun()
    with col2:
        if st.button("Admin"):
            st.session_state["role"] = "admin_login"
            st.experimental_rerun()


role = st.session_state["role"]

if role is None:
    render_landing()
elif role == "guest":
    render_guest_page()
elif role == "admin_login":
    render_admin_login()
elif role == "admin":
    render_admin_page()
