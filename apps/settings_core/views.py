# apps/settings_core/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from core.permissions import (
    HasPermission, IsSuperAdmin, IsBranchManager, IsClinicManager,
    IsAdmin, IsStaff
)
from .models import *
from .serializers import *
from .services import SettingsService


class SystemSettingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for System Settings (Global settings)
    """
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'data_type', 'is_editable', 'requires_superuser']
    search_fields = ['key', 'name', 'description']
    ordering_fields = ['category', 'sort_order', 'name', 'last_modified_at']
    ordering = ['category', 'sort_order']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by category if provided
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        
        return queryset

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get all setting categories"""
        categories = SystemSetting.CATEGORY_CHOICES
        return Response([{'value': cat[0], 'label': cat[1]} for cat in categories])

    @action(detail=False, methods=['get'])
    def data_types(self, request):
        """Get all data types"""
        data_types = SystemSetting.DATA_TYPE_CHOICES
        return Response([{'value': dt[0], 'label': dt[1]} for dt in data_types])

    @action(detail=False, methods=['post'])
    def initialize_defaults(self, request):
        """Initialize default system settings"""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only superusers can initialize defaults'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            SettingsService.initialize_default_settings()
            return Response(
                {'message': 'Default settings initialized successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BranchSettingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Branch Settings
    """
    serializer_class = BranchSettingSerializer
    permission_classes = [IsAuthenticated, HasPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['branch', 'category', 'data_type', 'override_system']
    search_fields = ['key', 'name', 'description']
    ordering_fields = ['branch', 'category', 'sort_order']
    ordering = ['branch', 'category', 'sort_order']

    def get_queryset(self):
        user = self.request.user
        queryset = BranchSetting.objects.all()
        
        # Apply branch filtering based on user role
        if not user.role or not user.role.scope_all_branches:
            queryset = queryset.filter(branch=user.branch)
        
        # Filter by branch if specified
        branch_id = self.request.query_params.get('branch', None)
        if branch_id:
            if user.role and user.role.scope_all_branches:
                queryset = queryset.filter(branch_id=branch_id)
        
        return queryset

    def get_permissions(self):
        """
        Require branch manager for certain actions
        """
        permissions = super().get_permissions()
        
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permissions.append(IsBranchManager())
        
        return permissions

    def create(self, request, *args, **kwargs):
        """Create branch setting with branch context"""
        data = request.data.copy()
        
        # If user is not superuser/admin with all branches access, use their branch
        if not request.user.role or not request.user.role.scope_all_branches:
            data['branch'] = request.user.branch.id
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user, updated_by=request.user)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )


class ClinicConfigurationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Clinic Configuration
    """
    serializer_class = ClinicConfigurationSerializer
    permission_classes = [IsAuthenticated, HasPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['branch']

    def get_queryset(self):
        user = self.request.user
        queryset = ClinicConfiguration.objects.all()
        
        # Apply branch filtering based on user role
        if not user.role or not user.role.scope_all_branches:
            queryset = queryset.filter(branch=user.branch)
        
        return queryset

    def get_permissions(self):
        """
        Require branch manager for certain actions
        """
        permissions = super().get_permissions()
        
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permissions.append(IsBranchManager())
        
        return permissions

    @action(detail=False, methods=['get'])
    def current_branch(self, request):
        """Get configuration for current user's branch"""
        try:
            config = ClinicConfiguration.objects.get(branch=request.user.branch)
            serializer = self.get_serializer(config)
            return Response(serializer.data)
        except ClinicConfiguration.DoesNotExist:
            # Create default configuration
            config = SettingsService.get_clinic_configuration(request.user.branch)
            serializer = self.get_serializer(config)
            return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def working_hours(self, request):
        """Get working hours for a specific date"""
        branch = request.user.branch
        date_str = request.query_params.get('date')
        
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            date = timezone.now().date()
        
        is_working = SettingsService.is_working_day(branch, date)
        working_hours = SettingsService.get_working_hours(branch, date)
        
        return Response({
            'date': date,
            'is_working_day': is_working,
            'working_hours': working_hours
        })

    @action(detail=False, methods=['get'])
    def available_slots(self, request):
        """Get available appointment slots"""
        branch = request.user.branch
        date_str = request.query_params.get('date')
        doctor_id = request.query_params.get('doctor')
        duration = int(request.query_params.get('duration', 30))
        
        if not date_str:
            return Response(
                {'error': 'Date parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        doctor = None
        if doctor_id:
            from apps.doctors.models import Doctor
            try:
                doctor = Doctor.objects.get(id=doctor_id, branch=branch)
            except Doctor.DoesNotExist:
                return Response(
                    {'error': 'Doctor not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        slots = SettingsService.get_available_time_slots(
            branch=branch,
            date=date,
            doctor=doctor,
            duration=duration
        )
        
        return Response({
            'date': date,
            'doctor': doctor.id if doctor else None,
            'slots': [slot.strftime('%H:%M') for slot in slots]
        })


class HolidayViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Holidays
    """
    serializer_class = HolidaySerializer
    permission_classes = [IsAuthenticated, HasPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['branch', 'is_recurring']
    search_fields = ['name', 'description']

    def get_queryset(self):
        user = self.request.user
        queryset = Holiday.objects.all()
        
        # Apply branch filtering based on user role
        if not user.role or not user.role.scope_all_branches:
            queryset = queryset.filter(branch=user.branch)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(date__range=[start, end])
            except ValueError:
                pass
        
        return queryset.order_by('date')

    def get_permissions(self):
        """
        Require branch manager for certain actions
        """
        permissions = super().get_permissions()
        
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permissions.append(IsBranchManager())
        
        return permissions

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming holidays"""
        days = int(request.query_params.get('days', 30))
        from_date = timezone.now().date()
        to_date = from_date + timedelta(days=days)
        
        queryset = self.get_queryset()
        upcoming_holidays = queryset.filter(date__range=[from_date, to_date])
        
        serializer = self.get_serializer(upcoming_holidays, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple holidays at once"""
        data = request.data
        
        if not isinstance(data, list):
            return Response(
                {'error': 'Expected a list of holidays'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created = []
        errors = []
        
        for holiday_data in data:
            serializer = self.get_serializer(data=holiday_data)
            if serializer.is_valid():
                serializer.save(created_by=request.user, updated_by=request.user)
                created.append(serializer.data)
            else:
                errors.append({
                    'data': holiday_data,
                    'errors': serializer.errors
                })
        
        return Response({
            'created': len(created),
            'errors': len(errors),
            'details': errors
        })


class TaxConfigurationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Tax Configuration
    """
    serializer_class = TaxConfigurationSerializer
    permission_classes = [IsAuthenticated, HasPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['branch', 'tax_type', 'is_active']
    search_fields = ['name', 'code', 'description']

    def get_queryset(self):
        user = self.request.user
        queryset = TaxConfiguration.objects.all()
        
        # Apply branch filtering based on user role
        if not user.role or not user.role.scope_all_branches:
            queryset = queryset.filter(branch=user.branch)
        
        # Filter by applicability
        date = timezone.now().date()
        queryset = queryset.filter(
            is_active=True,
            applicable_from__lte=date
        ).filter(
            models.Q(applicable_to__isnull=True) |
            models.Q(applicable_to__gte=date)
        )
        
        return queryset

    def get_permissions(self):
        """
        Require branch manager for certain actions
        """
        permissions = super().get_permissions()
        
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permissions.append(IsBranchManager())
        
        return permissions

    @action(detail=False, methods=['get'])
    def active_taxes(self, request):
        """Get all active taxes"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        """Calculate tax for a given amount"""
        try:
            tax_config = self.get_object()
            amount = Decimal(request.data.get('amount', '0'))
            
            tax_amount = tax_config.calculate_tax(amount)
            total_amount = amount + tax_amount
            
            return Response({
                'tax_config': TaxConfigurationSerializer(tax_config).data,
                'amount': amount,
                'tax_amount': tax_amount,
                'total_amount': total_amount
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Notification Templates
    """
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated, HasPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['branch', 'notification_type', 'trigger', 'is_active']
    search_fields = ['name', 'sms_template', 'email_subject']

    def get_queryset(self):
        user = self.request.user
        queryset = NotificationTemplate.objects.all()
        
        # Show branch-specific and system-wide (branch=None) templates
        if not user.role or not user.role.scope_all_branches:
            queryset = queryset.filter(
                models.Q(branch=user.branch) | models.Q(branch__isnull=True)
            )
        
        return queryset

    @action(detail=True, methods=['post'])
    def test_render(self, request, pk=None):
        """Test template rendering with sample context"""
        template = self.get_object()
        
        context = request.data.get('context', {})
        notification_type = request.data.get('notification_type', None)
        
        try:
            result = template.render_template(context, notification_type)
            
            return Response({
                'template': self.get_serializer(template).data,
                'context': context,
                'rendered': result
            })
        except Exception as e:
            return Response(
                {'error': f'Template rendering failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class SMSConfigurationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SMS Configuration
    """
    serializer_class = SMSConfigurationSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['branch', 'provider', 'is_active']

    def get_queryset(self):
        user = self.request.user
        queryset = SMSConfiguration.objects.all()
        
        # Apply branch filtering based on user role
        if not user.role or not user.role.scope_all_branches:
            queryset = queryset.filter(branch=user.branch)
        
        return queryset

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test SMS configuration"""
        sms_config = self.get_object()
        phone_number = request.data.get('phone_number')
        message = request.data.get('message', 'Test message from Dental Clinic System')
        
        # TODO: Implement actual SMS sending test
        # This is a placeholder for SMS integration
        
        return Response({
            'success': True,
            'message': 'SMS configuration test initiated',
            'details': {
                'provider': sms_config.provider,
                'phone': phone_number,
                'message': message[:50] + '...' if len(message) > 50 else message
            }
        })


class EmailConfigurationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Email Configuration
    """
    serializer_class = EmailConfigurationSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['branch', 'provider', 'is_active']

    def get_queryset(self):
        user = self.request.user
        queryset = EmailConfiguration.objects.all()
        
        # Apply branch filtering based on user role
        if not user.role or not user.role.scope_all_branches:
            queryset = queryset.filter(branch=user.branch)
        
        return queryset

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test email configuration"""
        email_config = self.get_object()
        test_email = request.data.get('email', request.user.email)
        
        # TODO: Implement actual email sending test
        # This is a placeholder for email integration
        
        return Response({
            'success': True,
            'message': 'Email configuration test initiated',
            'details': {
                'provider': email_config.provider,
                'to_email': test_email,
                'from_email': email_config.from_email
            }
        })


class SettingsUtilityViewSet(viewsets.ViewSet):
    """
    Utility endpoints for settings
    """
    permission_classes = [IsAuthenticated, HasPermission]

    @action(detail=False, methods=['get'])
    def get_setting(self, request):
        """Get a specific setting value"""
        key = request.query_params.get('key')
        branch_id = request.query_params.get('branch')
        
        if not key:
            return Response(
                {'error': 'Setting key is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        branch = None
        if branch_id:
            from apps.clinics.models import Branch
            try:
                branch = Branch.objects.get(id=branch_id)
            except Branch.DoesNotExist:
                return Response(
                    {'error': 'Branch not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif not request.user.role or not request.user.role.scope_all_branches:
            branch = request.user.branch
        
        value = SettingsService.get_setting(key, branch)
        
        return Response({
            'key': key,
            'branch': branch.id if branch else None,
            'value': value
        })

    @action(detail=False, methods=['post'])
    def set_setting(self, request):
        """Set a specific setting value"""
        key = request.data.get('key')
        value = request.data.get('value')
        branch_id = request.data.get('branch')
        override_system = request.data.get('override_system', True)
        
        if not key or value is None:
            return Response(
                {'error': 'Setting key and value are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        branch = None
        if branch_id:
            from apps.clinics.models import Branch
            try:
                branch = Branch.objects.get(id=branch_id)
            except Branch.DoesNotExist:
                return Response(
                    {'error': 'Branch not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif not request.user.role or not request.user.role.scope_all_branches:
            branch = request.user.branch
        
        SettingsService.set_setting(
            key=key,
            value=value,
            branch=branch,
            user=request.user,
            override_system=override_system
        )
        
        return Response({
            'success': True,
            'message': f'Setting {key} updated successfully'
        })