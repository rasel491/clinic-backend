# apps/otp/webhooks.py

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json
import logging
from .models import OTPRequest

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def sms_delivery_webhook(request):
    """Webhook for SMS delivery status updates"""
    try:
        data = json.loads(request.body)
        
        # Extract relevant data based on your SMS provider
        message_sid = data.get('MessageSid', data.get('message_id'))
        status = data.get('MessageStatus', data.get('status'))
        
        # Find OTP request
        otp_request = OTPRequest.objects.filter(
            metadata__sms_message_sid=message_sid
        ).first()
        
        if otp_request:
            status_map = {
                'delivered': 'DELIVERED',
                'failed': 'FAILED',
                'undelivered': 'FAILED'
            }
            
            new_status = status_map.get(status.lower())
            if new_status:
                if new_status == 'DELIVERED':
                    otp_request.mark_delivered()
                elif new_status == 'FAILED':
                    otp_request.mark_failed(f"SMS delivery failed: {status}")
        
        return JsonResponse({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)