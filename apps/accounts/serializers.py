# clinic/Backend/apps/accounts/serializers.py

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import User, UserDevice

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone', 'first_name', 'last_name',
            'role', 'branch', 'is_active', 'is_email_verified',
            'is_phone_verified', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_active']

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'phone', 'first_name', 'last_name',
            'password', 'confirm_password', 'role'
        ]
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords don't match."})
        return data
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add custom claims
        user = self.user
        refresh = self.get_token(user)
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        
        # Add user info
        data['user'] = UserSerializer(user).data
        
        # Add device info to token
        device_id = self.context['request'].META.get('HTTP_X_DEVICE_ID')
        if device_id:
            refresh['device_id'] = device_id
            refresh.access_token['device_id'] = device_id
            
            # Update or create device record
            UserDevice.objects.update_or_create(
                user=user,
                device_id=device_id,
                defaults={
                    'device_name': self.context['request'].META.get('HTTP_X_DEVICE_NAME', ''),
                    'device_type': self.context['request'].META.get('HTTP_X_DEVICE_TYPE', 'web'),
                    'ip_address': self.context['request'].META.get('REMOTE_ADDR'),
                    'user_agent': self.context['request'].META.get('HTTP_USER_AGENT', ''),
                    'last_used': timezone.now(),
                    'is_active': True
                }
            )
        
        return data

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "New passwords don't match."})
        return data

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