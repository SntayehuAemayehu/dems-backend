# backend/services/currency_service.py
# COMPLETE CURRENCY MANAGEMENT SYSTEM

from django.conf import settings
import requests
import json
import logging

logger = logging.getLogger(__name__)

class CurrencyService:
    """Multi-currency support for payments and display"""
    
    def __init__(self):
        # Base currency (Ethiopian Birr)
        self.base_currency = 'ETB'
        
        # Cache exchange rates
        self.exchange_rates = None
        self.rates_updated = None
        
        # Supported currencies
        self.supported_currencies = [
            {'code': 'ETB', 'name': 'Ethiopian Birr', 'symbol': 'Br', 'country': 'Ethiopia'},
            {'code': 'USD', 'name': 'US Dollar', 'symbol': '$', 'country': 'United States'},
            {'code': 'EUR', 'name': 'Euro', 'symbol': '€', 'country': 'European Union'},
            {'code': 'GBP', 'name': 'British Pound', 'symbol': '£', 'country': 'United Kingdom'},
            {'code': 'CNY', 'name': 'Chinese Yuan', 'symbol': '¥', 'country': 'China'},
            {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥', 'country': 'Japan'},
        ]
    
    def convert_amount(self, amount, from_currency='ETB', to_currency='ETB'):
        """Convert amount between currencies"""
        if from_currency == to_currency:
            return amount
        
        # Get exchange rates
        rates = self.get_exchange_rates()
        
        if from_currency in rates and to_currency in rates:
            # Convert to base (ETB) first
            base_amount = amount / rates[from_currency]
            # Convert to target
            result = base_amount * rates[to_currency]
            return round(result, 2)
        
        return amount
    
    def get_exchange_rates(self):
        """Get exchange rates (cached)"""
        import datetime
        
        # Refresh rates if older than 1 hour
        if not self.exchange_rates or (self.rates_updated and 
            (datetime.datetime.now() - self.rates_updated).total_seconds() > 3600):
            self._fetch_exchange_rates()
        
        return self.exchange_rates or {'ETB': 1.0}
    
    def _fetch_exchange_rates(self):
        """Fetch live exchange rates from API"""
        try:
            # Try to fetch from API (using open exchange rates or similar)
            response = requests.get(
                f"https://open.er-api.com/v6/latest/ETB",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                self.exchange_rates = data.get('rates', {'ETB': 1.0})
                
                import datetime
                self.rates_updated = datetime.datetime.now()
                logger.info("✅ Exchange rates updated successfully")
                return
            
        except Exception as e:
            logger.warning(f"Failed to fetch exchange rates: {e}")
        
        # Fallback to hardcoded rates
        self.exchange_rates = {
            'ETB': 1.0,
            'USD': 0.017,
            'EUR': 0.016,
            'GBP': 0.013,
            'CNY': 0.123,
            'JPY': 2.56,
        }
        
        import datetime
        self.rates_updated = datetime.datetime.now()
    
    def get_currency_info(self, code):
        """Get currency information"""
        for currency in self.supported_currencies:
            if currency['code'] == code:
                return currency
        return None
    
    def format_amount(self, amount, currency='ETB'):
        """Format amount with currency symbol"""
        currency_info = self.get_currency_info(currency)
        symbol = currency_info['symbol'] if currency_info else currency
        
        return f"{symbol} {amount:,.2f}"
    
    def get_available_currencies(self):
        """Get list of supported currencies"""
        return self.supported_currencies

# Singleton
currency_service = CurrencyService()