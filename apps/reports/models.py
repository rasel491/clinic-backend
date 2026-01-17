# apps/reports/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid

User = get_user_model()


class BaseModel(models.Model):
    """Base model with common fields"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class BranchScopedModel(models.Model):
    """Branch scoping mixin"""
    branch = models.ForeignKey('clinics.Branch', on_delete=models.PROTECT)
    
    class Meta:
        abstract = True


class AuditableModel(models.Model):
    """Audit fields mixin"""
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, editable=False,
        related_name='created_%(class)s'
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, editable=False,
        related_name='updated_%(class)s'
    )
    
    class Meta:
        abstract = True


class BaseAppModel(BaseModel, AuditableModel, BranchScopedModel):
    """Combined base model for all apps"""
    class Meta:
        abstract = True


class ReportCategory(BaseModel):
    """Categories for organizing reports"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class name")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Report Category"
        verbose_name_plural = "Report Categories"
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['code', 'is_active']),
        ]
    
    def __str__(self):
        return self.name


class ReportTemplate(BaseAppModel):
    """Predefined report templates with configurations"""
    
    # Report Types
    FINANCIAL = 'FINANCIAL'
    CLINICAL = 'CLINICAL'
    OPERATIONAL = 'OPERATIONAL'
    INVENTORY = 'INVENTORY'
    CUSTOM = 'CUSTOM'
    
    REPORT_TYPE_CHOICES = [
        (FINANCIAL, 'Financial Reports'),
        (CLINICAL, 'Clinical Reports'),
        (OPERATIONAL, 'Operational Reports'),
        (INVENTORY, 'Inventory Reports'),
        (CUSTOM, 'Custom Reports'),
    ]
    
    # Output Formats
    HTML = 'HTML'
    PDF = 'PDF'
    EXCEL = 'EXCEL'
    CSV = 'CSV'
    JSON = 'JSON'
    
    OUTPUT_FORMAT_CHOICES = [
        (HTML, 'HTML'),
        (PDF, 'PDF'),
        (EXCEL, 'Excel'),
        (CSV, 'CSV'),
        (JSON, 'JSON'),
    ]
    
    # Frequency
    DAILY = 'DAILY'
    WEEKLY = 'WEEKLY'
    MONTHLY = 'MONTHLY'
    QUARTERLY = 'QUARTERLY'
    YEARLY = 'YEARLY'
    ON_DEMAND = 'ON_DEMAND'
    
    FREQUENCY_CHOICES = [
        (DAILY, 'Daily'),
        (WEEKLY, 'Weekly'),
        (MONTHLY, 'Monthly'),
        (QUARTERLY, 'Quarterly'),
        (YEARLY, 'Yearly'),
        (ON_DEMAND, 'On Demand'),
    ]
    
    # Core fields
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    category = models.ForeignKey(
        ReportCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='templates'
    )
    
    # Configuration
    query_sql = models.TextField(blank=True, help_text="SQL query for the report")
    query_parameters = models.JSONField(
        default=dict, blank=True,
        help_text="JSON schema for report parameters"
    )
    output_format = models.CharField(max_length=10, choices=OUTPUT_FORMAT_CHOICES, default=HTML)
    
    # Schedule
    is_scheduled = models.BooleanField(default=False)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default=ON_DEMAND)
    schedule_time = models.TimeField(null=True, blank=True, help_text="Time to run scheduled reports")
    schedule_day = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Day of month for monthly reports"
    )
    
    # Access control
    requires_permission = models.BooleanField(default=True)
    allowed_roles = models.JSONField(
        default=list, blank=True,
        help_text="List of role codes allowed to view this report"
    )
    
    # Display
    icon = models.CharField(max_length=50, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Template files
    html_template = models.TextField(blank=True, help_text="HTML template for rendering")
    excel_template = models.FileField(
        upload_to='report_templates/excel/',
        null=True, blank=True
    )
    
    # Metadata
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_run_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='last_run_reports'
    )
    
    class Meta:
        verbose_name = "Report Template"
        verbose_name_plural = "Report Templates"
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['code', 'is_active']),
            models.Index(fields=['report_type', 'is_active']),
            models.Index(fields=['is_scheduled', 'frequency']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def can_access(self, user):
        """Check if user can access this report"""
        if not self.requires_permission:
            return True
        
        if not self.allowed_roles:
            return True
        
        # Check if user has any of the allowed roles
        user_roles = user.roles.all() if hasattr(user, 'roles') else []
        user_role_codes = [role.code for role in user_roles]
        
        return any(role in user_role_codes for role in self.allowed_roles)


class GeneratedReport(BaseAppModel):
    """Instance of a generated report"""
    
    # Generation Status
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (PROCESSING, 'Processing'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
        (CANCELLED, 'Cancelled'),
    ]
    
    # Core fields
    report_number = models.CharField(max_length=50, unique=True)
    template = models.ForeignKey(
        ReportTemplate, on_delete=models.PROTECT,
        related_name='generated_reports'
    )
    
    # Parameters
    parameters = models.JSONField(
        default=dict, blank=True,
        help_text="Parameters used for generating this report"
    )
    
    # Date range
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    error_message = models.TextField(blank=True)
    stack_trace = models.TextField(blank=True)
    
    # Generation info
    generated_by = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='generated_reports'
    )
    generated_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # File storage
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)
    
    # Performance
    generation_duration = models.DurationField(null=True, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    
    # Metadata
    is_archived = models.BooleanField(default=False)
    archive_reason = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Generated Report"
        verbose_name_plural = "Generated Reports"
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['report_number']),
            models.Index(fields=['template', 'status']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['generated_by', 'generated_at']),
            models.Index(fields=['status', 'generated_at']),
        ]
    
    def __str__(self):
        return f"Report {self.report_number} - {self.template.name}"
    
    def save(self, *args, **kwargs):
        if not self.report_number:
            self.report_number = self.generate_report_number()
        super().save(*args, **kwargs)
    
    def generate_report_number(self):
        """Generate unique report number: REP-YYYYMMDD-XXXXX"""
        date_str = timezone.now().strftime('%Y%m%d')
        
        last_report = GeneratedReport.objects.filter(
            report_number__startswith=f'REP-{date_str}-'
        ).order_by('report_number').last()
        
        if last_report:
            last_num = int(last_report.report_number[-5:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"REP-{date_str}-{new_num:05d}"
    
    def mark_completed(self, file_path, file_size, duration, row_count=0):
        """Mark report as completed"""
        self.status = self.COMPLETED
        self.file_path = file_path
        self.file_size = file_size
        self.generation_duration = duration
        self.row_count = row_count
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, error_message, stack_trace=''):
        """Mark report as failed"""
        self.status = self.FAILED
        self.error_message = error_message
        self.stack_trace = stack_trace
        self.completed_at = timezone.now()
        self.save()
    
    def increment_download_count(self):
        """Increment download counter"""
        self.download_count += 1
        self.save()


class ReportData(BaseModel):
    """Structured data for reports (for caching and analysis)"""
    generated_report = models.OneToOneField(
        GeneratedReport, on_delete=models.CASCADE,
        related_name='data'
    )
    
    # Data storage
    data_json = models.JSONField(
        default=dict, blank=True,
        help_text="JSON structure of report data"
    )
    
    # Summary fields (for quick access)
    summary = models.JSONField(
        default=dict, blank=True,
        help_text="Summary/aggregated data"
    )
    
    # Metadata
    data_version = models.CharField(max_length=20, default='1.0')
    compressed = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Report Data"
        verbose_name_plural = "Report Data"
        indexes = [
            models.Index(fields=['generated_report']),
        ]
    
    def __str__(self):
        return f"Data for {self.generated_report.report_number}"


class Dashboard(BaseAppModel):
    """User dashboards with widgets"""
    
    # Dashboard Types
    PERSONAL = 'PERSONAL'
    BRANCH = 'BRANCH'
    DEPARTMENT = 'DEPARTMENT'
    MANAGEMENT = 'MANAGEMENT'
    
    DASHBOARD_TYPE_CHOICES = [
        (PERSONAL, 'Personal Dashboard'),
        (BRANCH, 'Branch Dashboard'),
        (DEPARTMENT, 'Department Dashboard'),
        (MANAGEMENT, 'Management Dashboard'),
    ]
    
    # Core fields
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    dashboard_type = models.CharField(max_length=20, choices=DASHBOARD_TYPE_CHOICES, default=PERSONAL)
    
    # Layout
    layout_config = models.JSONField(
        default=dict, blank=True,
        help_text="Dashboard layout configuration"
    )
    
    # Access
    is_public = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(
        User, blank=True,
        related_name='shared_dashboards',
        help_text="Users with access to this dashboard"
    )
    
    # Display
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, blank=True, default='#3498db')
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Defaults
    is_default = models.BooleanField(default=False, help_text="Default dashboard for this type")
    
    class Meta:
        verbose_name = "Dashboard"
        verbose_name_plural = "Dashboards"
        ordering = ['sort_order', 'name']
        unique_together = ['branch', 'dashboard_type', 'is_default']
        indexes = [
            models.Index(fields=['dashboard_type', 'is_active']),
            models.Index(fields=['is_default', 'branch']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.branch}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default dashboard per type per branch
        if self.is_default:
            Dashboard.objects.filter(
                branch=self.branch,
                dashboard_type=self.dashboard_type,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        
        super().save(*args, **kwargs)


class DashboardWidget(BaseModel, BranchScopedModel):
    """Widgets on a dashboard"""
    
    # Widget Types
    CHART = 'CHART'
    TABLE = 'TABLE'
    METRIC = 'METRIC'
    KPI = 'KPI'
    LIST = 'LIST'
    CALENDAR = 'CALENDAR'
    CUSTOM = 'CUSTOM'
    
    WIDGET_TYPE_CHOICES = [
        (CHART, 'Chart'),
        (TABLE, 'Data Table'),
        (METRIC, 'Metric Card'),
        (KPI, 'KPI Card'),
        (LIST, 'List'),
        (CALENDAR, 'Calendar'),
        (CUSTOM, 'Custom Widget'),
    ]
    
    # Chart Types
    BAR_CHART = 'BAR'
    LINE_CHART = 'LINE'
    PIE_CHART = 'PIE'
    DONUT_CHART = 'DONUT'
    AREA_CHART = 'AREA'
    SCATTER_CHART = 'SCATTER'
    
    CHART_TYPE_CHOICES = [
        (BAR_CHART, 'Bar Chart'),
        (LINE_CHART, 'Line Chart'),
        (PIE_CHART, 'Pie Chart'),
        (DONUT_CHART, 'Donut Chart'),
        (AREA_CHART, 'Area Chart'),
        (SCATTER_CHART, 'Scatter Chart'),
    ]
    
    # Core fields
    dashboard = models.ForeignKey(
        Dashboard, on_delete=models.CASCADE,
        related_name='widgets'
    )
    name = models.CharField(max_length=200)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPE_CHOICES)
    
    # Configuration
    config = models.JSONField(
        default=dict, blank=True,
        help_text="Widget configuration (chart type, colors, etc.)"
    )
    
    # Data source
    data_source_type = models.CharField(
        max_length=20,
        choices=[
            ('REPORT', 'Report Template'),
            ('QUERY', 'SQL Query'),
            ('API', 'API Endpoint'),
            ('STATIC', 'Static Data'),
        ],
        default='REPORT'
    )
    
    report_template = models.ForeignKey(
        ReportTemplate, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='widgets'
    )
    
    query_sql = models.TextField(blank=True)
    api_endpoint = models.CharField(max_length=500, blank=True)
    static_data = models.JSONField(default=dict, blank=True)
    
    # Display
    width = models.PositiveIntegerField(default=4, help_text="Grid width (1-12)")
    height = models.PositiveIntegerField(default=300, help_text="Height in pixels")
    position_x = models.PositiveIntegerField(default=0)
    position_y = models.PositiveIntegerField(default=0)
    
    # Refresh
    refresh_interval = models.PositiveIntegerField(
        default=0,
        help_text="Refresh interval in seconds (0 = manual)"
    )
    last_refreshed_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Dashboard Widget"
        verbose_name_plural = "Dashboard Widgets"
        ordering = ['position_y', 'position_x']
        indexes = [
            models.Index(fields=['dashboard', 'is_active']),
            models.Index(fields=['widget_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.dashboard.name}"


class ReportSchedule(BaseAppModel):
    """Scheduled report generation"""
    
    # Schedule Status
    ACTIVE = 'ACTIVE'
    PAUSED = 'PAUSED'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'
    
    STATUS_CHOICES = [
        (ACTIVE, 'Active'),
        (PAUSED, 'Paused'),
        (COMPLETED, 'Completed'),
        (CANCELLED, 'Cancelled'),
    ]
    
    # Delivery Methods
    EMAIL = 'EMAIL'
    DASHBOARD = 'DASHBOARD'
    DOWNLOAD = 'DOWNLOAD'
    ALL = 'ALL'
    
    DELIVERY_CHOICES = [
        (EMAIL, 'Email'),
        (DASHBOARD, 'Dashboard'),
        (DOWNLOAD, 'Download Only'),
        (ALL, 'Email & Dashboard'),
    ]
    
    # Core fields
    schedule_number = models.CharField(max_length=50, unique=True)
    template = models.ForeignKey(
        ReportTemplate, on_delete=models.CASCADE,
        related_name='schedules'
    )
    
    # Schedule configuration
    frequency = models.CharField(max_length=20, choices=ReportTemplate.FREQUENCY_CHOICES)
    schedule_time = models.TimeField(null=True, blank=True)
    schedule_day = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    
    # Date range
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_recurring = models.BooleanField(default=True)
    
    # Parameters
    parameters = models.JSONField(default=dict, blank=True)
    
    # Delivery
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default=EMAIL)
    email_recipients = models.JSONField(
        default=list, blank=True,
        help_text="List of email addresses"
    )
    email_subject = models.CharField(max_length=200, blank=True)
    email_body = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    
    # Execution tracking
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_run_status = models.CharField(max_length=20, blank=True)
    total_runs = models.PositiveIntegerField(default=0)
    successful_runs = models.PositiveIntegerField(default=0)
    failed_runs = models.PositiveIntegerField(default=0)
    
    # Created by
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='scheduled_reports'
    )
    
    class Meta:
        verbose_name = "Report Schedule"
        verbose_name_plural = "Report Schedules"
        ordering = ['next_run_at']
        indexes = [
            models.Index(fields=['schedule_number']),
            models.Index(fields=['template', 'status']),
            models.Index(fields=['status', 'next_run_at']),
            models.Index(fields=['frequency', 'next_run_at']),
        ]
    
    def __str__(self):
        return f"Schedule {self.schedule_number} - {self.template.name}"
    
    def save(self, *args, **kwargs):
        if not self.schedule_number:
            self.schedule_number = self.generate_schedule_number()
        
        # Calculate next run time if active
        if self.status == self.ACTIVE and not self.next_run_at:
            self.calculate_next_run()
        
        super().save(*args, **kwargs)
    
    def generate_schedule_number(self):
        """Generate unique schedule number: SCH-YYYYMMDD-XXXXX"""
        date_str = timezone.now().strftime('%Y%m%d')
        
        last_schedule = ReportSchedule.objects.filter(
            schedule_number__startswith=f'SCH-{date_str}-'
        ).order_by('schedule_number').last()
        
        if last_schedule:
            last_num = int(last_schedule.schedule_number[-5:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"SCH-{date_str}-{new_num:05d}"
    
    def calculate_next_run(self):
        """Calculate next run date/time"""
        from datetime import datetime, timedelta
        
        now = timezone.now()
        
        if self.frequency == ReportTemplate.DAILY:
            next_run = now + timedelta(days=1)
            if self.schedule_time:
                next_run = next_run.replace(
                    hour=self.schedule_time.hour,
                    minute=self.schedule_time.minute,
                    second=0,
                    microsecond=0
                )
        
        elif self.frequency == ReportTemplate.WEEKLY:
            next_run = now + timedelta(days=7)
        
        elif self.frequency == ReportTemplate.MONTHLY and self.schedule_day:
            # Calculate next month with same day
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=self.schedule_day)
            else:
                next_month = now.replace(month=now.month + 1, day=self.schedule_day)
            next_run = next_month
        
        else:
            # Default to tomorrow
            next_run = now + timedelta(days=1)
        
        self.next_run_at = next_run
    
    def execute(self):
        """Execute the scheduled report"""
        # This would be called by a scheduled task
        from .services import ReportService
        try:
            report = ReportService.generate_report_from_template(
                template=self.template,
                parameters=self.parameters,
                start_date=self.start_date,
                end_date=timezone.now().date(),
                generated_by=self.created_by
            )
            
            self.last_run_status = GeneratedReport.COMPLETED
            self.successful_runs += 1
            
            # Send email if configured
            if self.delivery_method in [self.EMAIL, self.ALL]:
                ReportService.send_report_email(report, self.email_recipients)
                
        except Exception as e:
            self.last_run_status = GeneratedReport.FAILED
            self.failed_runs += 1
        
        self.last_run_at = timezone.now()
        self.total_runs += 1
        self.calculate_next_run()
        self.save()


class ReportExport(BaseModel, BranchScopedModel):
    """Report export records"""
    
    # Export Formats
    PDF = 'PDF'
    EXCEL = 'EXCEL'
    CSV = 'CSV'
    JSON = 'JSON'
    
    FORMAT_CHOICES = [
        (PDF, 'PDF'),
        (EXCEL, 'Excel'),
        (CSV, 'CSV'),
        (JSON, 'JSON'),
    ]
    
    # Core fields
    export_number = models.CharField(max_length=50, unique=True)
    generated_report = models.ForeignKey(
        GeneratedReport, on_delete=models.CASCADE,
        related_name='exports'
    )
    
    # Export details
    export_format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    file_path = models.CharField(max_length=500)
    file_size = models.PositiveBigIntegerField()
    
    # Export options
    include_charts = models.BooleanField(default=True)
    include_summary = models.BooleanField(default=True)
    include_details = models.BooleanField(default=True)
    
    # Export info
    exported_by = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='report_exports'
    )
    exported_at = models.DateTimeField(default=timezone.now)
    
    # Performance
    export_duration = models.DurationField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Report Export"
        verbose_name_plural = "Report Exports"
        ordering = ['-exported_at']
        indexes = [
            models.Index(fields=['export_number']),
            models.Index(fields=['generated_report', 'export_format']),
            models.Index(fields=['exported_by', 'exported_at']),
        ]
    
    def __str__(self):
        return f"Export {self.export_number} - {self.export_format}"
    
    def save(self, *args, **kwargs):
        if not self.export_number:
            self.export_number = self.generate_export_number()
        super().save(*args, **kwargs)
    
    def generate_export_number(self):
        """Generate unique export number: EXP-YYYYMMDD-XXXXX"""
        date_str = timezone.now().strftime('%Y%m%d')
        
        last_export = ReportExport.objects.filter(
            export_number__startswith=f'EXP-{date_str}-'
        ).order_by('export_number').last()
        
        if last_export:
            last_num = int(last_export.export_number[-5:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"EXP-{date_str}-{new_num:05d}"


class ReportFavorite(BaseModel):
    """User's favorite reports for quick access"""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='favorite_reports'
    )
    report_template = models.ForeignKey(
        ReportTemplate, on_delete=models.CASCADE,
        related_name='favorited_by'
    )
    added_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Report Favorite"
        verbose_name_plural = "Report Favorites"
        unique_together = ['user', 'report_template']
        ordering = ['-added_at']
        indexes = [
            models.Index(fields=['user', 'report_template']),
        ]
    
    def __str__(self):
        return f"{self.user} favorites {self.report_template.name}"