import streamlit as st

from services.api_client import APIClient
from services.auth_service import (
    authenticate_user,
    authenticate_admin,
)

from views.user_dashboard import show_user_dashboard
from views.admin_dashboard import show_admin_dashboard
from views.monitoring_dashboard import show_monitoring_dashboard
from views.policy_dashboard import show_policy_dashboard

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="AI Identity & Access Gateway",
    page_icon="🤖",
    layout="wide",
)

BASE_URL = "http://127.0.0.1:8000"

# ---------------------------------------------------------
# Session State
# ---------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if "login_type" not in st.session_state:
    st.session_state["login_type"] = None

if "api_client" not in st.session_state:
    st.session_state["api_client"] = None

if "user" not in st.session_state:
    st.session_state["user"] = None

if "page" not in st.session_state:
    st.session_state["page"] = "User"

# ---------------------------------------------------------
# Login Screen
# ---------------------------------------------------------
if not st.session_state["authenticated"]:
    st.title("🤖 AI Identity & Access Gateway")
    st.subheader("🔐 Login")

    login_type = st.radio(
        "Login as",
        ["User", "Admin"],
        horizontal=True,
    )

    credential_label = "API Key" if login_type == "User" else "Admin Key"
    credential = st.text_input(
        credential_label,
        type="password",
        placeholder=f"Enter your {credential_label}",
    )

    login = st.button(
        "🔐 Login",
        type="primary",
        use_container_width=True,
    )

    if login:
        if not credential.strip():
            st.warning(f"Please enter your {credential_label}.")
        else:
            try:
                with st.spinner("Authenticating..."):
                    if login_type == "User":
                        client, user = authenticate_user(BASE_URL, credential.strip())
                        st.session_state["authenticated"] = True
                        st.session_state["login_type"] = "user"
                        st.session_state["api_client"] = client
                        st.session_state["user"] = user
                        st.session_state["page"] = "User"
                        st.success(f"Welcome, {user['name']}!")
                    else:
                        client = authenticate_admin(BASE_URL, credential.strip())
                        st.session_state["authenticated"] = True
                        st.session_state["login_type"] = "admin"
                        st.session_state["api_client"] = client
                        st.session_state["user"] = {
                            "name": "Administrator",
                            "email": "System Administrator",
                            "type": "admin",
                            "is_active": True,
                        }
                        st.session_state["page"] = "Admin"
                        st.success("Admin authentication successful.")
                st.rerun()
            except Exception as exc:
                st.error(f"Authentication failed: {exc}")

    st.stop()

# ---------------------------------------------------------
# Authenticated User
# ---------------------------------------------------------
api_client = st.session_state["api_client"]
user = st.session_state["user"] or {}
user_role = user.get("type", "user").lower()
login_kind = st.session_state.get("login_type")

# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
with st.sidebar:
    st.title("🤖 Parikshak : AI Gateway")
    st.divider()

    st.write(f"👤 **{user.get('name', 'User')}**")
    if user.get("is_active", False):
        st.success("● Active")
    else:
        st.error("● Inactive")
    st.caption(user.get("email", ""))
    st.divider()

    st.write("### Navigation")

    if st.button("👤 User Dashboard", use_container_width=True):
        st.session_state["page"] = "User"
        st.rerun()

    # Policy documents use a normal user's API key. Show the page to all
    # authenticated API-key users; the backend enforces org membership/role.
    if login_kind == "user":
        if st.button("📚 Policy Documents", use_container_width=True):
            st.session_state["page"] = "Policy Documents"
            st.rerun()

    if user_role == "admin":
        if st.button("🛡️ Admin Dashboard", use_container_width=True):
            st.session_state["page"] = "Admin"
            st.rerun()

        if st.button("📊 Monitoring Dashboard", use_container_width=True):
            st.session_state["page"] = "Monitoring"
            st.rerun()

    st.divider()

    if st.button("🚪 Logout", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["api_client"] = None
        st.session_state["user"] = None
        st.session_state["login_type"] = None
        st.session_state["page"] = "User"
        st.rerun()

    st.divider()
    st.caption("AI Identity & Access Gateway")
    st.caption("Enterprise AI Security Platform")
    st.caption("with ❤️ Abhijeet")

# ---------------------------------------------------------
# Page Routing
# ---------------------------------------------------------
current_page = st.session_state.get("page", "User")

if current_page == "User":
    show_user_dashboard(api_client)
elif current_page == "Policy Documents":
    # Defensive check: platform-admin credentials are not user API keys.
    if login_kind != "user":
        st.warning("Log in with a user API key to access organization policy documents.")
        st.session_state["page"] = "Admin"
    else:
        show_policy_dashboard(api_client)
elif current_page == "Admin":
    show_admin_dashboard(api_client)
elif current_page == "Monitoring":
    show_monitoring_dashboard(api_client)
else:
    st.session_state["page"] = "User"
    st.rerun()
