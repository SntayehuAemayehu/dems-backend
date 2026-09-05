
import openai
import json
import logging
from functools import lru_cache
from typing import Dict, List, Optional
from django.conf import settings
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class OpenAIService:
    """Unified OpenAI Service for all AI features"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        openai.api_key = self.api_key
        self.model = "gpt-4"  # or "gpt-3.5-turbo" for cost savings
        self.executor = ThreadPoolExecutor(max_workers=10)
        
    # ============================================================
    # 1. SMART ESSAY GRADING
    # ============================================================
    
    def grade_essay(self, student_answer: str, model_answer: str, rubric: str = "", max_marks: int = 100) -> Dict:
        """
        Grade an essay using OpenAI with rubric-based scoring
        
        Returns:
            {
                'score': float,
                'feedback': str,
                'strengths': List[str],
                'weaknesses': List[str],
                'suggestions': List[str],
                'detailed_breakdown': Dict
            }
        """
        try:
            system_prompt = f"""
            You are an expert essay grader with deep subject knowledge. Grade the student essay against the model answer.
            
            Grading Rubric:
            - Content Accuracy (40%): How well does the student answer match the model?
            - Depth of Analysis (30%): Does the student provide detailed analysis?
            - Clarity & Structure (20%): Is the essay well-organized and clear?
            - Language & Grammar (10%): Is the writing grammatically correct?
            
            Return ONLY a JSON object with this EXACT structure:
            {{
                "score": number (0-{max_marks}),
                "percentage": number (0-100),
                "feedback": "string",
                "strengths": ["string", "string"],
                "weaknesses": ["string", "string"],
                "suggestions": ["string", "string"],
                "detailed_breakdown": {{
                    "content_accuracy": number (0-40),
                    "depth_of_analysis": number (0-30),
                    "clarity_structure": number (0-20),
                    "language_grammar": number (0-10)
                }}
            }}
            
            {f"Rubric: {rubric}" if rubric else ""}
            """
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""
                        Model Answer:
                        {model_answer}
                        
                        Student Answer:
                        {student_answer}
                    """}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            
            result = json.loads(response.choices[0].message.content)
            return {
                'success': True,
                **result,
                'graded_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"OpenAI grading failed: {e}")
            return self._fallback_grading(student_answer, model_answer, max_marks)
    
    def grade_essay_batch(self, essays: List[Dict]) -> List[Dict]:
        """Grade multiple essays in batch"""
        results = []
        for essay in essays:
            result = self.grade_essay(
                essay['student_answer'],
                essay['model_answer'],
                essay.get('rubric', ''),
                essay.get('max_marks', 100)
            )
            results.append(result)
        return results
    
    def _fallback_grading(self, student_answer: str, model_answer: str, max_marks: int) -> Dict:
        """Fallback grading when OpenAI fails"""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        try:
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform([student_answer, model_answer])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            
            score = similarity * max_marks
            return {
                'success': True,
                'score': round(score, 2),
                'percentage': round(similarity * 100, 2),
                'feedback': f'Content similarity: {round(similarity * 100, 2)}%',
                'strengths': ['Content matches model answer'],
                'weaknesses': ['AI grading - manual review recommended'],
                'suggestions': ['Please review the automated grade'],
                'detailed_breakdown': {
                    'content_accuracy': round(score * 0.4, 2),
                    'depth_of_analysis': round(score * 0.3, 2),
                    'clarity_structure': round(score * 0.2, 2),
                    'language_grammar': round(score * 0.1, 2)
                }
            }
        except:
            return {
                'success': False,
                'score': 0,
                'percentage': 0,
                'feedback': 'Grading failed - manual review required',
                'strengths': [],
                'weaknesses': ['Automated grading failed'],
                'suggestions': ['Please grade manually'],
                'detailed_breakdown': {}
            }
    
    # ============================================================
    # 2. ADVANCED PLAGIARISM DETECTION
    # ============================================================
    
    def check_plagiarism_ai(self, text: str, context: str = "") -> Dict:
        """
        Advanced plagiarism detection using OpenAI
        
        Returns:
            {
                'plagiarism_score': float (0-100),
                'is_plagiarized': bool,
                'confidence': float,
                'detected_sources': List[str],
                'suspicious_phrases': List[str],
                'explanation': str
            }
        """
        try:
            system_prompt = """
            You are a plagiarism detection AI. Analyze the text and detect potential plagiarism.
            
            Return ONLY a JSON object with this EXACT structure:
            {
                "plagiarism_score": number (0-100),
                "is_plagiarized": boolean,
                "confidence": number (0-1),
                "detected_sources": ["string"],
                "suspicious_phrases": ["string"],
                "explanation": "string"
            }
            """
            
            user_prompt = f"Analyze this text for plagiarism:\n\n{text}"
            if context:
                user_prompt += f"\n\nContext: {context}"
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            result = json.loads(response.choices[0].message.content)
            return {'success': True, **result}
            
        except Exception as e:
            logger.error(f"AI Plagiarism check failed: {e}")
            return {
                'success': False,
                'plagiarism_score': 0,
                'is_plagiarized': False,
                'confidence': 0,
                'detected_sources': [],
                'suspicious_phrases': [],
                'explanation': 'AI check failed - use traditional methods'
            }
    
    # ============================================================
    # 3. AI QUESTION GENERATION
    # ============================================================
    
    def generate_questions(self, topic: str, difficulty: str = "medium", count: int = 5) -> List[Dict]:
        """
        Generate exam questions using AI
        
        Returns:
            [
                {
                    'type': 'MCQ' | 'TF' | 'SHORT',
                    'text': str,
                    'options': List[str] (for MCQ),
                    'correct_answer': str,
                    'marks': int,
                    'explanation': str
                }
            ]
        """
        try:
            system_prompt = f"""
            You are an expert exam question generator. Generate {count} questions about '{topic}'.
            
            Difficulty: {difficulty}
            
            For each question, return:
            - type: "MCQ", "TF", or "SHORT"
            - text: The question text
            - options: Array of 4 options (for MCQ only)
            - correct_answer: The correct answer
            - marks: 1-5
            - explanation: Brief explanation of the answer
            
            Return ONLY a JSON array.
            """
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Generate {count} {difficulty} questions about {topic}"}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            questions = json.loads(response.choices[0].message.content)
            return {'success': True, 'questions': questions}
            
        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            return {'success': False, 'questions': [], 'error': str(e)}
    
    # ============================================================
    # 4. FEEDBACK GENERATION
    # ============================================================
    
    def generate_feedback(self, student_answer: str, expected_answer: str, score: float) -> Dict:
        """
        Generate detailed personalized feedback
        
        Returns:
            {
                'summary': str,
                'strengths': List[str],
                'areas_for_improvement': List[str],
                'specific_suggestions': List[str],
                'encouragement': str
            }
        """
        try:
            system_prompt = """
            You are a supportive teacher providing constructive feedback.
            
            Return ONLY a JSON object with this EXACT structure:
            {
                "summary": "Overall feedback summary",
                "strengths": ["Strength 1", "Strength 2"],
                "areas_for_improvement": ["Area 1", "Area 2"],
                "specific_suggestions": ["Suggestion 1", "Suggestion 2"],
                "encouragement": "Motivational message"
            }
            """
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""
                        Student Answer: {student_answer}
                        Expected Answer: {expected_answer}
                        Score: {score}/100
                        
                        Provide constructive feedback to help the student improve.
                    """}
                ],
                temperature=0.4,
                max_tokens=800
            )
            
            feedback = json.loads(response.choices[0].message.content)
            return {'success': True, **feedback}
            
        except Exception as e:
            logger.error(f"Feedback generation failed: {e}")
            return {
                'success': False,
                'summary': 'Feedback generation failed',
                'strengths': [],
                'areas_for_improvement': [],
                'specific_suggestions': [],
                'encouragement': 'Please review your answers carefully.'
            }

# ============================================================
# 5. AI PROCTORING - BACKEND
# ============================================================

class AIProctorService:
    """Backend AI Proctoring Service"""
    
    def __init__(self):
        self.suspicious_threshold = 3
        self.warning_threshold = 2
    
    def analyze_proctoring_data(self, attempt_id: int, image_data: List[Dict]) -> Dict:
        """
        Analyze proctoring images for suspicious activity
        
        Returns:
            {
                'is_suspicious': bool,
                'suspicious_count': int,
                'warnings': List[Dict],
                'severity': 'LOW' | 'MEDIUM' | 'HIGH'
            }
        """
        suspicious_events = []
        warnings = []
        
        for image in image_data:
            # Check for multiple faces
            if image.get('multiple_faces', False):
                suspicious_events.append({
                    'type': 'MULTIPLE_FACES',
                    'timestamp': image.get('timestamp'),
                    'severity': 'HIGH'
                })
                warnings.append('Multiple faces detected in frame')
            
            # Check for face lost
            if not image.get('face_detected', True):
                suspicious_events.append({
                    'type': 'FACE_LOST',
                    'timestamp': image.get('timestamp'),
                    'severity': 'MEDIUM'
                })
                warnings.append('Face not detected in frame')
            
            # Check for mobile detection
            if image.get('mobile_detected', False):
                suspicious_events.append({
                    'type': 'MOBILE_DETECTED',
                    'timestamp': image.get('timestamp'),
                    'severity': 'HIGH'
                })
                warnings.append('Mobile device detected')
        
        # Calculate severity
        suspicious_count = len(suspicious_events)
        high_count = sum(1 for e in suspicious_events if e.get('severity') == 'HIGH')
        
        if high_count >= self.suspicious_threshold:
            severity = 'HIGH'
            is_suspicious = True
        elif suspicious_count >= self.warning_threshold:
            severity = 'MEDIUM'
            is_suspicious = True
        else:
            severity = 'LOW'
            is_suspicious = False
        
        return {
            'is_suspicious': is_suspicious,
            'suspicious_count': suspicious_count,
            'high_severity_count': high_count,
            'wa rnings': warnings[:10],  # Limit warnings
            'severity': severity,
            'suspicious_events': suspicious_events[:20]
        }