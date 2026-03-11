"""Shared patient dropdown for ED and PCP dashboards."""

import httpx
import streamlit as st


@st.cache_data(ttl=300)
def _fetch_patients(api_url: str) -> list[dict]:
    response = httpx.get(f"{api_url}/api/v1/patients", timeout=30.0)
    response.raise_for_status()
    return response.json()


def render_patient_selector(api_url: str) -> dict | None:
    try:
        patients = _fetch_patients(api_url)
    except (httpx.ConnectError, httpx.HTTPStatusError) as e:
        st.error(f"Cannot load patient list: {e}")
        return None

    if not patients:
        st.warning("No patients found in dataset.")
        return None

    options = {
        f"{p.get('subject_id', '?')} — {p.get('admission_diagnosis', 'N/A')} "
        f"(age {p.get('age', '?')}, {p.get('gender', '?')})": p
        for p in patients
    }

    selected = st.selectbox(
        "Select Patient",
        options=list(options.keys()),
        index=None,
        placeholder="Search by ID or diagnosis...",
    )

    if selected is None:
        return None

    return options[selected]
