"""Q&A interface for PCP dashboard. Mistral answers using patient data."""

import httpx
import streamlit as st


def render_chat_box(api_url: str, hadm_id: int) -> None:
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Display chat history
    for entry in st.session_state["chat_history"]:
        with st.chat_message("user"):
            st.write(entry["question"])
        with st.chat_message("assistant"):
            st.write(entry["answer"])

    # Input
    question = st.chat_input("Ask about this patient...")

    if not question:
        return

    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = httpx.post(
                    f"{api_url}/api/v1/chat/ask",
                    json={"hadm_id": hadm_id, "question": question},
                    timeout=120.0,
                )
                response.raise_for_status()
                answer = response.json().get("answer", "No answer received.")
            except httpx.HTTPStatusError as e:
                answer = f"API error: {e.response.status_code} — {e.response.text}"
            except httpx.TimeoutException:
                answer = "Request timed out. Mistral 7B may need more time."
            except httpx.HTTPError as e:
                answer = f"Connection error: {e}"

        st.write(answer)

    st.session_state["chat_history"].append({
        "question": question,
        "answer": answer,
    })
