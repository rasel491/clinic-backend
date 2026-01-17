import json
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from apps.core.constants import AuditActions

class AuditLogMiddleware(MiddlewareMixin):
    """Middleware to log all requests"""
    
    def process_request(self, request):
        if request.user.is_authenticated:
            # Initialize audit log data
            request.audit_data = {
                'timestamp': timezone.now(),
                'user': request.user,
                'action': None,
                'resource': request.path,
                'method': request.method,
                'ip_address': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'device_id': request.headers.get('X-Device-ID', ''),
                'response_status': None,
                'response_time': None,
            }
    
    def process_response(self, request, response):
        if hasattr(request, 'audit_data'):
            from apps.accounts.models import AuditLog
            
            request.audit_data['response_status'] = response.status_code
            request.audit_data['response_time'] = timezone.now()
            
            # Determine action type
            if request.method == 'POST':
                action = AuditActions.CREATE
            elif request.method == 'PUT' or request.method == 'PATCH':
                action = AuditActions.UPDATE
            elif request.method == 'DELETE':
                action = AuditActions.DELETE
            elif request.method == 'GET':
                action = AuditActions.VIEW
            else:
                action = request.method.lower()
            
            request.audit_data['action'] = action
            
            # Log to database
            AuditLog.objects.create(
                user=request.audit_data['user'],
                action=action,
                resource=request.audit_data['resource'],
                method=request.method,
                ip_address=request.audit_data['ip_address'],
                user_agent=request.audit_data['user_agent'][:255],
                device_id=request.audit_data['device_id'][:255],
                status_code=response.status_code,
                request_body=self.get_request_body(request),
                response_body=self.get_response_body(response) if response.status_code >= 400 else '',
                timestamp=request.audit_data['timestamp'],
            )
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_request_body(self, request):
        """Safely get request body"""
        try:
            if request.body:
                return request.body.decode('utf-8')[:1000]  # Limit length
        except:
            pass
        return ''
    
    def get_response_body(self, response):
        """Safely get response body for error responses"""
        try:
            if hasattr(response, 'content'):
                return response.content.decode('utf-8')[:1000]  # Limit length
        except:
            pass
        return ''