# apps/doctors/filters.py

import django_filters
from django_filters import rest_framework as filters
from django.db.models import Q
from datetime import date

from .models import Doctor, DoctorSchedule, DoctorLeave


class DoctorFilter(filters.FilterSet):
    """Filter for doctors"""
    
    search = filters.CharFilter(method='filter_search')
    specialization = filters.CharFilter(field_name='specialization')
    branch = filters.NumberFilter(field_name='primary_branch_id')
    is_active = filters.BooleanFilter(field_name='is_active')
    is_accepting_new_patients = filters.BooleanFilter(field_name='is_accepting_new_patients')
    license_valid = filters.BooleanFilter(method='filter_license_valid')
    min_experience = filters.NumberFilter(field_name='years_of_experience', lookup_expr='gte')
    max_experience = filters.NumberFilter(field_name='years_of_experience', lookup_expr='lte')
    min_fee = filters.NumberFilter(field_name='consultation_fee', lookup_expr='gte')
    max_fee = filters.NumberFilter(field_name='consultation_fee', lookup_expr='lte')
    available_on = filters.DateFilter(method='filter_available_on')
    language = filters.CharFilter(method='filter_language')
    
    class Meta:
        model = Doctor
        fields = [
            'specialization', 'branch', 'is_active', 
            'is_accepting_new_patients', 'min_experience', 'max_experience',
            'min_fee', 'max_fee'
        ]
    
    def filter_search(self, queryset, name, value):
        """Search by name, email, doctor_id, or license number"""
        return queryset.filter(
            Q(user__full_name__icontains=value) |
            Q(user__email__icontains=value) |
            Q(doctor_id__icontains=value) |
            Q(license_number__icontains=value) |
            Q(registration_number__icontains=value)
        )
    
    def filter_license_valid(self, queryset, name, value):
        """Filter by license validity"""
        from django.utils import timezone
        
        if value:
            return queryset.filter(license_expiry__gte=timezone.now().date())
        else:
            return queryset.filter(license_expiry__lt=timezone.now().date())
    
    def filter_available_on(self, queryset, name, value):
        """Filter doctors available on a specific date"""
        # Get doctors with schedule on that day's weekday
        weekday = value.weekday()
        
        # Get doctors not on leave on that date
        doctors_on_leave = DoctorLeave.objects.filter(
            start_date__lte=value,
            end_date__gte=value,
            status='APPROVED'
        ).values_list('doctor_id', flat=True)
        
        # Get doctors with schedule on that weekday
        doctors_with_schedule = DoctorSchedule.objects.filter(
            day_of_week=weekday,
            is_active=True
        ).values_list('doctor_id', flat=True)
        
        return queryset.filter(
            id__in=doctors_with_schedule
        ).exclude(
            id__in=doctors_on_leave
        ).filter(
            is_active=True,
            is_accepting_new_patients=True
        )
    
    def filter_language(self, queryset, name, value):
        """Filter by language spoken"""
        return queryset.filter(languages_spoken__icontains=value)


class DoctorScheduleFilter(filters.FilterSet):
    """Filter for doctor schedules"""
    
    doctor = filters.NumberFilter(field_name='doctor_id')
    branch = filters.NumberFilter(field_name='branch_id')
    day_of_week = filters.NumberFilter(field_name='day_of_week')
    is_active = filters.BooleanFilter(field_name='is_active')
    date = filters.DateFilter(method='filter_by_date')
    
    class Meta:
        model = DoctorSchedule
        fields = ['doctor', 'branch', 'day_of_week', 'is_active']
    
    def filter_by_date(self, queryset, name, value):
        """Filter schedules for a specific date"""
        weekday = value.weekday()
        return queryset.filter(day_of_week=weekday, is_active=True)


class DoctorLeaveFilter(filters.FilterSet):
    """Filter for doctor leaves"""
    
    doctor = filters.NumberFilter(field_name='doctor_id')
    leave_type = filters.CharFilter(field_name='leave_type')
    status = filters.CharFilter(field_name='status')
    start_date = filters.DateFilter(field_name='start_date', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='end_date', lookup_expr='lte')
    is_current = filters.BooleanFilter(method='filter_current')
    upcoming = filters.BooleanFilter(method='filter_upcoming')
    
    class Meta:
        model = DoctorLeave
        fields = ['doctor', 'leave_type', 'status', 'start_date', 'end_date']
    
    def filter_current(self, queryset, name, value):
        """Filter current leaves (today is within leave period)"""
        today = date.today()
        if value:
            return queryset.filter(start_date__lte=today, end_date__gte=today)
        else:
            return queryset.exclude(start_date__lte=today, end_date__gte=today)
    
    def filter_upcoming(self, queryset, name, value):
        """Filter upcoming leaves (start date is in future)"""
        today = date.today()
        if value:
            return queryset.filter(start_date__gt=today)
        else:
            return queryset.exclude(start_date__gt=today)