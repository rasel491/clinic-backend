# apps/accounts/serializers.py

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from .models import User, UserDevice, UserBranchRole, Role, UserRole, UserBranch


# -----------------------------
# Branch Role Serializer
# -----------------------------
class BranchRoleSerializer(serializers.ModelSerializer):
    branch_id = serializers.IntegerField(source='branch.id', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    role_code = serializers.CharField(source='role.code', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)

    class Meta:
        model = UserBranchRole
    
        fields = ['branch_id', 'branch_name', 'role_code', 'role_name', 'is_active']



# -----------------------------
# UserRole Serializer
# -----------------------------      
class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ['id', 'user', 'role', 'is_active', 'assigned_at', 'assigned_by']
        read_only_fields = ['assigned_at', 'assigned_by']


# -----------------------------
# User Serializer
# -----------------------------
class UserSerializer(serializers.ModelSerializer):
    global_roles = UserRoleSerializer(source='user_roles', many=True, read_only=True)
    branch_roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone', 'full_name',
            'is_active', 'is_email_verified', 'is_phone_verified',
            'created_at', 'updated_at', 'branch_roles'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_active', 'branch_roles']

    def get_branch_roles(self, obj):
        roles = UserBranchRole.objects.filter(user=obj, is_active=True).select_related('branch', 'role')
        return BranchRoleSerializer(roles, many=True).data


# -----------------------------
# User Creation Serializer
# -----------------------------
class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    branch_id = serializers.IntegerField(required=False)
    role_code = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = ['email', 'phone', 'full_name', 'password', 'confirm_password', 'branch_id', 'role_code']

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords don't match."})
        return data

    def create(self, validated_data):
        branch_id = validated_data.pop('branch_id', None)
        role_code = validated_data.pop('role_code', None)
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')

        user = User.objects.create_user(password=password, **validated_data)

        # Assign branch and role if provided
        if branch_id and role_code:
            try:
                branch = UserBranch.objects.model._meta.get_field('branch').related_model.objects.get(id=branch_id)
                role = Role.objects.get(code=role_code)
                UserBranchRole.objects.create(user=user, branch=branch, role=role, is_active=True)
            except Exception as e:
                raise serializers.ValidationError({"branch_role": str(e)})

        return user


# -----------------------------
# JWT Token Serializer
# -----------------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT token: includes user info, branch roles, device tracking
    """

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        refresh = self.get_token(user)

        # Token strings
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)

        # Add serialized user data
        data['user'] = UserSerializer(user).data

        # Device binding
        request = self.context['request']
        device_id = request.META.get('HTTP_X_DEVICE_ID')
        if device_id:
            refresh['device_id'] = device_id
            refresh.access_token['device_id'] = device_id

            UserDevice.objects.update_or_create(
                user=user,
                device_id=device_id,
                defaults={
                    'device_name': request.META.get('HTTP_X_DEVICE_NAME', ''),
                    'device_type': request.META.get('HTTP_X_DEVICE_TYPE', 'web'),
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'last_seen_at': timezone.now(),
                    'is_active': True
                }
            )

        return data


# -----------------------------
# Change Password
# -----------------------------
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "New passwords don't match."})
        return data


# -----------------------------
# Password Reset
# -----------------------------
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords don't match."})
        return data
