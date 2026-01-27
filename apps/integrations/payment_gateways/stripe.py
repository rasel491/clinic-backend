import stripe
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class StripeGateway:
    """Stripe payment gateway integration"""
    
    def __init__(self, api_key, is_test_mode=True):
        self.api_key = api_key
        self.is_test_mode = is_test_mode
        
        # Initialize Stripe
        stripe.api_key = api_key
        
        # Set API version
        stripe.api_version = '2023-10-16'
    
    def create_payment(self, amount, currency, invoice_id, customer_name,
                      customer_email, customer_phone, return_url, metadata=None):
        """Create a payment intent"""
        try:
            # Create or retrieve customer
            customer = self._get_or_create_customer(
                email=customer_email,
                name=customer_name,
                phone=customer_phone
            )
            
            # Create payment intent
            intent_data = {
                'amount': int(float(amount) * 100),  # Convert to cents
                'currency': currency.lower(),
                'customer': customer.id,
                'description': f'Payment for Invoice {invoice_id}',
                'metadata': metadata or {},
                'payment_method_types': ['card'],
                'receipt_email': customer_email,
            }
            
            if return_url:
                intent_data['return_url'] = return_url
            
            intent = stripe.PaymentIntent.create(**intent_data)
            
            # Create checkout session for better UX
            session_data = {
                'customer': customer.id,
                'payment_method_types': ['card'],
                'line_items': [{
                    'price_data': {
                        'currency': currency.lower(),
                        'product_data': {
                            'name': f'Invoice {invoice_id}',
                            'description': 'Dental Clinic Services',
                        },
                        'unit_amount': int(float(amount) * 100),
                    },
                    'quantity': 1,
                }],
                'mode': 'payment',
                'success_url': return_url or settings.PAYMENT_SUCCESS_URL,
                'cancel_url': return_url or settings.PAYMENT_CANCEL_URL,
                'metadata': metadata or {},
                'customer_email': customer_email,
            }
            
            session = stripe.checkout.Session.create(**session_data)
            
            return {
                'payment_id': intent.id,
                'client_secret': intent.client_secret,
                'amount': amount,
                'currency': currency,
                'status': intent.status,
                'customer_id': customer.id,
                'stripe_session_id': session.id,
                'redirect_url': session.url,
                'created_at': timezone.now().isoformat()
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment: {str(e)}")
            raise Exception(f"Stripe payment creation failed: {str(e.user_message)}")
        except Exception as e:
            logger.error(f"Error creating Stripe payment: {str(e)}")
            raise Exception(f"Payment creation failed: {str(e)}")
    
    def capture_payment(self, payment_id, amount):
        """Capture a payment intent"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_id)
            
            if intent.status == 'requires_capture':
                captured_intent = stripe.PaymentIntent.capture(payment_id)
                
                return {
                    'payment_id': captured_intent.id,
                    'status': captured_intent.status,
                    'amount_captured': captured_intent.amount_received / 100,
                    'currency': captured_intent.currency,
                    'captured_at': timezone.now().isoformat()
                }
            else:
                raise Exception(f"Payment cannot be captured. Status: {intent.status}")
                
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error capturing payment: {str(e)}")
            raise Exception(f"Payment capture failed: {str(e.user_message)}")
        except Exception as e:
            logger.error(f"Error capturing Stripe payment: {str(e)}")
            raise Exception(f"Payment capture failed: {str(e)}")
    
    def refund_payment(self, payment_id, amount, reason=''):
        """Refund a payment"""
        try:
            refund_amount = int(float(amount) * 100)
            
            refund_data = {
                'payment_intent': payment_id,
                'amount': refund_amount,
                'reason': 'requested_by_customer' if reason else None,
                'metadata': {
                    'reason': reason
                }
            }
            
            refund = stripe.Refund.create(**refund_data)
            
            return {
                'refund_id': refund.id,
                'payment_intent': refund.payment_intent,
                'amount': refund.amount / 100,
                'currency': refund.currency,
                'status': refund.status,
                'reason': refund.reason,
                'metadata': refund.metadata
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error refunding payment: {str(e)}")
            raise Exception(f"Payment refund failed: {str(e.user_message)}")
        except Exception as e:
            logger.error(f"Error refunding Stripe payment: {str(e)}")
            raise Exception(f"Payment refund failed: {str(e)}")
    
    def verify_payment(self, payment_id):
        """Verify a payment"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_id)
            
            return {
                'verified': intent.status == 'succeeded',
                'payment_id': intent.id,
                'amount': intent.amount / 100,
                'currency': intent.currency,
                'status': intent.status,
                'customer_id': intent.customer,
                'payment_method': intent.payment_method,
                'charges': {
                    'total_count': len(intent.charges.data),
                    'data': [{
                        'id': charge.id,
                        'amount': charge.amount / 100,
                        'status': charge.status,
                        'paid': charge.paid,
                        'payment_method': charge.payment_method_details.type
                    } for charge in intent.charges.data]
                } if intent.charges.data else None,
                'created_at': intent.created
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error verifying payment: {str(e)}")
            return {'verified': False, 'error': str(e.user_message)}
        except Exception as e:
            logger.error(f"Error verifying Stripe payment: {str(e)}")
            return {'verified': False, 'error': str(e)}
    
    def test_connection(self):
        """Test connection to Stripe"""
        try:
            # Try to retrieve account balance
            balance = stripe.Balance.retrieve()
            
            return {
                'success': True,
                'available': [{'amount': amt.amount / 100, 'currency': amt.currency} 
                            for amt in balance.available],
                'pending': [{'amount': amt.amount / 100, 'currency': amt.currency} 
                          for amt in balance.pending],
                'test_mode': self.is_test_mode
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe connection test failed: {str(e)}")
            return {'success': False, 'error': str(e.user_message)}
        except Exception as e:
            logger.error(f"Stripe connection test failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _get_or_create_customer(self, email, name, phone):
        """Get existing customer or create new one"""
        try:
            # Search for existing customer by email
            customers = stripe.Customer.list(email=email, limit=1)
            
            if customers.data:
                return customers.data[0]
            else:
                # Create new customer
                customer_data = {
                    'email': email,
                    'name': name,
                    'phone': phone,
                    'metadata': {
                        'source': 'dental_clinic_system'
                    }
                }
                
                return stripe.Customer.create(**customer_data)
                
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer error: {str(e)}")
            raise Exception(f"Customer management failed: {str(e.user_message)}")
    
    def verify_webhook_signature(self, payload, signature, secret):
        """Verify webhook signature"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, secret
            )
            return event
        except ValueError as e:
            logger.error(f"Invalid Stripe webhook payload: {str(e)}")
            return None
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid Stripe webhook signature: {str(e)}")
            return None
    
    def get_payment_methods(self):
        """Get available payment methods"""
        try:
            # Stripe supports various payment methods
            return {
                'card': ['visa', 'mastercard', 'amex', 'discover', 'diners', 'jcb'],
                'bank_transfer': ['ach', 'sepa'],
                'wallet': ['apple_pay', 'google_pay'],
                'others': ['klarna', 'affirm', 'afterpay']
            }
        except Exception as e:
            logger.error(f"Error fetching payment methods: {str(e)}")
            return {}