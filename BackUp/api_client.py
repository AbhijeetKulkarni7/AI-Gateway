import requests


class APIClient:
    def __init__(
        self,
        base_url="http://127.0.0.1:8000",
        api_key=None,
        admin_key=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.admin_key = admin_key

    # ============================================================
    # User Authentication
    # ============================================================

    def get_monitoring(self):
        response = requests.get(
            f"{self.base_url}/admin/monitoring",
            headers=self._admin_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _headers(self):
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    def get_current_user(self):
        response = requests.get(
            f"{self.base_url}/v1/whoami",
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    # ============================================================
    # User APIs
    # ============================================================

    def get_credit_balance(self):
        response = requests.get(
            f"{self.base_url}/v1/credits/balance",
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _raise_gateway_error(response):
        """Raise a readable error from the gateway's FastAPI response."""
        try:
            error_data = response.json()
            detail = error_data.get("detail", error_data)
            if isinstance(detail, dict):
                error_code = detail.get("code", "UNKNOWN_ERROR")
                error_message = detail.get("message", "Request failed")
                raise Exception(f"{error_code}: {error_message}")
            raise Exception(str(detail))
        except ValueError:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    def send_chat(self, message, provider="huggingface"):
        """Legacy chat endpoint; retained for existing integrations."""
        response = requests.post(
            f"{self.base_url}/v1/chat",
            headers=self._headers(),
            json={"message": message, "provider": provider},
            timeout=120,
        )
        if response.status_code >= 400:
            self._raise_gateway_error(response)
        return response.json()

    def send_completion(self, messages, model="company-chat-azure"):
        """Call the OpenAI-compatible gateway chat-completions endpoint."""
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            headers=self._headers(),
            json={
                "model": model,
                "messages": messages,
                "stream": False,
            },
            timeout=120,
        )
        if response.status_code >= 400:
            self._raise_gateway_error(response)
        return response.json()

    # ============================================================
    # Admin Authentication
    # ============================================================

    def _admin_headers(self):
        if not self.admin_key:
            return {}
        return {"X-Admin-Key": self.admin_key}

    def validate_admin(self):
        response = requests.get(
            f"{self.base_url}/admin/credit-requests",
            headers=self._admin_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    # ============================================================
    # Admin - Principals / Users
    # ============================================================

    def get_principals(self, page=1, page_size=10, search=None):
        params = {"page": page, "page_size": page_size}
        if search:
            params["search"] = search
        response = requests.get(
            f"{self.base_url}/admin/principals",
            headers=self._admin_headers(),
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def create_principal(
        self,
        team_id,
        name,
        principal_type="user",
        email=None,
        initial_credits=200.0,
    ):
        params = {
            "team_id": team_id,
            "name": name,
            "principal_type": principal_type,
            "initial_credits": initial_credits,
        }
        if email:
            params["email"] = email
        response = requests.post(
            f"{self.base_url}/admin/principals",
            headers=self._admin_headers(),
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    # ============================================================
    # Admin - Teams
    # ============================================================

    def get_teams(self):
        response = requests.get(
            f"{self.base_url}/admin/teams",
            headers=self._admin_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def create_team(self, name):
        response = requests.post(
            f"{self.base_url}/admin/teams",
            headers=self._admin_headers(),
            params={"name": name},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def delete_team(self, team_id):
        response = requests.delete(
            f"{self.base_url}/admin/teams/{team_id}",
            headers=self._admin_headers(),
            timeout=30,
        )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", "Unknown error")
            except ValueError:
                detail = response.text or "Unknown error"
            raise Exception(detail)
        return response.json()

    # ============================================================
    # Admin - Credit Requests
    # ============================================================

    def get_credit_requests(self):
        response = requests.get(
            f"{self.base_url}/admin/credit-requests",
            headers=self._admin_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def approve_credit_request(self, request_id, approved_amount=None):
        payload = {}
        if approved_amount is not None:
            payload["approved_amount"] = approved_amount
        response = requests.post(
            f"{self.base_url}/admin/credit-requests/{request_id}/approve",
            headers=self._admin_headers(),
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def reject_credit_request(self, request_id):
        response = requests.post(
            f"{self.base_url}/admin/credit-requests/{request_id}/reject",
            headers=self._admin_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    # ============================================================
    # Admin - API Keys
    # ============================================================

    def issue_api_key(self, principal_id):
        response = requests.post(
            f"{self.base_url}/admin/principals/{principal_id}/keys",
            headers=self._admin_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def revoke_api_key(self, key_id):
        response = requests.delete(
            f"{self.base_url}/admin/keys/{key_id}",
            headers=self._admin_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_usage(self):
        response = requests.get(
            f"{self.base_url}/admin/usage",
            headers=self._admin_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
