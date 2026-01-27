# apps/reports/signals.py

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ValidationError
import logging

from .models import (
    ReportTemplate, GeneratedReport, Dashboard,
    DashboardWidget, ReportSchedule, ReportFavorite
)
from apps.audit.services import log_action

logger = logging.getLogger(__name__)


# ===========================================
# REPORT TEMPLATE SIGNALS
# ===========================================

@receiver(pre_save, sender=ReportTemplate)
def report_template_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for ReportTemplate
    """
    # Validate code uniqueness
    if ReportTemplate.objects.filter(
        code=instance.code
    ).exclude(id=instance.id).exists():
        raise ValidationError(f"A report template with code '{instance.code}' already exists")
    
    # Ensure HTML template has basic structure
    if instance.html_template and '<html>' not in instance.html_template.lower():
        # Add basic HTML structure if missing
        instance.html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{instance.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                .report-header {{ border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-bottom: 20px; }}
                .report-footer {{ margin-top: 30px; padding-top: 10px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            {instance.html_template}
            <div class="report-footer">
                Generated on {{generated_date}} at {{generated_time}}
            </div>
        </body>
        </html>
        """


@receiver(post_save, sender=ReportTemplate)
def report_template_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for ReportTemplate
    """
    action = 'REPORT_TEMPLATE_CREATED' if created else 'REPORT_TEMPLATE_UPDATED'
    
    try:
        user = getattr(instance, '_updated_by', instance.created_by)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=instance,
            action=action,
            metadata={
                'template_id': str(instance.id),
                'template_name': instance.name,
                'template_code': instance.code,
                'report_type': instance.report_type,
                'is_active': instance.is_active
            }
        )
    except Exception as e:
        logger.error(f"Failed to log report template action: {str(e)}")


# ===========================================
# GENERATED REPORT SIGNALS
# ===========================================

@receiver(pre_save, sender=GeneratedReport)
def generated_report_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for GeneratedReport
    """
    # Auto-set branch from template if not set
    if not instance.branch and instance.template:
        instance.branch = instance.template.branch
    
    # Auto-set generated_by from created_by if not set
    if not instance.generated_by and instance.created_by:
        instance.generated_by = instance.created_by


@receiver(post_save, sender=GeneratedReport)
def generated_report_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for GeneratedReport
    """
    action = 'REPORT_GENERATED' if created else 'REPORT_UPDATED'
    
    # Track status changes
    if not created and instance.tracker.has_changed('status'):
        old_status = instance.tracker.previous('status')
        new_status = instance.status
        action = f'REPORT_STATUS_CHANGED_{old_status}_TO_{new_status}'
    
    try:
        user = getattr(instance, '_updated_by', instance.generated_by)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=instance,
            action=action,
            metadata={
                'report_id': str(instance.id),
                'report_number': instance.report_number,
                'template_id': str(instance.template_id),
                'template_name': instance.template.name,
                'status': instance.status,
                'file_size': instance.file_size,
                'generation_duration': str(instance.generation_duration) if instance.generation_duration else None
            }
        )
    except Exception as e:
        logger.error(f"Failed to log generated report action: {str(e)}")
    
    # Update template's last run info
    if instance.status == GeneratedReport.COMPLETED:
        try:
            instance.template.last_run_at = instance.completed_at
            instance.template.last_run_by = instance.generated_by
            instance.template.save()
        except Exception as e:
            logger.error(f"Failed to update template last run info: {str(e)}")


# ===========================================
# DASHBOARD SIGNALS
# ===========================================

@receiver(pre_save, sender=Dashboard)
def dashboard_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for Dashboard
    """
    # Ensure only one default dashboard per type per branch
    if instance.is_default:
        # Clear other defaults
        Dashboard.objects.filter(
            branch=instance.branch,
            dashboard_type=instance.dashboard_type,
            is_default=True
        ).exclude(id=instance.id).update(is_default=False)


@receiver(post_save, sender=Dashboard)
def dashboard_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for Dashboard
    """
    action = 'DASHBOARD_CREATED' if created else 'DASHBOARD_UPDATED'
    
    try:
        user = getattr(instance, '_updated_by', instance.created_by)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=instance,
            action=action,
            metadata={
                'dashboard_id': str(instance.id),
                'dashboard_name': instance.name,
                'dashboard_type': instance.dashboard_type,
                'is_public': instance.is_public,
                'is_default': instance.is_default
            }
        )
    except Exception as e:
        logger.error(f"Failed to log dashboard action: {str(e)}")


# ===========================================
# DASHBOARD WIDGET SIGNALS
# ===========================================

@receiver(pre_save, sender=DashboardWidget)
def dashboard_widget_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for DashboardWidget
    """
    # Auto-set branch from dashboard if not set
    if not instance.branch and instance.dashboard:
        instance.branch = instance.dashboard.branch
    
    # Validate position
    if instance.position_x < 0:
        instance.position_x = 0
    if instance.position_y < 0:
        instance.position_y = 0
    
    # Validate width (1-12 grid)
    if instance.width < 1:
        instance.width = 1
    elif instance.width > 12:
        instance.width = 12


@receiver(post_save, sender=DashboardWidget)
def dashboard_widget_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for DashboardWidget
    """
    action = 'WIDGET_CREATED' if created else 'WIDGET_UPDATED'
    
    try:
        log_action(
            user=instance.dashboard.created_by if instance.dashboard else None,
            branch=instance.branch,
            instance=instance,
            action=action,
            metadata={
                'widget_id': str(instance.id),
                'widget_name': instance.name,
                'widget_type': instance.widget_type,
                'dashboard_id': str(instance.dashboard_id) if instance.dashboard else None,
                'dashboard_name': instance.dashboard.name if instance.dashboard else None
            }
        )
    except Exception as e:
        logger.error(f"Failed to log widget action: {str(e)}")


# ===========================================
# REPORT SCHEDULE SIGNALS
# ===========================================

@receiver(pre_save, sender=ReportSchedule)
def report_schedule_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for ReportSchedule
    """
    # Auto-set branch from template if not set
    if not instance.branch and instance.template:
        instance.branch = instance.template.branch
    
    # Auto-set created_by if not set
    if not instance.created_by and hasattr(instance, '_created_by_user'):
        instance.created_by = instance._created_by_user
    
    # Validate date range
    if instance.start_date and instance.end_date and instance.start_date > instance.end_date:
        raise ValidationError("Start date cannot be after end date")
    
    # Validate schedule parameters
    if instance.frequency == ReportTemplate.MONTHLY and not instance.schedule_day:
        raise ValidationError("Schedule day is required for monthly frequency")


@receiver(post_save, sender=ReportSchedule)
def report_schedule_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for ReportSchedule
    """
    action = 'SCHEDULE_CREATED' if created else 'SCHEDULE_UPDATED'
    
    # Track status changes
    if not created and instance.tracker.has_changed('status'):
        old_status = instance.tracker.previous('status')
        new_status = instance.status
        action = f'SCHEDULE_STATUS_CHANGED_{old_status}_TO_{new_status}'
    
    try:
        user = getattr(instance, '_updated_by', instance.created_by)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=instance,
            action=action,
            metadata={
                'schedule_id': str(instance.id),
                'schedule_number': instance.schedule_number,
                'template_id': str(instance.template_id),
                'template_name': instance.template.name,
                'frequency': instance.frequency,
                'status': instance.status,
                'next_run_at': str(instance.next_run_at) if instance.next_run_at else None
            }
        )
    except Exception as e:
        logger.error(f"Failed to log schedule action: {str(e)}")


# ===========================================
# REPORT FAVORITE SIGNALS
# ===========================================

@receiver(post_save, sender=ReportFavorite)
def report_favorite_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for ReportFavorite
    """
    if created:
        try:
            log_action(
                user=instance.user,
                branch=instance.report_template.branch,
                instance=instance,
                action='REPORT_FAVORITED',
                metadata={
                    'user_id': str(instance.user_id),
                    'template_id': str(instance.report_template_id),
                    'template_name': instance.report_template.name
                }
            )
        except Exception as e:
            logger.error(f"Failed to log favorite action: {str(e)}")


@receiver(post_delete, sender=ReportFavorite)
def report_favorite_post_delete(sender, instance, **kwargs):
    """
    Post-delete signal for ReportFavorite
    """
    try:
        log_action(
            user=instance.user,
            branch=instance.report_template.branch,
            instance=None,
            action='REPORT_UNFAVORITED',
            metadata={
                'user_id': str(instance.user_id),
                'template_id': str(instance.report_template_id),
                'template_name': instance.report_template.name
            }
        )
    except Exception as e:
        logger.error(f"Failed to log unfavorite action: {str(e)}")


# ===========================================
# MODEL TRACKER SETUP
# ===========================================

def init_model_trackers():
    """
    Initialize model trackers for change detection
    """
    from django.db import models
    
    # Add tracker to models
    for model in [ReportTemplate, GeneratedReport, Dashboard, DashboardWidget, ReportSchedule]:
        if not hasattr(model, 'tracker'):
            model.add_to_class('tracker', models.FieldTracker())
    
    logger.info("Report model trackers initialized")


# ===========================================
# SIGNALS REGISTRATION
# ===========================================

def register_signals():
    """
    Register all signals
    """
    # Initialize trackers
    try:
        init_model_trackers()
    except Exception as e:
        logger.error(f"Failed to initialize model trackers: {str(e)}")
    
    logger.info("Report signals registered")