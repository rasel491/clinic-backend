from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from core.permissions import (
    IsAuthenticatedAndActive, HasBranchAccess,
    IsCashier, IsReceptionist, IsDoctor,
    IsClinicManager, IsSuperAdmin
)
from .models import Invoice, InvoiceItem, DiscountPolicy, AppliedDiscount
from .serializers import (
    InvoiceSerializer, InvoiceCreateSerializer, InvoiceItemSerializer,
    DiscountPolicySerializer, AppliedDiscountSerializer,
    ApplyPaymentSerializer, VoidInvoiceSerializer, ApplyDiscountSerializer
)
from apps.payments.models import Payment
from apps.patients.models import Patient
from decimal import Decimal 

class InvoiceViewSet(viewsets.ModelViewSet):
    """ViewSet for Invoice CRUD operations"""
    
    queryset = Invoice.objects.select_related(
        'patient', 'patient__user', 'branch', 'visit', 'referred_by'
    ).prefetch_related('items', 'applied_discounts')
    
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticatedAndActive, HasBranchAccess]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'branch', 'patient', 'is_final', 'is_locked']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticatedAndActive() & (IsCashier() | IsReceptionist() | IsClinicManager() | IsSuperAdmin())]
        elif self.action in ['apply_payment', 'void_invoice', 'add_late_fee']:
            return [IsAuthenticatedAndActive() & (IsCashier() | IsClinicManager() | IsSuperAdmin())]
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
            queryset = queryset.filter(invoice_date__range=[start_date, end_date])
        
        return queryset
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create invoice with items"""
        serializer = InvoiceCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        invoice = serializer.save()
        
        # Return full invoice details
        full_serializer = InvoiceSerializer(invoice, context={'request': request})
        return Response(full_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def apply_payment(self, request, pk=None):
        """Apply payment to invoice"""
        invoice = self.get_object()
        serializer = ApplyPaymentSerializer(data=request.data, context={'view': self})
        serializer.is_valid(raise_exception=True)
        
        try:
            payment = invoice.apply_payment(
                amount=serializer.validated_data['amount'],
                payment_method=serializer.validated_data['payment_method'],
                user=request.user
            )
            
            return Response({
                'message': 'Payment applied successfully',
                'invoice': InvoiceSerializer(invoice, context={'request': request}).data,
                'payment_id': payment.id
            }, status=status.HTTP_200_OK)
        
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def void_invoice(self, request, pk=None):
        """Void an invoice"""
        invoice = self.get_object()
        serializer = VoidInvoiceSerializer(data=request.data, context={'view': self})
        serializer.is_valid(raise_exception=True)
        
        try:
            invoice.void_invoice(
                reason=serializer.validated_data['reason'],
                user=request.user
            )
            
            return Response({
                'message': 'Invoice voided successfully',
                'invoice': InvoiceSerializer(invoice, context={'request': request}).data
            }, status=status.HTTP_200_OK)
        
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def apply_discount(self, request, pk=None):
        """Apply discount to invoice"""
        invoice = self.get_object()
        serializer = ApplyDiscountSerializer(data=request.data, context={'view': self})
        serializer.is_valid(raise_exception=True)
        
        discount_policy = serializer.validated_data['discount_policy']
        discount_amount = discount_policy.calculate_discount(invoice.subtotal)
        
        if discount_amount <= 0:
            return Response({'error': 'Discount amount is zero'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create applied discount
        applied_discount = AppliedDiscount.objects.create(
            invoice=invoice,
            discount_policy=discount_policy,
            discount_amount=discount_amount,
            original_amount=invoice.subtotal,
            approved_by=request.user if not discount_policy.requires_approval else None,
            approved_at=timezone.now() if not discount_policy.requires_approval else None,
            approval_notes=serializer.validated_data.get('notes', '')
        )
        
        # Update invoice discount
        invoice.discount_amount += discount_amount
        invoice.save()
        
        return Response({
            'message': 'Discount applied successfully',
            'discount': AppliedDiscountSerializer(applied_discount).data,
            'invoice': InvoiceSerializer(invoice, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def add_late_fee(self, request, pk=None):
        """Add late fee to overdue invoice"""
        invoice = self.get_object()
        
        if invoice.status != 'OVERDUE':
            return Response({'error': 'Can only add late fee to overdue invoices'}, status=status.HTTP_400_BAD_REQUEST)
        
        fee_amount = request.data.get('fee_amount')
        reason = request.data.get('reason', '')
        
        if not fee_amount or Decimal(fee_amount) <= 0:
            return Response({'error': 'Invalid fee amount'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            invoice.add_late_fee(
                fee_amount=Decimal(fee_amount),
                reason=reason,
                user=request.user
            )
            
            return Response({
                'message': 'Late fee added successfully',
                'invoice': InvoiceSerializer(invoice, context={'request': request}).data
            }, status=status.HTTP_200_OK)
        
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get billing summary statistics"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Calculate statistics
        total_invoices = queryset.count()
        total_amount = queryset.aggregate(total=Sum('total_amount'))['total'] or 0
        total_paid = queryset.aggregate(total=Sum('paid_amount'))['total'] or 0
        total_balance = queryset.aggregate(total=Sum('balance_amount'))['total'] or 0
        
        # Status breakdown
        status_breakdown = queryset.values('status').annotate(
            count=Count('id'),
            amount=Sum('total_amount')
        ).order_by('status')
        
        # Recent invoices
        recent_invoices = queryset.order_by('-created_at')[:10]
        
        # Overdue invoices
        overdue_invoices = queryset.filter(status='OVERDUE').count()
        overdue_amount = queryset.filter(status='OVERDUE').aggregate(
            total=Sum('balance_amount')
        )['total'] or 0
        
        return Response({
            'total_invoices': total_invoices,
            'total_amount': total_amount,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'overdue_invoices': overdue_invoices,
            'overdue_amount': overdue_amount,
            'status_breakdown': status_breakdown,
            'recent_invoices': InvoiceSerializer(recent_invoices, many=True, context={'request': request}).data
        })


class InvoiceItemViewSet(viewsets.ModelViewSet):
    """ViewSet for InvoiceItem CRUD operations"""
    
    queryset = InvoiceItem.objects.select_related('invoice', 'treatment', 'doctor')
    serializer_class = InvoiceItemSerializer
    permission_classes = [IsAuthenticatedAndActive, HasBranchAccess]
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticatedAndActive() & (IsCashier() | IsReceptionist() | IsClinicManager() | IsSuperAdmin())]
        return super().get_permissions()
    
    def get_queryset(self):
        """Filter queryset based on invoice"""
        queryset = super().get_queryset()
        
        # Filter by invoice if specified
        invoice_id = self.request.query_params.get('invoice_id')
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)
        
        # Filter by doctor for doctors
        if self.request.user.role == 'doctor':
            queryset = queryset.filter(doctor__user=self.request.user)
        
        return queryset


class DiscountPolicyViewSet(viewsets.ModelViewSet):
    """ViewSet for DiscountPolicy CRUD operations"""
    
    queryset = DiscountPolicy.objects.all()
    serializer_class = DiscountPolicySerializer
    permission_classes = [IsAuthenticatedAndActive, HasBranchAccess]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'applicable_to', 'requires_approval']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticatedAndActive() & (IsClinicManager() | IsSuperAdmin())]
        return super().get_permissions()
    
    @action(detail=False, methods=['get'])
    def applicable(self, request):
        """Get applicable discounts for current context"""
        patient_id = request.query_params.get('patient_id')
        amount = request.query_params.get('amount', 0)
        
        if not patient_id:
            # FIXED: Use proper Response syntax
            return Response(
                data={'error': 'patient_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Patient is now imported, so this will work
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            return Response(
                data={'error': 'Patient not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get applicable discounts
        today = timezone.now().date()
        discounts = DiscountPolicy.objects.filter(
            is_active=True,
            valid_from__lte=today,
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=today)
        )
        
        # Filter by applicable_to
        applicable_discounts = []
        for discount in discounts:
            can_apply, message = discount.can_apply(patient, request.user)
            if can_apply and (not discount.minimum_amount or Decimal(amount) >= discount.minimum_amount):
                applicable_discounts.append(discount)
        
        serializer = self.get_serializer(applicable_discounts, many=True)
        return Response(serializer.data)
        
        # Filter by applicable_to
        applicable_discounts = []
        for discount in discounts:
            can_apply, message = discount.can_apply(patient, request.user)
            if can_apply and (not discount.minimum_amount or Decimal(amount) >= discount.minimum_amount):
                applicable_discounts.append(discount)
        
        serializer = self.get_serializer(applicable_discounts, many=True)
        return Response(serializer.data)
    
    
    @action(detail=True, methods=['post'])
    def add_late_fee(self, request, pk=None):
        """Add late fee to overdue invoice"""
        invoice = self.get_object()
        
        if invoice.status != 'OVERDUE':
            return Response({'error': 'Can only add late fee to overdue invoices'}, 
                           status=status.HTTP_400_BAD_REQUEST)  # Fixed line 289
        
        fee_amount = request.data.get('fee_amount')
        reason = request.data.get('reason', '')
        
        if not fee_amount or Decimal(fee_amount) <= 0:  # Decimal is now imported
            return Response({'error': 'Invalid fee amount'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        try:
            invoice.add_late_fee(
                fee_amount=Decimal(fee_amount),
                reason=reason,
                user=request.user
            )
            
            return Response({
                'message': 'Late fee added successfully',
                'invoice': InvoiceSerializer(invoice, context={'request': request}).data
            }, status=status.HTTP_200_OK)
        
        except ValueError as e:
            return Response({'error': str(e)}, 
                           status=status.HTTP_400_BAD_REQUEST)


class AppliedDiscountViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for AppliedDiscount read-only operations"""
    
    queryset = AppliedDiscount.objects.select_related('invoice', 'discount_policy', 'approved_by')
    serializer_class = AppliedDiscountSerializer
    permission_classes = [IsAuthenticatedAndActive, HasBranchAccess]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['invoice', 'discount_policy', 'is_reversed']