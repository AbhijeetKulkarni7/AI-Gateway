import html as html_lib
import streamlit as st
import streamlit.components.v1 as components



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
    """Render the user directory with backend pagination and backend search."""
    st.subheader("👥 Organization Users")
    st.caption("Search users by name, email, or external ID. Five matching users are loaded per page from the API.")

    page_state_key = "platform_admin_users_page"
    search_state_key = "platform_admin_users_search_term"
    search_reset_key = "platform_admin_users_search_reset_count"

    if page_state_key not in st.session_state:
        st.session_state[page_state_key] = 1
    if search_state_key not in st.session_state:
        st.session_state[search_state_key] = ""
    if search_reset_key not in st.session_state:
        st.session_state[search_reset_key] = 0

    # A changing widget key lets the Clear action reset the text box safely on rerun.
    search_widget_key = (
        f"platform_admin_users_search_input_{st.session_state[search_reset_key]}"
    )
    if search_widget_key not in st.session_state:
        st.session_state[search_widget_key] = st.session_state[search_state_key]

    # Search is submitted explicitly, so the backend is not queried on every keystroke.
    with st.form("platform_admin_users_search_form", clear_on_submit=False):
        search_col, button_col = st.columns([5, 1])
        with search_col:
            search_input = st.text_input(
                "Search users",
                placeholder="Name, email, or external ID",
                key=search_widget_key,
                label_visibility="collapsed",
            )
        with button_col:
            search_submitted = st.form_submit_button(
                "🔍 Search",
                use_container_width=True,
            )

    if search_submitted:
        st.session_state[search_state_key] = search_input.strip()
        st.session_state[page_state_key] = 1
        st.rerun()

    refresh_col, clear_col, info_col = st.columns([1, 1, 3])
    with refresh_col:
        refresh = st.button("🔄 Refresh", key="platform_admin_refresh_users", use_container_width=True)
    with clear_col:
        clear_search = st.button("✖ Clear search", key="platform_admin_clear_user_search", use_container_width=True)
    with info_col:
        if st.session_state[search_state_key]:
            st.caption(f"Search: {st.session_state[search_state_key]}")

    if clear_search:
        st.session_state[search_state_key] = ""
        st.session_state[search_reset_key] += 1
        st.session_state[page_state_key] = 1
        st.rerun()
    if refresh:
        st.rerun()

    page = max(1, int(st.session_state[page_state_key]))
    search_term = st.session_state[search_state_key].strip() or None

    try:
        response = api_client.get_principals(
            page=page,
            page_size=5,
            search=search_term,
        )
        if isinstance(response, dict):
            principals = response.get("items", [])
            total_users = int(response.get("total", len(principals)) or 0)
            total_pages = int(response.get("total_pages", 1) or 0)
            current_page = int(response.get("page", page) or page)
        else:
            # Backward-compatible fallback for clients returning an unpaginated list.
            principals = response or []
            total_users = len(principals)
            total_pages = max(1, (total_users + 4) // 5)
            current_page = page
            principals = principals[(page - 1) * 5:page * 5]
    except Exception as exc:
        st.error(f"❌ Failed to load users: {exc}")
        return

    # Handle cases where users were deleted while the admin was on a later page.
    if total_pages > 0 and page > total_pages:
        st.session_state[page_state_key] = total_pages
        st.rerun()

    if total_users == 0 or not principals:
        if search_term:
            st.info(f"No users matched '{search_term}'. Clear the search or try another term.")
        else:
            st.info("No users found.")
        return

    # Credit and active-user values below are intentionally page-scoped. The total
    # users count comes from the backend's COUNT query across all matching records.
    active_on_page = sum(1 for user in principals if user.get("is_active"))
    allocated_on_page = sum(safe_float(user.get("allocated_credits")) for user in principals)
    used_on_page = sum(safe_float(user.get("used_credits")) for user in principals)
    remaining_on_page = sum(safe_float(user.get("remaining_credits")) for user in principals)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total matching users", total_users)
    col2.metric("Active users (this page)", active_on_page)
    col3.metric("Allocated credits (this page)", f"${allocated_on_page:.4f}")
    col4.metric("Remaining credits (this page)", f"${remaining_on_page:.4f}")

    st.caption(
        f"Showing {(current_page - 1) * 5 + 1}–{min(current_page * 5, total_users)} "
        f"of {total_users} matching user(s) · Page {current_page} of {max(total_pages, 1)}"
    )
    st.divider()
    st.subheader("User Details")

    for user in principals:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.markdown(f"### 👤 {user.get('name', 'Unknown')}")
                st.write(f"**Principal ID:** `{user.get('principal_id')}`")
                st.write(f"**Email:** {user.get('email') or '—'}")
                st.write(f"**Type:** {user.get('type', '—')}")
                st.write(f"**Organization:** {user.get('organization_name') or '—'}")
                membership_role = user.get("membership_role")
                role_label = {
                    "org_admin": "Organization Admin (org_admin)",
                    "org_viewer": "Organization Viewer (org_viewer)",
                }.get(membership_role, "No active role assigned")
                st.write(f"**Organization Role:** {role_label}")
                st.caption(
                    "Membership: "
                    + ("Active" if user.get("membership_is_active") else "Inactive / missing")
                )

            with col2:
                st.write(f"**Team:** {user.get('team_name') or '—'}")
                st.write(f"**Team ID:** `{user.get('team_id')}`")
                status = "🟢 Active" if user.get("is_active") else "🔴 Inactive"
                st.write(f"**Status:** {status}")

            with col3:
                st.metric("Remaining", f"${safe_float(user.get('remaining_credits')):.4f}")

            st.divider()
            credit_col1, credit_col2, credit_col3 = st.columns(3)
            credit_col1.write(f"Allocated: **${safe_float(user.get('allocated_credits')):.4f}**")
            credit_col2.write(f"Used: **${safe_float(user.get('used_credits')):.4f}**")
            routing_status = "🟢 Enabled" if user.get("routing_enabled") else "🔴 Disabled"
            credit_col3.write(f"LLM Routing: **{routing_status}**")

    # Server-side pagination controls: each click requests only a five-user page.
    st.divider()
    previous_col, page_col, next_col = st.columns([1, 2, 1])
    with previous_col:
        if st.button(
            "⬅ Previous",
            key="platform_admin_users_previous_page",
            disabled=current_page <= 1,
            use_container_width=True,
        ):
            st.session_state[page_state_key] = current_page - 1
            st.rerun()
    with page_col:
        st.markdown(
            f"<div style='text-align:center;padding-top:0.45rem'>"
            f"Page <b>{current_page}</b> of <b>{max(total_pages, 1)}</b>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with next_col:
        if st.button(
            "Next ➡",
            key="platform_admin_users_next_page",
            disabled=current_page >= total_pages,
            use_container_width=True,
        ):
            st.session_state[page_state_key] = current_page + 1
            st.rerun()


# ============================================================
# Organization Membership Directory
# ============================================================

def show_membership_directory(api_client: APIClient):
    """Show organization membership roles from the backend as the source of truth."""
    st.subheader("🔐 Organization Role Directory")
    st.caption(
        "Verify who is an org_admin or org_viewer. These are organization membership roles; "
        "they do not change existing chatbot login behavior."
    )

    try:
        organizations = api_client.get_organizations()
    except Exception as exc:
        st.error(f"Could not load organizations: {exc}")
        return

    if not organizations:
        st.info("No organizations found.")
        return

    org_by_id = {int(org["id"]): org for org in organizations}
    org_ids = list(org_by_id)
    selected_org_id = st.selectbox(
        "Filter by organization",
        options=org_ids,
        format_func=lambda oid: f"{org_by_id[oid]['name']} (ID {oid})",
        key="role_directory_organization_id",
    )

    try:
        memberships = api_client.get_organization_memberships(selected_org_id)
    except Exception as exc:
        st.error(f"Could not load organization memberships: {exc}")
        return

    if not memberships:
        st.info("No organization memberships are assigned to this organization yet.")
        return

    records = []
    for membership in memberships:
        role = membership.get("role")
        role_label = {
            "org_admin": "Organization Admin",
            "org_viewer": "Organization Viewer",
        }.get(role, role or "Unassigned")
        records.append({
            "Principal ID": membership.get("principal_id"),
            "Name": membership.get("principal_name") or "Unknown",
            "Email": membership.get("principal_email") or "—",
            "Role": role_label,
            "Role Code": role or "—",
            "Membership Status": "Active" if membership.get("is_active") else "Inactive",
        })

    admin_count = sum(1 for row in records if row["Role Code"] == "org_admin" and row["Membership Status"] == "Active")
    viewer_count = sum(1 for row in records if row["Role Code"] == "org_viewer" and row["Membership Status"] == "Active")
    c1, c2, c3 = st.columns(3)
    c1.metric("Active Organization Admins", admin_count)
    c2.metric("Active Organization Viewers", viewer_count)
    c3.metric("Total Memberships", len(records))
    st.dataframe(records, use_container_width=True, hide_index=True)


# ============================================================
# Organization-Wise Hierarchy Graph
# ============================================================

def show_organization_hierarchy_graph(api_client: APIClient):
    """Render Organization -> Team -> User hierarchy with membership-role badges."""
    st.subheader("🌐 Organization-Wise Hierarchy Graph")
    st.caption("Each organization contains its teams and users. Role badges identify org_admin and org_viewer memberships.")

    try:
        organizations = api_client.get_organizations()
        teams = api_client.get_teams()
    except Exception as exc:
        st.error(f"Could not load organization hierarchy: {exc}")
        return

    if not organizations:
        st.info("No organizations are available to display.")
        return

    teams_by_org = {}
    roles_by_org = {}
    memberships_by_org = {}
    for org in organizations:
        org_id = int(org["id"])
        teams_by_org[org_id] = []
        try:
            memberships = api_client.get_organization_memberships(org_id)
        except Exception as exc:
            st.warning(f"Could not load memberships for {org.get('name', org_id)}: {exc}")
            memberships = []
        memberships_by_org[org_id] = memberships
        roles_by_org[org_id] = {}
        for membership in memberships:
            try:
                pid = int(membership.get("principal_id"))
            except (TypeError, ValueError):
                continue
            roles_by_org[org_id][pid] = {
                "role": membership.get("role"),
                "active": bool(membership.get("is_active")),
                "name": membership.get("principal_name") or f"Principal {pid}",
                "email": membership.get("principal_email") or "",
            }

    for team in teams:
        org_id = team.get("organization_id")
        if org_id is None:
            continue
        try:
            teams_by_org.setdefault(int(org_id), []).append(team)
        except (TypeError, ValueError):
            continue

    def role_badge(role_data):
        if not role_data:
            return '<span class="badge none">NO MEMBERSHIP</span>'
        role = role_data.get("role")
        active = role_data.get("active", False)
        if role == "org_admin":
            css, label = "admin", "ORG ADMIN"
        elif role == "org_viewer":
            css, label = "viewer", "ORG VIEWER"
        else:
            css, label = "none", str(role or "UNASSIGNED").upper()
        if not active:
            css, label = "inactive", f"INACTIVE · {label}"
        return f'<span class="badge {css}">{html_lib.escape(label)}</span>'

    html_parts = [r"""<!doctype html><html><head><meta charset="utf-8"><style>
      *{box-sizing:border-box} body{margin:0;padding:12px;font-family:Arial,sans-serif;color:#e8edf7;background:transparent}
      .org{border:2px solid #4263a6;background:#121a2a;border-radius:14px;padding:16px;margin:10px 0 22px;}
      .org-title{display:flex;flex-wrap:wrap;align-items:center;gap:10px;font-size:18px;font-weight:700;color:#fff}
      .muted{font-size:12px;color:#aab7cf;font-weight:400}.branches{display:flex;flex-wrap:wrap;gap:18px;margin:24px 0 4px;padding-top:18px;border-top:2px solid #465675;position:relative}
      .team{flex:1 1 260px;min-width:245px;max-width:480px;background:#192437;border:1px solid #4a5d7d;border-radius:10px;padding:12px;position:relative}
      .team:before{content:"";position:absolute;top:-20px;left:50%;height:19px;border-left:2px solid #465675}
      .team-title{font-weight:700;color:#dbeafe;margin-bottom:5px}.team-meta{font-size:11px;color:#9cacbf;margin-bottom:10px}
      .member{display:flex;gap:8px;justify-content:space-between;align-items:center;padding:8px;margin-top:7px;border-radius:7px;background:#0e1726;border:1px solid #34445d}
      .member-name{font-size:12px;font-weight:600;overflow-wrap:anywhere}.member-email{font-size:10px;color:#9cacbf;overflow-wrap:anywhere;margin-top:3px}
      .badge{flex-shrink:0;padding:4px 6px;border-radius:5px;font-size:9px;font-weight:700;letter-spacing:.3px}
      .admin{color:#fde68a;background:#713f12}.viewer{color:#bfdbfe;background:#1e40af}.none{color:#e5e7eb;background:#374151}.inactive{color:#fecaca;background:#7f1d1d}
      .empty{font-size:12px;color:#94a3b8;padding:9px;border:1px dashed #3b4b65;border-radius:7px}
      .unassigned{background:#33251a;border:1px solid #a16207;border-radius:10px;padding:12px;margin-top:12px}
      @media(max-width:650px){.member{align-items:flex-start;flex-direction:column}.team{max-width:100%;min-width:200px}}
    </style></head><body>"""]

    total_users = 0
    for org in organizations:
        org_id = int(org["id"])
        org_name = html_lib.escape(str(org.get("name", f"Organization {org_id}")))
        is_active = "Active" if org.get("is_active", True) else "Inactive"
        org_teams = teams_by_org.get(org_id, [])
        html_parts.append(
            f'<section class="org"><div class="org-title">🏢 {org_name} '
            f'<span class="muted">ORG ID {org_id} · {is_active} · {len(org_teams)} team(s)</span></div>'
            '<div class="branches">'
        )
        placed_ids = set()
        for team in org_teams:
            team_id = team.get("team_id", team.get("id", "—"))
            team_name = html_lib.escape(str(team.get("team_name", team.get("name", f"Team {team_id}"))))
            users = team.get("users") or []
            total_users += len(users)
            html_parts.append(
                f'<div class="team"><div class="team-title">👥 {team_name}</div>'
                f'<div class="team-meta">TEAM ID {html_lib.escape(str(team_id))} · {len(users)} user(s) · '
                f'DLP: {html_lib.escape(str(team.get("dlp_mode", "—")))}</div>'
            )
            if not users:
                html_parts.append('<div class="empty">No users assigned to this team.</div>')
            for user in users:
                try:
                    pid = int(user.get("principal_id"))
                except (TypeError, ValueError):
                    pid = None
                role_data = roles_by_org.get(org_id, {}).get(pid) if pid is not None else None
                if pid is not None:
                    placed_ids.add(pid)
                member_name = html_lib.escape(str(user.get("name", "Unknown user")))
                email = html_lib.escape(str(user.get("email") or ""))
                active_suffix = " · DISABLED" if not user.get("is_active", False) else ""
                html_parts.append(
                    '<div class="member"><div><div class="member-name">👤 '
                    f'{member_name} <span class="muted">(ID {html_lib.escape(str(pid if pid is not None else "—"))}{active_suffix})</span>'
                    '</div><div class="member-email">' + email + '</div></div>'
                    + role_badge(role_data) + '</div>'
                )
            html_parts.append('</div>')
        html_parts.append('</div>')

        orphan_members = []
        for membership in memberships_by_org.get(org_id, []):
            try:
                pid = int(membership.get("principal_id"))
            except (TypeError, ValueError):
                continue
            if pid not in placed_ids:
                orphan_members.append(membership)
        if orphan_members:
            html_parts.append('<div class="unassigned"><strong>⚠ Memberships not found under this organization\'s team list</strong>')
            for membership in orphan_members:
                pid = membership.get("principal_id")
                person = html_lib.escape(str(membership.get("principal_name") or f"Principal {pid}"))
                email = html_lib.escape(str(membership.get("principal_email") or ""))
                html_parts.append(
                    '<div class="member"><div><div class="member-name">👤 '
                    f'{person} <span class="muted">(ID {html_lib.escape(str(pid))})</span></div>'
                    f'<div class="member-email">{email}</div></div>'
                    + role_badge({"role": membership.get("role"), "active": membership.get("is_active")})
                    + '</div>'
                )
            html_parts.append('</div>')
        html_parts.append('</section>')

    html_parts.append('</body></html>')
    height = min(1400, max(470, 170 + len(organizations) * 180 + total_users * 54))
    components.html("".join(html_parts), height=height, scrolling=True)


# Team Hierarchy

# ============================================================



def show_team_hierarchy(api_client: APIClient):

    st.subheader("🛠️ Team Details & Removal")



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
    """Platform-admin user creation; org membership role is separate from chat type."""
    st.subheader("👤 Create New User")
    st.caption(
        "Create a user in a selected organization and team. Choose the organization's permission role; "
        "this does not change the existing chat-login behavior."
    )

    try:
        organizations = [
            org for org in api_client.get_organizations()
            if org.get("is_active", True)
        ]
        teams = api_client.get_teams()
    except Exception as exc:
        st.error(f"Could not load organizations and teams: {exc}")
        return

    if not organizations:
        st.warning("Create an organization before creating users.")
        return

    organizations_by_id = {int(org["id"]): org for org in organizations}
    organization_ids = list(organizations_by_id)
    organization_id = st.selectbox(
        "Organization",
        options=organization_ids,
        format_func=lambda oid: f"{organizations_by_id[oid]['name']} (ID {oid})",
        key="create_user_organization_id",
    )

    teams_by_id = {
        int(team.get("team_id", team.get("id"))): team
        for team in teams
        if team.get("organization_id") is not None
        and int(team["organization_id"]) == int(organization_id)
    }
    if not teams_by_id:
        st.warning("This organization has no teams. Create a team below before creating a user.")
        return

    team_ids = list(teams_by_id)
    team_id = st.selectbox(
        "Team",
        options=team_ids,
        format_func=lambda tid: f"{teams_by_id[tid].get('team_name', teams_by_id[tid].get('name', 'Team'))} (ID {tid})",
        key=f"create_user_team_id_{organization_id}",
    )

    with st.form("create_user_form", clear_on_submit=True):
        name = st.text_input("Full Name", placeholder="e.g. Asha Sharma")
        email = st.text_input("Email", placeholder="e.g. asha@example.com")
        membership_role = st.selectbox(
            "Organization Permission",
            options=["org_viewer", "org_admin"],
            format_func=lambda role: "Organization User (org_viewer)" if role == "org_viewer" else "Organization Admin (org_admin)",
            help="This membership role is separate from Principal.type and does not change chatbot login access.",
        )
        initial_credits = st.number_input(
            "Initial Credits", min_value=0.0, value=200.0, step=10.0
        )
        submitted = st.form_submit_button("➕ Create User", use_container_width=True)

    if not submitted:
        return
    if not name.strip():
        st.error("Please enter the user's name.")
        return
    if "@" not in email.strip() or email.strip().startswith("@") or email.strip().endswith("@"):
        st.error("Please enter a valid email address.")
        return

    try:
        user_result = api_client.create_principal(
            organization_id=int(organization_id),
            team_id=int(team_id),
            name=name.strip(),
            email=email.strip(),
            principal_type="user",  # Keep chat-facing type unchanged.
            membership_role=membership_role,
            initial_credits=float(initial_credits),
        )
        key_result = api_client.issue_api_key(user_result["principal_id"])
        st.session_state["new_user_key"] = key_result["api_key"]
        st.session_state["new_user_details"] = user_result
        st.success(
            f"User created in {organizations_by_id[int(organization_id)]['name']} with role {membership_role}."
        )
    except Exception as exc:
        st.error(f"❌ Failed to create user: {exc}")


def show_create_team(api_client: APIClient):
    """Create a team under an explicitly selected active organization."""
    st.subheader("🏢 Create Team")
    try:
        organizations = [
            org for org in api_client.get_organizations()
            if org.get("is_active", True)
        ]
    except Exception as exc:
        st.error(f"Could not load organizations: {exc}")
        return

    if not organizations:
        st.info("Create an organization before creating a team.")
        return

    org_by_id = {int(org["id"]): org for org in organizations}
    with st.form("platform_create_team_form", clear_on_submit=True):
        organization_id = st.selectbox(
            "Organization for new team",
            options=list(org_by_id),
            format_func=lambda oid: f"{org_by_id[oid]['name']} (ID {oid})",
        )
        team_name = st.text_input("Team name", placeholder="e.g. CSP")
        submitted = st.form_submit_button("➕ Create Team", use_container_width=True)

    if submitted:
        if not team_name.strip():
            st.error("Enter a team name.")
            return
        try:
            result = api_client.create_team(team_name.strip(), organization_id=organization_id)
            st.success(
                f"Team '{result.get('name', team_name)}' created under "
                f"{result.get('organization_name', org_by_id[organization_id]['name'])}."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Team creation failed: {exc}")


def show_manage_users(api_client: APIClient):
    """Edit identity, team, and organization membership role; deactivate/reactivate users."""
    st.subheader("🛠️ Update User / Organization Permission")
    try:
        response = api_client.get_principals(page=1, page_size=100)
        principals = response.get("items", []) if isinstance(response, dict) else response
        organizations = [
            org for org in api_client.get_organizations()
            if org.get("is_active", True)
        ]
        teams = api_client.get_teams()
    except Exception as exc:
        st.error(f"Could not load user management data: {exc}")
        return

    if not principals:
        st.info("No users to update yet.")
        return
    if not organizations:
        st.info("No active organizations are available.")
        return

    users_by_id = {int(user["principal_id"]): user for user in principals}
    org_by_id = {int(org["id"]): org for org in organizations}
    principal_ids = list(users_by_id)
    principal_id = st.selectbox(
        "Select user",
        options=principal_ids,
        format_func=lambda pid: (
            f"{users_by_id[pid].get('name', 'User')} · ID {pid} · "
            f"{users_by_id[pid].get('email') or 'no email'}"
        ),
        key="platform_edit_principal_id",
    )
    selected = users_by_id[principal_id]
    current_org = selected.get("organization_id")
    if current_org not in org_by_id:
        current_org = next(iter(org_by_id))
    org_ids = list(org_by_id)
    org_index = org_ids.index(int(current_org)) if int(current_org) in org_ids else 0

    with st.form(f"platform_edit_user_form_{principal_id}"):
        organization_id = st.selectbox(
            "Organization",
            options=org_ids,
            index=org_index,
            format_func=lambda oid: f"{org_by_id[oid]['name']} (ID {oid})",
            key=f"platform_edit_org_{principal_id}",
        )
        team_map = {
            int(team.get("team_id", team.get("id"))): team
            for team in teams
            if team.get("organization_id") is not None
            and int(team["organization_id"]) == int(organization_id)
        }
        if not team_map:
            st.warning("Selected organization has no teams. Create a team before moving this user.")
            st.form_submit_button("Save Changes", disabled=True)
            return
        team_ids = list(team_map)
        current_team = selected.get("team_id")
        team_index = team_ids.index(int(current_team)) if current_team in team_ids else 0
        team_id = st.selectbox(
            "Team",
            options=team_ids,
            index=team_index,
            format_func=lambda tid: f"{team_map[tid].get('team_name', team_map[tid].get('name', 'Team'))} (ID {tid})",
            key=f"platform_edit_team_{principal_id}_{organization_id}",
        )
        name = st.text_input("Full Name", value=selected.get("name", ""), key=f"platform_edit_name_{principal_id}")
        email = st.text_input("Email", value=selected.get("email") or "", key=f"platform_edit_email_{principal_id}")
        current_role = selected.get("membership_role") or "org_viewer"
        role_options = ["org_viewer", "org_admin"]
        role_index = role_options.index(current_role) if current_role in role_options else 0
        membership_role = st.selectbox(
            "Organization Permission",
            options=role_options,
            index=role_index,
            format_func=lambda role: "Organization User (org_viewer)" if role == "org_viewer" else "Organization Admin (org_admin)",
            key=f"platform_edit_role_{principal_id}",
            help="Grant/demote org_admin permission without changing chat login type.",
        )
        current_credits = str(selected.get("allocated_credits", "200.0000000000"))
        st.text_input(
            "Current credit allocation (manage changes in Credits tab)",
            value=current_credits,
            disabled=True,
            key=f"platform_edit_credits_{principal_id}",
        )
        save = st.form_submit_button("💾 Save User Changes", use_container_width=True)

    if save:
        if not name.strip():
            st.error("Name is required.")
            return
        if email.strip() and ("@" not in email.strip() or email.strip().startswith("@") or email.strip().endswith("@")):
            st.error("Enter a valid email address or leave email blank.")
            return
        try:
            result = api_client.update_principal(
                principal_id=principal_id,
                organization_id=organization_id,
                team_id=team_id,
                name=name.strip(),
                email=email.strip(),
                membership_role=membership_role,
                current_allocated_credits=current_credits,
            )
            st.success(
                f"Updated {result.get('name', name)}. Membership role: {result.get('membership_role', membership_role)}."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"User update failed: {exc}")

    st.divider()
    status_label = "Active" if selected.get("is_active", False) else "Inactive"
    st.write(f"**Account status:** {status_label}")
    if selected.get("is_active", False):
        confirm_deactivate = st.checkbox(
            "I confirm that this user should be deactivated and their active API keys revoked.",
            key=f"confirm_deactivate_principal_{principal_id}",
        )
        if st.button(
            "🚫 Deactivate User",
            type="secondary",
            disabled=not confirm_deactivate,
            key=f"deactivate_principal_{principal_id}",
        ):
            try:
                result = api_client.set_principal_active(principal_id, False)
                st.success(result.get("message", "User deactivated."))
                st.rerun()
            except Exception as exc:
                st.error(f"User deactivation failed: {exc}")
    else:
        confirm_activate = st.checkbox(
            "I confirm that this user should be reactivated. A new API key will be issued.",
            key=f"confirm_activate_principal_{principal_id}",
        )
        if st.button(
            "✅ Reactivate User and Issue New API Key",
            disabled=not confirm_activate,
            key=f"reactivate_principal_{principal_id}",
        ):
            try:
                api_client.set_principal_active(principal_id, True)
                key_result = api_client.issue_api_key(principal_id)
                st.session_state["new_user_key"] = key_result["api_key"]
                st.session_state["new_user_details"] = selected
                st.success("User reactivated. A new API key has been issued; store it securely.")
                st.rerun()
            except Exception as exc:
                st.error(f"User reactivation failed: {exc}")


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

    organization = usage_data.get("organization", {})
    st.markdown("### 🏢 Organization Usage")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: st.metric("Requests", organization.get("request_count", 0))
    with col2: st.metric("Prompt Tokens", f"{organization.get('prompt_tokens', 0):,}")
    with col3: st.metric("Completion Tokens", f"{organization.get('completion_tokens', 0):,}")
    with col4: st.metric("Total Tokens", f"{organization.get('total_tokens', 0):,}")
    with col5: st.metric("Estimated Cost", f"${safe_float(organization.get('total_cost', 0)):.6f}")

    st.divider()
    st.markdown("### 📅 Usage Over Time")
    daily_usage = usage_data.get("daily", [])
    period = st.selectbox("Select Time Period", ["Today", "Last 7 Days", "Last 30 Days"], key="usage_period")
    from datetime import datetime, timedelta
    import pandas as pd
    today = datetime.now().date()
    start_date = today if period == "Today" else today - timedelta(days=6 if period == "Last 7 Days" else 29)
    filtered_daily_usage = []
    for record in daily_usage:
        try:
            record_date = datetime.strptime(record["date"], "%Y-%m-%d").date()
        except (ValueError, TypeError, KeyError):
            continue
        if start_date <= record_date <= today:
            filtered_daily_usage.append(record)
    if not filtered_daily_usage:
        st.info(f"No usage data available for {period.lower()}.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        total_requests = sum(x.get("request_count", 0) for x in filtered_daily_usage)
        total_prompt_tokens = sum(x.get("prompt_tokens", 0) for x in filtered_daily_usage)
        total_completion_tokens = sum(x.get("completion_tokens", 0) for x in filtered_daily_usage)
        total_tokens = sum(x.get("total_tokens", 0) for x in filtered_daily_usage)
        with col1: st.metric("Requests", total_requests)
        with col2: st.metric("Prompt Tokens", f"{total_prompt_tokens:,}")
        with col3: st.metric("Completion Tokens", f"{total_completion_tokens:,}")
        with col4: st.metric("Total Tokens", f"{total_tokens:,}")
        chart_data = pd.DataFrame(filtered_daily_usage)
        chart_data["date"] = pd.to_datetime(chart_data["date"])
        chart_data = chart_data.sort_values("date")
        chart_data["date_label"] = chart_data["date"].dt.strftime("%b %d")
        chart_data = chart_data.set_index("date_label")
        st.write("#### 📊 Daily Token Usage")
        st.bar_chart(chart_data[["total_tokens"]])
        st.write("#### 📊 Daily Requests")
        st.bar_chart(chart_data[["request_count"]])
        st.write("#### Daily Details")
        for record in filtered_daily_usage:
            cost = safe_float(record.get("total_cost", 0))
            st.write(f"**{record.get('date', 'Unknown')}** • Requests: `{record.get('request_count', 0)}` • Tokens: `{record.get('total_tokens', 0):,}` • Cost: `${cost:.6f}`")

    st.divider()
    st.markdown("### 👥 Team-wise Usage")
    teams = usage_data.get("teams", [])
    if not teams:
        st.info("No team usage data available.")
    else:
        for team in teams:
            team_name = team.get("team_name") or "Unassigned"
            with st.expander(f"🏷️ {team_name}", expanded=False):
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1: st.metric("Requests", team.get("request_count", 0))
                with col2: st.metric("Prompt Tokens", f"{team.get('prompt_tokens', 0):,}")
                with col3: st.metric("Completion Tokens", f"{team.get('completion_tokens', 0):,}")
                with col4: st.metric("Total Tokens", f"{team.get('total_tokens', 0):,}")
                with col5: st.metric("Estimated Cost", f"${safe_float(team.get('total_cost', 0)):.6f}")
        st.write("#### 📊 Team Token Consumption")
        team_chart_data = pd.DataFrame([{"Team": t.get("team_name") or "Unassigned", "Total Tokens": t.get("total_tokens", 0)} for t in teams]).set_index("Team")
        st.bar_chart(team_chart_data[["Total Tokens"]])
        st.write("#### 💰 Cost by Team")
        team_cost_data = pd.DataFrame([{"Team": t.get("team_name") or "Unassigned", "Estimated Cost": safe_float(t.get("total_cost", 0))} for t in teams]).set_index("Team")
        st.bar_chart(team_cost_data[["Estimated Cost"]])

    st.divider()
    st.markdown("### 👤 User-wise Usage")
    users = usage_data.get("users", [])
    if not users:
        st.info("No user usage data available.")
    else:
        for user in users:
            user_name = user.get("user_name") or "Unknown User"
            team_name = user.get("team_name") or "Unassigned"
            with st.expander(f"👤 {user_name} • Team: {team_name}", expanded=False):
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1: st.metric("Requests", user.get("request_count", 0))
                with col2: st.metric("Prompt Tokens", f"{user.get('prompt_tokens', 0):,}")
                with col3: st.metric("Completion Tokens", f"{user.get('completion_tokens', 0):,}")
                with col4: st.metric("Total Tokens", f"{user.get('total_tokens', 0):,}")
                with col5: st.metric("Estimated Cost", f"${safe_float(user.get('total_cost', 0)):.6f}")

    st.divider()
    st.markdown("### 🤖 Model-wise Usage")
    models = usage_data.get("models", [])
    if not models:
        st.info("No model usage data available.")
    else:
        for model in models:
            provider = model.get("provider") or "Unknown Provider"
            model_name = model.get("model") or "Unknown Model"
            with st.expander(f"🤖 {model_name} • {provider}", expanded=False):
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1: st.metric("Requests", model.get("request_count", 0))
                with col2: st.metric("Prompt Tokens", f"{model.get('prompt_tokens', 0):,}")
                with col3: st.metric("Completion Tokens", f"{model.get('completion_tokens', 0):,}")
                with col4: st.metric("Total Tokens", f"{model.get('total_tokens', 0):,}")
                with col5: st.metric("Estimated Cost", f"${safe_float(model.get('total_cost', 0)):.6f}")
        st.write("#### 📊 Model Token Consumption")
        model_chart_data = pd.DataFrame([{"Model": m.get("model") or "Unknown Model", "Total Tokens": m.get("total_tokens", 0)} for m in models]).set_index("Model")
        st.bar_chart(model_chart_data[["Total Tokens"]])


# AI Resources Overview

# ============================================================



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
        show_membership_directory(api_client)

        st.divider()
        show_create_team(api_client)

        st.divider()
        show_organization_hierarchy_graph(api_client)

        st.divider()
        show_team_hierarchy(api_client)

        st.divider()
        show_create_user(api_client)
        show_generated_key()

        st.divider()
        show_manage_users(api_client)

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