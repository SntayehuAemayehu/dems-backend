# payments/admin.py

from django.contrib import admin
from .models import PaymentProof, Invoice, PaymentTransaction

@admin.register(PaymentProof)
class PaymentProofAdmin(admin.ModelAdmin):
    list_display = ('student', 'transaction_id', 'amount', 'payment_type', 'status', 'uploaded_at')
    list_filter = ('status', 'payment_type', 'uploaded_at')
    search_fields = ('student__user__full_name', 'transaction_id', 'bank_name')
    readonly_fields = ('uploaded_at',)

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'student', 'semester', 'total_amount', 'balance_due', 'status')
    list_filter = ('status', 'semester')
    search_fields = ('invoice_number', 'student__user__full_name')

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('tx_ref', 'student', 'amount', 'payment_method', 'status', 'created_at')
    list_filter = ('status', 'payment_method')
    search_fields = ('tx_ref', 'student__user__full_name')