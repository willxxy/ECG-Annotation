import streamlit as st
import sqlite3
from datetime import datetime
import uuid

st.set_page_config(
    page_title="Minimal Q&A",
    page_icon="⬡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

QUESTION = "In one sentence, describe what you see in this ECG."


@st.cache_resource
def get_connection():
    conn = sqlite3.connect("responses.db", check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS responses (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            question TEXT,
            answer TEXT,
            filename TEXT
        )
        """
    )
    conn.commit()
    return conn


def save_response(question: str, answer: str, filename: str | None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO responses (id, created_at, question, answer, filename) VALUES (?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            datetime.utcnow().isoformat(timespec="seconds"),
            question,
            answer,
            filename,
        ),
    )
    conn.commit()


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

with st.expander("View collected responses (local DB)"):
    conn = get_connection()
    rows = conn.execute("SELECT created_at, filename, answer FROM responses ORDER BY created_at DESC").fetchall()
    if rows:
        import pandas as pd

        df = pd.DataFrame(rows, columns=["created_at", "filename", "answer"])
        st.dataframe(df, width=True)
    else:
        st.caption("No responses yet.")
