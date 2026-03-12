"""Side B — PCP Verified Report Dashboard."""

import os

import httpx
import streamlit as st

from components.flag_cards import render_flag_cards
from components.checklist_display import render_checklist
from components.comorbidity_graph import render_comorbidity_graph
from components.todo_list import render_todo_list
from components.chat_box import render_chat_box

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="BriefMD — PCP Report",
    page_icon="\u2695",
    layout="wide",
)

st.title("BriefMD — PCP Verified Report")
st.caption("Actionable intelligence from hospital discharge summaries")

# ── Patient selector ──
@st.cache_data(ttl=300)
def load_patients():
    """Fetch patient list from API."""
    try:
        resp = httpx.get(f"{API_URL}/api/v1/patients", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
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
    st.info("Select a patient to view their report.")
    st.stop()

patient = patient_options[selected_label]
hadm_id = patient["hadm_id"]

# ── Generate report ──
if st.button("Generate Report", type="primary"):
    with st.spinner("Running pipeline: Extract → Verify → Connect..."):
        try:
            response = httpx.post(
                f"{API_URL}/api/v1/pcp/report",
                json={"hadm_id": hadm_id},
                timeout=120.0,
            )
            response.raise_for_status()
            st.session_state["pcp_report"] = response.json()
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
if "pcp_report" not in st.session_state:
    st.stop()

report = st.session_state["pcp_report"]

# Summary metrics
col1, col2, col3, col4 = st.columns(4)
flags = report.get("flags", {})
all_flags = flags.get("flags", [])
todo = report.get("todo_list", [])
checklist = report.get("hqo_checklist", [])
critical = [f for f in all_flags if f.get("severity") == "critical"]
col1.metric("Critical Flags", len(critical))
col2.metric("Total Flags", len(all_flags))
col3.metric("To-Do Items", len(todo))
col4.metric("HQO Score", f"{sum(1 for c in checklist if c.get('passed'))}/{len(checklist)}")

# PCP Summary
pcp_summary = report.get("pcp_summary", "")
if pcp_summary:
    st.subheader("Patient Summary")
    st.markdown(pcp_summary)

# To-do list
st.subheader("Actionable To-Do List")
render_todo_list(todo)

# Flags
st.subheader("Flags")
render_flag_cards(flags)

# Comorbidity Network
st.subheader("Comorbidity Network")
network = report.get("network", {})
render_comorbidity_graph(network)

# HQO Checklist
st.subheader("HQO Safe Discharge Checklist")
render_checklist(checklist)

# Q&A
st.subheader("Ask About This Patient")
render_chat_box(API_URL, hadm_id)
