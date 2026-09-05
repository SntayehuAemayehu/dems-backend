# payments/payment_methods/telebirr.py

from .base import BasePaymentMethod
from ..models import PaymentTransaction
from django.utils import timezone

class TelebirrMethod(BasePaymentMethod):
    """Telebirr payment method"""
    
    def __init__(self):
        self.method_id = 'telebirr'
        self.method_name = 'Telebirr'
        self.method_icon = '📱'
        self.telebirr_details = {
            'phone_number': '0918114545',
            'account_name': 'DEMS University',
            'service': 'Telebirr Merchant'
        }
    
    def initialize_payment(self, student, amount, **kwargs):
        """Initialize Telebirr payment"""
        reference = self.generate_reference(student)
        phone_number = kwargs.get('phone_number', '')
        
        transaction = PaymentTransaction.objects.create(
            student=student,
            tx_ref=reference,
            amount=amount,
            payment_method=self.method_id,
            status='PENDING',
            created_at=timezone.now(),
            response_data={'phone_number': phone_number}
        )
        
        return {
            'success': True,
            'reference': reference,
            'transaction_id': transaction.id,
            'amount': float(amount),
            'method': self.method_id,
            'payment_details': {
                **self.telebirr_details,
                'reference': reference,
                'amount': float(amount),
                'student_phone': phone_number,
                'student_name': student.user.full_name
            },
            'instructions': self.get_payment_instructions(amount, reference, phone_number)
        }
    
    def verify_payment(self, transaction_id, **kwargs):
        """Verify Telebirr payment"""
        try:
            transaction = PaymentTransaction.objects.get(tx_ref=transaction_id)
            # Telebirr payments require manual verification
            return {
                'success': True,
                'status': 'PENDING_VERIFICATION',
                'message': 'Telebirr payment is pending verification by Finance'
            }
        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'status': 'FAILED',
                'message': 'Transaction not found'
            }
    
    def get_payment_details(self, transaction_id, **kwargs):
        """Get Telebirr payment details"""
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
                    'method': 'Telebirr'
                },
                'telebirr_details': self.telebirr_details
            }
        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'message': 'Transaction not found'
            }
    
    def get_payment_instructions(self, amount, reference, phone_number=''):
        """Get payment instructions"""
        instructions = f"""
        Send ETB {amount} via Telebirr:
        
        Telebirr Number: {self.telebirr_details['phone_number']}
        Account Name: {self.telebirr_details['account_name']}
        
        Reference: {reference}
        """
        
        if phone_number:
            instructions += f"\nYour Phone: {phone_number}"
        
        instructions += """
        
        After sending, please upload the transaction receipt for verification.
        """
        
        return instructions