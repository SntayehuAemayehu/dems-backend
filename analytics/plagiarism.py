# backend/analytics/plagiarism.py
# COMPLETE PLAGIARISM DETECTION WITH SMART GRADER

import re
import hashlib
import numpy as np
from difflib import SequenceMatcher
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict, Counter
import json
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from functools import lru_cache

logger = logging.getLogger(__name__)

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class PlagiarismResult:
    """Result of plagiarism check"""
    similarity_score: float
    is_plagiarized: bool
    matched_phrases: List[str] = field(default_factory=list)
    confidence: str = 'LOW'
    tfidf_score: float = 0.0
    sequence_score: float = 0.0
    word_overlap: float = 0.0
    source_sentences: List[str] = field(default_factory=list)
    matched_sentences: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)

@dataclass
class GradingResult:
    """Result of smart grading"""
    marks: float
    percentage: float
    feedback: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    plagiarism_check: Optional[PlagiarismResult] = None
    breakdown: Dict = field(default_factory=dict)
    grade_letter: str = 'F'
    passed: bool = False

# ============================================================
# PLAGIARISM DETECTOR - ENHANCED
# ============================================================

class PlagiarismDetector:
    """Advanced Plagiarism Detection with multiple methods"""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=10000,
            ngram_range=(1, 3)
        )
        self.word_pattern = re.compile(r'\b[a-zA-Z]+\b')
        self.sentence_pattern = re.compile(r'[.!?]+')
        self.cache = {}
    
    @lru_cache(maxsize=1000)
    def _get_tfidf_matrix(self, text1: str, text2: str):
        """Cached TF-IDF computation"""
        try:
            tfidf_matrix = self.vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
            return similarity[0][0]
        except Exception as e:
            logger.error(f"TF-IDF computation error: {e}")
            return 0.0
    
    def check_plagiarism(self, text1: str, text2: str, threshold: float = 0.7) -> PlagiarismResult:
        """
        Check plagiarism between two texts using multiple methods
        
        Args:
            text1: First text to compare
            text2: Second text to compare
            threshold: Similarity threshold (0-1)
        
        Returns:
            PlagiarismResult object
        """
        # Clean texts
        text1_clean = self._clean_text(text1)
        text2_clean = self._clean_text(text2)
        
        if not text1_clean or not text2_clean:
            return PlagiarismResult(
                similarity_score=0,
                is_plagiarized=False,
                confidence='LOW',
                details={'error': 'Empty text provided'}
            )
        
        # Method 1: TF-IDF Cosine Similarity
        tfidf_score = self._check_tfidf(text1_clean, text2_clean)
        
        # Method 2: Sequence Matching
        sequence_score = self._check_sequence(text1_clean, text2_clean)
        
        # Method 3: Word Overlap
        word_overlap = self._check_word_overlap(text1_clean, text2_clean)
        
        # Method 4: Sentence Similarity
        sentence_similarity = self._check_sentence_similarity(text1_clean, text2_clean)
        
        # Method 5: N-gram Overlap
        ngram_overlap = self._check_ngram_overlap(text1_clean, text2_clean)
        
        # Weighted average
        weights = {
            'tfidf': 0.3,
            'sequence': 0.25,
            'word_overlap': 0.15,
            'sentence': 0.15,
            'ngram': 0.15
        }
        
        avg_score = (
            tfidf_score * weights['tfidf'] +
            sequence_score * weights['sequence'] +
            word_overlap * weights['word_overlap'] +
            sentence_similarity * weights['sentence'] +
            ngram_overlap * weights['ngram']
        )
        
        # Find matching phrases
        matched_phrases = self._find_matching_phrases(text1_clean, text2_clean)
        matched_sentences = self._find_matching_sentences(text1_clean, text2_clean)
        
        # Determine confidence
        if avg_score > 0.85:
            confidence = 'HIGH'
        elif avg_score > 0.7:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'
        
        is_plagiarized = avg_score > threshold
        
        return PlagiarismResult(
            similarity_score=avg_score,
            is_plagiarized=is_plagiarized,
            matched_phrases=matched_phrases[:10],
            confidence=confidence,
            tfidf_score=tfidf_score,
            sequence_score=sequence_score,
            word_overlap=word_overlap,
            source_sentences=matched_sentences[:5],
            matched_sentences=matched_sentences[:5],
            details={
                'tfidf_score': tfidf_score,
                'sequence_score': sequence_score,
                'word_overlap': word_overlap,
                'sentence_similarity': sentence_similarity,
                'ngram_overlap': ngram_overlap,
                'threshold': threshold,
                'text1_length': len(text1_clean),
                'text2_length': len(text2_clean)
            }
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ''
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Convert to lowercase
        text = text.lower()
        # Remove special characters (keep letters, numbers, spaces, punctuation)
        text = re.sub(r'[^a-zA-Z0-9\s\.\,\!\?\'\"]', ' ', text)
        return text.strip()
    
    def _check_tfidf(self, text1: str, text2: str) -> float:
        """TF-IDF Cosine Similarity with caching"""
        try:
            return self._get_tfidf_matrix(text1, text2)
        except Exception as e:
            logger.error(f"TF-IDF check error: {e}")
            return 0.0
    
    def _check_sequence(self, text1: str, text2: str) -> float:
        """Sequence Matcher"""
        try:
            matcher = SequenceMatcher(None, text1, text2)
            return matcher.ratio()
        except Exception as e:
            logger.error(f"Sequence check error: {e}")
            return 0.0
    
    def _check_word_overlap(self, text1: str, text2: str) -> float:
        """Word Overlap with weighting"""
        try:
            words1 = set(self.word_pattern.findall(text1))
            words2 = set(self.word_pattern.findall(text2))
            
            if not words1 or not words2:
                return 0.0
            
            # Weighted intersection
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            return len(intersection) / len(union) if union else 0.0
        except Exception as e:
            logger.error(f"Word overlap error: {e}")
            return 0.0
    
    def _check_sentence_similarity(self, text1: str, text2: str) -> float:
        """Sentence-level similarity"""
        try:
            sentences1 = self.sentence_pattern.split(text1)
            sentences2 = self.sentence_pattern.split(text2)
            
            if not sentences1 or not sentences2:
                return 0.0
            
            # Count matching sentences (simple overlap)
            set1 = set(s.strip() for s in sentences1 if len(s.strip()) > 5)
            set2 = set(s.strip() for s in sentences2 if len(s.strip()) > 5)
            
            if not set1 or not set2:
                return 0.0
            
            intersection = set1.intersection(set2)
            union = set1.union(set2)
            
            return len(intersection) / len(union) if union else 0.0
        except Exception as e:
            logger.error(f"Sentence similarity error: {e}")
            return 0.0
    
    def _check_ngram_overlap(self, text1: str, text2: str, n: int = 3) -> float:
        """N-gram overlap"""
        try:
            words1 = text1.split()
            words2 = text2.split()
            
            if len(words1) < n or len(words2) < n:
                return 0.0
            
            ngrams1 = set(' '.join(words1[i:i+n]) for i in range(len(words1)-n+1))
            ngrams2 = set(' '.join(words2[i:i+n]) for i in range(len(words2)-n+1))
            
            if not ngrams1 or not ngrams2:
                return 0.0
            
            intersection = ngrams1.intersection(ngrams2)
            union = ngrams1.union(ngrams2)
            
            return len(intersection) / len(union) if union else 0.0
        except Exception as e:
            logger.error(f"N-gram overlap error: {e}")
            return 0.0
    
    def _find_matching_phrases(self, text1: str, text2: str, min_words: int = 4) -> List[str]:
        """Find matching phrases between texts"""
        try:
            phrases = []
            words1 = text1.split()
            words2 = text2.split()
            text2_str = ' '.join(words2)
            
            for i in range(len(words1) - min_words + 1):
                phrase = ' '.join(words1[i:i+min_words])
                if len(phrase) > 10 and phrase in text2_str:
                    phrases.append(phrase)
            
            # Remove duplicates and sort by length
            return sorted(set(phrases), key=len, reverse=True)
        except Exception as e:
            logger.error(f"Finding matching phrases error: {e}")
            return []
    
    def _find_matching_sentences(self, text1: str, text2: str) -> List[str]:
        """Find matching sentences between texts"""
        try:
            sentences1 = self.sentence_pattern.split(text1)
            sentences2 = self.sentence_pattern.split(text2)
            
            matches = []
            for s1 in sentences1:
                s1_clean = s1.strip()
                if len(s1_clean) > 10:
                    for s2 in sentences2:
                        if s1_clean in s2.strip() or s2.strip() in s1_clean:
                            matches.append(s1_clean)
                            break
            
            return matches
        except Exception as e:
            logger.error(f"Finding matching sentences error: {e}")
            return []
    
    def batch_check(self, texts: List[str], threshold: float = 0.7) -> List[Dict]:
        """
        Check multiple texts against each other for plagiarism
        
        Args:
            texts: List of texts to check
            threshold: Similarity threshold
        
        Returns:
            List of plagiarism results for each pair
        """
        results = []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                result = self.check_plagiarism(texts[i], texts[j], threshold)
                if result.is_plagiarized:
                    results.append({
                        'pair': (i, j),
                        'score': result.similarity_score,
                        'confidence': result.confidence,
                        'matched_phrases': result.matched_phrases,
                        'source_sentences': result.source_sentences
                    })
        
        # Sort by score descending
        results.sort(key=lambda x: x['score'], reverse=True)
        return results

# ============================================================
# SMART GRADER - COMPLETE
# ============================================================

class SmartGrader:
    """AI-Powered Smart Grader for Essays and Assignments"""
    
    def __init__(self):
        self.plagiarism_detector = PlagiarismDetector()
        self.grade_mapping = {
            'A': (90, 100),
            'B': (80, 89),
            'C': (70, 79),
            'D': (60, 69),
            'F': (0, 59)
        }
    
    def grade_essay(
        self, 
        student_answer: str, 
        model_answer: str, 
        max_marks: int = 100,
        rubric: Dict = None,
        check_plagiarism: bool = True,
        plagiarism_threshold: float = 0.5
    ) -> GradingResult:
        """
        Grade an essay using AI with multiple scoring methods
        
        Args:
            student_answer: Student's answer text
            model_answer: Model/expected answer
            max_marks: Maximum marks for the essay
            rubric: Optional grading rubric
            check_plagiarism: Whether to check for plagiarism
            plagiarism_threshold: Threshold for plagiarism detection
        
        Returns:
            GradingResult object
        """
        # Clean texts
        student_clean = student_answer.strip()
        model_clean = model_answer.strip()
        
        if not student_clean:
            return GradingResult(
                marks=0,
                percentage=0,
                feedback=['No answer provided'],
                strengths=[],
                weaknesses=['No content submitted'],
                suggestions=['Please provide an answer'],
                passed=False,
                grade_letter='F'
            )
        
        # 1. Plagiarism Check
        plagiarism_result = None
        if check_plagiarism and model_clean:
            plagiarism_result = self.plagiarism_detector.check_plagiarism(
                student_clean, 
                model_clean, 
                threshold=plagiarism_threshold
            )
        
        # 2. Content Quality Score
        content_score = self._check_content_quality(student_clean, model_clean)
        
        # 3. Length Analysis
        length_score = self._check_length(student_clean)
        
        # 4. Keyword Presence
        keyword_score = self._check_keywords(student_clean, model_clean)
        
        # 5. Structure Analysis
        structure_score = self._check_structure(student_clean)
        
        # 6. Grammar & Language
        grammar_score = self._check_grammar(student_clean)
        
        # 7. Relevance Score
        relevance_score = self._check_relevance(student_clean, model_clean)
        
        # Calculate weighted total
        weights = {
            'content': 0.35,
            'length': 0.10,
            'keywords': 0.15,
            'structure': 0.10,
            'grammar': 0.10,
            'relevance': 0.20
        }
        
        total_score = (
            content_score * weights['content'] +
            length_score * weights['length'] +
            keyword_score * weights['keywords'] +
            structure_score * weights['structure'] +
            grammar_score * weights['grammar'] +
            relevance_score * weights['relevance']
        )
        
        # Apply plagiarism penalty
        if plagiarism_result and plagiarism_result.is_plagiarized:
            penalty = plagiarism_result.similarity_score * 0.5
            total_score *= (1 - penalty)
            feedback = ['⚠️ Plagiarism detected! Marks reduced.']
        else:
            feedback = []
        
        # Calculate final marks
        final_marks = round(total_score * max_marks, 2)
        percentage = round(total_score * 100, 2)
        
        # Determine grade letter
        grade_letter = self._get_grade(percentage)
        passed = grade_letter != 'F'
        
        # Generate feedback
        feedback.extend(self._generate_feedback(
            student_clean, model_clean, 
            content_score, structure_score, grammar_score
        ))
        
        # Breakdown
        breakdown = {
            'content_quality': round(content_score * 100, 2),
            'length_adequacy': round(length_score * 100, 2),
            'keyword_presence': round(keyword_score * 100, 2),
            'structure_score': round(structure_score * 100, 2),
            'grammar_score': round(grammar_score * 100, 2),
            'relevance_score': round(relevance_score * 100, 2),
            'plagiarism_penalty': round((1 - (total_score / (total_score + 0.01))) * 100, 2)
        }
        
        return GradingResult(
            marks=final_marks,
            percentage=percentage,
            feedback=feedback,
            strengths=self._get_strengths(student_clean, model_clean),
            weaknesses=self._get_weaknesses(student_clean, model_clean),
            suggestions=self._get_suggestions(student_clean, model_clean),
            plagiarism_check=plagiarism_result,
            breakdown=breakdown,
            grade_letter=grade_letter,
            passed=passed
        )
    
    def _check_content_quality(self, student_answer: str, model_answer: str) -> float:
        """Check content quality using multiple metrics"""
        try:
            # TF-IDF similarity
            tfidf = self.plagiarism_detector._check_tfidf(student_answer, model_answer)
            
            # Sequence similarity
            sequence = self.plagiarism_detector._check_sequence(student_answer, model_answer)
            
            # Weighted average
            return (tfidf * 0.6 + sequence * 0.4)
        except Exception as e:
            logger.error(f"Content quality error: {e}")
            return 0.3
    
    def _check_length(self, text: str) -> float:
        """Check if answer length is adequate"""
        try:
            words = len(text.split())
            if words < 30:
                return 0.2
            elif words < 50:
                return 0.5
            elif words < 100:
                return 0.7
            elif words < 200:
                return 0.85
            else:
                return 1.0
        except Exception as e:
            logger.error(f"Length check error: {e}")
            return 0.5
    
    def _check_keywords(self, student_text: str, model_text: str) -> float:
        """Check if key terms from model are present"""
        try:
            if not model_text:
                return 0.5
            
            # Extract keywords from model (simple TF-IDF)
            model_words = set(model_text.lower().split())
            student_words = set(student_text.lower().split())
            
            # Remove common stopwords
            stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'to', 'of', 'and', 
                        'for', 'on', 'at', 'by', 'in', 'with', 'without', 'about', 'from'}
            model_words = model_words - stopwords
            student_words = student_words - stopwords
            
            if not model_words:
                return 0.5
            
            matches = len(model_words.intersection(student_words))
            return min(matches / len(model_words), 1.0)
        except Exception as e:
            logger.error(f"Keyword check error: {e}")
            return 0.5
    
    def _check_structure(self, text: str) -> float:
        """Check essay structure (paragraphs, sentences)"""
        try:
            paragraphs = text.split('\n\n')
            sentences = self.plagiarism_detector.sentence_pattern.split(text)
            
            score = 0.0
            
            # Paragraph count (2-5 is good)
            para_count = len([p for p in paragraphs if len(p.strip()) > 20])
            if 2 <= para_count <= 5:
                score += 0.4
            elif para_count >= 1:
                score += 0.2
            
            # Sentence count (5+ is good)
            sent_count = len([s for s in sentences if len(s.strip()) > 5])
            if sent_count >= 5:
                score += 0.3
            elif sent_count >= 3:
                score += 0.15
            
            # Average sentence length (10-20 words is good)
            if sent_count > 0:
                avg_len = sum(len(s.split()) for s in sentences) / sent_count
                if 10 <= avg_len <= 20:
                    score += 0.3
                elif 5 <= avg_len <= 25:
                    score += 0.15
            
            return min(score, 1.0)
        except Exception as e:
            logger.error(f"Structure check error: {e}")
            return 0.5
    
    def _check_grammar(self, text: str) -> float:
        """Basic grammar check"""
        try:
            score = 0.5
            
            # Check capitalization
            sentences = self.plagiarism_detector.sentence_pattern.split(text)
            caps_count = 0
            for s in sentences:
                s = s.strip()
                if s and s[0].isupper():
                    caps_count += 1
            
            if sentences and caps_count / len(sentences) > 0.7:
                score += 0.2
            
            # Check punctuation
            if text.endswith(('.', '?', '!')):
                score += 0.15
            
            # Check for variety (simple heuristic)
            if len(set(text)) > 20:
                score += 0.15
            
            return min(score, 1.0)
        except Exception as e:
            logger.error(f"Grammar check error: {e}")
            return 0.5
    
    def _check_relevance(self, student_text: str, model_text: str) -> float:
        """Check relevance of answer to the question"""
        try:
            if not model_text:
                return 0.5
            
            # Use TF-IDF to check topic relevance
            vectorizer = TfidfVectorizer(stop_words='english')
            try:
                matrix = vectorizer.fit_transform([student_text, model_text])
                similarity = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
                return max(0, min(similarity, 1.0))
            except:
                return 0.5
        except Exception as e:
            logger.error(f"Relevance check error: {e}")
            return 0.5
    
    def _get_grade(self, percentage: float) -> str:
        """Get letter grade from percentage"""
        for grade, (min_score, max_score) in self.grade_mapping.items():
            if min_score <= percentage <= max_score:
                return grade
        return 'F'
    
    def _generate_feedback(
        self, 
        student_answer: str, 
        model_answer: str,
        content_score: float,
        structure_score: float,
        grammar_score: float
    ) -> List[str]:
        """Generate detailed feedback"""
        feedback = []
        
        # Content feedback
        if content_score < 0.4:
            feedback.append('📝 Content needs significant improvement. Key points are missing.')
        elif content_score < 0.6:
            feedback.append('📝 Content is adequate but could be more comprehensive.')
        else:
            feedback.append('📝 Good content coverage.')
        
        # Structure feedback
        if structure_score < 0.4:
            feedback.append('📋 Structure needs improvement. Consider using clear paragraphs and topic sentences.')
        elif structure_score < 0.6:
            feedback.append('📋 Structure is acceptable but could be more organized.')
        else:
            feedback.append('📋 Well-structured response.')
        
        # Grammar feedback
        if grammar_score < 0.4:
            feedback.append('✏️ Grammar needs improvement. Consider proofreading.')
        elif grammar_score < 0.6:
            feedback.append('✏️ Some grammatical errors present.')
        else:
            feedback.append('✏️ Good grammar and language usage.')
        
        # Length feedback
        words = len(student_answer.split())
        if words < 50:
            feedback.append('📏 Answer is too short. Provide more detail and analysis.')
        elif words > 300:
            feedback.append('📏 Answer is detailed but could be more concise.')
        
        return feedback
    
    def _get_strengths(self, student_answer: str, model_answer: str) -> List[str]:
        """Identify strengths in the answer"""
        strengths = []
        words = len(student_answer.split())
        
        if words > 100:
            strengths.append('Good length and detail')
        
        if self._check_grammar(student_answer) > 0.7:
            strengths.append('Good grammar and language usage')
        
        if self._check_structure(student_answer) > 0.7:
            strengths.append('Well-organized structure')
        
        if self._check_keywords(student_answer, model_answer) > 0.7:
            strengths.append('Good use of key concepts and terminology')
        
        return strengths[:3]  # Return top 3
    
    def _get_weaknesses(self, student_answer: str, model_answer: str) -> List[str]:
        """Identify weaknesses in the answer"""
        weaknesses = []
        words = len(student_answer.split())
        
        if words < 50:
            weaknesses.append('Answer is too brief')
        
        if self._check_grammar(student_answer) < 0.5:
            weaknesses.append('Grammar and language needs improvement')
        
        if self._check_structure(student_answer) < 0.5:
            weaknesses.append('Structure could be more organized')
        
        if self._check_keywords(student_answer, model_answer) < 0.5:
            weaknesses.append('Missing key concepts and terminology')
        
        return weaknesses[:3]  # Return top 3
    
    def _get_suggestions(self, student_answer: str, model_answer: str) -> List[str]:
        """Generate improvement suggestions"""
        suggestions = []
        words = len(student_answer.split())
        
        if words < 50:
            suggestions.append('Expand your answer with more detail and examples')
        
        if self._check_structure(student_answer) < 0.5:
            suggestions.append('Use clear paragraphs with topic sentences')
        
        if self._check_keywords(student_answer, model_answer) < 0.5:
            suggestions.append('Incorporate more key concepts and terminology')
        
        if self._check_grammar(student_answer) < 0.5:
            suggestions.append('Proofread your answer for grammar errors')
        
        # Add general suggestions
        if not suggestions:
            suggestions.append('Continue practicing to refine your writing skills')
            suggestions.append('Review the model answer for additional insights')
        
        return suggestions[:3]
    
    def batch_grade(
        self, 
        essays: List[Dict], 
        max_marks: int = 100,
        check_plagiarism: bool = True
    ) -> List[GradingResult]:
        """
        Grade multiple essays in batch
        
        Args:
            essays: List of dicts with 'student_answer' and 'model_answer'
            max_marks: Maximum marks for each essay
            check_plagiarism: Whether to check for plagiarism
        
        Returns:
            List of GradingResult objects
        """
        results = []
        for essay in essays:
            result = self.grade_essay(
                student_answer=essay.get('student_answer', ''),
                model_answer=essay.get('model_answer', ''),
                max_marks=essay.get('max_marks', max_marks),
                rubric=essay.get('rubric'),
                check_plagiarism=check_plagiarism,
                plagiarism_threshold=essay.get('plagiarism_threshold', 0.5)
            )
            results.append(result)
        
        return results