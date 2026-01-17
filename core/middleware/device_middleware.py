# clinic/Backend/core/middleware/device_middleware.py
class DeviceMiddleware:
    """Middleware to extract and validate device ID from headers"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Extract device info from headers
        device_id = request.META.get('HTTP_X_DEVICE_ID', '')
        device_name = request.META.get('HTTP_X_DEVICE_NAME', 'Unknown')
        device_type = request.META.get('HTTP_X_DEVICE_TYPE', 'web')
        
        # Add to request for use in views and authentication
        request.device_id = device_id
        request.device_name = device_name
        request.device_type = device_type
        
        response = self.get_response(request)
        
        return response