import qrcode
import json
import base64
from io import BytesIO
from django.utils import timezone
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger(__name__)


class QRCodeService:
    """Service for generating QR codes for prescriptions and orders"""
    
    def __init__(self):
        self.qr_version = 1
        self.box_size = 10
        self.border = 4
    
    def generate_prescription_qr(self, prescription):
        """Generate QR code for prescription"""
        try:
            # Prepare data for QR code
            qr_data = {
                'type': 'prescription',
                'prescription_id': str(prescription.id),
                'patient_id': str(prescription.patient.id),
                'patient_name': prescription.patient.name,
                'doctor_id': str(prescription.doctor.id),
                'doctor_name': prescription.doctor.get_full_name(),
                'date': prescription.created_at.isoformat(),
                'clinic': prescription.branch.name,
                'verification_url': f"https://clinic.example.com/verify/{prescription.verification_code}"
            }
            
            # Add medicine summary
            if hasattr(prescription, 'medicines'):
                qr_data['medicines_count'] = prescription.medicines.count()
                qr_data['total_items'] = sum(m.quantity for m in prescription.medicines.all())
            
            return self._generate_qr_code(qr_data)
            
        except Exception as e:
            logger.error(f"Error generating prescription QR: {str(e)}")
            raise
    
    def generate_order_qr(self, order):
        """Generate QR code for pharmacy order"""
        try:
            qr_data = {
                'type': 'pharmacy_order',
                'order_id': str(order.order_id),
                'external_order_id': order.external_order_id,
                'prescription_id': str(order.prescription.id),
                'patient_name': order.prescription.patient.name,
                'status': order.status,
                'total_amount': str(order.total),
                'pharmacy': order.branch_integration.provider.name,
                'tracking_url': order.tracking_url or '',
                'verification_url': f"https://clinic.example.com/orders/{order.order_id}"
            }
            
            return self._generate_qr_code(qr_data)
            
        except Exception as e:
            logger.error(f"Error generating order QR: {str(e)}")
            raise
    
    def generate_payment_qr(self, transaction):
        """Generate QR code for payment (UPI, etc.)"""
        try:
            if transaction.payment_method_type == 'upi':
                return self._generate_upi_qr(transaction)
            else:
                return self._generate_payment_details_qr(transaction)
                
        except Exception as e:
            logger.error(f"Error generating payment QR: {str(e)}")
            raise
    
    def _generate_qr_code(self, data):
        """Generate QR code from data"""
        try:
            # Convert data to JSON string
            json_data = json.dumps(data, ensure_ascii=False)
            
            # Generate QR code
            qr = qrcode.QRCode(
                version=self.qr_version,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=self.box_size,
                border=self.border,
            )
            
            qr.add_data(json_data)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            return {
                'data': data,
                'image_base64': img_base64,
                'image_url': f"data:image/png;base64,{img_base64}",
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in QR generation: {str(e)}")
            raise
    
    def _generate_upi_qr(self, transaction):
        """Generate UPI QR code"""
        try:
            # Format: upi://pay?pa=UPI_ID&pn=NAME&am=AMOUNT&tn=NOTE&cu=CURRENCY
            upi_id = transaction.upi_id or 'clinic@upi'
            amount = str(transaction.amount)
            
            upi_url = f"upi://pay?pa={upi_id}&pn={transaction.customer_name}&am={amount}&tn=Payment for invoice {transaction.invoice.invoice_number}&cu={transaction.currency}"
            
            qr = qrcode.QRCode(
                version=self.qr_version,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=self.box_size,
                border=self.border,
            )
            
            qr.add_data(upi_url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            return {
                'type': 'upi_qr',
                'upi_url': upi_url,
                'amount': amount,
                'currency': transaction.currency,
                'image_base64': img_base64,
                'image_url': f"data:image/png;base64,{img_base64}"
            }
            
        except Exception as e:
            logger.error(f"Error generating UPI QR: {str(e)}")
            raise
    
    def _generate_payment_details_qr(self, transaction):
        """Generate QR code with payment details"""
        try:
            qr_data = {
                'type': 'payment_details',
                'transaction_id': str(transaction.transaction_id),
                'payment_id': transaction.payment_id,
                'invoice_number': transaction.invoice.invoice_number if transaction.invoice else '',
                'amount': str(transaction.amount),
                'currency': transaction.currency,
                'payment_method': transaction.payment_method,
                'customer_name': transaction.customer_name,
                'timestamp': transaction.initiated_at.isoformat(),
                'payment_url': f"https://clinic.example.com/payments/{transaction.transaction_id}"
            }
            
            return self._generate_qr_code(qr_data)
            
        except Exception as e:
            logger.error(f"Error generating payment details QR: {str(e)}")
            raise
    
    def verify_qr_code(self, qr_data):
        """Verify QR code data"""
        try:
            if isinstance(qr_data, str):
                data = json.loads(qr_data)
            else:
                data = qr_data
            
            # Verify based on type
            if data.get('type') == 'prescription':
                return self._verify_prescription_qr(data)
            elif data.get('type') == 'pharmacy_order':
                return self._verify_order_qr(data)
            elif data.get('type') == 'payment_details':
                return self._verify_payment_qr(data)
            else:
                raise Exception("Unknown QR code type")
                
        except Exception as e:
            logger.error(f"Error verifying QR code: {str(e)}")
            return {'valid': False, 'error': str(e)}
    
    def _verify_prescription_qr(self, data):
        """Verify prescription QR code"""
        # Use absolute import instead of relative
        from apps.prescriptions.models import Prescription
        
        try:
            prescription = Prescription.objects.get(id=data['prescription_id'])
            
            return {
                'valid': True,
                'prescription': {
                    'id': prescription.id,
                    'patient_name': prescription.patient.name,
                    'doctor_name': prescription.doctor.get_full_name(),
                    'date': prescription.created_at,
                    'status': prescription.status
                },
                'verification_timestamp': timezone.now()
            }
            
        except Prescription.DoesNotExist:
            return {'valid': False, 'error': 'Prescription not found'}
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def _verify_order_qr(self, data):
        """Verify pharmacy order QR code"""
        # Use absolute import instead of relative
        from apps.integrations.models import PharmacyOrder
        
        try:
            order = PharmacyOrder.objects.get(order_id=data['order_id'])
            
            return {
                'valid': True,
                'order': {
                    'id': order.id,
                    'order_id': order.order_id,
                    'status': order.status,
                    'total_amount': order.total,
                    'delivery_type': order.delivery_type
                },
                'verification_timestamp': timezone.now()
            }
            
        except PharmacyOrder.DoesNotExist:
            return {'valid': False, 'error': 'Order not found'}
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def _verify_payment_qr(self, data):
        """Verify payment QR code"""
        # Use absolute import instead of relative
        from apps.integrations.models import PaymentTransaction
        
        try:
            transaction = PaymentTransaction.objects.get(transaction_id=data['transaction_id'])
            
            return {
                'valid': True,
                'transaction': {
                    'id': transaction.id,
                    'transaction_id': transaction.transaction_id,
                    'amount': transaction.amount,
                    'status': transaction.status,
                    'payment_method': transaction.payment_method
                },
                'verification_timestamp': timezone.now()
            }
            
        except PaymentTransaction.DoesNotExist:
            return {'valid': False, 'error': 'Transaction not found'}
        except Exception as e:
            return {'valid': False, 'error': str(e)}