"""Side B — PCP Verified Report Dashboard."""

import os

import httpx
import streamlit as st

from components.patient_selector import render_patient_selector
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
patient = render_patient_selector(API_URL)

if patient is None:
    st.info("Select a patient to view their report.")
    st.stop()

hadm_id = patient["hadm_id"]

# ── Generate report ──
if st.button("Generate Report", type="primary"):
    with st.spinner("Running pipeline: Extract → Verify → Connect..."):
        try:
            response = httpx.post(
                f"{API_URL}/api/v1/pcp/report",
                json={"patient_id": hadm_id},
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
todo = report.get("todo_list", [])
pcp_prefs = report.get("pcp_preferences", [])
col1.metric("Contraindications", len(flags.get("contraindications", [])))
col2.metric("Drug Interactions", len(flags.get("drug_interactions", [])))
col3.metric("To-Do Items", len(todo))
col4.metric("PCP Prefs Score", f"{sum(1 for p in pcp_prefs if p.get('passed'))}/{len(pcp_prefs)}")

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

# PCP Preferences
st.subheader("PCP Preferences Checklist")
render_checklist(pcp_prefs)

# Q&A
st.subheader("Ask About This Patient")
render_chat_box(API_URL, hadm_id)
