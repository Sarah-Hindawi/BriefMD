"""Actionable to-do list for PCP dashboard."""

import streamlit as st

_PRIORITY_CONFIG = {
    1: {"label": "URGENT", "color": "#FF4B4B"},
    2: {"label": "REVIEW", "color": "#FF8C00"},
    3: {"label": "FOLLOW-UP", "color": "#4B9BFF"},
}


def render_todo_list(items: list[dict]) -> None:
    if not items:
        st.info("No action items found.")
        return

    for item in items:
        priority = item.get("priority", 3)
        config = _PRIORITY_CONFIG.get(priority, _PRIORITY_CONFIG[3])
        action = item.get("action", "")
        reason = item.get("reason", "")
        category = item.get("category", "")

        st.markdown(
            f"""<div style="
                border-left: 4px solid {config['color']};
                padding: 0.5rem 0.75rem;
                margin-bottom: 0.4rem;
                background-color: {config['color']}10;
                border-radius: 0 4px 4px 0;
            ">
                <strong style="color: {config['color']};">[{config['label']}]</strong>
                {f'<span style="color: #888; margin-left: 0.25rem;">[{category}]</span>' if category else ''}
                <span style="margin-left: 0.25rem;">{action}</span>
                {f'<br/><span style="color: #888; font-size: 0.9em;">{reason}</span>' if reason else ''}
            </div>""",
            unsafe_allow_html=True,
        )
