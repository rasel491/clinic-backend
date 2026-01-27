# apps/reports/serializers.py

from rest_framework import serializers
from django.utils import timezone
from django.db.models import Count, Sum, Avg
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import (
    ReportCategory, ReportTemplate, GeneratedReport,
    ReportData, Dashboard, DashboardWidget, ReportSchedule,
    ReportExport, ReportFavorite
)
from apps.clinics.serializers import BranchSerializer
from apps.accounts.serializers import UserSerializer


class ReportCategorySerializer(serializers.ModelSerializer):
    """Serializer for Report Categories"""
    
    class Meta:
        model = ReportCategory
        fields = [
            'id', 'name', 'code', 'description',
            'icon', 'sort_order', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ReportTemplateSerializer(serializers.ModelSerializer):
    """Serializer for Report Templates"""
    
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True, required=False)
    category = ReportCategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True, required=False)
    last_run_by = UserSerializer(read_only=True)
    
    # Statistics
    total_runs = serializers.SerializerMethodField()
    last_run_status = serializers.SerializerMethodField()
    avg_generation_time = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportTemplate
        fields = [
            'id', 'name', 'code', 'description',
            'report_type', 'category', 'category_id',
            'query_sql', 'query_parameters', 'output_format',
            'is_scheduled', 'frequency', 'schedule_time', 'schedule_day',
            'requires_permission', 'allowed_roles',
            'icon', 'sort_order', 'is_active',
            'html_template', 'excel_template',
            'branch', 'branch_id',
            'last_run_at', 'last_run_by',
            
            # Statistics
            'total_runs', 'last_run_status', 'avg_generation_time',
            
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'last_run_at', 'last_run_by',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def get_total_runs(self, obj):
        return obj.generated_reports.count()
    
    def get_last_run_status(self, obj):
        last_report = obj.generated_reports.order_by('-generated_at').first()
        return last_report.status if last_report else None
    
    def get_avg_generation_time(self, obj):
        reports = obj.generated_reports.filter(
            generation_duration__isnull=False,
            status=GeneratedReport.COMPLETED
        )
        if reports.exists():
            total_seconds = sum(
                r.generation_duration.total_seconds() 
                for r in reports
            )
            return total_seconds / reports.count()
        return 0
    
    def validate_query_parameters(self, value):
        """Validate query parameters JSON schema"""
        try:
            # Ensure it's valid JSON
            if value:
                json.dumps(value)
            return value
        except (TypeError, ValueError):
            raise serializers.ValidationError("Invalid JSON format for query parameters")
    
    def validate_allowed_roles(self, value):
        """Validate allowed roles list"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Allowed roles must be a list")
        
        valid_roles = ['super_admin', 'clinic_manager', 'doctor', 
                      'receptionist', 'cashier', 'lab_technician', 
                      'inventory_manager']
        
        for role in value:
            if role not in valid_roles:
                raise serializers.ValidationError(f"Invalid role: {role}")
        
        return value


class ReportTemplateCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Report Templates"""
    
    class Meta:
        model = ReportTemplate
        fields = [
            'name', 'code', 'description', 'report_type',
            'category_id', 'query_sql', 'query_parameters',
            'output_format', 'is_scheduled', 'frequency',
            'schedule_time', 'schedule_day', 'allowed_roles',
            'html_template', 'branch_id'
        ]
    
    def validate_code(self, value):
        """Ensure code is unique"""
        if ReportTemplate.objects.filter(code=value).exists():
            raise serializers.ValidationError("A report template with this code already exists")
        return value


class GeneratedReportSerializer(serializers.ModelSerializer):
    """Serializer for Generated Reports"""
    
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True, required=False)
    template = ReportTemplateSerializer(read_only=True)
    template_id = serializers.IntegerField(write_only=True)
    generated_by = UserSerializer(read_only=True)
    generated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    # File info
    file_size_display = serializers.SerializerMethodField()
    generation_duration_display = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    
    # Status flags
    can_download = serializers.SerializerMethodField()
    can_retry = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    
    class Meta:
        model = GeneratedReport
        fields = [
            'id', 'report_number', 'template', 'template_id',
            'parameters', 'start_date', 'end_date', 'status',
            'error_message', 'stack_trace',
            'generated_by', 'generated_by_id', 'generated_at',
            'completed_at', 'file_path', 'file_size', 'file_size_display',
            'download_count', 'generation_duration', 'generation_duration_display',
            'row_count', 'is_archived', 'archive_reason',
            'branch', 'branch_id',
            
            # Computed fields
            'download_url', 'can_download', 'can_retry', 'can_cancel',
            
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'report_number', 'status', 'error_message', 'stack_trace',
            'generated_at', 'completed_at', 'file_path', 'file_size',
            'download_count', 'generation_duration', 'row_count',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def get_file_size_display(self, obj):
        """Format file size for display"""
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        elif obj.file_size < 1024 * 1024 * 1024:
            return f"{obj.file_size / (1024 * 1024):.1f} MB"
        else:
            return f"{obj.file_size / (1024 * 1024 * 1024):.1f} GB"
    
    def get_generation_duration_display(self, obj):
        """Format generation duration for display"""
        if not obj.generation_duration:
            return "N/A"
        
        total_seconds = obj.generation_duration.total_seconds()
        if total_seconds < 60:
            return f"{total_seconds:.1f} sec"
        elif total_seconds < 3600:
            return f"{total_seconds / 60:.1f} min"
        else:
            return f"{total_seconds / 3600:.1f} hours"
    
    def get_download_url(self, obj):
        """Get download URL for the report"""
        if obj.status == GeneratedReport.COMPLETED and obj.file_path:
            return f"/api/reports/{obj.id}/download/"
        return None
    
    def get_can_download(self, obj):
        """Check if report can be downloaded"""
        return obj.status == GeneratedReport.COMPLETED and obj.file_path
    
    def get_can_retry(self, obj):
        """Check if report can be retried"""
        return obj.status in [GeneratedReport.FAILED, GeneratedReport.CANCELLED]
    
    def get_can_cancel(self, obj):
        """Check if report can be cancelled"""
        return obj.status in [GeneratedReport.PENDING, GeneratedReport.PROCESSING]


class ReportDataSerializer(serializers.ModelSerializer):
    """Serializer for Report Data"""
    
    generated_report = GeneratedReportSerializer(read_only=True)
    
    class Meta:
        model = ReportData
        fields = [
            'id', 'generated_report', 'data_json', 'summary',
            'data_version', 'compressed',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class DashboardSerializer(serializers.ModelSerializer):
    """Serializer for Dashboards"""
    
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True, required=False)
    shared_with = UserSerializer(many=True, read_only=True)
    shared_with_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=UserSerializer.Meta.model.objects.all(),
        write_only=True,
        required=False
    )
    
    # Statistics
    widget_count = serializers.SerializerMethodField()
    last_updated = serializers.SerializerMethodField()
    
    class Meta:
        model = Dashboard
        fields = [
            'id', 'name', 'description', 'dashboard_type',
            'layout_config', 'is_public', 'shared_with', 'shared_with_ids',
            'icon', 'color', 'sort_order', 'is_active', 'is_default',
            'branch', 'branch_id',
            
            # Statistics
            'widget_count', 'last_updated',
            
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    def get_widget_count(self, obj):
        return obj.widgets.count()
    
    def get_last_updated(self, obj):
        return obj.updated_at
    
    def validate_layout_config(self, value):
        """Validate layout configuration"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Layout config must be a JSON object")
        return value
    
    def create(self, validated_data):
        """Create dashboard with shared users"""
        shared_with_ids = validated_data.pop('shared_with_ids', [])
        dashboard = Dashboard.objects.create(**validated_data)
        dashboard.shared_with.set(shared_with_ids)
        return dashboard
    
    def update(self, instance, validated_data):
        """Update dashboard with shared users"""
        shared_with_ids = validated_data.pop('shared_with_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        if shared_with_ids is not None:
            instance.shared_with.set(shared_with_ids)
        
        return instance


class DashboardWidgetSerializer(serializers.ModelSerializer):
    """Serializer for Dashboard Widgets"""
    
    dashboard = DashboardSerializer(read_only=True)
    dashboard_id = serializers.IntegerField(write_only=True)
    report_template = ReportTemplateSerializer(read_only=True)
    report_template_id = serializers.IntegerField(write_only=True, required=False)
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True, required=False)
    
    # Data preview
    data_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = DashboardWidget
        fields = [
            'id', 'dashboard', 'dashboard_id', 'name', 'widget_type',
            'config', 'data_source_type', 'report_template', 'report_template_id',
            'query_sql', 'api_endpoint', 'static_data',
            'width', 'height', 'position_x', 'position_y',
            'refresh_interval', 'last_refreshed_at', 'is_active',
            'branch', 'branch_id',
            
            # Computed fields
            'data_preview',
            
            'created_at', 'updated_at'
        ]
        read_only_fields = ['last_refreshed_at', 'created_at', 'updated_at']
    
    def get_data_preview(self, obj):
        """Get preview of widget data"""
        # This would fetch and return sample data for the widget
        # For now, return empty dict
        return {}
    
    def validate(self, data):
        """Validate widget configuration"""
        data_source_type = data.get('data_source_type')
        
        if data_source_type == 'REPORT' and not data.get('report_template'):
            raise serializers.ValidationError({
                'report_template': 'Report template is required for REPORT data source'
            })
        
        elif data_source_type == 'QUERY' and not data.get('query_sql'):
            raise serializers.ValidationError({
                'query_sql': 'SQL query is required for QUERY data source'
            })
        
        elif data_source_type == 'API' and not data.get('api_endpoint'):
            raise serializers.ValidationError({
                'api_endpoint': 'API endpoint is required for API data source'
            })
        
        return data
    
    def validate_config(self, value):
        """Validate widget configuration"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Config must be a JSON object")
        
        # Validate chart-specific config
        widget_type = self.initial_data.get('widget_type')
        
        if widget_type == 'CHART':
            if 'chart_type' not in value:
                raise serializers.ValidationError({
                    'config': 'chart_type is required for CHART widgets'
                })
        
        return value


class ReportScheduleSerializer(serializers.ModelSerializer):
    """Serializer for Report Schedules"""
    
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True, required=False)
    template = ReportTemplateSerializer(read_only=True)
    template_id = serializers.IntegerField(write_only=True)
    created_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    
    # Schedule info
    next_run_display = serializers.SerializerMethodField()
    last_run_display = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    # Status flags
    can_execute_now = serializers.SerializerMethodField()
    can_pause = serializers.SerializerMethodField()
    can_resume = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportSchedule
        fields = [
            'id', 'schedule_number', 'template', 'template_id',
            'frequency', 'schedule_time', 'schedule_day',
            'start_date', 'end_date', 'is_recurring',
            'parameters', 'delivery_method', 'email_recipients',
            'email_subject', 'email_body', 'status',
            'next_run_at', 'last_run_at', 'last_run_status',
            'total_runs', 'successful_runs', 'failed_runs',
            'created_by', 'created_by_id',
            'branch', 'branch_id',
            
            # Computed fields
            'next_run_display', 'last_run_display', 'success_rate',
            'can_execute_now', 'can_pause', 'can_resume',
            
            'created_at', 'updated_at', 'updated_by'
        ]
        read_only_fields = [
            'schedule_number', 'next_run_at', 'last_run_at',
            'last_run_status', 'total_runs', 'successful_runs',
            'failed_runs', 'created_at', 'updated_at', 'updated_by'
        ]
    
    def get_next_run_display(self, obj):
        """Format next run time for display"""
        if not obj.next_run_at:
            return "Not scheduled"
        return obj.next_run_at.strftime("%Y-%m-%d %I:%M %p")
    
    def get_last_run_display(self, obj):
        """Format last run time for display"""
        if not obj.last_run_at:
            return "Never run"
        return obj.last_run_at.strftime("%Y-%m-%d %I:%M %p")
    
    def get_success_rate(self, obj):
        """Calculate success rate"""
        if obj.total_runs == 0:
            return 0
        return (obj.successful_runs / obj.total_runs) * 100
    
    def get_can_execute_now(self, obj):
        """Check if schedule can be executed now"""
        return obj.status == ReportSchedule.ACTIVE
    
    def get_can_pause(self, obj):
        """Check if schedule can be paused"""
        return obj.status == ReportSchedule.ACTIVE
    
    def get_can_resume(self, obj):
        """Check if schedule can be resumed"""
        return obj.status == ReportSchedule.PAUSED
    
    def validate_email_recipients(self, value):
        """Validate email recipients list"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Email recipients must be a list")
        
        # Simple email validation
        import re
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        for email in value:
            if not re.match(email_regex, email):
                raise serializers.ValidationError(f"Invalid email address: {email}")
        
        return value
    
    def validate_parameters(self, value):
        """Validate report parameters"""
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            raise serializers.ValidationError("Invalid JSON format for parameters")


class ReportExportSerializer(serializers.ModelSerializer):
    """Serializer for Report Exports"""
    
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True, required=False)
    generated_report = GeneratedReportSerializer(read_only=True)
    generated_report_id = serializers.IntegerField(write_only=True)
    exported_by = UserSerializer(read_only=True)
    exported_by_id = serializers.IntegerField(write_only=True, required=False)
    
    # File info
    file_size_display = serializers.SerializerMethodField()
    export_duration_display = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportExport
        fields = [
            'id', 'export_number', 'generated_report', 'generated_report_id',
            'export_format', 'file_path', 'file_size', 'file_size_display',
            'include_charts', 'include_summary', 'include_details',
            'exported_by', 'exported_by_id', 'exported_at',
            'export_duration', 'export_duration_display',
            'branch', 'branch_id',
            
            # Computed fields
            'download_url',
            
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'export_number', 'exported_at', 'export_duration',
            'created_at', 'updated_at'
        ]
    
    def get_file_size_display(self, obj):
        """Format file size for display"""
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        elif obj.file_size < 1024 * 1024 * 1024:
            return f"{obj.file_size / (1024 * 1024):.1f} MB"
        else:
            return f"{obj.file_size / (1024 * 1024 * 1024):.1f} GB"
    
    def get_export_duration_display(self, obj):
        """Format export duration for display"""
        if not obj.export_duration:
            return "N/A"
        
        total_seconds = obj.export_duration.total_seconds()
        if total_seconds < 60:
            return f"{total_seconds:.1f} sec"
        elif total_seconds < 3600:
            return f"{total_seconds / 60:.1f} min"
        else:
            return f"{total_seconds / 3600:.1f} hours"
    
    def get_download_url(self, obj):
        """Get download URL for the export"""
        return f"/api/reports/exports/{obj.id}/download/"


class ReportFavoriteSerializer(serializers.ModelSerializer):
    """Serializer for Report Favorites"""
    
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    report_template = ReportTemplateSerializer(read_only=True)
    report_template_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = ReportFavorite
        fields = [
            'id', 'user', 'user_id', 'report_template', 'report_template_id',
            'added_at', 'notes'
        ]
        read_only_fields = ['added_at']


# Request/Response serializers
class GenerateReportSerializer(serializers.Serializer):
    """Serializer for generating reports"""
    template_id = serializers.IntegerField(required=True)
    parameters = serializers.DictField(default=dict)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    output_format = serializers.ChoiceField(
        choices=ReportTemplate.OUTPUT_FORMAT_CHOICES,
        default=ReportTemplate.HTML
    )
    
    def validate(self, data):
        """Validate report generation request"""
        try:
            template = ReportTemplate.objects.get(id=data['template_id'])
            
            # Check if user can access this report
            if template.requires_permission:
                user = self.context['request'].user
                if not template.can_access(user):
                    raise serializers.ValidationError(
                        "You don't have permission to generate this report"
                    )
            
            # Validate date range
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            
            if start_date and end_date and start_date > end_date:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date'
                })
            
            # Validate parameters against template schema
            template_params = template.query_parameters or {}
            report_params = data.get('parameters', {})
            
            # Basic validation - in production, use JSON schema validation
            for param_name, param_schema in template_params.items():
                if param_schema.get('required', False) and param_name not in report_params:
                    raise serializers.ValidationError({
                        'parameters': f"Missing required parameter: {param_name}"
                    })
            
            return data
            
        except ReportTemplate.DoesNotExist:
            raise serializers.ValidationError({
                'template_id': 'Report template not found'
            })


class ScheduleReportSerializer(serializers.Serializer):
    """Serializer for scheduling reports"""
    template_id = serializers.IntegerField(required=True)
    frequency = serializers.ChoiceField(
        choices=ReportTemplate.FREQUENCY_CHOICES,
        required=True
    )
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=False)
    parameters = serializers.DictField(default=dict)
    delivery_method = serializers.ChoiceField(
        choices=ReportSchedule.DELIVERY_CHOICES,
        default=ReportSchedule.EMAIL
    )
    email_recipients = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        default=list
    )
    email_subject = serializers.CharField(required=False, allow_blank=True)
    email_body = serializers.CharField(required=False, allow_blank=True)


class WidgetDataRequestSerializer(serializers.Serializer):
    """Serializer for requesting widget data"""
    widget_id = serializers.IntegerField(required=False)
    widget_config = serializers.DictField(required=False)
    refresh = serializers.BooleanField(default=False)
    
    def validate(self, data):
        """Validate widget data request"""
        widget_id = data.get('widget_id')
        widget_config = data.get('widget_config')
        
        if not widget_id and not widget_config:
            raise serializers.ValidationError(
                "Either widget_id or widget_config must be provided"
            )
        
        return data


class ReportFilterSerializer(serializers.Serializer):
    """Serializer for filtering reports"""
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    report_type = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    template_id = serializers.IntegerField(required=False)
    search = serializers.CharField(required=False, allow_blank=True)


class DashboardCloneSerializer(serializers.Serializer):
    """Serializer for cloning dashboards"""
    new_name = serializers.CharField(required=True)
    clone_widgets = serializers.BooleanField(default=True)
    share_with_current_user = serializers.BooleanField(default=True)


# Statistics serializers
class ReportStatsSerializer(serializers.Serializer):
    """Serializer for report statistics"""
    total_templates = serializers.IntegerField()
    total_generated = serializers.IntegerField()
    total_scheduled = serializers.IntegerField()
    total_dashboards = serializers.IntegerField()
    success_rate = serializers.FloatField()
    avg_generation_time = serializers.FloatField()
    recent_reports = GeneratedReportSerializer(many=True)
    top_templates = serializers.ListField()


class BranchPerformanceSerializer(serializers.Serializer):
    """Serializer for branch performance data"""
    branch_id = serializers.IntegerField()
    branch_name = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_patients = serializers.IntegerField()
    total_appointments = serializers.IntegerField()
    collection_rate = serializers.FloatField()
    utilization_rate = serializers.FloatField()


class FinancialSummarySerializer(serializers.Serializer):
    """Serializer for financial summary"""
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    outstanding_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    collection_efficiency = serializers.FloatField()
    daily_revenue = serializers.ListField()
    revenue_by_doctor = serializers.ListField()