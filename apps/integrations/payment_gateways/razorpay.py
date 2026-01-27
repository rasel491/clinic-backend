import razorpay
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class RazorpayGateway:
    """Razorpay payment gateway integration"""
    
    def __init__(self, api_key, api_secret, is_test_mode=True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_test_mode = is_test_mode
        
        # Initialize client
        self.client = razorpay.Client(auth=(api_key, api_secret))
        
        # Set base URL based on mode
        if is_test_mode:
            self.base_url = "https://api.razorpay.com/v1"
        else:
            self.base_url = "https://api.razorpay.com/v1"
    
    def create_payment(self, amount, currency, invoice_id, customer_name, 
                      customer_email, customer_phone, return_url, metadata=None):
        """Create a payment order"""
        try:
            # Convert amount to paise (Razorpay uses smallest currency unit)
            amount_in_paise = int(float(amount) * 100)
            
            # Create order
            order_data = {
                'amount': amount_in_paise,
                'currency': currency,
                'receipt': invoice_id,
                'payment_capture': 1,  # Auto capture
                'notes': metadata or {},
                'customer': {
                    'name': customer_name,
                    'email': customer_email,
                    'contact': customer_phone
                }
            }
            
            order = self.client.order.create(data=order_data)
            
            # Create payment link
            payment_link_data = {
                'amount': amount_in_paise,
                'currency': currency,
                'accept_partial': False,
                'description': f'Payment for Invoice {invoice_id}',
                'customer': {
                    'name': customer_name,
                    'email': customer_email,
                    'contact': customer_phone
                },
                'notify': {
                    'sms': True,
                    'email': True
                },
                'reminder_enable': True,
                'notes': metadata or {},
                'callback_url': return_url or settings.PAYMENT_CALLBACK_URL,
                'callback_method': 'get'
            }
            
            payment_link = self.client.payment_link.create(data=payment_link_data)
            
            return {
                'order_id': order['id'],
                'payment_id': None,  # Will be set after payment
                'amount': amount,
                'currency': currency,
                'status': order['status'],
                'razorpay_order_id': order['id'],
                'razorpay_payment_link_id': payment_link['id'],
                'redirect_url': payment_link['short_url'],
                'created_at': order['created_at']
            }
            
        except Exception as e:
            logger.error(f"Error creating Razorpay payment: {str(e)}")
            raise Exception(f"Razorpay payment creation failed: {str(e)}")
    
    def capture_payment(self, payment_id, amount):
        """Capture a payment"""
        try:
            # Razorpay auto-captures when payment_capture=1
            # This method is for manual capture if needed
            payment = self.client.payment.fetch(payment_id)
            
            if payment['status'] == 'authorized':
                capture_data = {
                    'amount': int(float(amount) * 100),
                    'currency': payment['currency']
                }
                
                captured_payment = self.client.payment.capture(payment_id, capture_data)
                
                return {
                    'payment_id': captured_payment['id'],
                    'status': captured_payment['status'],
                    'amount_captured': captured_payment['amount'] / 100,
                    'captured_at': timezone.now().isoformat()
                }
            else:
                raise Exception(f"Payment cannot be captured. Status: {payment['status']}")
                
        except Exception as e:
            logger.error(f"Error capturing Razorpay payment: {str(e)}")
            raise Exception(f"Payment capture failed: {str(e)}")
    
    def refund_payment(self, payment_id, amount, reason=''):
        """Refund a payment"""
        try:
            refund_amount = int(float(amount) * 100)
            
            refund_data = {
                'amount': refund_amount,
                'speed': 'normal',
                'notes': {
                    'reason': reason
                }
            }
            
            refund = self.client.payment.refund(payment_id, refund_data)
            
            return {
                'refund_id': refund['id'],
                'payment_id': refund['payment_id'],
                'amount': refund['amount'] / 100,
                'currency': refund['currency'],
                'status': refund['status'],
                'speed_requested': refund['speed_requested'],
                'speed_processed': refund['speed_processed'],
                'notes': refund.get('notes', {})
            }
            
        except Exception as e:
            logger.error(f"Error refunding Razorpay payment: {str(e)}")
            raise Exception(f"Payment refund failed: {str(e)}")
    
    def verify_payment(self, payment_id):
        """Verify a payment"""
        try:
            payment = self.client.payment.fetch(payment_id)
            
            return {
                'verified': payment['status'] == 'captured',
                'payment_id': payment['id'],
                'order_id': payment['order_id'],
                'amount': payment['amount'] / 100,
                'currency': payment['currency'],
                'status': payment['status'],
                'method': payment['method'],
                'description': payment.get('description', ''),
                'email': payment.get('email', ''),
                'contact': payment.get('contact', ''),
                'error_code': payment.get('error_code'),
                'error_description': payment.get('error_description'),
                'created_at': payment['created_at'],
                'captured_at': payment.get('captured_at')
            }
            
        except Exception as e:
            logger.error(f"Error verifying Razorpay payment: {str(e)}")
            return {'verified': False, 'error': str(e)}
    
    def test_connection(self):
        """Test connection to Razorpay"""
        try:
            # Try to fetch account details
            account = self.client.account.fetch()
            return {
                'success': True,
                'account_id': account.get('id'),
                'account_name': account.get('business_name'),
                'email': account.get('email'),
                'test_mode': self.is_test_mode
            }
        except Exception as e:
            logger.error(f"Razorpay connection test failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def verify_webhook_signature(self, payload, signature, secret):
        """Verify webhook signature"""
        try:
            self.client.utility.verify_webhook_signature(payload, signature, secret)
            return True
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            return False
    
    def get_payment_methods(self):
        """Get available payment methods"""
        try:
            methods = self.client.payment_method.all()
            return {
                'netbanking': methods.get('netbanking', []),
                'wallet': methods.get('wallet', []),
                'card': methods.get('card', []),
                'upi': methods.get('upi', [])
            }
        except Exception as e:
            logger.error(f"Error fetching payment methods: {str(e)}")
            return {}