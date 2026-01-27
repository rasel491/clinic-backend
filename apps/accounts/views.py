# # clinic/Backend/apps/accounts/views.py old
# from rest_framework import status, viewsets, permissions
# from rest_framework.decorators import action
# from rest_framework.response import Response
# from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
# from django.contrib.auth import logout
# from django.utils import timezone

# from .models import User, UserDevice
# from .serializers import (
#     UserSerializer, UserCreateSerializer, CustomTokenObtainPairSerializer,
#     ChangePasswordSerializer, PasswordResetRequestSerializer, 
#     PasswordResetConfirmSerializer
# )
# from core.permissions import IsAdmin, IsManager

# class UserViewSet(viewsets.ModelViewSet):
#     queryset = User.objects.filter(is_active=True)
#     serializer_class = UserSerializer
#     permission_classes = [IsAdmin]
#     filterset_fields = ['role', 'branch', 'is_active']
#     search_fields = ['email', 'phone', 'first_name', 'last_name']
    
#     def get_serializer_class(self):
#         if self.action == 'create':
#             return UserCreateSerializer
#         return super().get_serializer_class()
    
#     def get_permissions(self):
#         if self.action in ['me', 'change_password']:
#             return [permissions.IsAuthenticated()]
#         elif self.action in ['create']:
#             return [IsManager]  # Only managers can create staff users
#         return super().get_permissions()
    
#     @action(detail=False, methods=['get', 'put', 'patch'])
#     def me(self, request):
#         """Get or update current user profile"""
#         if request.method == 'GET':
#             serializer = self.get_serializer(request.user)
#             return Response(serializer.data)
        
#         serializer = self.get_serializer(request.user, data=request.data, partial=True)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(serializer.data)
    
#     @action(detail=False, methods=['post'])
#     def change_password(self, request):
#         """Change password for current user"""
#         serializer = ChangePasswordSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
        
#         user = request.user
#         if not user.check_password(serializer.validated_data['old_password']):
#             return Response(
#                 {'old_password': ['Wrong password.']},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         user.set_password(serializer.validated_data['new_password'])
#         user.save()
        
#         # Logout from all devices
#         UserDevice.objects.filter(user=user).update(is_active=False)
        
#         return Response({'detail': 'Password changed successfully.'})
    
#     @action(detail=False, methods=['post'])
#     def logout(self, request):
#         """Logout user and invalidate device"""
#         device_id = request.META.get('HTTP_X_DEVICE_ID')
        
#         if device_id:
#             UserDevice.objects.filter(
#                 user=request.user,
#                 device_id=device_id
#             ).update(is_active=False)
        
#         logout(request)
#         return Response({'detail': 'Successfully logged out.'})
    
#     @action(detail=False, methods=['post'])
#     def logout_all(self, request):
#         """Logout from all devices"""
#         UserDevice.objects.filter(user=request.user).update(is_active=False)
#         logout(request)
#         return Response({'detail': 'Successfully logged out from all devices.'})

# class CustomTokenObtainPairView(TokenObtainPairView):
#     serializer_class = CustomTokenObtainPairSerializer

# class PasswordResetViewSet(viewsets.GenericViewSet):
#     @action(detail=False, methods=['post'])
#     def request(self, request):
#         """Request password reset (send email)"""
#         serializer = PasswordResetRequestSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
        
#         # TODO: Implement email sending
#         return Response({
#             'detail': 'If the email exists, a reset link has been sent.'
#         })
    
#     @action(detail=False, methods=['post'])
#     def confirm(self, request):
#         """Confirm password reset"""
#         serializer = PasswordResetConfirmSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
        
#         # TODO: Implement token validation and password reset
#         return Response({
#             'detail': 'Password has been reset successfully.'
#         })


# apps/accounts/views.py

from rest_framework import status, viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import logout
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import User, UserDevice, UserBranchRole, Role, UserBranch
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    BranchRoleSerializer
)
from core.permissions import IsAdmin, IsManager, IsAuthenticatedAndActive
from django_filters.rest_framework import DjangoFilterBackend

# -----------------------------
# User CRUD and Profile
# -----------------------------
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['email', 'phone', 'full_name']
    ordering_fields = ['email', 'full_name', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return super().get_serializer_class()

    def get_permissions(self):
        if self.action in ['me', 'change_password', 'logout', 'logout_all']:
            return [IsAuthenticatedAndActive()]
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsManager()]  # Only managers/admins
        return super().get_permissions()

    # -----------------------------
    # Current User Profile
    # -----------------------------
    @action(detail=False, methods=['get', 'put', 'patch'])
    def me(self, request):
        user = request.user
        if request.method == 'GET':
            serializer = self.get_serializer(user)
            return Response(serializer.data)

        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    # -----------------------------
    # Change Password
    # -----------------------------
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({'old_password': ['Wrong password.']},
                            status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])

        # Logout from all devices
        UserDevice.objects.filter(user=user).update(is_active=False)

        return Response({'detail': 'Password changed successfully.'})

    # -----------------------------
    # Logout current device
    # -----------------------------
    @action(detail=False, methods=['post'])
    def logout(self, request):
        device_id = request.META.get('HTTP_X_DEVICE_ID')
        if device_id:
            UserDevice.objects.filter(user=request.user, device_id=device_id).update(is_active=False)

        logout(request)
        return Response({'detail': 'Successfully logged out.'})

    # -----------------------------
    # Logout all devices
    # -----------------------------
    @action(detail=False, methods=['post'])
    def logout_all(self, request):
        UserDevice.objects.filter(user=request.user).update(is_active=False)
        logout(request)
        return Response({'detail': 'Successfully logged out from all devices.'})

    # -----------------------------
    # Assign Branch Role to User
    # -----------------------------
    @action(detail=True, methods=['post'])
    def assign_branch_role(self, request, pk=None):
        user = self.get_object()
        branch_id = request.data.get('branch_id')
        role_code = request.data.get('role_code')

        if not branch_id or not role_code:
            return Response({'detail': 'branch_id and role_code are required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        branch = get_object_or_404(UserBranch.objects.model._meta.get_field('branch').related_model, id=branch_id)
        role = get_object_or_404(Role, code=role_code)

        # Create or update
        obj, created = UserBranchRole.objects.update_or_create(
            user=user,
            branch=branch,
            role=role,
            defaults={'is_active': True, 'assigned_by': request.user, 'assigned_at': timezone.now()}
        )

        serializer = BranchRoleSerializer(obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


# -----------------------------
# JWT Token Views
# -----------------------------
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class CustomTokenRefreshView(TokenRefreshView):
    """Standard JWT refresh endpoint"""
    pass


# -----------------------------
# Password Reset Views
# -----------------------------
class PasswordResetViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['post'])
    def request(self, request):
        """Request password reset (send email)"""
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # TODO: Implement email sending with token
        return Response({'detail': 'If the email exists, a reset link has been sent.'})

    @action(detail=False, methods=['post'])
    def confirm(self, request):
        """Confirm password reset"""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # TODO: Implement token validation and reset password
        return Response({'detail': 'Password has been reset successfully.'})
