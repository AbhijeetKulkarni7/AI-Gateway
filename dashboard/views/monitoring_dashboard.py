
import pandas as pd
import streamlit as st


def show_monitoring_dashboard(api_client):
    st.title("🛡️ Monitoring Dashboard")
    st.caption("Operational and security monitoring for the LLM Gateway")

    # ---------------------------------------------------------
    # Refresh
    # ---------------------------------------------------------
    _, refresh_col = st.columns([5, 1])

    with refresh_col:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    # ---------------------------------------------------------
    # Load monitoring data
    # ---------------------------------------------------------
    try:
        data = api_client.get_monitoring()
    except Exception as exc:
        st.error(f"Failed to load monitoring data: {exc}")
        return

    organization = data.get("organization") or {}
    users = data.get("users") or []
    providers = data.get("providers") or []
    daily_trends = data.get("daily_trends") or []

    # ---------------------------------------------------------
    # Organization Overview
    # ---------------------------------------------------------
    st.subheader("🏢 Organization Overview")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Requests", organization.get("total_requests", 0))
    col2.metric("Successful", organization.get("successful", 0))
    col3.metric(
        "Success Rate",
        f"{float(organization.get('success_rate') or 0):.2f}%",
    )
    col4.metric("Secrets Redacted", organization.get("secrets_redacted", 0))

    # ---------------------------------------------------------
    # Security and Failure Metrics
    # ---------------------------------------------------------
    st.subheader("🚨 Security & Failure Events")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Policy Blocked", organization.get("policy_blocked", 0))
    col2.metric("Provider Errors", organization.get("provider_errors", 0))
    col3.metric("Credit Exhausted", organization.get("credit_exhausted", 0))
    col4.metric(
        "Account Blocked",
        organization.get("credit_account_blocked", 0),
    )

    st.divider()

    # ---------------------------------------------------------
    # Provider and Model Monitoring
    # ---------------------------------------------------------
    st.subheader("🤖 Provider & Model Monitoring")

    if providers:
        provider_df = pd.DataFrame(providers)

        provider_defaults = {
            "provider": "unknown",
            "model": "unknown",
            "total_requests": 0,
            "successful": 0,
            "provider_errors": 0,
            "total_tokens": 0,
            "estimated_cost": 0,
        }

        for column, default in provider_defaults.items():
            if column not in provider_df.columns:
                provider_df[column] = default

        provider_df["provider"] = (
            provider_df["provider"].fillna("unknown").astype(str)
        )
        provider_df["model"] = (
            provider_df["model"].fillna("unknown").astype(str)
        )

        numeric_columns = [
            "total_requests",
            "successful",
            "provider_errors",
            "total_tokens",
            "estimated_cost",
        ]

        for column in numeric_columns:
            provider_df[column] = pd.to_numeric(
                provider_df[column], errors="coerce"
            ).fillna(0)

        # Aggregate model rows into provider-level totals.
        provider_summary = (
            provider_df.groupby("provider")[numeric_columns]
            .sum()
            .sort_values("total_requests", ascending=False)
        )

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("**Requests by Provider**")
            st.bar_chart(provider_summary[["total_requests"]])

        with chart_col2:
            st.markdown("**Tokens by Provider**")
            st.bar_chart(provider_summary[["total_tokens"]])

        chart_col3, chart_col4 = st.columns(2)

        with chart_col3:
            st.markdown("**Successful Requests vs. Provider Errors**")
            st.bar_chart(
                provider_summary[["successful", "provider_errors"]]
            )

        with chart_col4:
            st.markdown("**Estimated Cost by Provider**")
            st.bar_chart(provider_summary[["estimated_cost"]])

        st.markdown("**Provider and Model Details**")

        provider_display = provider_df.copy()
        provider_display["estimated_cost"] = (
            provider_display["estimated_cost"].map(
                lambda value: f"${value:,.8f}"
            )
        )

        provider_display = provider_display.rename(
            columns={
                "provider": "Provider",
                "model": "Model",
                "total_requests": "Requests",
                "successful": "Successful",
                "provider_errors": "Provider Errors",
                "total_tokens": "Tokens",
                "estimated_cost": "Estimated Cost",
            }
        )

        st.dataframe(
            provider_display,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No provider usage data available yet. "
            "Generate requests through the gateway to populate these charts."
        )

    st.divider()

    # ---------------------------------------------------------
    # Daily Request Trends
    # ---------------------------------------------------------
    st.subheader("📅 Daily Request Trends")

    if daily_trends:
        daily_df = pd.DataFrame(daily_trends)

        daily_defaults = {
            "date": None,
            "total_requests": 0,
            "successful": 0,
            "provider_errors": 0,
            "policy_blocked": 0,
        }

        for column, default in daily_defaults.items():
            if column not in daily_df.columns:
                daily_df[column] = default

        daily_df["date"] = pd.to_datetime(
            daily_df["date"], errors="coerce"
        )
        daily_df = daily_df.dropna(subset=["date"])

        daily_numeric_columns = [
            "total_requests",
            "successful",
            "provider_errors",
            "policy_blocked",
        ]

        for column in daily_numeric_columns:
            daily_df[column] = pd.to_numeric(
                daily_df[column], errors="coerce"
            ).fillna(0)

        daily_df = daily_df.sort_values("date")

        if not daily_df.empty:
            daily_df = daily_df.set_index("date")

            st.markdown("**Daily Requests by Status**")
            st.line_chart(
                daily_df[
                    ["successful", "provider_errors", "policy_blocked"]
                ]
            )

            st.markdown("**Total Requests per Day**")
            st.bar_chart(daily_df[["total_requests"]])

            with st.expander("View daily trend data"):
                st.dataframe(
                    daily_df.reset_index(),
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("No valid daily trend dates were returned by the API.")
    else:
        st.info(
            "No daily request history available yet. "
            "Daily trends appear when usage records exist."
        )

    st.divider()

    # ---------------------------------------------------------
    # User-wise Monitoring
    # ---------------------------------------------------------
    st.subheader("👥 User-wise Monitoring")

    if not users:
        st.info("No user monitoring records available yet.")
        return

    rows = []

    for user in users:
        rows.append(
            {
                "User": user.get("user_name") or "Unknown",
                "Team": user.get("team_name") or "-",
                "Requests": user.get("total_requests", 0) or 0,
                "Successful": user.get("successful", 0) or 0,
                "Policy Blocked": user.get("policy_blocked", 0) or 0,
                "Provider Errors": user.get("provider_errors", 0) or 0,
                "Credit Exhausted": user.get("credit_exhausted", 0) or 0,
                "Secrets Redacted": user.get("secrets_redacted", 0) or 0,
                "Tokens": user.get("total_tokens", 0) or 0,
                "Cost": float(user.get("estimated_cost") or 0),
                "Success Rate": float(user.get("success_rate") or 0),
            }
        )

    user_df = pd.DataFrame(rows)

    # ---------------------------------------------------------
    # User Search
    # ---------------------------------------------------------
    search = st.text_input(
        "🔎 Search user or team",
        placeholder="Enter a user or team name...",
        key="monitoring_user_search",
    )

    if search.strip():
        mask = (
            user_df["User"].astype(str).str.contains(
                search, case=False, na=False
            )
            | user_df["Team"].astype(str).str.contains(
                search, case=False, na=False
            )
        )
        filtered_df = user_df[mask].copy()
    else:
        filtered_df = user_df.copy()

    if filtered_df.empty:
        st.info("No users match your search.")
        return

    # ---------------------------------------------------------
    # User Analytics
    # ---------------------------------------------------------
    st.markdown("### 📈 User Usage Analytics")

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("**Requests by User**")
        request_chart = filtered_df.set_index("User")[["Requests"]]
        st.bar_chart(request_chart)

    with chart_col2:
        st.markdown("**Token Usage by User**")
        token_chart = filtered_df.set_index("User")[["Tokens"]]
        st.bar_chart(token_chart)

    st.markdown("**Estimated Cost by User**")
    cost_chart = filtered_df.set_index("User")[["Cost"]]
    st.bar_chart(cost_chart)

    st.divider()

    # ---------------------------------------------------------
    # User Monitoring Table
    # ---------------------------------------------------------
    st.markdown("### 📋 User Monitoring Details")

    display_df = filtered_df.copy()
    display_df["Cost"] = display_df["Cost"].map(
        lambda value: f"${value:,.8f}"
    )
    display_df["Success Rate"] = display_df["Success Rate"].map(
        lambda value: f"{value:.2f}%"
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        f"Showing {len(filtered_df)} of {len(user_df)} users."
    )
