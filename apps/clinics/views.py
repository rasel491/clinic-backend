# # Backend/apps/clinics/views.py
# from rest_framework import serializers
# from rest_framework import viewsets, status, filters, generics
# from rest_framework.decorators import action, api_view, permission_classes
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated, AllowAny
# from rest_framework.views import APIView
# from rest_framework.pagination import PageNumberPagination
# from django.utils import timezone
# from django.db.models import Q, Count, Sum, Avg, Max, Min
# from django.db import transaction
# from django.http import HttpResponse, JsonResponse
# from django.shortcuts import get_object_or_404
# from datetime import timedelta, datetime
# import json
# import csv
# from io import StringIO, BytesIO
# import pandas as pd
# import logging
# from django_filters.rest_framework import DjangoFilterBackend

# from core.permissions import (
#     IsAdminUser,           # For super admin
#     IsManager,             # For clinic manager (includes super admin)
#     IsDoctor,              # For doctors
#     IsReceptionist,        # For receptionists
#     IsCashier,             # For cashiers
#     IsStaff,               # For all staff
#     HasBranchAccess,       # For branch-scoped access
#     CanOverride,           # For override actions
#     IsAuthenticatedAndActive,  # For basic auth check
# )

# from .models import Branch, Counter
# from .serializers import (
#     BranchSerializer,
#     BranchCreateSerializer,
#     BranchUpdateSerializer,
#     BranchListSerializer,
#     BranchEODSerializer,
#     BranchStatsSerializer,
#     BranchConfigurationSerializer,
#     BranchOperationalHoursSerializer,
#     BranchImportSerializer,
#     BranchExportSerializer,
#     BranchSearchSerializer,
#     BranchGeoSerializer,
#     BranchSyncSerializer,
#     CounterSerializer,
#     CounterCreateSerializer,
#     CounterListSerializer,
#     CounterAssignmentSerializer,
#     CounterStatsSerializer,
# )
# from apps.accounts.models import User
# from apps.eod.services import EodService
# from apps.audit.services import log_action, attach_audit_context

# logger = logging.getLogger(__name__)


# # ============================
# # Custom Pagination
# # ============================

# class BranchPagination(PageNumberPagination):
#     """Custom pagination for branches"""
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


# class CounterPagination(PageNumberPagination):
#     """Custom pagination for counters"""
#     page_size = 50
#     page_size_query_param = 'page_size'
#     max_page_size = 200
    
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
# # Branch ViewSet
# # ============================

# class BranchViewSet(viewsets.ModelViewSet):
#     """
#     ViewSet for managing branches.
#     """
#     queryset = Branch.objects.filter(deleted_at__isnull=True)
#     serializer_class = BranchSerializer
#     permission_classes = [IsAuthenticated, IsManager]
#     pagination_class = BranchPagination
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     search_fields = ['name', 'code', 'address', 'phone', 'email']
#     ordering_fields = ['name', 'code', 'created_at', 'is_active']
#     ordering = ['name']
    
#     def get_queryset(self):
#         """
#         Filter queryset based on user permissions.
#         """
#         queryset = super().get_queryset()
        
#         # Superusers can see all
#         if self.request.user.is_superuser or self.request.user.is_admin():
#             return queryset
        
#         # Managers can see their assigned branches
#         if self.request.user.is_manager():
#             # Get user's assigned branches
#             user_branches = self.request.user.user_branches.filter(
#                 is_active=True
#             ).values_list('branch_id', flat=True)
            
#             if user_branches:
#                 return queryset.filter(id__in=user_branches)
#             else:
#                 # No branch assigned - return empty
#                 return queryset.none()
        
#         # Doctors and staff can see their current branch
#         if hasattr(self.request.user, 'current_branch'):
#             return queryset.filter(id=self.request.user.current_branch.id)
        
#         # Others can see active branches only
#         return queryset.filter(is_active=True)
    
#     def get_serializer_class(self):
#         """
#         Use different serializers based on action.
#         """
#         if self.action == 'list':
#             return BranchListSerializer
#         elif self.action == 'create':
#             return BranchCreateSerializer
#         elif self.action == 'update' or self.action == 'partial_update':
#             return BranchUpdateSerializer
#         return super().get_serializer_class()
    
#     def perform_create(self, serializer):
#         """Create branch with audit logging"""
#         with transaction.atomic():
#             # Attach audit context
#             attach_audit_context(serializer, self.request)
            
#             # Save branch
#             branch = serializer.save(
#                 created_by=self.request.user,
#                 updated_by=self.request.user
#             )
            
#             # Log creation
#             log_action(
#                 instance=branch,
#                 action='CREATE',
#                 user=self.request.user,
#                 branch=branch,
#                 device_id=self.request.META.get('HTTP_X_DEVICE_ID'),
#                 ip_address=self.request.META.get('REMOTE_ADDR'),
#             )
            
#             logger.info(f"Branch created: {branch.code} by {self.request.user}")
    
#     def perform_update(self, serializer):
#         """Update branch with audit logging"""
#         with transaction.atomic():
#             # Check EOD lock
#             branch = self.get_object()
            
#             if branch.is_eod_locked:
#                 # Check if trying to modify restricted fields
#                 restricted_fields = ['opening_time', 'closing_time', 'is_active']
#                 for field in restricted_fields:
#                     if field in serializer.validated_data:
#                         raise serializers.ValidationError({
#                             field: f'Cannot modify {field} when EOD is locked'
#                         })
            
#             # Attach audit context
#             attach_audit_context(serializer, self.request)
            
#             # Save updates
#             updated_branch = serializer.save(
#                 updated_by=self.request.user
#             )
            
#             # Log update
#             log_action(
#                 instance=updated_branch,
#                 action='UPDATE',
#                 user=self.request.user,
#                 branch=updated_branch,
#                 device_id=self.request.META.get('HTTP_X_DEVICE_ID'),
#                 ip_address=self.request.META.get('REMOTE_ADDR'),
#             )
            
#             logger.info(f"Branch updated: {updated_branch.code} by {self.request.user}")
    
#     def perform_destroy(self, instance):
#         """Soft delete branch with audit logging"""
#         with transaction.atomic():
#             # Check if branch has active appointments or transactions
#             from apps.visits.models import Appointment
#             from apps.billing.models import Invoice
            
#             active_appointments = Appointment.objects.filter(
#                 branch=instance,
#                 status__in=['scheduled', 'confirmed']
#             ).exists()
            
#             pending_invoices = Invoice.objects.filter(
#                 branch=instance,
#                 payment_status='pending'
#             ).exists()
            
#             if active_appointments or pending_invoices:
#                 raise serializers.ValidationError(
#                     "Cannot delete branch with active appointments or pending invoices"
#                 )
            
#             # Soft delete
#             instance.deleted_at = timezone.now()
#             instance.deleted_by = self.request.user
#             instance.is_active = False
#             instance.save()
            
#             # Log deletion
#             log_action(
#                 instance=instance,
#                 action='DELETE',
#                 user=self.request.user,
#                 branch=instance,
#                 device_id=self.request.META.get('HTTP_X_DEVICE_ID'),
#                 ip_address=self.request.META.get('REMOTE_ADDR'),
#             )
            
#             logger.info(f"Branch soft deleted: {instance.code} by {self.request.user}")
    
#     @action(detail=True, methods=['post'])
#     def eod_lock(self, request, pk=None):
#         """
#         Lock branch for End of Day.
#         Only managers and admins can perform this.
#         """
#         branch = self.get_object()
        
#         # Check permissions
#         if not (request.user.is_superuser or request.user.is_admin() or request.user.is_manager()):
#             return Response(
#                 {'error': 'Permission denied. Only managers and admins can lock EOD.'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         # Check if already locked
#         if branch.is_eod_locked:
#             return Response(
#                 {'error': 'Branch EOD is already locked'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         # Validate using EOD service
#         eod_service = EodService()
        
#         try:
#             # Check if EOD can be locked
#             can_lock, message = eod_service.can_lock_branch(branch)
            
#             if not can_lock:
#                 return Response(
#                     {'error': f'Cannot lock EOD: {message}'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
            
#             # Perform EOD lock
#             with transaction.atomic():
#                 branch.lock_eod(user=request.user)
                
#                 # Log EOD lock
#                 log_action(
#                     instance=branch,
#                     action='EOD_LOCK',
#                     user=request.user,
#                     branch=branch,
#                     device_id=request.META.get('HTTP_X_DEVICE_ID'),
#                     ip_address=request.META.get('REMOTE_ADDR'),
#                 )
                
#                 # Create EOD record
#                 eod_service.create_eod_record(branch, request.user)
                
#                 logger.info(f"Branch EOD locked: {branch.code} by {request.user}")
                
#                 return Response({
#                     'success': True,
#                     'message': f'EOD locked for branch {branch.name}',
#                     'locked_at': branch.eod_locked_at,
#                     'locked_by': request.user.email
#                 })
        
#         except Exception as e:
#             logger.error(f"Error locking EOD for branch {branch.code}: {str(e)}")
#             return Response(
#                 {'error': f'Failed to lock EOD: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     @action(detail=True, methods=['post'])
#     def eod_unlock(self, request, pk=None):
#         """
#         Unlock branch (admin only for security).
#         """
#         branch = self.get_object()
        
#         # Only superusers and admins can unlock
#         if not (request.user.is_superuser or request.user.is_admin()):
#             return Response(
#                 {'error': 'Permission denied. Only admins can unlock EOD.'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         # Check if actually locked
#         if not branch.is_eod_locked:
#             return Response({
#                 'success': True,
#                 'message': 'Branch is not locked',
#                 'already_unlocked': True
#             })
        
#         # Perform unlock
#         with transaction.atomic():
#             branch.is_eod_locked = False
#             branch.eod_locked_at = None
#             branch.eod_locked_by = None
#             branch.save()
            
#             # Log EOD unlock
#             log_action(
#                 instance=branch,
#                 action='EOD_UNLOCK',
#                 user=request.user,
#                 branch=branch,
#                 device_id=request.META.get('HTTP_X_DEVICE_ID'),
#                 ip_address=request.META.get('REMOTE_ADDR'),
#             )
            
#             logger.info(f"Branch EOD unlocked: {branch.code} by {request.user}")
            
#             return Response({
#                 'success': True,
#                 'message': f'EOD unlocked for branch {branch.name}',
#                 'unlocked_at': timezone.now(),
#                 'unlocked_by': request.user.email
#             })
    
#     @action(detail=True, methods=['get'])
#     def stats(self, request, pk=None):
#         """
#         Get detailed statistics for a branch.
#         """
#         branch = self.get_object()
        
#         try:
#             from apps.patients.models import Patient
#             from apps.visits.models import Appointment
#             from apps.billing.models import Invoice
#             from apps.accounts.models import UserBranch
            
#             today = timezone.now().date()
#             week_ago = today - timedelta(days=7)
            
#             # Patient statistics
#             total_patients = Patient.objects.filter(branch=branch).count()
            
#             # Appointment statistics
#             todays_appointments = Appointment.objects.filter(
#                 branch=branch,
#                 appointment_date=today,
#                 status__in=['scheduled', 'confirmed', 'completed']
#             ).count()
            
#             weeks_appointments = Appointment.objects.filter(
#                 branch=branch,
#                 appointment_date__gte=week_ago,
#                 appointment_date__lte=today,
#                 status__in=['scheduled', 'confirmed', 'completed']
#             ).count()
            
#             # Staff statistics
#             active_staff = UserBranch.objects.filter(
#                 branch=branch,
#                 is_active=True
#             ).count()
            
#             # Counter statistics
#             active_counters = Counter.objects.filter(
#                 branch=branch,
#                 is_active=True
#             ).count()
            
#             # Financial statistics
#             todays_invoices = Invoice.objects.filter(
#                 branch=branch,
#                 created_at__date=today,
#                 payment_status='paid'
#             )
#             todays_revenue = todays_invoices.aggregate(
#                 total=Sum('total_amount')
#             )['total'] or 0
            
#             weeks_invoices = Invoice.objects.filter(
#                 branch=branch,
#                 created_at__date__gte=week_ago,
#                 created_at__date__lte=today,
#                 payment_status='paid'
#             )
#             weeks_revenue = weeks_invoices.aggregate(
#                 total=Sum('total_amount')
#             )['total'] or 0
            
#             pending_payments = Invoice.objects.filter(
#                 branch=branch,
#                 payment_status='pending'
#             ).aggregate(
#                 total=Sum('total_amount')
#             )['total'] or 0
            
#             # EOD status
#             days_since_lock = None
#             if branch.eod_locked_at:
#                 days_since_lock = (timezone.now() - branch.eod_locked_at).days
            
#             # Occupancy statistics
#             avg_daily_appointments = Appointment.objects.filter(
#                 branch=branch,
#                 appointment_date__gte=today - timedelta(days=30),
#                 status='completed'
#             ).values('appointment_date').annotate(
#                 count=Count('id')
#             ).aggregate(
#                 avg=Avg('count')
#             )['avg'] or 0
            
#             # Max capacity (assuming 8 working hours, 30 min appointments)
#             max_daily_capacity = 16  # 8 hours * 2 appointments per hour
#             current_occupancy = (todays_appointments / max_daily_capacity * 100) if max_daily_capacity > 0 else 0
            
#             # Prepare response
#             stats_data = {
#                 'branch_id': branch.id,
#                 'branch_name': branch.name,
#                 'branch_code': branch.code,
#                 'total_patients': total_patients,
#                 'total_appointments_today': todays_appointments,
#                 'total_appointments_week': weeks_appointments,
#                 'active_staff': active_staff,
#                 'active_counters': active_counters,
#                 'todays_revenue': float(todays_revenue),
#                 'weeks_revenue': float(weeks_revenue),
#                 'pending_payments': float(pending_payments),
#                 'eod_locked': branch.is_eod_locked,
#                 'eod_locked_at': branch.eod_locked_at,
#                 'days_since_last_lock': days_since_lock,
#                 'current_occupancy': round(current_occupancy, 2),
#                 'average_daily_appointments': round(avg_daily_appointments, 2),
#             }
            
#             serializer = BranchStatsSerializer(data=stats_data)
#             if serializer.is_valid():
#                 return Response(serializer.data)
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         except Exception as e:
#             logger.error(f"Error getting branch stats: {str(e)}")
#             return Response(
#                 {'error': f'Failed to get statistics: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     @action(detail=False, methods=['get'])
#     def all_stats(self, request):
#         """
#         Get statistics for all branches (admin/manager only).
#         """
#         # Check permissions
#         if not (request.user.is_superuser or request.user.is_admin() or request.user.is_manager()):
#             return Response(
#                 {'error': 'Permission denied'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         branches = self.get_queryset()
#         all_stats = []
        
#         for branch in branches:
#             try:
#                 # Get basic stats for each branch
#                 stats_data = {
#                     'branch_id': branch.id,
#                     'branch_name': branch.name,
#                     'branch_code': branch.code,
#                     'is_active': branch.is_active,
#                     'is_eod_locked': branch.is_eod_locked,
#                     'eod_locked_at': branch.eod_locked_at,
#                     'active_counters': branch.counters.filter(is_active=True).count(),
#                     'todays_appointments': 0,  # You would calculate this
#                 }
#                 all_stats.append(stats_data)
#             except Exception as e:
#                 logger.error(f"Error getting stats for branch {branch.code}: {str(e)}")
#                 continue
        
#         return Response(all_stats)
    
#     @action(detail=True, methods=['get', 'put'])
#     def configuration(self, request, pk=None):
#         """
#         Get or update branch configuration.
#         """
#         branch = self.get_object()
        
#         if request.method == 'GET':
#             # Get configuration from settings_core or branch settings
#             try:
#                 from apps.settings_core.models import BranchSetting
                
#                 # Get branch-specific settings
#                 settings = BranchSetting.objects.filter(branch=branch).values('key', 'value')
                
#                 # Convert to configuration format
#                 config_data = {}
#                 for setting in settings:
#                     config_data[setting['key']] = setting['value']
                
#                 serializer = BranchConfigurationSerializer(data=config_data)
#                 if serializer.is_valid():
#                     return Response(serializer.data)
                
#                 return Response(config_data)
            
#             except Exception as e:
#                 logger.error(f"Error getting branch configuration: {str(e)}")
#                 # Return default configuration
#                 serializer = BranchConfigurationSerializer(data={})
#                 if serializer.is_valid():
#                     return Response(serializer.data)
#                 return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         elif request.method == 'PUT':
#             # Update configuration
#             if not (request.user.is_superuser or request.user.is_admin() or request.user.is_manager()):
#                 return Response(
#                     {'error': 'Permission denied'},
#                     status=status.HTTP_403_FORBIDDEN
#                 )
            
#             serializer = BranchConfigurationSerializer(data=request.data)
#             if not serializer.is_valid():
#                 return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
#             try:
#                 with transaction.atomic():
#                     from apps.settings_core.models import BranchSetting
                    
#                     config_data = serializer.validated_data
                    
#                     # Save each setting
#                     for key, value in config_data.items():
#                         BranchSetting.objects.update_or_create(
#                             branch=branch,
#                             key=key,
#                             defaults={
#                                 'value': value,
#                                 'updated_by': request.user
#                             }
#                         )
                    
#                     # Log configuration change
#                     log_action(
#                         instance=branch,
#                         action='CONFIG_UPDATE',
#                         user=request.user,
#                         branch=branch,
#                         device_id=request.META.get('HTTP_X_DEVICE_ID'),
#                         ip_address=request.META.get('REMOTE_ADDR'),
#                         metadata={'config': config_data}
#                     )
                    
#                     logger.info(f"Branch configuration updated: {branch.code} by {request.user}")
                    
#                     return Response({
#                         'success': True,
#                         'message': 'Configuration updated successfully',
#                         'config': config_data
#                     })
            
#             except Exception as e:
#                 logger.error(f"Error updating branch configuration: {str(e)}")
#                 return Response(
#                     {'error': f'Failed to update configuration: {str(e)}'},
#                     status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
    
#     @action(detail=True, methods=['get', 'put'])
#     def operational_hours(self, request, pk=None):
#         """
#         Get or update operational hours.
#         """
#         branch = self.get_object()
        
#         if request.method == 'GET':
#             # Get operational hours from settings
#             try:
#                 from apps.settings_core.models import BranchSetting
                
#                 hours_setting = BranchSetting.objects.filter(
#                     branch=branch,
#                     key='operational_hours'
#                 ).first()
                
#                 if hours_setting:
#                     return Response(hours_setting.value)
                
#                 # Default operational hours
#                 default_hours = [
#                     {'day': 'monday', 'is_open': True, 'opening_time': '09:00', 'closing_time': '18:00'},
#                     {'day': 'tuesday', 'is_open': True, 'opening_time': '09:00', 'closing_time': '18:00'},
#                     {'day': 'wednesday', 'is_open': True, 'opening_time': '09:00', 'closing_time': '18:00'},
#                     {'day': 'thursday', 'is_open': True, 'opening_time': '09:00', 'closing_time': '18:00'},
#                     {'day': 'friday', 'is_open': True, 'opening_time': '09:00', 'closing_time': '18:00'},
#                     {'day': 'saturday', 'is_open': True, 'opening_time': '09:00', 'closing_time': '14:00'},
#                     {'day': 'sunday', 'is_open': False},
#                 ]
                
#                 return Response(default_hours)
            
#             except Exception as e:
#                 logger.error(f"Error getting operational hours: {str(e)}")
#                 return Response(
#                     {'error': f'Failed to get operational hours: {str(e)}'},
#                     status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
        
#         elif request.method == 'PUT':
#             # Update operational hours
#             if not (request.user.is_superuser or request.user.is_admin() or request.user.is_manager()):
#                 return Response(
#                     {'error': 'Permission denied'},
#                     status=status.HTTP_403_FORBIDDEN
#                 )
            
#             serializer = BranchOperationalHoursSerializer(data=request.data, many=True)
#             if not serializer.is_valid():
#                 return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
#             try:
#                 with transaction.atomic():
#                     from apps.settings_core.models import BranchSetting
                    
#                     hours_data = serializer.validated_data
                    
#                     # Save operational hours
#                     BranchSetting.objects.update_or_create(
#                         branch=branch,
#                         key='operational_hours',
#                         defaults={
#                             'value': hours_data,
#                             'updated_by': request.user
#                         }
#                     )
                    
#                     # Log hours change
#                     log_action(
#                         instance=branch,
#                         action='HOURS_UPDATE',
#                         user=request.user,
#                         branch=branch,
#                         device_id=request.META.get('HTTP_X_DEVICE_ID'),
#                         ip_address=request.META.get('REMOTE_ADDR'),
#                         metadata={'hours': hours_data}
#                     )
                    
#                     logger.info(f"Operational hours updated: {branch.code} by {request.user}")
                    
#                     return Response({
#                         'success': True,
#                         'message': 'Operational hours updated successfully',
#                         'hours': hours_data
#                     })
            
#             except Exception as e:
#                 logger.error(f"Error updating operational hours: {str(e)}")
#                 return Response(
#                     {'error': f'Failed to update operational hours: {str(e)}'},
#                     status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
    
#     @action(detail=False, methods=['post'])
#     def import_branches(self, request):
#         """
#         Import branches from CSV/Excel file.
#         """
#         if not (request.user.is_superuser or request.user.is_admin()):
#             return Response(
#                 {'error': 'Permission denied. Only admins can import branches.'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         serializer = BranchImportSerializer(data=request.data)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         file = serializer.validated_data['file']
#         overwrite = serializer.validated_data['overwrite']
        
#         try:
#             import pandas as pd
            
#             # Read file based on extension
#             if file.name.endswith('.csv'):
#                 df = pd.read_csv(file)
#             elif file.name.endswith('.xlsx') or file.name.endswith('.xls'):
#                 df = pd.read_excel(file)
#             else:
#                 return Response(
#                     {'error': 'Unsupported file format. Use CSV or Excel.'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
            
#             # Validate required columns
#             required_columns = ['name', 'code', 'address', 'phone', 'opening_time', 'closing_time']
#             missing_columns = [col for col in required_columns if col not in df.columns]
            
#             if missing_columns:
#                 return Response(
#                     {'error': f'Missing required columns: {missing_columns}'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
            
#             imported = 0
#             updated = 0
#             errors = []
            
#             with transaction.atomic():
#                 for index, row in df.iterrows():
#                     try:
#                         branch_data = {
#                             'name': row['name'],
#                             'code': row['code'],
#                             'address': row['address'],
#                             'phone': str(row['phone']),
#                             'opening_time': row['opening_time'],
#                             'closing_time': row['closing_time'],
#                             'email': row.get('email', ''),
#                             'is_active': row.get('is_active', True),
#                         }
                        
#                         # Check if branch exists
#                         existing = Branch.objects.filter(
#                             code=branch_data['code'],
#                             deleted_at__isnull=True
#                         ).first()
                        
#                         if existing and overwrite:
#                             # Update existing branch
#                             serializer = BranchUpdateSerializer(
#                                 existing,
#                                 data=branch_data,
#                                 context={'request': request}
#                             )
                            
#                             if serializer.is_valid():
#                                 serializer.save(updated_by=request.user)
#                                 updated += 1
#                             else:
#                                 errors.append({
#                                     'row': index + 2,  # +2 for header and 0-based index
#                                     'code': branch_data['code'],
#                                     'errors': serializer.errors
#                                 })
                        
#                         elif not existing:
#                             # Create new branch
#                             serializer = BranchCreateSerializer(
#                                 data=branch_data,
#                                 context={'request': request}
#                             )
                            
#                             if serializer.is_valid():
#                                 serializer.save(
#                                     created_by=request.user,
#                                     updated_by=request.user
#                                 )
#                                 imported += 1
#                             else:
#                                 errors.append({
#                                     'row': index + 2,
#                                     'code': branch_data['code'],
#                                     'errors': serializer.errors
#                                 })
                        
#                         else:
#                             # Skip (exists but no overwrite)
#                             pass
                    
#                     except Exception as e:
#                         errors.append({
#                             'row': index + 2,
#                             'code': row.get('code', 'unknown'),
#                             'error': str(e)
#                         })
#                         continue
            
#             return Response({
#                 'success': True,
#                 'imported': imported,
#                 'updated': updated,
#                 'total_rows': len(df),
#                 'errors': errors if errors else None,
#                 'message': f'Imported {imported} new branches, updated {updated} existing branches'
#             })
        
#         except Exception as e:
#             logger.error(f"Error importing branches: {str(e)}")
#             return Response(
#                 {'error': f'Import failed: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     @action(detail=False, methods=['post'])
#     def export_branches(self, request):
#         """
#         Export branches to CSV/Excel/JSON.
#         """
#         if not (request.user.is_superuser or request.user.is_admin()):
#             return Response(
#                 {'error': 'Permission denied. Only admins can export branches.'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         serializer = BranchExportSerializer(data=request.data)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         export_format = serializer.validated_data['format']
#         include_inactive = serializer.validated_data['include_inactive']
#         include_counters = serializer.validated_data['include_counters']
        
#         try:
#             # Get branches
#             branches = self.get_queryset()
            
#             if not include_inactive:
#                 branches = branches.filter(is_active=True)
            
#             # Get counter data if requested
#             counters_data = {}
#             if include_counters:
#                 for branch in branches:
#                     counters = Counter.objects.filter(
#                         branch=branch,
#                         is_active=True
#                     ).values('counter_number', 'name', 'device_id')
#                     counters_data[branch.id] = list(counters)
            
#             if export_format == 'csv':
#                 # Generate CSV
#                 response = HttpResponse(content_type='text/csv')
#                 response['Content-Disposition'] = 'attachment; filename="branches_export.csv"'
                
#                 writer = csv.writer(response)
#                 writer.writerow([
#                     'ID', 'Name', 'Code', 'Address', 'Phone', 'Email',
#                     'Opening Time', 'Closing Time', 'Is Active', 'EOD Locked',
#                     'Created At', 'Updated At'
#                 ])
                
#                 for branch in branches:
#                     writer.writerow([
#                         branch.id,
#                         branch.name,
#                         branch.code,
#                         branch.address,
#                         branch.phone,
#                         branch.email or '',
#                         branch.opening_time,
#                         branch.closing_time,
#                         'Yes' if branch.is_active else 'No',
#                         'Yes' if branch.is_eod_locked else 'No',
#                         branch.created_at,
#                         branch.updated_at,
#                     ])
                
#                 return response
            
#             elif export_format == 'excel':
#                 # Generate Excel
#                 data = []
#                 for branch in branches:
#                     row = {
#                         'ID': branch.id,
#                         'Name': branch.name,
#                         'Code': branch.code,
#                         'Address': branch.address,
#                         'Phone': branch.phone,
#                         'Email': branch.email or '',
#                         'Opening Time': branch.opening_time,
#                         'Closing Time': branch.closing_time,
#                         'Is Active': 'Yes' if branch.is_active else 'No',
#                         'EOD Locked': 'Yes' if branch.is_eod_locked else 'No',
#                         'Created At': branch.created_at,
#                         'Updated At': branch.updated_at,
#                     }
                    
#                     if include_counters:
#                         row['Counters'] = json.dumps(counters_data.get(branch.id, []))
                    
#                     data.append(row)
                
#                 df = pd.DataFrame(data)
#                 output = BytesIO()
#                 with pd.ExcelWriter(output, engine='openpyxl') as writer:
#                     df.to_excel(writer, sheet_name='Branches', index=False)
                
#                 output.seek(0)
#                 response = HttpResponse(
#                     output.read(),
#                     content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
#                 )
#                 response['Content-Disposition'] = 'attachment; filename="branches_export.xlsx"'
#                 return response
            
#             else:  # JSON format (default)
#                 serializer = BranchListSerializer(branches, many=True)
#                 data = serializer.data
                
#                 if include_counters:
#                     for branch_data in data:
#                         branch_id = branch_data['id']
#                         branch_data['counters'] = counters_data.get(branch_id, [])
                
#                 return JsonResponse(data, safe=False)
        
#         except Exception as e:
#             logger.error(f"Error exporting branches: {str(e)}")
#             return Response(
#                 {'error': f'Export failed: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     @action(detail=False, methods=['get'])
#     def search(self, request):
#         """
#         Advanced search for branches.
#         """
#         serializer = BranchSearchSerializer(data=request.query_params)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         try:
#             # Start with base queryset
#             queryset = self.get_queryset()
            
#             # Apply filters
#             data = serializer.validated_data
            
#             if data.get('q'):
#                 search_term = data['q']
#                 queryset = queryset.filter(
#                     Q(name__icontains=search_term) |
#                     Q(code__icontains=search_term) |
#                     Q(address__icontains=search_term) |
#                     Q(phone__icontains=search_term)
#                 )
            
#             if data.get('active_only'):
#                 queryset = queryset.filter(is_active=True)
            
#             if data.get('has_counter'):
#                 queryset = queryset.filter(counters__is_active=True).distinct()
            
#             # Apply pagination
#             page = self.paginate_queryset(queryset)
#             if page is not None:
#                 serializer = BranchListSerializer(page, many=True)
#                 return self.get_paginated_response(serializer.data)
            
#             # If no pagination, return all
#             serializer = BranchListSerializer(queryset, many=True)
#             return Response(serializer.data)
        
#         except Exception as e:
#             logger.error(f"Error searching branches: {str(e)}")
#             return Response(
#                 {'error': f'Search failed: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     @action(detail=False, methods=['get'])
#     def geo_data(self, request):
#         """
#         Get geographical data for branches (for maps).
#         """
#         # This would typically integrate with a geocoding service
#         # For now, return basic data
        
#         branches = self.get_queryset().filter(is_active=True)
        
#         geo_data = []
#         for branch in branches:
#             try:
#                 # In production, you would geocode the address here
#                 # For now, use mock coordinates or store them in the database
                
#                 geo_entry = {
#                     'branch_id': branch.id,
#                     'name': branch.name,
#                     'code': branch.code,
#                     'address': branch.address,
#                     'phone': branch.phone,
#                     'latitude': None,  # Would come from geocoding
#                     'longitude': None,  # Would come from geocoding
#                     'is_active': branch.is_active,
#                     'is_eod_locked': branch.is_eod_locked,
#                     'todays_appointments': 0,  # Calculate this
#                     'active_staff': 0,  # Calculate this
#                 }
                
#                 geo_data.append(geo_entry)
            
#             except Exception as e:
#                 logger.error(f"Error processing geo data for branch {branch.code}: {str(e)}")
#                 continue
        
#         serializer = BranchGeoSerializer(data=geo_data, many=True)
#         if serializer.is_valid():
#             return Response(serializer.data)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
#     @action(detail=False, methods=['post'])
#     def sync(self, request):
#         """
#         Synchronize branch data (for mobile/offline apps).
#         """
#         serializer = BranchSyncSerializer(data=request.data)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         last_sync = serializer.validated_data.get('last_sync')
#         include = serializer.validated_data.get('include', ['branches'])
        
#         try:
#             response_data = {}
            
#             if 'branches' in include:
#                 # Get branches changed since last sync
#                 branches_qs = self.get_queryset()
                
#                 if last_sync:
#                     branches_qs = branches_qs.filter(
#                         Q(created_at__gt=last_sync) |
#                         Q(updated_at__gt=last_sync)
#                     )
                
#                 serializer = BranchListSerializer(branches_qs, many=True)
#                 response_data['branches'] = serializer.data
            
#             if 'counters' in include:
#                 # Get counters
#                 counters_qs = Counter.objects.filter(is_active=True)
                
#                 if last_sync:
#                     counters_qs = counters_qs.filter(
#                         Q(created_at__gt=last_sync) |
#                         Q(updated_at__gt=last_sync)
#                     )
                
#                 # Filter by user's branches
#                 if not (request.user.is_superuser or request.user.is_admin()):
#                     user_branches = request.user.user_branches.filter(
#                         is_active=True
#                     ).values_list('branch_id', flat=True)
                    
#                     if user_branches:
#                         counters_qs = counters_qs.filter(branch_id__in=user_branches)
                
#                 serializer = CounterListSerializer(counters_qs, many=True)
#                 response_data['counters'] = serializer.data
            
#             # Add sync metadata
#             response_data['sync_timestamp'] = timezone.now()
#             response_data['last_sync'] = last_sync
            
#             return Response(response_data)
        
#         except Exception as e:
#             logger.error(f"Error syncing branch data: {str(e)}")
#             return Response(
#                 {'error': f'Sync failed: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


# # ============================
# # Counter ViewSet
# # ============================

# class CounterViewSet(viewsets.ModelViewSet):
#     """
#     ViewSet for managing counters.
#     """
#     queryset = Counter.objects.all()
#     serializer_class = CounterSerializer
#     permission_classes = [IsAuthenticated, IsManager]
#     pagination_class = CounterPagination
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_fields = ['branch', 'is_active']
#     search_fields = ['name', 'device_id', 'counter_number']
#     ordering_fields = ['counter_number', 'name', 'created_at']
#     ordering = ['branch', 'counter_number']
    
#     def get_queryset(self):
#         """
#         Filter counters based on user permissions.
#         """
#         queryset = super().get_queryset()
        
#         # Superusers can see all
#         if self.request.user.is_superuser or self.request.user.is_admin():
#             return queryset
        
#         # Managers can see counters in their branches
#         if self.request.user.is_manager():
#             # Get user's branches
#             user_branches = self.request.user.user_branches.filter(
#                 is_active=True
#             ).values_list('branch_id', flat=True)
            
#             if user_branches:
#                 return queryset.filter(branch_id__in=user_branches)
#             else:
#                 return queryset.none()
        
#         # Cashiers can see active counters
#         if self.request.user.is_cashier():
#             return queryset.filter(is_active=True)
        
#         # Others can see counters in their current branch
#         if hasattr(self.request.user, 'current_branch'):
#             return queryset.filter(branch=self.request.user.current_branch)
        
#         return queryset.none()
    
#     def get_serializer_class(self):
#         """
#         Use different serializers based on action.
#         """
#         if self.action == 'list':
#             return CounterListSerializer
#         elif self.action == 'create':
#             return CounterCreateSerializer
#         return super().get_serializer_class()
    
#     def perform_create(self, serializer):
#         """Create counter with audit logging"""
#         with transaction.atomic():
#             # Attach audit context
#             attach_audit_context(serializer, self.request)
            
#             # Save counter
#             counter = serializer.save()
            
#             # Log creation
#             log_action(
#                 instance=counter,
#                 action='CREATE',
#                 user=self.request.user,
#                 branch=counter.branch,
#                 device_id=self.request.META.get('HTTP_X_DEVICE_ID'),
#                 ip_address=self.request.META.get('REMOTE_ADDR'),
#             )
            
#             logger.info(f"Counter created: {counter.name} in {counter.branch.code} by {self.request.user}")
    
#     def perform_update(self, serializer):
#         """Update counter with audit logging"""
#         with transaction.atomic():
#             # Check if branch is EOD locked
#             counter = self.get_object()
            
#             if counter.branch.is_eod_locked:
#                 raise serializers.ValidationError({
#                     'branch': 'Cannot modify counters when branch EOD is locked'
#                 })
            
#             # Attach audit context
#             attach_audit_context(serializer, self.request)
            
#             # Save updates
#             updated_counter = serializer.save()
            
#             # Log update
#             log_action(
#                 instance=updated_counter,
#                 action='UPDATE',
#                 user=self.request.user,
#                 branch=updated_counter.branch,
#                 device_id=self.request.META.get('HTTP_X_DEVICE_ID'),
#                 ip_address=self.request.META.get('REMOTE_ADDR'),
#             )
            
#             logger.info(f"Counter updated: {updated_counter.name} by {self.request.user}")
    
#     def perform_destroy(self, instance):
#         """Delete counter with audit logging"""
#         with transaction.atomic():
#             # Check if branch is EOD locked
#             if instance.branch.is_eod_locked:
#                 raise serializers.ValidationError({
#                     'branch': 'Cannot delete counters when branch EOD is locked'
#                 })
            
#             # Check if counter is in use
#             from apps.payments.models import Payment
#             recent_payments = Payment.objects.filter(
#                 counter=instance,
#                 created_at__gte=timezone.now() - timedelta(days=1)
#             ).exists()
            
#             if recent_payments:
#                 raise serializers.ValidationError(
#                     "Cannot delete counter with recent payments. Deactivate instead."
#                 )
            
#             # Delete counter
#             instance.delete()
            
#             # Log deletion
#             log_action(
#                 instance=instance,
#                 action='DELETE',
#                 user=self.request.user,
#                 branch=instance.branch,
#                 device_id=self.request.META.get('HTTP_X_DEVICE_ID'),
#                 ip_address=self.request.META.get('REMOTE_ADDR'),
#             )
            
#             logger.info(f"Counter deleted: {instance.name} from {instance.branch.code} by {self.request.user}")
    
#     @action(detail=True, methods=['post'])
#     def assign_device(self, request, pk=None):
#         """
#         Assign a device to this counter.
#         """
#         counter = self.get_object()
        
#         # Only managers, admins, and cashiers can assign devices
#         if not (request.user.is_superuser or request.user.is_admin() or 
#                 request.user.is_manager() or request.user.is_cashier()):
#             return Response(
#                 {'error': 'Permission denied'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         serializer = CounterAssignmentSerializer(data=request.data)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         device_id = serializer.validated_data['device_id']
#         force = serializer.validated_data['force']
        
#         # Check if device is already assigned to another counter
#         existing_assignment = Counter.objects.filter(
#             device_id=device_id,
#             is_active=True
#         ).exclude(id=counter.id).first()
        
#         if existing_assignment and not force:
#             return Response({
#                 'error': f'Device already assigned to {existing_assignment.name}',
#                 'existing_counter': {
#                     'id': existing_assignment.id,
#                     'name': existing_assignment.name,
#                     'branch': existing_assignment.branch.code
#                 },
#                 'force_required': True
#             }, status=status.HTTP_400_BAD_REQUEST)
        
#         with transaction.atomic():
#             # Remove from existing counter if forcing
#             if existing_assignment and force:
#                 existing_assignment.device_id = None
#                 existing_assignment.save()
                
#                 # Log device removal
#                 log_action(
#                     instance=existing_assignment,
#                     action='DEVICE_UNASSIGN',
#                     user=request.user,
#                     branch=existing_assignment.branch,
#                     device_id=request.META.get('HTTP_X_DEVICE_ID'),
#                     ip_address=request.META.get('REMOTE_ADDR'),
#                     metadata={'device_id': device_id, 'forced': True}
#                 )
            
#             # Assign to this counter
#             old_device_id = counter.device_id
#             counter.device_id = device_id
#             counter.save()
            
#             # Log assignment
#             log_action(
#                 instance=counter,
#                 action='DEVICE_ASSIGN',
#                 user=request.user,
#                 branch=counter.branch,
#                 device_id=request.META.get('HTTP_X_DEVICE_ID'),
#                 ip_address=request.META.get('REMOTE_ADDR'),
#                 metadata={
#                     'old_device_id': old_device_id,
#                     'new_device_id': device_id,
#                     'forced': force
#                 }
#             )
            
#             logger.info(f"Device {device_id} assigned to counter {counter.name} by {request.user}")
            
#             return Response({
#                 'success': True,
#                 'message': f'Device {device_id} assigned to counter {counter.name}',
#                 'counter': CounterSerializer(counter).data
#             })
    
#     @action(detail=True, methods=['post'])
#     def unassign_device(self, request, pk=None):
#         """
#         Unassign device from counter.
#         """
#         counter = self.get_object()
        
#         # Only managers, admins, and cashiers can unassign devices
#         if not (request.user.is_superuser or request.user.is_admin() or 
#                 request.user.is_manager() or request.user.is_cashier()):
#             return Response(
#                 {'error': 'Permission denied'},
#                 status=status.HTTP_403_FORBIDDEN
#             )
        
#         if not counter.device_id:
#             return Response({
#                 'success': True,
#                 'message': 'Counter has no device assigned',
#                 'already_unassigned': True
#             })
        
#         with transaction.atomic():
#             old_device_id = counter.device_id
#             counter.device_id = None
#             counter.save()
            
#             # Log unassignment
#             log_action(
#                 instance=counter,
#                 action='DEVICE_UNASSIGN',
#                 user=request.user,
#                 branch=counter.branch,
#                 device_id=request.META.get('HTTP_X_DEVICE_ID'),
#                 ip_address=request.META.get('REMOTE_ADDR'),
#                 metadata={'old_device_id': old_device_id}
#             )
            
#             logger.info(f"Device {old_device_id} unassigned from counter {counter.name} by {request.user}")
            
#             return Response({
#                 'success': True,
#                 'message': f'Device {old_device_id} unassigned from counter',
#                 'counter': CounterSerializer(counter).data
#             })
    
#     @action(detail=True, methods=['get'])
#     def stats(self, request, pk=None):
#         """
#         Get statistics for a counter.
#         """
#         counter = self.get_object()
        
#         try:
#             from apps.payments.models import Payment
#             from apps.accounts.models import UserDevice
            
#             today = timezone.now().date()
#             week_ago = today - timedelta(days=7)
            
#             # Transaction statistics
#             todays_transactions = Payment.objects.filter(
#                 counter=counter,
#                 created_at__date=today,
#                 status='completed'
#             ).count()
            
#             weeks_transactions = Payment.objects.filter(
#                 counter=counter,
#                 created_at__date__gte=week_ago,
#                 created_at__date__lte=today,
#                 status='completed'
#             ).count()
            
#             total_transactions = Payment.objects.filter(
#                 counter=counter,
#                 status='completed'
#             ).count()
            
#             # User statistics
#             current_user = None
#             last_user = None
#             last_used_at = None
            
#             if counter.device_id:
#                 # Find current user
#                 current_device = UserDevice.objects.filter(
#                     device_id=counter.device_id,
#                     last_seen_at__gte=timezone.now() - timedelta(minutes=30)
#                 ).first()
                
#                 if current_device:
#                     current_user = f"{current_device.user.full_name} ({current_device.user.email})"
                
#                 # Find last user
#                 last_payment = Payment.objects.filter(
#                     counter=counter
#                 ).order_by('-created_at').first()
                
#                 if last_payment:
#                     last_user = f"{last_payment.created_by.full_name} ({last_payment.created_by.email})"
#                     last_used_at = last_payment.created_at
            
#             # Performance statistics
#             recent_payments = Payment.objects.filter(
#                 counter=counter,
#                 created_at__gte=today
#             )
            
#             if recent_payments.exists():
#                 # Calculate average transaction time
#                 # This would require tracking start/end times
#                 average_transaction_time = 120  # Default 2 minutes
#             else:
#                 average_transaction_time = 0
            
#             # Peak hour analysis
#             payments_by_hour = Payment.objects.filter(
#                 counter=counter,
#                 created_at__gte=week_ago
#             ).extra({
#                 'hour': "EXTRACT(HOUR FROM created_at)"
#             }).values('hour').annotate(
#                 count=Count('id')
#             ).order_by('-count')
            
#             peak_hour = None
#             if payments_by_hour.exists():
#                 peak_hour_data = payments_by_hour.first()
#                 peak_hour = f"{int(peak_hour_data['hour'])}:00"
            
#             # Prepare response
#             stats_data = {
#                 'counter_id': counter.id,
#                 'counter_name': counter.name,
#                 'branch_name': counter.branch.name,
#                 'todays_transactions': todays_transactions,
#                 'weeks_transactions': weeks_transactions,
#                 'total_transactions': total_transactions,
#                 'current_user': current_user,
#                 'last_user': last_user,
#                 'last_used_at': last_used_at,
#                 'average_transaction_time': average_transaction_time,
#                 'peak_hour': peak_hour,
#             }
            
#             serializer = CounterStatsSerializer(data=stats_data)
#             if serializer.is_valid():
#                 return Response(serializer.data)
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         except Exception as e:
#             logger.error(f"Error getting counter stats: {str(e)}")
#             return Response(
#                 {'error': f'Failed to get statistics: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     @action(detail=False, methods=['get'])
#     def my_counter(self, request):
#         """
#         Get the counter assigned to the current user's device.
#         """
#         device_id = request.META.get('HTTP_X_DEVICE_ID')
        
#         if not device_id:
#             return Response(
#                 {'error': 'Device ID not provided in headers'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         try:
#             counter = Counter.objects.get(device_id=device_id, is_active=True)
#             serializer = CounterSerializer(counter)
#             return Response(serializer.data)
        
#         except Counter.DoesNotExist:
#             return Response(
#                 {'error': 'No counter assigned to this device'},
#                 status=status.HTTP_404_NOT_FOUND
#             )
        
#         except Exception as e:
#             logger.error(f"Error getting user's counter: {str(e)}")
#             return Response(
#                 {'error': f'Failed to get counter: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


# # ============================
# # Additional Views
# # ============================

# class BranchPublicView(generics.ListAPIView):
#     """
#     Public view for active branches (no authentication required).
#     Used for appointment booking, location finder, etc.
#     """
#     permission_classes = [AllowAny]
#     serializer_class = BranchListSerializer
#     pagination_class = BranchPagination
    
#     def get_queryset(self):
#         """Return only active branches"""
#         return Branch.objects.filter(
#             is_active=True,
#             deleted_at__isnull=True
#         ).order_by('name')


# class CounterPublicView(generics.ListAPIView):
#     """
#     Public view for active counters.
#     """
#     permission_classes = [AllowAny]
#     serializer_class = CounterListSerializer
    
#     def get_queryset(self):
#         """Return only active counters"""
#         return Counter.objects.filter(
#             is_active=True
#         ).order_by('branch', 'counter_number')


# class NearestBranchView(APIView):
#     """
#     Find nearest branches based on coordinates.
#     """
#     permission_classes = [AllowAny]
    
#     def post(self, request):
#         """
#         Find nearest branches to given coordinates.
#         Requires geocoded branch data in production.
#         """
#         latitude = request.data.get('latitude')
#         longitude = request.data.get('longitude')
#         max_distance = request.data.get('max_distance', 10)  # km
        
#         if not latitude or not longitude:
#             return Response(
#                 {'error': 'Latitude and longitude are required'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         try:
#             # In production, you would use PostGIS or similar
#             # For now, return all active branches
#             branches = Branch.objects.filter(
#                 is_active=True,
#                 deleted_at__isnull=True
#             )
            
#             # Simulate distance calculation
#             # In real implementation, use geospatial query
#             branches_data = []
#             for branch in branches:
#                 # Mock distance (replace with actual calculation)
#                 distance = 5.0  # km
                
#                 if distance <= max_distance:
#                     branches_data.append({
#                         'branch': BranchListSerializer(branch).data,
#                         'distance_km': round(distance, 2),
#                         'estimated_travel_time': round(distance * 2, 1),  # minutes
#                     })
            
#             # Sort by distance
#             branches_data.sort(key=lambda x: x['distance_km'])
            
#             return Response({
#                 'user_location': {
#                     'latitude': latitude,
#                     'longitude': longitude
#                 },
#                 'max_distance_km': max_distance,
#                 'branches_found': len(branches_data),
#                 'branches': branches_data[:10]  # Return top 10
#             })
        
#         except Exception as e:
#             logger.error(f"Error finding nearest branches: {str(e)}")
#             return Response(
#                 {'error': f'Failed to find nearest branches: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


# class BranchAvailabilityView(APIView):
#     """
#     Check branch availability for appointments.
#     """
#     permission_classes = [AllowAny]
    
#     def get(self, request, branch_id):
#         """
#         Check if branch has available slots for a given date.
#         """
#         date_str = request.query_params.get('date')
        
#         if not date_str:
#             date = timezone.now().date()
#         else:
#             try:
#                 date = datetime.strptime(date_str, '%Y-%m-%d').date()
#             except ValueError:
#                 return Response(
#                     {'error': 'Invalid date format. Use YYYY-MM-DD'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
        
#         try:
#             branch = get_object_or_404(Branch, id=branch_id, is_active=True)
            
#             from apps.visits.models import Appointment
#             from apps.doctors.models import DoctorSchedule
            
#             # Check if branch is open on this date
#             # This would check operational hours and holidays
            
#             # Get booked appointments for the date
#             booked_appointments = Appointment.objects.filter(
#                 branch=branch,
#                 appointment_date=date,
#                 status__in=['scheduled', 'confirmed']
#             ).count()
            
#             # Get available doctors
#             available_doctors = DoctorSchedule.objects.filter(
#                 branch=branch,
#                 is_active=True,
#                 day_of_week=date.strftime('%A').upper()
#             ).count()
            
#             # Calculate available slots
#             # Assuming 30-minute slots, 8 working hours
#             max_slots_per_day = 16  # 8 hours * 2 slots per hour
#             available_slots = max(0, max_slots_per_day - booked_appointments)
            
#             return Response({
#                 'branch_id': branch.id,
#                 'branch_name': branch.name,
#                 'date': date,
#                 'is_open': True,  # Would check actual schedule
#                 'booked_appointments': booked_appointments,
#                 'available_doctors': available_doctors,
#                 'available_slots': available_slots,
#                 'max_slots_per_day': max_slots_per_day,
#                 'occupancy_percentage': round((booked_appointments / max_slots_per_day * 100), 2),
#                 'recommended': available_slots > 0 and available_doctors > 0
#             })
        
#         except Branch.DoesNotExist:
#             return Response(
#                 {'error': 'Branch not found or not active'},
#                 status=status.HTTP_404_NOT_FOUND
#             )
        
#         except Exception as e:
#             logger.error(f"Error checking branch availability: {str(e)}")
#             return Response(
#                 {'error': f'Failed to check availability: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


# # ============================
# # Health Check View
# # ============================

# class ClinicsHealthCheckView(APIView):
#     """
#     Health check for clinics system.
#     """
#     permission_classes = [IsAuthenticated, IsManager]
    
#     def get(self, request):
#         """
#         Check clinics system health.
#         """
#         try:
#             # Check database connections
#             total_branches = Branch.objects.filter(
#                 deleted_at__isnull=True
#             ).count()
            
#             active_branches = Branch.objects.filter(
#                 is_active=True,
#                 deleted_at__isnull=True
#             ).count()
            
#             total_counters = Counter.objects.count()
#             active_counters = Counter.objects.filter(is_active=True).count()
            
#             # Check for EOD locked branches
#             eod_locked_branches = Branch.objects.filter(
#                 is_eod_locked=True,
#                 is_active=True
#             ).count()
            
#             # Check for branches without counters
#             branches_without_counters = Branch.objects.filter(
#                 is_active=True,
#                 deleted_at__isnull=True,
#                 counters__isnull=True
#             ).distinct().count()
            
#             health_data = {
#                 'status': 'healthy',
#                 'database': 'connected',
#                 'statistics': {
#                     'total_branches': total_branches,
#                     'active_branches': active_branches,
#                     'total_counters': total_counters,
#                     'active_counters': active_counters,
#                     'eod_locked_branches': eod_locked_branches,
#                     'branches_without_counters': branches_without_counters,
#                 },
#                 'checks': {
#                     'database_connection': True,
#                     'branch_integrity': branches_without_counters == 0,
#                     'counter_assignments': active_branches <= active_counters,
#                 },
#                 'timestamp': timezone.now()
#             }
            
#             return Response(health_data)
        
#         except Exception as e:
#             logger.error(f"Clinics health check failed: {str(e)}")
#             return Response(
#                 {
#                     'status': 'unhealthy',
#                     'error': str(e),
#                     'timestamp': timezone.now()
#                 },
#                 status=status.HTTP_503_SERVICE_UNAVAILABLE
#             )