# #Backend/apps/audit/serializers.py   #  Split all in serializers folder
# from rest_framework import serializers
# from django.db.models import Count, Avg, Max, Min
# from django.utils import timezone
# from datetime import timedelta
# import json

# from .models import AuditLog
# from apps.accounts.serializers import UserSerializer
# from apps.clinics.serializers import BranchSerializer


# class AuditLogSerializer(serializers.ModelSerializer):
#     """Main serializer for AuditLog model"""
    
#     # Foreign key relationships with details
#     user_details = UserSerializer(source='user', read_only=True)
#     branch_details = BranchSerializer(source='branch', read_only=True)
    
#     # Readable action display
#     # action_display = serializers.CharField(source='get_action_display', read_only=True)
    
#     # Formatted duration
#     duration_seconds = serializers.SerializerMethodField()
#     duration_display = serializers.SerializerMethodField()
    
#     # Hash chain verification
#     hash_valid = serializers.SerializerMethodField()
#     previous_hash_short = serializers.SerializerMethodField()
#     record_hash_short = serializers.SerializerMethodField()
    
#     # Before/After data (safe serialization)
#     before_safe = serializers.SerializerMethodField()
#     after_safe = serializers.SerializerMethodField()
    
#     # Audit trail links
#     object_audit_url = serializers.SerializerMethodField()
    
#     class Meta:
#         model = AuditLog
#         fields = [
#             'id',
#             'branch', 'branch_details',
#             'user', 'user_details',
#             'device_id',
#             'ip_address',
#             'action', 'action_display',
#             'model_name',
#             'object_id',
#             'before', 'before_safe',
#             'after', 'after_safe',
#             'previous_hash', 'previous_hash_short',
#             'record_hash', 'record_hash_short',
#             'timestamp',
#             'duration', 'duration_seconds', 'duration_display',
#             'hash_valid',
#             'object_audit_url',
#         ]
#         read_only_fields = fields  # All fields are read-only
    
#     def get_duration_seconds(self, obj):
#         """Get duration in seconds"""
#         if obj.duration:
#             return obj.duration.total_seconds()
#         return None
    
#     def get_duration_display(self, obj):
#         """Get human-readable duration"""
#         if obj.duration:
#             total_seconds = obj.duration.total_seconds()
#             if total_seconds < 1:
#                 return f"{total_seconds * 1000:.0f}ms"
#             elif total_seconds < 60:
#                 return f"{total_seconds:.1f}s"
#             else:
#                 minutes = total_seconds / 60
#                 return f"{minutes:.1f}min"
#         return None
    

#     def get_hash_valid(self, obj):
#         if not obj.record_hash:
#             return None

#         payload = {
#             "timestamp": obj.timestamp.isoformat(),
#             "branch_id": obj.branch_id,
#             "user_id": obj.user_id,
#             "action": obj.action,
#             "model": obj.model_name,
#             "object_id": obj.object_id,
#             "before": obj.before,
#             "after": obj.after,
#         }

#         from .services import compute_hash
#         expected = compute_hash(obj.previous_hash, payload)
#         return expected == obj.record_hash

        
#     def get_previous_hash_short(self, obj):
#         """Get shortened hash for display"""
#         if obj.previous_hash:
#             return f"{obj.previous_hash[:8]}...{obj.previous_hash[-8:]}"
#         return "GENESIS"
    
#     def get_record_hash_short(self, obj):
#         """Get shortened hash for display"""
#         if obj.record_hash:
#             return f"{obj.record_hash[:8]}...{obj.record_hash[-8:]}"
#         return None
    
#     def get_before_safe(self, obj):
#         """Safe serialization of before data"""
#         return self._safe_json(obj.before)
    
#     def get_after_safe(self, obj):
#         """Safe serialization of after data"""
#         return self._safe_json(obj.after)
    
#     def _safe_json(self, data):
#         """Convert JSON data to safe format for display"""
#         if not isinstance(data, dict):
#             return data
        
#         return self._remove_sensitive_fields(data)
    
    
#     def _remove_sensitive_fields(self, data):
#         """Remove sensitive fields from audit data"""
#         if not isinstance(data, dict):
#             return data
        
#         sensitive_patterns = [
#             'password', 'token', 'secret', 'key',
#             'ssn', 'pan', 'aadhaar', 'credit_card',
#             'cvv', 'pin', 'otp', 'salt', 'hash'
#         ]
        
#         safe_data = {}
#         for key, value in data.items():
#             key_lower = key.lower()
            
#             # Check if field contains sensitive information
#             is_sensitive = any(pattern in key_lower for pattern in sensitive_patterns)
            
#             if is_sensitive:
#                 safe_data[key] = '[REDACTED]'
#             elif isinstance(value, dict):
#                 safe_data[key] = self._remove_sensitive_fields(value)
#             elif isinstance(value, list):
#                 safe_data[key] = [
#                     self._remove_sensitive_fields(item) if isinstance(item, dict) else item
#                     for item in value
#                 ]
#             else:
#                 safe_data[key] = value
        
#         return safe_data
    
#     def get_object_audit_url(self, obj):
#         """Get URL to view audit trail for this object"""
#         if obj.model_name and obj.object_id:
#             return f"/api/audit/trail/{obj.model_name}/{obj.object_id}/"
#         return None


# class AuditLogListSerializer(serializers.ModelSerializer):
#     """Lightweight serializer for list views"""
    
#     user_email = serializers.CharField(source='user.email', read_only=True)
#     branch_name = serializers.CharField(source='branch.name', read_only=True)
#     # action_display = serializers.CharField(source='get_action_display', read_only=True)
    
#     class Meta:
#         model = AuditLog
#         fields = [
#             'id',
#             'timestamp',
#             'action', 'action_display',
#             'model_name',
#             'object_id',
#             'user_email',
#             'branch_name',
#             'device_id',
#             'ip_address',
#         ]
#         read_only_fields = fields


# class AuditLogDetailSerializer(AuditLogSerializer):
#     """Detailed serializer with change analysis"""
    
#     # Change analysis
#     changes = serializers.SerializerMethodField()
#     changed_fields = serializers.SerializerMethodField()
#     is_creation = serializers.SerializerMethodField()
#     is_deletion = serializers.SerializerMethodField()
    
#     # Related logs
#     previous_log = serializers.SerializerMethodField()
#     next_log = serializers.SerializerMethodField()
    
#     class Meta(AuditLogSerializer.Meta):
#         fields = AuditLogSerializer.Meta.fields + [
#             'changes',
#             'changed_fields',
#             'is_creation',
#             'is_deletion',
#             'previous_log',
#             'next_log',
#         ]
    
#     def get_changes(self, obj):
#         """Get detailed changes between before and after"""
#         if not obj.before or not obj.after:
#             return None
        
#         try:
#             before = obj.before if isinstance(obj.before, dict) else json.loads(obj.before)
#             after = obj.after if isinstance(obj.after, dict) else json.loads(obj.after)
            
#             changes = {}
#             all_keys = set(before.keys()) | set(after.keys())
            
#             for key in all_keys:
#                 before_val = before.get(key)
#                 after_val = after.get(key)
                
#                 if before_val != after_val:
#                     changes[key] = {
#                         'before': before_val,
#                         'after': after_val,
#                         'changed': True
#                     }
#                 else:
#                     changes[key] = {
#                         'value': before_val,
#                         'changed': False
#                     }
            
#             return changes
#         except Exception:
#             return None
    
#     def get_changed_fields(self, obj):
#         """Get list of changed field names"""
#         changes = self.get_changes(obj)
#         if not changes:
#             return []
        
#         return [field for field, data in changes.items() if data.get('changed', False)]
    
#     def get_is_creation(self, obj):
#         """Check if this log represents object creation"""
#         return obj.before is None and obj.after is not None
    
#     def get_is_deletion(self, obj):
#         """Check if this log represents object deletion"""
#         return obj.before is not None and obj.after is None
    
#     def get_previous_log(self, obj):
#         """Get previous log in sequence"""
#         if not obj.id:
#             return None
        
#         previous = AuditLog.objects.filter(
#             id__lt=obj.id
#         ).order_by('-id').first()
        
#         if previous:
#             return {
#                 'id': previous.id,
#                 'timestamp': previous.timestamp,
#                 'action': previous.action,
#                 'model_name': previous.model_name,
#                 'object_id': previous.object_id,
#                 'record_hash_short': f"{previous.record_hash[:8]}...{previous.record_hash[-8:]}"
#             }
#         return None
    
#     def get_next_log(self, obj):
#         """Get next log in sequence"""
#         if not obj.id:
#             return None
        
#         next_log = AuditLog.objects.filter(
#             id__gt=obj.id
#         ).order_by('id').first()
        
#         if next_log:
#             return {
#                 'id': next_log.id,
#                 'timestamp': next_log.timestamp,
#                 'action': next_log.action,
#                 'model_name': next_log.model_name,
#                 'object_id': next_log.object_id,
#                 'record_hash_short': f"{next_log.record_hash[:8]}...{next_log.record_hash[-8:]}"
#             }
#         return None


# class AuditTrailSerializer(serializers.Serializer):
#     """Serializer for object audit trail"""
    
#     object_id = serializers.CharField()
#     model_name = serializers.CharField()
#     total_logs = serializers.IntegerField()
#     first_log = serializers.DateTimeField()
#     last_log = serializers.DateTimeField()
#     logs = AuditLogSerializer(many=True)
    
#     class Meta:
#         fields = ['object_id', 'model_name', 'total_logs', 'first_log', 'last_log', 'logs']


# class AuditStatsSerializer(serializers.Serializer):
#     """Serializer for audit statistics"""
    
#     # Time period
#     period_start = serializers.DateTimeField()
#     period_end = serializers.DateTimeField()
    
#     # Counts
#     total_logs = serializers.IntegerField()
#     logs_today = serializers.IntegerField()
#     logs_this_week = serializers.IntegerField()
#     logs_this_month = serializers.IntegerField()
    
#     # By action
#     by_action = serializers.DictField()
    
#     # By model
#     by_model = serializers.DictField()
    
#     # By user
#     by_user = serializers.ListField()
    
#     # By hour (for heatmap)
#     by_hour = serializers.DictField()
    
#     # Chain integrity
#     chain_verified = serializers.BooleanField()
#     broken_links_count = serializers.IntegerField(default=0)
    
#     # Performance
#     avg_duration_seconds = serializers.FloatField()
#     max_duration_seconds = serializers.FloatField()
#     min_duration_seconds = serializers.FloatField()
    
#     class Meta:
#         fields = [
#             'period_start', 'period_end',
#             'total_logs', 'logs_today', 'logs_this_week', 'logs_this_month',
#             'by_action', 'by_model', 'by_user', 'by_hour',
#             'chain_verified', 'broken_links_count',
#             'avg_duration_seconds', 'max_duration_seconds', 'min_duration_seconds',
#         ]


# class AuditExportSerializer(serializers.Serializer):
#     """Serializer for audit export requests"""
    
#     start_date = serializers.DateTimeField(required=True)
#     end_date = serializers.DateTimeField(required=True)
#     format = serializers.ChoiceField(
#         choices=['json', 'csv', 'excel'],
#         default='json'
#     )
#     include_sensitive = serializers.BooleanField(default=False)
#     compress = serializers.BooleanField(default=False)
    
#     class Meta:
#         fields = ['start_date', 'end_date', 'format', 'include_sensitive', 'compress']


# class AuditSearchSerializer(serializers.Serializer):
#     """Serializer for audit search requests"""
    
#     q = serializers.CharField(required=False)
#     model_name = serializers.CharField(required=False)
#     action = serializers.CharField(required=False)
#     user_id = serializers.IntegerField(required=False)
#     branch_id = serializers.IntegerField(required=False)
#     date_from = serializers.DateTimeField(required=False)
#     date_to = serializers.DateTimeField(required=False)
#     object_id = serializers.CharField(required=False)
    
#     # Pagination
#     page = serializers.IntegerField(default=1, min_value=1)
#     page_size = serializers.IntegerField(default=20, min_value=1, max_value=100)
    
#     # Sorting
#     sort_by = serializers.ChoiceField(
#         choices=['timestamp', 'action', 'model_name', 'user__email'],
#         default='timestamp'
#     )
#     sort_order = serializers.ChoiceField(
#         choices=['asc', 'desc'],
#         default='desc'
#     )
    
#     class Meta:
#         fields = [
#             'q', 'model_name', 'action', 'user_id', 'branch_id',
#             'date_from', 'date_to', 'object_id',
#             'page', 'page_size', 'sort_by', 'sort_order'
#         ]


# class ChainVerificationSerializer(serializers.Serializer):
#     """Serializer for hash chain verification"""
    
#     verified = serializers.BooleanField()
#     total_records = serializers.IntegerField()
#     broken_links = serializers.ListField()
#     first_record_hash = serializers.CharField()
#     last_record_hash = serializers.CharField()
#     verification_timestamp = serializers.DateTimeField()
    
#     class Meta:
#         fields = [
#             'verified', 'total_records', 'broken_links',
#             'first_record_hash', 'last_record_hash', 'verification_timestamp'
#         ]


# class AuditSummarySerializer(serializers.Serializer):
#     """Serializer for audit summary dashboard"""
    
#     # Today's activity
#     today_total = serializers.IntegerField()
#     today_by_action = serializers.DictField()
#     today_top_models = serializers.ListField()
#     today_top_users = serializers.ListField()
    
#     # Recent activity (last 7 days)
#     week_activity = serializers.ListField()
    
#     # System health
#     chain_healthy = serializers.BooleanField()
#     storage_used_mb = serializers.FloatField()
#     avg_logs_per_day = serializers.FloatField()
    
#     # Alerts
#     suspicious_activity_count = serializers.IntegerField()
#     failed_logins_today = serializers.IntegerField()
    
#     # Recent critical logs
#     recent_critical = AuditLogListSerializer(many=True)
    
#     class Meta:
#         fields = [
#             'today_total', 'today_by_action', 'today_top_models', 'today_top_users',
#             'week_activity',
#             'chain_healthy', 'storage_used_mb', 'avg_logs_per_day',
#             'suspicious_activity_count', 'failed_logins_today',
#             'recent_critical'
#         ]


# # ============================
# # Nested serializers for related data
# # ============================

# class AuditLogChangeSerializer(serializers.Serializer):
#     """Serializer for individual field changes"""
    
#     field = serializers.CharField()
#     before = serializers.JSONField(allow_null=True)
#     after = serializers.JSONField(allow_null=True)
#     changed = serializers.BooleanField()
    
#     class Meta:
#         fields = ['field', 'before', 'after', 'changed']


# class AuditLogDiffSerializer(serializers.Serializer):
#     """Serializer for showing differences between two audit logs"""
    
#     log1 = AuditLogSerializer()
#     log2 = AuditLogSerializer()
#     differences = AuditLogChangeSerializer(many=True)
    
#     class Meta:
#         fields = ['log1', 'log2', 'differences']


# # ============================
# # Custom field serializers
# # ============================

# class DurationField(serializers.Field):
#     """Custom field for duration display"""
    
#     def to_representation(self, value):
#         if value is None:
#             return None
        
#         total_seconds = value.total_seconds()
        
#         if total_seconds < 1:
#             return f"{total_seconds * 1000:.0f}ms"
#         elif total_seconds < 60:
#             return f"{total_seconds:.1f}s"
#         elif total_seconds < 3600:
#             minutes = total_seconds / 60
#             return f"{minutes:.1f}min"
#         else:
#             hours = total_seconds / 3600
#             return f"{hours:.1f}hr"
    
#     def to_internal_value(self, data):
#         # Not needed for read-only field
#         raise NotImplementedError("DurationField is read-only")


# class HashField(serializers.Field):
#     """Custom field for hash display"""
    
#     def to_representation(self, value):
#         if not value:
#             return None
        
#         if len(value) > 16:
#             return f"{value[:8]}...{value[-8:]}"
#         return value
    
#     def to_internal_value(self, data):
#         # Not needed for read-only field
#         raise NotImplementedError("HashField is read-only")


# # ============================
# # Response serializers for API endpoints
# # ============================

# class AuditLogResponseSerializer(serializers.Serializer):
#     """Standard response for audit log operations"""
    
#     success = serializers.BooleanField()
#     message = serializers.CharField()
#     data = serializers.JSONField(required=False)
#     log_id = serializers.IntegerField(required=False)
#     timestamp = serializers.DateTimeField()
    
#     class Meta:
#         fields = ['success', 'message', 'data', 'log_id', 'timestamp']


# class BulkAuditResponseSerializer(serializers.Serializer):
#     """Response for bulk audit operations"""
    
#     success = serializers.BooleanField()
#     message = serializers.CharField()
#     total_processed = serializers.IntegerField()
#     successful = serializers.IntegerField()
#     failed = serializers.IntegerField()
#     failed_details = serializers.ListField(required=False)
#     timestamp = serializers.DateTimeField()
    
#     class Meta:
#         fields = [
#             'success', 'message', 'total_processed',
#             'successful', 'failed', 'failed_details', 'timestamp'
#         ]


# # ============================
# # Webhook/Event serializers
# # ============================

# class AuditWebhookSerializer(serializers.Serializer):
#     """Serializer for audit webhook events"""
    
#     event_type = serializers.CharField()
#     log_id = serializers.IntegerField()
#     timestamp = serializers.DateTimeField()
#     data = AuditLogSerializer()
#     signature = serializers.CharField(required=False)
    
#     class Meta:
#         fields = ['event_type', 'log_id', 'timestamp', 'data', 'signature']


# class AuditAlertSerializer(serializers.Serializer):
#     """Serializer for audit alerts"""
    
#     alert_type = serializers.ChoiceField(choices=[
#         ('SUSPICIOUS_ACTIVITY', 'Suspicious Activity'),
#         ('CHAIN_TAMPERING', 'Hash Chain Tampering'),
#         ('RATE_LIMIT_EXCEEDED', 'Rate Limit Exceeded'),
#         ('SENSITIVE_OPERATION', 'Sensitive Operation'),
#         ('UNAUTHORIZED_ACCESS', 'Unauthorized Access'),
#     ])
#     severity = serializers.ChoiceField(choices=[
#         ('LOW', 'Low'),
#         ('MEDIUM', 'Medium'),
#         ('HIGH', 'High'),
#         ('CRITICAL', 'Critical'),
#     ])
#     message = serializers.CharField()
#     details = serializers.JSONField()
#     timestamp = serializers.DateTimeField()
#     resolved = serializers.BooleanField(default=False)
    
#     class Meta:
#         fields = ['alert_type', 'severity', 'message', 'details', 'timestamp', 'resolved']