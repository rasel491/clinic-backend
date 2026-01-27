# # Backend/apps/audit/urls.py

# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from .views import (
#     AuditLogViewSet,
#     ObjectAuditTrailView,
#     UserAuditLogsView,
#     BranchAuditLogsView,
#     LiveAuditFeedView,
#     AuditHealthCheckView,
#     audit_webhook,
#     manual_audit_log,
#     bulk_audit_logs,
# )

# # Create a router and register our viewsets
# router = DefaultRouter()
# router.register(r'logs', AuditLogViewSet, basename='audit-log')

# # The API URLs are now determined automatically by the router
# urlpatterns = [
#     # Main router URLs
#     path('', include(router.urls)),
    
#     # Specialized endpoints
#     path('trail/<str:model_name>/<str:object_id>/', 
#          ObjectAuditTrailView.as_view(), 
#          name='object-audit-trail'),
    
#     path('user/<int:user_id>/', 
#          UserAuditLogsView.as_view(), 
#          name='user-audit-logs'),
    
#     path('branch/<int:branch_id>/', 
#          BranchAuditLogsView.as_view(), 
#          name='branch-audit-logs'),
    
#     path('live/', 
#          LiveAuditFeedView.as_view(), 
#          name='live-audit-feed'),
    
#     # Webhook and manual operations
#     path('webhook/', 
#          audit_webhook, 
#          name='audit-webhook'),
    
#     path('manual/', 
#          manual_audit_log, 
#          name='manual-audit-log'),
    
#     path('bulk/', 
#          bulk_audit_logs, 
#          name='bulk-audit-logs'),
    
#     # Health check
#     path('health/', 
#          AuditHealthCheckView.as_view(), 
#          name='audit-health-check'),
# ]

# # ============================
# # URL Documentation
# # ============================

# """
# AUDIT MODULE URLS
# -----------------

# BASE: /api/audit/

# MAIN ENDPOINTS:
# 1. /logs/                    - List all audit logs (GET)
#    - ?page=1                 - Pagination
#    - ?page_size=20           - Page size (1-100)
#    - ?search=keyword         - Search across fields
#    - ?action=CREATE          - Filter by action
#    - ?model_name=Patient     - Filter by model
#    - ?branch_id=1            - Filter by branch
#    - ?user_id=1              - Filter by user
#    - ?date_from=2024-01-01   - Date range filter
#    - ?date_to=2024-01-31     - Date range filter
#    - ?sort_by=timestamp      - Sort field
#    - ?sort_order=desc        - Sort order

# 2. /logs/{id}/               - Get specific audit log (GET)
#    - Includes hash validation, change details

# 3. /logs/stats/              - Get audit statistics (GET)
#    - ?days=30                - Time period in days

# 4. /logs/summary/            - Dashboard summary (GET)

# 5. /logs/export/             - Export logs (POST)
#    - Request body:
#      {
#        "start_date": "2024-01-01T00:00:00Z",
#        "end_date": "2024-01-31T23:59:59Z",
#        "format": "json|csv|excel",
#        "include_sensitive": false,
#        "compress": false
#      }

# 6. /logs/verify_chain/       - Verify hash chain integrity (GET)

# 7. /logs/search/             - Advanced search (GET)
#    - ?q=search_term          - Full-text search
#    - Additional filters same as /logs/

# 8. /logs/{id}/trail/         - Get audit trail for object (GET)

# 9. /logs/{id}/diff/          - Compare with another log (GET)
#    - ?compare_with=123       - ID of log to compare with

# SPECIALIZED ENDPOINTS:
# 10. /trail/{model}/{id}/     - Direct object audit trail (GET)
#     - /trail/Patient/123/

# 11. /user/{user_id}/         - User-specific audit logs (GET)

# 12. /branch/{branch_id}/     - Branch-specific audit logs (GET)

# 13. /live/                   - Live audit feed (GET)
#     - Accept: text/event-stream for SSE

# UTILITY ENDPOINTS:
# 14. /webhook/                - External webhook receiver (POST)
#     - Requires signature verification

# 15. /manual/                 - Manual audit log creation (POST)
#     - Admin only, for testing/backfilling

# 16. /bulk/                   - Bulk audit log creation (POST)
#     - Admin only

# 17. /health/                 - System health check (GET)

# PERMISSIONS:
# - Admin: Full access to all endpoints
# - Manager: Access to their branch logs only
# - Regular User: Access to their own actions only
# - Auditor: Read-only access to audit logs
# - Webhook: No authentication (signature based)

# AUTHENTICATION:
# - All endpoints except /webhook/ require JWT authentication
# - Role-based permissions enforced in views
# - Device binding for sensitive operations

# RATE LIMITING:
# - /webhook/: 100 requests/hour per IP
# - /live/: 10 concurrent connections per user
# - /export/: 5 requests/day per user
# - /bulk/: 1 request/minute per user
# """




# Backend/apps/audit/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.audit.views.base import AuditLogViewSet
from apps.audit.views.trail import ObjectAuditTrailView
from apps.audit.views.stats import AuditStatsView
from apps.audit.views.verify import AuditChainVerifyView
from apps.audit.views.export import AuditExportView
from apps.audit.views.health import AuditHealthView
from apps.audit.views.webhooks import audit_webhook

router = DefaultRouter()
router.register(r"logs", AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("", include(router.urls)),

    # Object-level trail
    path(
        "trail/<str:model_name>/<str:object_id>/",
        ObjectAuditTrailView.as_view(),
        name="object-audit-trail",
    ),

    # Statistics & verification
    path("stats/", AuditStatsView.as_view(), name="audit-stats"),
    path("verify/", AuditChainVerifyView.as_view(), name="audit-verify"),

    # Export
    path("export/", AuditExportView.as_view(), name="audit-export"),

    # Health
    path("health/", AuditHealthView.as_view(), name="audit-health"),

    # Webhook
    path("webhook/", audit_webhook, name="audit-webhook"),
]

