# # apps/notifications/views.py
# from rest_framework import viewsets, status, filters
# from rest_framework.decorators import action
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated
# from django.utils import timezone
# from django.db.models import Q
# from django_filters.rest_framework import DjangoFilterBackend
# import logging

# from core.permissions import (
#     IsAdminUser, IsManager, IsDoctor, IsReceptionist, IsCashier
# )
# from apps.clinics.models import Branch
# from .models import (
#     NotificationTemplate, NotificationLog, SMSProvider, 
#     EmailProvider, NotificationSetting, NotificationQueue
# )
# from .serializers import (
#     NotificationTemplateSerializer, NotificationLogSerializer,
#     SMSProviderSerializer, EmailProviderSerializer,
#     NotificationSettingSerializer, NotificationQueueSerializer,
#     SendNotificationSerializer
# )
# from .services import NotificationService

# logger = logging.getLogger(__name__)


# class NotificationTemplateViewSet(viewsets.ModelViewSet):
#     """ViewSet for managing notification templates"""
#     queryset = NotificationTemplate.objects.filter(deleted_at__isnull=True)
#     serializer_class = NotificationTemplateSerializer
#     permission_classes = [IsAuthenticated, IsManager]
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_fields = ['notification_type', 'category', 'is_active', 'branch']
#     search_fields = ['name', 'subject', 'body']
#     ordering_fields = ['name', 'created_at']
    
#     def get_queryset(self):
#         queryset = super().get_queryset()
#         branch_id = self.request.query_params.get('branch_id')
#         if branch_id:
#             queryset = queryset.filter(branch_id=branch_id)
#         return queryset
    
#     def perform_create(self, serializer):
#         serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
#     def perform_update(self, serializer):
#         serializer.save(updated_by=self.request.user)
    
#     @action(detail=True, methods=['post'])
#     def duplicate(self, request, pk=None):
#         """Duplicate a template"""
#         template = self.get_object()
#         new_template = NotificationTemplate.objects.create(
#             name=f"{template.name} (Copy)",
#             notification_type=template.notification_type,
#             category=template.category,
#             subject=template.subject,
#             body=template.body,
#             variables=template.variables,
#             is_active=template.is_active,
#             branch=template.branch,
#             created_by=request.user,
#             updated_by=request.user
#         )
#         serializer = self.get_serializer(new_template)
#         return Response(serializer.data, status=status.HTTP_201_CREATED)


# class NotificationLogViewSet(viewsets.ModelViewSet):
#     """ViewSet for viewing notification logs"""
#     queryset = NotificationLog.objects.all()
#     serializer_class = NotificationLogSerializer
#     permission_classes = [IsAuthenticated, IsManager]
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_fields = ['notification_type', 'status', 'priority', 'branch', 'recipient_type']
#     search_fields = ['recipient_contact', 'message', 'subject']
#     ordering_fields = ['created_at', 'sent_at', 'priority']
    
#     def get_queryset(self):
#         queryset = super().get_queryset()
        
#         # Filter by branch if user is not admin
#         if not self.request.user.is_superuser:
#             branch_id = self.request.query_params.get('branch_id')
#             if branch_id:
#                 queryset = queryset.filter(branch_id=branch_id)
#             else:
#                 # If user has specific branch access
#                 if hasattr(self.request.user, 'branch'):
#                     queryset = queryset.filter(branch=self.request.user.branch)
        
#         # Filter by date range
#         start_date = self.request.query_params.get('start_date')
#         end_date = self.request.query_params.get('end_date')
#         if start_date:
#             queryset = queryset.filter(created_at__date__gte=start_date)
#         if end_date:
#             queryset = queryset.filter(created_at__date__lte=end_date)
        
#         return queryset
    
#     @action(detail=False, methods=['post'])
#     def send(self, request):
#         """Send a notification"""
#         serializer = SendNotificationSerializer(data=request.data)
#         if serializer.is_valid():
#             notification_service = NotificationService()
#             try:
#                 notification_log = notification_service.send_notification(
#                     **serializer.validated_data,
#                     branch_id=request.data.get('branch_id'),
#                     user=request.user
#                 )
#                 return Response(
#                     NotificationLogSerializer(notification_log).data,
#                     status=status.HTTP_201_CREATED
#                 )
#             except Exception as e:
#                 logger.error(f"Error sending notification: {str(e)}")
#                 return Response(
#                     {'error': str(e)},
#                     status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
#     @action(detail=True, methods=['post'])
#     def retry(self, request, pk=None):
#         """Retry a failed notification"""
#         notification_log = self.get_object()
#         if notification_log.status not in ['failed', 'pending']:
#             return Response(
#                 {'error': 'Only failed or pending notifications can be retried'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         notification_service = NotificationService()
#         try:
#             success = notification_service.retry_notification(notification_log)
#             if success:
#                 notification_log.refresh_from_db()
#                 return Response(NotificationLogSerializer(notification_log).data)
#             else:
#                 return Response(
#                     {'error': 'Failed to retry notification'},
#                     status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
#         except Exception as e:
#             logger.error(f"Error retrying notification: {str(e)}")
#             return Response(
#                 {'error': str(e)},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     @action(detail=False, methods=['get'])
#     def stats(self, request):
#         """Get notification statistics"""
#         queryset = self.get_queryset()
        
#         stats = {
#             'total': queryset.count(),
#             'sent': queryset.filter(status='sent').count(),
#             'delivered': queryset.filter(status='delivered').count(),
#             'failed': queryset.filter(status='failed').count(),
#             'pending': queryset.filter(status='pending').count(),
#             'by_type': list(queryset.values('notification_type').annotate(
#                 count=models.Count('id')
#             )),
#             'by_category': list(queryset.values('recipient_type').annotate(
#                 count=models.Count('id')
#             )),
#         }
        
#         return Response(stats)


# class SMSProviderViewSet(viewsets.ModelViewSet):
#     """ViewSet for managing SMS providers"""
#     queryset = SMSProvider.objects.filter(deleted_at__isnull=True)
#     serializer_class = SMSProviderSerializer
#     permission_classes = [IsAuthenticated, IsManager]
#     filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
#     filterset_fields = ['provider_type', 'is_active', 'branch']
    
#     def get_queryset(self):
#         queryset = super().get_queryset()
        
#         # Filter by branch if user is not admin
#         if not self.request.user.is_superuser:
#             branch_id = self.request.query_params.get('branch_id')
#             if branch_id:
#                 queryset = queryset.filter(branch_id=branch_id)
#             else:
#                 if hasattr(self.request.user, 'branch'):
#                     queryset = queryset.filter(branch=self.request.user.branch)
        
#         return queryset
    
#     def perform_create(self, serializer):
#         serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
#     def perform_update(self, serializer):
#         serializer.save(updated_by=self.request.user)
    
#     @action(detail=True, methods=['post'])
#     def test(self, request, pk=None):
#         """Test SMS provider configuration"""
#         provider = self.get_object()
#         test_number = request.data.get('test_number')
        
#         if not test_number:
#             return Response(
#                 {'error': 'test_number is required'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         notification_service = NotificationService()
#         try:
#             success = notification_service.test_sms_provider(provider, test_number)
#             if success:
#                 return Response({'message': 'Test SMS sent successfully'})
#             else:
#                 return Response(
#                     {'error': 'Failed to send test SMS'},
#                     status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
#         except Exception as e:
#             logger.error(f"Error testing SMS provider: {str(e)}")
#             return Response(
#                 {'error': str(e)},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


# class EmailProviderViewSet(viewsets.ModelViewSet):
#     """ViewSet for managing Email providers"""
#     queryset = EmailProvider.objects.filter(deleted_at__isnull=True)
#     serializer_class = EmailProviderSerializer
#     permission_classes = [IsAuthenticated, IsManager]
#     filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
#     filterset_fields = ['provider_type', 'is_active', 'branch']
    
#     def get_queryset(self):
#         queryset = super().get_queryset()
        
#         # Filter by branch if user is not admin
#         if not self.request.user.is_superuser:
#             branch_id = self.request.query_params.get('branch_id')
#             if branch_id:
#                 queryset = queryset.filter(branch_id=branch_id)
#             else:
#                 if hasattr(self.request.user, 'branch'):
#                     queryset = queryset.filter(branch=self.request.user.branch)
        
#         return queryset
    
#     def perform_create(self, serializer):
#         serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
#     def perform_update(self, serializer):
#         serializer.save(updated_by=self.request.user)
    
#     @action(detail=True, methods=['post'])
#     def test(self, request, pk=None):
#         """Test Email provider configuration"""
#         provider = self.get_object()
#         test_email = request.data.get('test_email')
        
#         if not test_email:
#             return Response(
#                 {'error': 'test_email is required'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         notification_service = NotificationService()
#         try:
#             success = notification_service.test_email_provider(provider, test_email)
#             if success:
#                 return Response({'message': 'Test email sent successfully'})
#             else:
#                 return Response(
#                     {'error': 'Failed to send test email'},
#                     status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
#         except Exception as e:
#             logger.error(f"Error testing email provider: {str(e)}")
#             return Response(
#                 {'error': str(e)},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


# class NotificationSettingViewSet(viewsets.ModelViewSet):
#     """ViewSet for managing notification settings"""
#     queryset = NotificationSetting.objects.all()
#     serializer_class = NotificationSettingSerializer
#     permission_classes = [IsAuthenticated, IsManager]
    
#     @action(detail=False, methods=['get'])
#     def for_appointment(self, request):
#         """Get settings for appointment notifications"""
#         settings = {
#             'confirmation': NotificationSetting.objects.filter(
#                 category='appointment_confirmation'
#             ).first(),
#             'reminder': NotificationSetting.objects.filter(
#                 category='appointment_reminder'
#             ).first(),
#             'cancellation': NotificationSetting.objects.filter(
#                 category='appointment_cancellation'
#             ).first(),
#         }
#         serializer = self.get_serializer(settings)
#         return Response(serializer.data)


# class NotificationQueueViewSet(viewsets.ReadOnlyModelViewSet):
#     """ViewSet for viewing notification queue"""
#     queryset = NotificationQueue.objects.filter(processing=False)
#     serializer_class = NotificationQueueSerializer
#     permission_classes = [IsAuthenticated, IsManager]
#     filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
#     filterset_fields = ['priority', 'processing']
    
#     @action(detail=False, methods=['post'])
#     def process(self, request):
#         """Process queued notifications"""
#         limit = request.data.get('limit', 10)
#         notification_service = NotificationService()
        
#         try:
#             processed = notification_service.process_queue(limit=limit)
#             return Response({
#                 'message': f'Processed {processed} notifications',
#                 'processed': processed
#             })
#         except Exception as e:
#             logger.error(f"Error processing queue: {str(e)}")
#             return Response(
#                 {'error': str(e)},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


# apps/notifications/views.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q, Count  # Added Count import
from django_filters.rest_framework import DjangoFilterBackend
import logging

from core.permissions import (
    IsAdminUser, IsManager, IsDoctor, IsReceptionist, IsCashier
)
from apps.clinics.models import Branch
from .models import (
    NotificationTemplate, NotificationLog, SMSProvider, 
    EmailProvider, NotificationSetting, NotificationQueue
)
from .serializers import (
    NotificationTemplateSerializer, NotificationLogSerializer,
    SMSProviderSerializer, EmailProviderSerializer,
    NotificationSettingSerializer, NotificationQueueSerializer,
    SendNotificationSerializer
)
from .services import NotificationService

logger = logging.getLogger(__name__)


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notification templates"""
    queryset = NotificationTemplate.objects.filter(deleted_at__isnull=True)
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'category', 'is_active', 'branch']
    search_fields = ['name', 'subject', 'body']
    ordering_fields = ['name', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        branch_id = self.request.query_params.get('branch_id')
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a template"""
        template = self.get_object()
        new_template = NotificationTemplate.objects.create(
            name=f"{template.name} (Copy)",
            notification_type=template.notification_type,
            category=template.category,
            subject=template.subject,
            body=template.body,
            variables=template.variables,
            is_active=template.is_active,
            branch=template.branch,
            created_by=request.user,
            updated_by=request.user
        )
        serializer = self.get_serializer(new_template)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NotificationLogViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing notification logs"""
    queryset = NotificationLog.objects.all()
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'status', 'priority', 'branch', 'recipient_type']
    search_fields = ['recipient_contact', 'message', 'subject']
    ordering_fields = ['created_at', 'sent_at', 'priority']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch if user is not admin
        if not self.request.user.is_superuser:
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                queryset = queryset.filter(branch_id=branch_id)
            else:
                # If user has specific branch access
                if hasattr(self.request.user, 'branch'):
                    queryset = queryset.filter(branch=self.request.user.branch)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def send(self, request):
        """Send a notification"""
        serializer = SendNotificationSerializer(data=request.data)
        if serializer.is_valid():
            notification_service = NotificationService()
            try:
                # Extract branch_id from validated data
                validated_data = serializer.validated_data.copy()
                branch_id = validated_data.pop('branch_id')
                
                notification_log = notification_service.send_notification(
                    **validated_data,
                    branch_id=branch_id,
                    user=request.user
                )
                return Response(
                    NotificationLogSerializer(notification_log).data,
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
                logger.error(f"Error sending notification: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry a failed notification"""
        notification_log = self.get_object()
        if notification_log.status not in ['failed', 'pending']:
            return Response(
                {'error': 'Only failed or pending notifications can be retried'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notification_service = NotificationService()
        try:
            success = notification_service.retry_notification(notification_log)
            if success:
                notification_log.refresh_from_db()
                return Response(NotificationLogSerializer(notification_log).data)
            else:
                return Response(
                    {'error': 'Failed to retry notification'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            logger.error(f"Error retrying notification: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get notification statistics"""
        queryset = self.get_queryset()
        
        # Using Count from django.db.models
        from django.db.models import Count
        
        stats = {
            'total': queryset.count(),
            'sent': queryset.filter(status='sent').count(),
            'delivered': queryset.filter(status='delivered').count(),
            'failed': queryset.filter(status='failed').count(),
            'pending': queryset.filter(status='pending').count(),
            'by_type': list(queryset.values('notification_type').annotate(
                count=Count('id')
            )),
            'by_category': list(queryset.values('recipient_type').annotate(
                count=Count('id')
            )),
        }
        
        return Response(stats)


class SMSProviderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing SMS providers"""
    queryset = SMSProvider.objects.filter(deleted_at__isnull=True)
    serializer_class = SMSProviderSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['provider_type', 'is_active', 'branch']
    
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
    def test(self, request, pk=None):
        """Test SMS provider configuration"""
        provider = self.get_object()
        test_number = request.data.get('test_number')
        
        if not test_number:
            return Response(
                {'error': 'test_number is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notification_service = NotificationService()
        try:
            success = notification_service.test_sms_provider(provider, test_number)
            if success:
                return Response({'message': 'Test SMS sent successfully'})
            else:
                return Response(
                    {'error': 'Failed to send test SMS'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            logger.error(f"Error testing SMS provider: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EmailProviderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Email providers"""
    queryset = EmailProvider.objects.filter(deleted_at__isnull=True)
    serializer_class = EmailProviderSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['provider_type', 'is_active', 'branch']
    
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
    def test(self, request, pk=None):
        """Test Email provider configuration"""
        provider = self.get_object()
        test_email = request.data.get('test_email')
        
        if not test_email:
            return Response(
                {'error': 'test_email is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notification_service = NotificationService()
        try:
            success = notification_service.test_email_provider(provider, test_email)
            if success:
                return Response({'message': 'Test email sent successfully'})
            else:
                return Response(
                    {'error': 'Failed to send test email'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            logger.error(f"Error testing email provider: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NotificationSettingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notification settings"""
    queryset = NotificationSetting.objects.all()
    serializer_class = NotificationSettingSerializer
    permission_classes = [IsAuthenticated, IsManager]
    
    @action(detail=False, methods=['get'])
    def for_appointment(self, request):
        """Get settings for appointment notifications"""
        settings = {
            'confirmation': NotificationSetting.objects.filter(
                category='appointment_confirmation'
            ).first(),
            'reminder': NotificationSetting.objects.filter(
                category='appointment_reminder'
            ).first(),
            'cancellation': NotificationSetting.objects.filter(
                category='appointment_cancellation'
            ).first(),
        }
        
        # Serialize each setting
        serializer = self.get_serializer
        data = {
            'confirmation': serializer(settings['confirmation']).data if settings['confirmation'] else None,
            'reminder': serializer(settings['reminder']).data if settings['reminder'] else None,
            'cancellation': serializer(settings['cancellation']).data if settings['cancellation'] else None,
        }
        
        return Response(data)


class NotificationQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing notification queue"""
    queryset = NotificationQueue.objects.filter(processing=False)
    serializer_class = NotificationQueueSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['priority', 'processing']
    
    @action(detail=False, methods=['post'])
    def process(self, request):
        """Process queued notifications"""
        limit = request.data.get('limit', 10)
        notification_service = NotificationService()
        
        try:
            processed = notification_service.process_queue(limit=limit)
            return Response({
                'message': f'Processed {processed} notifications',
                'processed': processed
            })
        except Exception as e:
            logger.error(f"Error processing queue: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )