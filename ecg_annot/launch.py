import streamlit as st
import sqlite3
from datetime import datetime
import uuid
import json
import pandas as pd
import numpy as np
import tempfile
import os
from ecg_annot.configs.annotation import QRS_GRAPH
from ecg_annot.data_utils.prepare_xml import load_ecg_signals_only, PTB_ORDER
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
if "ecg_data" not in st.session_state:
    st.session_state["ecg_data"] = None
if "selected_leads" not in st.session_state:
    st.session_state["selected_leads"] = [PTB_ORDER[1]]
if "file_uploaded" not in st.session_state:
    st.session_state["file_uploaded"] = False
if "current_filename" not in st.session_state:
    st.session_state["current_filename"] = None
if "completed_files" not in st.session_state:
    st.session_state["completed_files"] = []
if "submission_complete" not in st.session_state:
    st.session_state["submission_complete"] = False


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
    clean_answers = dict(answers)
    duration_answer = clean_answers.get("Duration")
    followups = [">120", "110-120", "<110"]
    if duration_answer in followups:
        for opt in followups:
            if opt != duration_answer and opt in clean_answers:
                del clean_answers[opt]
    else:
        for opt in followups:
            if opt in clean_answers:
                del clean_answers[opt]
    conn = get_connection()
    user_id = st.session_state["user_id"]
    cur = conn.execute("SELECT data FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row is None or row[0] is None:
        payload = {}
    else:
        payload = json.loads(row[0])
    for key, answer in clean_answers.items():
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


def reset_database():
    conn = get_connection()
    conn.execute("DELETE FROM users")
    conn.commit()
    get_connection.clear()


def reset_session_for_new_file():
    st.session_state["current_question_index"] = 0
    st.session_state["answers"] = {}
    st.session_state["ecg_data"] = None
    st.session_state["selected_leads"] = [PTB_ORDER[1]]
    st.session_state["file_uploaded"] = False
    st.session_state["current_filename"] = None
    st.session_state["submission_complete"] = False


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
    div[data-testid="stRadio"] > div {
        min-height: 120px;
    }
    .completed-files {
        position: fixed;
        right: 20px;
        top: 80px;
        background: #f0f2f6;
        padding: 10px;
        border-radius: 8px;
        max-width: 200px;
        font-size: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def back_to_portal():
    if st.button("Back to Portal"):
        st.session_state["role"] = None
        reset_session_for_new_file()
        st.session_state["completed_files"] = []
        st.rerun()


def render_completed_files_widget():
    if st.session_state["completed_files"]:
        files_html = "<br>".join([f"✓ {f}" for f in st.session_state["completed_files"]])
        st.markdown(
            f"""
            <div class="completed-files">
                <strong>Completed:</strong><br>
                {files_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_file_upload_page():
    back_to_portal()
    render_completed_files_widget()
    st.title("ECG Annotation")
    st.subheader("Upload ECG File")
    uploaded_file = st.file_uploader("Upload a file", accept_multiple_files=False)
    if uploaded_file is None:
        return
    filename = uploaded_file.name
    if filename and filename.endswith(".xml"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        try:
            st.session_state["ecg_data"] = load_ecg_signals_only(tmp_path)
            st.session_state["current_filename"] = filename
            st.session_state["file_uploaded"] = True
        finally:
            os.unlink(tmp_path)
        if st.button("Start Annotation", width="stretch"):
            st.rerun()


def render_questions_page():
    back_to_portal()
    render_completed_files_widget()
    st.title("ECG Annotation")
    if st.session_state["current_filename"]:
        st.caption(f"File: {st.session_state['current_filename']}")
    if st.session_state["ecg_data"] is not None:
        ecg_data = st.session_state["ecg_data"]
        cols = st.columns(6)
        selected_leads = []
        for i, lead in enumerate(PTB_ORDER):
            col = cols[i % len(cols)]
            key = f"lead_{lead}"
            if key not in st.session_state:
                st.session_state[key] = lead in st.session_state["selected_leads"]
            val = col.checkbox(lead, key=key)
            if val:
                selected_leads.append(lead)
        if not selected_leads:
            selected_leads = [PTB_ORDER[1]]
        st.session_state["selected_leads"] = selected_leads
        time_axis = np.arange(ecg_data.shape[1])
        if len(selected_leads) == 1:
            lead = selected_leads[0]
            idx = PTB_ORDER.index(lead)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=time_axis, y=ecg_data[idx], mode="lines", name=lead))
            fig.update_layout(xaxis_title="Time", yaxis_title="Amplitude")
        else:
            fig = make_subplots(
                rows=len(selected_leads),
                cols=1,
                shared_xaxes=False,
                vertical_spacing=0.02,
            )
            for i, lead in enumerate(selected_leads):
                idx = PTB_ORDER.index(lead)
                fig.add_trace(
                    go.Scatter(x=time_axis, y=ecg_data[idx], mode="lines", name=lead),
                    row=i + 1,
                    col=1,
                )
                fig.update_yaxes(title_text=lead, row=i + 1, col=1)
            fig.update_layout(
                xaxis_title="Time",
                height=200 * len(selected_leads),
                showlegend=False,
            )
        st.plotly_chart(fig, width="stretch")
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
            if st.button("Back", width="stretch"):
                st.session_state["current_question_index"] = max(0, len(order) - 1)
                duration_answer = st.session_state["answers"].get("Duration")
                if duration_answer in [">120", "110-120", "<110"]:
                    last_followup = duration_answer
                    if last_followup in st.session_state["answers"]:
                        del st.session_state["answers"][last_followup]
                st.rerun()
        with col_submit:
            if st.button("Submit", width="stretch"):
                save_all_responses(st.session_state["answers"], st.session_state["current_filename"])
                if st.session_state["current_filename"] not in st.session_state["completed_files"]:
                    st.session_state["completed_files"].append(st.session_state["current_filename"])
                st.session_state["submission_complete"] = True
                st.rerun()
        return
    question_data = QRS_GRAPH[question_key]
    question_text = question_data["question"]
    choices = question_data["choices"]
    st.markdown("### Question")
    st.write(question_text)
    if question_key in st.session_state["answers"]:
        prev_answer = st.session_state["answers"][question_key]
        if prev_answer in choices:
            selected = st.radio(
                "Your answer",
                choices,
                index=choices.index(prev_answer),
                key=f"answer_{question_key}",
            )
        else:
            selected = st.radio(
                "Your answer",
                choices,
                key=f"answer_{question_key}",
            )
    else:
        selected = st.radio(
            "Your answer",
            choices,
            key=f"answer_{question_key}",
        )
    if st.session_state["current_question_index"] > 0:
        col_back, col_next = st.columns(2)
        with col_back:
            if st.button("Back", width="stretch"):
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
            if st.button("Next", width="stretch"):
                st.session_state["answers"][question_key] = selected
                if question_key == "Duration":
                    for opt in [">120", "110-120", "<110"]:
                        if opt in st.session_state["answers"]:
                            del st.session_state["answers"][opt]
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
        if st.button("Next", width="stretch"):
            st.session_state["answers"][question_key] = selected
            if question_key == "Duration":
                for opt in [">120", "110-120", "<110"]:
                    if opt in st.session_state["answers"]:
                        del st.session_state["answers"][opt]
            if question_key in order:
                idx = order.index(question_key)
                if question_key == "Duration":
                    st.session_state["current_question_index"] = idx
                else:
                    st.session_state["current_question_index"] = idx + 1
            else:
                st.session_state["current_question_index"] = len(order)
            st.rerun()


def render_completion_page():
    back_to_portal()
    render_completed_files_widget()
    st.title("Submission Complete")
    st.success("Thank you for your submission.")
    st.write("Would you like to upload another file?")
    if st.button("Upload Another File", width="stretch"):
        reset_session_for_new_file()
        st.rerun()


def render_guest_page():
    if st.session_state["submission_complete"]:
        render_completion_page()
    elif not st.session_state["file_uploaded"]:
        render_file_upload_page()
    else:
        render_questions_page()


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
    if not df.empty:
        st.subheader("All user data")
        st.dataframe(df, width="stretch")
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            csv,
            "responses.csv",
            "text/csv",
        )
    else:
        st.info("No responses yet.")
    st.divider()
    if "reset_confirmed" not in st.session_state:
        st.session_state["reset_confirmed"] = False
    if st.session_state["reset_confirmed"]:
        st.warning("⚠️ Are you sure you want to delete ALL data? This cannot be undone.")
        col_confirm, col_cancel = st.columns(2)
        with col_confirm:
            if st.button("Confirm Reset", type="primary", width="stretch"):
                reset_database()
                st.session_state["reset_confirmed"] = False
                st.success("Database reset successfully.")
                st.rerun()
        with col_cancel:
            if st.button("Cancel", width="stretch"):
                st.session_state["reset_confirmed"] = False
                st.rerun()
    else:
        if st.button("Reset Database", type="secondary", width="stretch"):
            st.session_state["reset_confirmed"] = True
            st.rerun()
    if st.button("Back to Portal"):
        st.session_state["role"] = None
        st.session_state["reset_confirmed"] = False
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
