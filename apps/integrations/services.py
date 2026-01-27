# apps/integrations/services.py

import logging
from django.utils import timezone
from datetime import timedelta
import requests
import json
import hashlib
import hmac

from .models import (
    BranchIntegration, PharmacyIntegration, PaymentGatewayIntegration,
    PharmacyOrder, PaymentTransaction, IntegrationLog
)
from apps.prescriptions.models import Prescription
from apps.billing.models import Invoice

logger = logging.getLogger(__name__)


class PharmacyService:
    """Service for pharmacy integration operations"""
    
    def __init__(self):
        self.session = requests.Session()
    
    def create_order(self, prescription_id, delivery_type, delivery_address=None, 
                    payment_method='cod', notes='', user=None):
        """Create a pharmacy order"""
        try:
            # Get prescription
            prescription = Prescription.objects.get(id=prescription_id)
            
            # Get active pharmacy integration for branch
            integration = BranchIntegration.objects.filter(
                branch=prescription.branch,
                integration_type__integration_type='pharmacy',
                status='active',
                is_default=True
            ).first()
            
            if not integration:
                raise Exception("No active pharmacy integration configured for this branch")
            
            # Prepare order data
            order_data = {
                'prescription': prescription,
                'medicines': [],  # Extract from prescription
                'patient': prescription.patient,
                'delivery_type': delivery_type,
                'delivery_address': delivery_address or {},
                'payment_method': payment_method,
                'notes': notes
            }
            
            # Call pharmacy API
            response = self._call_pharmacy_api(integration, 'create_order', order_data)
            
            # Create pharmacy order record
            order = PharmacyOrder.objects.create(
                prescription=prescription,
                branch_integration=integration,
                external_order_id=response.get('order_id'),
                status='pending',
                payment_status='pending',
                payment_method=payment_method,
                delivery_type=delivery_type,
                delivery_address=delivery_address or {},
                items=response.get('items', []),
                subtotal=response.get('subtotal', 0),
                tax=response.get('tax', 0),
                delivery_charge=response.get('delivery_charge', 0),
                discount=response.get('discount', 0),
                total=response.get('total', 0),
                estimated_delivery=response.get('estimated_delivery'),
                notes=notes,
                created_by=user,
                updated_by=user
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error creating pharmacy order: {str(e)}")
            raise
    
    def cancel_order(self, order):
        """Cancel a pharmacy order"""
        try:
            response = self._call_pharmacy_api(
                order.branch_integration,
                'cancel_order',
                {'order_id': order.external_order_id}
            )
            
            order.status = 'cancelled'
            order.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling pharmacy order: {str(e)}")
            raise
    
    def sync_inventory(self, integration):
        """Sync inventory with pharmacy"""
        try:
            response = self._call_pharmacy_api(integration, 'get_inventory', {})
            
            # Update pharmacy integration sync info
            pharmacy_config = integration.pharmacy_config
            pharmacy_config.last_inventory_sync = timezone.now()
            pharmacy_config.save()
            
            return {
                'success': True,
                'items_synced': len(response.get('items', [])),
                'timestamp': timezone.now()
            }
            
        except Exception as e:
            logger.error(f"Error syncing inventory: {str(e)}")
            raise
    
    def test_connection(self, integration):
        """Test pharmacy connection"""
        try:
            response = self._call_pharmacy_api(integration, 'test_connection', {})
            return response.get('success', False)
            
        except Exception as e:
            logger.error(f"Error testing pharmacy connection: {str(e)}")
            return False
    
    def _call_pharmacy_api(self, integration, endpoint, data):
        """Make API call to pharmacy"""
        try:
            # Prepare request
            url = f"{integration.endpoint_url}/{endpoint}"
            headers = self._prepare_headers(integration)
            
            # Log request
            log = IntegrationLog.objects.create(
                branch_integration=integration,
                log_type='api_call',
                direction='outgoing',
                status='pending',
                endpoint=url,
                method='POST',
                request_data=data,
                request_headers=headers,
                started_at=timezone.now()
            )
            
            # Make request
            response = self.session.post(url, json=data, headers=headers, timeout=30)
            
            # Log response
            log.completed_at = timezone.now()
            log.response_code = response.status_code
            log.response_headers = dict(response.headers)
            
            if response.status_code == 200:
                response_data = response.json()
                log.response_data = response_data
                log.status = 'success'
                log.save()
                return response_data
            else:
                log.response_data = {'error': response.text}
                log.status = 'failed'
                log.error_message = f"HTTP {response.status_code}: {response.text}"
                log.save()
                raise Exception(f"API call failed: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Error in pharmacy API call: {str(e)}")
            raise
    
    def _prepare_headers(self, integration):
        """Prepare headers for pharmacy API call"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        if integration.auth_type == 'api_key':
            headers['X-API-Key'] = integration.api_key
        elif integration.auth_type == 'jwt' and integration.access_token:
            headers['Authorization'] = f'Bearer {integration.access_token}'
        
        return headers


class PaymentService:
    """Service for payment gateway operations"""
    
    def __init__(self):
        self.gateways = {
            'razorpay': None,  # Will be lazy loaded
            'stripe': None,
            'paypal': None,
        }
    
    def create_payment_intent(self, invoice_id, amount, currency='INR', 
                             payment_method=None, customer_name=None,
                             customer_email=None, customer_phone=None,
                             return_url=None, user=None):
        """Create a payment intent"""
        try:
            # Get invoice
            invoice = Invoice.objects.get(id=invoice_id)
            
            # Get active payment integration for branch
            integration = BranchIntegration.objects.filter(
                branch=invoice.branch,
                integration_type__integration_type='payment',
                status='active',
                is_default=True
            ).first()
            
            if not integration:
                raise Exception("No active payment integration configured for this branch")
            
            # Get gateway client
            gateway = self._get_gateway_client(integration)
            
            # Create payment intent
            payment_data = gateway.create_payment(
                amount=amount,
                currency=currency,
                invoice_id=invoice.invoice_number,
                customer_name=customer_name or invoice.patient.name,
                customer_email=customer_email or invoice.patient.email,
                customer_phone=customer_phone or invoice.patient.phone,
                return_url=return_url,
                metadata={
                    'invoice_id': invoice.id,
                    'branch_id': invoice.branch.id,
                    'patient_id': invoice.patient.id
                }
            )
            
            # Create payment transaction record
            transaction = PaymentTransaction.objects.create(
                branch_integration=integration,
                invoice=invoice,
                payment_type='payment',
                status='created',
                amount=amount,
                currency=currency,
                payment_method=payment_method,
                customer_name=customer_name or invoice.patient.name,
                customer_email=customer_email or invoice.patient.email,
                customer_phone=customer_phone or invoice.patient.phone,
                gateway_response=payment_data,
                created_by=user,
                updated_by=user
            )
            
            return {
                'transaction_id': transaction.transaction_id,
                'payment_id': payment_data.get('payment_id'),
                'order_id': payment_data.get('order_id'),
                'amount': amount,
                'currency': currency,
                'gateway_data': payment_data,
                'redirect_url': payment_data.get('redirect_url')
            }
            
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            raise
    
    def capture_payment(self, transaction):
        """Capture a payment"""
        try:
            gateway = self._get_gateway_client(transaction.branch_integration)
            
            # Check if payment is authorized
            if transaction.status != 'authorized':
                raise Exception("Payment is not authorized for capture")
            
            # Capture payment
            capture_data = gateway.capture_payment(
                payment_id=transaction.payment_id,
                amount=transaction.amount
            )
            
            # Update transaction
            transaction.status = 'captured'
            transaction.captured_at = timezone.now()
            transaction.gateway_response = capture_data
            transaction.save()
            
            # Update invoice
            if transaction.invoice:
                transaction.invoice.payment_status = 'paid'
                transaction.invoice.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Error capturing payment: {str(e)}")
            raise
    
    def refund_payment(self, transaction, amount=None, reason=''):
        """Refund a payment"""
        try:
            gateway = self._get_gateway_client(transaction.branch_integration)
            
            # Check if payment is captured
            if transaction.status != 'captured':
                raise Exception("Payment is not captured for refund")
            
            refund_amount = amount or transaction.amount
            
            # Process refund
            refund_data = gateway.refund_payment(
                payment_id=transaction.payment_id,
                amount=refund_amount,
                reason=reason
            )
            
            # Create refund transaction
            refund_transaction = PaymentTransaction.objects.create(
                branch_integration=transaction.branch_integration,
                invoice=transaction.invoice,
                payment_type='refund',
                status='refunded',
                amount=refund_amount,
                currency=transaction.currency,
                payment_method=transaction.payment_method,
                customer_name=transaction.customer_name,
                customer_email=transaction.customer_email,
                customer_phone=transaction.customer_phone,
                gateway_response=refund_data,
                refunded_at=timezone.now(),
                created_by=transaction.updated_by,
                updated_by=transaction.updated_by
            )
            
            # Update original transaction
            if refund_amount == transaction.amount:
                transaction.status = 'refunded'
            else:
                transaction.status = 'partially_refunded'
            transaction.save()
            
            # Update invoice
            if transaction.invoice:
                # Update invoice refund status
                pass
            
            return refund_transaction
            
        except Exception as e:
            logger.error(f"Error refunding payment: {str(e)}")
            raise
    
    def verify_payment(self, transaction):
        """Verify a payment transaction"""
        try:
            gateway = self._get_gateway_client(transaction.branch_integration)
            
            verification_data = gateway.verify_payment(
                payment_id=transaction.payment_id
            )
            
            if verification_data.get('verified'):
                transaction.is_verified = True
                transaction.verified_at = timezone.now()
                transaction.verification_notes = verification_data.get('notes', '')
                transaction.save()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            raise
    
    def test_connection(self, integration):
        """Test payment gateway connection"""
        try:
            gateway = self._get_gateway_client(integration)
            return gateway.test_connection()
            
        except Exception as e:
            logger.error(f"Error testing payment connection: {str(e)}")
            return False
    
    def _get_gateway_client(self, integration):
        """Get gateway client based on provider"""
        provider_type = integration.provider.provider_type
        
        if provider_type == 'razorpay':
            from .payment_gateways.razorpay import RazorpayGateway
            if not self.gateways['razorpay']:
                self.gateways['razorpay'] = RazorpayGateway(
                    api_key=integration.api_key,
                    api_secret=integration.api_secret,
                    is_test_mode=integration.is_test_mode
                )
            return self.gateways['razorpay']
        
        elif provider_type == 'stripe':
            from .payment_gateways.stripe import StripeGateway
            if not self.gateways['stripe']:
                self.gateways['stripe'] = StripeGateway(
                    api_key=integration.api_key,
                    is_test_mode=integration.is_test_mode
                )
            return self.gateways['stripe']
        
        else:
            raise Exception(f"Unsupported payment provider: {provider_type}")