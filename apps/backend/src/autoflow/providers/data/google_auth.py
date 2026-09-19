"""Google authorization for the Sheets provider.

Two authorization shapes are supported: an installed-app OAuth refresh token
(the desktop PKCE exchange is performed by the desktop host) and a service
account private key. Both only ever produce a short lived access token; the
secret material lives in the operating system credential store.
"""

from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
READONLY_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
GRANTED_SCOPE = f"openid email {SHEETS_SCOPE}"


class GoogleAuthError(RuntimeError):
    """A Google authorization failure with a stable machine readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


class TokenTransport(Protocol):
    def post_form(self, url: str, data: dict[str, str]) -> dict[str, Any]: ...


class HttpxTokenTransport:
    """The only component that talks to the Google token endpoint."""

    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    def post_form(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    url, data=data, headers={"Accept": "application/json"}
                )
        except httpx.HTTPError as error:
            raise GoogleAuthError(
                "GOOGLE_UNREACHABLE", "Google 授权服务当前不可达。"
            ) from error
        if response.status_code >= 400:
            raise GoogleAuthError(
                "GOOGLE_AUTH_REJECTED",
                f"Google 拒绝本次授权请求（HTTP {response.status_code}）。",
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise GoogleAuthError(
                "GOOGLE_AUTH_INVALID", "Google 返回了无法解析的授权响应。"
            ) from error
        if not isinstance(payload, dict):
            raise GoogleAuthError(
                "GOOGLE_AUTH_INVALID", "Google 返回了无法解析的授权响应。"
            )
        return payload


@dataclass(frozen=True)
class GoogleCredential:
    """Secret material for one Google connection."""

    auth_method: str
    account_label: str
    granted_scope: str
    refresh_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    service_account: dict[str, Any] | None = None

    @property
    def writable(self) -> bool:
        return SHEETS_SCOPE in self.granted_scope.split()

    def to_secret(self) -> bytes:
        return json.dumps(self._fields(), separators=(",", ":")).encode("utf-8")

    def _fields(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "authMethod": self.auth_method,
            "accountLabel": self.account_label,
            "grantedScope": self.granted_scope,
        }
        if self.auth_method == "oauth":
            payload.update(
                {
                    "refreshToken": self.refresh_token,
                    "clientId": self.client_id,
                    "clientSecret": self.client_secret,
                }
            )
        else:
            payload["serviceAccount"] = self.service_account
        return payload

    @classmethod
    def from_secret(cls, raw: bytes) -> GoogleCredential:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise GoogleAuthError(
                "GOOGLE_CREDENTIAL_INVALID", "已保存的 Google 凭据无法解析。"
            ) from error
        if not isinstance(payload, dict):
            raise GoogleAuthError(
                "GOOGLE_CREDENTIAL_INVALID", "已保存的 Google 凭据无法解析。"
            )
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> GoogleCredential:
        method = payload.get("authMethod")
        label = payload.get("accountLabel")
        if not isinstance(label, str) or not label.strip():
            raise GoogleAuthError("GOOGLE_CREDENTIAL_INVALID", "缺少账号名称。")
        if method == "oauth":
            refresh, client_id, client_secret = (
                payload.get("refreshToken"),
                payload.get("clientId"),
                payload.get("clientSecret"),
            )
            if not all(
                isinstance(value, str) and value
                for value in (refresh, client_id, client_secret)
            ):
                raise GoogleAuthError(
                    "GOOGLE_CREDENTIAL_INVALID", "OAuth 凭据不完整，请重新授权。"
                )
            return cls(
                "oauth",
                label.strip(),
                str(payload.get("grantedScope") or READONLY_SHEETS_SCOPE),
                refresh_token=str(refresh),
                client_id=str(client_id),
                client_secret=str(client_secret),
            )
        if method == "service_account":
            account = _service_account(payload.get("serviceAccount"))
            email = account.get("client_email")
            return cls(
                "service_account",
                label.strip() or str(email or "服务账号"),
                str(payload.get("grantedScope") or SHEETS_SCOPE),
                service_account=account,
            )
        raise GoogleAuthError("GOOGLE_CREDENTIAL_INVALID", "授权方式不受支持。")


def _service_account(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError as error:
            raise GoogleAuthError(
                "GOOGLE_CREDENTIAL_INVALID", "服务账号密钥不是合法 JSON。"
            ) from error
    if not isinstance(value, dict):
        raise GoogleAuthError("GOOGLE_CREDENTIAL_INVALID", "缺少服务账号密钥。")
    account: dict[str, Any] = {
        "client_email": value.get("client_email"),
        "private_key": value.get("private_key"),
        "token_uri": value.get("token_uri") or TOKEN_URL,
        "project_id": value.get("project_id"),
    }
    if not isinstance(account["client_email"], str) or not isinstance(
        account["private_key"], str
    ):
        raise GoogleAuthError(
            "GOOGLE_CREDENTIAL_INVALID", "服务账号密钥缺少 client_email 或 private_key。"
        )
    if account["token_uri"] != TOKEN_URL:
        raise GoogleAuthError(
            "GOOGLE_CREDENTIAL_INVALID", "服务账号令牌地址不被信任。"
        )
    return account


def access_token(
    credential: GoogleCredential, transport: TokenTransport, now: float | None = None
) -> str:
    """Exchange the stored secret for a fresh access token."""
    issued = time.time() if now is None else now
    if credential.auth_method == "oauth":
        assert credential.refresh_token and credential.client_id is not None
        assert credential.client_secret is not None
        payload = transport.post_form(
            TOKEN_URL,
            {
                "client_id": credential.client_id,
                "client_secret": credential.client_secret,
                "refresh_token": credential.refresh_token,
                "grant_type": "refresh_token",
            },
        )
    else:
        assert credential.service_account is not None
        payload = transport.post_form(
            TOKEN_URL,
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion(
                    credential.service_account, issued, credential.granted_scope
                ),
            },
        )
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise GoogleAuthError(
            "GOOGLE_AUTH_REJECTED", "Google 未返回访问令牌，请重新授权。"
        )
    return token


def assertion(
    service_account: dict[str, Any], issued: float, scope: str = SHEETS_SCOPE
) -> str:
    """Build the signed JWT bearer assertion for a service account."""
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": service_account["client_email"],
        "scope": scope,
        "aud": TOKEN_URL,
        "iat": int(issued),
        "exp": int(issued) + 3600,
    }
    signing_input = (
        f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}."
        f"{_b64url(json.dumps(claims, separators=(',', ':')).encode())}"
    )
    try:
        key = serialization.load_pem_private_key(
            str(service_account["private_key"]).encode(), password=None
        )
        if not isinstance(key, rsa.RSAPrivateKey):
            raise GoogleAuthError(
                "GOOGLE_CREDENTIAL_INVALID", "服务账号私钥必须是 RSA 私钥。"
            )
        signature = key.sign(
            signing_input.encode(), padding.PKCS1v15(), hashes.SHA256()
        )
    except (ValueError, TypeError, AttributeError) as error:
        raise GoogleAuthError(
            "GOOGLE_CREDENTIAL_INVALID", "服务账号私钥无法用于签名。"
        ) from error
    return f"{signing_input}.{_b64url(signature)}"


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = _b64url(sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def authorization_url(
    client_id: str, redirect_uri: str, challenge: str, state: str
) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": GRANTED_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    return f"{AUTHORIZATION_URL}?{query}"


def exchange_code(
    client_id: str,
    client_secret: str,
    code: str,
    verifier: str,
    redirect_uri: str,
    transport: TokenTransport,
) -> dict[str, Any]:
    payload = transport.post_form(
        TOKEN_URL,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if not payload.get("refresh_token"):
        raise GoogleAuthError(
            "GOOGLE_AUTH_REJECTED", "授权未返回长期凭据，请重新授权并确认离线访问。"
        )
    return payload


def revoke(token: str, transport: TokenTransport) -> None:
    """Revoke a refresh token; the local copy is removed regardless."""
    try:
        transport.post_form(REVOKE_URL, {"token": token})
    except GoogleAuthError:
        return
