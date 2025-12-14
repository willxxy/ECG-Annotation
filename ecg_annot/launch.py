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
    T_QUESTION_ORDER,
    ALL_QUESTION_ORDER,
    NOISE_LEAD_QUESTIONS,
    NOISE_TO_LEAD_QUESTION,
)
from ecg_annot.data_utils.prepare_xml import load_ecg_signals_only as load_ecg_xml, PTB_ORDER
from ecg_annot.data_utils.prepare_np import load_ecg_signals_only as load_ecg_np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import gspread
from google.oauth2.service_account import Credentials
import base64
from streamlit_agraph import agraph, Node, Edge, Config

st.set_page_config(
    page_title="ECG Annotation",
    page_icon="⬡",
    layout="wide",
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
        "selected_leads": lambda: PTB_ORDER[:],
        "file_uploaded": False,
        "current_filename": None,
        "completed_files": list,
        "submission_complete": False,
        "reset_confirmed": False,
        "file_type": None,
        "visualization_data": None,
        "show_graph": True,
        "navigation_history": list,
        "show_review": False,
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


def find_last_answered(question_list, answers):
    for i in range(len(question_list) - 1, -1, -1):
        if question_list[i] in answers:
            return i
    return -1


def get_question_index(key):
    if key in NOISE_ARTIFACTS_QUESTION_ORDER:
        return NOISE_ARTIFACTS_QUESTION_ORDER.index(key)
    if key in QRS_QUESTION_ORDER:
        return len(NOISE_ARTIFACTS_QUESTION_ORDER) + QRS_QUESTION_ORDER.index(key)
    if key in T_QUESTION_ORDER:
        return len(NOISE_ARTIFACTS_QUESTION_ORDER) + len(QRS_QUESTION_ORDER) + T_QUESTION_ORDER.index(key)
    return len(ALL_QUESTION_ORDER)


def should_skip_ap(answers):
    return answers.get("Preexcitation") == "No"


def is_qrs_complete(answers):
    if answers.get("QRS") == "No (Asystole)":
        return True
    if answers.get("Preexcitation") == "Yes" and "AP" in answers:
        return True
    skip_ap = should_skip_ap(answers)
    for key in QRS_QUESTION_ORDER:
        if skip_ap and key == "AP":
            continue
        if key not in answers:
            return False
    duration_answer = answers.get("Duration")
    return not (duration_answer in DURATION_FOLLOWUPS and duration_answer not in answers)


def get_next_question_key(current_index, answers):
    if "Noise artifacts" not in answers:
        return "Noise artifacts"
    noise_answers = answers.get("Noise artifacts", [])
    if noise_answers != ["None"]:
        for noise_type, lead_key in NOISE_TO_LEAD_QUESTION.items():
            if noise_type in noise_answers and lead_key not in answers:
                return lead_key
    if not is_qrs_complete(answers):
        skip_ap = should_skip_ap(answers)
        for key in QRS_QUESTION_ORDER:
            if skip_ap and key == "AP":
                continue
            if key not in answers:
                return key
        duration_answer = answers.get("Duration")
        if duration_answer in DURATION_FOLLOWUPS and duration_answer not in answers:
            return duration_answer
    for key in T_QUESTION_ORDER:
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


def reset_session_for_new_file():
    st.session_state.update({
        "current_question_index": 0,
        "answers": {},
        "ecg_data": None,
        "selected_leads": PTB_ORDER[:],
        "file_uploaded": False,
        "current_filename": None,
        "submission_complete": False,
        "file_type": None,
        "visualization_data": None,
        "navigation_history": [],
        "show_review": False,
    })


st.markdown(
    """
    <style>
    .main {
        padding-top: 1rem;
        padding-bottom: 2rem;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    }
    .stButton>button {
        border-radius: 0.5rem;
        font-size: 1.05rem;
        padding: 0.6rem 1.2rem;
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
        min-height: 130px;
    }
    div[data-testid="stRadio"] label {
        font-size: 1.05rem;
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
        z-index: 999;
    }
    .question-panel {
        min-height: 400px;
        max-height: 400px;
        overflow-y: auto;
        padding-right: 0.5rem;
    }
    .question-text {
        font-size: 1.15rem;
        font-weight: 600;
        margin-bottom: 0.75rem;
    }
    .portal-choose {
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
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


def render_lead_selection():
    cols = st.columns(6)
    selected_leads = []
    for i, lead in enumerate(PTB_ORDER):
        key = f"lead_{lead}"
        st.session_state.setdefault(key, lead in st.session_state["selected_leads"])
        if cols[i % 6].checkbox(lead, key=key):
            selected_leads.append(lead)
    return selected_leads or PTB_ORDER[:]


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


def render_visualization(file_bytes: bytes, filename: str):
    if filename.lower().endswith(".png"):
        st.image(file_bytes, width="stretch")
    elif filename.lower().endswith(".pdf"):
        base64_pdf = base64.b64encode(file_bytes).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800px" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)


def get_node_color(node_id, current_question_key):
    if node_id == current_question_key:
        return "#ffaaaa"
    elif node_id in st.session_state["answers"]:
        return "#aaffaa"
    elif node_id in st.session_state["navigation_history"]:
        return "#ffddaa"
    else:
        return "#aaaaff"


def build_traversed_edges():
    edges = []
    history = st.session_state["navigation_history"]
    for i in range(len(history) - 1):
        from_node = history[i]
        to_node = history[i + 1]
        edges.append(Edge(source=from_node, target=to_node, type="CURVE_SMOOTH", color="#000000", width=3))
    return edges


def navigate_to_question(question_key):
    st.session_state["current_question_index"] = get_question_index(question_key)
    st.session_state["show_review"] = False
    st.rerun()


def render_question_graph(current_question_key):
    import random

    random.seed(42)

    all_keys = NOISE_ARTIFACTS_QUESTION_ORDER + QRS_QUESTION_ORDER + DURATION_FOLLOWUPS + T_QUESTION_ORDER
    nodes = [
        Node(
            id=key,
            label=ALL_QUESTIONS_GRAPH[key]["question"][:30] + "...",
            size=40,
            color=get_node_color(key, current_question_key),
            shape="box",
            x=random.randint(-500, 500),
            y=random.randint(-500, 500),
            font={"size": 18, "color": "#000000"},
        )
        for key in all_keys
        if key in ALL_QUESTIONS_GRAPH
    ]

    config = Config(
        width="100%",
        height=500,
        directed=True,
        physics={
            "enabled": True,
            "barnesHut": {
                "gravitationalConstant": -10000,
                "centralGravity": 0.3,
                "springLength": 200,
                "springConstant": 0.04,
                "damping": 0.09,
                "avoidOverlap": 1,
            },
            "solver": "barnesHut",
        },
        hierarchical=False,
    )

    return_value = agraph(nodes=nodes, edges=build_traversed_edges(), config=config)
    if return_value and return_value in all_keys:
        navigate_to_question(return_value)
        st.rerun()


def update_navigation_history(new_question_key):
    history = st.session_state["navigation_history"]
    if not history or history[-1] != new_question_key:
        history.append(new_question_key)
    st.session_state["navigation_history"] = history


def render_file_upload_page():
    render_page_header("ECG Annotation", "Upload ECG File")
    uploaded_file = st.file_uploader("Upload a file", type=["xml", "npy", "png", "pdf"], accept_multiple_files=False)
    if uploaded_file is None:
        return
    filename = uploaded_file.name
    file_bytes = uploaded_file.getvalue()

    if filename.endswith((".xml", ".npy")):
        suffix = ".xml" if filename.endswith(".xml") else ".npy"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        try:
            loader = load_ecg_xml if filename.endswith(".xml") else load_ecg_np
            st.session_state["ecg_data"] = loader(tmp_path)
            st.session_state["file_type"] = "signal"
        finally:
            os.unlink(tmp_path)
    elif filename.endswith((".png", ".pdf")):
        st.session_state["visualization_data"] = file_bytes
        st.session_state["file_type"] = "visualization"

    st.session_state["current_filename"] = filename
    st.session_state["file_uploaded"] = True

    if st.button("Start Annotation", width="stretch"):
        first_question = get_next_question_key(0, {})
        if first_question:
            update_navigation_history(first_question)
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
        st.session_state["show_review"] = False
        history = st.session_state["navigation_history"]
        if history:
            history.pop()
        for followup in DURATION_FOLLOWUPS:
            if followup in answers:
                answers.pop(followup, None)
                st.session_state["current_question_index"] = len(ALL_QUESTION_ORDER)
                st.rerun()
                return
        last_idx = find_last_answered(ALL_QUESTION_ORDER, answers)
        if last_idx >= 0:
            answers.pop(ALL_QUESTION_ORDER[last_idx], None)
            st.session_state["current_question_index"] = last_idx
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


def go_back_to_noise(answers):
    last_idx = find_last_answered(NOISE_ARTIFACTS_QUESTION_ORDER, answers)
    if last_idx >= 0:
        answers.pop(NOISE_ARTIFACTS_QUESTION_ORDER[last_idx], None)
        return last_idx
    return 0


def handle_back_navigation(question_key):
    answers = st.session_state["answers"]
    history = st.session_state["navigation_history"]

    if history and history[-1] == question_key:
        history.pop()

    if question_key in DURATION_FOLLOWUPS:
        answers.pop("Duration", None)
        st.session_state["current_question_index"] = len(NOISE_ARTIFACTS_QUESTION_ORDER) + QRS_QUESTION_ORDER.index("Duration")
    elif question_key in T_QUESTION_ORDER:
        answers.pop(question_key, None)
        last_qrs_idx = find_last_answered(QRS_QUESTION_ORDER, answers)
        if last_qrs_idx >= 0:
            answers.pop(QRS_QUESTION_ORDER[last_qrs_idx], None)
            st.session_state["current_question_index"] = len(NOISE_ARTIFACTS_QUESTION_ORDER) + last_qrs_idx
        else:
            st.session_state["current_question_index"] = go_back_to_noise(answers)
    elif question_key in QRS_QUESTION_ORDER:
        answers.pop(question_key, None)
        qrs_idx = QRS_QUESTION_ORDER.index(question_key)
        if qrs_idx > 0:
            answers.pop(QRS_QUESTION_ORDER[qrs_idx - 1], None)
            st.session_state["current_question_index"] = len(NOISE_ARTIFACTS_QUESTION_ORDER) + qrs_idx - 1
        else:
            st.session_state["current_question_index"] = go_back_to_noise(answers)
    elif question_key in NOISE_LEAD_QUESTIONS:
        answers.pop(question_key, None)
        noise_answers = answers.get("Noise artifacts", [])
        prev_lead_key = None
        for noise_type, lead_key in NOISE_TO_LEAD_QUESTION.items():
            if lead_key == question_key:
                break
            if noise_type in noise_answers:
                prev_lead_key = lead_key
        if prev_lead_key:
            answers.pop(prev_lead_key, None)
            st.session_state["current_question_index"] = NOISE_ARTIFACTS_QUESTION_ORDER.index(prev_lead_key)
        else:
            answers.pop("Noise artifacts", None)
            st.session_state["current_question_index"] = 0
    else:
        new_index = st.session_state["current_question_index"] - 1
        if 0 <= new_index < len(NOISE_ARTIFACTS_QUESTION_ORDER):
            answers.pop(NOISE_ARTIFACTS_QUESTION_ORDER[new_index], None)
            st.session_state["current_question_index"] = new_index

    st.session_state["navigation_history"] = history
    st.rerun()


def handle_next_navigation(question_key, selected):
    answers = st.session_state["answers"]
    answers[question_key] = selected
    update_navigation_history(question_key)
    if question_key == "Duration":
        for opt in DURATION_FOLLOWUPS:
            answers.pop(opt, None)

    current_idx = get_question_index(question_key)
    if question_key == "Duration":
        st.session_state["current_question_index"] = current_idx
    else:
        st.session_state["current_question_index"] = current_idx + 1

    next_key = get_next_question_key(st.session_state["current_question_index"], answers)
    if next_key:
        update_navigation_history(next_key)
    else:
        st.session_state["show_review"] = True

    st.rerun()


def render_questions_page():
    render_page_header("ECG Annotation")
    file_type = st.session_state.get("file_type")
    if file_type == "signal":
        ecg_data = st.session_state["ecg_data"]
        if ecg_data is not None:
            selected_leads = render_lead_selection()
            st.session_state["selected_leads"] = selected_leads
            render_ecg_plot(ecg_data, selected_leads)
    elif file_type == "visualization":
        visualization_data = st.session_state.get("visualization_data")
        filename = st.session_state.get("current_filename")
        if visualization_data is not None and filename:
            render_visualization(visualization_data, filename)

    left_col, right_col = st.columns([3, 2])
    with left_col:
        st.markdown('<div class="question-panel">', unsafe_allow_html=True)

        if st.session_state["show_review"]:
            render_review_page()
        else:
            question_key = get_next_question_key(st.session_state["current_question_index"], st.session_state["answers"])
            if question_key is None:
                st.session_state["show_review"] = True
                st.rerun()
            else:
                question_data = ALL_QUESTIONS_GRAPH[question_key]
                st.markdown("### Question")
                st.markdown(
                    f'<div class="question-text">{question_data["question"]}</div>',
                    unsafe_allow_html=True,
                )
                prev_answer = st.session_state["answers"].get(question_key)
                if question_data.get("multilabel"):
                    default_val = prev_answer if isinstance(prev_answer, list) else []
                    selected = st.multiselect("Your answer", question_data["choices"], default=default_val, key=f"answer_{question_key}")
                else:
                    default_index = question_data["choices"].index(prev_answer) if prev_answer in question_data["choices"] else 0
                    selected = st.radio("Your answer", question_data["choices"], index=default_index, key=f"answer_{question_key}")

                if st.session_state["current_question_index"] > 0:
                    render_button_pair(
                        "Back",
                        "Next",
                        lambda: handle_back_navigation(question_key),
                        lambda: handle_next_navigation(question_key, selected),
                    )
                else:
                    if st.button("Next", width="stretch"):
                        handle_next_navigation(question_key, selected)
        st.markdown("</div>", unsafe_allow_html=True)
    with right_col:
        if st.session_state["show_graph"] and not st.session_state["show_review"]:
            question_key = get_next_question_key(st.session_state["current_question_index"], st.session_state["answers"])
            current_key = question_key or list(ALL_QUESTIONS_GRAPH.keys())[0]
            st.markdown("### Question Graph")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Hide Graph"):
                    st.session_state["show_graph"] = False
                    st.rerun()
            with col_b:
                if st.button("Reset Graph"):
                    st.session_state["navigation_history"] = []
                    st.rerun()

            render_question_graph(current_key)
        elif not st.session_state["show_review"]:
            st.markdown("### Question Graph")
            if st.button("Show Graph"):
                st.session_state["show_graph"] = True
                st.rerun()


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
    st.markdown('<p class="portal-choose">Choose mode:</p>', unsafe_allow_html=True)
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
