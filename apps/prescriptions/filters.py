# apps/prescriptions/filters.py


import django_filters
from django.db import models
from django_filters import rest_framework as filters
from django.db.models import Q
from datetime import date, timedelta

from .models import Prescription, Medication, PrescriptionTemplate


class PrescriptionFilter(filters.FilterSet):
    """Filter for prescriptions"""
    
    search = filters.CharFilter(method='filter_search')
    patient = filters.NumberFilter(field_name='patient_id')
    doctor = filters.NumberFilter(field_name='doctor_id')
    status = filters.CharFilter(field_name='status')
    prescription_type = filters.CharFilter(field_name='prescription_type')
    is_refillable = filters.BooleanFilter(field_name='is_refillable')
    is_valid = filters.BooleanFilter(method='filter_valid')
    start_date = filters.DateFilter(field_name='issue_date', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='issue_date', lookup_expr='lte')
    medication = filters.NumberFilter(method='filter_by_medication')
    needs_dispensing = filters.BooleanFilter(method='filter_needs_dispensing')
    
    class Meta:
        model = Prescription
        fields = [
            'patient', 'doctor', 'status', 'prescription_type',
            'is_refillable', 'start_date', 'end_date'
        ]
    
    def filter_search(self, queryset, name, value):
        """Search by prescription ID, patient name, or doctor name"""
        return queryset.filter(
            Q(prescription_id__icontains=value) |
            Q(patient__user__full_name__icontains=value) |
            Q(patient__patient_id__icontains=value) |
            Q(doctor__user__full_name__icontains=value) |
            Q(doctor__doctor_id__icontains=value)
        )
    
    def filter_valid(self, queryset, name, value):
        """Filter by prescription validity"""
        from django.utils import timezone
        
        if value:
            return queryset.filter(
                status__in=['ISSUED', 'DISPENSED'],
                valid_until__gte=timezone.now().date()
            )
        else:
            return queryset.filter(
                Q(status__in=['CANCELLED', 'EXPIRED']) |
                Q(valid_until__lt=timezone.now().date())
            )
    
    def filter_by_medication(self, queryset, name, value):
        """Filter prescriptions containing specific medication"""
        return queryset.filter(items__medication_id=value).distinct()
    
    def filter_needs_dispensing(self, queryset, name, value):
        """Filter prescriptions that need dispensing"""
        if value:
            # Prescriptions that are issued but not fully dispensed
            return queryset.filter(
                status='ISSUED',
                items__is_dispensed=False
            ).distinct()
        return queryset


class MedicationFilter(filters.FilterSet):
    """Filter for medications"""
    
    search = filters.CharFilter(method='filter_search')
    category = filters.CharFilter(field_name='category')
    form = filters.CharFilter(field_name='form')
    requires_prescription = filters.BooleanFilter(field_name='requires_prescription')
    is_active = filters.BooleanFilter(field_name='is_active')
    in_stock = filters.BooleanFilter(field_name='in_stock')
    stock_status = filters.CharFilter(method='filter_stock_status')
    low_stock = filters.BooleanFilter(method='filter_low_stock')
    expired = filters.BooleanFilter(method='filter_expired')
    min_price = filters.NumberFilter(field_name='unit_price', lookup_expr='gte')
    max_price = filters.NumberFilter(field_name='unit_price', lookup_expr='lte')
    
    class Meta:
        model = Medication
        fields = [
            'category', 'form', 'requires_prescription',
            'is_active', 'in_stock', 'min_price', 'max_price'
        ]
    
    def filter_search(self, queryset, name, value):
        """Search by medicine name, generic name, or brand"""
        return queryset.filter(
            Q(name__icontains=value) |
            Q(generic_name__icontains=value) |
            Q(brand__icontains=value) |
            Q(medicine_id__icontains=value)
        )
    
    def filter_stock_status(self, queryset, name, value):
        """Filter by stock status"""
        if value == 'OUT_OF_STOCK':
            return queryset.filter(current_stock=0)
        elif value == 'LOW_STOCK':
            return queryset.filter(
                current_stock__gt=0,
                current_stock__lte=models.F('min_stock_level')
            )
        elif value == 'IN_STOCK':
            return queryset.filter(
                current_stock__gt=models.F('min_stock_level')
            )
        return queryset
    
    def filter_low_stock(self, queryset, name, value):
        """Filter medications with low stock"""
        if value:
            return queryset.filter(
                current_stock__gt=0,
                current_stock__lte=models.F('min_stock_level')
            )
        return queryset
    
    def filter_expired(self, queryset, name, value):
        """Filter expired medications"""
        from django.utils import timezone
        
        if value:
            return queryset.filter(expiry_date__lt=timezone.now().date())
        else:
            return queryset.filter(
                Q(expiry_date__gte=timezone.now().date()) |
                Q(expiry_date__isnull=True)
            )


class PrescriptionTemplateFilter(filters.FilterSet):
    """Filter for prescription templates"""
    
    search = filters.CharFilter(method='filter_search')
    specialization = filters.CharFilter(field_name='specialization')
    is_active = filters.BooleanFilter(field_name='is_active')
    
    class Meta:
        model = PrescriptionTemplate
        fields = ['specialization', 'is_active']
    
    def filter_search(self, queryset, name, value):
        """Search by template name or diagnoses"""
        return queryset.filter(
            Q(name__icontains=value) |
            Q(diagnoses__icontains=value) |
            Q(template_id__icontains=value)
        )