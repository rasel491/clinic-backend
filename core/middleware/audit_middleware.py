# clinic/Backend/core/middleware/audit_middleware.py

import json
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser

class AuditMiddleware:
    """Middleware to automatically log all requests to audit log"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip audit for certain paths
        if self._should_skip_audit(request):
            return self.get_response(request)
        
        start_time = timezone.now()
        
        # Process the request
        response = self.get_response(request)
        
        # Calculate duration
        duration = timezone.now() - start_time
        
        # Log to audit (async - don't block response)
        if self._should_log_request(request, response):
            self._log_to_audit(request, response, duration)
        
        return response
    
    def _should_skip_audit(self, request):
        """Determine if request should be skipped"""
        skip_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/favicon.ico',
            '/health/',
        ]
        
        return any(request.path.startswith(path) for path in skip_paths)
    
    def _should_log_request(self, request, response):
        """Determine if request should be logged"""
        # Don't log OPTIONS requests (CORS preflight)
        if request.method == 'OPTIONS':
            return False
        
        # Don't log if user is anonymous and it's not auth endpoint
        if isinstance(request.user, AnonymousUser) and not request.path.startswith('/api/accounts/'):
            return False
        
        # Only log successful requests (2xx, 3xx) and important errors (4xx, 5xx)
        return response.status_code < 400 or response.status_code >= 500
    
    def _log_to_audit(self, request, response, duration):
        """Async log to audit database"""
        try:
            from apps.audit.models import AuditLog
            
            # Get user info
            user = request.user if not isinstance(request.user, AnonymousUser) else None
            
            # Determine action type
            action = self._get_action_type(request.method, response.status_code)
            
            # Create audit log (in background)
            AuditLog.objects.create(
                branch=getattr(user, 'current_branch', None) if user else None,
                user=user,
                device_id=request.META.get('HTTP_X_DEVICE_ID', ''),
                ip_address=self._get_client_ip(request),
                action=action,
                model_name=self._get_model_name(request.path),
                object_id=self._get_object_id(request, response),
                before=None,  # Would need to capture before state (requires signals)
                after=self._get_after_data(request, response),
                duration=duration
            )
        except Exception as e:
            # Don't crash the app if audit fails
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Audit logging failed: {e}")
    
    def _get_action_type(self, method, status_code):
        """Map HTTP method to audit action"""
        action_map = {
            'GET': 'VIEW',
            'POST': 'CREATE',
            'PUT': 'UPDATE',
            'PATCH': 'UPDATE',
            'DELETE': 'DELETE',
        }
        return action_map.get(method, 'OTHER')
    
    def _get_model_name(self, path):
        """Extract model name from URL path"""
        # Example: /api/patients/123/ -> 'Patient'
        parts = path.strip('/').split('/')
        if len(parts) >= 2 and parts[0] == 'api':
            return parts[1].title().replace('-', '')
        return 'Unknown'
    
    def _get_object_id(self, request, response):
        """Extract object ID from request/response"""
        # Try to get from URL first (e.g., /api/patients/123/)
        parts = request.path.strip('/').split('/')
        if len(parts) >= 3 and parts[-1].isdigit():
            return parts[-1]
        
        # Try to get from response data
        try:
            if hasattr(response, 'data') and isinstance(response.data, dict):
                return response.data.get('id', '')
        except:
            pass
        
        return ''
    
    def _get_after_data(self, request, response):
        """Get after state data"""
        try:
            if request.method in ['POST', 'PUT', 'PATCH']:
                if hasattr(response, 'data'):
                    return response.data
                elif hasattr(response, 'content'):
                    return json.loads(response.content)
        except:
            pass
        return {}
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip