# payments/payment_methods/telebirr.py

from .base import BasePaymentMethod
from ..models import PaymentTransaction
from django.utils import timezone
from analytics.models import SystemConfig   # ✅ ADD THIS

class TelebirrMethod(BasePaymentMethod):
    """Telebirr payment method — reads phone number live from SystemConfig"""

    def __init__(self):
        self.method_id = 'telebirr'
        self.method_name = 'Telebirr'
        self.method_icon = '📱'

    @property
    def telebirr_details(self):
        # ✅ Read EVERY time from DB — never hardcoded
        return {
            'phone_number': SystemConfig.get_value('payment_phone', '0918114545'),
            'account_name': SystemConfig.get_value('account_name', 'DEMS University'),
            'service': 'Telebirr Merchant',
        }

    def initialize_payment(self, student, amount, **kwargs):
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
                **self.telebirr_details,          # ✅ live
                'reference': reference,
                'amount': float(amount),
                'student_phone': phone_number,
                'student_name': student.user.full_name,
            },
            'instructions': self.get_payment_instructions(amount, reference, phone_number),
        }

    def verify_payment(self, transaction_id, **kwargs):
        try:
            PaymentTransaction.objects.get(tx_ref=transaction_id)
            return {
                'success': True,
                'status': 'PENDING_VERIFICATION',
                'message': 'Telebirr payment is pending verification by Finance'
            }
        except PaymentTransaction.DoesNotExist:
            return {'success': False, 'status': 'FAILED', 'message': 'Transaction not found'}

    def get_payment_details(self, transaction_id, **kwargs):
        try:
            t = PaymentTransaction.objects.get(tx_ref=transaction_id)
            return {
                'success': True,
                'transaction': {
                    'id': t.id,
                    'reference': t.tx_ref,
                    'amount': float(t.amount),
                    'status': t.status,
                    'created_at': t.created_at.isoformat(),
                    'method': 'Telebirr',
                },
                'telebirr_details': self.telebirr_details,   # ✅ live
            }
        except PaymentTransaction.DoesNotExist:
            return {'success': False, 'message': 'Transaction not found'}

    def get_payment_instructions(self, amount, reference, phone_number=''):
        phone = self.telebirr_details['phone_number']       # ✅ live
        account = self.telebirr_details['account_name']
        instructions = f"""
        Send ETB {amount} via Telebirr:

        Telebirr Number: {phone}
        Account Name: {account}

        Reference: {reference}
        """
        if phone_number:
            instructions += f"\nYour Phone: {phone_number}"
        instructions += "\n\nAfter sending, please upload the transaction receipt for verification."
        return instructions