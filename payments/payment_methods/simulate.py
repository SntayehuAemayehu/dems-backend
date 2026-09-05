# payments/payment_methods/simulate.py

from .base import BasePaymentMethod
from ..models import PaymentProof, PaymentTransaction
from django.utils import timezone
import uuid

class SimulateMethod(BasePaymentMethod):
    """Simulate payment method (1-Click Demo)"""
    
    def __init__(self):
        self.method_id = 'simulate'
        self.method_name = 'Demo Payment (1-Click)'
        self.method_icon = '🧪'
    
    def initialize_payment(self, student, amount, **kwargs):
        """Initialize simulated payment"""
        reference = f"DEMO-{uuid.uuid4().hex[:8].upper()}"
        
        transaction = PaymentTransaction.objects.create(
            student=student,
            tx_ref=reference,
            amount=amount,
            payment_method=self.method_id,
            status='PENDING',
            created_at=timezone.now()
        )
        
        return {
            'success': True,
            'reference': reference,
            'transaction_id': transaction.id,
            'amount': float(amount),
            'method': self.method_id,
            'instructions': self.get_payment_instructions(amount, reference),
            'is_demo': True
        }
    
    def verify_payment(self, transaction_id, **kwargs):
        """Verify simulated payment - INSTANT"""
        try:
            transaction = PaymentTransaction.objects.get(tx_ref=transaction_id)
            
            # Auto-verify
            transaction.status = 'PAID'
            transaction.save()
            
            # Create payment proof
            PaymentProof.objects.create(
                student=transaction.student,
                transaction_id=transaction.tx_ref,
                amount=transaction.amount,
                bank_name='DEMO PAYMENT',
                transaction_date=timezone.now().date(),
                status='VERIFIED',
                verified_at=timezone.now(),
                payment_type='REGISTRATION'
            )
            
            # Update student payment status
            student = transaction.student
            student.payment_status = 'VERIFIED'
            student.save()
            
            return {
                'success': True,
                'status': 'PAID',
                'message': '✅ Payment simulated successfully!'
            }
            
        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'status': 'FAILED',
                'message': 'Transaction not found'
            }
    
    def get_payment_details(self, transaction_id, **kwargs):
        """Get simulated payment details"""
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
                    'method': 'Demo Payment'
                },
                'is_demo': True,
                'note': 'This is a demonstration payment. No real money involved.'
            }
        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'message': 'Transaction not found'
            }
    
    def get_payment_instructions(self, amount, reference):
        """Get payment instructions"""
        return f"""
        🧪 DEMO PAYMENT - No real money involved
        
        Click "Complete Demo Payment" to instantly verify your payment.
        
        Amount: ETB {amount}
        Reference: {reference}
        
        This is for demonstration purposes only.
        """