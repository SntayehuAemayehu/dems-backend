# payments/payment_methods/base.py

from abc import ABC, abstractmethod
from django.utils import timezone
import uuid

class BasePaymentMethod(ABC):
    """Base class for all payment methods"""
    
    def __init__(self):
        self.method_id = None
        self.method_name = None
        self.method_icon = None
    
    @abstractmethod
    def initialize_payment(self, student, amount, **kwargs):
        """Initialize a payment"""
        pass
    
    @abstractmethod
    def verify_payment(self, transaction_id, **kwargs):
        """Verify a payment"""
        pass
    
    @abstractmethod
    def get_payment_details(self, transaction_id, **kwargs):
        """Get payment details"""
        pass
    
    def generate_reference(self, student):
        """Generate unique payment reference"""
        return f"{self.method_id.upper()}-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    def get_metadata(self):
        """Get method metadata"""
        return {
            'id': self.method_id,
            'name': self.method_name,
            'icon': self.method_icon,
            'enabled': True
        }