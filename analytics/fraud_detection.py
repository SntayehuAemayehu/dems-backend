# backend/analytics/fraud_detection.py
# COMPLETE FRAUD DETECTION WITH ML ENHANCEMENT

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass, field
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import os
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class FraudAlert:
    """Fraud alert data"""
    type: str
    severity: str
    message: str
    timestamp: str
    data: Dict = field(default_factory=dict)
    risk_score: float = 0.0

@dataclass
class FraudAnalysisResult:
    """Result of fraud analysis"""
    user_id: str
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    risk_score: float  # 0-100
    alerts: List[FraudAlert] = field(default_factory=list)
    flags: List[Dict] = field(default_factory=list)
    recommendation: str = ''
    timestamp: str = ''

# ============================================================
# FRAUD DETECTOR WITH ML
# ============================================================

class FraudDetector:
    """Advanced Fraud Detection with ML enhancement"""
    
    def __init__(self, model_path: str = None):
        self.session_data = defaultdict(list)
        self.suspicious_patterns = []
        self.user_profiles = {}
        self.ip_activity = defaultdict(list)
        self.device_activity = defaultdict(list)
        
        # ML Model
        self.model = None
        self.scaler = StandardScaler()
        self.model_path = model_path or Path(__file__).parent / 'models' / 'fraud_model.pkl'
        self.scaler_path = Path(__file__).parent / 'models' / 'scaler.pkl'
        self.feature_names = [
            'login_time_hour',
            'login_count_24h',
            'unique_ips_24h',
            'unique_devices_24h',
            'action_speed_ms',
            'tab_switches',
            'pattern_deviation_score',
            'unusual_time_score',
            'ip_reputation_score',
            'device_fingerprint_score'
        ]
        
        # Load existing model if available
        self._load_model()
    
    def _load_model(self):
        """Load trained ML model if exists"""
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                logger.info("✅ Fraud detection ML model loaded")
            else:
                logger.info("ℹ️ No pre-trained fraud model found. Using rule-based detection.")
        except Exception as e:
            logger.warning(f"Failed to load fraud model: {e}")
            self.model = None
        
        try:
            if os.path.exists(self.scaler_path):
                self.scaler = joblib.load(self.scaler_path)
                logger.info("✅ Fraud scaler loaded")
        except Exception as e:
            logger.warning(f"Failed to load scaler: {e}")
    
    def _save_model(self):
        """Save trained ML model"""
        try:
            # Create models directory if it doesn't exist
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            logger.info("✅ Fraud detection ML model saved")
            return True
        except Exception as e:
            logger.error(f"Failed to save fraud model: {e}")
            return False
    
    # ============================================================
    # ML TRAINING
    # ============================================================
    
    def train_model(self, historical_data: List[Dict], labels: List[int] = None):
        """
        Train ML model on historical fraud data
        
        Args:
            historical_data: List of user activity records
            labels: List of labels (0 = normal, 1 = fraud)
        """
        try:
            df = pd.DataFrame(historical_data)
            
            # Ensure all required features exist
            for feature in self.feature_names:
                if feature not in df.columns:
                    df[feature] = 0
            
            # Prepare features
            X = df[self.feature_names].values
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # If labels not provided, use heuristics
            if labels is None:
                labels = self._generate_heuristic_labels(df)
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, labels, test_size=0.2, random_state=42
            )
            
            # Train model
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                class_weight='balanced',
                random_state=42,
                n_jobs=-1
            )
            self.model.fit(X_train, y_train)
            
            # Evaluate
            y_pred = self.model.predict(X_test)
            
            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred, zero_division=0),
                'recall': recall_score(y_test, y_pred, zero_division=0),
                'f1_score': f1_score(y_test, y_pred, zero_division=0)
            }
            
            logger.info(f"📊 Fraud model trained! Metrics: {metrics}")
            
            # Save model
            self._save_model()
            
            return metrics
            
        except Exception as e:
            logger.error(f"Training fraud model failed: {e}")
            return None
    
    def _generate_heuristic_labels(self, df: pd.DataFrame) -> List[int]:
        """Generate labels using heuristic rules"""
        labels = []
        
        for _, row in df.iterrows():
            is_fraud = 0
            
            # Heuristic rules
            if row.get('login_count_24h', 0) > 10:
                is_fraud = 1
            elif row.get('unique_ips_24h', 0) > 5:
                is_fraud = 1
            elif row.get('action_speed_ms', 1000) < 100:
                is_fraud = 1
            elif row.get('tab_switches', 0) > 20:
                is_fraud = 1
            elif row.get('pattern_deviation_score', 0) > 0.8:
                is_fraud = 1
            
            labels.append(is_fraud)
        
        return labels
    
    # ============================================================
    # FRAUD ANALYSIS
    # ============================================================
    
    def analyze_behavior(
        self, 
        user_id: str, 
        activity_type: str, 
        data: Dict
    ) -> FraudAnalysisResult:
        """
        Analyze user behavior for fraud patterns
        
        Args:
            user_id: User identifier
            activity_type: Type of activity (LOGIN, EXAM_TAKING, etc.)
            data: Activity data
        
        Returns:
            FraudAnalysisResult object
        """
        timestamp = datetime.now().isoformat()
        alerts = []
        flags = []
        
        # Store session data
        self.session_data[user_id].append({
            'timestamp': datetime.now(),
            'type': activity_type,
            'data': data
        })
        
        # ============================================================
        # RULE-BASED DETECTION
        # ============================================================
        
        # 1. Multiple accounts from same IP
        if activity_type == 'LOGIN':
            ip = data.get('ip')
            if ip:
                flag = self._check_multiple_accounts(ip, user_id)
                if flag:
                    flags.append(flag)
                    alerts.append(FraudAlert(
                        type='MULTIPLE_ACCOUNTS',
                        severity='HIGH',
                        message=f"Multiple accounts from same IP: {ip}",
                        timestamp=timestamp,
                        data={'ip': ip, 'count': flag.get('count', 0)}
                    ))
        
        # 2. Speed of actions (too fast = bot)
        if activity_type in ['EXAM_TAKING', 'ASSIGNMENT_SUBMISSION']:
            flag = self._check_action_speed(user_id, data)
            if flag:
                flags.append(flag)
                alerts.append(FraudAlert(
                    type='TOO_FAST',
                    severity='HIGH' if flag.get('avg_time', 0) < 0.5 else 'MEDIUM',
                    message=f"Impossibly fast actions ({flag.get('avg_time', 0):.2f}s average)",
                    timestamp=timestamp,
                    data={'avg_time': flag.get('avg_time', 0)}
                ))
        
        # 3. Unusual timing
        if activity_type == 'LOGIN':
            flag = self._check_unusual_time(datetime.now())
            if flag:
                flags.append(flag)
                alerts.append(FraudAlert(
                    type='UNUSUAL_TIME',
                    severity='LOW',
                    message=f"Login at unusual hour: {flag.get('hour')}:00",
                    timestamp=timestamp,
                    data={'hour': flag.get('hour', 0)}
                ))
        
        # 4. Pattern deviation
        flag = self._check_pattern_deviation(user_id, activity_type)
        if flag:
            flags.append(flag)
            alerts.append(FraudAlert(
                type='PATTERN_DEVIATION',
                severity='MEDIUM',
                message=f"Unusual activity pattern detected",
                timestamp=timestamp,
                data={'deviation': flag.get('score', 0)}
            ))
        
        # 5. Device fingerprint (if available)
        if data.get('device_fingerprint'):
            flag = self._check_device_fingerprint(user_id, data.get('device_fingerprint'))
            if flag:
                flags.append(flag)
                alerts.append(FraudAlert(
                    type='DEVICE_CHANGE',
                    severity='MEDIUM',
                    message="New device detected",
                    timestamp=timestamp,
                    data={'device': data.get('device_fingerprint')}
                ))
        
        # ============================================================
        # ML-BASED DETECTION (if model is available)
        # ============================================================
        
        ml_risk_score = 0
        ml_prediction = False
        
        if self.model is not None:
            try:
                # Extract features for ML
                features = self._extract_ml_features(user_id, activity_type, data)
                
                # Scale features
                features_scaled = self.scaler.transform([features])
                
                # Predict
                ml_prediction = self.model.predict(features_scaled)[0]
                ml_probability = self.model.predict_proba(features_scaled)[0]
                ml_risk_score = ml_probability[1] * 100  # Probability of fraud
                
                if ml_prediction or ml_risk_score > 70:
                    alerts.append(FraudAlert(
                        type='ML_FRAUD_DETECTION',
                        severity='HIGH' if ml_risk_score > 85 else 'MEDIUM',
                        message=f"ML model detected potential fraud (confidence: {ml_risk_score:.1f}%)",
                        timestamp=timestamp,
                        data={'ml_score': ml_risk_score}
                    ))
                
            except Exception as e:
                logger.error(f"ML prediction failed: {e}")
        
        # ============================================================
        # CALCULATE OVERALL RISK
        # ============================================================
        
        # Calculate risk level
        risk_score = self._calculate_risk_score(alerts, flags, ml_risk_score)
        risk_level = self._get_risk_level(risk_score)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(risk_level, alerts)
        
        return FraudAnalysisResult(
            user_id=user_id,
            risk_level=risk_level,
            risk_score=risk_score,
            alerts=alerts,
            flags=flags,
            recommendation=recommendation,
            timestamp=timestamp
        )
    
    # ============================================================
    # ML FEATURE EXTRACTION
    # ============================================================
    
    def _extract_ml_features(self, user_id: str, activity_type: str, data: Dict) -> List[float]:
        """Extract features for ML model"""
        
        # Get user session history
        user_sessions = self.session_data.get(user_id, [])
        
        # 1. Login time hour (0-23)
        login_hour = datetime.now().hour
        
        # 2. Login count in last 24 hours
        login_count_24h = sum(
            1 for s in user_sessions 
            if s['type'] == 'LOGIN' and 
            (datetime.now() - s['timestamp']).total_seconds() < 86400
        )
        
        # 3. Unique IPs in last 24 hours
        ips_24h = set(
            s.get('data', {}).get('ip') 
            for s in user_sessions 
            if (datetime.now() - s['timestamp']).total_seconds() < 86400
        )
        unique_ips_24h = len([ip for ip in ips_24h if ip])
        
        # 4. Unique devices in last 24 hours
        devices_24h = set(
            s.get('data', {}).get('device_fingerprint') 
            for s in user_sessions 
            if (datetime.now() - s['timestamp']).total_seconds() < 86400
        )
        unique_devices_24h = len([d for d in devices_24h if d])
        
        # 5. Action speed (average time between actions)
        recent_actions = user_sessions[-10:] if len(user_sessions) >= 10 else user_sessions
        if len(recent_actions) > 1:
            times = [s['timestamp'] for s in recent_actions]
            avg_diff = sum(
                (times[i] - times[i-1]).total_seconds() 
                for i in range(1, len(times))
            ) / (len(times) - 1)
            action_speed_ms = avg_diff * 1000
        else:
            action_speed_ms = 1000
        
        # 6. Tab switches (from data)
        tab_switches = data.get('tab_switches', 0)
        
        # 7. Pattern deviation score
        pattern_deviation = self._calculate_pattern_deviation(user_id)
        
        # 8. Unusual time score
        unusual_time = 1.0 if (login_hour < 4 or login_hour > 23) else 0.0
        
        # 9. IP reputation score (placeholder)
        ip_reputation = 0.0  # Could integrate with external API
        
        # 10. Device fingerprint score
        device_fingerprint_score = 1.0 if data.get('device_fingerprint') else 0.0
        
        features = [
            login_hour / 24.0,  # Normalize
            min(login_count_24h / 20.0, 1.0),
            min(unique_ips_24h / 10.0, 1.0),
            min(unique_devices_24h / 5.0, 1.0),
            min(action_speed_ms / 5000.0, 1.0),
            min(tab_switches / 50.0, 1.0),
            min(pattern_deviation, 1.0),
            unusual_time,
            ip_reputation,
            device_fingerprint_score
        ]
        
        return features
    
    def _calculate_pattern_deviation(self, user_id: str) -> float:
        """Calculate pattern deviation score"""
        user_sessions = self.session_data.get(user_id, [])
        
        if len(user_sessions) < 10:
            return 0.0
        
        # Count activity types
        type_counts = defaultdict(int)
        for session in user_sessions[-20:]:
            type_counts[session['type']] += 1
        
        total = sum(type_counts.values())
        if total == 0:
            return 0.0
        
        # Calculate entropy (higher = more deviation)
        entropy = -sum(
            (count / total) * np.log(count / total + 0.001) 
            for count in type_counts.values()
        )
        
        # Normalize entropy (max entropy for 3 types = log(3) ≈ 1.1)
        max_entropy = np.log(len(type_counts) + 1)
        normalized_entropy = min(entropy / max_entropy, 1.0)
        
        return normalized_entropy
    
    # ============================================================
    # RULE-BASED CHECKS
    # ============================================================
    
    def _check_multiple_accounts(self, ip: str, current_user: str) -> Optional[Dict]:
        """Check multiple accounts from same IP"""
        count = 0
        for user_id, sessions in self.session_data.items():
            if user_id != current_user:
                for session in sessions:
                    if (session.get('data', {}).get('ip') == ip and
                        (datetime.now() - session['timestamp']).total_seconds() < 86400):
                        count += 1
        
        if count > 3:
            return {
                'type': 'MULTIPLE_ACCOUNTS',
                'severity': 'HIGH',
                'message': f'Multiple accounts ({count}) from same IP',
                'ip': ip,
                'count': count
            }
        return None
    
    def _check_action_speed(self, user_id: str, data: Dict) -> Optional[Dict]:
        """Check if actions are too fast (bot behavior)"""
        recent_actions = self.session_data.get(user_id, [])[-5:]
        if len(recent_actions) < 2:
            return None
        
        times = [a['timestamp'] for a in recent_actions]
        avg_diff = sum(
            (times[i] - times[i-1]).total_seconds() 
            for i in range(1, len(times))
        ) / (len(times) - 1) if len(times) > 1 else 0
        
        if avg_diff < 1 and data.get('question_count', 0) > 5:
            return {
                'type': 'TOO_FAST',
                'severity': 'HIGH',
                'message': f'Impossibly fast actions ({avg_diff:.2f}s average)',
                'avg_time': avg_diff
            }
        return None
    
    def _check_unusual_time(self, timestamp: datetime) -> Optional[Dict]:
        """Check if login time is unusual"""
        hour = timestamp.hour
        if hour < 4 or hour > 23:
            return {
                'type': 'UNUSUAL_TIME',
                'severity': 'LOW',
                'message': f'Login at unusual hour: {hour}:00',
                'hour': hour
            }
        return None
    
    def _check_pattern_deviation(self, user_id: str, activity_type: str) -> Optional[Dict]:
        """Check if user deviates from normal pattern"""
        user_sessions = self.session_data.get(user_id, [])
        if len(user_sessions) < 10:
            return None
        
        type_counts = defaultdict(int)
        for session in user_sessions[-20:]:
            type_counts[session['type']] += 1
        
        total = sum(type_counts.values())
        if total == 0:
            return None
        
        normal_percentage = type_counts.get(activity_type, 0) / total
        if normal_percentage < 0.1 and len(user_sessions) > 10:
            return {
                'type': 'PATTERN_DEVIATION',
                'severity': 'MEDIUM',
                'message': f'Unusual activity: {activity_type} (normally {normal_percentage*100:.1f}%)',
                'score': 1 - normal_percentage
            }
        return None
    
    def _check_device_fingerprint(self, user_id: str, fingerprint: str) -> Optional[Dict]:
        """Check for device changes"""
        if not fingerprint:
            return None
        
        for session in self.session_data.get(user_id, []):
            old_fingerprint = session.get('data', {}).get('device_fingerprint')
            if old_fingerprint and old_fingerprint != fingerprint:
                return {
                    'type': 'DEVICE_CHANGE',
                    'severity': 'MEDIUM',
                    'message': 'New device detected'
                }
        return None
    
    # ============================================================
    # RISK CALCULATION
    # ============================================================
    
    def _calculate_risk_score(self, alerts: List[FraudAlert], flags: List[Dict], ml_score: float) -> float:
        """Calculate overall risk score (0-100)"""
        score = 0.0
        
        # Alert weights
        alert_weights = {
            'HIGH': 30,
            'MEDIUM': 15,
            'LOW': 5
        }
        
        # Add alert scores
        for alert in alerts:
            score += alert_weights.get(alert.severity, 10)
        
        # Add flag scores
        for flag in flags:
            severity = flag.get('severity', 'MEDIUM')
            score += alert_weights.get(severity, 10)
        
        # Add ML score (weighted)
        score += ml_score * 0.4
        
        # Cap at 100
        return min(score, 100.0)
    
    def _get_risk_level(self, score: float) -> str:
        """Get risk level from score"""
        if score >= 80:
            return 'CRITICAL'
        elif score >= 60:
            return 'HIGH'
        elif score >= 30:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _generate_recommendation(self, risk_level: str, alerts: List[FraudAlert]) -> str:
        """Generate recommendation based on risk level"""
        if risk_level == 'CRITICAL':
            return '🚨 Immediate action required! Flag user account and notify admin.'
        elif risk_level == 'HIGH':
            return '⚠️ High risk detected. Review user activity and consider temporary lockout.'
        elif risk_level == 'MEDIUM':
            return 'ℹ️ Medium risk detected. Monitor user activity closely.'
        else:
            return '✅ Low risk. No action required.'
    
    # ============================================================
    # BATCH ANALYSIS
    # ============================================================
    
    def batch_analyze(self, user_activities: List[Dict]) -> List[FraudAnalysisResult]:
        """Analyze multiple user activities in batch"""
        results = []
        for activity in user_activities:
            result = self.analyze_behavior(
                user_id=activity.get('user_id'),
                activity_type=activity.get('type'),
                data=activity.get('data', {})
            )
            results.append(result)
        return results
    
    # ============================================================
    # REPORTING
    # ============================================================
    
    def get_fraud_summary(self) -> Dict:
        """Get summary of fraud detection"""
        total_users = len(self.session_data)
        flagged_users = 0
        high_risk_users = 0
        total_alerts = 0
        
        for user_id, sessions in self.session_data.items():
            alerts = sum(1 for s in sessions if s.get('data', {}).get('suspicious'))
            if alerts > 0:
                flagged_users += 1
                total_alerts += alerts
                if alerts > 3:
                    high_risk_users += 1
        
        return {
            'total_users': total_users,
            'flagged_users': flagged_users,
            'high_risk_users': high_risk_users,
            'total_alerts': total_alerts,
            'alert_rate': (flagged_users / total_users * 100) if total_users > 0 else 0,
            'risk_levels': {
                'CRITICAL': high_risk_users,
                'HIGH': flagged_users - high_risk_users,
                'MEDIUM': total_users - flagged_users - high_risk_users,
                'LOW': total_users - flagged_users
            }
        }
    
    # ============================================================
    # MODEL MANAGEMENT
    # ============================================================
    
    def update_model(self, new_data: List[Dict], labels: List[int] = None):
        """Update model with new data"""
        if self.model is None:
            return self.train_model(new_data, labels)
        
        # Incremental learning (retrain with new data)
        return self.train_model(new_data, labels)
    
    def export_model(self, export_path: str):
        """Export model for deployment"""
        try:
            joblib.dump(self.model, export_path)
            return True
        except Exception as e:
            logger.error(f"Failed to export model: {e}")
            return False
    
    def import_model(self, import_path: str):
        """Import trained model"""
        try:
            self.model = joblib.load(import_path)
            return True
        except Exception as e:
            logger.error(f"Failed to import model: {e}")
            return False