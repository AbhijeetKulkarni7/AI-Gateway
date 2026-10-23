import streamlit as st

from services.api_client import APIClient


MODEL_OPTIONS = {
    "Azure OpenAI · GPT-4o": "company-chat-azure",
    "Google Gemini": "company-chat",
    "Meta Llama · Hugging Face": "company-chat-hf",
}


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _cost_label(value):
    """Do not present an uncalculated zero as free usage."""
    cost = _safe_float(value, default=-1.0)
    if cost <= 0:
        return "Not reported"
    return f"${cost:.8f}"


def _show_message_metadata(message):
    usage = message.get("usage") or {}
    gateway = message.get("gateway") or {}

    if not usage and not gateway:
        return

    with st.expander("Usage and gateway details", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Input tokens", usage.get("prompt_tokens", 0))
        with col2:
            st.metric("Output tokens", usage.get("completion_tokens", 0))
        with col3:
            st.metric("Total tokens", usage.get("total_tokens", 0))

        st.caption(f"Provider: {gateway.get('provider', 'Not reported')}")
        st.caption(f"Request cost: {_cost_label(gateway.get('estimated_cost'))}")

        usage_record_id = gateway.get("usage_record_id")
        if usage_record_id is not None:
            st.caption(f"Usage record: {usage_record_id}")

        if gateway.get("secrets_redacted"):
            st.info("The gateway detected and redacted one or more secrets before provider invocation.")


def show_user_dashboard(api_client: APIClient):
    user = st.session_state.get("user")
    if not user:
        st.error("User information not available. Please sign in again.")
        st.stop()

    st.title("AI Gateway Chat")
    st.caption(
        f"Welcome, {user.get('name', 'User')}. "
        "Your requests are processed through IAM_GATEWAY security controls."
    )

    # Keep conversation history scoped to the authenticated user so a reused
    # Streamlit session cannot display another user's prior chat.
    user_scope = (
        user.get("principal_id")
        or user.get("id")
        or user.get("email")
        or user.get("name")
        or "unknown"
    )
    history_key = f"chat_history_{user_scope}"
    st.session_state.setdefault(history_key, [])

    # Credit overview is kept compact so the chat remains the main focus.
    with st.expander("Credit overview", expanded=False):
        try:
            balance = api_client.get_credit_balance()
            st.session_state["credit_balance"] = balance
        except Exception as exc:
            balance = st.session_state.get("credit_balance", {})
            st.warning(f"Could not refresh credit balance: {exc}")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Allocated",
                f"${_safe_float(balance.get('allocated_credits')):.4f}",
            )
        with col2:
            st.metric(
                "Used",
                f"${_safe_float(balance.get('used_credits')):.4f}",
            )
        with col3:
            st.metric(
                "Remaining",
                f"${_safe_float(balance.get('remaining_credits')):.4f}",
            )

    # Model alias is resolved server-side by the gateway registry.
    control_col, clear_col = st.columns([5, 1])
    with control_col:
        selected_label = st.selectbox(
            "Model",
            options=list(MODEL_OPTIONS.keys()),
            index=0,
            key="chat_model_label",
        )
        selected_model = MODEL_OPTIONS[selected_label]
    with clear_col:
        st.write("")
        st.write("")
        if st.button("New chat", use_container_width=True, key="clear_chat_history"):
            st.session_state[history_key] = []
            st.session_state["last_chat_error"] = None
            st.rerun()

    st.caption(f"Gateway model alias: `{selected_model}`")
    st.divider()

    # Render prior conversation in ChatGPT-style message bubbles.
    for message in st.session_state[history_key]:
        role = message.get("role", "assistant")
        with st.chat_message(role):
            if message.get("is_error"):
                st.error(message.get("content", "Request failed."))
            else:
                st.markdown(message.get("content", ""))
                if role == "assistant":
                    _show_message_metadata(message)

    prompt = st.chat_input("Message IAM Gateway...")
    if not prompt or not prompt.strip():
        return

    st.session_state["last_chat_error"] = None
    st.session_state[history_key].append({
        "role": "user",
        "content": prompt.strip(),
    })

    # Only send actual user/assistant messages. Error notices and UI metadata
    # are not sent to the LLM as conversation content.
    messages_for_api = [
        {"role": item["role"], "content": item["content"]}
        for item in st.session_state[history_key]
        if item.get("role") in {"user", "assistant"}
        and not item.get("is_error")
    ]

    try:
        with st.spinner(f"Generating a response with {selected_label}..."):
            result = api_client.send_completion(
                messages=messages_for_api,
                model=selected_model,
            )

        choices = result.get("choices") or []
        if not choices:
            raise RuntimeError("The gateway returned no completion choices.")

        answer = (choices[0].get("message") or {}).get("content")
        if not answer:
            finish_reason = choices[0].get("finish_reason", "unknown")
            raise RuntimeError(
                f"The model returned an empty response (finish reason: {finish_reason})."
            )

        st.session_state[history_key].append({
            "role": "assistant",
            "content": answer,
            "usage": result.get("usage") or {},
            "gateway": result.get("x_gateway") or {},
        })

        # Refresh credits after a response, without turning a successful
        # completion into a failure if the balance endpoint is unavailable.
        try:
            st.session_state["credit_balance"] = api_client.get_credit_balance()
        except Exception:
            pass

        st.rerun()

    except Exception as exc:
        error_text = str(exc)
        lower_error = error_text.lower()

        if any(term in lower_error for term in ("502", "503", "serviceunavailable", "llm_provider_error")):
            friendly_error = (
                f"{selected_label} is temporarily unavailable or returned an upstream error. "
                "Please try again later or select another configured model."
            )
        else:
            # APIClient extracts the gateway's safe error code/message when available.
            friendly_error = error_text or "The request could not be completed."

        st.session_state[history_key].append({
            "role": "assistant",
            "content": friendly_error,
            "is_error": True,
        })
        st.rerun()
