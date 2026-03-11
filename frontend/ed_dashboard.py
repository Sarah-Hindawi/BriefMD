"""Side A — ED Doctor Quality Gate Dashboard."""

import os

import httpx
import streamlit as st

from components.patient_selector import render_patient_selector
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
patient = render_patient_selector(API_URL)

if patient is None:
    st.info("Select a patient to begin analysis.")
    st.stop()

hadm_id = patient["hadm_id"]

# ── Note override ──
st.subheader("Discharge Summary")
with st.expander("View / Edit Note", expanded=False):
    note_override = st.text_area(
        "Edit the note and re-analyze to check fixes",
        value="",
        height=300,
        key="note_override",
    )

# ── Run analysis ──
if st.button("Analyze Discharge Summary", type="primary"):
    with st.spinner("Running pipeline: Extract → Verify → Connect..."):
        payload = {"patient_id": hadm_id}
        if note_override.strip():
            payload["note_override"] = note_override

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
            st.error("Request timed out. Mistral 7B may need more time for this note.")
            st.stop()
        except httpx.HTTPError as e:
            st.error(f"Connection error: {e}")
            st.stop()

# ── Display results ──
if "ed_report" not in st.session_state:
    st.stop()

report = st.session_state["ed_report"]

# Summary metrics
col1, col2, col3, col4 = st.columns(4)
flags = report.get("flags", {})
checklist = report.get("hqo_checklist", [])
col1.metric("Contraindications", len(flags.get("contraindications", [])))
col2.metric("Drug Interactions", len(flags.get("drug_interactions", [])))
col3.metric("Diagnosis Gaps", len(flags.get("diagnosis_gaps", [])))
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
