"""
Audit App for Dental Clinic Management System

Features:
1. Immutable audit logging with hash chain
2. Role-based access control for audit viewing
3. Real-time audit feed
4. Export capabilities (JSON, CSV, Excel)
5. Hash chain verification
6. Object-level audit trails
7. Webhook integration
8. Health monitoring

Usage:
- Import services in your models/signals
- Use middleware for automatic request logging
- Use views for audit log viewing and management

Permissions:
- IsAuditor: Can view audit logs
- IsManager: Can view branch audit logs
- IsAdminUser: Full access
"""


default_app_config = "apps.audit.apps.AuditConfig"
