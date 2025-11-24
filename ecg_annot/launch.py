import streamlit as st
import sqlite3
from datetime import datetime
import uuid
import json
import pandas as pd
from ecg_annot.configs.annotation import QRS_GRAPH

st.set_page_config(
    page_title="Minimal Q&A",
    page_icon="⬡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

if "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())
if "role" not in st.session_state:
    st.session_state["role"] = None
if "current_question_index" not in st.session_state:
    st.session_state["current_question_index"] = 0
if "answers" not in st.session_state:
    st.session_state["answers"] = {}


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


def save_all_responses(answers: dict, filename: str | None):
    conn = get_connection()
    user_id = st.session_state["user_id"]
    cur = conn.execute("SELECT data FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row is None or row[0] is None:
        payload = {}
    else:
        payload = json.loads(row[0])
    for key, answer in answers.items():
        question_text = QRS_GRAPH[key]["question"]
        payload[question_text] = {
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


def get_question_order():
    base_order = ["QRS", "Pacing", "Axis", "Lead reversal", "Rate", "Amplitude", "Preexcitation", "AP", "Duration"]
    return base_order


def get_next_question_key(current_index, answers):
    order = get_question_order()
    for i in range(current_index, len(order)):
        key = order[i]
        if key not in answers:
            return key
        if key == "Duration":
            duration_answer = answers[key]
            if duration_answer == ">120" and ">120" not in answers:
                return ">120"
            elif duration_answer == "110-120" and "110-120" not in answers:
                return "110-120"
            elif duration_answer == "<110" and "<110" not in answers:
                return "<110"
    duration_answer = answers.get("Duration")
    if duration_answer == ">120" and ">120" not in answers:
        return ">120"
    elif duration_answer == "110-120" and "110-120" not in answers:
        return "110-120"
    elif duration_answer == "<110" and "<110" not in answers:
        return "<110"
    return None


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
        border-radius: 0.5rem;
    }
    .button-row {
        display: flex;
        gap: 0.5rem;
        margin-top: 1.5rem;
    }
    .button-row > div {
        flex: 1;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_guest_page():
    st.title("ECG Annotation")
    uploaded_file = st.file_uploader("Upload a file", accept_multiple_files=False)
    filename = uploaded_file.name if uploaded_file is not None else None
    order = get_question_order()
    question_key = get_next_question_key(st.session_state["current_question_index"], st.session_state["answers"])
    if question_key is None:
        st.subheader("Review your answers")
        for key in order:
            if key in st.session_state["answers"]:
                st.markdown(f"**{QRS_GRAPH[key]['question']}**")
                st.write(st.session_state["answers"][key])
        duration_answer = st.session_state["answers"].get("Duration")
        if duration_answer == ">120" and ">120" in st.session_state["answers"]:
            st.markdown(f"**{QRS_GRAPH['>120']['question']}**")
            st.write(st.session_state["answers"][">120"])
        elif duration_answer == "110-120" and "110-120" in st.session_state["answers"]:
            st.markdown(f"**{QRS_GRAPH['110-120']['question']}**")
            st.write(st.session_state["answers"]["110-120"])
        elif duration_answer == "<110" and "<110" in st.session_state["answers"]:
            st.markdown(f"**{QRS_GRAPH['<110']['question']}**")
            st.write(st.session_state["answers"]["<110"])
        col_back, col_submit = st.columns(2)
        with col_back:
            if st.button("Back", use_container_width=True):
                st.session_state["current_question_index"] = max(0, len(order) - 1)
                duration_answer = st.session_state["answers"].get("Duration")
                if duration_answer in [">120", "110-120", "<110"]:
                    last_followup = duration_answer
                    if last_followup in st.session_state["answers"]:
                        del st.session_state["answers"][last_followup]
                st.rerun()
        with col_submit:
            if st.button("Submit", use_container_width=True):
                save_all_responses(st.session_state["answers"], filename)
                st.success("Thank you for your submission.")
                if st.button("Back to Portal"):
                    st.session_state["role"] = None
                    st.session_state["current_question_index"] = 0
                    st.session_state["answers"] = {}
                    st.rerun()
        return
    question_data = QRS_GRAPH[question_key]
    question_text = question_data["question"]
    choices = question_data["choices"]
    st.markdown("### Question")
    st.write(question_text)
    if question_key in st.session_state["answers"]:
        prev_answer = st.session_state["answers"][question_key]
        default_index = choices.index(prev_answer) if prev_answer in choices else None
    else:
        default_index = None
    selected = st.radio(
        "Your answer",
        choices,
        index=default_index,
        key=f"answer_{question_key}",
    )
    if st.session_state["current_question_index"] > 0:
        col_back, col_next = st.columns(2)
        with col_back:
            if st.button("Back", use_container_width=True):
                if question_key in [">120", "110-120", "<110"]:
                    if "Duration" in st.session_state["answers"]:
                        del st.session_state["answers"]["Duration"]
                    st.session_state["current_question_index"] = order.index("Duration")
                else:
                    new_index = st.session_state["current_question_index"] - 1
                    prev_question_key = order[new_index]
                    if prev_question_key in st.session_state["answers"]:
                        del st.session_state["answers"][prev_question_key]
                    st.session_state["current_question_index"] = new_index
                st.rerun()
        with col_next:
            if st.button("Next", use_container_width=True):
                if selected is None:
                    st.error("Please select an option before continuing.")
                    return
                st.session_state["answers"][question_key] = selected
                if question_key in order:
                    idx = order.index(question_key)
                    if question_key == "Duration":
                        st.session_state["current_question_index"] = idx
                    else:
                        st.session_state["current_question_index"] = idx + 1
                else:
                    st.session_state["current_question_index"] = len(order)
                st.rerun()
    else:
        if st.button("Next", use_container_width=True):
            if selected is None:
                st.error("Please select an option before continuing.")
                return
            st.session_state["answers"][question_key] = selected
            if question_key in order:
                idx = order.index(question_key)
                if question_key == "Duration":
                    st.session_state["current_question_index"] = idx
                else:
                    st.session_state["current_question_index"] = idx + 1
            else:
                st.session_state["current_question_index"] = len(order)
            st.rerun()
    if st.button("Back to Portal"):
        st.session_state["role"] = None
        st.session_state["current_question_index"] = 0
        st.session_state["answers"] = {}
        st.rerun()


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
            st.rerun()
        else:
            st.error("Incorrect password.")
    if st.button("Back to Portal"):
        st.session_state["role"] = None
        st.rerun()


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
    if st.button("Back to Portal"):
        st.session_state["role"] = None
        st.rerun()


def render_landing():
    st.title("Portal")
    st.write("Choose mode:")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Guest"):
            st.session_state["role"] = "guest"
            st.rerun()
    with col2:
        if st.button("Admin"):
            st.session_state["role"] = "admin_login"
            st.rerun()


role = st.session_state["role"]
if role is None:
    render_landing()
elif role == "guest":
    render_guest_page()
elif role == "admin_login":
    render_admin_login()
elif role == "admin":
    render_admin_page()
