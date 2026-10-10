# backend/analytics/recommendations.py
# AI Course Recommendations
# ✅ Works with or without scikit-learn (Python 3.14 compatible)

from collections import defaultdict
import json

# ============================================================
# ✅ OPTIONAL IMPORTS
# ============================================================
try:
    import numpy as np
except ImportError:
    np = None
    print("⚠️ numpy not available in recommendations.py")

try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
    print("✅ sklearn loaded in recommendations.py")
except ImportError:
    cosine_similarity = None
    TfidfVectorizer = None
    SKLEARN_AVAILABLE = False
    print("⚠️ sklearn not available in recommendations.py - using popularity fallback")


class CourseRecommender:
    def __init__(self):
        if SKLEARN_AVAILABLE:
            self.vectorizer = TfidfVectorizer(stop_words='english')
        else:
            self.vectorizer = None
        self.course_features = {}
        self.user_history = {}

    def load_data(self, courses, enrollments):
        """Load course and enrollment data"""
        self.courses = courses
        self.enrollments = enrollments

        # Build course features
        for course in courses:
            features = f"{course.title} {course.description} {course.department} {course.course_code}"
            self.course_features[course.id] = features

        # Build user history
        for enrollment in enrollments:
            user_id = enrollment.user_id
            if user_id not in self.user_history:
                self.user_history[user_id] = []
            self.user_history[user_id].append(enrollment.course_id)

    def get_recommendations(self, user_id, top_n=5):
        """Get personalized course recommendations"""
        if user_id not in self.user_history or not self.user_history[user_id]:
            popular = self._get_popular_courses(top_n)
            return {
                'content_based': popular,
                'collaborative': popular,
                'hybrid': popular
            }

        user_courses = self.user_history[user_id]

        content_recommendations = self._content_based(user_courses, top_n)
        collab_recommendations = self._collaborative_filtering(user_id, top_n)
        hybrid = self._hybrid_recommendations(
            content_recommendations,
            collab_recommendations,
            top_n
        )

        return {
            'content_based': content_recommendations,
            'collaborative': collab_recommendations,
            'hybrid': hybrid
        }

    def _content_based(self, user_courses, top_n):
        """Content-based filtering"""
        # ✅ Fallback if sklearn not available
        if not SKLEARN_AVAILABLE or self.vectorizer is None:
            return self._get_popular_courses(top_n)

        user_features = []
        for course_id in user_courses:
            if course_id in self.course_features:
                user_features.append(self.course_features[course_id])

        if not user_features:
            return self._get_popular_courses(top_n)

        user_profile = " ".join(user_features)

        all_features = [user_profile] + [
            self.course_features[cid] for cid in self.course_features
            if cid not in user_courses
        ]

        try:
            tfidf_matrix = self.vectorizer.fit_transform(all_features)
            similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        except Exception as e:
            print(f"⚠️ Content-based recommendation failed: {e}")
            return self._get_popular_courses(top_n)

        course_ids = [cid for cid in self.course_features if cid not in user_courses]
        recommendations = sorted(
            zip(course_ids, similarities),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        return [{'course_id': cid, 'score': float(score)} for cid, score in recommendations]

    def _collaborative_filtering(self, user_id, top_n):
        """Collaborative filtering - find similar users"""
        similar_users = self._find_similar_users(user_id)

        if not similar_users:
            return self._get_popular_courses(top_n)

        recommendations = defaultdict(float)
        user_courses = set(self.user_history.get(user_id, []))

        for similar_user, similarity in similar_users[:5]:
            for course_id in self.user_history.get(similar_user, []):
                if course_id not in user_courses:
                    recommendations[course_id] += similarity

        sorted_recommendations = sorted(
            recommendations.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        return [{'course_id': cid, 'score': score} for cid, score in sorted_recommendations]

    def _find_similar_users(self, user_id):
        """Find users with similar course history"""
        if user_id not in self.user_history:
            return []

        user_courses = set(self.user_history[user_id])
        similar = []

        for other_user, courses in self.user_history.items():
            if other_user == user_id:
                continue

            other_courses = set(courses)
            if not other_courses:
                continue

            intersection = len(user_courses.intersection(other_courses))
            union = len(user_courses.union(other_courses))
            similarity = intersection / union if union > 0 else 0

            if similarity > 0.3:
                similar.append((other_user, similarity))

        return sorted(similar, key=lambda x: x[1], reverse=True)

    def _hybrid_recommendations(self, content, collaborative, top_n):
        """Combine content and collaborative recommendations"""
        hybrid = defaultdict(float)

        for rec in content:
            hybrid[rec['course_id']] += rec['score'] * 0.6

        for rec in collaborative:
            hybrid[rec['course_id']] += rec['score'] * 0.4

        sorted_hybrid = sorted(
            hybrid.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        return [{'course_id': cid, 'score': score} for cid, score in sorted_hybrid]

    def _get_popular_courses(self, top_n):
        """Fallback: recommend most popular courses"""
        if not hasattr(self, 'enrollments'):
            return []

        course_counts = defaultdict(int)
        for enrollment in self.enrollments:
            course_counts[enrollment.course_id] += 1

        if not course_counts:
            return []

        max_count = max(course_counts.values()) if course_counts else 1

        sorted_courses = sorted(
            course_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        return [{'course_id': cid, 'score': count / max_count}
                for cid, count in sorted_courses]