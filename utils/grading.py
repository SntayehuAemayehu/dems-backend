# backend/utils/grading.py
# COMPLETE GRADE CALCULATION UTILITY

from decimal import Decimal

def calculate_grade(percentage):
    """
    Calculate letter grade based on percentage
    
    Args:
        percentage: float or Decimal (0-100)
    
    Returns:
        dict: {
            'letter': str (A+, A, B+, B, B-, C+, C, C-, D, F, NON),
            'gpa': float,
            'status': str (PASS/FAIL)
        }
    """
    if percentage is None:
        return {
            'letter': 'NON',
            'gpa': 0.0,
            'status': 'NON'
        }
    
    # Convert to float if Decimal
    if isinstance(percentage, Decimal):
        percentage = float(percentage)
    
    # Grade mapping
    if percentage >= 90:
        return {'letter': 'A+', 'gpa': 4.0, 'status': 'PASS'}
    elif percentage >= 85:
        return {'letter': 'A', 'gpa': 4.0, 'status': 'PASS'}
    elif percentage >= 80:
        return {'letter': 'A-', 'gpa': 3.7, 'status': 'PASS'}
    elif percentage >= 75:
        return {'letter': 'B+', 'gpa': 3.3, 'status': 'PASS'}
    elif percentage >= 70:
        return {'letter': 'B', 'gpa': 3.0, 'status': 'PASS'}
    elif percentage >= 65:
        return {'letter': 'B-', 'gpa': 2.7, 'status': 'PASS'}
    elif percentage >= 60:
        return {'letter': 'C+', 'gpa': 2.3, 'status': 'PASS'}
    elif percentage >= 55:
        return {'letter': 'C', 'gpa': 2.0, 'status': 'PASS'}
    elif percentage >= 50:
        return {'letter': 'C-', 'gpa': 1.7, 'status': 'PASS'}
    elif percentage >= 45:
        return {'letter': 'D+', 'gpa': 1.3, 'status': 'PASS'}
    elif percentage >= 40:
        return {'letter': 'D', 'gpa': 1.0, 'status': 'PASS'}
    else:
        return {'letter': 'F', 'gpa': 0.0, 'status': 'FAIL'}


def calculate_grade_from_mark(marks_obtained, total_marks):
    """
    Calculate grade from obtained marks and total marks
    
    Args:
        marks_obtained: float
        total_marks: float
    
    Returns:
        dict: Grade information
    """
    if total_marks == 0:
        return {'letter': 'NON', 'gpa': 0.0, 'status': 'NON', 'percentage': 0}
    
    percentage = (marks_obtained / total_marks) * 100
    grade_info = calculate_grade(percentage)
    grade_info['percentage'] = round(percentage, 2)
    grade_info['marks_obtained'] = marks_obtained
    grade_info['total_marks'] = total_marks
    
    return grade_info


# Grade point values for reference
GRADE_POINTS = {
    'A+': 4.0,
    'A': 4.0,
    'A-': 3.7,
    'B+': 3.3,
    'B': 3.0,
    'B-': 2.7,
    'C+': 2.3,
    'C': 2.0,
    'C-': 1.7,
    'D+': 1.3,
    'D': 1.0,
    'F': 0.0,
    'NON': 0.0,
}