# payments/payment_methods/chapa.py
# COMPLETE CORRECTED CHAPA INTEGRATION
# Real API integration with proper error handling, timeouts, and DB updates

from .base import BasePaymentMethod
from ..models import PaymentTransaction, PaymentProof
from django.conf import settings
from django.utils import timezone
import requests
import logging

logger = logging.getLogger(__name__)


class ChapaMethod(BasePaymentMethod):
    """Chapa payment method — real API integration (Test Mode by default)"""

    def __init__(self):
        self.method_id = 'chapa'
        self.method_name = 'Chapa'
        self.method_icon = '💳'

        # Real secret key from settings (env var)
        self.secret_key = getattr(settings, 'CHAPA_TEST_SECRET_KEY', '')

        # Determine test vs live mode from key prefix
        self.is_test_mode = not self.secret_key.startswith('CHAP_LIVE_')

        # Base URLs
        self.base_url = getattr(settings, 'CHAPA_BASE_URL', 'https://api.chapa.co/v1')

        # Frontend/backend URLs (add these to settings!)
        self.backend_url = getattr(settings, 'BACKEND_URL', settings.BASE_URL)
        self.frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')

    # ================================================================
    # INITIALIZE PAYMENT
    # ================================================================
    def initialize_payment(self, student, amount, **kwargs):
        """
        Initialize a Chapa payment.
        Returns dict with checkout_url to redirect the user to.
        """
        if not self.secret_key or 'xxxx' in self.secret_key:
            logger.error("❌ Chapa secret key missing or placeholder")
            return {
                'success': False,
                'error': 'Chapa is not configured',
                'message': 'Please contact admin: Chapa API key missing.'
            }

        reference = self.generate_reference(student)
        student_name = (student.user.full_name or 'Student').strip()
        name_parts = student_name.split()
        first_name = name_parts[0] if name_parts else 'Student'
        last_name = name_parts[1] if len(name_parts) > 1 else first_name
# Add this line in chapa.py right before payload = {
        print("🔍 URL SENT TO CHAPA:", f"{self.backend_url}/api/payments/webhook/chapa/")
        payload = {
            "amount": str(amount),
            "currency": "ETB",
            "email": student.user.email,
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": student.user.phone or '0900123456',
            "tx_ref": reference,
            "callback_url": f"{self.backend_url}/api/payments/webhook/chapa/",
            "return_url": f"{self.frontend_url}/payments?ref={reference}",
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
            logger.info(f"🚀 Chapa init: {reference} — ETB {amount} — {student.user.email}")
            response = requests.post(
                f"{self.base_url}/transaction/initialize",
                json=payload,
                headers=headers,
                timeout=30
            )

            # Log the raw response for debugging
            logger.info(f"📥 Chapa init response: {response.status_code}")

            try:
                data = response.json()
            except ValueError:
                logger.error(f"❌ Chapa returned non-JSON: {response.text[:500]}")
                return {
                    'success': False,
                    'error': 'Invalid response from Chapa',
                    'message': 'Payment gateway error'
                }

            # Success path
            if response.status_code == 200 and data.get('status') == 'success':
                checkout_url = data.get('data', {}).get('checkout_url')
                payment_id = data.get('data', {}).get('id')

                if not checkout_url:
                    logger.error(f"❌ Chapa: no checkout_url in response: {data}")
                    return {
                        'success': False,
                        'error': 'Missing checkout URL',
                        'message': 'Payment gateway error'
                    }

                transaction = PaymentTransaction.objects.create(
                    student=student,
                    tx_ref=reference,
                    amount=amount,
                    payment_method=self.method_id,
                    status='PENDING',
                    created_at=timezone.now(),
                    response_data=data.get('data', {})
                )

                logger.info(f"✅ Chapa transaction created: {reference}")

                return {
                    'success': True,
                    'reference': reference,
                    'transaction_id': transaction.id,
                    'amount': float(amount),
                    'method': self.method_id,
                    'checkout_url': checkout_url,
                    'payment_id': payment_id,
                    'is_test_mode': self.is_test_mode,
                    'instructions': self.get_payment_instructions(amount, reference)
                }

            # Error path — log EVERYTHING so you can debug
            logger.error(
                f"❌ Chapa init failed: status={response.status_code} "
                f"body={response.text[:500]}"
            )
            return {
                'success': False,
                'error': data.get('message', 'Chapa initialization failed'),
                'message': data.get('message', 'Please try again later'),
                'status_code': response.status_code
            }

        except requests.Timeout:
            logger.error(f"❌ Chapa init timeout for {reference}")
            return {
                'success': False,
                'error': 'Chapa timeout',
                'message': 'Payment gateway did not respond. Please try again.'
            }
        except requests.RequestException as e:
            logger.error(f"❌ Chapa network error: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Cannot connect to Chapa. Please check your internet.'
            }
        except Exception as e:
            logger.exception(f"❌ Chapa unexpected error: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Unexpected error occurred'
            }

    # ================================================================
    # VERIFY PAYMENT
    # ================================================================
    def verify_payment(self, transaction_id, **kwargs):
        """
        Verify a Chapa payment AND update:
         - PaymentTransaction.status → PAID
         - Create PaymentProof (so Finance sees it)
         - Update student.payment_status → VERIFIED
        """
        headers = {"Authorization": f"Bearer {self.secret_key}"}

        try:
            logger.info(f"🔎 Chapa verify: {transaction_id}")
            response = requests.get(
                f"{self.base_url}/transaction/verify/{transaction_id}",
                headers=headers,
                timeout=30
            )

            try:
                data = response.json()
            except ValueError:
                logger.error(f"❌ Chapa verify returned non-JSON: {response.text[:500]}")
                return {'success': False, 'status': 'ERROR', 'message': 'Invalid response'}

            logger.info(f"📥 Chapa verify response: {response.status_code} — {data.get('status')}")

            if response.status_code != 200:
                logger.error(f"❌ Chapa verify failed: {response.text[:500]}")
                return {
                    'success': False,
                    'status': 'FAILED',
                    'message': data.get('message', 'Verification failed')
                }

            # Chapa's verify response: data['status'] = 'success', data['data']['status'] = 'success'
            chapa_status = data.get('data', {}).get('status')
            if data.get('status') != 'success' or chapa_status != 'success':
                return {
                    'success': False,
                    'status': chapa_status.upper() if chapa_status else 'FAILED',
                    'message': f"Payment not successful (Chapa status: {chapa_status})"
                }

            # ============ PAYMENT SUCCEEDED ============
            try:
                transaction = PaymentTransaction.objects.get(tx_ref=transaction_id)
            except PaymentTransaction.DoesNotExist:
                logger.error(f"❌ Transaction not found in DB: {transaction_id}")
                return {
                    'success': False,
                    'status': 'FAILED',
                    'message': 'Transaction not found'
                }

            # Idempotency — don't double-process
            if transaction.status == 'PAID':
                logger.info(f"♻️ Already verified: {transaction_id}")
                return {'success': True, 'status': 'PAID', 'message': 'Already verified'}

            student = transaction.student

            # 1. Update transaction
            transaction.status = 'PAID'
            transaction.response_data = {
                **(transaction.response_data or {}),
                'verified_at': timezone.now().isoformat(),
                'chapa_data': data.get('data', {})
            }
            transaction.save()

            # 2. Create PaymentProof (only if not already created)
            proof, created = PaymentProof.objects.get_or_create(
                transaction_id=transaction_id,
                defaults={
                    'student': student,
                    'amount': transaction.amount,
                    'bank_name': 'Chapa',
                    'transaction_date': timezone.now().date(),
                    'status': 'VERIFIED',
                    'verified_at': timezone.now(),
                    'payment_type': 'SEMESTER',
                    'receipt_image': None,
                }
            )
            if created:
                logger.info(f"✅ PaymentProof created for {transaction_id}")
            else:
                logger.info(f"♻️ PaymentProof already exists for {transaction_id}")

            # 3. Update student payment status
            if student.payment_status != 'VERIFIED':
                student.payment_status = 'VERIFIED'
                student.save(update_fields=['payment_status'])
                logger.info(f"✅ Student {student.user.email} → payment_status = VERIFIED")

            # 4. Notify Finance + student
            try:
                from notifications.utils import send_notification
                send_notification(
                    recipient_user=student.user,
                    title='✅ Payment Successful',
                    message=f'Your Chapa payment of ETB {transaction.amount} has been confirmed.',
                    notification_type='PAYMENT_VERIFIED',
                    link='/dashboard'
                )
                send_notification(
                    recipient_roles=['FINANCE'],
                    title='💳 Chapa Payment Received',
                    message=f'{student.user.full_name} paid ETB {transaction.amount} via Chapa.',
                    notification_type='PAYMENT_VERIFIED',
                    link='/finance/dashboard'
                )
            except Exception as e:
                logger.warning(f"⚠️ Notification failed: {e}")

            return {
                'success': True,
                'status': 'PAID',
                'message': 'Payment verified successfully',
                'amount': float(transaction.amount),
                'reference': transaction_id
            }

        except requests.Timeout:
            return {'success': False, 'status': 'ERROR', 'message': 'Chapa verify timeout'}
        except requests.RequestException as e:
            logger.error(f"❌ Chapa verify network error: {e}")
            return {'success': False, 'status': 'ERROR', 'message': str(e)}
        except Exception as e:
            logger.exception(f"❌ Chapa verify unexpected error: {e}")
            return {'success': False, 'status': 'ERROR', 'message': str(e)}

    # ================================================================
    # GET PAYMENT DETAILS
    # ================================================================
    def get_payment_details(self, transaction_id, **kwargs):
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
            return {'success': False, 'message': 'Transaction not found'}

    # ================================================================
    # INSTRUCTIONS
    # ================================================================
    def get_payment_instructions(self, amount, reference):
        mode = "🧪 TEST MODE" if self.is_test_mode else "🟢 LIVE MODE"
        return f"""
{mode} — Chapa Payment

Amount: ETB {amount}
Reference: {reference}

Click "Pay with Chapa" to be redirected to Chapa's secure
payment page. You can pay using:
  • Telebirr
  • CBEBirr
  • Credit/Debit Card

{"⚠️ TEST MODE: No real money will be charged." if self.is_test_mode else ""}
"""