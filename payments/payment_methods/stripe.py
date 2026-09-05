# payments/payment_methods/stripe.py

from .base import BasePaymentMethod
from ..models import PaymentTransaction
from django.conf import settings
import stripe
from django.utils import timezone

class StripeMethod(BasePaymentMethod):
    """Stripe payment method (Test Mode)"""
    
    def __init__(self):
        self.method_id = 'stripe'
        self.method_name = 'Stripe (Card)'
        self.method_icon = '💳'
        self.is_test_mode = True
        
        # Use test keys
        if hasattr(settings, 'STRIPE_TEST_SECRET_KEY'):
            stripe.api_key = settings.STRIPE_TEST_SECRET_KEY
        else:
            stripe.api_key = 'sk_test_xxxxxxxx'
    
    def initialize_payment(self, student, amount, **kwargs):
        """Initialize Stripe payment"""
        reference = self.generate_reference(student)
        
        try:
            # Create a PaymentIntent
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency='usd',
                payment_method_types=['card'],
                receipt_email=student.user.email,
                metadata={
                    'student_id': student.id,
                    'student_name': student.user.full_name,
                    'reference': reference,
                    'integration_check': 'test_payment'
                },
                description=f"DEMS Payment - {reference}"
            )
            
            # Create transaction record
            transaction = PaymentTransaction.objects.create(
                student=student,
                tx_ref=reference,
                amount=amount,
                payment_method=self.method_id,
                status='PENDING',
                created_at=timezone.now(),
                response_data={
                    'payment_intent_id': intent.id,
                    'client_secret': intent.client_secret
                }
            )
            
            return {
                'success': True,
                'reference': reference,
                'transaction_id': transaction.id,
                'amount': float(amount),
                'method': self.method_id,
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'publishable_key': settings.STRIPE_TEST_PUBLISHABLE_KEY if hasattr(settings, 'STRIPE_TEST_PUBLISHABLE_KEY') else 'pk_test_xxxxxxxx',
                'instructions': self.get_payment_instructions(amount, reference)
            }
            
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Stripe payment initialization failed'
            }
    
    def verify_payment(self, transaction_id, **kwargs):
        """Verify Stripe payment"""
        try:
            transaction = PaymentTransaction.objects.get(tx_ref=transaction_id)
            payment_intent_id = transaction.response_data.get('payment_intent_id')
            
            if payment_intent_id:
                intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                
                if intent.status == 'succeeded':
                    transaction.status = 'PAID'
                    transaction.save()
                    return {
                        'success': True,
                        'status': 'PAID',
                        'message': 'Payment verified successfully'
                    }
            
            return {
                'success': False,
                'status': 'PENDING',
                'message': 'Payment not yet completed'
            }
            
        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'status': 'FAILED',
                'message': 'Transaction not found'
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'status': 'ERROR',
                'message': str(e)
            }
    
    def get_payment_details(self, transaction_id, **kwargs):
        """Get Stripe payment details"""
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
                    'method': 'Stripe'
                },
                'is_test_mode': self.is_test_mode,
                'payment_intent_id': transaction.response_data.get('payment_intent_id')
            }
        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'message': 'Transaction not found'
            }
    
    def get_payment_instructions(self, amount, reference):
        """Get payment instructions"""
        return f"""
        TEST MODE - No real money will be charged
        
        Enter your card details (use test card numbers):
        
        Card Number: 4242 4242 4242 4242
        Expiry: 12/25
        CVC: 123
        
        Amount: ${amount}
        Reference: {reference}
        """