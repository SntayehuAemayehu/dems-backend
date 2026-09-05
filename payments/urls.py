# payments/urls.py - ADD WEBHOOK URLS

from django.urls import path
from . import views

urlpatterns = [
    # ============ PAYMENT METHODS ============
    path('methods/', views.PaymentMethodsListView.as_view(), name='payment-methods'),
    path('methods/legacy/', views.PaymentMethodListView.as_view(), name='payment-methods-legacy'),
    
    # ============ PAYMENT FLOW ============
    path('initialize/', views.PaymentInitializeView.as_view(), name='payment-initialize'),
    path('verify/', views.PaymentVerifyView.as_view(), name='payment-verify'),
    path('status/', views.PaymentStatusView.as_view(), name='payment-status'),
    path('<str:transaction_id>/details/', views.PaymentDetailsView.as_view(), name='payment-details'),
    # ============ QR CODE ============
    path('qr/generate/', views.GeneratePaymentQRView.as_view(), name='generate-qr'),
    path('qr/image/', views.GeneratePaymentQRView.as_view(), name='qr-image'),
    
    # ============ SIMULATE PAYMENT ============
    path('simulate/', views.SimulatePaymentView.as_view(), name='simulate-payment'),
    # ============ WEBHOOKS ============
    path('webhook/chapa/', views.chapa_webhook, name='chapa-webhook'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe-webhook'),
    
    # ============ PROOF UPLOAD ============
    path('proofs/upload/', views.PaymentProofUploadView.as_view(), name='upload-proof'),
    path('proofs/', views.PaymentProofListView.as_view(), name='proofs-list'),
    path('proofs/<int:pk>/verify/', views.PaymentProofVerifyView.as_view(), name='verify-proof'),
    
    # ============ BALANCE & INVOICES ============
    path('balance/', views.MyBalanceView.as_view(), name='my-balance'),
    path('invoices/', views.InvoiceListView.as_view(), name='invoices'),
    path('invoices/generate/<int:student_id>/', views.GenerateInvoiceView.as_view(), name='generate-invoice'),
    
    # ============ RECEIPTS ============
    path('<int:payment_id>/receipt/', views.PaymentReceiptView.as_view(), name='payment-receipt'),
    path('<int:payment_id>/receipt/download/', views.PaymentReceiptDownloadView.as_view(), name='payment-receipt-download'),
    
    # ============ ROLLBACK ============
    path('<int:payment_id>/rollback/', views.PaymentRollbackView.as_view(), name='payment-rollback'),
    path('rollbacks/', views.PaymentRollbackListView.as_view(), name='payment-rollbacks'),
    path('<int:payment_id>/check-rollback/', views.CheckPaymentRollbackView.as_view(), name='check-rollback'),
    path('<int:payment_id>/reverse-rollback/', views.PaymentReversalView.as_view(), name='reverse-rollback'),
    
    # ============ STATS ============
    path('stats/', views.StudentPaymentStatsView.as_view(), name='payment-stats'),
    path('fee-amount/', views.StudentFeeAmountView.as_view(), name='student-fee-amount'),
    path('<int:payment_id>/cancel/', views.CancelPaymentView.as_view(), name='cancel-payment'),
]