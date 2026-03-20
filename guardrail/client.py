"""
guardrail — Official Python SDK for the Guardrail API.

Requires: Python 3.9+, httpx>=0.27
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Union
import httpx


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ApiError(Exception):
    """Raised when the Guardrail API returns a non-2xx response."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        request_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.request_id = request_id

    def __repr__(self) -> str:
        return f"ApiError(status={self.status}, code={self.code!r}, message={str(self)!r})"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class GuardrailClient:
    """
    Sync HTTP client for the Guardrail API.

    Parameters
    ----------
    base_url:
        Base URL of the API, e.g. ``https://api.code.aitrafficlight.com``.
    token:
        Default Bearer token (JWT or ``gr_live_…`` API key). Can be overridden
        per-call or updated via :meth:`set_token`.
    timeout:
        Request timeout in seconds (default: 30).
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._client = httpx.Client(timeout=timeout)

    def set_token(self, token: Optional[str]) -> None:
        """Update the default bearer token for subsequent requests."""
        self._token = token

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "GuardrailClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: Optional[str] = None,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        effective_token = token if token is not None else self._token
        hdrs: Dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
        if effective_token:
            hdrs["Authorization"] = f"Bearer {effective_token}"
        if headers:
            hdrs.update(headers)

        response = self._client.request(
            method,
            f"{self._base_url}{path}",
            headers=hdrs,
            json=body,
        )

        try:
            data = response.json()
        except Exception:
            data = {}

        if not response.is_success:
            code = data.get("code") or data.get("error") or "UNKNOWN"
            message = data.get("message") or response.reason_phrase
            raise ApiError(
                status=response.status_code,
                code=code,
                message=message,
                request_id=data.get("requestId"),
            )

        return data

    # ==================================================================
    # Health
    # ==================================================================

    def health(self) -> Dict[str, Any]:
        """GET /v2/health — system health check."""
        return self._request("GET", "/v2/health")

    # ==================================================================
    # Auth
    # ==================================================================

    def onboard(
        self,
        name: str,
        email: str,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /v2/onboard — register a new user account."""
        body: Dict[str, Any] = {"name": name, "email": email}
        if company:
            body["company"] = company
        return self._request("POST", "/v2/onboard", body=body)

    def request_magic_link(self, email: str) -> Dict[str, Any]:
        """POST /v2/auth/magic-link — request a sign-in email."""
        return self._request("POST", "/v2/auth/magic-link", body={"email": email})

    def get_login_url(self) -> Dict[str, Any]:
        """GET /v2/auth/login-url — get the Keycloak PKCE login URL."""
        return self._request("GET", "/v2/auth/login-url")

    def exchange_auth_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /v2/auth/exchange-code — exchange a KC auth code for JWTs."""
        body: Dict[str, Any] = {"code": code, "redirect_uri": redirect_uri}
        if code_verifier:
            body["code_verifier"] = code_verifier
        return self._request("POST", "/v2/auth/exchange-code", body=body)

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """POST /v2/auth/refresh — refresh an access token."""
        return self._request("POST", "/v2/auth/refresh", body={"refresh_token": refresh_token})

    # ==================================================================
    # Device Flow (CLI / MCP login)
    # ==================================================================

    def device_authorize(self, scope: str = "openid email profile") -> Dict[str, Any]:
        """POST /v2/device/authorize — start a device authorization flow."""
        return self._request("POST", "/v2/device/authorize", body={"scope": scope})

    def device_token(self, device_code: str) -> Dict[str, Any]:
        """POST /v2/device/token — poll for device flow completion."""
        return self._request("POST", "/v2/device/token", body={"device_code": device_code})

    # ==================================================================
    # User / Account
    # ==================================================================

    def me(self, token: Optional[str] = None) -> Dict[str, Any]:
        """GET /v2/me — current user info."""
        return self._request("GET", "/v2/me", token=token)

    def update_profile(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """PATCH /v2/me — update display name / profile fields."""
        body: Dict[str, Any] = {}
        if first_name is not None:
            body["firstName"] = first_name
        if last_name is not None:
            body["lastName"] = last_name
        return self._request("PATCH", "/v2/me", token=token, body=body)

    def save_github_token(
        self,
        github_token: Optional[str],
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """PATCH /v2/me/github-token — store a PAT for GitHub scans."""
        return self._request("PATCH", "/v2/me/github-token", token=token, body={"githubToken": github_token})

    def get_github_connect_url(self, token: Optional[str] = None) -> Dict[str, Any]:
        """GET /v2/github/connect — get the GitHub OAuth authorization URL."""
        return self._request("GET", "/v2/github/connect", token=token)

    def fetch_github_token(self, token: Optional[str] = None) -> Dict[str, Any]:
        """GET /v2/github/token — fetch the saved GitHub token after OAuth callback."""
        return self._request("GET", "/v2/github/token", token=token)

    def usage(self, token: Optional[str] = None) -> Dict[str, Any]:
        """GET /v2/usage — scan usage for the current billing period."""
        return self._request("GET", "/v2/usage", token=token)

    # ==================================================================
    # Pricing
    # ==================================================================

    def get_pricing(self) -> Dict[str, Any]:
        """GET /v2/pricing — tier pricing and metadata (public)."""
        return self._request("GET", "/v2/pricing")

    # ==================================================================
    # Billing
    # ==================================================================

    def get_subscription(self, token: Optional[str] = None) -> Dict[str, Any]:
        """GET /v2/billing/subscription — live subscription state."""
        return self._request("GET", "/v2/billing/subscription", token=token)

    def create_checkout(
        self,
        tier: str,
        interval: Literal["month", "year"] = "month",
        embedded: bool = True,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /v2/billing/checkout — create an embedded checkout session for an authenticated user."""
        return self._request(
            "POST", "/v2/billing/checkout",
            token=token,
            body={"tier": tier, "interval": interval, "embedded": embedded},
        )

    def switch_active_subscription(self, subscription_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """POST /v2/billing/subscription/active — switch active subscription."""
        return self._request(
            "POST", "/v2/billing/subscription/active",
            token=token, body={"subscriptionId": subscription_id},
        )

    def get_billing_portal(
        self,
        return_url: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /v2/billing/portal — Stripe customer portal URL."""
        qs = f"?return_url={httpx.URL(return_url)}" if return_url else ""
        return self._request("GET", f"/v2/billing/portal{qs}", token=token)

    def get_downgrade_portal(self, return_url: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """POST /v2/billing/downgrade — get Stripe portal URL for mid-cycle plan changes."""
        qs = f"?return_url={httpx.URL(return_url)}" if return_url else ""
        return self._request("POST", f"/v2/billing/downgrade{qs}", token=token, body={})

    def cancel_subscription(self, token: Optional[str] = None) -> Dict[str, Any]:
        """POST /v2/billing/cancel — cancel subscription at period end."""
        return self._request("POST", "/v2/billing/cancel", token=token, body={})

    def cancel_subscription_immediately(self, token: Optional[str] = None) -> Dict[str, Any]:
        """POST /v2/billing/cancel/immediate — immediate cancel (test keys only)."""
        return self._request("POST", "/v2/billing/cancel/immediate", token=token, body={})

    def sync_subscription(self, token: Optional[str] = None) -> Dict[str, Any]:
        """POST /v2/billing/sync — reconcile Stripe subscription state."""
        return self._request("POST", "/v2/billing/sync", token=token, body={})

    # ------------------------------------------------------------------
    # Guest Billing (public — no auth required)
    # ------------------------------------------------------------------

    def guest_checkout(
        self,
        email: str,
        tier: Optional[str] = None,
        price_id: Optional[str] = None,
        interval: Literal["month", "year"] = "month",
        name: Optional[str] = None,
        org_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST /v2/billing/guest-checkout — start a Stripe Elements checkout session.

        Returns ``clientSecret``, ``subscriptionId``, ``intentType``, and a
        signed ``checkoutToken`` that must be passed to :meth:`apply_coupon`.
        """
        body: Dict[str, Any] = {"email": email, "interval": interval}
        if tier:
            body["tier"] = tier
        if price_id:
            body["priceId"] = price_id
        if name:
            body["name"] = name
        if org_name:
            body["orgName"] = org_name
        return self._request("POST", "/v2/billing/guest-checkout", body=body)

    def guest_provision(
        self,
        id: str,
        id_type: Literal["subscriptionId", "sessionId"] = "subscriptionId",
        org_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /v2/billing/guest-provision — provision a Guardrail account after payment."""
        body: Dict[str, Any] = {id_type: id}
        if org_name:
            body["orgName"] = org_name
        return self._request("POST", "/v2/billing/guest-provision", body=body)

    def apply_coupon(
        self,
        subscription_id: str,
        promotion_code: str,
        checkout_token: str,
    ) -> Dict[str, Any]:
        """
        POST /v2/billing/apply-coupon — apply a Stripe promotion code.

        Parameters
        ----------
        subscription_id:
            Stripe subscription ID (``sub_…``) from :meth:`guest_checkout`.
        promotion_code:
            Human-readable promo code string, e.g. ``"SUMMER40"``.
        checkout_token:
            HMAC-signed token returned by :meth:`guest_checkout`.
            Expires after 6 hours; re-run checkout to obtain a fresh one.
        """
        return self._request(
            "POST",
            "/v2/billing/apply-coupon",
            body={
                "subscriptionId": subscription_id,
                "promotionCode": promotion_code,
                "checkoutToken": checkout_token,
            },
        )

    # ==================================================================
    # API Keys
    # ==================================================================

    def list_keys(self, token: Optional[str] = None) -> Dict[str, Any]:
        """GET /v2/keys — list API keys (masked prefixes only)."""
        return self._request("GET", "/v2/keys", token=token)

    def create_key(
        self,
        name: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /v2/keys — generate a new API key (full key shown once)."""
        body: Dict[str, Any] = {}
        if name:
            body["name"] = name
        if expires_in_days is not None:
            body["expiresInDays"] = expires_in_days
        return self._request("POST", "/v2/keys", token=token, body=body)

    def rotate_key(self, key_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """POST /v2/keys/:id/rotate — rotate an existing API key."""
        return self._request("POST", f"/v2/keys/{key_id}/rotate", token=token, body={})

    def revoke_key(self, key_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """DELETE /v2/keys/:id — permanently revoke an API key."""
        return self._request("DELETE", f"/v2/keys/{key_id}", token=token)

    # ==================================================================
    # Scans
    # ==================================================================

    def scan(
        self,
        target: str,
        type: str,
        depth: Literal["quick", "standard", "deep"] = "standard",
        options: Optional[Dict[str, bool]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /v2/scan — initiate a new scan."""
        body: Dict[str, Any] = {"target": target, "type": type, "depth": depth}
        if options:
            body["options"] = options
        return self._request("POST", "/v2/scan", token=token, body=body, headers=extra_headers)

    def get_scan(self, scan_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """GET /v2/scans/:id — fetch scan status / result."""
        return self._request("GET", f"/v2/scans/{scan_id}", token=token)

    def get_scan_history(self, limit: int = 20, token: Optional[str] = None) -> Dict[str, Any]:
        """GET /v2/scans/history — paginated scan history."""
        return self._request("GET", f"/v2/scans/history?limit={limit}", token=token)

    # ==================================================================
    # Organizations
    # ==================================================================

    def list_organizations(self, token: Optional[str] = None) -> Dict[str, Any]:
        """GET /v2/organizations — list orgs the caller belongs to."""
        return self._request("GET", "/v2/organizations", token=token)

    def get_organization(self, org_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """GET /v2/organizations/:id — org details, members, and seat quota."""
        return self._request("GET", f"/v2/organizations/{org_id}", token=token)

    def create_organization(
        self,
        name: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /v2/organizations — create a new organization."""
        body: Dict[str, Any] = {"name": name}
        if display_name:
            body["displayName"] = display_name
        if description:
            body["description"] = description
        return self._request("POST", "/v2/organizations", token=token, body=body)

    def add_org_member(
        self,
        org_id: str,
        email: Optional[str] = None,
        user_id: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /v2/organizations/:id/members — add a member by email or userId."""
        body: Dict[str, Any] = {}
        if email:
            body["email"] = email
        if user_id:
            body["userId"] = user_id
        return self._request("POST", f"/v2/organizations/{org_id}/members", token=token, body=body)

    def remove_org_member(
        self, org_id: str, user_id: str, token: Optional[str] = None
    ) -> Dict[str, Any]:
        """DELETE /v2/organizations/:id/members/:userId — remove a member."""
        return self._request(
            "DELETE", f"/v2/organizations/{org_id}/members/{user_id}", token=token
        )

    def get_org_subscription(
        self, org_id: str, token: Optional[str] = None
    ) -> Dict[str, Any]:
        """GET /v2/organizations/:id/subscription — org subscription details."""
        return self._request("GET", f"/v2/organizations/{org_id}/subscription", token=token)

    def link_org_subscription(self, org_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """POST /v2/organizations/:id/subscription — link caller's subscription to an org."""
        return self._request("POST", f"/v2/organizations/{org_id}/subscription", token=token, body={})

    def invite_org_member(
        self,
        org_id: str,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /v2/organizations/:id/invite — invite a user by email."""
        body: Dict[str, Any] = {"email": email}
        if first_name:
            body["firstName"] = first_name
        if last_name:
            body["lastName"] = last_name
        if redirect_uri:
            body["redirectUri"] = redirect_uri
        return self._request("POST", f"/v2/organizations/{org_id}/invite", token=token, body=body)

    def delete_organization(self, org_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """DELETE /v2/organizations/:id — delete an organization."""
        return self._request("DELETE", f"/v2/organizations/{org_id}", token=token)


