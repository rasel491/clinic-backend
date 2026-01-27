# apps/accounts/authentication.py

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.utils.translation import gettext_lazy as _


class CustomJWTAuthentication(JWTAuthentication):
    """
    JWT Authentication with device binding and active user check.
    """

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
            raise AuthenticationFailed(_('Token is invalid or expired.'))

        user = self.get_user(validated_token)

        if not user or not user.is_active:
            raise AuthenticationFailed(_('User account is disabled.'))

        # Device binding check
        device_id = request.META.get("HTTP_X_DEVICE_ID")
        token_device_id = validated_token.get("device_id")
        if token_device_id and device_id != token_device_id:
            raise AuthenticationFailed(_('Device mismatch. Please login from registered device.'))

        # Update last login IP
        user.last_login_ip = request.META.get('REMOTE_ADDR')
        user.save(update_fields=['last_login_ip'])

        return (user, validated_token)
