# payments/payment_methods/bank_transfer.py

from .base import BasePaymentMethod
from ..models import PaymentProof, PaymentTransaction
from accounts.models import StudentProfile
from django.utils import timezone
import uuid

class BankTransferMethod(BasePaymentMethod):
    """Bank Transfer payment method"""
    
    def __init__(self):
        self.method_id = 'bank_transfer'
        self.method_name = 'Bank Transfer'
        self.method_icon = '🏦'
        self.bank_details = {
            'bank_name': 'Commercial Bank of Ethiopia',
            'account_name': 'DEMS University',
            'account_number': '1000225566778',
            'branch': 'Addis Ababa Main Branch',
            'swift_code': 'CBETETADD'
        }
    
    def initialize_payment(self, student, amount, **kwargs):
        """Initialize bank transfer payment"""
        reference = self.generate_reference(student)
        
        # Create transaction record
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
            'payment_details': {
                **self.bank_details,
                'reference': reference,
                'amount': float(amount),
                'student_name': student.user.full_name,
                'student_id': student.student_id
            },
            'instructions': self.get_payment_instructions(amount, reference)
        }
    
    def verify_payment(self, transaction_id, **kwargs):
        """Verify bank transfer payment"""
        try:
            transaction = PaymentTransaction.objects.get(tx_ref=transaction_id)
            # Bank transfers require manual verification
            # This is done by Finance through the admin panel
            return {
                'success': True,
                'status': 'PENDING_VERIFICATION',
                'message': 'Payment is pending verification by Finance'
            }
        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'status': 'FAILED',
                'message': 'Transaction not found'
            }
    
    def get_payment_details(self, transaction_id, **kwargs):
        """Get bank transfer payment details"""
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
                    'method': 'Bank Transfer'
                },
                'bank_details': self.bank_details
            }
        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'message': 'Transaction not found'
            }
    
    def get_payment_instructions(self, amount, reference):
        """Get payment instructions"""
        return f"""
        Please transfer ETB {amount} to:
        
        Bank: {self.bank_details['bank_name']}
        Account Name: {self.bank_details['account_name']}
        Account Number: {self.bank_details['account_number']}
        Branch: {self.bank_details['branch']}
        
        Reference: {reference}
        
        After transfer, please upload the receipt for verification.
        """