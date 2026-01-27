# apps/otp/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Q, Count
from django_filters.rest_framework import DjangoFilterBackend
import logging

from core.permissions import (
    IsAdminUser, IsManager, IsDoctor, IsReceptionist, IsCashier
)
from apps.clinics.models import Branch
from .models import (
    OTPConfig, OTPRequest, OTPBlacklist,
    OTPRateLimit, OTPTemplate, OTPType
)
from .serializers import (
    OTPConfigSerializer, OTPRequestSerializer,
    OTPBlacklistSerializer, OTPRateLimitSerializer,
    OTPTemplateSerializer, RequestOTPSerializer,
    VerifyOTPSerializer, ResendOTPSerializer,
    OTPStatsSerializer, CheckRateLimitSerializer
)
from .services import OTPService

logger = logging.getLogger(__name__)


class OTPConfigViewSet(viewsets.ModelViewSet):
    """ViewSet for managing OTP configurations"""
    queryset = OTPConfig.objects.filter(deleted_at__isnull=True)
    serializer_class = OTPConfigSerializer
    permission_classes = [IsAuthenticated, IsManager]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch if user is not admin
        if not self.request.user.is_superuser:
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                queryset = queryset.filter(branch_id=branch_id)
            else:
                if hasattr(self.request.user, 'branch'):
                    queryset = queryset.filter(branch=self.request.user.branch)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def reset_counters(self, request, pk=None):
        """Reset OTP counters"""
        config = self.get_object()
        config.total_otp_sent = 0
        config.total_verified = 0
        config.total_failed = 0
        config.save()
        
        return Response({'message': 'Counters reset successfully'})


class OTPRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for managing OTP requests"""
    queryset = OTPRequest.objects.all()
    serializer_class = OTPRequestSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'otp_type', 'channel', 'branch', 'recipient_type']
    search_fields = ['recipient_contact', 'otp_code', 'reference_id']
    ordering_fields = ['created_at', 'expires_at', 'sent_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch if user is not admin
        if not self.request.user.is_superuser:
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                queryset = queryset.filter(branch_id=branch_id)
            else:
                if hasattr(self.request.user, 'branch'):
                    queryset = queryset.filter(branch=self.request.user.branch)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        # Filter by recipient (for doctors/patients)
        if self.request.user.role == 'doctor':
            queryset = queryset.filter(
                Q(recipient_type='PATIENT') |
                Q(related_object_type='appointment', recipient_type='PATIENT')
            )
        
        return queryset
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def request_otp(self, request):
        """Request OTP (public endpoint)"""
        serializer = RequestOTPSerializer(data=request.data)
        if serializer.is_valid():
            otp_service = OTPService()
            
            try:
                # Add IP and device info
                ip_address = request.META.get('REMOTE_ADDR')
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                device_id = request.data.get('device_id', '')
                
                otp_request = otp_service.request_otp(
                    **serializer.validated_data,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    device_id=device_id
                )
                
                # Don't return OTP code in response for security
                response_data = {
                    'otp_id': str(otp_request.otp_id),
                    'status': otp_request.status,
                    'expires_at': otp_request.expires_at,
                    'message': 'OTP sent successfully'
                }
                
                return Response(response_data, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Error requesting OTP: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def verify_otp(self, request):
        """Verify OTP (public endpoint)"""
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            otp_service = OTPService()
            
            try:
                verified = otp_service.verify_otp(
                    otp_id=serializer.validated_data['otp_id'],
                    otp_code=serializer.validated_data['otp_code'],
                    recipient_contact=serializer.validated_data.get('recipient_contact'),
                    increment_attempt=serializer.validated_data.get('increment_attempt', True)
                )
                
                if verified:
                    return Response({
                        'verified': True,
                        'message': 'OTP verified successfully'
                    })
                else:
                    return Response({
                        'verified': False,
                        'message': 'Invalid OTP or OTP expired'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
            except Exception as e:
                logger.error(f"Error verifying OTP: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def resend_otp(self, request):
        """Resend OTP (public endpoint)"""
        serializer = ResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            otp_service = OTPService()
            
            try:
                otp_request = otp_service.resend_otp(
                    otp_id=serializer.validated_data['otp_id'],
                    channel=serializer.validated_data.get('channel')
                )
                
                if otp_request:
                    response_data = {
                        'otp_id': str(otp_request.otp_id),
                        'status': otp_request.status,
                        'expires_at': otp_request.expires_at,
                        'message': 'OTP resent successfully'
                    }
                    return Response(response_data)
                else:
                    return Response(
                        {'error': 'Cannot resend OTP'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
            except Exception as e:
                logger.error(f"Error resending OTP: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get OTP statistics"""
        queryset = self.get_queryset()
        
        # Calculate stats
        total_requests = queryset.count()
        total_verified = queryset.filter(status='VERIFIED').count()
        total_failed = queryset.filter(status='FAILED').count()
        success_rate = (total_verified / total_requests * 100) if total_requests > 0 else 0
        
        # Stats by type
        by_type = queryset.values('otp_type').annotate(
            count=Count('id'),
            verified=Count('id', filter=Q(status='VERIFIED')),
            failed=Count('id', filter=Q(status='FAILED'))
        )
        
        # Stats by channel
        by_channel = queryset.values('channel').annotate(
            count=Count('id'),
            success_rate=Count('id', filter=Q(status='VERIFIED')) * 100.0 / Count('id')
        )
        
        # Recent requests
        recent_requests = queryset.order_by('-created_at')[:10]
        recent_data = OTPRequestSerializer(recent_requests, many=True).data
        
        stats = {
            'total_requests': total_requests,
            'total_verified': total_verified,
            'total_failed': total_failed,
            'success_rate': round(success_rate, 2),
            'by_type': list(by_type),
            'by_channel': list(by_channel),
            'recent_requests': recent_data
        }
        
        return Response(stats)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel OTP request"""
        otp_request = self.get_object()
        
        if otp_request.status in ['VERIFIED', 'EXPIRED']:
            return Response(
                {'error': f'Cannot cancel OTP in {otp_request.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        otp_request.status = 'EXPIRED'
        otp_request.save()
        
        return Response({'message': 'OTP cancelled successfully'})


class OTPBlacklistViewSet(viewsets.ModelViewSet):
    """ViewSet for managing OTP blacklists"""
    queryset = OTPBlacklist.objects.all()
    serializer_class = OTPBlacklistSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['blacklist_type', 'reason', 'is_permanent', 'branch']
    search_fields = ['identifier', 'description']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch if user is not admin
        if not self.request.user.is_superuser:
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                queryset = queryset.filter(branch_id=branch_id)
            else:
                if hasattr(self.request.user, 'branch'):
                    queryset = queryset.filter(branch=self.request.user.branch)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        """Unblock blacklisted entry"""
        blacklist = self.get_object()
        
        if blacklist.is_permanent:
            return Response(
                {'error': 'Cannot unblock permanent blacklist'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        blacklist.blocked_until = None
        blacklist.save()
        
        return Response({'message': 'Entry unblocked successfully'})
    
    @action(detail=False, methods=['post'])
    def check(self, request):
        """Check if identifier is blacklisted"""
        identifier = request.data.get('identifier')
        blacklist_type = request.data.get('blacklist_type')
        branch_id = request.data.get('branch_id')
        
        if not identifier or not blacklist_type:
            return Response(
                {'error': 'identifier and blacklist_type are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset()
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        blacklist = queryset.filter(
            identifier=identifier,
            blacklist_type=blacklist_type
        ).first()
        
        if blacklist and blacklist.is_blocked():
            return Response({
                'blocked': True,
                'reason': blacklist.reason,
                'blocked_until': blacklist.blocked_until,
                'is_permanent': blacklist.is_permanent
            })
        
        return Response({'blocked': False})


class OTPRateLimitViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing OTP rate limits"""
    queryset = OTPRateLimit.objects.all()
    serializer_class = OTPRateLimitSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['identifier_type', 'branch']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch if user is not admin
        if not self.request.user.is_superuser:
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                queryset = queryset.filter(branch_id=branch_id)
            else:
                if hasattr(self.request.user, 'branch'):
                    queryset = queryset.filter(branch=self.request.user.branch)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def check_limit(self, request):
        """Check rate limit for identifier"""
        serializer = CheckRateLimitSerializer(data=request.data)
        if serializer.is_valid():
            otp_service = OTPService()
            
            try:
                limit_info = otp_service.check_rate_limit(
                    identifier=serializer.validated_data['identifier'],
                    identifier_type=serializer.validated_data['identifier_type'],
                    branch_id=serializer.validated_data.get('branch_id')
                )
                
                return Response(limit_info)
                
            except Exception as e:
                logger.error(f"Error checking rate limit: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OTPTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for managing OTP templates"""
    queryset = OTPTemplate.objects.filter(deleted_at__isnull=True)
    serializer_class = OTPTemplateSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['template_type', 'is_default', 'branch']
    search_fields = ['name', 'content']
    ordering_fields = ['name', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch if user is not admin
        if not self.request.user.is_superuser:
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                queryset = queryset.filter(branch_id=branch_id)
            else:
                if hasattr(self.request.user, 'branch'):
                    queryset = queryset.filter(branch=self.request.user.branch)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set template as default for its type"""
        template = self.get_object()
        
        # Clear existing default for same type and branch
        OTPTemplate.objects.filter(
            template_type=template.template_type,
            branch=template.branch,
            is_default=True
        ).update(is_default=False)
        
        template.is_default = True
        template.save()
        
        return Response({'message': f'{template.name} set as default template'})
    
    @action(detail=True, methods=['post'])
    def test_render(self, request, pk=None):
        """Test template rendering"""
        template = self.get_object()
        test_context = request.data.get('context', {})
        
        try:
            rendered_content = template.render(test_context)
            
            # For email templates, include subject
            if template.template_type == 'EMAIL':
                from django.template import Template, Context
                subject_template = Template(template.subject)
                rendered_subject = subject_template.render(Context(test_context))
                
                return Response({
                    'subject': rendered_subject,
                    'content': rendered_content
                })
            
            return Response({'content': rendered_content})
            
        except Exception as e:
            logger.error(f"Error rendering template: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Public endpoints (no authentication required)
class PublicOTPView(APIView):
    """Public OTP endpoints"""
    permission_classes = [AllowAny]
    
    def post(self, request, action):
        """Handle public OTP actions"""
        otp_service = OTPService()
        
        if action == 'request':
            serializer = RequestOTPSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    ip_address = request.META.get('REMOTE_ADDR')
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                    device_id = request.data.get('device_id', '')
                    
                    otp_request = otp_service.request_otp(
                        **serializer.validated_data,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        device_id=device_id
                    )
                    
                    return Response({
                        'otp_id': str(otp_request.otp_id),
                        'status': otp_request.status,
                        'expires_at': otp_request.expires_at,
                        'message': 'OTP sent successfully'
                    }, status=status.HTTP_201_CREATED)
                    
                except Exception as e:
                    logger.error(f"Public OTP request error: {str(e)}")
                    return Response(
                        {'error': str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        elif action == 'verify':
            serializer = VerifyOTPSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    verified = otp_service.verify_otp(
                        otp_id=serializer.validated_data['otp_id'],
                        otp_code=serializer.validated_data['otp_code'],
                        recipient_contact=serializer.validated_data.get('recipient_contact')
                    )
                    
                    if verified:
                        return Response({
                            'verified': True,
                            'message': 'OTP verified successfully'
                        })
                    else:
                        return Response({
                            'verified': False,
                            'message': 'Invalid OTP or OTP expired'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                except Exception as e:
                    logger.error(f"Public OTP verify error: {str(e)}")
                    return Response(
                        {'error': str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        elif action == 'resend':
            serializer = ResendOTPSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    otp_request = otp_service.resend_otp(
                        otp_id=serializer.validated_data['otp_id'],
                        channel=serializer.validated_data.get('channel')
                    )
                    
                    if otp_request:
                        return Response({
                            'otp_id': str(otp_request.otp_id),
                            'status': otp_request.status,
                            'expires_at': otp_request.expires_at,
                            'message': 'OTP resent successfully'
                        })
                    else:
                        return Response(
                            {'error': 'Cannot resend OTP'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                except Exception as e:
                    logger.error(f"Public OTP resend error: {str(e)}")
                    return Response(
                        {'error': str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(
            {'error': 'Invalid action'},
            status=status.HTTP_400_BAD_REQUEST
        )