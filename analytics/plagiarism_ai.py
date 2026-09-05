# backend/analytics/plagiarism_ai.py - NEW FILE
import openai

class AIPlagiarismDetector(PlagiarismDetector):
    def __init__(self, openai_key):
        super().__init__()
        openai.api_key = openai_key
    
    def ai_check(self, text, threshold=0.8):
        """Use OpenAI to check if text is AI-generated or plagiarized"""
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a plagiarism detection AI. Analyze the text and return the plagiarism score (0-100) and explanation."},
                {"role": "user", "content": f"Check this text for plagiarism/duplicate content:\n\n{text}"}
            ]
        )
        return response.choices[0].message.content