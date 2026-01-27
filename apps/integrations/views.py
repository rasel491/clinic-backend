# apps/integrations/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
import logging

from core.permissions import (
    IsAdminUser, IsManager, IsDoctor, IsReceptionist, IsCashier
)
from apps.clinics.models import Branch
from .models import (
    IntegrationType, IntegrationProvider, BranchIntegration,
    PharmacyIntegration, PaymentGatewayIntegration,
    IntegrationLog, WebhookEvent, PharmacyOrder, PaymentTransaction
)
from .serializers import (
    IntegrationTypeSerializer, IntegrationProviderSerializer,
    BranchIntegrationSerializer, PharmacyIntegrationSerializer,
    PaymentGatewayIntegrationSerializer, IntegrationLogSerializer,
    WebhookEventSerializer, PharmacyOrderSerializer,
    PaymentTransactionSerializer, PharmacyOrderCreateSerializer,
    PaymentIntentSerializer
)
from .services import PharmacyService, PaymentService
from .pharmacy.qr_service import QRCodeService
# from .payment_gateways.razorpay import RazorpayGateway
# from .payment_gateways.stripe import StripeGateway

logger = logging.getLogger(__name__)


class IntegrationTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing integration types"""
    queryset = IntegrationType.objects.filter(deleted_at__isnull=True)
    serializer_class = IntegrationTypeSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['integration_type', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class IntegrationProviderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing integration providers"""
    queryset = IntegrationProvider.objects.filter(deleted_at__isnull=True)
    serializer_class = IntegrationProviderSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['provider_type', 'integration_type', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class BranchIntegrationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing branch integrations"""
    queryset = BranchIntegration.objects.filter(deleted_at__isnull=True)
    serializer_class = BranchIntegrationSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'is_default', 'integration_type', 'branch']
    search_fields = ['provider__name']
    ordering_fields = ['-is_default', 'created_at']
    
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
    def test_connection(self, request, pk=None):
        """Test integration connection"""
        integration = self.get_object()
        
        try:
            if integration.integration_type.integration_type == 'payment':
                payment_service = PaymentService()
                success = payment_service.test_connection(integration)
            elif integration.integration_type.integration_type == 'pharmacy':
                pharmacy_service = PharmacyService()
                success = pharmacy_service.test_connection(integration)
            else:
                return Response(
                    {'error': 'Test connection not supported for this integration type'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if success:
                integration.status = 'active'
                integration.save()
                return Response({'message': 'Connection test successful'})
            else:
                integration.status = 'failed'
                integration.save()
                return Response(
                    {'error': 'Connection test failed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error testing connection: {str(e)}")
            integration.status = 'failed'
            integration.save()
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """Trigger data sync for integration"""
        integration = self.get_object()
        
        try:
            if integration.integration_type.integration_type == 'pharmacy':
                pharmacy_service = PharmacyService()
                result = pharmacy_service.sync_inventory(integration)
            else:
                return Response(
                    {'error': 'Sync not supported for this integration type'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error syncing integration: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PharmacyIntegrationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing pharmacy integrations"""
    queryset = PharmacyIntegration.objects.all()
    serializer_class = PharmacyIntegrationSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['delivery_enabled', 'sync_inventory', 'auto_create_order']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch
        if not self.request.user.is_superuser:
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                queryset = queryset.filter(branch_integration__branch_id=branch_id)
            else:
                if hasattr(self.request.user, 'branch'):
                    queryset = queryset.filter(branch_integration__branch=self.request.user.branch)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class PaymentGatewayIntegrationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing payment gateway integrations"""
    queryset = PaymentGatewayIntegration.objects.all()
    serializer_class = PaymentGatewayIntegrationSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch
        if not self.request.user.is_superuser:
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                queryset = queryset.filter(branch_integration__branch_id=branch_id)
            else:
                if hasattr(self.request.user, 'branch'):
                    queryset = queryset.filter(branch_integration__branch=self.request.user.branch)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class IntegrationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing integration logs"""
    queryset = IntegrationLog.objects.all()
    serializer_class = IntegrationLogSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['log_type', 'direction', 'status', 'branch_integration']
    ordering_fields = ['-started_at', 'duration']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch
        if not self.request.user.is_superuser:
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                queryset = queryset.filter(branch_integration__branch_id=branch_id)
            else:
                if hasattr(self.request.user, 'branch'):
                    queryset = queryset.filter(branch_integration__branch=self.request.user.branch)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(started_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(started_at__date__lte=end_date)
        
        return queryset


class WebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing webhook events"""
    queryset = WebhookEvent.objects.all()
    serializer_class = WebhookEventSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['event_type', 'processed', 'branch_integration']
    ordering_fields = ['-created_at', 'processed_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch
        if not self.request.user.is_superuser:
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                queryset = queryset.filter(branch_integration__branch_id=branch_id)
            else:
                if hasattr(self.request.user, 'branch'):
                    queryset = queryset.filter(branch_integration__branch=self.request.user.branch)
        
        return queryset


class PharmacyOrderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing pharmacy orders"""
    queryset = PharmacyOrder.objects.all()
    serializer_class = PharmacyOrderSerializer
    permission_classes = [IsAuthenticated, IsReceptionist]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_status', 'delivery_type', 'branch_integration']
    search_fields = ['order_id', 'external_order_id', 'prescription__patient__name']
    ordering_fields = ['-created_at', 'estimated_delivery']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch
        if not self.request.user.is_superuser:
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                queryset = queryset.filter(branch_integration__branch_id=branch_id)
            else:
                if hasattr(self.request.user, 'branch'):
                    queryset = queryset.filter(branch_integration__branch=self.request.user.branch)
        
        # Filter by patient if doctor
        if self.request.user.role == 'doctor':
            queryset = queryset.filter(prescription__doctor=self.request.user)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def create_order(self, request):
        """Create a pharmacy order"""
        serializer = PharmacyOrderCreateSerializer(data=request.data)
        if serializer.is_valid():
            pharmacy_service = PharmacyService()
            try:
                order = pharmacy_service.create_order(
                    prescription_id=serializer.validated_data['prescription_id'],
                    delivery_type=serializer.validated_data['delivery_type'],
                    delivery_address=serializer.validated_data.get('delivery_address'),
                    payment_method=serializer.validated_data['payment_method'],
                    notes=serializer.validated_data.get('notes'),
                    user=request.user
                )
                return Response(
                    PharmacyOrderSerializer(order).data,
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
                logger.error(f"Error creating pharmacy order: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a pharmacy order"""
        order = self.get_object()
        
        if order.status in ['delivered', 'cancelled']:
            return Response(
                {'error': f'Cannot cancel order in {order.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pharmacy_service = PharmacyService()
        try:
            success = pharmacy_service.cancel_order(order)
            if success:
                order.refresh_from_db()
                return Response(PharmacyOrderSerializer(order).data)
            else:
                return Response(
                    {'error': 'Failed to cancel order'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def qr_code(self, request, pk=None):
        """Generate QR code for pharmacy order"""
        order = self.get_object()
        qr_service = QRCodeService()
        
        try:
            qr_data = qr_service.generate_order_qr(order)
            return Response(qr_data)
        except Exception as e:
            logger.error(f"Error generating QR code: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentTransactionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing payment transactions"""
    queryset = PaymentTransaction.objects.all()
    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated, IsCashier]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_type', 'payment_method', 'branch_integration']
    search_fields = ['transaction_id', 'external_transaction_id', 'customer_email', 'customer_phone']
    ordering_fields = ['-initiated_at', 'amount']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch
        if not self.request.user.is_superuser:
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                queryset = queryset.filter(branch_integration__branch_id=branch_id)
            else:
                if hasattr(self.request.user, 'branch'):
                    queryset = queryset.filter(branch_integration__branch=self.request.user.branch)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def create_payment_intent(self, request):
        """Create a payment intent"""
        serializer = PaymentIntentSerializer(data=request.data)
        if serializer.is_valid():
            payment_service = PaymentService()
            try:
                payment_data = payment_service.create_payment_intent(
                    invoice_id=serializer.validated_data['invoice_id'],
                    amount=serializer.validated_data['amount'],
                    currency=serializer.validated_data['currency'],
                    payment_method=serializer.validated_data.get('payment_method'),
                    customer_name=serializer.validated_data.get('customer_name'),
                    customer_email=serializer.validated_data.get('customer_email'),
                    customer_phone=serializer.validated_data.get('customer_phone'),
                    return_url=serializer.validated_data.get('return_url'),
                    user=request.user
                )
                return Response(payment_data)
            except Exception as e:
                logger.error(f"Error creating payment intent: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def capture(self, request, pk=None):
        """Capture a payment"""
        transaction = self.get_object()
        
        if transaction.status != 'authorized':
            return Response(
                {'error': 'Only authorized payments can be captured'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_service = PaymentService()
        try:
            success = payment_service.capture_payment(transaction)
            if success:
                transaction.refresh_from_db()
                return Response(PaymentTransactionSerializer(transaction).data)
            else:
                return Response(
                    {'error': 'Failed to capture payment'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            logger.error(f"Error capturing payment: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        """Refund a payment"""
        transaction = self.get_object()
        
        if transaction.status != 'captured':
            return Response(
                {'error': 'Only captured payments can be refunded'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        amount = request.data.get('amount')
        reason = request.data.get('reason', '')
        
        payment_service = PaymentService()
        try:
            refund_transaction = payment_service.refund_payment(transaction, amount, reason)
            return Response(PaymentTransactionSerializer(refund_transaction).data)
        except Exception as e:
            logger.error(f"Error refunding payment: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify a payment transaction"""
        transaction = self.get_object()
        
        payment_service = PaymentService()
        try:
            verified = payment_service.verify_payment(transaction)
            if verified:
                transaction.refresh_from_db()
                return Response(PaymentTransactionSerializer(transaction).data)
            else:
                return Response(
                    {'error': 'Payment verification failed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Webhook endpoints (no authentication required for incoming webhooks)
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

class WebhookReceiverView(APIView):
    """Receive webhooks from integrated services"""
    permission_classes = [AllowAny]
    
    def post(self, request, provider, integration_id):
        try:
            integration = BranchIntegration.objects.get(id=integration_id, provider__provider_type=provider)
            
            # Verify webhook signature if configured
            if integration.webhook_secret:
                # Add signature verification logic here
                pass
            
            # Create webhook event
            webhook_event = WebhookEvent.objects.create(
                branch_integration=integration,
                event_type=request.data.get('event', 'custom'),
                event_id=request.data.get('id'),
                payload=request.data,
                headers=dict(request.headers),
                signature=request.headers.get('X-Signature', '')
            )
            
            # Process webhook asynchronously
            # You can use Celery or Django Q here for async processing
            self._process_webhook_async(webhook_event)
            
            return Response({'status': 'received'}, status=status.HTTP_200_OK)
            
        except BranchIntegration.DoesNotExist:
            return Response({'error': 'Integration not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _process_webhook_async(self, webhook_event):
        """Process webhook asynchronously"""
        # This should be implemented with Celery or Django Q
        # For now, we'll process synchronously
        try:
            if webhook_event.event_type == 'payment_success':
                self._handle_payment_success(webhook_event)
            elif webhook_event.event_type == 'payment_failed':
                self._handle_payment_failed(webhook_event)
            elif webhook_event.event_type == 'order_delivered':
                self._handle_order_delivered(webhook_event)
            # Add more event handlers as needed
            
            webhook_event.processed = True
            webhook_event.processed_at = timezone.now()
            webhook_event.save()
            
        except Exception as e:
            logger.error(f"Error processing webhook event: {str(e)}")
            webhook_event.processing_error = str(e)
            webhook_event.save()
    
    def _handle_payment_success(self, webhook_event):
        """Handle payment success webhook"""
        payment_id = webhook_event.payload.get('payment_id')
        # Update payment transaction status
        # Update invoice status
        # Send notification
        pass
    
    def _handle_payment_failed(self, webhook_event):
        """Handle payment failed webhook"""
        pass
    
    def _handle_order_delivered(self, webhook_event):
        """Handle order delivered webhook"""
        pass