# # apps/accounts/views.py

# from django.contrib.auth import authenticate
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.exceptions import AuthenticationFailed
# from rest_framework_simplejwt.tokens import RefreshToken

# from .models import UserDevice


# class LoginView(APIView):
#     permission_classes = []

#     def post(self, request):
#         data = request.data

#         user = authenticate(
#             email=data["email"],
#             password=data["password"]
#         )

#         if not user or not user.is_active:
#             raise AuthenticationFailed("Invalid credentials")

#         # Branch validation happens here (simple existence check)
#         branch_id = data["branch_id"]

#         # Resolve active role (simplest: first active role)
#         user_role = user.roles.filter(is_active=True).first()
#         if not user_role:
#             raise AuthenticationFailed("No active role assigned")

#         refresh = RefreshToken.for_user(user)

#         refresh["role"] = user_role.role.code
#         refresh["branch_id"] = str(branch_id)

#         access_token = str(refresh.access_token)
#         refresh_token = str(refresh)

#         # Store device + refresh token hash
#         UserDevice.objects.update_or_create(
#             user=user,
#             device_id=data["device_id"],
#             defaults={
#                 "device_type": data["device_type"],
#                 "refresh_token_hash": hash(refresh_token),
#                 "is_active": True,
#             },
#         )

#         return Response({
#             "access": access_token,
#             "refresh": refresh_token
#         })


# class LogoutView(APIView):
#     def post(self, request):
#         device_id = request.headers.get("X-Device-ID")

#         UserDevice.objects.filter(
#             user=request.user,
#             device_id=device_id
#         ).update(is_active=False)

#         return Response(status=204)


# # class VisitViewSet(BranchQuerySetMixin, ModelViewSet):
# #     queryset = Visit.objects.all()
# #     serializer_class = VisitSerializer



# clinic/Backend/apps/accounts/views.py
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import logout
from django.utils import timezone

from .models import User, UserDevice
from .serializers import (
    UserSerializer, UserCreateSerializer, CustomTokenObtainPairSerializer,
    ChangePasswordSerializer, PasswordResetRequestSerializer, 
    PasswordResetConfirmSerializer
)
from core.permissions import IsAdmin, IsManager

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ['role', 'branch', 'is_active']
    search_fields = ['email', 'phone', 'first_name', 'last_name']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return super().get_serializer_class()
    
    def get_permissions(self):
        if self.action in ['me', 'change_password']:
            return [permissions.IsAuthenticated()]
        elif self.action in ['create']:
            return [IsManager]  # Only managers can create staff users
        return super().get_permissions()
    
    @action(detail=False, methods=['get', 'put', 'patch'])
    def me(self, request):
        """Get or update current user profile"""
        if request.method == 'GET':
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
        
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change password for current user"""
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': ['Wrong password.']},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        # Logout from all devices
        UserDevice.objects.filter(user=user).update(is_active=False)
        
        return Response({'detail': 'Password changed successfully.'})
    
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """Logout user and invalidate device"""
        device_id = request.META.get('HTTP_X_DEVICE_ID')
        
        if device_id:
            UserDevice.objects.filter(
                user=request.user,
                device_id=device_id
            ).update(is_active=False)
        
        logout(request)
        return Response({'detail': 'Successfully logged out.'})
    
    @action(detail=False, methods=['post'])
    def logout_all(self, request):
        """Logout from all devices"""
        UserDevice.objects.filter(user=request.user).update(is_active=False)
        logout(request)
        return Response({'detail': 'Successfully logged out from all devices.'})

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class PasswordResetViewSet(viewsets.GenericViewSet):
    @action(detail=False, methods=['post'])
    def request(self, request):
        """Request password reset (send email)"""
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # TODO: Implement email sending
        return Response({
            'detail': 'If the email exists, a reset link has been sent.'
        })
    
    @action(detail=False, methods=['post'])
    def confirm(self, request):
        """Confirm password reset"""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # TODO: Implement token validation and password reset
        return Response({
            'detail': 'Password has been reset successfully.'
        })