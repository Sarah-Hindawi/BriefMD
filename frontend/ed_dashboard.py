"""Side A — ED Doctor Quality Gate Dashboard."""

import os

import httpx
import streamlit as st


from components.flag_cards import render_flag_cards
from components.checklist_display import render_checklist
from components.comorbidity_graph import render_comorbidity_graph

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="BriefMD — ED Quality Gate",
    page_icon="\u2695",
    layout="wide",
)

st.title("BriefMD — ED Quality Gate")
st.caption("Verify discharge summaries before they leave the hospital")

# ── Patient selector ──
@st.cache_data(ttl=300)
def _fetch_patients():
    """Fetch patient list from API (cached only on success)."""
    resp = httpx.get(f"{API_URL}/api/v1/patients", timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def load_patients():
    """Load patients, clearing cache on failure so errors aren't sticky."""
    try:
        return _fetch_patients()
    except Exception as e:
        _fetch_patients.clear()
        st.error(f"Failed to load patients: {e}")
        return []


patients = load_patients()

if not patients:
    st.warning("No patients loaded. Is the API running?")
    st.stop()
# Build dropdown labels: "hadm_id — Age/Gender — Diagnosis"
patient_options = {
    f"{p['hadm_id']} — {p.get('age', '?')}y {p.get('gender', '?')} — {p.get('admission_diagnosis', 'Unknown')[:60]}": p
    for p in patients
}

selected_label = st.selectbox(
    "Select Patient",
    options=list(patient_options.keys()),
    placeholder="Choose a patient...",
)

if not selected_label:
    st.info("Select a patient to begin analysis.")
    st.stop()

patient = patient_options[selected_label]
hadm_id = patient["hadm_id"]

# ── Load the actual discharge summary ──
@st.cache_data(ttl=300)
def load_summary(hid: int):
    """Fetch full discharge summary + record counts."""
    try:
        resp = httpx.get(f"{API_URL}/api/v1/ed/summaries/{hid}", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


summary_data = load_summary(hadm_id)

if summary_data is None:
    st.error(f"Could not load summary for hadm_id={hadm_id}")
    st.stop()

# Show record counts as context
col_a, col_b, col_c = st.columns(3)
counts = summary_data.get("record_counts", {})
col_a.metric("Coded Diagnoses", counts.get("diagnoses", "?"))
col_b.metric("Medications", counts.get("medications", "?"))
col_c.metric("Lab Results", counts.get("labs", "?"))

# ── Discharge summary viewer/editor ──
st.subheader("Discharge Summary")

original_note = summary_data.get("discharge_summary", "")

with st.expander("View / Edit Note", expanded=True):
    note_text = st.text_area(
        "Edit the note and re-analyze to check your fixes",
        value=original_note,
        height=400,
        key="note_editor",
    )

    # Show if the note has been modified
    if note_text != original_note and note_text.strip():
        st.info("Note has been modified. Click 'Analyze' to check the updated version.")

# ── Run analysis ──
if st.button("Analyze Discharge Summary", type="primary"):
    with st.spinner("Running pipeline: Extract → Verify → Connect..."):
        payload = {"hadm_id": hadm_id}

        # If the user edited the note, send the edited version
        if note_text.strip() and note_text != original_note:
            payload["discharge_note"] = note_text

        try:
            response = httpx.post(
                f"{API_URL}/api/v1/ed/analyze",
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            st.session_state["ed_report"] = response.json()
        except httpx.HTTPStatusError as e:
            st.error(f"API error: {e.response.status_code} — {e.response.text}")
            st.stop()
        except httpx.TimeoutException:
            st.error("Request timed out. The LLM may need more time for long notes.")
            st.stop()
        except httpx.HTTPError as e:
            st.error(f"Connection error: {e}")
            st.stop()

# ── Display results ──
if "ed_report" not in st.session_state:
    st.stop()

report = st.session_state["ed_report"]

# Summary metrics
st.subheader("Analysis Results")
col1, col2, col3, col4 = st.columns(4)

flags = report.get("flags", {})
all_flags = flags.get("flags", []) if isinstance(flags, dict) else flags
checklist = report.get("hqo_checklist", [])
critical = [f for f in all_flags if f.get("severity") == "critical"]
warnings = [f for f in all_flags if f.get("severity") == "warning"]

col1.metric("Critical Flags", len(critical))
col2.metric("Warnings", len(warnings))
col3.metric("Diagnoses Missed", len(flags.get("diagnoses_missed", []) if isinstance(flags, dict) else []))
col4.metric("HQO Score", f"{sum(1 for c in checklist if c.get('passed'))}/{len(checklist)}")

# Flags
st.subheader("Flags")
render_flag_cards(flags)

# Fix suggestions
suggestions = report.get("fix_suggestions", [])
if suggestions:
    st.subheader("Fix Suggestions")
    for i, suggestion in enumerate(suggestions, 1):
        st.markdown(f"**{i}.** {suggestion}")

# HQO Checklist
st.subheader("HQO Safe Discharge Checklist")
render_checklist(checklist)

# Comorbidity Network
st.subheader("Comorbidity Network")
network = report.get("network", {})
render_comorbidity_graph(network)

































