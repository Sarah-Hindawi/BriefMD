"""Flag display component matching VerificationResult schema."""

import streamlit as st

_SEVERITY_CONFIG = {
    "critical": {"icon": "X", "color": "#FF4B4B", "label": "CRITICAL"},
    "warning": {"icon": "!", "color": "#FF8C00", "label": "WARNING"},
    "info": {"icon": "i", "color": "#4B9EFF", "label": "INFO"},
    "monitor": {"icon": "?", "color": "#FFD700", "label": "MONITOR"},
}


def render_flag_cards(flags: dict) -> None:
    all_flags = flags.get("flags", [])

    for flag in all_flags:
        severity = flag.get("severity", "info")
        _render_card(
            severity=severity,
            title=flag.get("title", ""),
            subtitle=flag.get("category", ""),
            detail=flag.get("detail", ""),
            action=flag.get("suggested_action", ""),
        )

    if not all_flags:
        st.success("No flags found.")


def _render_card(severity: str, title: str, subtitle: str, detail: str, action: str = "") -> None:
    config = _SEVERITY_CONFIG.get(severity, _SEVERITY_CONFIG["info"])

    action_html = f'<br/><em style="color: #4B9EFF;">Suggestion: {action}</em>' if action else ""

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
            {action_html}
        </div>""",
        unsafe_allow_html=True,
    )
