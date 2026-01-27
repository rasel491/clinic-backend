# apps/reports/views.py

from decimal import Decimal
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
import logging
from datetime import datetime, timedelta
from django.db.models import Max


from core.permissions import (
    IsAdminUser, IsManager, IsDoctor, IsReceptionist, IsCashier,
    HasBranchAccess
)
from .models import (
    ReportCategory, ReportTemplate, GeneratedReport,
    ReportData, Dashboard, DashboardWidget, ReportSchedule,
    ReportExport, ReportFavorite
)
from .serializers import (
    ReportCategorySerializer, ReportTemplateSerializer, ReportTemplateCreateSerializer,
    GeneratedReportSerializer, ReportDataSerializer,
    DashboardSerializer, DashboardWidgetSerializer,
    ReportScheduleSerializer, ReportExportSerializer, ReportFavoriteSerializer,
    GenerateReportSerializer, ScheduleReportSerializer,
    WidgetDataRequestSerializer, ReportFilterSerializer,
    DashboardCloneSerializer, ReportStatsSerializer,
    BranchPerformanceSerializer, FinancialSummarySerializer
)
from .services import ReportService
from apps.audit.services import log_action

logger = logging.getLogger(__name__)


class ReportCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Report Categories"""
    queryset = ReportCategory.objects.filter(is_active=True)
    serializer_class = ReportCategorySerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['sort_order', 'name', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def with_templates(self, request):
        """Get categories with active templates count"""
        categories = self.get_queryset()
        
        data = []
        for category in categories:
            template_count = ReportTemplate.objects.filter(
                category=category,
                is_active=True
            ).count()
            
            data.append({
                'id': category.id,
                'name': category.name,
                'code': category.code,
                'description': category.description,
                'icon': category.icon,
                'template_count': template_count,
                'is_active': category.is_active
            })
        
        return Response(data)


class ReportTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Report Templates"""
    queryset = ReportTemplate.objects.filter(is_active=True)
    serializer_class = ReportTemplateSerializer
    permission_classes = [IsAuthenticated, HasBranchAccess]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['report_type', 'is_active', 'is_scheduled', 'branch']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['sort_order', 'name', 'created_at', 'last_run_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ReportTemplateCreateSerializer
        return ReportTemplateSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Filter by branch
        branch_id = getattr(self.request, 'branch_id', None)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        elif not user.is_superuser and hasattr(user, 'branch'):
            queryset = queryset.filter(branch=user.branch)
        
        # Filter by user permissions
        if not user.is_superuser and not user.role == 'clinic_manager':
            # Filter templates that user can access
            accessible_templates = []
            for template in queryset:
                if template.can_access(user):
                    accessible_templates.append(template.id)
            queryset = queryset.filter(id__in=accessible_templates)
        
        # Filter by search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset
    
    def perform_create(self, serializer):
        # Set branch from request
        branch_id = getattr(self.request, 'branch_id', None)
        if branch_id:
            from apps.clinics.models import Branch
            branch = Branch.objects.get(id=branch_id)
            serializer.save(branch=branch, created_by=self.request.user)
        else:
            serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        """Generate a report from template"""
        template = self.get_object()
        
        # Check permission
        if template.requires_permission and not template.can_access(request.user):
            return Response(
                {'error': 'You do not have permission to generate this report'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = GenerateReportSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            try:
                # Use ReportService to generate report
                report = ReportService.generate_report_from_template(
                    template=template,
                    parameters=serializer.validated_data.get('parameters', {}),
                    start_date=serializer.validated_data.get('start_date'),
                    end_date=serializer.validated_data.get('end_date'),
                    generated_by=request.user
                )
                
                # Log action
                log_action(
                    user=request.user,
                    branch=template.branch,
                    instance=report,
                    action='REPORT_GENERATED',
                    metadata={
                        'template_id': str(template.id),
                        'template_name': template.name,
                        'parameters': serializer.validated_data.get('parameters', {}),
                        'output_format': serializer.validated_data.get('output_format', 'HTML')
                    }
                )
                
                return Response(
                    GeneratedReportSerializer(report, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
                
            except Exception as e:
                logger.error(f"Error generating report: {str(e)}")
                return Response(
                    {'error': f'Failed to generate report: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get generation history for this template"""
        template = self.get_object()
        
        # Get reports for this template
        reports = GeneratedReport.objects.filter(
            template=template
        ).order_by('-generated_at')[:50]
        
        serializer = GeneratedReportSerializer(reports, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def schedule(self, request, pk=None):
        """Schedule this template"""
        template = self.get_object()
        
        # Check permission
        if template.requires_permission and not template.can_access(request.user):
            return Response(
                {'error': 'You do not have permission to schedule this report'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ScheduleReportSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                schedule = ReportSchedule.objects.create(
                    template=template,
                    frequency=serializer.validated_data['frequency'],
                    start_date=serializer.validated_data['start_date'],
                    end_date=serializer.validated_data.get('end_date'),
                    parameters=serializer.validated_data.get('parameters', {}),
                    delivery_method=serializer.validated_data.get('delivery_method', 'EMAIL'),
                    email_recipients=serializer.validated_data.get('email_recipients', []),
                    email_subject=serializer.validated_data.get('email_subject', ''),
                    email_body=serializer.validated_data.get('email_body', ''),
                    created_by=request.user,
                    branch=template.branch
                )
                
                # Log action
                log_action(
                    user=request.user,
                    branch=template.branch,
                    instance=schedule,
                    action='REPORT_SCHEDULED',
                    metadata={
                        'template_id': str(template.id),
                        'frequency': serializer.validated_data['frequency'],
                        'start_date': str(serializer.validated_data['start_date'])
                    }
                )
                
                return Response(
                    ReportScheduleSerializer(schedule, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
                
            except Exception as e:
                logger.error(f"Error scheduling report: {str(e)}")
                return Response(
                    {'error': f'Failed to schedule report: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a report template"""
        template = self.get_object()
        
        try:
            # Create a copy
            new_template = ReportTemplate.objects.create(
                name=f"{template.name} (Copy)",
                code=f"{template.code}_copy_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                description=template.description,
                report_type=template.report_type,
                category=template.category,
                query_sql=template.query_sql,
                query_parameters=template.query_parameters,
                output_format=template.output_format,
                is_scheduled=False,  # Disable scheduling for copies
                frequency=template.frequency,
                schedule_time=template.schedule_time,
                schedule_day=template.schedule_day,
                requires_permission=template.requires_permission,
                allowed_roles=template.allowed_roles,
                icon=template.icon,
                sort_order=template.sort_order + 1,
                html_template=template.html_template,
                branch=template.branch,
                created_by=request.user
            )
            
            # Log action
            log_action(
                user=request.user,
                branch=template.branch,
                instance=new_template,
                action='REPORT_TEMPLATE_DUPLICATED',
                metadata={
                    'original_template_id': str(template.id),
                    'original_template_name': template.name
                }
            )
            
            return Response(
                ReportTemplateSerializer(new_template, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Error duplicating template: {str(e)}")
            return Response(
                {'error': f'Failed to duplicate template: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GeneratedReportViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Generated Reports"""
    queryset = GeneratedReport.objects.all()
    serializer_class = GeneratedReportSerializer
    permission_classes = [IsAuthenticated, HasBranchAccess]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'template', 'generated_by', 'branch']
    search_fields = ['report_number', 'template__name']
    ordering_fields = ['generated_at', 'completed_at', 'download_count']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Filter by branch
        branch_id = getattr(self.request, 'branch_id', None)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        elif not user.is_superuser and hasattr(user, 'branch'):
            queryset = queryset.filter(branch=user.branch)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(generated_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(generated_at__date__lte=end_date)
        
        # Filter by user permissions
        if not user.is_superuser and user.role not in ['clinic_manager', 'doctor']:
            # Users can only see reports they generated
            queryset = queryset.filter(generated_by=user)
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download generated report file"""
        report = self.get_object()
        
        # Check permission
        if not self._can_access_report(request.user, report):
            return Response(
                {'error': 'You do not have permission to download this report'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Increment download count
        report.increment_download_count()
        
        # Log action
        log_action(
            user=request.user,
            branch=report.branch,
            instance=report,
            action='REPORT_DOWNLOADED',
            metadata={
                'report_number': report.report_number,
                'template_name': report.template.name
            }
        )
        
        # In production, serve the actual file
        # For now, return file info
        return Response({
            'report_id': report.id,
            'report_number': report.report_number,
            'template_name': report.template.name,
            'file_path': report.file_path,
            'file_size': report.file_size,
            'download_count': report.download_count,
            'message': 'File download would be served here in production'
        })
    
    @action(detail=True, methods=['get'])
    def data(self, request, pk=None):
        """Get report data"""
        report = self.get_object()
        
        # Check permission
        if not self._can_access_report(request.user, report):
            return Response(
                {'error': 'You do not have permission to view this report data'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            report_data = ReportData.objects.get(generated_report=report)
            serializer = ReportDataSerializer(report_data, context={'request': request})
            return Response(serializer.data)
        except ReportData.DoesNotExist:
            return Response(
                {'error': 'Report data not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry a failed report generation"""
        report = self.get_object()
        
        if report.status not in [GeneratedReport.FAILED, GeneratedReport.CANCELLED]:
            return Response(
                {'error': 'Only failed or cancelled reports can be retried'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Update status to pending
            report.status = GeneratedReport.PENDING
            report.save()
            
            # Log action
            log_action(
                user=request.user,
                branch=report.branch,
                instance=report,
                action='REPORT_RETRY',
                metadata={
                    'report_number': report.report_number,
                    'previous_status': report.status
                }
            )
            
            # In production, this would trigger a background task
            # For now, just return success
            return Response({
                'message': 'Report generation queued for retry',
                'report_id': report.id,
                'status': report.status
            })
            
        except Exception as e:
            logger.error(f"Error retrying report: {str(e)}")
            return Response(
                {'error': f'Failed to retry report: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a pending or processing report"""
        report = self.get_object()
        
        if report.status not in [GeneratedReport.PENDING, GeneratedReport.PROCESSING]:
            return Response(
                {'error': 'Only pending or processing reports can be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            report.status = GeneratedReport.CANCELLED
            report.completed_at = timezone.now()
            report.save()
            
            # Log action
            log_action(
                user=request.user,
                branch=report.branch,
                instance=report,
                action='REPORT_CANCELLED',
                metadata={
                    'report_number': report.report_number
                }
            )
            
            return Response({
                'message': 'Report generation cancelled',
                'report_id': report.id,
                'status': report.status
            })
            
        except Exception as e:
            logger.error(f"Error cancelling report: {str(e)}")
            return Response(
                {'error': f'Failed to cancel report: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get report statistics"""
        user = request.user
        
        # Get base queryset
        queryset = self.get_queryset()
        
        # Calculate statistics
        total_reports = queryset.count()
        completed_reports = queryset.filter(status=GeneratedReport.COMPLETED).count()
        failed_reports = queryset.filter(status=GeneratedReport.FAILED).count()
        pending_reports = queryset.filter(status__in=[GeneratedReport.PENDING, GeneratedReport.PROCESSING]).count()
        
        success_rate = (completed_reports / total_reports * 100) if total_reports > 0 else 0
        
        avg_generation_time = queryset.filter(
            generation_duration__isnull=False,
            status=GeneratedReport.COMPLETED
        ).aggregate(
            avg_time=Avg('generation_duration')
        )['avg_time'] or timedelta(0)
        
        # Recent reports
        recent_reports = queryset.order_by('-generated_at')[:10]
        recent_serializer = GeneratedReportSerializer(recent_reports, many=True, context={'request': request})
        
        return Response({
            'total_reports': total_reports,
            'completed_reports': completed_reports,
            'failed_reports': failed_reports,
            'pending_reports': pending_reports,
            'success_rate': round(success_rate, 2),
            'avg_generation_time_seconds': avg_generation_time.total_seconds(),
            'recent_reports': recent_serializer.data
        })
    
    def _can_access_report(self, user, report):
        """Check if user can access the report"""
        if user.is_superuser or user.role == 'clinic_manager':
            return True
        
        if user == report.generated_by:
            return True
        
        # Check template permissions
        return report.template.can_access(user)


class DashboardViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Dashboards"""
    queryset = Dashboard.objects.filter(is_active=True)
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated, HasBranchAccess]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['dashboard_type', 'is_active', 'is_public', 'branch']
    search_fields = ['name', 'description']
    ordering_fields = ['sort_order', 'name', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Filter by branch
        branch_id = getattr(self.request, 'branch_id', None)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        elif not user.is_superuser and hasattr(user, 'branch'):
            queryset = queryset.filter(branch=user.branch)
        
        # Filter by user access
        if not user.is_superuser:
            queryset = queryset.filter(
                Q(is_public=True) |
                Q(created_by=user) |
                Q(shared_with=user)
            ).distinct()
        
        return queryset
    
    def perform_create(self, serializer):
        # Set branch from request
        branch_id = getattr(self.request, 'branch_id', None)
        if branch_id:
            from apps.clinics.models import Branch
            branch = Branch.objects.get(id=branch_id)
            instance = serializer.save(branch=branch, created_by=self.request.user)
        else:
            instance = serializer.save(created_by=self.request.user)
        
        # Add creator to shared_with if not public
        if not instance.is_public:
            instance.shared_with.add(self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Clone a dashboard"""
        dashboard = self.get_object()
        
        serializer = DashboardCloneSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Create new dashboard
                new_dashboard = Dashboard.objects.create(
                    name=serializer.validated_data['new_name'],
                    description=dashboard.description,
                    dashboard_type=dashboard.dashboard_type,
                    layout_config=dashboard.layout_config.copy(),
                    is_public=dashboard.is_public,
                    icon=dashboard.icon,
                    color=dashboard.color,
                    sort_order=dashboard.sort_order,
                    branch=dashboard.branch,
                    created_by=request.user
                )
                
                # Clone widgets if requested
                if serializer.validated_data.get('clone_widgets', True):
                    for widget in dashboard.widgets.filter(is_active=True):
                        DashboardWidget.objects.create(
                            dashboard=new_dashboard,
                            name=widget.name,
                            widget_type=widget.widget_type,
                            config=widget.config.copy(),
                            data_source_type=widget.data_source_type,
                            report_template=widget.report_template,
                            query_sql=widget.query_sql,
                            api_endpoint=widget.api_endpoint,
                            static_data=widget.static_data.copy(),
                            width=widget.width,
                            height=widget.height,
                            position_x=widget.position_x,
                            position_y=widget.position_y,
                            refresh_interval=widget.refresh_interval,
                            branch=widget.branch
                        )
                
                # Share with current user if requested
                if serializer.validated_data.get('share_with_current_user', True):
                    new_dashboard.shared_with.add(request.user)
                
                # Log action
                log_action(
                    user=request.user,
                    branch=dashboard.branch,
                    instance=new_dashboard,
                    action='DASHBOARD_CLONED',
                    metadata={
                        'original_dashboard_id': str(dashboard.id),
                        'original_dashboard_name': dashboard.name
                    }
                )
                
                return Response(
                    DashboardSerializer(new_dashboard, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
                
        except Exception as e:
            logger.error(f"Error cloning dashboard: {str(e)}")
            return Response(
                {'error': f'Failed to clone dashboard: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def widgets(self, request, pk=None):
        """Get widgets for this dashboard"""
        dashboard = self.get_object()
        widgets = dashboard.widgets.filter(is_active=True).order_by('position_y', 'position_x')
        
        serializer = DashboardWidgetSerializer(widgets, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set this dashboard as default for its type"""
        dashboard = self.get_object()
        
        try:
            dashboard.is_default = True
            dashboard.save()
            
            return Response({
                'message': f'{dashboard.name} set as default {dashboard.get_dashboard_type_display()} dashboard',
                'dashboard_id': dashboard.id
            })
            
        except Exception as e:
            logger.error(f"Error setting default dashboard: {str(e)}")
            return Response(
                {'error': f'Failed to set default dashboard: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DashboardWidgetViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Dashboard Widgets"""
    queryset = DashboardWidget.objects.filter(is_active=True)
    serializer_class = DashboardWidgetSerializer
    permission_classes = [IsAuthenticated, HasBranchAccess]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['widget_type', 'is_active', 'dashboard', 'branch']
    search_fields = ['name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch
        branch_id = getattr(self.request, 'branch_id', None)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Filter by dashboard access
        user = self.request.user
        if not user.is_superuser:
            accessible_dashboards = Dashboard.objects.filter(
                Q(is_public=True) |
                Q(created_by=user) |
                Q(shared_with=user)
            )
            queryset = queryset.filter(dashboard__in=accessible_dashboards)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def data(self, request, pk=None):
        """Get data for widget"""
        widget = self.get_object()
        
        serializer = WidgetDataRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Update last refreshed time
            widget.last_refreshed_at = timezone.now()
            widget.save()
            
            # Get widget data based on data source
            data = widget.get_data()
            
            return Response({
                'widget_id': widget.id,
                'widget_name': widget.name,
                'widget_type': widget.widget_type,
                'data': data,
                'last_refreshed': widget.last_refreshed_at,
                'refresh_interval': widget.refresh_interval
            })
            
        except Exception as e:
            logger.error(f"Error getting widget data: {str(e)}")
            return Response(
                {'error': f'Failed to get widget data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        """Force refresh widget data"""
        widget = self.get_object()
        
        try:
            # Update last refreshed time
            widget.last_refreshed_at = timezone.now()
            widget.save()
            
            return Response({
                'message': 'Widget data refresh triggered',
                'widget_id': widget.id,
                'last_refreshed': widget.last_refreshed_at
            })
            
        except Exception as e:
            logger.error(f"Error refreshing widget: {str(e)}")
            return Response(
                {'error': f'Failed to refresh widget: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ReportScheduleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Report Schedules"""
    queryset = ReportSchedule.objects.all()
    serializer_class = ReportScheduleSerializer
    permission_classes = [IsAuthenticated, IsManager, HasBranchAccess]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'frequency', 'template', 'branch']
    search_fields = ['schedule_number', 'template__name']
    ordering_fields = ['next_run_at', 'last_run_at', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch
        branch_id = getattr(self.request, 'branch_id', None)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Filter by active schedules
        active_only = self.request.query_params.get('active_only', 'false').lower() == 'true'
        if active_only:
            queryset = queryset.filter(status=ReportSchedule.ACTIVE)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def execute_now(self, request, pk=None):
        """Execute schedule immediately"""
        schedule = self.get_object()
        
        if schedule.status != ReportSchedule.ACTIVE:
            return Response(
                {'error': 'Only active schedules can be executed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Execute schedule
            schedule.execute()
            
            # Log action
            log_action(
                user=request.user,
                branch=schedule.branch,
                instance=schedule,
                action='SCHEDULE_EXECUTED_MANUALLY',
                metadata={
                    'schedule_number': schedule.schedule_number,
                    'template_name': schedule.template.name
                }
            )
            
            return Response({
                'message': 'Schedule executed successfully',
                'schedule_id': schedule.id,
                'last_run_at': schedule.last_run_at,
                'last_run_status': schedule.last_run_status
            })
            
        except Exception as e:
            logger.error(f"Error executing schedule: {str(e)}")
            return Response(
                {'error': f'Failed to execute schedule: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause a schedule"""
        schedule = self.get_object()
        
        if schedule.status != ReportSchedule.ACTIVE:
            return Response(
                {'error': 'Only active schedules can be paused'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            schedule.status = ReportSchedule.PAUSED
            schedule.save()
            
            # Log action
            log_action(
                user=request.user,
                branch=schedule.branch,
                instance=schedule,
                action='SCHEDULE_PAUSED',
                metadata={
                    'schedule_number': schedule.schedule_number
                }
            )
            
            return Response({
                'message': 'Schedule paused',
                'schedule_id': schedule.id,
                'status': schedule.status
            })
            
        except Exception as e:
            logger.error(f"Error pausing schedule: {str(e)}")
            return Response(
                {'error': f'Failed to pause schedule: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume a paused schedule"""
        schedule = self.get_object()
        
        if schedule.status != ReportSchedule.PAUSED:
            return Response(
                {'error': 'Only paused schedules can be resumed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            schedule.status = ReportSchedule.ACTIVE
            schedule.calculate_next_run()
            schedule.save()
            
            # Log action
            log_action(
                user=request.user,
                branch=schedule.branch,
                instance=schedule,
                action='SCHEDULE_RESUMED',
                metadata={
                    'schedule_number': schedule.schedule_number
                }
            )
            
            return Response({
                'message': 'Schedule resumed',
                'schedule_id': schedule.id,
                'status': schedule.status,
                'next_run_at': schedule.next_run_at
            })
            
        except Exception as e:
            logger.error(f"Error resuming schedule: {str(e)}")
            return Response(
                {'error': f'Failed to resume schedule: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ReportExportViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing Report Exports"""
    queryset = ReportExport.objects.all()
    serializer_class = ReportExportSerializer
    permission_classes = [IsAuthenticated, HasBranchAccess]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['export_format', 'generated_report', 'branch']
    ordering_fields = ['exported_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch
        branch_id = getattr(self.request, 'branch_id', None)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Filter by user permissions
        user = self.request.user
        if not user.is_superuser and user.role not in ['clinic_manager', 'doctor']:
            # Users can only see exports they created
            queryset = queryset.filter(exported_by=user)
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download export file"""
        export = self.get_object()
        
        # Check permission
        if not self._can_access_export(request.user, export):
            return Response(
                {'error': 'You do not have permission to download this export'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # In production, serve the actual file
        # For now, return file info
        return Response({
            'export_id': export.id,
            'export_number': export.export_number,
            'export_format': export.export_format,
            'file_path': export.file_path,
            'file_size': export.file_size,
            'generated_report': export.generated_report.report_number,
            'message': 'File download would be served here in production'
        })
    
    def _can_access_export(self, user, export):
        """Check if user can access the export"""
        if user.is_superuser or user.role == 'clinic_manager':
            return True
        
        if user == export.exported_by:
            return True
        
        # Check if user can access the generated report
        return export.generated_report.template.can_access(user)


class ReportFavoriteViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Report Favorites"""
    queryset = ReportFavorite.objects.all()
    serializer_class = ReportFavoriteSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def templates(self, request):
        """Get favorite report templates"""
        favorites = self.get_queryset()
        template_ids = favorites.values_list('report_template_id', flat=True)
        
        templates = ReportTemplate.objects.filter(
            id__in=template_ids,
            is_active=True
        )
        
        serializer = ReportTemplateSerializer(templates, many=True, context={'request': request})
        return Response(serializer.data)


# API Views for specific operations
class ReportsAPIView(APIView):
    """API for report operations"""
    permission_classes = [IsAuthenticated, HasBranchAccess]
    
    def get(self, request, format=None):
        """Get filtered reports"""
        serializer = ReportFilterSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Build filters
        filters = Q()
        
        # Branch filter
        branch_id = getattr(request, 'branch_id', None)
        if branch_id:
            filters &= Q(branch_id=branch_id)
        
        # Date range
        start_date = serializer.validated_data.get('start_date')
        end_date = serializer.validated_data.get('end_date')
        
        if start_date:
            filters &= Q(generated_at__date__gte=start_date)
        if end_date:
            filters &= Q(generated_at__date__lte=end_date)
        
        # Report type
        report_type = serializer.validated_data.get('report_type')
        if report_type:
            filters &= Q(template__report_type=report_type)
        
        # Status
        status = serializer.validated_data.get('status')
        if status:
            filters &= Q(status=status)
        
        # Template
        template_id = serializer.validated_data.get('template_id')
        if template_id:
            filters &= Q(template_id=template_id)
        
        # Search
        search = serializer.validated_data.get('search')
        if search:
            filters &= (
                Q(report_number__icontains=search) |
                Q(template__name__icontains=search)
            )
        
        # Get reports
        reports = GeneratedReport.objects.filter(filters).order_by('-generated_at')
        
        serializer = GeneratedReportSerializer(reports, many=True, context={'request': request})
        return Response(serializer.data)


class ReportStatisticsAPIView(APIView):
    """API for report statistics"""
    permission_classes = [IsAuthenticated, HasBranchAccess]
    
    def get(self, request):
        """Get comprehensive report statistics"""
        branch_id = getattr(request, 'branch_id', None)
        
        # Get base querysets
        if branch_id:
            templates = ReportTemplate.objects.filter(branch_id=branch_id, is_active=True)
            reports = GeneratedReport.objects.filter(branch_id=branch_id)
            schedules = ReportSchedule.objects.filter(branch_id=branch_id)
            dashboards = Dashboard.objects.filter(branch_id=branch_id, is_active=True)
        else:
            templates = ReportTemplate.objects.filter(is_active=True)
            reports = GeneratedReport.objects.all()
            schedules = ReportSchedule.objects.all()
            dashboards = Dashboard.objects.filter(is_active=True)
        
        # Calculate statistics
        total_templates = templates.count()
        total_generated = reports.count()
        total_scheduled = schedules.count()
        total_dashboards = dashboards.count()
        
        completed_reports = reports.filter(status=GeneratedReport.COMPLETED).count()
        success_rate = (completed_reports / total_generated * 100) if total_generated > 0 else 0
        
        avg_generation_time = reports.filter(
            generation_duration__isnull=False,
            status=GeneratedReport.COMPLETED
        ).aggregate(
            avg_time=Avg('generation_duration')
        )['avg_time'] or timedelta(0)
        
        # Recent reports
        recent_reports = reports.order_by('-generated_at')[:10]
        recent_serializer = GeneratedReportSerializer(recent_reports, many=True, context={'request': request})
        
        # Top templates by usage
        top_templates = reports.values(
            'template__name', 'template__code'
        ).annotate(
            count=Count('id'),
            last_run=Max('generated_at')
        ).order_by('-count')[:5]
        
        data = {
            'total_templates': total_templates,
            'total_generated': total_generated,
            'total_scheduled': total_scheduled,
            'total_dashboards': total_dashboards,
            'success_rate': round(success_rate, 2),
            'avg_generation_time_seconds': avg_generation_time.total_seconds(),
            'recent_reports': recent_serializer.data,
            'top_templates': list(top_templates),
            'generation_status': {
                'completed': completed_reports,
                'failed': reports.filter(status=GeneratedReport.FAILED).count(),
                'pending': reports.filter(status__in=[GeneratedReport.PENDING, GeneratedReport.PROCESSING]).count(),
                'cancelled': reports.filter(status=GeneratedReport.CANCELLED).count(),
            }
        }
        
        return Response(data)


class BranchPerformanceAPIView(APIView):
    """API for branch performance reports"""
    permission_classes = [IsAuthenticated, IsManager]
    
    def get(self, request):
        """Get branch performance data"""
        from datetime import datetime, timedelta
        
        # Get date range (last 30 days by default)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        # Get all branches
        from apps.clinics.models import Branch
        
        if request.user.is_superuser:
            branches = Branch.objects.filter(is_active=True)
        else:
            # Get user's branches
            if hasattr(request.user, 'user_branches'):
                branches = Branch.objects.filter(
                    id__in=request.user.user_branches.filter(is_active=True).values_list('branch_id', flat=True),
                    is_active=True
                )
            else:
                branches = Branch.objects.filter(is_active=True)
        
        performance_data = []
        
        for branch in branches:
            # Get financial data
            invoices = GeneratedReport.objects.filter(
                branch=branch,
                generated_at__date__range=[start_date, end_date]
            )  # Simplified - would use actual financial models
            
            total_revenue = Decimal('0')  # Would calculate from invoices
            
            # Get patient data
            total_patients = 0  # Would query patients model
            
            # Get appointment data
            total_appointments = 0  # Would query appointments model
            
            # Calculate metrics
            collection_rate = 0  # Would calculate
            utilization_rate = 0  # Would calculate
            
            performance_data.append({
                'branch_id': branch.id,
                'branch_name': branch.name,
                'total_revenue': total_revenue,
                'total_patients': total_patients,
                'total_appointments': total_appointments,
                'collection_rate': collection_rate,
                'utilization_rate': utilization_rate,
            })
        
        serializer = BranchPerformanceSerializer(performance_data, many=True)
        return Response(serializer.data)


class FinancialSummaryAPIView(APIView):
    """API for financial summary reports"""
    permission_classes = [IsAuthenticated, IsManager, HasBranchAccess]
    
    def get(self, request):
        """Get financial summary"""
        branch_id = getattr(request, 'branch_id', None)
        
        # Get date range
        end_date = timezone.now().date()
        start_date = request.query_params.get('start_date', end_date - timedelta(days=30))
        
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        # Calculate financial data
        # This would integrate with your billing system
        # For now, return placeholder data
        
        data = {
            'total_revenue': Decimal('0'),
            'total_expenses': Decimal('0'),
            'net_profit': Decimal('0'),
            'outstanding_amount': Decimal('0'),
            'collection_efficiency': 0.0,
            'daily_revenue': [],
            'revenue_by_doctor': [],
        }
        
        serializer = FinancialSummarySerializer(data)
        return Response(serializer.data)


class QuickReportsAPIView(APIView):
    """API for quick, pre-defined reports"""
    permission_classes = [IsAuthenticated, HasBranchAccess]
    
    def get(self, request, report_type):
        """Get quick report"""
        branch_id = getattr(request, 'branch_id', None)
        
        # Get date range (last 30 days by default)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        # Parse custom date range if provided
        custom_start = request.query_params.get('start_date')
        custom_end = request.query_params.get('end_date')
        
        if custom_start:
            start_date = datetime.strptime(custom_start, '%Y-%m-%d').date()
        if custom_end:
            end_date = datetime.strptime(custom_end, '%Y-%m-%d').date()
        
        # Generate report based on type
        if report_type == 'daily_sales':
            data = self._get_daily_sales(start_date, end_date, branch_id)
        elif report_type == 'doctor_performance':
            data = self._get_doctor_performance(start_date, end_date, branch_id)
        elif report_type == 'patient_statistics':
            data = self._get_patient_statistics(start_date, end_date, branch_id)
        elif report_type == 'appointment_summary':
            data = self._get_appointment_summary(start_date, end_date, branch_id)
        else:
            return Response(
                {'error': f'Unknown report type: {report_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(data)
    
    def _get_daily_sales(self, start_date, end_date, branch_id):
        """Get daily sales report"""
        # This would query your billing system
        return {
            'report_type': 'daily_sales',
            'period': {'start_date': start_date, 'end_date': end_date},
            'summary': {'total_sales': 0, 'average_daily': 0},
            'daily_data': []
        }
    
    def _get_doctor_performance(self, start_date, end_date, branch_id):
        """Get doctor performance report"""
        # This would query your visits/billing system
        return {
            'report_type': 'doctor_performance',
            'period': {'start_date': start_date, 'end_date': end_date},
            'doctors': []
        }
    
    def _get_patient_statistics(self, start_date, end_date, branch_id):
        """Get patient statistics report"""
        # This would query your patients system
        return {
            'report_type': 'patient_statistics',
            'period': {'start_date': start_date, 'end_date': end_date},
            'statistics': {
                'total_patients': 0,
                'new_patients': 0,
                'returning_patients': 0
            }
        }
    
    def _get_appointment_summary(self, start_date, end_date, branch_id):
        """Get appointment summary report"""
        # This would query your appointments system
        return {
            'report_type': 'appointment_summary',
            'period': {'start_date': start_date, 'end_date': end_date},
            'summary': {
                'total_appointments': 0,
                'completed': 0,
                'cancelled': 0,
                'no_show': 0
            }
        }