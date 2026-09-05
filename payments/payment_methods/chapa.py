# payments/payment_methods/chapa.py

from .base import BasePaymentMethod
from ..models import PaymentTransaction
from django.conf import settings
import requests
import uuid
from django.utils import timezone

class ChapaMethod(BasePaymentMethod):
    """Chapa payment method (Test Mode)"""
    
    def __init__(self):
        self.method_id = 'chapa'
        self.method_name = 'Chapa'
        self.method_icon = '💳'
        self.secret_key = settings.CHAPA_TEST_SECRET_KEY if hasattr(settings, 'CHAPA_TEST_SECRET_KEY') else 'CHASECK_TEST-xxxxxxxx'
        self.base_url = 'https://api.chapa.co/v1'
        self.is_test_mode = True
    
    def initialize_payment(self, student, amount, **kwargs):
        """Initialize Chapa payment"""
        reference = self.generate_reference(student)
        
        # Prepare payload for Chapa
        payload = {
            "amount": str(amount),
            "currency": "ETB",
            "email": student.user.email,
            "first_name": student.user.full_name.split()[0] if student.user.full_name else 'Student',
            "last_name": ' '.join(student.user.full_name.split()[1:]) if student.user.full_name else 'DEMS',
            "tx_ref": reference,
            "callback_url": f"{settings.BASE_URL}/api/payments/chapa-callback/",
            "return_url": f"{settings.BASE_URL}/payments",
            "customization": {
                "title": "DEMS Payment",
                "description": "Distance Education Management System"
            }
        }
        
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/transaction/initialize",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    # Create transaction record
                    transaction = PaymentTransaction.objects.create(
                        student=student,
                        tx_ref=reference,
                        amount=amount,
                        payment_method=self.method_id,
                        status='PENDING',
                        created_at=timezone.now(),
                        response_data=data.get('data', {})
                    )
                    
                    return {
                        'success': True,
                        'reference': reference,
                        'transaction_id': transaction.id,
                        'amount': float(amount),
                        'method': self.method_id,
                        'checkout_url': data['data']['checkout_url'],
                        'payment_id': data['data']['id'],
                        'instructions': self.get_payment_instructions(amount, reference)
                    }
            
            return {
                'success': False,
                'error': 'Chapa payment initialization failed',
                'message': response.json().get('message', 'Unknown error')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to connect to Chapa'
            }
    
    def verify_payment(self, transaction_id, **kwargs):
        """Verify Chapa payment"""
        headers = {
            "Authorization": f"Bearer {self.secret_key}"
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/transaction/verify/{transaction_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    # Update transaction
                    try:
                        transaction = PaymentTransaction.objects.get(tx_ref=transaction_id)
                        transaction.status = 'PAID'
                        transaction.save()
                        
                        return {
                            'success': True,
                            'status': 'PAID',
                            'message': 'Payment verified successfully'
                        }
                    except PaymentTransaction.DoesNotExist:
                        pass
                
                return {
                    'success': False,
                    'status': 'FAILED',
                    'message': 'Payment verification failed'
                }
            
            return {
                'success': False,
                'status': 'FAILED',
                'message': 'Failed to verify payment'
            }
            
        except Exception as e:
            return {
                'success': False,
                'status': 'ERROR',
                'message': str(e)
            }
    
    def get_payment_details(self, transaction_id, **kwargs):
        """Get Chapa payment details"""
        try:
            transaction = PaymentTransaction.objects.get(tx_ref=transaction_id)
            return {
                'success': True,
                'transaction': {
                    'id': transaction.id,
                    'reference': transaction.tx_ref,
                    'amount': float(transaction.amount),
                    'status': transaction.status,
                    'created_at': transaction.created_at.isoformat(),
                    'method': 'Chapa'
                },
                'is_test_mode': self.is_test_mode
            }
        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'message': 'Transaction not found'
            }
    
    def get_payment_instructions(self, amount, reference):
        """Get payment instructions"""
        mode = "TEST" if self.is_test_mode else "LIVE"
        return f"""
        {mode} MODE - No real money will be transferred
        
        Click the payment link to complete your payment:
        
        Amount: ETB {amount}
        Reference: {reference}
        
        You will be redirected to Chapa's secure payment page.
        """