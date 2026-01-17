# apps/reports/services.py
import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import connection
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from django.conf import settings

from .models import ReportTemplate, GeneratedReport, ReportData
from apps.billing.models import Invoice, Payment
from apps.payments.models import Payment as PaymentModel
from apps.visits.models import Visit, Appointment
from apps.patients.models import Patient
from apps.doctors.models import Doctor
from apps.treatments.models import Treatment, TreatmentPlan
from apps.clinics.models import Branch


class ReportService:
    """Service for generating and managing reports"""
    
    @staticmethod
    def generate_report_from_template(template, parameters, start_date, end_date, generated_by):
        """
        Generate a report from a template
        """
        # Create the report record
        report = GeneratedReport.objects.create(
            template=template,
            parameters=parameters,
            start_date=start_date,
            end_date=end_date,
            generated_by=generated_by,
            branch=generated_by.branch if hasattr(generated_by, 'branch') else None,
            created_by=generated_by,
            status=GeneratedReport.PROCESSING
        )
        
        try:
            start_time = timezone.now()
            
            # Generate data based on template type
            if template.report_type == ReportTemplate.FINANCIAL:
                data = ReportService.generate_financial_report(
                    template, parameters, start_date, end_date, generated_by.branch
                )
            elif template.report_type == ReportTemplate.CLINICAL:
                data = ReportService.generate_clinical_report(
                    template, parameters, start_date, end_date, generated_by.branch
                )
            elif template.report_type == ReportTemplate.OPERATIONAL:
                data = ReportService.generate_operational_report(
                    template, parameters, start_date, end_date, generated_by.branch
                )
            else:
                # Use custom SQL query
                data = ReportService.execute_custom_query(
                    template.query_sql, parameters, start_date, end_date
                )
            
            # Save data
            ReportData.objects.create(
                generated_report=report,
                data_json=data,
                summary=ReportService.generate_summary(data, template)
            )
            
            # Save file (simplified - in production, generate actual files)
            file_path = f"reports/{report.report_number}.json"
            file_size = len(json.dumps(data).encode('utf-8'))
            
            duration = timezone.now() - start_time
            
            # Mark as completed
            report.mark_completed(
                file_path=file_path,
                file_size=file_size,
                duration=duration,
                row_count=len(data.get('rows', []))
            )
            
            return report
            
        except Exception as e:
            report.mark_failed(str(e))
            raise
    
    @staticmethod
    def generate_financial_report(template, parameters, start_date, end_date, branch):
        """Generate financial reports"""
        report_type = parameters.get('report_type', 'revenue_summary')
        
        if report_type == 'revenue_summary':
            return ReportService._generate_revenue_summary(start_date, end_date, branch)
        elif report_type == 'collection_efficiency':
            return ReportService._generate_collection_efficiency(start_date, end_date, branch)
        elif report_type == 'outstanding_summary':
            return ReportService._generate_outstanding_summary(start_date, end_date, branch)
        elif report_type == 'payment_method_analysis':
            return ReportService._generate_payment_method_analysis(start_date, end_date, branch)
        elif report_type == 'doctor_commission':
            return ReportService._generate_doctor_commission(start_date, end_date, branch)
        else:
            return {}
    
    @staticmethod
    def _generate_revenue_summary(start_date, end_date, branch):
        """Generate revenue summary report"""
        # Daily revenue
        daily_revenue = Invoice.objects.filter(
            branch=branch,
            invoice_date__range=[start_date, end_date],
            status__in=['PAID', 'PARTIALLY_PAID']
        ).values('invoice_date').annotate(
            invoices=Count('id'),
            total_amount=Sum('total_amount'),
            paid_amount=Sum('paid_amount')
        ).order_by('invoice_date')
        
        # Revenue by doctor
        revenue_by_doctor = Invoice.objects.filter(
            branch=branch,
            invoice_date__range=[start_date, end_date],
            status__in=['PAID', 'PARTIALLY_PAID'],
            doctor__isnull=False
        ).values('doctor__first_name', 'doctor__last_name').annotate(
            invoices=Count('id'),
            total_amount=Sum('total_amount'),
            paid_amount=Sum('paid_amount')
        ).order_by('-total_amount')
        
        # Revenue by treatment category
        # This would require joining with invoice items
        
        return {
            'report_type': 'revenue_summary',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'branch': branch.name if branch else 'All'
            },
            'summary': {
                'total_invoices': Invoice.objects.filter(
                    branch=branch,
                    invoice_date__range=[start_date, end_date]
                ).count(),
                'total_amount': Invoice.objects.filter(
                    branch=branch,
                    invoice_date__range=[start_date, end_date]
                ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0'),
                'total_paid': Invoice.objects.filter(
                    branch=branch,
                    invoice_date__range=[start_date, end_date]
                ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0'),
            },
            'daily_revenue': list(daily_revenue),
            'revenue_by_doctor': list(revenue_by_doctor),
        }
    
    @staticmethod
    def _generate_collection_efficiency(start_date, end_date, branch):
        """Generate collection efficiency report"""
        invoices = Invoice.objects.filter(
            branch=branch,
            invoice_date__range=[start_date, end_date]
        )
        
        total_invoices = invoices.count()
        paid_invoices = invoices.filter(status='PAID').count()
        partially_paid = invoices.filter(status='PARTIALLY_PAID').count()
        unpaid_invoices = invoices.filter(status='UNPAID').count()
        
        total_amount = invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        paid_amount = invoices.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        
        collection_efficiency = (paid_amount / total_amount * 100) if total_amount > 0 else 0
        
        return {
            'report_type': 'collection_efficiency',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'branch': branch.name if branch else 'All'
            },
            'summary': {
                'total_invoices': total_invoices,
                'paid_invoices': paid_invoices,
                'partially_paid_invoices': partially_paid,
                'unpaid_invoices': unpaid_invoices,
                'total_amount': total_amount,
                'paid_amount': paid_amount,
                'collection_efficiency': float(collection_efficiency),
            },
            'aging_summary': ReportService._generate_aging_summary(branch),
        }
    
    @staticmethod
    def _generate_aging_summary(branch):
        """Generate accounts receivable aging summary"""
        today = timezone.now().date()
        
        aging_buckets = {
            'current': {'days': 0, 'amount': Decimal('0')},
            '1-30': {'days': 30, 'amount': Decimal('0')},
            '31-60': {'days': 60, 'amount': Decimal('0')},
            '61-90': {'days': 90, 'amount': Decimal('0')},
            '90+': {'days': 999, 'amount': Decimal('0')},
        }
        
        unpaid_invoices = Invoice.objects.filter(
            branch=branch,
            status__in=['UNPAID', 'PARTIALLY_PAID', 'OVERDUE'],
            balance_amount__gt=0
        )
        
        for invoice in unpaid_invoices:
            days_overdue = (today - invoice.due_date).days if invoice.due_date else 0
            
            if days_overdue <= 0:
                aging_buckets['current']['amount'] += invoice.balance_amount
            elif days_overdue <= 30:
                aging_buckets['1-30']['amount'] += invoice.balance_amount
            elif days_overdue <= 60:
                aging_buckets['31-60']['amount'] += invoice.balance_amount
            elif days_overdue <= 90:
                aging_buckets['61-90']['amount'] += invoice.balance_amount
            else:
                aging_buckets['90+']['amount'] += invoice.balance_amount
        
        return aging_buckets
    
    @staticmethod
    def _generate_outstanding_summary(start_date, end_date, branch):
        """Generate outstanding amounts report"""
        outstanding_invoices = Invoice.objects.filter(
            branch=branch,
            status__in=['UNPAID', 'PARTIALLY_PAID', 'OVERDUE'],
            balance_amount__gt=0,
            invoice_date__range=[start_date, end_date]
        ).order_by('-due_date')
        
        return {
            'report_type': 'outstanding_summary',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'branch': branch.name if branch else 'All'
            },
            'total_outstanding': outstanding_invoices.aggregate(
                total=Sum('balance_amount')
            )['total'] or Decimal('0'),
            'invoices': list(outstanding_invoices.values(
                'invoice_number', 'patient__first_name', 'patient__last_name',
                'invoice_date', 'due_date', 'total_amount', 'paid_amount',
                'balance_amount', 'status'
            )),
        }
    
    @staticmethod
    def _generate_payment_method_analysis(start_date, end_date, branch):
        """Generate payment method analysis"""
        payments = PaymentModel.objects.filter(
            branch=branch,
            payment_date__range=[start_date, end_date],
            status=PaymentModel.COMPLETED
        ).values('payment_method__name').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('-total_amount')
        
        return {
            'report_type': 'payment_method_analysis',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'branch': branch.name if branch else 'All'
            },
            'payments': list(payments),
        }
    
    @staticmethod
    def _generate_doctor_commission(start_date, end_date, branch):
        """Generate doctor commission report"""
        # This would query invoice items with doctor commissions
        # Simplified for now
        return {
            'report_type': 'doctor_commission',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'branch': branch.name if branch else 'All'
            },
            'commissions': [],
        }
    
    @staticmethod
    def generate_clinical_report(template, parameters, start_date, end_date, branch):
        """Generate clinical reports"""
        report_type = parameters.get('report_type', 'doctor_utilization')
        
        if report_type == 'doctor_utilization':
            return ReportService._generate_doctor_utilization(start_date, end_date, branch)
        elif report_type == 'treatment_analysis':
            return ReportService._generate_treatment_analysis(start_date, end_date, branch)
        elif report_type == 'patient_demographics':
            return ReportService._generate_patient_demographics(start_date, end_date, branch)
        elif report_type == 'follow_up_analysis':
            return ReportService._generate_follow_up_analysis(start_date, end_date, branch)
        else:
            return {}
    
    @staticmethod
    def _generate_doctor_utilization(start_date, end_date, branch):
        """Generate doctor utilization report"""
        doctors = Doctor.objects.filter(branch=branch, is_active=True)
        
        utilization_data = []
        for doctor in doctors:
            visits = Visit.objects.filter(
                doctor=doctor,
                scheduled_date__range=[start_date, end_date],
                status__in=['COMPLETED', 'READY_FOR_BILLING', 'PAID']
            )
            
            total_visits = visits.count()
            total_hours = sum(
                (v.consultation_duration.total_seconds() / 3600 if v.consultation_duration else 0)
                for v in visits
            )
            
            # Calculate available hours (assuming 8 hours/day, 6 days/week)
            days_in_period = (end_date - start_date).days + 1
            available_hours = days_in_period * 8 * (6/7)  # 6 working days per week
            
            utilization_rate = (total_hours / available_hours * 100) if available_hours > 0 else 0
            
            utilization_data.append({
                'doctor_id': doctor.id,
                'doctor_name': f"{doctor.first_name} {doctor.last_name}",
                'total_visits': total_visits,
                'total_hours': round(total_hours, 2),
                'available_hours': round(available_hours, 2),
                'utilization_rate': round(utilization_rate, 2),
                'avg_consultation_time': round(total_hours / total_visits * 60, 2) if total_visits > 0 else 0,
            })
        
        return {
            'report_type': 'doctor_utilization',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'branch': branch.name if branch else 'All'
            },
            'doctors': utilization_data,
        }
    
    @staticmethod
    def _generate_treatment_analysis(start_date, end_date, branch):
        """Generate treatment analysis report"""
        # This would analyze treatments performed
        # Simplified for now
        return {
            'report_type': 'treatment_analysis',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'branch': branch.name if branch else 'All'
            },
            'treatments': [],
        }
    
    @staticmethod
    def _generate_patient_demographics(start_date, end_date, branch):
        """Generate patient demographics report"""
        patients = Patient.objects.filter(
            branch=branch,
            created_at__date__range=[start_date, end_date]
        )
        
        # Age groups
        age_groups = {
            '0-18': patients.filter(age__range=(0, 18)).count(),
            '19-30': patients.filter(age__range=(19, 30)).count(),
            '31-45': patients.filter(age__range=(31, 45)).count(),
            '46-60': patients.filter(age__range=(46, 60)).count(),
            '61+': patients.filter(age__gt=60).count(),
        }
        
        # Gender distribution
        gender_dist = patients.values('gender').annotate(count=Count('id'))
        
        # New vs returning
        total_patients = patients.count()
        returning_patients = patients.filter(visits__count__gt=1).distinct().count()
        new_patients = total_patients - returning_patients
        
        return {
            'report_type': 'patient_demographics',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'branch': branch.name if branch else 'All'
            },
            'summary': {
                'total_patients': total_patients,
                'new_patients': new_patients,
                'returning_patients': returning_patients,
            },
            'age_groups': age_groups,
            'gender_distribution': list(gender_dist),
        }
    
    @staticmethod
    def generate_operational_report(template, parameters, start_date, end_date, branch):
        """Generate operational reports"""
        report_type = parameters.get('report_type', 'appointment_statistics')
        
        if report_type == 'appointment_statistics':
            return ReportService._generate_appointment_statistics(start_date, end_date, branch)
        elif report_type == 'patient_wait_times':
            return ReportService._generate_wait_times(start_date, end_date, branch)
        elif report_type == 'branch_performance':
            return ReportService._generate_branch_performance(start_date, end_date, branch)
        else:
            return {}
    
    @staticmethod
    def _generate_appointment_statistics(start_date, end_date, branch):
        """Generate appointment statistics report"""
        appointments = Appointment.objects.filter(
            branch=branch,
            appointment_date__range=[start_date, end_date]
        )
        
        total_appointments = appointments.count()
        completed = appointments.filter(status='COMPLETED').count()
        no_show = appointments.filter(status='NO_SHOW').count()
        cancelled = appointments.filter(status='CANCELLED').count()
        
        # Status breakdown
        status_breakdown = appointments.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Source breakdown
        source_breakdown = Visit.objects.filter(
            branch=branch,
            scheduled_date__range=[start_date, end_date]
        ).values('appointment_source').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {
            'report_type': 'appointment_statistics',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'branch': branch.name if branch else 'All'
            },
            'summary': {
                'total_appointments': total_appointments,
                'completed': completed,
                'no_show': no_show,
                'cancelled': cancelled,
                'completion_rate': (completed / total_appointments * 100) if total_appointments > 0 else 0,
                'no_show_rate': (no_show / total_appointments * 100) if total_appointments > 0 else 0,
            },
            'status_breakdown': list(status_breakdown),
            'source_breakdown': list(source_breakdown),
        }
    
    @staticmethod
    def _generate_wait_times(start_date, end_date, branch):
        """Generate patient wait times report"""
        visits = Visit.objects.filter(
            branch=branch,
            scheduled_date__range=[start_date, end_date],
            actual_checkin__isnull=False,
            wait_duration__isnull=False
        )
        
        total_visits = visits.count()
        
        if total_visits == 0:
            return {
                'report_type': 'patient_wait_times',
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'branch': branch.name if branch else 'All'
                },
                'summary': {
                    'total_visits': 0,
                    'avg_wait_time': 0,
                    'max_wait_time': 0,
                    'min_wait_time': 0,
                },
                'wait_time_distribution': {},
            }
        
        # Calculate wait times in minutes
        wait_times = []
        for visit in visits:
            if visit.wait_duration:
                wait_minutes = visit.wait_duration.total_seconds() / 60
                wait_times.append(wait_minutes)
        
        avg_wait = sum(wait_times) / len(wait_times)
        max_wait = max(wait_times)
        min_wait = min(wait_times)
        
        # Distribution
        distribution = {
            '0-15 min': len([t for t in wait_times if t <= 15]),
            '16-30 min': len([t for t in wait_times if 16 <= t <= 30]),
            '31-45 min': len([t for t in wait_times if 31 <= t <= 45]),
            '46-60 min': len([t for t in wait_times if 46 <= t <= 60]),
            '60+ min': len([t for t in wait_times if t > 60]),
        }
        
        return {
            'report_type': 'patient_wait_times',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'branch': branch.name if branch else 'All'
            },
            'summary': {
                'total_visits': total_visits,
                'avg_wait_time': round(avg_wait, 2),
                'max_wait_time': round(max_wait, 2),
                'min_wait_time': round(min_wait, 2),
            },
            'wait_time_distribution': distribution,
        }
    
    @staticmethod
    def execute_custom_query(query_sql, parameters, start_date, end_date):
        """Execute custom SQL query"""
        # Replace placeholders
        query = query_sql.replace('{{start_date}}', str(start_date))
        query = query.replace('{{end_date}}', str(end_date))
        
        # Execute query
        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
        
        # Convert to dict
        data = []
        for row in rows:
            data.append(dict(zip(columns, row)))
        
        return {
            'report_type': 'custom_query',
            'query': query_sql,
            'parameters': parameters,
            'columns': columns,
            'rows': data,
        }
    
    @staticmethod
    def generate_summary(data, template):
        """Generate summary from report data"""
        if template.report_type == ReportTemplate.FINANCIAL:
            return {
                'total_amount': data.get('summary', {}).get('total_amount', 0),
                'total_paid': data.get('summary', {}).get('total_paid', 0),
                'collection_rate': data.get('summary', {}).get('collection_efficiency', 0),
            }
        elif template.report_type == ReportTemplate.CLINICAL:
            return {
                'total_visits': data.get('summary', {}).get('total_visits', 0),
                'total_patients': data.get('summary', {}).get('total_patients', 0),
            }
        elif template.report_type == ReportTemplate.OPERATIONAL:
            return {
                'total_appointments': data.get('summary', {}).get('total_appointments', 0),
                'completion_rate': data.get('summary', {}).get('completion_rate', 0),
            }
        else:
            return {}
    
    @staticmethod
    def send_report_email(report, recipients):
        """Send report via email"""
        # This would integrate with your email service
        # Simplified for now
        pass