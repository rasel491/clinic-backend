# apps/reports/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages

from .models import (
    ReportCategory, ReportTemplate, GeneratedReport,
    ReportData, Dashboard, DashboardWidget, ReportSchedule,
    ReportExport, ReportFavorite
)


@admin.register(ReportCategory)
class ReportCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    list_editable = ('sort_order', 'is_active')
    search_fields = ('name', 'code', 'description')
    ordering = ('sort_order', 'name')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description', 'icon')
        }),
        ('Display', {
            'fields': ('sort_order', 'is_active')
        }),
    )


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'report_type', 'category',
                   'output_format', 'is_scheduled', 'is_active',
                   'last_run_at')
    list_filter = ('report_type', 'is_active', 'is_scheduled',
                  'output_format', 'branch')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('last_run_at', 'last_run_by', 'created_at',
                      'updated_at')
    raw_id_fields = ('category', 'last_run_by', 'branch',
                    'created_by', 'updated_by')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description', 'report_type',
                      'category', 'branch')
        }),
        ('Configuration', {
            'fields': ('query_sql', 'query_parameters',
                      'output_format', 'html_template',
                      'excel_template')
        }),
        ('Schedule', {
            'fields': ('is_scheduled', 'frequency', 'schedule_time',
                      'schedule_day')
        }),
        ('Access Control', {
            'fields': ('requires_permission', 'allowed_roles')
        }),
        ('Display', {
            'fields': ('icon', 'sort_order', 'is_active')
        }),
        ('Metadata', {
            'fields': ('last_run_at', 'last_run_by',
                      'created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    actions = ['run_report', 'duplicate_template']
    
    def run_report(self, request, queryset):
        """Action to run selected reports"""
        from .services import ReportService
        
        for template in queryset:
            try:
                report = ReportService.generate_report_from_template(
                    template=template,
                    parameters={},
                    start_date=timezone.now().date() - timezone.timedelta(days=30),
                    end_date=timezone.now().date(),
                    generated_by=request.user
                )
                self.message_user(
                    request,
                    f"Report {template.name} generated: {report.report_number}",
                    messages.SUCCESS
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to generate {template.name}: {str(e)}",
                    messages.ERROR
                )
    run_report.short_description = "Run selected reports"
    
    def duplicate_template(self, request, queryset):
        """Action to duplicate selected templates"""
        for template in queryset:
            new_template = ReportTemplate.objects.create(
                name=f"{template.name} (Copy)",
                code=f"{template.code}_COPY_{timezone.now().strftime('%Y%m%d')}",
                description=template.description,
                report_type=template.report_type,
                category=template.category,
                branch=template.branch,
                query_sql=template.query_sql,
                query_parameters=template.query_parameters,
                output_format=template.output_format,
                is_scheduled=False,  # Don't schedule copies
                created_by=request.user,
                updated_by=request.user
            )
        self.message_user(request, f"{queryset.count()} template(s) duplicated.")
    duplicate_template.short_description = "Duplicate templates"


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ('report_number', 'template_link', 'branch',
                   'status', 'generated_by', 'generated_at',
                   'file_size', 'download_count', 'row_count')
    list_filter = ('status', 'branch', 'generated_at',
                  'template__report_type')
    search_fields = ('report_number', 'template__name',
                    'generated_by__username')
    readonly_fields = ('report_number', 'generated_at', 'completed_at',
                      'file_size', 'download_count', 'generation_duration',
                      'row_count', 'created_at', 'updated_at')
    raw_id_fields = ('template', 'generated_by', 'branch',
                    'created_by', 'updated_by')
    date_hierarchy = 'generated_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('report_number', 'template', 'branch', 'status')
        }),
        ('Parameters', {
            'fields': ('parameters', 'start_date', 'end_date')
        }),
        ('Generation Info', {
            'fields': ('generated_by', 'generated_at', 'completed_at',
                      'generation_duration', 'row_count')
        }),
        ('File Information', {
            'fields': ('file_path', 'file_size', 'download_count',
                      'error_message', 'stack_trace')
        }),
        ('Archival', {
            'fields': ('is_archived', 'archive_reason')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    def template_link(self, obj):
        url = reverse('admin:reports_reporttemplate_change', args=[obj.template.id])
        return format_html('<a href="{}">{}</a>', url, obj.template.name)
    template_link.short_description = 'Template'
    
    actions = ['regenerate_reports', 'archive_reports']
    
    def regenerate_reports(self, request, queryset):
        """Action to regenerate selected reports"""
        from .services import ReportService
        
        for report in queryset.filter(status=GeneratedReport.COMPLETED):
            try:
                new_report = ReportService.generate_report_from_template(
                    template=report.template,
                    parameters=report.parameters,
                    start_date=report.start_date,
                    end_date=report.end_date,
                    generated_by=request.user
                )
                self.message_user(
                    request,
                    f"Regenerated {report.template.name} as {new_report.report_number}",
                    messages.SUCCESS
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to regenerate {report.report_number}: {str(e)}",
                    messages.ERROR
                )
    regenerate_reports.short_description = "Regenerate reports"
    
    def archive_reports(self, request, queryset):
        """Action to archive selected reports"""
        count = queryset.update(is_archived=True)
        self.message_user(request, f"{count} report(s) archived.")
    archive_reports.short_description = "Archive reports"


@admin.register(ReportData)
class ReportDataAdmin(admin.ModelAdmin):
    list_display = ('generated_report_link', 'data_version',
                   'compressed', 'created_at')
    list_filter = ('compressed', 'data_version')
    search_fields = ('generated_report__report_number',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('generated_report', 'data_version', 'compressed')
        }),
        ('Data Storage', {
            'fields': ('data_json', 'summary')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def generated_report_link(self, obj):
        url = reverse('admin:reports_generatedreport_change', args=[obj.generated_report.id])
        return format_html('<a href="{}">{}</a>', url, obj.generated_report.report_number)
    generated_report_link.short_description = 'Generated Report'


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ('name', 'dashboard_type', 'branch',
                   'is_public', 'is_default', 'is_active',
                   'created_by')
    list_filter = ('dashboard_type', 'is_public', 'is_default',
                  'is_active', 'branch')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('branch', 'created_by', 'updated_by',
                    'shared_with')
    filter_horizontal = ('shared_with',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'dashboard_type', 'branch')
        }),
        ('Layout & Display', {
            'fields': ('layout_config', 'icon', 'color', 'sort_order')
        }),
        ('Access Control', {
            'fields': ('is_public', 'shared_with')
        }),
        ('Status', {
            'fields': ('is_default', 'is_active')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    actions = ['set_as_default', 'duplicate_dashboard']
    
    def set_as_default(self, request, queryset):
        """Action to set dashboard as default"""
        for dashboard in queryset:
            dashboard.is_default = True
            dashboard.save()
        self.message_user(request, f"{queryset.count()} dashboard(s) set as default.")
    set_as_default.short_description = "Set as default dashboard"
    
    def duplicate_dashboard(self, request, queryset):
        """Action to duplicate dashboards"""
        for dashboard in queryset:
            new_dashboard = Dashboard.objects.create(
                name=f"{dashboard.name} (Copy)",
                description=dashboard.description,
                dashboard_type=dashboard.dashboard_type,
                branch=dashboard.branch,
                layout_config=dashboard.layout_config,
                icon=dashboard.icon,
                color=dashboard.color,
                sort_order=dashboard.sort_order + 100,  # Put at end
                is_public=dashboard.is_public,
                is_default=False,  # Don't make copies default
                is_active=True,
                created_by=request.user,
                updated_by=request.user
            )
            # Copy shared users
            new_dashboard.shared_with.set(dashboard.shared_with.all())
            
            # Copy widgets
            for widget in dashboard.widgets.all():
                DashboardWidget.objects.create(
                    dashboard=new_dashboard,
                    name=widget.name,
                    widget_type=widget.widget_type,
                    config=widget.config,
                    data_source_type=widget.data_source_type,
                    report_template=widget.report_template,
                    query_sql=widget.query_sql,
                    api_endpoint=widget.api_endpoint,
                    static_data=widget.static_data,
                    width=widget.width,
                    height=widget.height,
                    position_x=widget.position_x,
                    position_y=widget.position_y,
                    refresh_interval=widget.refresh_interval,
                    branch=widget.branch,
                    is_active=widget.is_active
                )
        
        self.message_user(request, f"{queryset.count()} dashboard(s) duplicated.")
    duplicate_dashboard.short_description = "Duplicate dashboards"


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ('name', 'dashboard_link', 'widget_type',
                   'data_source_type', 'width', 'height',
                   'is_active', 'last_refreshed_at')
    list_filter = ('widget_type', 'data_source_type', 'is_active',
                  'branch')
    search_fields = ('name', 'dashboard__name')
    readonly_fields = ('last_refreshed_at', 'created_at', 'updated_at')
    raw_id_fields = ('dashboard', 'report_template', 'branch')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('dashboard', 'name', 'widget_type', 'branch')
        }),
        ('Configuration', {
            'fields': ('config', 'width', 'height',
                      'position_x', 'position_y')
        }),
        ('Data Source', {
            'fields': ('data_source_type', 'report_template',
                      'query_sql', 'api_endpoint', 'static_data')
        }),
        ('Refresh', {
            'fields': ('refresh_interval', 'last_refreshed_at')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def dashboard_link(self, obj):
        url = reverse('admin:reports_dashboard_change', args=[obj.dashboard.id])
        return format_html('<a href="{}">{}</a>', url, obj.dashboard.name)
    dashboard_link.short_description = 'Dashboard'
    
    actions = ['refresh_widgets', 'resize_widgets']
    
    def refresh_widgets(self, request, queryset):
        """Action to refresh selected widgets"""
        for widget in queryset:
            widget.last_refreshed_at = timezone.now()
            widget.save()
        self.message_user(request, f"{queryset.count()} widget(s) refreshed.")
    refresh_widgets.short_description = "Refresh widgets"
    
    def resize_widgets(self, request, queryset):
        """Action to resize widgets"""
        for widget in queryset:
            widget.width = 6  # Default to medium width
            widget.height = 400
            widget.save()
        self.message_user(request, f"{queryset.count()} widget(s) resized.")
    resize_widgets.short_description = "Resize to medium"


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ('schedule_number', 'template_link', 'branch',
                   'frequency', 'status', 'next_run_at',
                   'last_run_at', 'total_runs', 'created_by')
    list_filter = ('frequency', 'status', 'delivery_method',
                  'branch')
    search_fields = ('schedule_number', 'template__name',
                    'created_by__username')
    readonly_fields = ('schedule_number', 'next_run_at', 'last_run_at',
                      'last_run_status', 'total_runs', 'successful_runs',
                      'failed_runs', 'created_at', 'updated_at')
    raw_id_fields = ('template', 'created_by', 'branch')
    date_hierarchy = 'next_run_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('schedule_number', 'template', 'branch', 'status')
        }),
        ('Schedule Configuration', {
            'fields': ('frequency', 'schedule_time', 'schedule_day',
                      'start_date', 'end_date', 'is_recurring')
        }),
        ('Parameters', {
            'fields': ('parameters',)
        }),
        ('Delivery', {
            'fields': ('delivery_method', 'email_recipients',
                      'email_subject', 'email_body')
        }),
        ('Execution Tracking', {
            'fields': ('next_run_at', 'last_run_at', 'last_run_status',
                      'total_runs', 'successful_runs', 'failed_runs')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def template_link(self, obj):
        url = reverse('admin:reports_reporttemplate_change', args=[obj.template.id])
        return format_html('<a href="{}">{}</a>', url, obj.template.name)
    template_link.short_description = 'Template'
    
    actions = ['run_schedule_now', 'pause_schedules', 'activate_schedules']
    
    def run_schedule_now(self, request, queryset):
        """Action to run schedules immediately"""
        for schedule in queryset.filter(status=ReportSchedule.ACTIVE):
            try:
                schedule.execute()
                self.message_user(
                    request,
                    f"Scheduled {schedule.template.name} executed.",
                    messages.SUCCESS
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to execute {schedule.schedule_number}: {str(e)}",
                    messages.ERROR
                )
    run_schedule_now.short_description = "Run schedule now"
    
    def pause_schedules(self, request, queryset):
        """Action to pause schedules"""
        count = queryset.update(status=ReportSchedule.PAUSED)
        self.message_user(request, f"{count} schedule(s) paused.")
    pause_schedules.short_description = "Pause schedules"
    
    def activate_schedules(self, request, queryset):
        """Action to activate schedules"""
        count = queryset.update(status=ReportSchedule.ACTIVE)
        self.message_user(request, f"{count} schedule(s) activated.")
    activate_schedules.short_description = "Activate schedules"


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    list_display = ('export_number', 'generated_report_link',
                   'export_format', 'file_size', 'exported_by',
                   'exported_at', 'export_duration')
    list_filter = ('export_format', 'branch')
    search_fields = ('export_number', 'generated_report__report_number',
                    'exported_by__username')
    readonly_fields = ('export_number', 'exported_at', 'file_size',
                      'export_duration', 'created_at', 'updated_at')
    raw_id_fields = ('generated_report', 'exported_by', 'branch')
    date_hierarchy = 'exported_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('export_number', 'generated_report',
                      'export_format', 'branch')
        }),
        ('File Information', {
            'fields': ('file_path', 'file_size')
        }),
        ('Export Options', {
            'fields': ('include_charts', 'include_summary',
                      'include_details')
        }),
        ('Export Info', {
            'fields': ('exported_by', 'exported_at',
                      'export_duration')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def generated_report_link(self, obj):
        url = reverse('admin:reports_generatedreport_change', args=[obj.generated_report.id])
        return format_html('<a href="{}">{}</a>', url, obj.generated_report.report_number)
    generated_report_link.short_description = 'Generated Report'


@admin.register(ReportFavorite)
class ReportFavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'report_template_link', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('user__username', 'report_template__name')
    readonly_fields = ('added_at',)
    raw_id_fields = ('user', 'report_template')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'report_template')
        }),
        ('Notes', {
            'fields': ('notes', 'added_at')
        }),
    )
    
    def report_template_link(self, obj):
        url = reverse('admin:reports_reporttemplate_change', args=[obj.report_template.id])
        return format_html('<a href="{}">{}</a>', url, obj.report_template.name)
    report_template_link.short_description = 'Report Template'