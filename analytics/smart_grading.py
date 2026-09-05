# backend/analytics/smart_grading.py - NEW FILE
import openai
from transformers import pipeline

class AISmartGrader:
    def __init__(self, openai_key):
        self.openai_key = openai_key
        openai.api_key = openai_key
        
        # Load BERT for similarity (fallback)
        try:
            self.similarity_model = pipeline(
                "feature-extraction", 
                model="sentence-transformers/all-MiniLM-L6-v2"
            )
        except:
            self.similarity_model = None
    
    def grade_essay(self, student_answer, model_answer, rubric, max_marks=100):
        """
        Grade essay using OpenAI API
        """
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"""
                        You are an AI essay grader. Grade the student essay against the model answer.
                        Return ONLY a JSON object with these fields:
                        - score: number (0-{max_marks})
                        - feedback: string
                        - strengths: array of strings
                        - weaknesses: array of strings
                        - suggestions: array of strings
                        
                        Rubric:
                        {rubric}
                    """},
                    {"role": "user", "content": f"""
                        Model Answer:
                        {model_answer}
                        
                        Student Answer:
                        {student_answer}
                    """}
                ],
                temperature=0.3
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            # Fallback to BERT similarity
            return self.grade_with_bert(student_answer, model_answer, max_marks)
    
    def grade_with_bert(self, student_answer, model_answer, max_marks):
        """Fallback grading using BERT similarity"""
        from sklearn.metrics.pairwise import cosine_similarity
        from sentence_transformers import SentenceTransformer
        
        model = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = model.encode([student_answer, model_answer])
        similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        
        score = similarity * max_marks
        return {
            'score': round(score, 2),
            'feedback': f'Similarity score: {similarity*100:.1f}%',
            'strengths': ['Content matches model answer'],
            'weaknesses': ['AI grading - manual review recommended'],
            'suggestions': ['Please review the automated grade']
        }