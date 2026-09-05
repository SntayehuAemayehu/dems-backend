# exams/ai_proctor.py - COMPLETE AI PROCTOR BACKEND

import json
import logging
import numpy as np
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from collections import defaultdict

logger = logging.getLogger(__name__)

class AIProctorBackend:
    """
    Complete AI Proctor Backend with real security validation
    """
    
    def __init__(self):
        self.thresholds = {
            'trust_score': 60,           # Below this = suspicious
            'tab_switches': 3,            # Max allowed
            'fullscreen_exits': 3,        # Max allowed
            'face_confidence': 0.6,       # Minimum face match
            'gaze_away_seconds': 10,      # Max gaze away time
            'head_tilt_degrees': 30,      # Max head tilt
            'suspicious_events': 5,       # Auto-flag threshold
            'network_latency_ms': 500,    # Max latency
            'mouse_anomaly_threshold': 3,  # Standard deviations
        }
        
        self.risk_weights = {
            'tab_switch': 15,
            'fullscreen_exit': 20,
            'face_lost': 10,
            'multiple_faces': 30,
            'gaze_away': 12,
            'head_tilt': 8,
            'eyes_closed': 10,
            'object_detected': 25,
            'network_latency': 5,
            'mouse_anomaly': 10,
            'keystroke_anomaly': 10,
        }
    
    def analyze_heartbeat(self, attempt, data):
        """
        Analyze heartbeat data in real-time
        """
        try:
            # Extract data
            trust_score = data.get('trust_score', 100)
            network_latency = data.get('network_latency', 0)
            mouse_movements = data.get('mouse_movements', 0)
            keystrokes = data.get('keystrokes', 0)
            tab_switches = data.get('tab_switches', 0)
            violations = data.get('violations', 0)
            is_fullscreen = data.get('is_fullscreen', True)
            face_detected = data.get('face_detected', True)
            multiple_faces = data.get('multiple_faces', False)
            gaze_direction = data.get('gaze_direction', 'CENTER')
            
            # Update attempt with real-time data
            attempt.tab_switch_count = tab_switches
            attempt.suspicious_events_count = violations
            
            # Calculate risk score
            risk_score = self._calculate_risk_score({
                'trust_score': trust_score,
                'network_latency': network_latency,
                'tab_switches': tab_switches,
                'violations': violations,
                'is_fullscreen': is_fullscreen,
                'face_detected': face_detected,
                'multiple_faces': multiple_faces,
                'gaze_direction': gaze_direction,
                'mouse_movements': mouse_movements,
                'keystrokes': keystrokes,
            })
            
            # Update AI risk
            attempt.ai_risk_score = risk_score
            attempt.ai_risk_level = self._get_risk_level(risk_score)
            
            # Auto-flag if critical
            if risk_score >= 70:
                attempt.ai_flagged = True
                attempt.ai_flag_reason = f"AI risk score: {risk_score}% - Auto-flagged"
                attempt.status = 'FLAGGED'
            
            # Check for lockdown conditions
            if risk_score >= 85:
                attempt.is_locked = True
                attempt.lock_reason = f"Critical risk detected ({risk_score}%) - Exam locked"
            
            attempt.save()
            
            return {
                'success': True,
                'risk_score': risk_score,
                'risk_level': attempt.ai_risk_level,
                'is_flagged': attempt.ai_flagged,
                'is_locked': attempt.is_locked,
                'flag_reason': attempt.ai_flag_reason if attempt.ai_flagged else None,
                'lock_reason': attempt.lock_reason if attempt.is_locked else None,
            }
            
        except Exception as e:
            logger.error(f"Heartbeat analysis failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _calculate_risk_score(self, data):
        """
        Calculate comprehensive risk score
        """
        score = 0
        total_weight = 0
        
        # 1. Trust Score (higher = better)
        trust_score = data.get('trust_score', 100)
        if trust_score < 60:
            score += (100 - trust_score) * 0.3
            total_weight += 0.3
        
        # 2. Tab Switches
        tab_switches = data.get('tab_switches', 0)
        if tab_switches > 0:
            score += min(tab_switches * 10, 30)
            total_weight += 0.2
        
        # 3. Fullscreen Exit
        if not data.get('is_fullscreen', True):
            score += 20
            total_weight += 0.15
        
        # 4. Face Detection
        if not data.get('face_detected', True):
            score += 15
            total_weight += 0.15
        
        # 5. Multiple Faces
        if data.get('multiple_faces', False):
            score += 30
            total_weight += 0.2
        
        # 6. Gaze Direction
        gaze = data.get('gaze_direction', 'CENTER')
        if gaze != 'CENTER':
            gaze_weights = {
                'LEFT': 10,
                'RIGHT': 10,
                'UP': 8,
                'DOWN': 8,
                'UP_LEFT': 12,
                'UP_RIGHT': 12,
                'DOWN_LEFT': 12,
                'DOWN_RIGHT': 12,
            }
            score += gaze_weights.get(gaze, 10)
            total_weight += 0.15
        
        # 7. Network Latency
        latency = data.get('network_latency', 0)
        if latency > 300:
            score += min((latency - 300) / 20, 15)
            total_weight += 0.1
        
        # 8. Mouse Movement Anomaly
        mouse_movements = data.get('mouse_movements', 0)
        if mouse_movements < 50:
            score += 10  # Suspicious - too still
            total_weight += 0.05
        elif mouse_movements > 500:
            score += 15  # Suspicious - too active
            total_weight += 0.05
        
        # 9. Keystroke Anomaly
        keystrokes = data.get('keystrokes', 0)
        if keystrokes < 10:
            score += 10  # Suspicious - too few keystrokes
            total_weight += 0.05
        elif keystrokes > 200:
            score += 15  # Suspicious - too many keystrokes
            total_weight += 0.05
        
        # Normalize
        if total_weight > 0:
            score = (score / total_weight)
        
        return min(max(score, 0), 100)
    
    def _get_risk_level(self, score):
        """
        Get risk level based on score
        """
        if score >= 80:
            return 'CRITICAL'
        elif score >= 60:
            return 'HIGH'
        elif score >= 35:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def analyze_face_verification(self, attempt, face_data):
        """
        Analyze face verification data
        """
        try:
            confidence = face_data.get('confidence', 0)
            face_match = face_data.get('face_match', False)
            landmarks = face_data.get('landmarks', {})
            
            # Update attempt
            attempt.face_match_confidence = confidence
            attempt.face_verified = face_match and confidence > self.thresholds['face_confidence']
            
            # If face verification fails
            if not attempt.face_verified:
                attempt.suspicious_events_count += 1
                if attempt.suspicious_events_count >= self.thresholds['suspicious_events']:
                    attempt.ai_flagged = True
                    attempt.ai_flag_reason = "Face verification failed multiple times"
            
            attempt.save()
            
            return {
                'success': True,
                'verified': attempt.face_verified,
                'confidence': confidence,
                'is_flagged': attempt.ai_flagged,
            }
            
        except Exception as e:
            logger.error(f"Face verification analysis failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def analyze_gaze_data(self, attempt, gaze_data):
        """
        Analyze gaze tracking data
        """
        try:
            direction = gaze_data.get('direction', 'CENTER')
            confidence = gaze_data.get('confidence', 0)
            gaze_x = gaze_data.get('gaze_x', 0)
            gaze_y = gaze_data.get('gaze_y', 0)
            
            # Update attempt
            if not attempt.gaze_analysis:
                attempt.gaze_analysis = {
                    'history': [],
                    'gaze_away_count': 0,
                    'total_frames': 0,
                }
            
            attempt.gaze_analysis['total_frames'] += 1
            attempt.gaze_analysis['history'].append({
                'timestamp': timezone.now().isoformat(),
                'direction': direction,
                'confidence': confidence,
                'gaze_x': gaze_x,
                'gaze_y': gaze_y,
            })
            
            # Keep only last 100 entries
            if len(attempt.gaze_analysis['history']) > 100:
                attempt.gaze_analysis['history'] = attempt.gaze_analysis['history'][-100:]
            
            # Check for prolonged gaze away
            if direction != 'CENTER':
                attempt.gaze_analysis['gaze_away_count'] += 1
                attempt.suspicious_events_count += 1
                
                if attempt.gaze_analysis['gaze_away_count'] >= 5:
                    attempt.ai_flagged = True
                    attempt.ai_flag_reason = f"Prolonged gaze away: {direction}"
            
            attempt.save()
            
            return {
                'success': True,
                'gaze_away_count': attempt.gaze_analysis['gaze_away_count'],
                'is_flagged': attempt.ai_flagged,
                'flag_reason': attempt.ai_flag_reason if attempt.ai_flagged else None,
            }
            
        except Exception as e:
            logger.error(f"Gaze analysis failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def analyze_objects_detected(self, attempt, objects):
        """
        Analyze detected objects
        """
        try:
            suspicious_objects = [
                'cell phone', 'mobile phone', 'phone',
                'book', 'notebook', 'laptop', 'computer',
                'tablet', 'ipad', 'kindle',
                'remote control', 'tv remote'
            ]
            
            detected_suspicious = []
            for obj in objects:
                obj_lower = obj.lower()
                for suspicious in suspicious_objects:
                    if suspicious in obj_lower:
                        detected_suspicious.append(obj)
                        break
            
            if detected_suspicious:
                if not attempt.object_detection:
                    attempt.object_detection = {
                        'detected_objects': [],
                        'suspicious_count': 0,
                    }
                
                attempt.object_detection['detected_objects'].extend(detected_suspicious)
                attempt.object_detection['suspicious_count'] += len(detected_suspicious)
                attempt.suspicious_events_count += len(detected_suspicious)
                
                if attempt.object_detection['suspicious_count'] >= 3:
                    attempt.ai_flagged = True
                    attempt.ai_flag_reason = f"Suspicious objects detected: {', '.join(detected_suspicious)}"
            
            attempt.save()
            
            return {
                'success': True,
                'detected_suspicious': detected_suspicious,
                'is_flagged': attempt.ai_flagged,
                'flag_reason': attempt.ai_flag_reason if attempt.ai_flagged else None,
            }
            
        except Exception as e:
            logger.error(f"Object detection analysis failed: {e}")
            return {'success': False, 'error': str(e)}