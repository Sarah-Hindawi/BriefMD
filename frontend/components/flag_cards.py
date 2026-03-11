"""Red/yellow/orange flag display component."""

import streamlit as st

_SEVERITY_CONFIG = {
    "red": {"icon": "X", "color": "#FF4B4B", "label": "CRITICAL"},
    "orange": {"icon": "!", "color": "#FF8C00", "label": "WARNING"},
    "yellow": {"icon": "?", "color": "#FFD700", "label": "MISSING"},
}


def render_flag_cards(flags: dict) -> None:
    # Contraindications
    for ci in flags.get("contraindications", []):
        _render_card(
            severity="red",
            title=f"{ci.get('drug', '')} + {ci.get('condition', '')}",
            subtitle=ci.get("severity_label", ""),
            detail=ci.get("detail", ""),
        )

    # Drug interactions
    for di in flags.get("drug_interactions", []):
        _render_card(
            severity="orange",
            title=f"{di.get('drug_a', '')} + {di.get('drug_b', '')}",
            subtitle=di.get("severity_label", ""),
            detail=di.get("detail", ""),
        )

    # General flags
    for flag in flags.get("flags", []):
        severity = flag.get("severity", "yellow")
        _render_card(
            severity=severity,
            title=flag.get("summary", ""),
            subtitle=flag.get("category", ""),
            detail=flag.get("detail", ""),
        )

    # No flags
    total = (
        len(flags.get("contraindications", []))
        + len(flags.get("drug_interactions", []))
        + len(flags.get("flags", []))
    )
    if total == 0:
        st.success("No flags found.")


def _render_card(severity: str, title: str, subtitle: str, detail: str) -> None:
    config = _SEVERITY_CONFIG.get(severity, _SEVERITY_CONFIG["yellow"])

    st.markdown(
        f"""<div style="
            border-left: 4px solid {config['color']};
            padding: 0.75rem 1rem;
            margin-bottom: 0.5rem;
            background-color: {config['color']}15;
            border-radius: 0 4px 4px 0;
        ">
            <strong style="color: {config['color']};">[{config['label']}]</strong>
            <strong>{title}</strong><br/>
            <span style="color: #888;">{subtitle}</span>
            {f'<br/><span>{detail}</span>' if detail else ''}
        </div>""",
        unsafe_allow_html=True,
    )
