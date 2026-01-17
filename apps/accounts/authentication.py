# clinic/Backend/apps/accounts/authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.utils.translation import gettext_lazy as _

class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except InvalidToken:
            raise AuthenticationFailed(_('Token is invalid or expired'))
        
        # Device binding check
        device_id = request.META.get('HTTP_X_DEVICE_ID')
        token_device = validated_token.get('device_id', None)
        
        if token_device and device_id != token_device:
            raise AuthenticationFailed(_('Device mismatch. Please login again from your registered device.'))
        
        user = self.get_user(validated_token)
        
        if not user.is_active:
            raise AuthenticationFailed(_('User account is disabled.'))
        
        # Update last login IP
        user.last_login_ip = request.META.get('REMOTE_ADDR')
        user.save(update_fields=['last_login_ip'])
        
        return (user, validated_token)