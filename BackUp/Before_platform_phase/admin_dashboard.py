import streamlit as st

from services.api_client import APIClient


# ============================================================
# Helper: Safe Number
# ============================================================

def safe_float(value, default=0.0):

    try:
        return float(value)

    except (TypeError, ValueError):
        return default


# ============================================================
# Credit Requests
# ============================================================

def show_credit_requests(api_client: APIClient):

    st.subheader("💳 Credit Requests")

    col1, col2 = st.columns([4, 1])

    with col2:

        refresh = st.button(
            "🔄 Refresh",
            use_container_width=True,
        )

    if refresh:
        st.rerun()

    try:

        requests_data = (
            api_client.get_credit_requests()
        )

    except Exception as exc:

        st.error(
            f"❌ Failed to load credit requests: {exc}"
        )

        return

    if not requests_data:

        st.info(
            "No credit requests found."
        )

        return

    pending_count = sum(
        1
        for request in requests_data
        if request.get("status") == "pending"
    )

    approved_count = sum(
        1
        for request in requests_data
        if request.get("status") == "approved"
    )

    rejected_count = sum(
        1
        for request in requests_data
        if request.get("status") == "rejected"
    )

    metric1, metric2, metric3 = st.columns(3)

    with metric1:

        st.metric(
            "Pending",
            pending_count,
        )

    with metric2:

        st.metric(
            "Approved",
            approved_count,
        )

    with metric3:

        st.metric(
            "Rejected",
            rejected_count,
        )

    st.divider()

    for request in requests_data:

        request_id = request.get(
            "request_id"
        )

        principal_id = request.get(
            "principal_id"
        )

        requested_amount = request.get(
            "requested_amount"
        )

        approved_amount = request.get(
            "approved_amount"
        )

        reason = request.get(
            "reason"
        )

        status = request.get(
            "status",
            "unknown",
        )

        with st.container(border=True):

            top_col1, top_col2, top_col3 = (
                st.columns(3)
            )

            with top_col1:

                st.write(
                    f"**Request #{request_id}**"
                )

                st.write(
                    f"Principal ID: `{principal_id}`"
                )

            with top_col2:

                st.write(
                    f"**Requested:** "
                    f"${requested_amount}"
                )

                if approved_amount:

                    st.write(
                        f"**Approved:** "
                        f"${approved_amount}"
                    )

            with top_col3:

                st.write(
                    f"**Status:** "
                    f"`{status.upper()}`"
                )

            if reason:

                st.write(
                    f"**Reason:** {reason}"
                )

            # ------------------------------------------------
            # Pending Actions
            # ------------------------------------------------

            if status == "pending":

                st.divider()

                action_col1, action_col2, action_col3 = (
                    st.columns([2, 2, 1])
                )

                with action_col1:

                    approve_amount = st.number_input(
                        "Approval Amount",
                        min_value=0.01,
                        value=100.0,
                        step=10.0,
                        key=f"amount_{request_id}",
                    )

                with action_col2:

                    st.write("")
                    st.write("")

                    approve = st.button(
                        "✅ Approve",
                        key=f"approve_{request_id}",
                        use_container_width=True,
                    )

                with action_col3:

                    st.write("")
                    st.write("")

                    reject = st.button(
                        "❌ Reject",
                        key=f"reject_{request_id}",
                        use_container_width=True,
                    )

                # --------------------------------------------
                # Approve
                # --------------------------------------------

                if approve:

                    try:

                        result = (
                            api_client
                            .approve_credit_request(
                                request_id,
                                approved_amount=approve_amount,
                            )
                        )

                        st.success(
                            "✅ Credit request approved."
                        )

                        st.rerun()

                    except Exception as exc:

                        st.error(
                            f"❌ Approval failed: {exc}"
                        )

                # --------------------------------------------
                # Reject
                # --------------------------------------------

                if reject:

                    try:

                        api_client.reject_credit_request(
                            request_id
                        )

                        st.success(
                            "✅ Credit request rejected."
                        )

                        st.rerun()

                    except Exception as exc:

                        st.error(
                            f"❌ Rejection failed: {exc}"
                        )

# ============================================================
# Users
# ============================================================

def show_users(api_client: APIClient):
    st.subheader("👥 Organization Users")

    # ========================================================
    # Controls
    # ========================================================

    col1, col2, col3 = st.columns([4, 1, 1])

    with col1:
        search = st.text_input(
            "🔎 Search User",
            placeholder="Search by name, email or external ID...",
            key="user_search",
        )

    with col2:
        page_size = st.selectbox(
            "Users per page",
            options=[10, 25, 50, 100],
            index=0,
            key="user_page_size",
        )

    with col3:
        refresh = st.button(
            "🔄 Refresh",
            use_container_width=True,
            key="refresh_users",
        )

    if refresh:
        st.rerun()

    # ========================================================
    # Page state
    # ========================================================

    if "users_page" not in st.session_state:
        st.session_state["users_page"] = 1

    # Reset to page 1 when search/page size changes
    current_search = search.strip()

    previous_search = st.session_state.get(
        "previous_user_search",
        "",
    )

    previous_page_size = st.session_state.get(
        "previous_user_page_size",
        10,
    )

    if (
        current_search != previous_search
        or page_size != previous_page_size
    ):
        st.session_state["users_page"] = 1

    st.session_state["previous_user_search"] = current_search
    st.session_state["previous_user_page_size"] = page_size

    page = st.session_state["users_page"]

    # ========================================================
    # Load users from backend
    # ========================================================

    try:
        users_data = api_client.get_principals(
            page=page,
            page_size=page_size,
            search=current_search or None,
        )

    except Exception as exc:
        st.error(
            f"❌ Failed to load users: {exc}"
        )
        return

    # ========================================================
    # Extract paginated response
    # ========================================================

    principals = users_data.get(
        "items",
        [],
    )

    total_users = users_data.get(
        "total",
        0,
    )

    total_pages = users_data.get(
        "total_pages",
        0,
    )

    current_page = users_data.get(
        "page",
        page,
    )

    # ========================================================
    # No users
    # ========================================================

    if total_users == 0:

        if current_search:
            st.info(
                f'No users found for "{current_search}".'
            )
        else:
            st.info("No users found.")

        return

    # ========================================================
    # Search Result Section
    # ========================================================

    if current_search:

        st.markdown(
            f"### 🔎 Search Results for "
            f"`{current_search}`"
        )

        st.caption(
            f"{total_users} matching user(s) found"
        )

        for user in principals:

            with st.container(border=True):

                col1, col2, col3 = st.columns(
                    [2, 2, 1]
                )

                with col1:
                    st.write(
                        f"### 👤 "
                        f"{user.get('name', 'Unknown')}"
                    )

                    st.write(
                        f"**Principal ID:** "
                        f"`{user.get('principal_id')}`"
                    )

                    st.write(
                        f"**Email:** "
                        f"{user.get('email') or '—'}"
                    )

                with col2:

                    st.write(
                        f"**Team:** "
                        f"{user.get('team_name') or '—'}"
                    )

                    status = (
                        "🟢 Active"
                        if user.get("is_active")
                        else "🔴 Inactive"
                    )

                    st.write(
                        f"**Status:** {status}"
                    )

                    st.write(
                        f"**Type:** "
                        f"{user.get('type', '—')}"
                    )

                with col3:
                    st.metric(
                        "Remaining",
                        f"${
                            safe_float(
                                user.get(
                                    'remaining_credits'
                                )
                            )
                        :.4f}",
                    )

        st.divider()

    # ========================================================
    # Summary
    #
    # NOTE:
    # total_users comes from the database, so this works
    # correctly even with 10,000+ users.
    # ========================================================

    active_users = sum(
        1
        for user in principals
        if user.get("is_active")
    )

    total_allocated = sum(
        safe_float(
            user.get("allocated_credits")
        )
        for user in principals
    )

    total_used = sum(
        safe_float(
            user.get("used_credits")
        )
        for user in principals
    )

    total_remaining = sum(
        safe_float(
            user.get("remaining_credits")
        )
        for user in principals
    )

    st.markdown("### 📊 User Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Users",
            total_users,
        )

    with col2:
        st.metric(
            "Active on Current Page",
            active_users,
        )

    with col3:
        st.metric(
            "Allocated Credits",
            f"${total_allocated:.4f}",
        )

    with col4:
        st.metric(
            "Remaining Credits",
            f"${total_remaining:.4f}",
        )

    st.divider()

    # ========================================================
    # User Details
    # ========================================================

    st.subheader(
        "User Details"
    )

    start_user = (
        (current_page - 1) * page_size
    ) + 1

    end_user = min(
        start_user + len(principals) - 1,
        total_users,
    )

    st.caption(
        f"Showing {start_user}–{end_user} "
        f"of {total_users} users"
    )

    for user in principals:

        with st.container(border=True):

            col1, col2, col3 = st.columns(
                [2, 2, 1]
            )

            # ------------------------------------------------
            # User information
            # ------------------------------------------------

            with col1:

                st.write(
                    f"### 👤 "
                    f"{user.get('name', 'Unknown')}"
                )

                st.write(
                    f"**Principal ID:** "
                    f"`{user.get('principal_id')}`"
                )

                st.write(
                    f"**Email:** "
                    f"{user.get('email') or '—'}"
                )

                st.write(
                    f"**Type:** "
                    f"{user.get('type', '—')}"
                )

            # ------------------------------------------------
            # Team information
            # ------------------------------------------------

            with col2:

                st.write(
                    f"**Team:** "
                    f"{user.get('team_name') or '—'}"
                )

                st.write(
                    f"**Team ID:** "
                    f"`{user.get('team_id')}`"
                )

                status = (
                    "🟢 Active"
                    if user.get("is_active")
                    else "🔴 Inactive"
                )

                st.write(
                    f"**Status:** {status}"
                )

            # ------------------------------------------------
            # Remaining credits
            # ------------------------------------------------

            with col3:

                st.metric(
                    "Remaining",
                    f"${
                        safe_float(
                            user.get(
                                'remaining_credits'
                            )
                        )
                    :.4f}",
                )

            st.divider()

            # ------------------------------------------------
            # Credit information
            # ------------------------------------------------

            credit_col1, credit_col2, credit_col3 = (
                st.columns(3)
            )

            with credit_col1:

                st.write(
                    f"Allocated: "
                    f"**${
                        safe_float(
                            user.get(
                                'allocated_credits'
                            )
                        )
                    :.4f}**"
                )

            with credit_col2:

                st.write(
                    f"Used: "
                    f"**${
                        safe_float(
                            user.get(
                                'used_credits'
                            )
                        )
                    :.4f}**"
                )

            with credit_col3:

                routing_status = (
                    "🟢 Enabled"
                    if user.get("routing_enabled")
                    else "🔴 Disabled"
                )

                st.write(
                    f"LLM Routing: "
                    f"**{routing_status}**"
                )

    # ========================================================
    # Pagination
    # ========================================================

    st.divider()

    previous_col, page_col, next_col = st.columns(
        [1, 2, 1]
    )

    with previous_col:

        previous_disabled = (
            current_page <= 1
        )

        if st.button(
            "◀ Previous",
            disabled=previous_disabled,
            use_container_width=True,
            key="users_previous_page",
        ):
            st.session_state["users_page"] = (
                current_page - 1
            )

            st.rerun()

    with page_col:

        st.markdown(
            f"<div style='text-align:center;'>"
            f"<b>Page {current_page} "
            f"of {total_pages}</b>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with next_col:

        next_disabled = (
            current_page >= total_pages
        )

        if st.button(
            "Next ▶",
            disabled=next_disabled,
            use_container_width=True,
            key="users_next_page",
        ):
            st.session_state["users_page"] = (
                current_page + 1
            )

            st.rerun()

# ============================================================
# Team Hierarchy
# ============================================================

def show_team_hierarchy(api_client: APIClient):
    st.subheader("🏢 Organization Team Hierarchy")

    if "team_delete_error" in st.session_state:
        error_col1, error_col2 = st.columns([10, 1])

        with error_col1:
            st.error(
                f"❌ Cannot delete team: "
                f"{st.session_state['team_delete_error']}"
            )

        with error_col2:
            if st.button(
                "✕",
                key="close_team_delete_error",
            ):
                st.session_state.pop(
                    "team_delete_error",
                    None,
                )
                st.rerun()

    # --------------------------------------------------------
    # Load Teams
    # --------------------------------------------------------

    try:
        teams = api_client.get_teams()
    except Exception as exc:
        st.error(f"❌ Failed to load teams: {exc}")
        return

    if not teams:
        st.info("No teams found.")
        return

    # --------------------------------------------------------
    # Organization Summary
    # --------------------------------------------------------

    total_teams = len(teams)

    total_users = sum(
        team.get("user_count", 0)
        for team in teams
    )

    active_users = sum(
        1
        for team in teams
        for user in team.get("users", [])
        if user.get("is_active")
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Teams",
            total_teams,
        )

    with col2:
        st.metric(
            "Total Users",
            total_users,
        )

    with col3:
        st.metric(
            "Active Users",
            active_users,
        )

    st.divider()

    # --------------------------------------------------------
    # Team Hierarchy
    # --------------------------------------------------------

    for team in teams:

        team_name = team.get(
            "team_name",
            "Unknown Team",
        )

        team_id = team.get(
            "team_id",
            "—",
        )

        users = team.get(
            "users",
            [],
        )

        with st.expander(
            f"🏢 {team_name}  •  {len(users)} users",
            expanded=True,
        ):

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.write(
                    f"**Team ID:** `{team_id}`"
                )

            with col2:
                routing_status = (
                    "🟢 Enabled"
                    if team.get("routing_enabled")
                    else "🔴 Disabled"
                )

                st.write(
                    f"**LLM Routing:** {routing_status}"
                )

            with col3:
                st.write(
                    f"**DLP Mode:** "
                    f"`{team.get('dlp_mode', '—')}`"
                )

            with col4:
                delete_team = st.button(
                    "🗑️ Delete Team",
                    key=f"delete_team_{team_id}",
                    type="secondary",
                    use_container_width=True,
                )

                if delete_team:
                    try:
                        api_client.delete_team(team_id)

                        st.success(
                            f"Team '{team_name}' deleted successfully."
                        )

                        st.rerun()

                    except Exception as exc:
                        st.session_state["team_delete_error"] = str(exc)

            st.divider()

            if not users:
                st.info(
                    "No users assigned to this team."
                )
                continue

            st.write("### 👥 Team Members")

            # ------------------------------------------------
            # Team Users
            # ------------------------------------------------

            for user in users:

                user_id = user.get("principal_id")
                user_name = user.get(
                    "name",
                    "Unknown",
                )

                user_col1, user_col2, user_col3, user_col4 = st.columns(
                    [2, 2, 1, 1]
                )

                with user_col1:
                    st.write(
                        f"**👤 {user_name}**"
                    )

                    st.caption(
                        f"Principal ID: "
                        f"{user_id}"
                    )

                with user_col2:
                    st.write(
                        user.get("email") or "—"
                    )

                    st.caption(
                        f"Type: "
                        f"{user.get('type', '—')}"
                    )

                with user_col3:
                    status = (
                        "🟢 Active"
                        if user.get("is_active")
                        else "🔴 Inactive"
                    )

                    st.write(status)

                with user_col4:
                    view_usage = st.button(
                        "📊 Usage",
                        key=f"user_usage_{user_id}",
                        use_container_width=True,
                    )

                    if view_usage:
                        st.session_state["selected_user_id"] = user_id
                        st.session_state["selected_user_name"] = user_name
                        st.session_state["selected_user_team"] = team_name

                        st.rerun()

    # --------------------------------------------------------
    # Selected User Usage
    # --------------------------------------------------------

    if "selected_user_id" in st.session_state:
        st.divider()

        show_selected_user_usage(api_client)

def show_selected_user_usage(api_client: APIClient):
    user_id = st.session_state.get("selected_user_id")
    user_name = st.session_state.get(
        "selected_user_name",
        "Unknown User",
    )
    team_name = st.session_state.get(
        "selected_user_team",
        "Unknown Team",
    )

    st.subheader(
        f"📊 User Usage — {user_name}"
    )

    st.caption(
        f"Principal ID: {user_id}  •  Team: {team_name}"
    )

    # --------------------------------------------------------
    # Close User Details
    # --------------------------------------------------------

    close_col1, close_col2 = st.columns([10, 1])

    with close_col2:
        if st.button(
            "✕ Close",
            key="close_selected_user",
        ):
            st.session_state.pop(
                "selected_user_id",
                None,
            )

            st.session_state.pop(
                "selected_user_name",
                None,
            )

            st.session_state.pop(
                "selected_user_team",
                None,
            )

            st.rerun()

    # --------------------------------------------------------
    # Load Usage
    # --------------------------------------------------------

    try:
        usage_data = api_client.get_usage()
    except Exception as exc:
        st.error(
            f"❌ Failed to load usage data: {exc}"
        )
        return

    users = usage_data.get(
        "users",
        [],
    )

    # Find selected user
    selected_user = next(
        (
            user
            for user in users
            if user.get("principal_id") == user_id
        ),
        None,
    )

    # --------------------------------------------------------
    # No Usage
    # --------------------------------------------------------

    if selected_user is None:
        st.info(
            "No usage records found for this user."
        )
        return

    # --------------------------------------------------------
    # Usage Metrics
    # --------------------------------------------------------

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Requests",
            selected_user.get(
                "request_count",
                0,
            ),
        )

    with col2:
        st.metric(
            "Prompt Tokens",
            f"{selected_user.get('prompt_tokens', 0):,}",
        )

    with col3:
        st.metric(
            "Completion Tokens",
            f"{selected_user.get('completion_tokens', 0):,}",
        )

    with col4:
        st.metric(
            "Total Tokens",
            f"{selected_user.get('total_tokens', 0):,}",
        )

    with col5:
        st.metric(
            "Estimated Cost",
            f"${safe_float(selected_user.get('total_cost', 0)):.6f}",
        )

    st.divider()

    # --------------------------------------------------------
    # User Details
    # --------------------------------------------------------

    st.markdown("### 👤 User Details")

    detail_col1, detail_col2, detail_col3 = st.columns(3)

    with detail_col1:
        st.write(
            f"**User:** {selected_user.get('user_name', user_name)}"
        )

    with detail_col2:
        st.write(
            f"**Team:** {selected_user.get('team_name', team_name)}"
        )

    with detail_col3:
        st.write(
            f"**Principal ID:** `{user_id}`"
        )
# ============================================================
# Create User
# ============================================================

def show_create_user(api_client: APIClient):

    st.subheader("👤 Create New User")

    with st.form(
        "create_user_form",
        clear_on_submit=True,
    ):

        name = st.text_input(
            "Full Name",
            placeholder="e.g. Abhijeet Kulkarni",
        )

        email = st.text_input(
            "Email",
            placeholder="e.g. abhi@example.com",
        )

        team_id = st.number_input(
            "Team ID",
            min_value=1,
            value=1,
            step=1,
        )

        initial_credits = st.number_input(
            "Initial Credits",
            min_value=0.0,
            value=200.0,
            step=10.0,
        )

        submitted = st.form_submit_button(
            "➕ Create User",
            use_container_width=True,
        )

    if not submitted:

        return

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if not name.strip():

        st.error(
            "Please enter the user's name."
        )

        return

    if not email.strip():

        st.error(
            "Please enter the user's email."
        )

        return

    try:

        # ----------------------------------------------------
        # Create Principal
        # ----------------------------------------------------

        user_result = (
            api_client.create_principal(
                team_id=int(team_id),
                name=name.strip(),
                email=email.strip(),
                principal_type="user",
                initial_credits=float(
                    initial_credits
                ),
            )
        )

        principal_id = user_result[
            "principal_id"
        ]

        # ----------------------------------------------------
        # Generate API Key
        # ----------------------------------------------------

        key_result = (
            api_client.issue_api_key(
                principal_id
            )
        )

        # ----------------------------------------------------
        # Store result
        # ----------------------------------------------------

        st.session_state[
            "new_user_key"
        ] = key_result["api_key"]

        st.session_state[
            "new_user_details"
        ] = user_result

        st.success(
            "✅ User created successfully."
        )

    except Exception as exc:

        st.error(
            f"❌ Failed to create user: {exc}"
        )


# ============================================================
# Generated API Key
# ============================================================

def show_generated_key():

    if "new_user_key" not in st.session_state:

        return

    st.divider()

    st.subheader(
        "🔐 Generated API Key"
    )

    user_details = (
        st.session_state.get(
            "new_user_details",
            {},
        )
    )

    st.success(
        f"User **{user_details.get('name', 'Unknown')}** "
        "was created successfully."
    )

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Principal ID",
            user_details.get(
                "principal_id",
                "-",
            ),
        )

    with col2:

        st.metric(
            "Initial Credits",
            f"${user_details.get('initial_credits', '0')}",
        )

    st.warning(
        "⚠️ Save this API key securely. "
        "It will not be shown again after this session."
    )

    st.code(
        st.session_state["new_user_key"],
        language="text",
    )

    if st.button(
        "🗑️ Clear Key",
        use_container_width=True,
    ):

        st.session_state.pop(
            "new_user_key",
            None,
        )

        st.session_state.pop(
            "new_user_details",
            None,
        )

        st.rerun()


# ============================================================
# Organization Overview
# ============================================================

def show_organization_overview():

    st.subheader(
        "🏢 Organization Overview"
    )

    st.info(
        "Organization-wide usage analytics will be "
        "connected here in the next Admin Dashboard phase."
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Organizations",
            "1",
        )

    with col2:

        st.metric(
            "Teams",
            "—",
        )

    with col3:

        st.metric(
            "Users",
            "—",
        )

    with col4:

        st.metric(
            "AI Requests",
            "—",
        )


# ============================================================
# Usage Overview
# ============================================================

def show_usage_overview(api_client):
    st.subheader("📊 Usage Overview")
    st.caption("Organization, team-wise, user-wise and model-wise LLM usage")

    try:
        usage_data = api_client.get_usage()
    except Exception as exc:
        st.error(f"❌ Failed to load usage data: {exc}")
        return

    # =========================================================
    # Organization Overview
    # =========================================================

    organization = usage_data.get("organization", {})

    st.markdown("### 🏢 Organization Usage")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Requests",
            organization.get("request_count", 0),
        )

    with col2:
        st.metric(
            "Prompt Tokens",
            f"{organization.get('prompt_tokens', 0):,}",
        )

    with col3:
        st.metric(
            "Completion Tokens",
            f"{organization.get('completion_tokens', 0):,}",
        )

    with col4:
        st.metric(
            "Total Tokens",
            f"{organization.get('total_tokens', 0):,}",
        )

    with col5:
        st.metric(
            "Estimated Cost",
            f"${safe_float(organization.get('total_cost', 0)):.6f}",
        )

    st.divider()

    # =========================================================
    # Usage Over Time
    # =========================================================

    st.markdown("### 📅 Usage Over Time")

    daily_usage = usage_data.get("daily", [])

    period = st.selectbox(
        "Select Time Period",
        [
            "Today",
            "Last 7 Days",
            "Last 30 Days",
        ],
        key="usage_period",
    )

    from datetime import datetime, timedelta
    import pandas as pd

    today = datetime.now().date()

    if period == "Today":
        start_date = today
    elif period == "Last 7 Days":
        start_date = today - timedelta(days=6)
    else:
        start_date = today - timedelta(days=29)

    filtered_daily_usage = []

    for record in daily_usage:
        try:
            record_date = datetime.strptime(
                record["date"],
                "%Y-%m-%d",
            ).date()
        except (ValueError, TypeError, KeyError):
            continue

        if start_date <= record_date <= today:
            filtered_daily_usage.append(record)

    if not filtered_daily_usage:
        st.info(
            f"No usage data available for {period.lower()}."
        )
    else:

        # -----------------------------------------------------
        # Period Summary
        # -----------------------------------------------------

        total_requests = sum(
            item.get("request_count", 0)
            for item in filtered_daily_usage
        )

        total_prompt_tokens = sum(
            item.get("prompt_tokens", 0)
            for item in filtered_daily_usage
        )

        total_completion_tokens = sum(
            item.get("completion_tokens", 0)
            for item in filtered_daily_usage
        )

        total_tokens = sum(
            item.get("total_tokens", 0)
            for item in filtered_daily_usage
        )

        total_cost = sum(
            safe_float(item.get("total_cost", 0))
            for item in filtered_daily_usage
        )

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric(
                "Requests",
                total_requests,
            )

        with col2:
            st.metric(
                "Prompt Tokens",
                f"{total_prompt_tokens:,}",
            )

        with col3:
            st.metric(
                "Completion Tokens",
                f"{total_completion_tokens:,}",
            )

        with col4:
            st.metric(
                "Total Tokens",
                f"{total_tokens:,}",
            )

        with col5:
            st.metric(
                "Estimated Cost",
                f"${total_cost:.6f}",
            )

        st.divider()

        # -----------------------------------------------------
        # Prepare Chart Data
        # -----------------------------------------------------

        chart_data = pd.DataFrame(
            filtered_daily_usage
        )

        chart_data["date"] = pd.to_datetime(
            chart_data["date"]
        )

        chart_data = chart_data.sort_values(
            "date"
        )

        chart_data["display_date"] = (
            chart_data["date"].dt.strftime("%b %d")
        )

        # =====================================================
        # Daily Token Usage
        # =====================================================

        st.markdown("#### 📊 Daily Token Usage")

        token_chart_data = chart_data[
            [
                "display_date",
                "total_tokens",
            ]
        ].copy()

        token_chart_data = token_chart_data.set_index(
            "display_date"
        )

        st.bar_chart(
            token_chart_data,
            use_container_width=True,
        )

        # =====================================================
        # Daily Requests
        # =====================================================

        st.markdown("#### 📊 Daily Requests")

        request_chart_data = chart_data[
            [
                "display_date",
                "request_count",
            ]
        ].copy()

        request_chart_data = request_chart_data.set_index(
            "display_date"
        )

        st.bar_chart(
            request_chart_data,
            use_container_width=True,
        )

        # =====================================================
        # Daily Cost
        # =====================================================

        st.markdown("#### 💰 Daily Cost")

        cost_chart_data = chart_data[
            [
                "display_date",
                "total_cost",
            ]
        ].copy()

        cost_chart_data["total_cost"] = cost_chart_data[
            "total_cost"
        ].astype(float)

        cost_chart_data = cost_chart_data.set_index(
            "display_date"
        )

        st.bar_chart(
            cost_chart_data,
            use_container_width=True,
        )

    st.divider()

    # =========================================================
    # Team-wise Usage
    # =========================================================

    st.markdown("### 👥 Team-wise Usage")

    teams = usage_data.get("teams", [])

    if not teams:
        st.info("No team usage data available.")
    else:

        for team in teams:

            team_name = (
                team.get("team_name")
                or "Unassigned"
            )

            with st.expander(
                f"🏷️ {team_name}",
                expanded=False,
            ):

                col1, col2, col3, col4, col5 = st.columns(5)

                with col1:
                    st.metric(
                        "Requests",
                        team.get(
                            "request_count",
                            0,
                        ),
                    )

                with col2:
                    st.metric(
                        "Prompt Tokens",
                        f"{team.get('prompt_tokens', 0):,}",
                    )

                with col3:
                    st.metric(
                        "Completion Tokens",
                        f"{team.get('completion_tokens', 0):,}",
                    )

                with col4:
                    st.metric(
                        "Total Tokens",
                        f"{team.get('total_tokens', 0):,}",
                    )

                with col5:
                    st.metric(
                        "Estimated Cost",
                        f"${safe_float(team.get('total_cost', 0)):.6f}",
                    )

        st.markdown("#### 📊 Team Token Consumption")

        team_chart_data = pd.DataFrame(
            [
                {
                    "Team": (
                        team.get("team_name")
                        or "Unassigned"
                    ),
                    "Total Tokens": team.get(
                        "total_tokens",
                        0,
                    ),
                }
                for team in teams
            ]
        )

        if not team_chart_data.empty:

            team_chart_data = team_chart_data.sort_values(
                "Total Tokens",
                ascending=False,
            )

            team_chart_data = team_chart_data.set_index(
                "Team"
            )

            st.bar_chart(
                team_chart_data,
                use_container_width=True,
            )

        # -----------------------------------------------------
        # Team Cost
        # -----------------------------------------------------

        st.markdown("#### 💰 Team Cost")

        team_cost_data = pd.DataFrame(
            [
                {
                    "Team": (
                        team.get("team_name")
                        or "Unassigned"
                    ),
                    "Estimated Cost": safe_float(
                        team.get(
                            "total_cost",
                            0,
                        )
                    ),
                }
                for team in teams
            ]
        )

        if not team_cost_data.empty:

            team_cost_data = team_cost_data.sort_values(
                "Estimated Cost",
                ascending=False,
            )

            team_cost_data = team_cost_data.set_index(
                "Team"
            )

            st.bar_chart(
                team_cost_data,
                use_container_width=True,
            )

    st.divider()

    # =========================================================
    # User-wise Usage
    # =========================================================

    st.markdown("### 👤 User-wise Usage")

    users = usage_data.get("users", [])

    if not users:
        st.info("No user usage data available.")
    else:

        for user in users:

            user_name = (
                user.get("user_name")
                or "Unknown User"
            )

            team_name = (
                user.get("team_name")
                or "Unassigned"
            )

            with st.expander(
                f"👤 {user_name}  •  Team: {team_name}",
                expanded=False,
            ):

                col1, col2, col3, col4, col5 = st.columns(5)

                with col1:
                    st.metric(
                        "Requests",
                        user.get(
                            "request_count",
                            0,
                        ),
                    )

                with col2:
                    st.metric(
                        "Prompt Tokens",
                        f"{user.get('prompt_tokens', 0):,}",
                    )

                with col3:
                    st.metric(
                        "Completion Tokens",
                        f"{user.get('completion_tokens', 0):,}",
                    )

                with col4:
                    st.metric(
                        "Total Tokens",
                        f"{user.get('total_tokens', 0):,}",
                    )

                with col5:
                    st.metric(
                        "Estimated Cost",
                        f"${safe_float(user.get('total_cost', 0)):.6f}",
                    )

        # -----------------------------------------------------
        # User Token Consumption
        # -----------------------------------------------------

        st.markdown("#### 📊 User Token Consumption")

        user_chart_data = pd.DataFrame(
            [
                {
                    "User": (
                        user.get("user_name")
                        or "Unknown User"
                    ),
                    "Total Tokens": user.get(
                        "total_tokens",
                        0,
                    ),
                }
                for user in users
            ]
        )

        if not user_chart_data.empty:

            user_chart_data = user_chart_data.sort_values(
                "Total Tokens",
                ascending=False,
            )

            user_chart_data = user_chart_data.set_index(
                "User"
            )

            st.bar_chart(
                user_chart_data,
                use_container_width=True,
            )

    st.divider()

    # =========================================================
    # Model-wise Usage
    # =========================================================

    st.markdown("### 🤖 Model-wise Usage")

    models = usage_data.get("models", [])

    if not models:
        st.info("No model usage data available.")
    else:

        for model in models:

            provider = (
                model.get("provider")
                or "Unknown Provider"
            )

            model_name = (
                model.get("model")
                or "Unknown Model"
            )

            with st.expander(
                f"🤖 {model_name}  •  {provider}",
                expanded=False,
            ):

                col1, col2, col3, col4, col5 = st.columns(5)

                with col1:
                    st.metric(
                        "Requests",
                        model.get(
                            "request_count",
                            0,
                        ),
                    )

                with col2:
                    st.metric(
                        "Prompt Tokens",
                        f"{model.get('prompt_tokens', 0):,}",
                    )

                with col3:
                    st.metric(
                        "Completion Tokens",
                        f"{model.get('completion_tokens', 0):,}",
                    )

                with col4:
                    st.metric(
                        "Total Tokens",
                        f"{model.get('total_tokens', 0):,}",
                    )

                with col5:
                    st.metric(
                        "Estimated Cost",
                        f"${safe_float(model.get('total_cost', 0)):.6f}",
                    )

        # -----------------------------------------------------
        # Model Token Consumption
        # -----------------------------------------------------

        st.markdown("#### 📊 Model Token Consumption")

        model_chart_data = pd.DataFrame(
            [
                {
                    "Model": (
                        model.get("model")
                        or "Unknown Model"
                    ),
                    "Total Tokens": model.get(
                        "total_tokens",
                        0,
                    ),
                }
                for model in models
            ]
        )

        if not model_chart_data.empty:

            model_chart_data = model_chart_data.sort_values(
                "Total Tokens",
                ascending=False,
            )

            model_chart_data = model_chart_data.set_index(
                "Model"
            )

            st.bar_chart(
                model_chart_data,
                use_container_width=True,
            )

def show_ai_resources():

    st.subheader(
        "🤖 AI Resources"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.write(
            "### 🧠 Models"
        )

        st.info(
            "Configured and used LLM models "
            "will appear here."
        )

    with col2:

        st.write(
            "### 🕵️ Agents"
        )

        st.info(
            "Configured agents and their usage "
            "will appear here."
        )

    with col3:

        st.write(
            "### 🔌 MCP Tools"
        )

        st.info(
            "MCP servers and tools attached to "
            "users or agents will appear here."
        )


# ============================================================
# Security Overview
# ============================================================

def show_security_overview():

    st.subheader(
        "🛡️ Security Overview"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "DLP Blocks",
            "—",
        )

    with col2:

        st.metric(
            "Secrets Detected",
            "—",
        )

    with col3:

        st.metric(
            "Policy Violations",
            "—",
        )

    with col4:

        st.metric(
            "Security Alerts",
            "—",
        )


# ============================================================
# Admin Dashboard
# ============================================================

def show_admin_dashboard(
    api_client: APIClient,
):

    # ========================================================
    # Header
    # ========================================================

    st.title(
        "🛡️ Admin Dashboard"
    )

    st.write(
        "Enterprise AI Gateway Administration & Governance"
    )

    st.divider()

    # ========================================================
    # Overview
    # ========================================================

    show_organization_overview()

    st.divider()

    # ========================================================
    # Tabs
    # ========================================================

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "👤 Users",
            "💳 Credits",
            "📊 Usage",
            "🤖 AI Resources",
            "🛡️ Security",
        ]
    )

    # ========================================================
    # Users
    # ========================================================

    with tab1:
        show_users(api_client)

        st.divider()

        show_team_hierarchy(api_client)

        st.divider()

        show_create_user(api_client)
        show_generated_key()

    # ========================================================
    # Credits
    # ========================================================

    with tab2:

        show_credit_requests(
            api_client
        )

    # ========================================================
    # Usage
    # ========================================================

    with tab3:

        show_usage_overview(api_client)

    # ========================================================
    # AI Resources
    # ========================================================

    with tab4:

        show_ai_resources()

    # ========================================================
    # Security
    # ========================================================

    with tab5:

        show_security_overview()