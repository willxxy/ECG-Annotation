import streamlit as st
from datetime import datetime
import os

st.set_page_config(
    page_title="ECG Annotation",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .main {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 ECG Annotation")

st.markdown("---")

st.subheader("File Upload")
uploaded_file = st.file_uploader(
    "Upload your ECG file",
    type=None,
    help="Select a file to upload",
    label_visibility="collapsed",
)

st.markdown("---")

st.subheader("Question")
question = "What is your assessment of this ECG?"
st.markdown(f"**{question}**")

answer = st.text_area(
    "Your answer",
    height=150,
    placeholder="Enter your assessment here...",
    label_visibility="collapsed",
)

if "submission_content" not in st.session_state:
    st.session_state.submission_content = None
if "submission_filename" not in st.session_state:
    st.session_state.submission_filename = None

if st.button("Submit", type="primary"):
    if answer.strip():
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        timestamp_file = now.strftime("%Y%m%d_%H%M%S")

        data_dir = "submissions"
        os.makedirs(data_dir, exist_ok=True)

        filename = os.path.join(data_dir, f"submission_{timestamp_file}.txt")

        submission_content = f"Timestamp: {timestamp}\n"
        submission_content += f"Question: {question}\n"
        submission_content += f"Answer: {answer}\n"
        if uploaded_file is not None:
            submission_content += f"File uploaded: {uploaded_file.name}\n"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(submission_content)

        st.session_state.submission_content = submission_content
        st.session_state.submission_filename = f"submission_{timestamp_file}.txt"

        st.success("Response saved successfully!")
        st.rerun()
    else:
        st.warning("Please enter an answer before submitting.")

if st.session_state.submission_content is not None:
    st.markdown("---")
    st.download_button(
        label="📥 Download Submission",
        data=st.session_state.submission_content,
        file_name=st.session_state.submission_filename,
        mime="text/plain",
        type="primary",
    )
