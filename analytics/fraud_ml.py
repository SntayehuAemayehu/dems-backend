# backend/analytics/fraud_ml.py - NEW FILE
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

class MLFraudDetector:
    def __init__(self):
        self.model = None
        
    def train_model(self, historical_data):
        """Train ML model on historical fraud data"""
        df = pd.DataFrame(historical_data)
        features = ['login_time', 'ip_count', 'action_speed', 'pattern_deviation']
        X = df[features]
        y = df['is_fraud']
        
        self.model = RandomForestClassifier(n_estimators=100)
        self.model.fit(X, y)
        
        joblib.dump(self.model, 'fraud_model.pkl')
        
    def predict(self, user_data):
        """Predict if user is fraudulent"""
        if self.model is None:
            self.model = joblib.load('fraud_model.pkl')
        
        features = [[
            user_data['login_time'],
            user_data['ip_count'],
            user_data['action_speed'],
            user_data['pattern_deviation']
        ]]
        
        probability = self.model.predict_proba(features)[0][1]
        return {
            'is_fraud': probability > 0.7,
            'confidence': probability,
            'risk_level': 'HIGH' if probability > 0.8 else 'MEDIUM' if probability > 0.5 else 'LOW'
        }