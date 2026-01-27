# core/utils/integrations.py
"""
Integration utilities for connecting visits app with notifications app
"""

def log_notification_to_app(**kwargs):
    """Log notification to notifications app if available"""
    try:
        from apps.notifications.models import NotificationLog
        
        return NotificationLog.objects.create(**kwargs)
    except ImportError:
        # Notifications app not installed or not available
        return None
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to log notification: {str(e)}")
        return None


def get_sms_provider(branch=None):
    """Get active SMS provider"""
    try:
        from apps.notifications.models import SMSProvider
        
        filters = {'is_active': True}
        if branch:
            filters['branch'] = branch
        
        provider = SMSProvider.objects.filter(**filters).first()
        return provider
    except ImportError:
        return None


def get_email_provider(branch=None):
    """Get active email provider"""
    try:
        from apps.notifications.models import EmailProvider
        
        filters = {'is_active': True}
        if branch:
            filters['branch'] = branch
        
        provider = EmailProvider.objects.filter(**filters).first()
        return provider
    except ImportError:
        return None