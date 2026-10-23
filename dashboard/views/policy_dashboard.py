import streamlit as st

from services.api_client import APIClient, GatewayAPIError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def _human_size(size):
    if size is None:
        return "Unknown size"
    size = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def _handle_error(exc):
    if isinstance(exc, GatewayAPIError):
        st.error(f"HTTP {exc.status_code} · {exc.message}")
        if exc.code:
            st.caption(f"Error code: {exc.code}")
        if isinstance(exc.detail, dict):
            extra = {
                key: value for key, value in exc.detail.items()
                if key not in {"message", "code"}
            }
            if extra:
                with st.expander("Error details"):
                    st.json(extra)
    else:
        st.error(f"Request failed: {exc}")


def _status_label(document):
    status = str(document.get("status", "unknown")).replace("_", " ").title()
    return status


def _render_document(document, organization_id, api_client):
    document_id = document.get("id")
    title = document.get("title") or f"Policy document {document_id}"
    status = _status_label(document)
    versions = document.get("versions") or []
    with st.expander(f"{title} · {status} · Document #{document_id}", expanded=False):
        details_col1, details_col2, details_col3 = st.columns(3)
        details_col1.metric("Document ID", document_id if document_id is not None else "—")
        details_col2.metric("Versions", len(versions))
        active_version = next((v for v in versions if v.get("is_active")), None)
        details_col3.metric(
            "Active version",
            f"v{active_version.get('version_number')}" if active_version else "None",
        )
        st.caption(f"Organization: {organization_id} · Scope: {document.get('scope', 'organization')}")
        if document.get("created_at"):
            st.caption(f"Created: {document['created_at']}")

        st.markdown("**Version history**")
        if not versions:
            st.info("This document has no versions yet.")
        for version in versions:
            version_id = version.get("id")
            version_num = version.get("version_number", "?")
            is_active = bool(version.get("is_active"))
            status_text = version.get("processing_status", "unknown")
            badge = " · ACTIVE" if is_active else ""
            st.write(f"**Version {version_num}**{badge}")
            st.caption(
                f"{version.get('original_filename', 'file')} · "
                f"{_human_size(version.get('file_size_bytes'))} · "
                f"Processing: {status_text}"
            )
            if version.get("sha256"):
                with st.expander(f"SHA-256 for version {version_num}"):
                    st.code(version["sha256"])

            action_cols = st.columns([1, 1, 3])
            can_activate = (
                not is_active
                and status_text == "ready"
                and document.get("status") != "archived"
            )
            with action_cols[0]:
                if st.button(
                    f"Activate v{version_num}",
                    key=f"activate_policy_{organization_id}_{document_id}_{version_id}",
                    disabled=not can_activate,
                    use_container_width=True,
                ):
                    try:
                        api_client.activate_policy_document_version(
                            organization_id, document_id, version_id
                        )
                        st.success(f"Version {version_num} activated.")
                        st.rerun()
                    except Exception as exc:
                        _handle_error(exc)
            with action_cols[1]:
                st.write("Active" if is_active else ("Ready" if status_text == "ready" else status_text.title()))
            st.divider()

        if document.get("status") != "archived":
            st.markdown("**Upload a new version**")
            new_file = st.file_uploader(
                "Choose an updated PDF or DOCX",
                type=["pdf", "docx"],
                key=f"policy_version_file_{organization_id}_{document_id}",
                help="Maximum size: 10 MiB. A new version is inactive until activated.",
            )
            if new_file is not None:
                st.caption(f"Selected: {new_file.name} · {_human_size(new_file.size)}")
            if st.button(
                "Upload new version",
                key=f"upload_policy_version_{organization_id}_{document_id}",
                disabled=new_file is None,
                use_container_width=False,
            ):
                if new_file.size > MAX_UPLOAD_BYTES:
                    st.error("The file exceeds the 10 MiB upload limit.")
                else:
                    try:
                        with st.spinner("Uploading and processing the new version..."):
                            api_client.upload_policy_document_version(
                                organization_id=organization_id,
                                document_id=document_id,
                                file_name=new_file.name,
                                file_bytes=new_file.getvalue(),
                                content_type=("application/pdf" if new_file.name.lower().endswith(".pdf") else DOCX_CONTENT_TYPE),
                            )
                        st.success("New version uploaded. Activate it after verifying the version details.")
                        st.rerun()
                    except Exception as exc:
                        _handle_error(exc)

            if status != "Archived":
                confirm_archive = st.checkbox(
                    "I understand archiving disables retrieval for this document.",
                    key=f"confirm_archive_{organization_id}_{document_id}",
                )
                if st.button(
                    "Archive document",
                    type="secondary",
                    key=f"archive_policy_{organization_id}_{document_id}",
                    disabled=not confirm_archive,
                ):
                    try:
                        api_client.archive_policy_document(organization_id, document_id)
                        st.success("Document archived. Its history has been retained.")
                        st.rerun()
                    except Exception as exc:
                        _handle_error(exc)


def show_policy_dashboard(api_client: APIClient):
    """Separate organization policy upload and lifecycle dashboard."""
    user = st.session_state.get("user") or {}
    st.title("Policy Documents")
    st.caption(
        "Upload and manage organization-specific policy documents for later RAG retrieval. "
        "PDF and DOCX are supported; maximum upload size is 10 MiB."
    )

    # This is a display/filter choice, not an authorization boundary. The API
    # verifies the caller's membership, role, and team/organization relationship.
    suggested_org_id = st.session_state.get("organization_id", 2)
    try:
        suggested_org_id = int(suggested_org_id)
    except (TypeError, ValueError):
        suggested_org_id = 2
    org_key = f"policy_dashboard_org_id_{user.get('principal_id', 'session')}"
    organization_id = st.number_input(
        "Organization ID",
        min_value=1,
        value=suggested_org_id,
        step=1,
        key=org_key,
        help="The gateway verifies that your authenticated user belongs to this organization.",
    )
    organization_id = int(organization_id)

    st.info(
        "Uploading, activating, archiving, and creating versions require an active "
        "org_admin membership. org_viewer users can list and inspect documents only. "
        "Permissions are enforced by the gateway, not by this UI."
    )

    upload_tab, library_tab = st.tabs(["Upload policy", "Policy library"])

    with upload_tab:
        st.subheader("Upload a policy document")
        title = st.text_input(
            "Document title",
            placeholder="e.g. CSP Security and AI Usage Policy",
            key=f"policy_upload_title_{organization_id}",
        )
        uploaded_file = st.file_uploader(
            "Policy file",
            type=["pdf", "docx"],
            key=f"policy_upload_file_{organization_id}",
            help="PDF must contain selectable text. Scanned PDFs need OCR, which is not enabled.",
        )
        if uploaded_file is not None:
            col1, col2, col3 = st.columns(3)
            col1.metric("File", uploaded_file.name)
            col2.metric("Size", _human_size(uploaded_file.size))
            col3.metric("Format", uploaded_file.name.rsplit(".", 1)[-1].upper())
            if uploaded_file.size > MAX_UPLOAD_BYTES:
                st.error("The selected file exceeds the 10 MiB limit. Choose a smaller file.")

        st.caption(
            "New documents are uploaded as drafts. Review the extracted document and version "
            "metadata in the library, then activate the ready version to include it in RAG retrieval."
        )
        upload_disabled = (
            uploaded_file is None
            or not title.strip()
            or (uploaded_file is not None and uploaded_file.size > MAX_UPLOAD_BYTES)
        )
        if st.button(
            "Upload policy",
            type="primary",
            disabled=upload_disabled,
            key=f"policy_upload_submit_{organization_id}",
            use_container_width=True,
        ):
            try:
                extension = uploaded_file.name.lower().rsplit(".", 1)[-1]
                content_type = "application/pdf" if extension == "pdf" else DOCX_CONTENT_TYPE
                with st.spinner("Uploading and extracting text..."):
                    result = api_client.upload_policy_document(
                        organization_id=organization_id,
                        title=title.strip(),
                        file_name=uploaded_file.name,
                        file_bytes=uploaded_file.getvalue(),
                        content_type=content_type,
                    )
                # Show a compact, user-friendly summary instead of dumping
                # the entire API response JSON into the dashboard.
                document_id = result.get("id", "—")
                display_title = result.get("title") or title.strip()
                document_status = str(result.get("status", "draft")).replace("_", " ").title()
                versions = result.get("versions") or []
                latest_version = max(
                    versions,
                    key=lambda item: item.get("version_number", 0),
                    default={},
                )
                version_number = latest_version.get("version_number", "—")
                processing_status = str(
                    latest_version.get("processing_status", "unknown")
                ).replace("_", " ").title()

                st.success(f"{display_title} was uploaded successfully.")
                st.markdown("#### Upload summary")
                summary_cols = st.columns(3)
                summary_cols[0].metric("Document ID", document_id)
                summary_cols[1].metric("Document status", document_status)
                summary_cols[2].metric(
                    "Latest version",
                    f"v{version_number}" if version_number != "—" else "—",
                )
                st.markdown(
                    f"**File:** {uploaded_file.name}  \n"
                    f"**Processing:** {processing_status}"
                )
                if str(latest_version.get("processing_status", "")).lower() == "ready":
                    st.info(
                        "Next step: open the **Policy library** tab and activate this version "
                        "when you're ready to include it in RAG retrieval."
                    )
                else:
                    st.warning(
                        "The file was uploaded, but processing is not marked ready yet. "
                        "Refresh the Policy library and check the version status before activation."
                    )
            except Exception as exc:
                _handle_error(exc)

    with library_tab:
        top_col, refresh_col = st.columns([5, 1])
        with top_col:
            st.subheader("Organization policy library")
        with refresh_col:
            refresh = st.button("Refresh", key=f"refresh_policy_library_{organization_id}")

        try:
            with st.spinner("Loading organization policy documents..."):
                documents = api_client.get_policy_documents(organization_id)
            if not documents:
                st.info("No policy documents found for this organization yet. Upload one in the Upload policy tab.")
            else:
                st.caption(f"{len(documents)} document(s) in organization {organization_id}.")
                for document in documents:
                    _render_document(document, organization_id, api_client)
        except Exception as exc:
            _handle_error(exc)

    st.caption(f"Signed in as {user.get('name', 'User')} · Organization ID {organization_id}")
