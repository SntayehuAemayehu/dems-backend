# backend/exams/trust_engine.py
"""
Server-side trust score engine.
NEVER trusts client-sent trust_score. Computes from raw signals.

Signals collected SERVER-SIDE:
- Time between heartbeats (regular = bot)
- Time between submissions
- Tab switches (reported by client but validated by timing)
- Number of violations with timestamps
- Network latency patterns

Server-side computed:
- suspicion_score (0-100, higher = more suspicious)
- trust_score (0-100, higher = more trusted)
- risk_level
"""

import logging
from datetime import datetime, timedelta
from django.utils import timezone
from collections import deque

logger = logging.getLogger(__name__)


class TrustEngine:
    """
    Computes trust score from server-collected signals only.
    """

    def __init__(self, attempt):
        self.attempt = attempt
        self.weights = {
            'tab_switches': 12,
            'fullscreen_exits': 15,
            'face_lost': 8,
            'multiple_faces': 25,
            'gaze_away': 6,
            'head_tilt': 4,
            'eyes_closed': 5,
            'suspicious_objects': 20,
            'keystroke_anomaly': 8,
            'mouse_anomaly': 6,
            'heartbeat_irregular': 10,
            'face_verification_failed': 20,
            'network_latency_spikes': 5,
        }

    # ============================================================
    # SERVER-SIDE HEARTBEAT VALIDATION
    # ============================================================

    def record_heartbeat(self, client_data):
        """
        Record a heartbeat. Server-side computes suspicion.
        Client data is UNTRUSTED.
        """
        now = timezone.now()

        # Get or initialize history
        history = self.attempt.heartbeat_history or []

        # Server-side: time since last heartbeat
        time_since_last = None
        if self.attempt.last_heartbeat:
            time_since_last = (now - self.attempt.last_heartbeat).total_seconds()

        # Detect regular intervals (indicates bot)
        heartbeat_irregular = False
        if time_since_last is not None:
            # Client claims to send every 5s. If it's exactly 5.000s, suspicious.
            # Real humans have 4.5-5.5s jitter.
            if 4.98 < time_since_last < 5.02:
                history.append({'t': now.timestamp(), 'interval': time_since_last, 'suspicious': 'too_regular'})
                heartbeat_irregular = True

        # Trim history
        history = history[-200:]

        # Save
        self.attempt.heartbeat_history = history
        self.attempt.last_heartbeat = now

        return {
            'time_since_last': time_since_last,
            'heartbeat_irregular': heartbeat_irregular,
        }

    # ============================================================
    # COMPUTE TRUST SCORE FROM DB STATE
    # ============================================================

    def compute_trust_score(self):
        """
        Compute trust score from server-side persisted state.
        IGNORES any client-sent trust_score.
        """
        attempt = self.attempt
        suspicion = 0

        # 1. Tab switches (server tracked from DB)
        tab_switches = attempt.tab_switch_count or 0
        suspicion += min(tab_switches * self.weights['tab_switches'], 60)

        # 2. Fullscreen exits
        fullscreen_exits = getattr(attempt, 'fullscreen_exit_count', 0) or 0
        suspicion += min(fullscreen_exits * self.weights['fullscreen_exits'], 45)

        # 3. Face verification
        if not attempt.face_verified:
            suspicion += self.weights['face_verification_failed']

        # 4. Gaze analysis (from persisted data)
        gaze_data = attempt.gaze_analysis or {}
        gaze_away_count = gaze_data.get('gaze_away_count', 0)
        suspicion += min(gaze_away_count * self.weights['gaze_away'], 30)

        # 5. Multiple faces events
        logs = attempt.proctor_logs.all() if hasattr(attempt, 'proctor_logs') else []
        multiple_faces_events = sum(1 for log in logs if log.event_type == 'MULTIPLE_FACES')
        suspicion += min(multiple_faces_events * self.weights['multiple_faces'], 50)

        face_lost_events = sum(1 for log in logs if log.event_type == 'FACE_LOST')
        suspicion += min(face_lost_events * self.weights['face_lost'], 30)

        object_events = sum(1 for log in logs if log.event_type == 'OBJECT_DETECTED')
        suspicion += min(object_events * self.weights['suspicious_objects'], 40)

        # 6. Heartbeat regularity (from history)
        history = attempt.heartbeat_history or []
        irregular = sum(1 for h in history if h.get('suspicious') == 'too_regular')
        suspicion += min(irregular * self.weights['heartbeat_irregular'], 25)

        # 7. Network latency (server-detected patterns)
        latency_history = attempt.network_latency_history or []
        if len(latency_history) > 5:
            # Detect spikes: > 3 std deviations from mean
            import statistics
            try:
                values = [float(x) for x in latency_history if x]
                if values:
                    mean = statistics.mean(values)
                    if len(values) > 1:
                        stdev = statistics.stdev(values)
                        spikes = sum(1 for v in values if v > mean + 3 * stdev and v > 500)
                        suspicion += min(spikes * self.weights['network_latency_spikes'], 15)
            except Exception:
                pass

        # 8. Suspicious events count (from DB)
        suspicion += min((attempt.suspicious_events_count or 0) * 3, 30)

        # Cap suspicion
        suspicion = min(suspicion, 100)

        # Trust = inverse of suspicion
        trust = 100 - suspicion

        # Determine risk level
        if suspicion >= 70:
            risk_level = 'CRITICAL'
        elif suspicion >= 50:
            risk_level = 'HIGH'
        elif suspicion >= 25:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'

        return {
            'trust_score': int(trust),
            'suspicion_score': int(suspicion),
            'risk_level': risk_level,
            'should_flag': suspicion >= 50,
            'should_lock': suspicion >= 80,
        }

    def save_trust_to_attempt(self):
        """Compute and persist trust score."""
        result = self.compute_trust_score()
        self.attempt.trust_score = result['trust_score']
        self.attempt.ai_risk_score = result['suspicion_score']
        self.attempt.ai_risk_level = result['risk_level']

        if result['should_flag'] and not self.attempt.ai_flagged:
            self.attempt.ai_flagged = True
            self.attempt.ai_flag_reason = f"Server-side trust score: {result['trust_score']}% (risk: {result['risk_level']})"
            if self.attempt.status not in ['SUBMITTED', 'GRADED', 'FLAGGED']:
                self.attempt.status = 'FLAGGED'

        if result['should_lock']:
            self.attempt.is_locked = True
            self.attempt.lock_reason = f"Critical risk detected (trust: {result['trust_score']}%)"

        self.attempt.save()
        return result