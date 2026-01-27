# apps/eod/views.py

from rest_framework import viewsets, mixins, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Sum, Count
from datetime import datetime, timedelta, date
from decimal import Decimal

from .models import EodLock, DailySummary, CashReconciliation, EodException
from .serializers import (
    EodLockSerializer, EodLockCreateSerializer, EodLockReviewSerializer,
    EodLockReverseSerializer, DailySummarySerializer, DailySummaryCreateSerializer,
    CashReconciliationSerializer, CashReconciliationVerifySerializer,
    EodExceptionSerializer, EodExceptionAssignSerializer, EodExceptionResolveSerializer,
    EodReportSerializer, CashPositionSerializer, DateLockStatusSerializer
)
from .services import EodService, CashManagementService
from core.permissions import (
    IsSuperAdmin, IsClinicManager, IsCashier, IsReceptionist,
    HasBranchAccess, CanPerformEOD, CanApproveEOD, CanReverseEOD
)
from ..audit.services import log_action


class EodLockViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing EOD Locks
    
    Permissions:
    - Prepare: Cashier, Clinic Manager, Super Admin
    - Review: Clinic Manager, Super Admin
    - Lock: Clinic Manager, Super Admin
    - Reverse: Super Admin only
    """
    queryset = EodLock.objects.all()
    permission_classes = [permissions.IsAuthenticated & HasBranchAccess]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EodLockCreateSerializer
        elif self.action == 'review':
            return EodLockReviewSerializer
        elif self.action == 'reverse':
            return EodLockReverseSerializer
        elif self.action == 'lock':
            return None  # No data needed for lock
        return EodLockSerializer
    
    def get_permissions(self):
        """
        Custom permissions for different actions
        """
        if self.action in ['create', 'prepare']:
            permission_classes = [permissions.IsAuthenticated & HasBranchAccess & CanPerformEOD]
        elif self.action in ['review', 'lock']:
            permission_classes = [permissions.IsAuthenticated & HasBranchAccess & CanApproveEOD]
        elif self.action == 'reverse':
            permission_classes = [permissions.IsAuthenticated & HasBranchAccess & CanReverseEOD]
        elif self.action in ['destroy', 'update', 'partial_update']:
            permission_classes = [permissions.IsAuthenticated & HasBranchAccess & IsSuperAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated & HasBranchAccess]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter queryset based on user role and branch
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Get branch from request or user
        branch_id = getattr(self.request, 'branch_id', None)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(lock_date__range=[start, end])
            except ValueError:
                pass
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Order by most recent first
        queryset = queryset.order_by('-lock_date', '-created_at')
        
        return queryset
    
    def perform_create(self, serializer):
        """Create EOD with audit logging"""
        user = self.request.user
        branch_id = getattr(self.request, 'branch_id', None)
        
        # Save the EOD
        eod_lock = serializer.save(
            prepared_by=user,
            created_by=user
        )
        
        # Log the action
        log_action(
            user=user,
            branch=eod_lock.branch,
            instance=eod_lock,
            action='EOD_PREPARED',
            device_id=self.request.META.get('HTTP_X_DEVICE_ID'),
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
    
    @action(detail=False, methods=['post'])
    def prepare(self, request):
        """
        Prepare a new EOD for a branch
        """
        serializer = EodLockCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            try:
                # Use service to prepare EOD
                eod = EodService.prepare_eod(
                    branch=serializer.validated_data['branch'],
                    prepared_by=request.user,
                    lock_date=serializer.validated_data.get('lock_date')
                )
                
                # Set notes if provided
                if 'notes' in serializer.validated_data:
                    eod.notes = serializer.validated_data['notes']
                    eod.save()
                
                # Log action
                log_action(
                    user=request.user,
                    branch=eod.branch,
                    instance=eod,
                    action='EOD_PREPARED',
                    device_id=request.META.get('HTTP_X_DEVICE_ID'),
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                return Response(
                    EodLockSerializer(eod, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
                
            except ValueError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """
        Review an EOD
        """
        eod = self.get_object()
        
        # Check if EOD can be reviewed
        if eod.status != EodLock.PREPARED:
            return Response(
                {'error': 'Only prepared EODs can be reviewed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = EodLockReviewSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            # Update EOD with review data
            eod.status = EodLock.REVIEWED
            eod.reviewed_by = request.user
            eod.reviewed_at = timezone.now()
            eod.review_notes = serializer.validated_data.get('review_notes', '')
            
            # Verify cash if provided
            actual_cash = serializer.validated_data.get('actual_cash')
            if actual_cash is not None:
                eod.verify_cash(actual_cash, request.user)
            
            if serializer.validated_data.get('cash_verified'):
                eod.cash_verified = True
                eod.cash_verified_by = request.user
                eod.cash_verified_at = timezone.now()
            
            eod.save()
            
            # Log action
            log_action(
                user=request.user,
                branch=eod.branch,
                instance=eod,
                action='EOD_REVIEWED',
                device_id=request.META.get('HTTP_X_DEVICE_ID'),
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            return Response(
                EodLockSerializer(eod, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """
        Lock an EOD (prevent further modifications)
        """
        eod = self.get_object()
        
        # Check if EOD can be locked
        if eod.status != EodLock.REVIEWED:
            return Response(
                {'error': 'Only reviewed EODs can be locked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if all verifications are complete
        if not (eod.cash_verified and eod.digital_payments_verified and eod.invoices_verified):
            return Response(
                {'error': 'All verifications must be completed before locking'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Lock the EOD
            eod.lock(request.user)
            
            # Log action
            log_action(
                user=request.user,
                branch=eod.branch,
                instance=eod,
                action='EOD_LOCKED',
                device_id=request.META.get('HTTP_X_DEVICE_ID'),
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            return Response(
                EodLockSerializer(eod, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        """
        Reverse a locked EOD (requires super admin)
        """
        eod = self.get_object()
        
        serializer = EodLockReverseSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            try:
                # Reverse the EOD
                eod.reverse(
                    reversed_by=request.user,
                    reason=serializer.validated_data['reversal_reason']
                )
                
                # Log action
                log_action(
                    user=request.user,
                    branch=eod.branch,
                    instance=eod,
                    action='EOD_REVERSED',
                    device_id=request.META.get('HTTP_X_DEVICE_ID'),
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                return Response(
                    EodLockSerializer(eod, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )
                
            except ValueError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        """
        Recalculate EOD totals
        """
        eod = self.get_object()
        
        # Check if EOD is locked
        if eod.status == EodLock.LOCKED:
            return Response(
                {'error': 'Cannot recalculate locked EOD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Recalculate totals
        eod.calculate_totals()
        
        # Log action
        log_action(
            user=request.user,
            branch=eod.branch,
            instance=eod,
            action='EOD_RECALCULATED',
            device_id=request.META.get('HTTP_X_DEVICE_ID'),
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response(
            EodLockSerializer(eod, context={'request': request}).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def status_summary(self, request):
        """
        Get EOD status summary for a branch
        """
        from .utils import EodValidator
        
        branch_id = getattr(request, 'branch_id', None)
        if not branch_id:
            return Response(
                {'error': 'Branch not specified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from ..clinics.models import Branch
        try:
            branch = Branch.objects.get(id=branch_id)
        except Branch.DoesNotExist:
            return Response(
                {'error': 'Branch not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        summary = EodValidator.get_eod_status_summary(branch)
        
        return Response(summary, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def pending_locks(self, request):
        """
        Get list of dates pending EOD lock
        """
        branch_id = getattr(request, 'branch_id', None)
        if not branch_id:
            return Response(
                {'error': 'Branch not specified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from ..clinics.models import Branch
        try:
            branch = Branch.objects.get(id=branch_id)
        except Branch.DoesNotExist:
            return Response(
                {'error': 'Branch not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        pending_dates = EodService.get_unlocked_dates(branch)
        
        return Response({
            'branch': branch.name,
            'pending_dates': pending_dates,
            'count': len(pending_dates)
        }, status=status.HTTP_200_OK)



    @action(detail=False, methods=['get'])
    def detailed_stats(self, request):
        """Get detailed OTP statistics"""
        from django.db.models import Count, Q, F, ExpressionWrapper, FloatField
        from django.db.models.functions import TruncDay
        
        queryset = self.get_queryset()
        
        # Time-based analysis
        daily_stats = queryset.annotate(
            day=TruncDay('created_at')
        ).values('day').annotate(
            total=Count('id'),
            verified=Count('id', filter=Q(status='VERIFIED')),
            failed=Count('id', filter=Q(status='FAILED')),
            success_rate=ExpressionWrapper(
                Count('id', filter=Q(status='VERIFIED')) * 100.0 / Count('id'),
                output_field=FloatField()
            )
        ).order_by('-day')[:30]
        
        # Channel performance
        channel_performance = queryset.values('channel').annotate(
            total=Count('id'),
            delivered=Count('id', filter=Q(status='DELIVERED')),
            verified=Count('id', filter=Q(status='VERIFIED')),
            avg_delivery_time=ExpressionWrapper(
                F('delivered_at') - F('sent_at'),
                output_field=FloatField()
            )
        )
        
        # Geographic analysis (if IP data available)
        geo_stats = queryset.exclude(ip_address__isnull=True).values(
            'ip_address'
        ).annotate(
            count=Count('id'),
            failed=Count('id', filter=Q(status='FAILED'))
        ).order_by('-count')[:10]
        
        return Response({
            'daily_stats': list(daily_stats),
            'channel_performance': list(channel_performance),
            'suspicious_ips': list(geo_stats),
            'time_period': {
                'start': queryset.first().created_at if queryset.exists() else None,
                'end': queryset.last().created_at if queryset.exists() else None,
                'total_days': queryset.dates('created_at', 'day').count()
            }
        })

class DailySummaryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Daily Summaries
    """
    queryset = DailySummary.objects.all()
    serializer_class = DailySummarySerializer
    permission_classes = [permissions.IsAuthenticated & HasBranchAccess]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return DailySummaryCreateSerializer
        return DailySummarySerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Filter by branch
        branch_id = getattr(self.request, 'branch_id', None)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(summary_date__range=[start, end])
            except ValueError:
                pass
        
        # Filter by summary type
        summary_type = self.request.query_params.get('summary_type')
        if summary_type:
            queryset = queryset.filter(summary_type=summary_type)
        
        # Order by most recent first
        queryset = queryset.order_by('-summary_date', '-period_end')
        
        return queryset
    
    def perform_create(self, serializer):
        """Create daily summary with audit logging"""
        user = self.request.user
        
        # Save the summary
        summary = serializer.save(
            generated_by=user,
            created_by=user
        )
        
        # Log the action
        log_action(
            user=user,
            branch=summary.branch,
            instance=summary,
            action='SUMMARY_GENERATED',
            device_id=self.request.META.get('HTTP_X_DEVICE_ID'),
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Generate a new daily summary
        """
        serializer = DailySummaryCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            summary = serializer.save()
            
            return Response(
                DailySummarySerializer(summary, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """
        Get today's summaries for the branch
        """
        branch_id = getattr(request, 'branch_id', None)
        if not branch_id:
            return Response(
                {'error': 'Branch not specified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        today = timezone.now().date()
        summaries = DailySummary.objects.filter(
            branch_id=branch_id,
            summary_date=today
        ).order_by('-period_end')
        
        serializer = self.get_serializer(summaries, many=True)
        return Response(serializer.data)


class CashReconciliationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Cash Reconciliations
    """
    queryset = CashReconciliation.objects.all()
    serializer_class = CashReconciliationSerializer
    permission_classes = [permissions.IsAuthenticated & HasBranchAccess]
    
    def get_permissions(self):
        """
        Custom permissions for cash reconciliations
        """
        if self.action in ['create', 'handover']:
            # Cashiers and above can create reconciliations
            permission_classes = [permissions.IsAuthenticated & HasBranchAccess & 
                                (IsCashier | IsClinicManager | IsSuperAdmin)]
        elif self.action in ['verify']:
            # Only managers can verify
            permission_classes = [permissions.IsAuthenticated & HasBranchAccess & 
                                (IsClinicManager | IsSuperAdmin)]
        else:
            permission_classes = [permissions.IsAuthenticated & HasBranchAccess]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch
        branch_id = getattr(self.request, 'branch_id', None)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Filter by date
        date_param = self.request.query_params.get('date')
        if date_param:
            try:
                date = datetime.strptime(date_param, '%Y-%m-%d').date()
                queryset = queryset.filter(reconciliation_date=date)
            except ValueError:
                pass
        
        # Filter by reconciliation type
        recon_type = self.request.query_params.get('type')
        if recon_type:
            queryset = queryset.filter(reconciliation_type=recon_type)
        
        # Filter by cashier
        cashier_id = self.request.query_params.get('cashier_id')
        if cashier_id:
            queryset = queryset.filter(cashier_id=cashier_id)
        
        # Filter by verification status
        verified = self.request.query_params.get('verified')
        if verified is not None:
            queryset = queryset.filter(verified=verified.lower() == 'true')
        
        # Order by most recent first
        queryset = queryset.order_by('-reconciliation_date', '-created_at')
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def handover(self, request):
        """
        Record cash handover between shifts
        """
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                reconciliation = CashManagementService.record_cash_handover(
                    branch=serializer.validated_data['branch'],
                    cashier=request.user,
                    counter=serializer.validated_data['counter'],
                    cash_amount=serializer.validated_data['declared_cash'],
                    reconciliation_type=serializer.validated_data['reconciliation_type'],
                    notes=serializer.validated_data.get('notes', '')
                )
                
                # Log action
                log_action(
                    user=request.user,
                    branch=reconciliation.branch,
                    instance=reconciliation,
                    action='CASH_HANDOVER_RECORDED',
                    device_id=request.META.get('HTTP_X_DEVICE_ID'),
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                return Response(
                    CashReconciliationSerializer(reconciliation, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
                
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Verify cash reconciliation
        """
        reconciliation = self.get_object()
        
        # Check if already verified
        if reconciliation.verified:
            return Response(
                {'error': 'Cash reconciliation already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = CashReconciliationVerifySerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            try:
                # Verify cash
                CashManagementService.verify_cash_handover(
                    reconciliation_id=reconciliation.id,
                    supervisor=request.user,
                    counted_cash=serializer.validated_data['counted_cash'],
                    denomination_breakdown=serializer.validated_data.get('denomination_breakdown'),
                    notes=serializer.validated_data.get('verification_notes', '')
                )
                
                # Log action
                log_action(
                    user=request.user,
                    branch=reconciliation.branch,
                    instance=reconciliation,
                    action='CASH_RECONCILIATION_VERIFIED',
                    device_id=request.META.get('HTTP_X_DEVICE_ID'),
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                return Response(
                    CashReconciliationSerializer(reconciliation, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )
                
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def todays_reconciliations(self, request):
        """
        Get today's cash reconciliations for the branch
        """
        branch_id = getattr(request, 'branch_id', None)
        if not branch_id:
            return Response(
                {'error': 'Branch not specified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        today = timezone.now().date()
        reconciliations = CashReconciliation.objects.filter(
            branch_id=branch_id,
            reconciliation_date=today
        ).order_by('-created_at')
        
        serializer = self.get_serializer(reconciliations, many=True)
        return Response(serializer.data)


class EodExceptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing EOD Exceptions
    """
    queryset = EodException.objects.all()
    serializer_class = EodExceptionSerializer
    permission_classes = [permissions.IsAuthenticated & HasBranchAccess]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by branch
        branch_id = getattr(self.request, 'branch_id', None)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(exception_date__range=[start, end])
            except ValueError:
                pass
        
        # Filter by exception type
        exception_type = self.request.query_params.get('exception_type')
        if exception_type:
            queryset = queryset.filter(exception_type=exception_type)
        
        # Filter by severity
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by assigned user
        assigned_to = self.request.query_params.get('assigned_to')
        if assigned_to:
            queryset = queryset.filter(assigned_to_id=assigned_to)
        
        # Filter by unresolved
        unresolved = self.request.query_params.get('unresolved')
        if unresolved and unresolved.lower() == 'true':
            queryset = queryset.filter(status__in=[EodException.OPEN, EodException.IN_PROGRESS])
        
        # Order by severity and date
        queryset = queryset.order_by(
            '-severity', '-exception_date', '-created_at'
        )
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """
        Assign exception to a user
        """
        exception = self.get_object()
        
        # Check if exception is already assigned/resolved
        if exception.status in [EodException.IN_PROGRESS, EodException.RESOLVED, EodException.CANCELLED]:
            return Response(
                {'error': f'Exception is already {exception.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = EodExceptionAssignSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            try:
                exception.assign(request.user)
                
                # Log action
                log_action(
                    user=request.user,
                    branch=exception.branch,
                    instance=exception,
                    action='EXCEPTION_ASSIGNED',
                    device_id=request.META.get('HTTP_X_DEVICE_ID'),
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                return Response(
                    EodExceptionSerializer(exception, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )
                
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """
        Resolve an exception
        """
        exception = self.get_object()
        
        # Check if exception can be resolved
        if exception.status in [EodException.RESOLVED, EodException.CANCELLED]:
            return Response(
                {'error': f'Exception is already {exception.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = EodExceptionResolveSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            try:
                exception.resolve(
                    resolved_by=request.user,
                    resolution_notes=serializer.validated_data['resolution_notes'],
                    resolution_action=serializer.validated_data.get('resolution_action', '')
                )
                
                # Log action
                log_action(
                    user=request.user,
                    branch=exception.branch,
                    instance=exception,
                    action='EXCEPTION_RESOLVED',
                    device_id=request.META.get('HTTP_X_DEVICE_ID'),
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                return Response(
                    EodExceptionSerializer(exception, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )
                
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """
        Get exception dashboard statistics
        """
        branch_id = getattr(request, 'branch_id', None)
        if not branch_id:
            return Response(
                {'error': 'Branch not specified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get date range (last 30 days)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        # Get exceptions for the date range
        exceptions = EodException.objects.filter(
            branch_id=branch_id,
            exception_date__range=[start_date, end_date]
        )
        
        # Calculate statistics
        total_count = exceptions.count()
        
        by_status = exceptions.values('status').annotate(
            count=Count('id'),
            total_amount=Sum('amount_involved')
        )
        
        by_type = exceptions.values('exception_type').annotate(
            count=Count('id')
        )
        
        by_severity = exceptions.values('severity').annotate(
            count=Count('id')
        )
        
        # Overdue exceptions
        overdue = exceptions.filter(
            status__in=[EodException.OPEN, EodException.IN_PROGRESS],
            exception_date__lt=end_date - timedelta(days=7)
        ).count()
        
        return Response({
            'date_range': {
                'start_date': start_date,
                'end_date': end_date
            },
            'statistics': {
                'total_count': total_count,
                'overdue_count': overdue,
                'by_status': list(by_status),
                'by_type': list(by_type),
                'by_severity': list(by_severity)
            }
        }, status=status.HTTP_200_OK)


# ===========================================
# API VIEWS FOR SPECIFIC OPERATIONS
# ===========================================

class CheckDateLockStatusAPIView(APIView):
    """
    API to check if a date is locked for a branch
    """
    permission_classes = [permissions.IsAuthenticated & HasBranchAccess]
    
    def post(self, request):
        serializer = DateLockStatusSerializer(data=request.data)
        
        if serializer.is_valid():
            branch_id = getattr(request, 'branch_id', None)
            if not branch_id:
                return Response(
                    {'error': 'Branch not specified'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from ..clinics.models import Branch
            try:
                branch = Branch.objects.get(id=branch_id)
            except Branch.DoesNotExist:
                return Response(
                    {'error': 'Branch not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            check_date = serializer.validated_data['check_date']
            transaction_type = serializer.validated_data['transaction_type']
            
            is_locked = EodService.check_date_locked(branch, check_date)
            
            # Get EOD lock details if exists
            eod_details = None
            try:
                eod_lock = EodLock.objects.get(
                    branch=branch,
                    lock_date=check_date,
                    status=EodLock.LOCKED
                )
                eod_details = {
                    'lock_number': eod_lock.lock_number,
                    'locked_by': str(eod_lock.locked_by),
                    'locked_at': eod_lock.locked_at
                }
            except EodLock.DoesNotExist:
                pass
            
            response_data = {
                'branch': branch.name,
                'check_date': check_date,
                'transaction_type': transaction_type,
                'is_locked': is_locked,
                'eod_lock': eod_details,
                'message': 'Date is locked' if is_locked else 'Date is open for transactions'
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GetCashPositionAPIView(APIView):
    """
    API to get current cash position for a branch
    """
    permission_classes = [permissions.IsAuthenticated & HasBranchAccess & 
                         (IsCashier | IsClinicManager | IsSuperAdmin)]
    
    def post(self, request):
        serializer = CashPositionSerializer(data=request.data)
        
        if serializer.is_valid():
            branch_id = getattr(request, 'branch_id', None)
            if not branch_id:
                return Response(
                    {'error': 'Branch not specified'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from ..clinics.models import Branch
            try:
                branch = Branch.objects.get(id=branch_id)
            except Branch.DoesNotExist:
                return Response(
                    {'error': 'Branch not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            as_of_date = serializer.validated_data['as_of_date']
            include_details = serializer.validated_data['include_details']
            
            cash_position = CashManagementService.get_cash_position(branch, as_of_date)
            
            return Response(cash_position, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GenerateEodReportAPIView(APIView):
    """
    API to generate EOD reports
    """
    permission_classes = [permissions.IsAuthenticated & HasBranchAccess & 
                         (IsClinicManager | IsSuperAdmin)]
    
    def post(self, request):
        serializer = EodReportSerializer(data=request.data)
        
        if serializer.is_valid():
            branch_id = getattr(request, 'branch_id', None)
            if not branch_id:
                return Response(
                    {'error': 'Branch not specified'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from ..clinics.models import Branch
            try:
                branch = Branch.objects.get(id=branch_id)
            except Branch.DoesNotExist:
                return Response(
                    {'error': 'Branch not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            start_date = serializer.validated_data['start_date']
            end_date = serializer.validated_data['end_date']
            report_type = serializer.validated_data['report_type']
            include_summaries = serializer.validated_data['include_summaries']
            include_exceptions = serializer.validated_data['include_exceptions']
            format_type = serializer.validated_data['format']
            
            # Get EOD locks in date range
            eod_locks = EodLock.objects.filter(
                branch=branch,
                lock_date__range=[start_date, end_date],
                status=EodLock.LOCKED
            ).order_by('lock_date')
            
            # Build report data
            report_data = {
                'branch': branch.name,
                'report_period': {
                    'start_date': start_date,
                    'end_date': end_date,
                    'report_type': report_type
                },
                'eod_locks': [],
                'summary': {
                    'total_days': (end_date - start_date).days + 1,
                    'locked_days': eod_locks.count(),
                    'total_invoice_amount': Decimal('0'),
                    'total_payment_amount': Decimal('0'),
                    'total_cash_collected': Decimal('0'),
                    'total_digital_collected': Decimal('0'),
                    'total_refund_amount': Decimal('0')
                }
            }
            
            # Add EOD lock details
            eod_serializer = EodLockSerializer(
                eod_locks, many=True, context={'request': request}
            )
            report_data['eod_locks'] = eod_serializer.data
            
            # Calculate totals
            for eod in eod_locks:
                report_data['summary']['total_invoice_amount'] += eod.total_invoice_amount
                report_data['summary']['total_payment_amount'] += eod.total_payment_amount
                report_data['summary']['total_cash_collected'] += eod.total_cash_collected
                report_data['summary']['total_digital_collected'] += (
                    eod.card_collections + eod.upi_collections + 
                    eod.bank_transfers + eod.insurance_collections + 
                    eod.cheque_collections
                )
                report_data['summary']['total_refund_amount'] += eod.total_refund_amount
            
            # Add daily summaries if requested
            if include_summaries:
                summaries = DailySummary.objects.filter(
                    branch=branch,
                    summary_date__range=[start_date, end_date]
                ).order_by('summary_date', 'period_start')
                
                summary_serializer = DailySummarySerializer(
                    summaries, many=True, context={'request': request}
                )
                report_data['daily_summaries'] = summary_serializer.data
            
            # Add exceptions if requested
            if include_exceptions:
                exceptions = EodException.objects.filter(
                    branch=branch,
                    exception_date__range=[start_date, end_date]
                ).order_by('exception_date', 'severity')
                
                exception_serializer = EodExceptionSerializer(
                    exceptions, many=True, context={'request': request}
                )
                report_data['exceptions'] = exception_serializer.data
            
            # Format response based on requested format
            if format_type == 'json':
                return Response(report_data, status=status.HTTP_200_OK)
            else:
                # TODO: Implement CSV, PDF, Excel exports
                return Response({
                    'message': f'{format_type.upper()} export not yet implemented',
                    'data': report_data
                }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ValidateTransactionDateAPIView(APIView):
    """
    API to validate if a transaction can be posted for a date
    """
    permission_classes = [permissions.IsAuthenticated & HasBranchAccess]
    
    def post(self, request):
        data = request.data
        
        branch_id = getattr(request, 'branch_id', None)
        if not branch_id:
            return Response(
                {'error': 'Branch not specified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        transaction_date = data.get('transaction_date')
        transaction_type = data.get('transaction_type')
        amount = data.get('amount', 0)
        
        if not transaction_date or not transaction_type:
            return Response(
                {'error': 'transaction_date and transaction_type are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from ..clinics.models import Branch
        try:
            branch = Branch.objects.get(id=branch_id)
            trans_date = datetime.strptime(transaction_date, '%Y-%m-%d').date()
        except (Branch.DoesNotExist, ValueError):
            return Response(
                {'error': 'Invalid branch or date format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if date is locked
        is_locked = EodService.check_date_locked(branch, trans_date)
        
        if is_locked:
            return Response({
                'is_valid': False,
                'error': f'Date {trans_date} is locked. Cannot post {transaction_type}.',
                'transaction_date': trans_date,
                'transaction_type': transaction_type,
                'amount': amount
            }, status=status.HTTP_200_OK)
        
        # Check if date is too far in past
        max_allowed_days = 30
        if (timezone.now().date() - trans_date).days > max_allowed_days:
            return Response({
                'is_valid': False,
                'error': f'Cannot post transactions older than {max_allowed_days} days',
                'transaction_date': trans_date,
                'transaction_type': transaction_type,
                'amount': amount
            }, status=status.HTTP_200_OK)
        
        return Response({
            'is_valid': True,
            'message': f'Date {trans_date} is open for {transaction_type}',
            'transaction_date': trans_date,
            'transaction_type': transaction_type,
            'amount': amount
        }, status=status.HTTP_200_OK)