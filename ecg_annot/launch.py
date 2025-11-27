import streamlit as st
from datetime import datetime
import uuid
import json
import pandas as pd
import numpy as np
import tempfile
import os
from ecg_annot.configs.annotation import (
    ALL_QUESTIONS_GRAPH,
    QRS_QUESTION_ORDER,
    NOISE_ARTIFACTS_QUESTION_ORDER,
    ALL_QUESTION_ORDER,
)
from ecg_annot.data_utils.prepare_xml import load_ecg_signals_only, PTB_ORDER
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Minimal Q&A",
    page_icon="⬡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

DURATION_FOLLOWUPS = [">120", "110-120", "<110"]


def init_session_state():
    defaults = {
        "user_id": lambda: str(uuid.uuid4()),
        "role": None,
        "current_question_index": 0,
        "answers": dict,
        "ecg_data": None,
        "selected_leads": lambda: [PTB_ORDER[1]],
        "file_uploaded": False,
        "current_filename": None,
        "completed_files": list,
        "submission_complete": False,
        "reset_confirmed": False,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default() if callable(default) else default


init_session_state()


@st.cache_resource
def get_sheets_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)


def get_worksheet():
    return get_sheets_client().open_by_key(st.secrets["SHEET_ID"]).sheet1


def clean_duration_answers(answers):
    clean = dict(answers)
    duration = clean.get("Duration")
    keep = [duration] if duration in DURATION_FOLLOWUPS else []
    for opt in DURATION_FOLLOWUPS:
        if opt not in keep:
            clean.pop(opt, None)
    return clean


def save_all_responses(answers: dict, filename: str | None):
    clean_answers = clean_duration_answers(answers)
    user_id = st.session_state["user_id"]
    ws = get_worksheet()
    all_data = ws.get_all_records()
    existing_row = next((i + 2 for i, row in enumerate(all_data) if row.get("user_id") == user_id), None)
    current_data = json.loads(all_data[existing_row - 2].get("data", "{}")) if existing_row else {}
    file_data = {ALL_QUESTIONS_GRAPH[key]["question"]: answer for key, answer in clean_answers.items()}
    file_data["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
    current_data[filename] = file_data
    data_str = json.dumps(current_data)
    if existing_row:
        ws.update_cell(existing_row, 3, data_str)
    else:
        ws.append_row([user_id, datetime.utcnow().isoformat(timespec="seconds"), data_str])


def is_qrs_complete(answers):
    if answers.get("QRS") == "No (Asystole)":
        return True
    preexc = answers.get("Preexcitation")
    if preexc == "No" and "AP" in QRS_QUESTION_ORDER:
        skip_ap = True
    else:
        skip_ap = False
    if preexc == "Yes" and "AP" in answers:
        return True
    for key in QRS_QUESTION_ORDER:
        if skip_ap and key == "AP":
            continue
        if key not in answers:
            return False
        if key == "Duration" and answers[key] in DURATION_FOLLOWUPS and answers[key] not in answers:
            return False
    duration_answer = answers.get("Duration")
    if duration_answer in DURATION_FOLLOWUPS and duration_answer not in answers:
        return False
    return True


def get_next_question_key(current_index, answers):
    if not is_qrs_complete(answers):
        preexc = answers.get("Preexcitation")
        if preexc == "No" and "AP" in QRS_QUESTION_ORDER:
            skip_ap = True
        else:
            skip_ap = False
        for i in range(current_index, len(QRS_QUESTION_ORDER)):
            key = QRS_QUESTION_ORDER[i]
            if skip_ap and key == "AP":
                continue
            if key not in answers:
                return key
            if key == "Duration" and answers[key] in DURATION_FOLLOWUPS and answers[key] not in answers:
                return answers[key]
        duration_answer = answers.get("Duration")
        if duration_answer in DURATION_FOLLOWUPS and duration_answer not in answers:
            return duration_answer
    else:
        for key in NOISE_ARTIFACTS_QUESTION_ORDER:
            if key not in answers:
                return key
    return None


def has_more_questions(answers):
    return get_next_question_key(0, answers) is not None


def load_all_users():
    return pd.DataFrame(get_worksheet().get_all_records())


def reset_database():
    ws = get_worksheet()
    ws.clear()
    ws.append_row(["user_id", "created_at", "data"])
    get_sheets_client.clear()


def reset_session_for_new_file():
    st.session_state.update({
        "current_question_index": 0,
        "answers": {},
        "ecg_data": None,
        "selected_leads": [PTB_ORDER[1]],
        "file_uploaded": False,
        "current_filename": None,
        "submission_complete": False,
    })


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
        st.session_state.update({"role": None, "completed_files": []})
        reset_session_for_new_file()
        st.rerun()


def render_completed_files_widget():
    if st.session_state["completed_files"]:
        files_html = "<br>".join([f"✓ {f}" for f in st.session_state["completed_files"]])
        st.markdown(f'<div class="completed-files"><strong>Completed:</strong><br>{files_html}</div>', unsafe_allow_html=True)


def render_page_header(title, subtitle=None):
    back_to_portal()
    render_completed_files_widget()
    st.title(title)
    if subtitle:
        st.subheader(subtitle)
    if st.session_state.get("current_filename"):
        st.caption(f"File: {st.session_state['current_filename']}")


def render_button_pair(left_text, right_text, left_callback, right_callback, right_type="primary"):
    col1, col2 = st.columns(2)
    with col1:
        if st.button(left_text, width="stretch"):
            left_callback()
    with col2:
        if st.button(right_text, type=right_type, width="stretch"):
            right_callback()


def render_lead_selection(ecg_data):
    cols = st.columns(6)
    selected_leads = []
    for i, lead in enumerate(PTB_ORDER):
        key = f"lead_{lead}"
        st.session_state.setdefault(key, lead in st.session_state["selected_leads"])
        if cols[i % 6].checkbox(lead, key=key):
            selected_leads.append(lead)
    return selected_leads or [PTB_ORDER[1]]


def render_ecg_plot(ecg_data, selected_leads):
    time_axis = np.arange(ecg_data.shape[1])
    if len(selected_leads) == 1:
        idx = PTB_ORDER.index(selected_leads[0])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=time_axis, y=ecg_data[idx], mode="lines", name=selected_leads[0]))
        fig.update_layout(xaxis_title="Time", yaxis_title="Amplitude")
    else:
        fig = make_subplots(rows=len(selected_leads), cols=1, shared_xaxes=False, vertical_spacing=0.02)
        for i, lead in enumerate(selected_leads):
            idx = PTB_ORDER.index(lead)
            fig.add_trace(go.Scatter(x=time_axis, y=ecg_data[idx], mode="lines", name=lead), row=i + 1, col=1)
            fig.update_yaxes(title_text=lead, row=i + 1, col=1)
            if i < len(selected_leads) - 1:
                fig.update_xaxes(showticklabels=False, row=i + 1, col=1)
        fig.update_xaxes(title_text="Time", row=len(selected_leads), col=1)
        fig.update_layout(height=200 * len(selected_leads), showlegend=False)
    st.plotly_chart(fig, width="stretch")


def render_file_upload_page():
    render_page_header("ECG Annotation", "Upload ECG File")
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


def render_review_page():
    st.subheader("Review your answers")
    answers = st.session_state["answers"]
    for key in ALL_QUESTION_ORDER:
        if key in answers:
            st.markdown(f"**{ALL_QUESTIONS_GRAPH[key]['question']}**")
            st.write(answers[key])
    duration_answer = answers.get("Duration")
    if duration_answer in DURATION_FOLLOWUPS and duration_answer in answers:
        st.markdown(f"**{ALL_QUESTIONS_GRAPH[duration_answer]['question']}**")
        st.write(answers[duration_answer])

    def go_back():
        for followup in DURATION_FOLLOWUPS:
            if followup in answers:
                answers.pop(followup, None)
                st.session_state["current_question_index"] = len(ALL_QUESTION_ORDER)
                st.rerun()
                return
        last_answered_index = -1
        for i in range(len(ALL_QUESTION_ORDER) - 1, -1, -1):
            key = ALL_QUESTION_ORDER[i]
            if key in answers:
                last_answered_index = i
                break
        if last_answered_index >= 0:
            last_key = ALL_QUESTION_ORDER[last_answered_index]
            answers.pop(last_key, None)
            st.session_state["current_question_index"] = last_answered_index
        else:
            st.session_state["current_question_index"] = 0
        st.rerun()

    def submit():
        save_all_responses(answers, st.session_state["current_filename"])
        filename = st.session_state["current_filename"]
        if filename not in st.session_state["completed_files"]:
            st.session_state["completed_files"].append(filename)
        st.session_state["submission_complete"] = True
        st.rerun()

    render_button_pair("Back", "Submit", go_back, submit)


def handle_back_navigation(question_key):
    answers = st.session_state["answers"]
    if question_key in DURATION_FOLLOWUPS:
        answers.pop("Duration", None)
        st.session_state["current_question_index"] = QRS_QUESTION_ORDER.index("Duration")
    elif question_key in NOISE_ARTIFACTS_QUESTION_ORDER:
        answers.pop(question_key, None)
        last_qrs_index = -1
        for i in range(len(QRS_QUESTION_ORDER) - 1, -1, -1):
            key = QRS_QUESTION_ORDER[i]
            if key in answers:
                last_qrs_index = i
                break
        if last_qrs_index >= 0:
            st.session_state["current_question_index"] = last_qrs_index
        else:
            st.session_state["current_question_index"] = 0
    else:
        new_index = st.session_state["current_question_index"] - 1
        if new_index >= 0 and new_index < len(QRS_QUESTION_ORDER):
            answers.pop(QRS_QUESTION_ORDER[new_index], None)
            st.session_state["current_question_index"] = new_index
    st.rerun()


def handle_next_navigation(question_key, selected):
    answers = st.session_state["answers"]
    answers[question_key] = selected
    if question_key == "Duration":
        for opt in DURATION_FOLLOWUPS:
            answers.pop(opt, None)
    if question_key in QRS_QUESTION_ORDER:
        idx = QRS_QUESTION_ORDER.index(question_key)
        st.session_state["current_question_index"] = idx if question_key == "Duration" else idx + 1
    elif question_key in NOISE_ARTIFACTS_QUESTION_ORDER:
        idx = NOISE_ARTIFACTS_QUESTION_ORDER.index(question_key)
        if idx + 1 < len(NOISE_ARTIFACTS_QUESTION_ORDER):
            st.session_state["current_question_index"] = len(QRS_QUESTION_ORDER) + idx + 1
        else:
            st.session_state["current_question_index"] = len(ALL_QUESTION_ORDER)
    else:
        st.session_state["current_question_index"] = len(ALL_QUESTION_ORDER)
    st.rerun()


def handle_submit_from_question(question_key, selected):
    answers = st.session_state["answers"]
    answers[question_key] = selected
    save_all_responses(answers, st.session_state["current_filename"])
    filename = st.session_state["current_filename"]
    if filename not in st.session_state["completed_files"]:
        st.session_state["completed_files"].append(filename)
    st.session_state["submission_complete"] = True
    st.rerun()


def render_questions_page():
    render_page_header("ECG Annotation")
    ecg_data = st.session_state["ecg_data"]
    if ecg_data is not None:
        selected_leads = render_lead_selection(ecg_data)
        st.session_state["selected_leads"] = selected_leads
        render_ecg_plot(ecg_data, selected_leads)
    question_key = get_next_question_key(st.session_state["current_question_index"], st.session_state["answers"])
    if question_key is None:
        render_review_page()
        return
    question_data = ALL_QUESTIONS_GRAPH[question_key]
    st.markdown("### Question")
    st.write(question_data["question"])
    prev_answer = st.session_state["answers"].get(question_key)
    default_index = question_data["choices"].index(prev_answer) if prev_answer in question_data["choices"] else 0
    selected = st.radio("Your answer", question_data["choices"], index=default_index, key=f"answer_{question_key}")
    temp_answers = {**st.session_state["answers"], question_key: selected}
    is_last_question = not has_more_questions(temp_answers)
    if st.session_state["current_question_index"] > 0:
        if is_last_question:
            render_button_pair(
                "Back", "Submit", lambda: handle_back_navigation(question_key), lambda: handle_submit_from_question(question_key, selected)
            )
        else:
            render_button_pair("Back", "Next", lambda: handle_back_navigation(question_key), lambda: handle_next_navigation(question_key, selected))
    else:
        if is_last_question:
            if st.button("Submit", width="stretch"):
                handle_submit_from_question(question_key, selected)
        else:
            if st.button("Next", width="stretch"):
                handle_next_navigation(question_key, selected)


def render_completion_page():
    render_page_header("Submission Complete")
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
            if password == st.secrets["ADMIN_PASSWORD"]:
                st.session_state["role"] = "admin"
                st.rerun()
            else:
                st.error("Incorrect password.")
        except Exception:
            st.error("ADMIN_PASSWORD not set in secrets.")
    if st.button("Back to Portal"):
        st.session_state["role"] = None
        st.rerun()


def render_reset_button():
    if st.session_state.get("reset_confirmed"):
        st.warning("⚠️ Are you sure you want to delete ALL data? This cannot be undone.")

        def cancel():
            st.session_state["reset_confirmed"] = False
            st.rerun()

        def confirm():
            reset_database()
            st.session_state["reset_confirmed"] = False
            st.success("Database reset successfully.")
            st.rerun()

        render_button_pair("Cancel", "Confirm Reset", cancel, confirm)
    else:
        if st.button("Reset Database", type="secondary", width="stretch"):
            st.session_state["reset_confirmed"] = True
            st.rerun()


def render_admin_page():
    st.title("Admin Panel")
    df = load_all_users()
    if not df.empty:
        st.subheader("All user data")
        st.dataframe(df, width="stretch")
        st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), "responses.csv", "text/csv")
    else:
        st.info("No responses yet.")
    st.divider()
    render_reset_button()
    if st.button("Back to Portal"):
        st.session_state.update({"role": None, "reset_confirmed": False})
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


ROUTERS = {
    None: render_landing,
    "guest": render_guest_page,
    "admin_login": render_admin_login,
    "admin": render_admin_page,
}
ROUTERS[st.session_state["role"]]()
