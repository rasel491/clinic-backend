from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from core.permissions import (
    IsAuthenticatedAndActive, HasBranchAccess,
    IsCashier, IsReceptionist, IsDoctor,
    IsClinicManager, IsSuperAdmin
)
from .models import (
    PaymentMethod, Payment, Refund, 
    PaymentReceipt, PaymentSplit
)
from .serializers import (
    PaymentMethodSerializer, PaymentSerializer, PaymentCreateSerializer,
    RefundSerializer, RefundCreateSerializer, PaymentReceiptSerializer,
    ReceiptGenerateSerializer, ApprovePaymentSerializer,
    CompleteRefundSerializer, ReconcilePaymentSerializer
)


# ===========================================
# PAYMENT METHOD VIEWSET
# ===========================================
class PaymentMethodViewSet(viewsets.ModelViewSet):
    """ViewSet for PaymentMethod CRUD operations"""
    
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticatedAndActive, HasBranchAccess]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'requires_approval']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticatedAndActive() & (IsClinicManager() | IsSuperAdmin())]
        return super().get_permissions()
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active payment methods"""
        methods = PaymentMethod.objects.filter(is_active=True).order_by('sort_order')
        serializer = self.get_serializer(methods, many=True)
        return Response(serializer.data)


# ===========================================
# PAYMENT VIEWSET
# ===========================================
class PaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for Payment CRUD operations"""
    
    queryset = Payment.objects.select_related(
        'invoice', 'patient', 'patient__user', 'branch',
        'payment_method', 'approved_by', 'reconciled_by',
        'last_reprinted_by'
    ).prefetch_related('splits', 'refunds')
    
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticatedAndActive, HasBranchAccess]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'branch', 'patient', 'payment_method', 'reconciled', 'is_locked']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update']:
            return [IsAuthenticatedAndActive() & (IsCashier() | IsReceptionist() | IsClinicManager() | IsSuperAdmin())]
        elif self.action in ['destroy', 'approve', 'reconcile']:
            return [IsAuthenticatedAndActive() & (IsClinicManager() | IsSuperAdmin())]
        return super().get_permissions()
    
    def get_queryset(self):
        """Filter queryset based on user role and branch"""
        queryset = super().get_queryset()
        
        # Filter by branch if specified
        branch_id = self.request.query_params.get('branch_id')
        if branch_id and self.request.user.role in [IsClinicManager, IsSuperAdmin]:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Filter by patient for patients
        if self.request.user.role == 'patient':
            queryset = queryset.filter(patient__user=self.request.user)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(payment_date__date__range=[start_date, end_date])
        
        # Filter by amount range
        min_amount = self.request.query_params.get('min_amount')
        max_amount = self.request.query_params.get('max_amount')
        if min_amount:
            queryset = queryset.filter(amount__gte=Decimal(min_amount))
        if max_amount:
            queryset = queryset.filter(amount__lte=Decimal(max_amount))
        
        # Filter by payment method
        method_code = self.request.query_params.get('method_code')
        if method_code:
            queryset = queryset.filter(payment_method__code=method_code)
        
        return queryset
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create payment with optional splits"""
        serializer = PaymentCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        payment = serializer.save()
        
        # Return full payment details
        full_serializer = PaymentSerializer(payment, context={'request': request})
        return Response(full_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def approve(self, request, pk=None):
        """Approve a pending payment"""
        payment = self.get_object()
        serializer = ApprovePaymentSerializer(data=request.data, context={'view': self})
        serializer.is_valid(raise_exception=True)
        
        # Check if user can approve
        if not request.user.has_role('clinic_manager') and not request.user.is_superuser:
            return Response(
                {'error': 'Only managers can approve payments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        payment.status = Payment.COMPLETED
        payment.completed_at = timezone.now()
        payment.approved_by = request.user
        payment.approved_at = timezone.now()
        payment.approval_notes = serializer.validated_data.get('notes', '')
        payment.save()
        
        return Response({
            'message': 'Payment approved successfully',
            'payment': PaymentSerializer(payment, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def reconcile(self, request, pk=None):
        """Reconcile a payment"""
        payment = self.get_object()
        serializer = ReconcilePaymentSerializer(data=request.data, context={'view': self})
        serializer.is_valid(raise_exception=True)
        
        payment.reconciled = serializer.validated_data['reconciled']
        payment.reconciled_at = timezone.now()
        payment.reconciled_by = request.user
        payment.save()
        
        return Response({
            'message': 'Payment reconciled successfully',
            'payment': PaymentSerializer(payment, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def generate_receipt(self, request, pk=None):
        """Generate receipt for payment"""
        payment = self.get_object()
        serializer = ReceiptGenerateSerializer(data=request.data, context={'view': self})
        serializer.is_valid(raise_exception=True)
        
        if payment.receipt_generated:
            return Response(
                {'error': 'Receipt already generated'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            receipt = payment.generate_receipt(request.user)
            
            return Response({
                'message': 'Receipt generated successfully',
                'receipt': PaymentReceiptSerializer(receipt).data,
                'payment': PaymentSerializer(payment, context={'request': request}).data
            }, status=status.HTTP_200_OK)
        
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get payment summary statistics"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Calculate statistics
        total_payments = queryset.count()
        total_amount = queryset.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Status breakdown
        status_breakdown = queryset.values('status').annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('status')
        
        # Method breakdown
        method_breakdown = queryset.values('payment_method__name', 'payment_method__code').annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('-amount')
        
        # Daily totals for last 7 days
        seven_days_ago = timezone.now() - timedelta(days=7)
        daily_totals = queryset.filter(
            payment_date__gte=seven_days_ago
        ).extra(
            {'date': "DATE(payment_date)"}
        ).values('date').annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('date')
        
        # Recent payments
        recent_payments = queryset.order_by('-payment_date')[:10]
        
        # Unreconciled payments
        unreconciled_count = queryset.filter(reconciled=False).count()
        unreconciled_amount = queryset.filter(reconciled=False).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        return Response({
            'total_payments': total_payments,
            'total_amount': total_amount,
            'unreconciled_count': unreconciled_count,
            'unreconciled_amount': unreconciled_amount,
            'status_breakdown': status_breakdown,
            'method_breakdown': method_breakdown,
            'daily_totals': daily_totals,
            'recent_payments': PaymentSerializer(recent_payments, many=True, context={'request': request}).data
        })
    
    @action(detail=False, methods=['get'])
    def daily_summary(self, request):
        """Get daily payment summary"""
        date = request.query_params.get('date', timezone.now().date())
        
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        
        payments = Payment.objects.filter(
            payment_date__date=date,
            branch=request.branch if hasattr(request, 'branch') else None
        )
        
        # Cashier summary
        cashier_summary = payments.values('created_by__username').annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('-amount')
        
        # Method summary
        method_summary = payments.values('payment_method__name').annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('-amount')
        
        # Hourly breakdown
        hourly_summary = payments.extra(
            {'hour': "EXTRACT(HOUR FROM payment_date)"}
        ).values('hour').annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('hour')
        
        return Response({
            'date': date,
            'total_payments': payments.count(),
            'total_amount': payments.aggregate(total=Sum('amount'))['total'] or Decimal('0'),
            'cashier_summary': cashier_summary,
            'method_summary': method_summary,
            'hourly_summary': hourly_summary
        })


# ===========================================
# REFUND VIEWSET
# ===========================================
class RefundViewSet(viewsets.ModelViewSet):
    """ViewSet for Refund CRUD operations"""
    
    queryset = Refund.objects.select_related(
        'payment', 'invoice', 'branch',
        'requested_by', 'approved_by', 'rejected_by', 'completed_by'
    )
    
    serializer_class = RefundSerializer
    permission_classes = [IsAuthenticatedAndActive, HasBranchAccess]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'branch', 'refund_method', 'is_locked']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create']:
            return [IsAuthenticatedAndActive() & (IsCashier() | IsReceptionist() | IsClinicManager() | IsSuperAdmin())]
        elif self.action in ['approve', 'reject', 'complete']:
            return [IsAuthenticatedAndActive() & (IsClinicManager() | IsSuperAdmin())]
        elif self.action in ['destroy']:
            return [IsAuthenticatedAndActive() & (IsSuperAdmin())]
        return super().get_permissions()
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        queryset = super().get_queryset()
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(requested_at__date__range=[start_date, end_date])
        
        # Filter by amount range
        min_amount = self.request.query_params.get('min_amount')
        max_amount = self.request.query_params.get('max_amount')
        if min_amount:
            queryset = queryset.filter(amount__gte=Decimal(min_amount))
        if max_amount:
            queryset = queryset.filter(amount__lte=Decimal(max_amount))
        
        return queryset
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create refund request"""
        serializer = RefundCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        payment = serializer.validated_data['payment']
        
        # Create refund
        refund = Refund.objects.create(
            payment=payment,
            invoice=payment.invoice,
            branch=payment.branch,
            amount=serializer.validated_data['amount'],
            refund_method=serializer.validated_data['refund_method'],
            reason=serializer.validated_data['reason'],
            notes=serializer.validated_data.get('notes', ''),
            reference_number=serializer.validated_data.get('reference_number', ''),
            bank_name=serializer.validated_data.get('bank_name', ''),
            account_number=serializer.validated_data.get('account_number', ''),
            ifsc_code=serializer.validated_data.get('ifsc_code', ''),
            cheque_number=serializer.validated_data.get('cheque_number', ''),
            cheque_date=serializer.validated_data.get('cheque_date'),
            requested_by=request.user,
            created_by=request.user,
            updated_by=request.user
        )
        
        # Auto-approve if small amount and user has permission
        if refund.amount <= Decimal('1000') and request.user.has_role('clinic_manager'):
            refund.approve(request.user, "Auto-approved: Small amount refund")
        
        return Response({
            'message': 'Refund request created successfully',
            'refund': RefundSerializer(refund, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def approve(self, request, pk=None):
        """Approve refund request"""
        refund = self.get_object()
        
        if refund.status != Refund.REQUESTED:
            return Response(
                {'error': f'Cannot approve refund in {refund.get_status_display()} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notes = request.data.get('notes', '')
        refund.approve(request.user, notes)
        
        return Response({
            'message': 'Refund approved successfully',
            'refund': RefundSerializer(refund, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def reject(self, request, pk=None):
        """Reject refund request"""
        refund = self.get_object()
        
        if refund.status != Refund.REQUESTED:
            return Response(
                {'error': f'Cannot reject refund in {refund.get_status_display()} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        if not reason:
            return Response(
                {'error': 'Rejection reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        refund.reject(request.user, reason)
        
        return Response({
            'message': 'Refund rejected successfully',
            'refund': RefundSerializer(refund, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def complete(self, request, pk=None):
        """Complete refund (process payment)"""
        refund = self.get_object()
        serializer = CompleteRefundSerializer(data=request.data, context={'view': self})
        serializer.is_valid(raise_exception=True)
        
        if refund.status != Refund.APPROVED:
            return Response(
                {'error': f'Cannot complete refund in {refund.get_status_display()} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update reference number if provided
        reference_number = serializer.validated_data.get('reference_number')
        if reference_number:
            refund.reference_number = reference_number
        
        refund.complete(request.user)
        
        return Response({
            'message': 'Refund completed successfully',
            'refund': RefundSerializer(refund, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get refund summary statistics"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Calculate statistics
        total_refunds = queryset.count()
        total_amount = queryset.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Status breakdown
        status_breakdown = queryset.values('status').annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('status')
        
        # Method breakdown
        method_breakdown = queryset.values('refund_method').annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('-amount')
        
        # Recent refunds
        recent_refunds = queryset.order_by('-requested_at')[:10]
        
        # Pending approval
        pending_count = queryset.filter(status=Refund.REQUESTED).count()
        pending_amount = queryset.filter(status=Refund.REQUESTED).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        return Response({
            'total_refunds': total_refunds,
            'total_amount': total_amount,
            'pending_count': pending_count,
            'pending_amount': pending_amount,
            'status_breakdown': status_breakdown,
            'method_breakdown': method_breakdown,
            'recent_refunds': RefundSerializer(recent_refunds, many=True, context={'request': request}).data
        })


# ===========================================
# RECEIPT VIEWSET
# ===========================================
class PaymentReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for PaymentReceipt read-only operations"""
    
    queryset = PaymentReceipt.objects.select_related(
        'payment', 'generated_by', 'original_receipt', 'branch'
    )
    
    serializer_class = PaymentReceiptSerializer
    permission_classes = [IsAuthenticatedAndActive, HasBranchAccess]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['branch', 'is_duplicate', 'generated_by']
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        queryset = super().get_queryset()
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(generated_at__date__range=[start_date, end_date])
        
        # Filter by receipt number
        receipt_number = self.request.query_params.get('receipt_number')
        if receipt_number:
            queryset = queryset.filter(receipt_number__icontains=receipt_number)
        
        # Filter by security code for verification
        security_code = self.request.query_params.get('security_code')
        if security_code:
            queryset = queryset.filter(security_code=security_code)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def create_duplicate(self, request, pk=None):
        """Create duplicate receipt"""
        receipt = self.get_object()
        
        if receipt.is_duplicate:
            return Response(
                {'error': 'Cannot create duplicate of a duplicate receipt'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        duplicate = receipt.create_duplicate(request.user)
        
        return Response({
            'message': 'Duplicate receipt created successfully',
            'original_receipt': PaymentReceiptSerializer(receipt).data,
            'duplicate_receipt': PaymentReceiptSerializer(duplicate).data
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def verify(self, request):
        """Verify receipt authenticity"""
        receipt_number = request.query_params.get('receipt_number')
        security_code = request.query_params.get('security_code')
        
        if not receipt_number or not security_code:
            return Response(
                {'error': 'Receipt number and security code are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            receipt = PaymentReceipt.objects.get(
                receipt_number=receipt_number,
                security_code=security_code
            )
            
            return Response({
                'is_valid': True,
                'receipt': PaymentReceiptSerializer(receipt).data,
                'payment': PaymentSerializer(receipt.payment).data
            }, status=status.HTTP_200_OK)
        
        except PaymentReceipt.DoesNotExist:
            return Response({
                'is_valid': False,
                'message': 'Invalid receipt or security code'
            }, status=status.HTTP_200_OK)