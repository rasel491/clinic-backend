# # Backend/apps/audit/views.py   # Split all in views folder
# from rest_framework import viewsets, status, filters, generics
# from rest_framework.decorators import action, api_view, permission_classes
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated, AllowAny
# from rest_framework.views import APIView
# from rest_framework.pagination import PageNumberPagination
# from django.utils import timezone
# from django.db.models import Q, Count, Avg, Max, Min
# from django.db import transaction
# from django.http import HttpResponse, JsonResponse
# from django.shortcuts import get_object_or_404
# from datetime import timedelta, datetime
# import json
# import csv
# from io import StringIO, BytesIO
# import pandas as pd
# import logging

# from core.permissions import IsAdminUser, IsManager, IsAuditor
# from django_filters.rest_framework import DjangoFilterBackend

# from .models import AuditLog
# from .serializers import (
#     AuditLogSerializer,
#     AuditLogListSerializer,
#     AuditLogDetailSerializer,
#     AuditTrailSerializer,
#     AuditStatsSerializer,
#     AuditExportSerializer,
#     AuditSearchSerializer,
#     ChainVerificationSerializer,
#     AuditSummarySerializer,
#     AuditLogResponseSerializer,
#     AuditLogDiffSerializer,
#     AuditAlertSerializer,
#     AuditWebhookSerializer,
#     BulkAuditResponseSerializer,
# )
# from .filters import AuditLogFilter
# from .services import (
#     verify_chain,
#     get_audit_trail,
#     export_audit_logs,
#     log_action,
#     log_create,
#     log_update,
#     log_delete,
# )
# from apps.accounts.models import User
# from apps.clinics.models import Branch

# logger = logging.getLogger(__name__)


# # ============================
# # Custom Pagination
# # ============================

# class AuditLogPagination(PageNumberPagination):
#     """Custom pagination for audit logs"""
#     page_size = 20
#     page_size_query_param = 'page_size'
#     max_page_size = 100
    
#     def get_paginated_response(self, data):
#         return Response({
#             'count': self.page.paginator.count,
#             'next': self.get_next_link(),
#             'previous': self.get_previous_link(),
#             'current_page': self.page.number,
#             'total_pages': self.page.paginator.num_pages,
#             'page_size': self.get_page_size(self.request),
#             'results': data
#         })


# # ============================
# # Main ViewSet
# # ============================

# class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
#     """
#     ViewSet for viewing audit logs.
#     Read-only - audit logs are immutable.
#     """
#     queryset = AuditLog.objects.all()
#     serializer_class = AuditLogSerializer
#     permission_classes = [IsAuthenticated, IsAuditor]
#     pagination_class = AuditLogPagination
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_class = AuditLogFilter
#     search_fields = ['action', 'model_name', 'object_id', 'device_id', 'ip_address']
#     ordering_fields = ['timestamp', 'action', 'model_name', 'user__email']
#     ordering = ['-timestamp']  # Default ordering
    
#     def get_queryset(self):
#         """
#         Filter queryset based on user permissions.
#         """
#         queryset = super().get_queryset()
        
#         # Admins can see all
#         if self.request.user.is_superuser or self.request.user.is_admin():
#             return queryset
        
#         # Managers can see their branch logs
#         if self.request.user.is_manager():
#             # Get user's branches
#             user_branches = self.request.user.user_branches.filter(
#                 is_active=True
#             ).values_list('branch_id', flat=True)
            
#             if user_branches:
#                 return queryset.filter(branch_id__in=user_branches)
#             else:
#                 # No branch assigned - return empty
#                 return queryset.none()
        
#         # Regular users can only see their own actions
#         return queryset.filter(user=self.request.user)
    
#     def get_serializer_class(self):
#         """
#         Use different serializers based on action.
#         """
#         if self.action == 'list':
#             return AuditLogListSerializer
#         elif self.action == 'retrieve':
#             return AuditLogDetailSerializer
#         return super().get_serializer_class()
    
#     @action(detail=False, methods=['get'])
#     def stats(self, request):
#         """
#         Get audit statistics for a date range.
#         """
#         # Parse date range parameters
#         days = int(request.query_params.get('days', 30))
#         start_date = timezone.now() - timedelta(days=days)
#         end_date = timezone.now()
        
#         queryset = self.get_queryset().filter(
#             timestamp__range=[start_date, end_date]
#         )
        
#         # Basic counts
#         total_logs = queryset.count()
#         logs_today = queryset.filter(
#             timestamp__date=timezone.now().date()
#         ).count()
        
#         logs_this_week = queryset.filter(
#             timestamp__gte=timezone.now() - timedelta(days=7)
#         ).count()
        
#         logs_this_month = queryset.filter(
#             timestamp__gte=timezone.now() - timedelta(days=30)
#         ).count()
        
#         # Group by action
#         by_action = dict(queryset.values_list('action').annotate(
#             count=Count('id')
#         ).order_by('-count'))
        
#         # Group by model
#         by_model = dict(queryset.values_list('model_name').annotate(
#             count=Count('id')
#         ).order_by('-count')[:10])  # Top 10 models
        
#         # Group by user
#         by_user = list(queryset.values('user__email').annotate(
#             count=Count('id'),
#             last_action=Max('timestamp')
#         ).order_by('-count')[:10])  # Top 10 users
        
#         # Group by hour (for heatmap)
#         by_hour = {}
#         for hour in range(24):
#             count = queryset.filter(
#                 timestamp__hour=hour
#             ).count()
#             by_hour[str(hour)] = count
        
#         # Chain verification
#         chain_verified = len(verify_chain()) == 0
#         broken_links_count = len(verify_chain())
        
#         # Performance stats
#         duration_stats = queryset.aggregate(
#             avg_duration=Avg('duration'),
#             max_duration=Max('duration'),
#             min_duration=Min('duration')
#         )
        
#         avg_duration_seconds = duration_stats['avg_duration'].total_seconds() if duration_stats['avg_duration'] else 0
#         max_duration_seconds = duration_stats['max_duration'].total_seconds() if duration_stats['max_duration'] else 0
#         min_duration_seconds = duration_stats['min_duration'].total_seconds() if duration_stats['min_duration'] else 0
        
#         # Prepare response
#         stats_data = {
#             'period_start': start_date,
#             'period_end': end_date,
#             'total_logs': total_logs,
#             'logs_today': logs_today,
#             'logs_this_week': logs_this_week,
#             'logs_this_month': logs_this_month,
#             'by_action': by_action,
#             'by_model': by_model,
#             'by_user': by_user,
#             'by_hour': by_hour,
#             'chain_verified': chain_verified,
#             'broken_links_count': broken_links_count,
#             'avg_duration_seconds': avg_duration_seconds,
#             'max_duration_seconds': max_duration_seconds,
#             'min_duration_seconds': min_duration_seconds,
#         }
        
#         serializer = AuditStatsSerializer(data=stats_data)
#         if serializer.is_valid():
#             return Response(serializer.data)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
#     @action(detail=False, methods=['get'])
#     def summary(self, request):
#         """
#         Get dashboard summary of audit activity.
#         """
#         # Today's activity
#         today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
#         today_logs = self.get_queryset().filter(timestamp__gte=today_start)
        
#         today_total = today_logs.count()
#         today_by_action = dict(today_logs.values_list('action').annotate(
#             count=Count('id')
#         ))
        
#         today_top_models = list(today_logs.values('model_name').annotate(
#             count=Count('id')
#         ).order_by('-count')[:5])
        
#         today_top_users = list(today_logs.values('user__email').annotate(
#             count=Count('id')
#         ).order_by('-count')[:5])
        
#         # Week activity
#         week_activity = []
#         for i in range(7):
#             date = today_start - timedelta(days=i)
#             count = self.get_queryset().filter(
#                 timestamp__date=date.date()
#             ).count()
#             week_activity.append({
#                 'date': date.date(),
#                 'count': count
#             })
        
#         # System health
#         chain_healthy = len(verify_chain()) == 0
        
#         # Estimate storage (rough calculation)
#         storage_used_mb = self.get_queryset().count() * 0.5  # ~0.5KB per log
        
#         # Average logs per day (last 30 days)
#         avg_logs_per_day = self.get_queryset().filter(
#             timestamp__gte=timezone.now() - timedelta(days=30)
#         ).count() / 30
        
#         # Alerts
#         suspicious_activity_count = today_logs.filter(
#             action__in=['FAILED_LOGIN', 'UNAUTHORIZED', 'SUSPICIOUS']
#         ).count()
        
#         failed_logins_today = today_logs.filter(
#             action='FAILED_LOGIN'
#         ).count()
        
#         # Recent critical logs
#         recent_critical = today_logs.filter(
#             action__in=['FAILED_LOGIN', 'UNAUTHORIZED', 'SENSITIVE_OPERATION']
#         ).order_by('-timestamp')[:10]
#         recent_critical_data = AuditLogListSerializer(recent_critical, many=True).data
        
#         # Prepare response
#         summary_data = {
#             'today_total': today_total,
#             'today_by_action': today_by_action,
#             'today_top_models': today_top_models,
#             'today_top_users': today_top_users,
#             'week_activity': week_activity,
#             'chain_healthy': chain_healthy,
#             'storage_used_mb': round(storage_used_mb, 2),
#             'avg_logs_per_day': round(avg_logs_per_day, 2),
#             'suspicious_activity_count': suspicious_activity_count,
#             'failed_logins_today': failed_logins_today,
#             'recent_critical': recent_critical_data,
#         }
        
#         serializer = AuditSummarySerializer(data=summary_data)
#         if serializer.is_valid():
#             return Response(serializer.data)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
#     @action(detail=False, methods=['post'])
#     def export(self, request):
#         """
#         Export audit logs for a date range.
#         """
#         serializer = AuditExportSerializer(data=request.data)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         try:
#             start_date = serializer.validated_data['start_date']
#             end_date = serializer.validated_data['end_date']
#             export_format = serializer.validated_data['format']
#             include_sensitive = serializer.validated_data['include_sensitive']
#             compress = serializer.validated_data['compress']
            
#             # Check permissions for sensitive data
#             if include_sensitive and not (request.user.is_superuser or request.user.is_admin()):
#                 return Response(
#                     {'error': 'Permission denied for sensitive data export'},
#                     status=status.HTTP_403_FORBIDDEN
#                 )
            
#             # Get filtered logs
#             queryset = self.get_queryset().filter(
#                 timestamp__gte=start_date,
#                 timestamp__lte=end_date
#             ).order_by('timestamp')
            
#             if export_format == 'csv':
#                 # Generate CSV
#                 response = HttpResponse(content_type='text/csv')
#                 response['Content-Disposition'] = f'attachment; filename="audit_logs_{start_date.date()}_to_{end_date.date()}.csv"'
                
#                 writer = csv.writer(response)
#                 # Write headers
#                 writer.writerow([
#                     'ID', 'Timestamp', 'Action', 'Model', 'Object ID',
#                     'User Email', 'Branch', 'Device ID', 'IP Address',
#                     'Duration (s)', 'Previous Hash', 'Record Hash'
#                 ])
                
#                 # Write data
#                 for log in queryset:
#                     writer.writerow([
#                         log.id,
#                         log.timestamp,
#                         log.action,
#                         log.model_name,
#                         log.object_id,
#                         log.user.email if log.user else '',
#                         log.branch.name if log.branch else '',
#                         log.device_id or '',
#                         log.ip_address or '',
#                         log.duration.total_seconds() if log.duration else '',
#                         log.previous_hash,
#                         log.record_hash
#                     ])
                
#                 return response
            
#             elif export_format == 'excel':
#                 # Generate Excel
#                 data = []
#                 for log in queryset:
#                     data.append({
#                         'ID': log.id,
#                         'Timestamp': log.timestamp,
#                         'Action': log.action,
#                         'Model': log.model_name,
#                         'Object ID': log.object_id,
#                         'User Email': log.user.email if log.user else '',
#                         'Branch': log.branch.name if log.branch else '',
#                         'Device ID': log.device_id or '',
#                         'IP Address': log.ip_address or '',
#                         'Duration (s)': log.duration.total_seconds() if log.duration else '',
#                         'Previous Hash': log.previous_hash,
#                         'Record Hash': log.record_hash
#                     })
                
#                 df = pd.DataFrame(data)
#                 output = BytesIO()
#                 with pd.ExcelWriter(output, engine='openpyxl') as writer:
#                     df.to_excel(writer, sheet_name='Audit Logs', index=False)
                
#                 output.seek(0)
#                 response = HttpResponse(
#                     output.read(),
#                     content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
#                 )
#                 response['Content-Disposition'] = f'attachment; filename="audit_logs_{start_date.date()}_to_{end_date.date()}.xlsx"'
#                 return response
            
#             else:  # JSON format (default)
#                 serializer = self.get_serializer(queryset, many=True)
#                 data = serializer.data
                
#                 if not include_sensitive:
#                     # Remove sensitive data from JSON response
#                     for log in data:
#                         if 'before_safe' in log:
#                             log['before'] = log['before_safe']
#                             del log['before_safe']
#                         if 'after_safe' in log:
#                             log['after'] = log['after_safe']
#                             del log['after_safe']
                
#                 if compress:
#                     # Compress JSON response
#                     import gzip
#                     compressed = gzip.compress(json.dumps(data).encode())
#                     response = HttpResponse(compressed, content_type='application/json')
#                     response['Content-Disposition'] = f'attachment; filename="audit_logs_{start_date.date()}_to_{end_date.date()}.json.gz"'
#                     response['Content-Encoding'] = 'gzip'
#                     return response
#                 else:
#                     return JsonResponse(data, safe=False)
        
#         except Exception as e:
#             logger.error(f"Error exporting audit logs: {str(e)}")
#             return Response(
#                 {'error': f'Export failed: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     @action(detail=False, methods=['get'])
#     def verify_chain(self, request):
#         """
#         Verify integrity of the audit hash chain.
#         """
#         try:
#             broken_links = verify_chain()
            
#             first_record = AuditLog.objects.order_by('id').first()
#             last_record = AuditLog.objects.order_by('-id').first()
            
#             verification_data = {
#                 'verified': len(broken_links) == 0,
#                 'total_records': AuditLog.objects.count(),
#                 'broken_links': broken_links,
#                 'first_record_hash': first_record.record_hash if first_record else None,
#                 'last_record_hash': last_record.record_hash if last_record else None,
#                 'verification_timestamp': timezone.now(),
#             }
            
#             serializer = ChainVerificationSerializer(data=verification_data)
#             if serializer.is_valid():
#                 return Response(serializer.data)
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         except Exception as e:
#             logger.error(f"Error verifying chain: {str(e)}")
#             return Response(
#                 {'error': f'Chain verification failed: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     @action(detail=False, methods=['get'])
#     def search(self, request):
#         """
#         Advanced search for audit logs.
#         """
#         serializer = AuditSearchSerializer(data=request.query_params)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         try:
#             # Start with base queryset
#             queryset = self.get_queryset()
            
#             # Apply filters
#             data = serializer.validated_data
            
#             if data.get('q'):
#                 queryset = queryset.filter(
#                     Q(model_name__icontains=data['q']) |
#                     Q(object_id__icontains=data['q']) |
#                     Q(action__icontains=data['q']) |
#                     Q(user__email__icontains=data['q'])
#                 )
            
#             if data.get('model_name'):
#                 queryset = queryset.filter(model_name=data['model_name'])
            
#             if data.get('action'):
#                 queryset = queryset.filter(action=data['action'])
            
#             if data.get('user_id'):
#                 queryset = queryset.filter(user_id=data['user_id'])
            
#             if data.get('branch_id'):
#                 queryset = queryset.filter(branch_id=data['branch_id'])
            
#             if data.get('date_from'):
#                 queryset = queryset.filter(timestamp__gte=data['date_from'])
            
#             if data.get('date_to'):
#                 queryset = queryset.filter(timestamp__lte=data['date_to'])
            
#             if data.get('object_id'):
#                 queryset = queryset.filter(object_id=data['object_id'])
            
#             # Apply sorting
#             sort_by = data.get('sort_by', 'timestamp')
#             sort_order = data.get('sort_order', 'desc')
            
#             if sort_order == 'desc':
#                 sort_by = f'-{sort_by}'
            
#             queryset = queryset.order_by(sort_by)
            
#             # Paginate
#             page = self.paginate_queryset(queryset)
#             if page is not None:
#                 serializer = AuditLogListSerializer(page, many=True)
#                 return self.get_paginated_response(serializer.data)
            
#             # If no pagination, return all
#             serializer = AuditLogListSerializer(queryset, many=True)
#             return Response(serializer.data)
        
#         except Exception as e:
#             logger.error(f"Error searching audit logs: {str(e)}")
#             return Response(
#                 {'error': f'Search failed: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     @action(detail=True, methods=['get'])
#     def trail(self, request, pk=None):
#         """
#         Get complete audit trail for a specific object.
#         """
#         audit_log = self.get_object()
        
#         # Get audit trail for this object
#         trail_queryset = get_audit_trail(
#             audit_log.model_name,
#             audit_log.object_id,
#             limit=100
#         )
        
#         if trail_queryset.exists():
#             first_log = trail_queryset.last()  # Oldest
#             last_log = trail_queryset.first()  # Newest
            
#             trail_data = {
#                 'object_id': audit_log.object_id,
#                 'model_name': audit_log.model_name,
#                 'total_logs': trail_queryset.count(),
#                 'first_log': first_log.timestamp,
#                 'last_log': last_log.timestamp,
#                 'logs': trail_queryset
#             }
            
#             serializer = AuditTrailSerializer(trail_data)
#             return Response(serializer.data)
        
#         return Response(
#             {'error': 'No audit trail found for this object'},
#             status=status.HTTP_404_NOT_FOUND
#         )
    
#     @action(detail=True, methods=['get'])
#     def diff(self, request, pk=None):
#         """
#         Compare this audit log with another.
#         """
#         compare_with = request.query_params.get('compare_with')
        
#         if not compare_with:
#             return Response(
#                 {'error': 'compare_with parameter required'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         try:
#             current_log = self.get_object()
#             other_log = get_object_or_404(AuditLog, id=compare_with)
            
#             # Ensure same object
#             if (current_log.model_name != other_log.model_name or 
#                 current_log.object_id != other_log.object_id):
#                 return Response(
#                     {'error': 'Can only compare logs for the same object'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
            
#             # Calculate differences
#             differences = []
#             if current_log.before and other_log.before:
#                 # Compare before states
#                 pass
#             elif current_log.after and other_log.after:
#                 # Compare after states
#                 pass
            
#             diff_data = {
#                 'log1': current_log,
#                 'log2': other_log,
#                 'differences': differences
#             }
            
#             serializer = AuditLogDiffSerializer(diff_data)
#             return Response(serializer.data)
        
#         except Exception as e:
#             logger.error(f"Error comparing audit logs: {str(e)}")
#             return Response(
#                 {'error': f'Comparison failed: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


# # ============================
# # Additional Views
# # ============================

# class ObjectAuditTrailView(generics.ListAPIView):
#     """
#     Get audit trail for any object by model name and object ID.
#     """
#     permission_classes = [IsAuthenticated, IsAuditor]
#     serializer_class = AuditLogSerializer
#     pagination_class = AuditLogPagination
    
#     def get_queryset(self):
#         model_name = self.kwargs.get('model_name')
#         object_id = self.kwargs.get('object_id')
        
#         if not model_name or not object_id:
#             return AuditLog.objects.none()
        
#         queryset = AuditLog.objects.filter(
#             model_name=model_name,
#             object_id=str(object_id)
#         ).order_by('-timestamp')
        
#         # Apply permission filtering
#         user = self.request.user
        
#         if not (user.is_superuser or user.is_admin()):
#             if user.is_manager():
#                 user_branches = user.user_branches.filter(
#                     is_active=True
#                 ).values_list('branch_id', flat=True)
                
#                 if user_branches:
#                     queryset = queryset.filter(branch_id__in=user_branches)
#                 else:
#                     return AuditLog.objects.none()
#             else:
#                 # Regular users can only see their own actions
#                 queryset = queryset.filter(user=user)
        
#         return queryset
    
#     def list(self, request, *args, **kwargs):
#         queryset = self.get_queryset()
        
#         if not queryset.exists():
#             return Response(
#                 {'error': 'No audit trail found for this object'},
#                 status=status.HTTP_404_NOT_FOUND
#             )
        
#         # Get summary info
#         first_log = queryset.last()  # Oldest
#         last_log = queryset.first()  # Newest
        
#         # Paginate
#         page = self.paginate_queryset(queryset)
#         if page is not None:
#             serializer = self.get_serializer(page, many=True)
#             response_data = {
#                 'object_id': self.kwargs.get('object_id'),
#                 'model_name': self.kwargs.get('model_name'),
#                 'total_logs': queryset.count(),
#                 'first_log': first_log.timestamp,
#                 'last_log': last_log.timestamp,
#                 'logs': serializer.data
#             }
            
#             # Use pagination response
#             return self.get_paginated_response(response_data)
        
#         # If no pagination
#         serializer = self.get_serializer(queryset, many=True)
#         trail_data = {
#             'object_id': self.kwargs.get('object_id'),
#             'model_name': self.kwargs.get('model_name'),
#             'total_logs': queryset.count(),
#             'first_log': first_log.timestamp,
#             'last_log': last_log.timestamp,
#             'logs': serializer.data
#         }
        
#         return Response(trail_data)


# class UserAuditLogsView(generics.ListAPIView):
#     """
#     Get audit logs for a specific user.
#     """
#     permission_classes = [IsAuthenticated, IsAuditor]
#     serializer_class = AuditLogListSerializer
#     pagination_class = AuditLogPagination
    
#     def get_queryset(self):
#         user_id = self.kwargs.get('user_id')
        
#         queryset = AuditLog.objects.filter(user_id=user_id).order_by('-timestamp')
        
#         # Apply permission filtering
#         current_user = self.request.user
        
#         if not (current_user.is_superuser or current_user.is_admin()):
#             if current_user.is_manager():
#                 # Managers can only see users in their branches
#                 user_branches = current_user.user_branches.filter(
#                     is_active=True
#                 ).values_list('branch_id', flat=True)
                
#                 if user_branches:
#                     queryset = queryset.filter(branch_id__in=user_branches)
#                 else:
#                     return AuditLog.objects.none()
#             else:
#                 # Regular users can only see their own logs
#                 if int(user_id) != current_user.id:
#                     return AuditLog.objects.none()
        
#         return queryset


# class BranchAuditLogsView(generics.ListAPIView):
#     """
#     Get audit logs for a specific branch.
#     """
#     permission_classes = [IsAuthenticated, IsAuditor]
#     serializer_class = AuditLogListSerializer
#     pagination_class = AuditLogPagination
    
#     def get_queryset(self):
#         branch_id = self.kwargs.get('branch_id')
        
#         queryset = AuditLog.objects.filter(branch_id=branch_id).order_by('-timestamp')
        
#         # Apply permission filtering
#         user = self.request.user
        
#         if not (user.is_superuser or user.is_admin()):
#             if user.is_manager():
#                 # Check if user has access to this branch
#                 if not user.user_branches.filter(branch_id=branch_id, is_active=True).exists():
#                     return AuditLog.objects.none()
#             else:
#                 # Regular users can only see their own actions in their branch
#                 user_branch = getattr(user, 'current_branch', None)
#                 if not user_branch or user_branch.id != int(branch_id):
#                     return AuditLog.objects.none()
                
#                 queryset = queryset.filter(user=user)
        
#         return queryset


# class LiveAuditFeedView(APIView):
#     """
#     Real-time audit feed (SSE/WebSocket ready).
#     """
#     permission_classes = [IsAuthenticated, IsAuditor]
    
#     def get(self, request):
#         """
#         Get recent audit logs for live feed.
#         Uses Server-Sent Events (SSE) format.
#         """
#         # Check if client accepts SSE
#         accept = request.META.get('HTTP_ACCEPT', '')
#         if 'text/event-stream' in accept:
#             # SSE setup
#             response = HttpResponse(
#                 self.generate_sse(request),
#                 content_type='text/event-stream'
#             )
#             response['Cache-Control'] = 'no-cache'
#             response['X-Accel-Buffering'] = 'no'
#             return response
        
#         # Regular JSON response (last 50 logs)
#         queryset = self.get_queryset()[:50]
#         serializer = AuditLogListSerializer(queryset, many=True)
#         return Response(serializer.data)
    
#     def get_queryset(self):
#         """
#         Get filtered queryset for live feed.
#         """
#         queryset = AuditLog.objects.all().order_by('-timestamp')
        
#         # Apply permission filtering
#         user = self.request.user
        
#         if not (user.is_superuser or user.is_admin()):
#             if user.is_manager():
#                 user_branches = user.user_branches.filter(
#                     is_active=True
#                 ).values_list('branch_id', flat=True)
                
#                 if user_branches:
#                     queryset = queryset.filter(branch_id__in=user_branches)
#                 else:
#                     return AuditLog.objects.none()
#             else:
#                 # Regular users can only see their own actions
#                 queryset = queryset.filter(user=user)
        
#         return queryset
    
#     def generate_sse(self, request):
#         """
#         Generate Server-Sent Events stream.
#         """
#         import time
        
#         last_id = request.GET.get('last_id', 0)
        
#         try:
#             while True:
#                 # Check if client disconnected
#                 if request.META.get('wsgi.disconnected', False):
#                     break
                
#                 # Get new logs since last_id
#                 new_logs = self.get_queryset().filter(
#                     id__gt=last_id
#                 ).order_by('id')[:10]
                
#                 if new_logs.exists():
#                     for log in new_logs:
#                         serializer = AuditLogListSerializer(log)
#                         yield f"id: {log.id}\n"
#                         yield f"event: audit\n"
#                         yield f"data: {json.dumps(serializer.data)}\n\n"
                    
#                     last_id = new_logs.last().id
                
#                 # Send heartbeat
#                 yield f"id: heartbeat\n"
#                 yield f"event: heartbeat\n"
#                 yield f"data: {time.time()}\n\n"
                
#                 time.sleep(5)  # Check every 5 seconds
        
#         except GeneratorExit:
#             # Client disconnected
#             pass


# # ============================
# # Webhook/Alert Views
# # ============================

# @api_view(['POST'])
# @permission_classes([AllowAny])
# def audit_webhook(request):
#     """
#     Receive audit webhooks from external systems.
#     """
#     try:
#         serializer = AuditWebhookSerializer(data=request.data)
#         if not serializer.is_valid():
#             logger.warning(f"Invalid webhook data: {serializer.errors}")
#             return Response(
#                 {'error': 'Invalid webhook data'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         data = serializer.validated_data
        
#         # Verify signature if provided
#         signature = data.get('signature')
#         if signature:
#             # Implement signature verification
#             # e.g., HMAC with shared secret
#             pass
        
#         # Process webhook
#         event_type = data['event_type']
#         log_data = data['data']
        
#         # Log the webhook as an audit event
#         webhook_log = AuditLog.objects.create(
#             branch=None,  # External system
#             user=None,
#             action=f'WEBHOOK_{event_type}',
#             model_name='ExternalSystem',
#             object_id=f"webhook_{data['log_id']}",
#             before=None,
#             after=log_data,
#             device_id=request.META.get('HTTP_USER_AGENT', ''),
#             ip_address=request.META.get('REMOTE_ADDR'),
#         )
        
#         # Trigger alerts if needed
#         if event_type in ['SUSPICIOUS', 'UNAUTHORIZED', 'TAMPERING']:
#             # Create alert
#             alert_data = {
#                 'alert_type': 'SUSPICIOUS_ACTIVITY',
#                 'severity': 'HIGH',
#                 'message': f'Suspicious activity from external system: {event_type}',
#                 'details': log_data,
#                 'timestamp': timezone.now(),
#                 'resolved': False
#             }
            
#             # Store alert (could be in database or send notification)
#             logger.warning(f"Alert triggered: {alert_data}")
        
#         return Response(
#             {'success': True, 'message': 'Webhook received'},
#             status=status.HTTP_200_OK
#         )
    
#     except Exception as e:
#         logger.error(f"Error processing webhook: {str(e)}")
#         return Response(
#             {'error': f'Webhook processing failed: {str(e)}'},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )


# class AuditAlertsView(generics.ListAPIView):
#     """
#     View and manage audit alerts.
#     """
#     permission_classes = [IsAuthenticated, IsAdminUser]
#     serializer_class = AuditAlertSerializer
    
#     def get_queryset(self):
#         """
#         In a real implementation, this would query an Alert model.
#         For now, we'll generate mock data.
#         """
#         # This is a placeholder - implement with actual Alert model
#         return []
    
#     @action(detail=False, methods=['post'])
#     def resolve(self, request):
#         """
#         Mark alerts as resolved.
#         """
#         alert_ids = request.data.get('alert_ids', [])
        
#         # In real implementation, update Alert model
#         # Alert.objects.filter(id__in=alert_ids).update(resolved=True, resolved_by=request.user)
        
#         return Response({
#             'success': True,
#             'message': f'Resolved {len(alert_ids)} alerts',
#             'resolved_count': len(alert_ids)
#         })


# # ============================
# # Utility Views
# # ============================

# @api_view(['POST'])
# @permission_classes([IsAuthenticated, IsAdminUser])
# def manual_audit_log(request):
#     """
#     Manually create an audit log entry (for testing/backfilling).
#     """
#     try:
#         # Extract data from request
#         data = request.data
        
#         # Validate required fields
#         required_fields = ['action', 'model_name', 'object_id']
#         for field in required_fields:
#             if field not in data:
#                 return Response(
#                     {'error': f'Missing required field: {field}'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
        
#         # Create audit log
#         audit_log = AuditLog.objects.create(
#             branch_id=data.get('branch_id'),
#             user=request.user,
#             device_id=data.get('device_id'),
#             ip_address=data.get('ip_address'),
#             action=data['action'],
#             model_name=data['model_name'],
#             object_id=str(data['object_id']),
#             before=data.get('before'),
#             after=data.get('after'),
#             duration=timedelta(seconds=data['duration']) if 'duration' in data else None,
#         )
        
#         serializer = AuditLogSerializer(audit_log)
        
#         response_data = {
#             'success': True,
#             'message': 'Audit log created manually',
#             'log_id': audit_log.id,
#             'data': serializer.data,
#             'timestamp': timezone.now()
#         }
        
#         response_serializer = AuditLogResponseSerializer(data=response_data)
#         if response_serializer.is_valid():
#             return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
#         return Response(response_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
#     except Exception as e:
#         logger.error(f"Error creating manual audit log: {str(e)}")
#         return Response(
#             {'error': f'Manual audit log creation failed: {str(e)}'},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )


# @api_view(['POST'])
# @permission_classes([IsAuthenticated, IsAdminUser])
# def bulk_audit_logs(request):
#     """
#     Create multiple audit logs in bulk.
#     """
#     try:
#         logs_data = request.data.get('logs', [])
        
#         if not logs_data:
#             return Response(
#                 {'error': 'No logs provided'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         successful = 0
#         failed = 0
#         failed_details = []
        
#         with transaction.atomic():
#             for log_data in logs_data:
#                 try:
#                     # Create audit log
#                     AuditLog.objects.create(
#                         branch_id=log_data.get('branch_id'),
#                         user_id=log_data.get('user_id'),
#                         device_id=log_data.get('device_id'),
#                         ip_address=log_data.get('ip_address'),
#                         action=log_data.get('action', 'MANUAL'),
#                         model_name=log_data.get('model_name', 'Unknown'),
#                         object_id=str(log_data.get('object_id', '0')),
#                         before=log_data.get('before'),
#                         after=log_data.get('after'),
#                         duration=timedelta(seconds=log_data['duration']) if 'duration' in log_data else None,
#                     )
#                     successful += 1
#                 except Exception as e:
#                     failed += 1
#                     failed_details.append({
#                         'data': log_data,
#                         'error': str(e)
#                     })
        
#         response_data = {
#             'success': successful > 0,
#             'message': f'Processed {len(logs_data)} logs',
#             'total_processed': len(logs_data),
#             'successful': successful,
#             'failed': failed,
#             'failed_details': failed_details if failed > 0 else None,
#             'timestamp': timezone.now()
#         }
        
#         serializer = BulkAuditResponseSerializer(data=response_data)
#         if serializer.is_valid():
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
        
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
#     except Exception as e:
#         logger.error(f"Error creating bulk audit logs: {str(e)}")
#         return Response(
#             {'error': f'Bulk audit log creation failed: {str(e)}'},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )


# # ============================
# # Health Check View
# # ============================

# class AuditHealthCheckView(APIView):
#     """
#     Health check for audit system.
#     """
#     permission_classes = [IsAuthenticated, IsAuditor]
    
#     def get(self, request):
#         """
#         Check audit system health.
#         """
#         try:
#             # Check database connection
#             total_logs = AuditLog.objects.count()
            
#             # Check chain integrity
#             broken_links = verify_chain()
#             chain_healthy = len(broken_links) == 0
            
#             # Check recent activity
#             recent_logs = AuditLog.objects.filter(
#                 timestamp__gte=timezone.now() - timedelta(hours=1)
#             ).count()
            
#             # Get oldest and newest logs
#             oldest_log = AuditLog.objects.order_by('timestamp').first()
#             newest_log = AuditLog.objects.order_by('-timestamp').first()
            
#             health_data = {
#                 'status': 'healthy',
#                 'database': 'connected',
#                 'total_logs': total_logs,
#                 'chain_healthy': chain_healthy,
#                 'broken_links': len(broken_links),
#                 'recent_activity': {
#                     'last_hour': recent_logs,
#                     'last_24_hours': AuditLog.objects.filter(
#                         timestamp__gte=timezone.now() - timedelta(days=1)
#                     ).count()
#                 },
#                 'time_range': {
#                     'oldest': oldest_log.timestamp if oldest_log else None,
#                     'newest': newest_log.timestamp if newest_log else None,
#                 },
#                 'timestamp': timezone.now()
#             }
            
#             return Response(health_data)
        
#         except Exception as e:
#             logger.error(f"Audit health check failed: {str(e)}")
#             return Response(
#                 {
#                     'status': 'unhealthy',
#                     'error': str(e),
#                     'timestamp': timezone.now()
#                 },
#                 status=status.HTTP_503_SERVICE_UNAVAILABLE
#             )