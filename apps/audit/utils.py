"""
Utility helpers for the Audit module.

Design principles:
- Pure helpers only (no DB writes)
- Safe for reuse in services, permissions, views, middleware
- No circular dependencies
"""

import json
import hashlib
from typing import Any, Dict, Optional
from django.utils.timezone import now
from django.http import HttpRequest


# ======================================================
# JSON / SERIALIZATION
# ======================================================

def json_safe(value: Any) -> Any:
    """
    Convert any value into JSON-safe representation.
    """
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]

    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if hasattr(value, "pk"):
        return value.pk

    return str(value)


def stable_json_dumps(data: Dict[str, Any]) -> str:
    """
    Deterministic JSON dump (used for hashing).
    """
    return json.dumps(
        json_safe(data),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


# ======================================================
# HASHING / CRYPTO
# ======================================================

def sha256_hash(value: str) -> str:
    """
    Compute SHA-256 hash.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def chained_hash(previous_hash: str, payload: Dict[str, Any]) -> str:
    """
    Compute chained audit hash.
    """
    raw = f"{previous_hash or ''}{stable_json_dumps(payload)}"
    return sha256_hash(raw)


# ======================================================
# REQUEST / CONTEXT EXTRACTION
# ======================================================

def get_client_ip(request: HttpRequest) -> Optional[str]:
    """
    Resolve client IP safely.
    """
    if not request:
        return None

    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def get_device_id(request: HttpRequest) -> Optional[str]:
    """
    Extract device identifier from headers.
    """
    if not request:
        return None
    return request.META.get("HTTP_X_DEVICE_ID")


def build_audit_context(request: Optional[HttpRequest]) -> Dict[str, Any]:
    """
    Build standardized audit context from request.
    """
    if not request:
        return {}

    user = getattr(request, "user", None)

    return {
        "user": user if getattr(user, "is_authenticated", False) else None,
        "branch": getattr(request, "branch", None)
                  or getattr(user, "current_branch", None),
        "device_id": get_device_id(request),
        "ip_address": get_client_ip(request),
        "start_time": getattr(request, "_audit_start_time", None) or now(),
    }


# ======================================================
# PERMISSION / ROLE HELPERS
# ======================================================

def user_has_any_role(user, roles) -> bool:
    """
    Check if user has any role from list.
    """
    if not user or not user.is_authenticated:
        return False

    for role in roles:
        if getattr(user, "has_role", lambda r: False)(role):
            return True

    return False


def is_audit_admin(user) -> bool:
    """
    Strong audit-level admin check.
    """
    return bool(
        user and user.is_authenticated and (
            user.is_superuser or
            getattr(user, "is_admin", lambda: False)()
        )
    )


# ======================================================
# SAFE DIFF / CHANGE UTILITIES
# ======================================================

def diff_dicts(
    before: Optional[Dict[str, Any]],
    after: Optional[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Compute field-level diff between two dictionaries.

    Returns:
    {
        "field_name": {"before": x, "after": y}
    }
    """
    before = before or {}
    after = after or {}

    diff = {}
    keys = set(before.keys()) | set(after.keys())

    for key in keys:
        if before.get(key) != after.get(key):
            diff[key] = {
                "before": before.get(key),
                "after": after.get(key),
            }

    return diff


def has_meaningful_change(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    """
    Check if there is any real change.
    """
    return bool(diff_dicts(before, after))


# ======================================================
# EXPORT / DISPLAY HELPERS
# ======================================================

def mask_sensitive_value(value: Any) -> str:
    """
    Mask sensitive values for UI/API output.
    """
    

    if value is None:
        return ""

    text = str(value)
    if len(text) <= 4:
        return "****"

    return f"{text[:2]}****{text[-2:]}"


def redact_sensitive_fields(
    data: Dict[str, Any],
    sensitive_fields=None,
) -> Dict[str, Any]:
    """
    Redact sensitive fields from payload.
    """
    sensitive_fields = sensitive_fields or {
        "password",
        "token",
        "secret",
        "api_key",
        "otp",
    }

    redacted = {}
    for key, value in data.items():
        if key.lower() in sensitive_fields:
            redacted[key] = mask_sensitive_value(value)
        else:
            redacted[key] = value

    return redacted


# ======================================================
# SAFETY GUARDS
# ======================================================

def ensure_immutable(instance):
    """
    Guard against mutation of audit records.
    """
    if hasattr(instance, "record_hash") and instance.pk:
        raise RuntimeError("Audit records are immutable")
