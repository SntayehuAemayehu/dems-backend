# payments/views.py - COMPLETE FIXED WITH FINANCE VERIFICATION
from .payment_methods import get_all_payment_methods, get_payment_method
from .payment_methods.bank_transfer import BankTransferMethod
from .payment_methods.telebirr import TelebirrMethod
from .payment_methods.chapa import ChapaMethod
from .payment_methods.stripe import StripeMethod
from .payment_methods.simulate import SimulateMethod
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import connection
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import FileResponse
from django.conf import settings
import qrcode
from io import BytesIO
from django.http import HttpResponse
from django.conf import settings
from django.shortcuts import redirect
from .models import PaymentProof, Invoice, PaymentTransaction, PaymentRollback
from .serializers import PaymentProofSerializer, InvoiceSerializer
from accounts.models import StudentProfile, Department
from notifications.utils import send_notification
from analytics.models import SystemConfig, FeeStructure
import logging
from decimal import Decimal, InvalidOperation
import traceback
import os
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
logger = logging.getLogger(__name__)

# payments/views.py - COMPLETE WITH ALL METHODS
# payments/views.py - ADD WEBHOOK HANDLERS
# payments/views.py - ADD SIMULATE PAYMENT VIEW

class SimulatePaymentView(APIView):
    """Simulate payment (Demo/Test mode)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=404)
        
        amount = request.data.get('amount', 1000)
        method_id = request.data.get('method', 'simulate')
        
        # Get simulate method
        method = get_payment_method('simulate')
        if not method:
            return Response({'error': 'Simulate method not found'}, status=400)
        
        # Initialize simulate payment
        result = method.initialize_payment(student, amount, **request.data)
        
        if result.get('success'):
            # Auto-verify the payment
            verify_result = method.verify_payment(result.get('reference'))
            
            return Response({
                'success': True,
                'message': '✅ Payment simulated successfully!',
                'reference': result.get('reference'),
                'amount': amount,
                'method': 'Demo Payment',
                'verified': True,
                'transaction_id': result.get('transaction_id')
            })
        else:
            return Response({
                'success': False,
                'error': result.get('error', 'Simulation failed'),
                'message': result.get('message', '')
            }, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
def chapa_webhook(request):
    """Handle Chapa webhook callbacks"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tx_ref = data.get('tx_ref')
            status = data.get('status')
            
            if status == 'success':
                # Update transaction status
                try:
                    transaction = PaymentTransaction.objects.get(tx_ref=tx_ref)
                    transaction.status = 'PAID'
                    transaction.save()
                    
                    # Create payment proof
                    PaymentProof.objects.create(
                        student=transaction.student,
                        transaction_id=tx_ref,
                        amount=transaction.amount,
                        bank_name='Chapa Payment',
                        transaction_date=timezone.now().date(),
                        status='VERIFIED',
                        verified_at=timezone.now(),
                        payment_type='SEMESTER'
                    )
                    
                    # Update student payment status
                    student = transaction.student
                    student.payment_status = 'VERIFIED'
                    student.save()
                    
                    return JsonResponse({'status': 'success'}, status=200)
                except PaymentTransaction.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'Transaction not found'}, status=404)
            
            return JsonResponse({'status': 'success'}, status=200)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhook callbacks"""
    if request.method == 'POST':
        try:
            payload = request.body
            sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
            
            # Verify webhook signature (optional but recommended)
            # webhook_secret = settings.STRIPE_WEBHOOK_SECRET
            # event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            
            data = json.loads(payload)
            event_type = data.get('type')
            
            if event_type == 'payment_intent.succeeded':
                payment_intent = data.get('data', {}).get('object', {})
                metadata = payment_intent.get('metadata', {})
                reference = metadata.get('reference')
                
                if reference:
                    try:
                        transaction = PaymentTransaction.objects.get(tx_ref=reference)
                        transaction.status = 'PAID'
                        transaction.save()
                        
                        # Create payment proof
                        PaymentProof.objects.create(
                            student=transaction.student,
                            transaction_id=reference,
                            amount=transaction.amount,
                            bank_name='Stripe Payment',
                            transaction_date=timezone.now().date(),
                            status='VERIFIED',
                            verified_at=timezone.now(),
                            payment_type='SEMESTER'
                        )
                        
                        # Update student payment status
                        student = transaction.student
                        student.payment_status = 'VERIFIED'
                        student.save()
                        
                        return JsonResponse({'status': 'success'}, status=200)
                    except PaymentTransaction.DoesNotExist:
                        return JsonResponse({'status': 'error', 'message': 'Transaction not found'}, status=404)
            
            return JsonResponse({'status': 'success'}, status=200)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
# payments/views.py - ADD QR CODE VIEW



class GeneratePaymentQRView(APIView):
    """Generate QR Code for payment"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=404)
        
        # Get payment details
        method_id = request.query_params.get('method', 'bank_transfer')
        amount = request.query_params.get('amount', '1000')
        
        # Get payment method
        method = get_payment_method(method_id)
        if not method:
            return Response({'error': 'Payment method not found'}, status=400)
        
        # Generate payment reference
        reference = method.generate_reference(student)
        
        # Create payment data for QR
        if method_id == 'bank_transfer':
            payment_data = {
                'bank': 'Commercial Bank of Ethiopia',
                'account': '1000225566778',
                'name': 'DEMS University',
                'amount': f'ETB {amount}',
                'ref': reference,
                'type': 'Bank Transfer'
            }
        elif method_id == 'telebirr':
            payment_data = {
                'phone': '0918114545',
                'name': 'DEMS University',
                'amount': f'ETB {amount}',
                'ref': reference,
                'type': 'Telebirr'
            }
        elif method_id == 'chapa':
            payment_data = {
                'method': 'Chapa',
                'amount': f'ETB {amount}',
                'ref': reference,
                'type': 'Online Payment'
            }
        elif method_id == 'stripe':
            payment_data = {
                'method': 'Stripe',
                'amount': f'ETB {amount}',
                'ref': reference,
                'type': 'Card Payment'
            }
        else:
            payment_data = {
                'method': method.method_name,
                'amount': f'ETB {amount}',
                'ref': reference,
            }
        
        # Create QR code
        qr_data = f"DEMS Payment\nAmount: ETB {amount}\nReference: {reference}\nMethod: {method.method_name}"
        
        # Generate QR code image
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Return QR code as image
        return HttpResponse(buffer, content_type='image/png')
    
    def post(self, request):
        """Generate QR code and return as base64 for frontend"""
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=404)
        
        method_id = request.data.get('method', 'bank_transfer')
        amount = request.data.get('amount', '1000')
        
        method = get_payment_method(method_id)
        if not method:
            return Response({'error': 'Payment method not found'}, status=400)
        
        reference = method.generate_reference(student)
        
        # Create payment data
        payment_data = {
            'amount': amount,
            'reference': reference,
            'method': method.method_name,
            'method_id': method_id,
            'student': student.user.full_name,
            'student_id': student.student_id,
        }
        
        # Add method-specific details
        if method_id == 'bank_transfer':
            payment_data['bank_name'] = 'Commercial Bank of Ethiopia'
            payment_data['account_number'] = '1000225566778'
            payment_data['account_name'] = 'DEMS University'
        elif method_id == 'telebirr':
            payment_data['phone_number'] = '0918114545'
            payment_data['account_name'] = 'DEMS University'
        
        # Generate QR code
        qr_data = f"DEMS Payment\nAmount: ETB {amount}\nReference: {reference}\nMethod: {method.method_name}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        import base64
        qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return Response({
            'success': True,
            'qr_code': f'data:image/png;base64,{qr_base64}',
            'payment_data': payment_data,
            'reference': reference,
            'instructions': method.get_payment_instructions(amount, reference)
        })
class PaymentMethodsListView(APIView):
    """Get all available payment methods"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            methods = get_all_payment_methods()
            data = []
            for method in methods:
                data.append({
                    'id': method.method_id,
                    'name': method.method_name,
                    'icon': method.method_icon,
                    'enabled': True,
                    'is_test_mode': getattr(method, 'is_test_mode', False)
                })
            return Response(data)
        except Exception as e:
            logger.error(f"Error fetching payment methods: {e}")
            # Return default methods if there's an error
            default_methods = [
                {'id': 'bank_transfer', 'name': 'Bank Transfer', 'icon': '🏦', 'enabled': True},
                {'id': 'telebirr', 'name': 'Telebirr', 'icon': '📱', 'enabled': True},
                {'id': 'chapa', 'name': 'Chapa', 'icon': '💳', 'enabled': True},
                {'id': 'stripe', 'name': 'Stripe', 'icon': '💳', 'enabled': True},
                {'id': 'simulate', 'name': 'Demo Payment', 'icon': '🧪', 'enabled': True},
            ]
            return Response(default_methods)


# payments/views.py - FIX PaymentInitializeView

class PaymentInitializeView(APIView):
    """Initialize payment with selected method"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=404)
        
        method_id = request.data.get('method', 'bank_transfer')
        amount = request.data.get('amount', 1000)
        
        # Get the payment method
        method = get_payment_method(method_id)
        if not method:
            return Response({'error': 'Payment method not found'}, status=400)
        
        # Initialize payment
        result = method.initialize_payment(student, amount, **request.data)
        
        if result.get('success'):
            return Response(result)
        else:
            return Response({
                'success': False,
                'error': result.get('error', 'Payment initialization failed'),
                'message': result.get('message', '')
            }, status=status.HTTP_400_BAD_REQUEST)

class PaymentVerifyView(APIView):
    """Verify a payment"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        transaction_id = request.data.get('transaction_id')
        method_id = request.data.get('method', 'bank_transfer')
        
        if not transaction_id:
            return Response({'error': 'Transaction ID required'}, status=400)
        
        method = get_payment_method(method_id)
        if not method:
            return Response({'error': 'Payment method not found'}, status=400)
        
        result = method.verify_payment(transaction_id)
        
        return Response(result)


class PaymentDetailsView(APIView):
    """Get payment details"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, transaction_id):
        method_id = request.query_params.get('method', 'bank_transfer')
        
        method = get_payment_method(method_id)
        if not method:
            return Response({'error': 'Payment method not found'}, status=400)
        
        result = method.get_payment_details(transaction_id)
        return Response(result)


class PaymentStatusView(APIView):
    """Get student's payment status"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({
                'is_verified': False,
                'status': 'NO_PROFILE',
                'message': 'Student profile not found'
            })
        
        # Get payment verification status
        is_verified = student.payment_status == 'VERIFIED'
        
        # Get recent transactions
        transactions = PaymentTransaction.objects.filter(
            student=student
        ).order_by('-created_at')[:5]
        
        return Response({
            'is_verified': is_verified,
            'payment_status': student.payment_status,
            'student_id': student.student_id,
            'student_name': student.user.full_name,
            'recent_transactions': [
                {
                    'id': t.id,
                    'reference': t.tx_ref,
                    'amount': float(t.amount),
                    'status': t.status,
                    'method': t.payment_method,
                    'created_at': t.created_at.isoformat()
                } for t in transactions
            ]
        })





class PaymentMethodListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        methods = []
        
        bank_name = SystemConfig.get_value('bank_name', 'Commercial Bank of Ethiopia')
        account_name = SystemConfig.get_value('account_name', 'DEMS University')
        account_number = SystemConfig.get_value('payment_account', '1000225566778')
        
        if account_number:
            methods.append({
                'id': 1,
                'name': 'Bank Transfer',
                'bank_name': bank_name,
                'account_name': account_name,
                'account_number': account_number,
                'instructions': SystemConfig.get_value('payment_instructions', 'Please make payment to the above account and upload the receipt for verification.')
            })
        
        phone_number = SystemConfig.get_value('payment_phone', '0918114545')
        if phone_number:
            methods.append({
                'id': 2,
                'name': 'Telebirr',
                'phone_number': phone_number,
                'account_name': 'Telebirr Account',
                'instructions': f'Send payment to {phone_number} via Telebirr and upload the transaction receipt.'
            })
        
        return Response(methods)


class PaymentProofUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            try:
                student = StudentProfile.objects.get(user=request.user)
            except StudentProfile.DoesNotExist:
                student = StudentProfile.objects.create(
                    user=request.user,
                    payment_status='PENDING'
                )
                logger.info(f"Created StudentProfile for user: {request.user.email}")
            
            if 'receipt_image' not in request.FILES:
                return Response(
                    {'error': 'Receipt image is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            receipt_file = request.FILES['receipt_image']
            
            if receipt_file.size > 10 * 1024 * 1024:
                return Response(
                    {'error': 'File size exceeds 10MB limit'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf']
            if receipt_file.content_type not in allowed_types:
                return Response(
                    {'error': 'Invalid file type. Please upload JPG, PNG, or PDF.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            transaction_id = request.data.get('transaction_id')
            amount = request.data.get('amount')
            bank_name = request.data.get('bank_name', '')
            transaction_date = request.data.get('transaction_date')
            payment_type = request.data.get('payment_type', 'SEMESTER')
            semester = request.data.get('semester', '')
            academic_year = request.data.get('academic_year', '')
            
            if not transaction_id or not amount or not transaction_date:
                return Response(
                    {'error': 'Transaction ID, Amount, and Date are required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                amount_decimal = Decimal(str(amount))
            except (InvalidOperation, ValueError, TypeError):
                return Response(
                    {'error': 'Invalid amount format. Please enter a valid number.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            payment_proof = PaymentProof(
                student=student,
                transaction_id=transaction_id,
                amount=amount_decimal,
                bank_name=bank_name,
                transaction_date=transaction_date,
                payment_type=payment_type,
                semester=semester,
                academic_year=academic_year,
                receipt_image=receipt_file
            )
            
            payment_proof.save()
            
            # Send notifications
            send_notification(
                recipient_user=student.user,
                title='💰 Payment Proof Received',
                message=f'Your payment of ETB {amount} has been received and is pending verification.',
                notification_type='PAYMENT_PENDING',
                link='/payments'
            )
            
            send_notification(
                recipient_roles=['FINANCE'],
                title='📤 New Payment Proof Uploaded',
                message=f'Student {student.user.full_name} has uploaded a payment proof of ETB {amount} for verification.',
                notification_type='PAYMENT_PENDING',
                link='/finance/dashboard'
            )
            
            send_notification(
                recipient_roles=['ADMIN'],
                title='📤 New Payment Uploaded',
                message=f'Student {student.user.full_name} uploaded payment proof of ETB {amount}.',
                notification_type='SYSTEM_ALERT',
                link='/admin/dashboard'
            )
            
            serializer = PaymentProofSerializer(payment_proof)
            return Response({
                'message': 'Payment proof uploaded successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error in payment upload: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# payments/views.py - COMPLETE FIXED PaymentProofListView

class PaymentProofListView(APIView):
    """List payment proofs - WITH FULL ACCESS FOR FINANCE"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            user = request.user
            
            # Build query with proper joins
            sql = """
                SELECT 
                    pp.id,
                    pp.transaction_id,
                    pp.amount,
                    pp.bank_name,
                    pp.status,
                    pp.receipt_image,
                    pp.uploaded_at,
                    pp.rejection_reason,
                    pp.payment_type,
                    pp.semester,
                    pp.academic_year,
                    pp.verified_at,
                    u.id as student_user_id,
                    u.full_name as student_name,
                    sp.student_id,
                    vu.full_name as verified_by_name
                FROM payments_paymentproof pp
                LEFT JOIN accounts_studentprofile sp ON pp.student_id = sp.id
                LEFT JOIN accounts_user u ON sp.user_id = u.id
                LEFT JOIN accounts_user vu ON pp.verified_by_id = vu.id
            """
            
            where_clauses = []
            params = []
            
            # STUDENT: Only see their own payments
            if user.role == 'STUDENT':
                try:
                    student = StudentProfile.objects.get(user=user)
                    where_clauses.append("pp.student_id = %s")
                    params.append(student.id)
                except StudentProfile.DoesNotExist:
                    return Response([], status=status.HTTP_200_OK)
            
            # FINANCE, ADMIN, REGISTRAR: See all payments
            elif user.role in ['FINANCE', 'ADMIN', 'REGISTRAR', 'DEPT_HEAD']:
                status_filter = request.query_params.get('status')
                if status_filter:
                    where_clauses.append("pp.status = %s")
                    params.append(status_filter)
                
                search = request.query_params.get('search')
                if search:
                    where_clauses.append("u.full_name LIKE %s")
                    params.append(f'%{search}%')
            
            else:
                return Response([], status=status.HTTP_200_OK)
            
            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)
            
            sql += " ORDER BY pp.uploaded_at DESC"
            
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
            
            # Build full URLs for receipt images
            result = []
            for row in rows:
                receipt_url = None
                if row[5]:  # receipt_image field
                    try:
                        # ✅ FIX: Build correct URL using MEDIA_URL
                        # row[5] contains the relative path like "payment_receipts/filename.jpg"
                        receipt_url = request.build_absolute_uri(
                            settings.MEDIA_URL + str(row[5])
                        )
                    except Exception as e:
                        print(f"Error building receipt URL: {e}")
                        receipt_url = None
                
                amount = float(row[2]) if row[2] is not None else 0.0
                
                result.append({
                    'id': row[0],
                    'transaction_id': row[1] or '',
                    'amount': amount,
                    'bank_name': row[3] or '',
                    'status': row[4] or 'PENDING',
                    'receipt_image': receipt_url,
                    'receipt_url': receipt_url,  # For frontend compatibility
                    'uploaded_at': row[6].isoformat() if row[6] else None,
                    'rejection_reason': row[7] or '',
                    'payment_type': row[8] or 'SEMESTER',
                    'semester': row[9] or '',
                    'academic_year': row[10] or '',
                    'verified_at': row[11].isoformat() if row[11] else None,
                    'student_name': row[13] or 'Unknown',
                    'student_id': row[14] or '',
                    'verified_by': row[15] or None,
                })
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error in PaymentProofListView: {e}")
            return Response([], status=status.HTTP_200_OK)
# backend/payments/views.py
# UPDATE PaymentProofVerifyView

# backend/payments/views.py
# REPLACE ONLY THE approve action in PaymentProofVerifyView

# backend/payments/views.py
# REPLACE ONLY THE approve action in PaymentProofVerifyView

class PaymentProofVerifyView(APIView):
    """Finance verifies or rejects payment"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        if request.user.role not in ['FINANCE', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Finance officers can verify payments.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            payment_proof = PaymentProof.objects.get(id=pk)
        except PaymentProof.DoesNotExist:
            return Response(
                {'error': 'Payment proof not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        action = request.data.get('action')
        
        if action == 'approve':
            # ✅ MARK PAYMENT AS VERIFIED
            payment_proof.status = 'VERIFIED'
            payment_proof.verified_by = request.user
            payment_proof.verified_at = timezone.now()
            payment_proof.save()
            
            student = payment_proof.student
            student.payment_status = 'VERIFIED'
            student.save()
            
            # ✅ ============================================================
            # ✅ CHECK: Is student ALREADY ACTIVATED? (RESTORATION)
            # ✅ ============================================================
            from analytics.models import StudentPaymentSchedule
            from analytics.models import StudentServiceAccess
            
            # Check if student is ALREADY ACTIVATED
            is_already_activated = student.is_enrolled
            
            if is_already_activated:
                # ✅ ============================================================
                # ✅ ACCOUNT RESTORATION - AUTO-RESTORE ALL SERVICES
                # ✅ ============================================================
                
                # Find locked/overdue schedules
                locked_schedules = StudentPaymentSchedule.objects.filter(
                    student=student,
                    status__in=['LOCKED', 'OVERDUE', 'PENDING']
                )
                
                unlocked_count = 0
                for schedule in locked_schedules:
                    schedule.mark_paid()  # ✅ Marks as PAID and restores access
                    unlocked_count += 1
                
                # ✅ RESTORE ALL SERVICE ACCESS
                StudentServiceAccess.objects.filter(
                    student=student,
                    is_allowed=False
                ).update(is_allowed=True)
                
                # ✅ SEND NOTIFICATION - ACCESS RESTORED
                send_notification(
                    recipient_user=student.user,
                    title='✅ Payment Verified - Access Restored!',
                    message=f'Your payment of ETB {payment_proof.amount} has been verified. ALL services are now restored!',
                    notification_type='PAYMENT_VERIFIED',
                    link='/dashboard'
                )
                
                # ✅ LOG THE ACTION
                from analytics.models import SystemLog
                SystemLog.objects.create(
                    user=request.user,
                    action=f'PAYMENT_RESTORED_ACCESS: {student.user.email}',
                    details={
                        'student': student.user.full_name,
                        'amount': float(payment_proof.amount),
                        'unlocked_schedules': unlocked_count,
                        'flow': 'RESTORATION',
                        'access_restored': True
                    },
                    log_level='INFO'
                )
                
                return Response({
                    'message': 'Payment approved - Access RESTORED!',
                    'student_id': student.student_id,
                    'payment_status': student.payment_status,
                    'access_restored': True,
                    'flow': 'RESTORATION',
                    'unlocked_schedules': unlocked_count,
                    'receipt_url': payment_proof.receipt_image.url if payment_proof.receipt_image else None
                })
            
            else:
                # ✅ ============================================================
                # ✅ FIRST-TIME REGISTRATION - KEEP EXISTING FLOW
                # ✅ ============================================================
                
                # Notify Registrar to start document verification
                send_notification(
                    recipient_roles=['REGISTRAR'],
                    title='🎓 Student Payment Verified - Ready for Document Verification',
                    message=f'Student {student.user.full_name} payment of ETB {payment_proof.amount} has been verified. Ready for document upload.',
                    notification_type='PAYMENT_VERIFIED',
                    link='/registrar/dashboard'
                )
                
                # Notify student to upload documents
                send_notification(
                    recipient_user=student.user,
                    title='✅ Payment Verified! Upload Your Documents',
                    message=f'Your payment of ETB {payment_proof.amount} has been verified. Please upload your documents for registration.',
                    notification_type='PAYMENT_VERIFIED',
                    link='/upload-documents'
                )
                
                return Response({
                    'message': 'Payment approved - Please upload documents',
                    'student_id': student.student_id,
                    'payment_status': student.payment_status,
                    'access_restored': False,
                    'flow': 'FIRST_TIME_REGISTRATION',
                    'next_step': 'DOCUMENT_UPLOAD',
                    'receipt_url': payment_proof.receipt_image.url if payment_proof.receipt_image else None
                })
        
        elif action == 'reject':
            reason = request.data.get('reason', 'No reason provided')
            payment_proof.status = 'REJECTED'
            payment_proof.rejection_reason = reason
            payment_proof.verified_by = request.user
            payment_proof.verified_at = timezone.now()
            payment_proof.save()
            
            send_notification(
                recipient_user=payment_proof.student.user,
                title='❌ Payment Rejected',
                message=f'Your payment of ETB {payment_proof.amount} has been rejected. Reason: {reason}',
                notification_type='PAYMENT_REJECTED',
                link='/payments'
            )
            
            return Response({'message': 'Payment rejected'})
        
        elif action == 'need_resubmission':
            reason = request.data.get('reason', 'Please upload a clearer image')
            payment_proof.status = 'NEED_RESUBMISSION'
            payment_proof.rejection_reason = reason
            payment_proof.save()
            
            send_notification(
                recipient_user=payment_proof.student.user,
                title='📤 Payment Resubmission Required',
                message=f'Your payment proof needs resubmission. Reason: {reason}',
                notification_type='PAYMENT_RESUBMIT',
                link='/payments'
            )
            
            return Response({'message': 'Requested resubmission'})
        
        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)
class MyBalanceView(APIView):
    """Get student's balance"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({'balance_due': 0, 'payment_status': 'PENDING'})
        
        # ✅ Check if student has overdue payments
        from analytics.models import StudentPaymentSchedule
        overdue_schedules = StudentPaymentSchedule.objects.filter(
            student=student,
            status__in=['PENDING', 'OVERDUE']
        )
        
        total_due = 0
        for schedule in overdue_schedules:
            total_due += float(schedule.total_amount)
        
        return Response({
            'balance_due': total_due,
            'payment_status': student.payment_status,
            'is_enrolled': student.is_enrolled,
            'student_id': student.student_id
        })


class InvoiceListView(APIView):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        sql = """
            SELECT 
                i.id,
                i.invoice_number,
                i.semester,
                i.academic_year,
                i.issue_date,
                i.due_date,
                i.subtotal,
                i.total_amount,
                i.amount_paid,
                i.balance_due,
                i.status,
                i.created_at,
                u.full_name as student_name,
                sp.student_id
            FROM payments_invoice i
            LEFT JOIN accounts_studentprofile sp ON i.student_id = sp.id
            LEFT JOIN accounts_user u ON sp.user_id = u.id
        """
        
        where_clauses = []
        params = []
        
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                where_clauses.append("i.student_id = %s")
                params.append(student.id)
            except StudentProfile.DoesNotExist:
                return Response([], status=status.HTTP_200_OK)
        elif user.role not in ['FINANCE', 'ADMIN']:
            return Response([], status=status.HTTP_200_OK)
        
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        
        sql += " ORDER BY i.created_at DESC"
        
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        
        result = []
        for row in rows:
            try:
                result.append({
                    'id': row[0],
                    'invoice_number': row[1] or '',
                    'semester': row[2] or '',
                    'academic_year': row[3] or '',
                    'issue_date': row[4].isoformat() if row[4] else None,
                    'due_date': row[5].isoformat() if row[5] else None,
                    'subtotal': float(row[6]) if row[6] is not None else 0.0,
                    'total_amount': float(row[7]) if row[7] is not None else 0.0,
                    'amount_paid': float(row[8]) if row[8] is not None else 0.0,
                    'balance_due': float(row[9]) if row[9] is not None else 0.0,
                    'status': row[10] or 'PENDING',
                    'created_at': row[11].isoformat() if row[11] else None,
                    'student_name': row[12] or 'Unknown',
                    'student_id': row[13] or '',
                })
            except Exception as e:
                logger.error(f"Error processing invoice: {e}")
                continue
        
        return Response(result, status=status.HTTP_200_OK)


class GenerateInvoiceView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, student_id):
        if request.user.role not in ['FINANCE', 'ADMIN']:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': 'Student not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        semester = request.data.get('semester', '1')
        academic_year = request.data.get('academic_year', str(timezone.now().year))
        total_amount = request.data.get('total_amount', 0)
        
        invoice_count = Invoice.objects.count() + 1
        invoice_number = f"INV-{timezone.now().year}-{student_id:06d}-{invoice_count:04d}"
        
        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            student=student,
            semester=semester,
            academic_year=academic_year,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=30),
            subtotal=total_amount,
            total_amount=total_amount,
            amount_paid=0,
            balance_due=total_amount,
            status='PENDING'
        )
        
        send_notification(
            recipient_user=student.user,
            title='📄 New Invoice Generated',
            message=f'Invoice {invoice_number} for Semester {semester} has been generated. Amount: ETB {total_amount}',
            notification_type='SYSTEM_ALERT',
            link='/payments'
        )
        
        return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)


# payments/views.py - Update PaymentReceiptView

class PaymentReceiptView(APIView):
    """Get payment receipt image URL"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, payment_id):
        try:
            payment = PaymentProof.objects.get(id=payment_id)
        except PaymentProof.DoesNotExist:
            return Response(
                {'error': 'Payment not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permission
        user = request.user
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                if payment.student != student:
                    return Response(
                        {'error': 'Permission denied'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'Permission denied'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        elif user.role not in ['ADMIN', 'FINANCE', 'REGISTRAR', 'DEPT_HEAD']:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not payment.receipt_image:
            return Response(
                {'error': 'No receipt found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # ✅ FIX: Build correct URL using MEDIA_URL
        receipt_url = request.build_absolute_uri(
            settings.MEDIA_URL + str(payment.receipt_image)
        )
        
        return Response({
            'receipt_url': receipt_url,
            'transaction_id': payment.transaction_id,
            'student_name': payment.student.user.full_name,
            'amount': str(payment.amount),
            'status': payment.status,
            'uploaded_at': payment.uploaded_at.isoformat() if payment.uploaded_at else None,
            'bank_name': payment.bank_name
        }, status=status.HTTP_200_OK)
class CancelPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def delete(self, request, payment_id):
        try:
            payment = PaymentProof.objects.get(id=payment_id)
        except PaymentProof.DoesNotExist:
            return Response(
                {'error': 'Payment not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        user = request.user
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                if payment.student != student:
                    return Response(
                        {'error': 'Permission denied'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'Permission denied'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        elif user.role not in ['ADMIN']:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if payment.status != 'PENDING':
            return Response(
                {'error': 'Only pending payments can be cancelled'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment.delete()
        return Response(
            {'message': 'Payment cancelled successfully'}, 
            status=status.HTTP_200_OK
        )


class StudentPaymentStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({
                'total_payments': 0,
                'total_amount': 0,
                'pending': 0,
                'verified': 0,
                'rejected': 0,
            })
        
        payments = PaymentProof.objects.filter(student=student)
        
        total_amount = 0
        for p in payments:
            try:
                if p.amount is not None:
                    total_amount += float(p.amount)
            except (ValueError, TypeError, InvalidOperation):
                pass
        
        pending = payments.filter(status='PENDING').count()
        verified = payments.filter(status='VERIFIED').count()
        rejected = payments.filter(status='REJECTED').count()
        
        return Response({
            'total_payments': payments.count(),
            'total_amount': total_amount,
            'pending': pending,
            'verified': verified,
            'rejected': rejected,
        })


class StudentFeeAmountView(APIView):
    """Get the fee amount for a student based on their department"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            student = StudentProfile.objects.get(user=request.user)
            
            department_name = student.department
            if not department_name:
                return Response({
                    'amount': 0,
                    'message': 'No department assigned',
                    'has_fee_structure': False
                }, status=status.HTTP_200_OK)
            
            try:
                department = Department.objects.get(name=department_name)
            except Department.DoesNotExist:
                return Response({
                    'amount': 0,
                    'message': 'Department not found',
                    'has_fee_structure': False
                }, status=status.HTTP_200_OK)
            
            try:
                fee_structure = FeeStructure.objects.filter(
                    department=department,
                    is_active=True
                ).first()
                
                if fee_structure:
                    return Response({
                        'amount': float(fee_structure.amount),
                        'payment_period': fee_structure.payment_period.name if fee_structure.payment_period else None,
                        'payment_period_display': fee_structure.payment_period.name if fee_structure.payment_period else None,
                        'department': department_name,
                        'has_fee_structure': True,
                        'penalty_per_day': float(fee_structure.penalty_per_day),
                        'grace_period_days': fee_structure.grace_period_days,
                        'fee_structure_id': fee_structure.id
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'amount': 0,
                        'message': 'No active fee structure for this department',
                        'has_fee_structure': False
                    }, status=status.HTTP_200_OK)
                    
            except FeeStructure.DoesNotExist:
                return Response({
                    'amount': 0,
                    'message': 'No fee structure found for this department',
                    'has_fee_structure': False
                }, status=status.HTTP_200_OK)
                
        except StudentProfile.DoesNotExist:
            return Response({
                'error': 'Student profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
 # payments/views.py - ADD PAYMENT ROLLBACK VIEW

# payments/views.py - ADD THESE VIEWS (Append to existing file)

from django.db import transaction
from django.db.models import Sum, Q

class PaymentRollbackView(APIView):
    """Rollback a payment - Finance or Admin only"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, payment_id):
        # Check permission
        if request.user.role not in ['FINANCE', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Finance or Admin can rollback payments.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            payment = PaymentProof.objects.get(id=payment_id)
        except PaymentProof.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already rolled back
        if payment.is_rolled_back:
            return Response(
                {'error': 'Payment already rolled back'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if can rollback
        if payment.status not in ['VERIFIED', 'PENDING', 'NEED_RESUBMISSION']:
            return Response(
                {'error': f'Cannot rollback payment with status: {payment.status}. Only VERIFIED, PENDING, or NEED_RESUBMISSION payments can be rolled back.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get rollback data
        reason = request.data.get('reason', '')
        notes = request.data.get('notes', '')
        rollback_type = request.data.get('rollback_type', 'FULL')
        
        if not reason:
            return Response(
                {'error': 'Reason for rollback is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Perform rollback
                payment.rollback(request.user, reason, notes)
                
                # Send notification to student
                send_notification(
                    recipient_user=payment.student.user,
                    title='🔄 Payment Rolled Back',
                    message=f'Your payment of ETB {payment.amount} has been rolled back. Reason: {reason}',
                    notification_type='SYSTEM_ALERT',
                    link='/payments'
                )
                
                # Notify Finance team
                send_notification(
                    recipient_roles=['FINANCE', 'ADMIN'],
                    title='🔄 Payment Rolled Back',
                    message=f'Payment of ETB {payment.amount} for {payment.student.user.full_name} has been rolled back by {request.user.full_name}. Reason: {reason}',
                    notification_type='SYSTEM_ALERT',
                    link='/finance/dashboard'
                )
                
                # Log the action
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Payment {payment.id} rolled back by {request.user.full_name}. Reason: {reason}")
                
                return Response({
                    'success': True,
                    'message': 'Payment rolled back successfully',
                    'payment_id': payment.id,
                    'transaction_id': payment.transaction_id,
                    'amount': str(payment.amount),
                    'student': payment.student.user.full_name,
                    'student_id': payment.student.student_id,
                    'rollback_reason': reason,
                    'rolled_back_at': payment.rolled_back_at.isoformat() if payment.rolled_back_at else None,
                    'original_status': payment.original_status,
                })
                
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Failed to rollback payment {payment_id}: {e}")
            return Response(
                {'error': f'Failed to rollback payment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentRollbackListView(APIView):
    """List all payment rollbacks"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        if request.user.role not in ['FINANCE', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Finance or Admin can view rollbacks.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        rollbacks = PaymentRollback.objects.all().select_related('payment', 'student', 'rolled_by').order_by('-created_at')
        
        result = []
        for rollback in rollbacks:
            result.append({
                'id': rollback.id,
                'payment_id': rollback.payment.id,
                'transaction_id': rollback.payment.transaction_id,
                'student_name': rollback.student.user.full_name if rollback.student else 'Unknown',
                'student_id': rollback.student.student_id if rollback.student else '',
                'amount': float(rollback.amount),
                'rolled_by': rollback.rolled_by.full_name if rollback.rolled_by else 'System',
                'reason': rollback.reason,
                'rollback_type': rollback.rollback_type,
                'original_status': rollback.original_status,
                'created_at': rollback.created_at.isoformat(),
                'notes': rollback.notes,
            })
        
        return Response(result)


class PaymentReversalView(APIView):
    """Reverse a rollback (restore payment) - Admin only"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, payment_id):
        if request.user.role != 'ADMIN':
            return Response(
                {'error': 'Permission denied. Only Admin can reverse rollbacks.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            payment = PaymentProof.objects.get(id=payment_id)
        except PaymentProof.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not payment.is_rolled_back:
            return Response(
                {'error': 'Payment is not rolled back'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'Rollback reversed by Admin')
        
        try:
            with transaction.atomic():
                # Restore original status
                payment.status = payment.original_status if payment.original_status else 'PENDING'
                payment.is_rolled_back = False
                payment.rolled_back_by = None
                payment.rolled_back_at = None
                payment.rollback_reason = ''
                payment.rollback_notes = ''
                
                # Restore student payment status
                if payment.original_payment_status:
                    payment.student.payment_status = payment.original_payment_status
                    payment.student.save()
                
                payment.save()
                
                # Create reversal record
                PaymentRollback.objects.create(
                    payment=payment,
                    student=payment.student,
                    rolled_by=request.user,
                    reason=f"Rollback reversed: {reason}",
                    amount=payment.amount,
                    original_status='ROLLED_BACK',
                    rollback_type='ADMIN',
                    notes=f"Reversed previous rollback. {reason}"
                )
                
                send_notification(
                    recipient_user=payment.student.user,
                    title='🔄 Rollback Reversed',
                    message=f'The rollback of your payment ETB {payment.amount} has been reversed by Admin.',
                    notification_type='SYSTEM_ALERT',
                    link='/payments'
                )
                
                return Response({
                    'success': True,
                    'message': 'Rollback reversed successfully',
                    'payment_id': payment.id,
                    'status': payment.status,
                })
                
        except Exception as e:
            return Response(
                {'error': f'Failed to reverse rollback: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CheckPaymentRollbackView(APIView):
    """Check if a payment can be rolled back"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, payment_id):
        try:
            payment = PaymentProof.objects.get(id=payment_id)
        except PaymentProof.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        can_rollback = (
            not payment.is_rolled_back and 
            payment.status in ['VERIFIED', 'PENDING', 'NEED_RESUBMISSION']
        )
        
        return Response({
            'can_rollback': can_rollback,
            'is_rolled_back': payment.is_rolled_back,
            'status': payment.status,
            'reason': 'Payment can be rolled back' if can_rollback else f'Payment status: {payment.status}, Rolled back: {payment.is_rolled_back}'
        })
 # payments/views.py - ADD THIS MISSING VIEW

# payments/views.py - PaymentReceiptDownloadView

class PaymentReceiptDownloadView(APIView):
    """Download payment receipt as a file"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, payment_id):
        try:
            payment = PaymentProof.objects.get(id=payment_id)
        except PaymentProof.DoesNotExist:
            return Response(
                {'error': 'Payment not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permission
        user = request.user
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                if payment.student != student:
                    return Response(
                        {'error': 'Permission denied'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'Permission denied'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        elif user.role not in ['ADMIN', 'FINANCE', 'REGISTRAR', 'DEPT_HEAD']:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not payment.receipt_image:
            return Response(
                {'error': 'No receipt found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # ✅ FIX: Return the file for download
        from django.http import FileResponse
        import os
        
        file_path = payment.receipt_image.path
        if os.path.exists(file_path):
            response = FileResponse(
                open(file_path, 'rb'),
                content_type='application/octet-stream',
                as_attachment=True,
                filename=f"receipt_{payment.transaction_id}.{os.path.splitext(payment.receipt_image.name)[1]}"
            )
            return response
        else:
            return Response(
                {'error': 'Receipt file not found on server'}, 
                status=status.HTTP_404_NOT_FOUND
            )