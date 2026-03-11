"""HQO checklist and PCP preferences pass/fail display component."""

import streamlit as st


def render_checklist(items: list[dict]) -> None:
    if not items:
        st.info("No checklist data available.")
        return

    passed = sum(1 for item in items if item.get("passed"))
    total = len(items)

    if passed == total:
        st.success(f"All {total} items passed.")
    elif passed == 0:
        st.error(f"0 of {total} items passed.")
    else:
        st.warning(f"{passed} of {total} items passed.")

    for item in items:
        is_passed = item.get("passed", False)
        label = item.get("label", "")
        detail = item.get("detail", "")
        item_id = item.get("id", "")

        icon = "PASS" if is_passed else "FAIL"
        color = "#28A745" if is_passed else "#FF4B4B"

        st.markdown(
            f"""<div style="
                display: flex;
                align-items: center;
                padding: 0.5rem 0.75rem;
                margin-bottom: 0.25rem;
                border-left: 3px solid {color};
                background-color: {color}10;
                border-radius: 0 4px 4px 0;
            ">
                <strong style="color: {color}; min-width: 3rem;">[{icon}]</strong>
                <span style="min-width: 5rem; color: #888;">{item_id}</span>
                <strong>{label}</strong>
                {f'<span style="color: #888; margin-left: 1rem;">— {detail}</span>' if detail else ''}
            </div>""",
            unsafe_allow_html=True,
        )
