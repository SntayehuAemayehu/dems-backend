# payments/payment_methods/__init__.py

from .bank_transfer import BankTransferMethod
from .telebirr import TelebirrMethod
from .chapa import ChapaMethod
from .stripe import StripeMethod
from .simulate import SimulateMethod

def get_all_payment_methods():
    """Get all registered payment methods"""
    return [
        BankTransferMethod(),
        TelebirrMethod(),
        ChapaMethod(),
        StripeMethod(),
        SimulateMethod()
    ]

def get_payment_method(method_id):
    """Get a specific payment method by ID"""
    for method in get_all_payment_methods():
        if method.method_id == method_id:
            return method
    return None

# Export all methods
__all__ = [
    'BankTransferMethod',
    'TelebirrMethod',
    'ChapaMethod',
    'StripeMethod',
    'SimulateMethod',
    'get_all_payment_methods',
    'get_payment_method'
]