import streamlit as st
from datetime import datetime
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- Configuration ---
st.set_page_config(
    page_title="ECG Annotation",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# --- Styles ---
st.markdown(
    """
    <style>
    .main { padding-top: 2rem; padding-bottom: 2rem; }
    .stButton>button { width: 100%; border-radius: 0.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 ECG Annotation")
st.markdown("---")

# --- Google Sheets Connection ---
# We establish the connection here.
# It requires a .streamlit/secrets.toml file to work (see instructions).
conn = st.connection("gsheets", type=GSheetsConnection)

# --- UI Layout ---
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

# --- Submission Logic ---
if st.button("Submit", type="primary"):
    if not answer.strip():
        st.warning("Please enter an answer before submitting.")
        st.stop()

    try:
        # 1. Fetch existing data to ensure we match the schema
        # We assume the sheet has headers: "Timestamp", "Filename", "Question", "Answer"
        # If the sheet is empty, this creates the dataframe structure.
        try:
            existing_data = conn.read(worksheet="Sheet1", usecols=list(range(4)), ttl=5)
            existing_data = existing_data.dropna(how="all")
        except Exception:
            # If sheet is completely empty or new
            existing_data = pd.DataFrame(columns=["Timestamp", "Filename", "Question", "Answer"])

        # 2. Prepare new data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename_str = uploaded_file.name if uploaded_file else "No file uploaded"

        new_row = pd.DataFrame([
            {
                "Timestamp": timestamp,
                "Filename": filename_str,
                "Question": question,
                "Answer": answer,
            }
        ])

        # 3. Append and Update
        # Concatenate old and new data
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)

        # Write back to Google Sheets
        conn.update(worksheet="Sheet1", data=updated_df)

        st.success("Response saved successfully to Google Sheets!")

        # Optional: Clear the form (requires session state management tricks or rerun)
        # st.rerun()

    except Exception as e:
        st.error(f"An error occurred saving to the database: {e}")
