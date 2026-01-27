# # apps/audit/services.py

# import hashlib
# import json
# from django.forms.models import model_to_dict
# from django.utils import timezone
# from django.db import transaction
# from typing import Optional, Dict, Any, List

# from apps.audit.models import AuditLog


# # ======================================================
# # CONSTANTS
# # ======================================================

# _AUDIT_BEFORE_ATTR = "_audit_before"
# _AUDIT_CONTEXT_ATTR = "_audit_context"


# # ======================================================
# # SERIALIZATION HELPERS
# # ======================================================

# def _json_serialize(value) -> str:
#     """
#     Safely serialize any value into JSON string.
#     Used for hash computation.
#     """
#     return json.dumps(value, sort_keys=True, default=str)


# def safe_model_dict(instance) -> Optional[Dict[str, Any]]:
#     """
#     Convert a Django model instance into a JSON-safe dictionary.
#     Handles FK, M2M, datetime, and non-serializable fields.
#     """
#     if instance is None:
#         return None

#     data = model_to_dict(instance)

#     for field, value in data.items():
#         if hasattr(value, "pk"):
#             # ForeignKey / OneToOne
#             data[field] = value.pk
#         elif hasattr(value, "all"):
#             # ManyToMany
#             data[field] = list(value.all().values_list("pk", flat=True))
#         elif hasattr(value, "isoformat"):
#             # Date / DateTime
#             data[field] = value.isoformat()
#         elif isinstance(value, (dict, list, int, float, str, bool, type(None))):
#             pass
#         else:
#             data[field] = str(value)

#     return data


# # ======================================================
# # HASH CHAIN
# # ======================================================

# def compute_hash(previous_hash: str, payload: Dict[str, Any]) -> str:
#     """
#     Compute SHA-256 hash for audit chain.
#     """
#     raw = (previous_hash or "") + _json_serialize(payload)
#     return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# # ======================================================
# # SNAPSHOT (BEFORE STATE)
# # ======================================================

# def snapshot_before(instance) -> None:
#     """
#     Capture BEFORE state of an instance.
#     Call from pre_save / pre_delete signals.
#     """
#     if not instance.pk:
#         instance._audit_before = None
#         return

#     try:
#         old = instance.__class__.objects.get(pk=instance.pk)
#         instance._audit_before = safe_model_dict(old)
#     except instance.__class__.DoesNotExist:
#         instance._audit_before = None


# # ======================================================
# # AUDIT CONTEXT (REQUEST BINDING)
# # ======================================================

# def attach_audit_context(instance, request) -> None:
#     """
#     Attach request-related audit context to a model instance.
#     Call BEFORE saving the instance.
#     """
#     context = {
#         "user": getattr(request, "user", None),
#         "branch": getattr(request, "branch", None)
#                   or getattr(getattr(request, "user", None), "current_branch", None),
#         "device_id": request.META.get("HTTP_X_DEVICE_ID"),
#         "ip_address": request.META.get("REMOTE_ADDR"),
#         "start_time": getattr(request, "_audit_start_time", None),
#     }

#     instance._audit_context = context


# def _get_context(instance) -> Dict[str, Any]:
#     """
#     Extract audit context from instance.
#     """
#     return getattr(instance, _AUDIT_CONTEXT_ATTR, {})


# # ======================================================
# # CORE AUDIT LOGGER (IMMUTABLE)
# # ======================================================

# @transaction.atomic
# def log_action(
#     *,
#     instance,
#     action: str,
#     user=None,
#     branch=None,
#     device_id: Optional[str] = None,
#     ip_address: Optional[str] = None,
#     duration=None,
#     metadata: Optional[Dict[str, Any]] = None,
# ) -> None:
#     """
#     Persist an immutable audit log entry with hash chaining.
#     """

#     # ------------------------------------
#     # Resolve context (instance > params)
#     # ------------------------------------
#     context = _get_context(instance)

#     user = user or context.get("user")
#     branch = branch or context.get("branch")
#     device_id = device_id or context.get("device_id")
#     ip_address = ip_address or context.get("ip_address")

#     if not duration and context.get("start_time"):
#         duration = timezone.now() - context["start_time"]

#     # ------------------------------------
#     # Resolve BEFORE / AFTER
#     # ------------------------------------
#     before = getattr(instance, _AUDIT_BEFORE_ATTR, None)

#     if action.upper() == "DELETE":
#         after = None
#     else:
#         after = safe_model_dict(instance)

#     # ------------------------------------
#     # Hash chain
#     # ------------------------------------
#     last = (
#         AuditLog.objects
#         .select_for_update()
#         .order_by("-id")
#         .only("record_hash")
#         .first()
#     )

#     previous_hash = last.record_hash if last else ""

#     model_name = instance.__class__.__name__
#     object_id = str(instance.pk) if instance.pk else "NEW"

#     payload = {
#         "timestamp": timezone.now().isoformat(),
#         "branch_id": branch.id if branch else None,
#         "user_id": user.id if user else None,
#         "action": action.upper(),
#         "model": model_name,
#         "object_id": object_id,
#         "before": before,
#         "after": after,
#         "metadata": metadata or {},
#     }

#     record_hash = compute_hash(previous_hash, payload)

#     # ------------------------------------
#     # Create immutable log
#     # ------------------------------------
#     AuditLog.objects.create(
#         branch=branch,
#         user=user,
#         device_id=device_id,
#         ip_address=ip_address,
#         action=action.upper(),
#         model_name=model_name,
#         object_id=object_id,
#         before=before,
#         after=after,
#         previous_hash=previous_hash,
#         record_hash=record_hash,
#         duration=duration,
#     )

#     # ------------------------------------
#     # Cleanup snapshot
#     # ------------------------------------
#     if hasattr(instance, _AUDIT_BEFORE_ATTR):
#         delattr(instance, _AUDIT_BEFORE_ATTR)


# # ======================================================
# # CONVENIENCE WRAPPERS
# # ======================================================

# def log_create(instance, **kwargs):
#     log_action(instance=instance, action="CREATE", **kwargs)


# def log_update(instance, **kwargs):
#     log_action(instance=instance, action="UPDATE", **kwargs)


# def log_delete(instance, **kwargs):
#     log_action(instance=instance, action="DELETE", **kwargs)


# def log_view(instance, **kwargs):
#     log_action(instance=instance, action="VIEW", **kwargs)


# def log_approve(instance, **kwargs):
#     log_action(instance=instance, action="APPROVE", **kwargs)


# # ======================================================
# # BULK OPERATIONS
# # ======================================================

# @transaction.atomic
# def log_bulk_create(instances: List, **kwargs):
#     for instance in instances:
#         log_create(instance, **kwargs)


# @transaction.atomic
# def log_bulk_update(instances: List, **kwargs):
#     for instance in instances:
#         log_update(instance, **kwargs)


# # ======================================================
# # INTEGRITY VERIFICATION
# # ======================================================

# def verify_chain() -> List[Dict[str, Any]]:
#     """
#     Verify audit hash chain integrity.
#     Returns list of broken links.
#     """
#     broken = []
#     previous_hash = ""

#     logs = AuditLog.objects.order_by("id").only(
#         "id", "previous_hash", "record_hash", "timestamp"
#     )

#     for log in logs:
#         if log.previous_hash != previous_hash:
#             broken.append({
#                 "log_id": log.id,
#                 "expected_previous": previous_hash,
#                 "actual_previous": log.previous_hash,
#                 "timestamp": log.timestamp,
#             })

#         previous_hash = log.record_hash

#     return broken


# # ======================================================
# # QUERY HELPERS
# # ======================================================

# def get_audit_trail(model_name: str, object_id, limit: int = 100):
#     return AuditLog.objects.filter(
#         model_name=model_name,
#         object_id=str(object_id)
#     ).order_by("-timestamp")[:limit]


# def export_audit_logs(start_date, end_date, format: str = "json"):
#     logs = AuditLog.objects.filter(
#         timestamp__gte=start_date,
#         timestamp__lte=end_date
#     ).order_by("timestamp")

#     data = list(logs.values(
#         "id",
#         "timestamp",
#         "action",
#         "model_name",
#         "object_id",
#         "user__email",
#         "branch__name",
#         "device_id",
#         "ip_address",
#         "record_hash",
#     ))

#     if format == "csv":
#         import csv
#         from io import StringIO

#         output = StringIO()
#         writer = csv.DictWriter(output, fieldnames=data[0].keys() if data else [])
#         writer.writeheader()
#         writer.writerows(data)
#         return output.getvalue()

#     return json.dumps(data, indent=2, default=str)


# apps/audit/services.py

import hashlib
import json
from typing import Optional, Dict, Any, List, Iterable

from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone

from apps.audit.models import AuditLog


# ======================================================
# INTERNAL CONSTANTS (DO NOT TOUCH)
# ======================================================

AUDIT_BEFORE_ATTR = "_audit_before"
AUDIT_CONTEXT_ATTR = "_audit_context"

VALID_ACTIONS = {
    "CREATE",
    "UPDATE",
    "DELETE",
    "VIEW",
    "APPROVE",
    "REJECT",
    "LOGIN",
    "LOGOUT",
}


# ======================================================
# JSON / SERIALIZATION UTILITIES
# ======================================================

def json_dumps(value: Any) -> str:
    """
    Deterministic JSON serialization for hashing.
    """
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def serialize_model(instance) -> Optional[Dict[str, Any]]:
    """
    Convert Django model instance to a JSON-safe dict.
    FK -> pk
    M2M -> list[pk]
    Date/Datetime -> ISO
    """
    if instance is None:
        return None

    raw = model_to_dict(instance)
    data: Dict[str, Any] = {}

    for field, value in raw.items():
        if hasattr(value, "pk"):
            data[field] = value.pk
        elif hasattr(value, "all"):
            data[field] = list(value.all().values_list("pk", flat=True))
        elif hasattr(value, "isoformat"):
            data[field] = value.isoformat()
        elif isinstance(value, (dict, list, str, int, float, bool)) or value is None:
            data[field] = value
        else:
            data[field] = str(value)

    return data


# ======================================================
# HASH CHAIN
# ======================================================

def compute_record_hash(previous_hash: str, payload: Dict[str, Any]) -> str:
    """
    Compute SHA-256 audit hash.
    """
    raw = f"{previous_hash}{json_dumps(payload)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ======================================================
# SNAPSHOT HANDLING (PRE-SAVE)
# ======================================================

def snapshot_before(instance) -> None:
    """
    Capture BEFORE snapshot.
    Called from pre_save / pre_delete signal.
    """
    if not instance.pk:
        setattr(instance, AUDIT_BEFORE_ATTR, None)
        return

    try:
        old = instance.__class__.objects.get(pk=instance.pk)
        setattr(instance, AUDIT_BEFORE_ATTR, serialize_model(old))
    except instance.__class__.DoesNotExist:
        setattr(instance, AUDIT_BEFORE_ATTR, None)


# ======================================================
# REQUEST / CONTEXT BINDING
# ======================================================

def attach_audit_context(instance, request) -> None:
    """
    Bind request context to instance.
    """
    context = {
        "user": getattr(request, "user", None),
        "branch": (
            getattr(request, "branch", None)
            or getattr(getattr(request, "user", None), "current_branch", None)
        ),
        "device_id": request.META.get("HTTP_X_DEVICE_ID"),
        "ip_address": request.META.get("REMOTE_ADDR"),
        "start_time": getattr(request, "_audit_start_time", None),
    }
    setattr(instance, AUDIT_CONTEXT_ATTR, context)


def _extract_context(instance) -> Dict[str, Any]:
    return getattr(instance, AUDIT_CONTEXT_ATTR, {}) or {}


# ======================================================
# CORE AUDIT LOGGER (IMMUTABLE)
# ======================================================

@transaction.atomic
def log_action(
    *,
    instance,
    action: str,
    user=None,
    branch=None,
    device_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    duration=None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Create immutable audit log with hash chaining.
    """

    action = action.upper()
    if action not in VALID_ACTIONS:
        raise ValueError(f"Invalid audit action: {action}")

    context = _extract_context(instance)

    user = user or context.get("user")
    branch = branch or context.get("branch")
    device_id = device_id or context.get("device_id")
    ip_address = ip_address or context.get("ip_address")

    if duration is None and context.get("start_time"):
        duration = timezone.now() - context["start_time"]

    before = getattr(instance, AUDIT_BEFORE_ATTR, None)

    after = None if action == "DELETE" else serialize_model(instance)

    last = (
        AuditLog.objects
        .select_for_update()
        .order_by("-id")
        .only("record_hash")
        .first()
    )

    previous_hash = last.record_hash if last else ""

    model_name = instance.__class__.__name__
    object_id = str(instance.pk) if instance.pk else "NEW"

    payload = {
        "timestamp": timezone.now().isoformat(),
        "branch_id": branch.id if branch else None,
        "user_id": user.id if user else None,
        "action": action,
        "model": model_name,
        "object_id": object_id,
        "before": before,
        "after": after,
        "metadata": metadata or {},
    }

    record_hash = compute_record_hash(previous_hash, payload)

    log = AuditLog.objects.create(
        branch=branch,
        user=user,
        device_id=device_id,
        ip_address=ip_address,
        action=action,
        model_name=model_name,
        object_id=object_id,
        before=before,
        after=after,
        metadata=metadata or {},
        previous_hash=previous_hash,
        record_hash=record_hash,
        duration=duration,
    )

    if hasattr(instance, AUDIT_BEFORE_ATTR):
        delattr(instance, AUDIT_BEFORE_ATTR)

    if hasattr(instance, AUDIT_CONTEXT_ATTR):
        delattr(instance, AUDIT_CONTEXT_ATTR)

    return log


# ======================================================
# ACTION SHORTCUTS
# ======================================================

def log_create(instance, **kwargs):
    return log_action(instance=instance, action="CREATE", **kwargs)


def log_update(instance, **kwargs):
    return log_action(instance=instance, action="UPDATE", **kwargs)


def log_delete(instance, **kwargs):
    return log_action(instance=instance, action="DELETE", **kwargs)


def log_view(instance, **kwargs):
    return log_action(instance=instance, action="VIEW", **kwargs)


def log_approve(instance, **kwargs):
    return log_action(instance=instance, action="APPROVE", **kwargs)


# ======================================================
# BULK OPERATIONS (ORDER PRESERVED)
# ======================================================

@transaction.atomic
def log_bulk(
    instances: Iterable,
    action: str,
    **kwargs,
):
    logs = []
    for instance in instances:
        logs.append(
            log_action(instance=instance, action=action, **kwargs)
        )
    return logs


# ======================================================
# CHAIN VERIFICATION
# ======================================================

def verify_chain() -> List[Dict[str, Any]]:
    """
    Verify audit hash chain by recomputing hashes.
    """
    broken = []
    previous_hash = ""

    logs = AuditLog.objects.order_by("id").iterator()

    for log in logs:
        payload = {
            "timestamp": log.timestamp.isoformat(),
            "branch_id": log.branch_id,
            "user_id": log.user_id,
            "action": log.action,
            "model": log.model_name,
            "object_id": log.object_id,
            "before": log.before,
            "after": log.after,
            "metadata": log.metadata or {},
        }

        expected_hash = compute_record_hash(previous_hash, payload)

        if (
            log.previous_hash != previous_hash
            or log.record_hash != expected_hash
        ):
            broken.append({
                "log_id": log.id,
                "expected_previous": previous_hash,
                "actual_previous": log.previous_hash,
                "expected_hash": expected_hash,
                "actual_hash": log.record_hash,
                "timestamp": log.timestamp,
            })

        previous_hash = log.record_hash

    return broken


# ======================================================
# QUERY HELPERS
# ======================================================

def get_audit_trail(
    *,
    model_name: str,
    object_id: Any,
    limit: int = 100,
):
    return (
        AuditLog.objects
        .filter(
            model_name=model_name,
            object_id=str(object_id),
        )
        .order_by("-timestamp")[:limit]
    )


# ======================================================
# EXPORT (BASIC – CSV / JSON)
# ======================================================

def export_audit_logs(start_date, end_date, format: str = "json"):
    logs = AuditLog.objects.filter(
        timestamp__gte=start_date,
        timestamp__lte=end_date,
    ).order_by("timestamp")

    data = list(
        logs.values(
            "id",
            "timestamp",
            "action",
            "model_name",
            "object_id",
            "user__email",
            "branch__name",
            "device_id",
            "ip_address",
            "record_hash",
        )
    )

    if format == "csv":
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=data[0].keys() if data else [],
        )
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()

    return json.dumps(data, indent=2, default=str)



# ==========================
# HASH CHAIN
# ==========================

def compute_hash(previous_hash: str, payload: dict) -> str:
    raw = (previous_hash or "") + json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()



# ==========================
# RECORD VALIDATION
# ==========================


def validate_record_hash(audit_log) -> bool:
    """
    Validate a single AuditLog record hash.
    Recomputes hash and compares with stored value.
    """

    payload = {
        "timestamp": audit_log.timestamp.isoformat(),
        "branch_id": audit_log.branch_id,
        "user_id": audit_log.user_id,
        "action": audit_log.action,
        "model": audit_log.model_name,
        "object_id": audit_log.object_id,
        "before": audit_log.before,
        "after": audit_log.after,
        "metadata": audit_log.metadata if hasattr(audit_log, "metadata") else {},
    }

    expected_hash = compute_hash(
        audit_log.previous_hash,
        payload,
    )

    return expected_hash == audit_log.record_hash