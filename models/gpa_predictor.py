import numpy as np
from database.schema import get_db_connection

def calculate_gpa(grades):
    """Calculate GPA based on grades
    
    Args:
        grades: Dictionary with course_id as key and 
                dict of mid, assignment, final as value
                
    Returns:
        float: GPA on a 4.0 scale
    """
    total_points = 0
    total_credits = 0
    
    # Get connection to database
    conn = get_db_connection()
    
    for course_id, marks in grades.items():
        # Get course credit hours
        course = conn.execute(
            "SELECT credit_hour FROM courses WHERE id = ?", 
            (course_id,)
        ).fetchone()
        
        if not course:
            continue
            
        credit_hour = course['credit_hour']
        
        # Calculate total marks (mid + assignment + final)
        total_marks = marks.get('mid', 0) + marks.get('assignment', 0) + marks.get('final', 0)
        
        # Convert to grade point using the new grading system
        if total_marks >= 80:
            grade_point = 4.00  # A+
        elif total_marks >= 75:
            grade_point = 3.75  # A
        elif total_marks >= 70:
            grade_point = 3.50  # A-
        elif total_marks >= 65:
            grade_point = 3.25  # B+
        elif total_marks >= 60:
            grade_point = 3.00  # B
        elif total_marks >= 55:
            grade_point = 2.75  # B-
        elif total_marks >= 50:
            grade_point = 2.50  # C+
        elif total_marks >= 45:
            grade_point = 2.25  # C
        elif total_marks >= 40:
            grade_point = 2.00  # D
        else:
            grade_point = 0.00  # F
            
        # Add to total
        total_points += grade_point * credit_hour
        total_credits += credit_hour
        
    conn.close()
    
    # Calculate GPA
    if total_credits > 0:
        return round(total_points / total_credits, 2)
    else:
        return 0.0

def predict_gpa(student_id, semester=None):
    """Predict GPA for a student
    
    Args:
        student_id: ID of the student
        semester: Semester to predict for, if None uses current grades
        
    Returns:
        float: Predicted GPA
    """
    conn = get_db_connection()
    
    # Get student's current grades
    query = """
        SELECT g.course_id, g.mid, g.assignment, g.final, c.credit_hour,
               (SELECT AVG(sa.marks/a.max_marks)*5 
                FROM student_assignments sa 
                JOIN assignments a ON sa.assignment_id = a.id 
                WHERE sa.student_id = g.student_id AND a.course_id = g.course_id AND a.semester = g.semester) as assignment_score,
               (SELECT AVG(sts.marks/ct.max_marks)*10 
                FROM student_test_submissions sts 
                JOIN class_tests ct ON sts.test_id = ct.id 
                WHERE sts.student_id = g.student_id AND ct.course_id = g.course_id AND ct.semester = g.semester) as test_score,
               (SELECT AVG(a.present)*5 
                FROM attendance a 
                WHERE a.student_id = g.student_id AND a.course_id = g.course_id) as attendance_score
        FROM grades g
        JOIN courses c ON g.course_id = c.id
        WHERE g.student_id = ?
    """
    params = [student_id]
    
    if semester:
        query += " AND g.semester = ?"
        params.append(semester)
        
    grades_data = conn.execute(query, params).fetchall()
    
    # Get student's attendance
    attendance_query = """
        SELECT a.course_id, COUNT(*) as total_classes,
        SUM(CASE WHEN a.present = 1 THEN 1 ELSE 0 END) as attended_classes
        FROM attendance a
        WHERE a.student_id = ?
        GROUP BY a.course_id
    """
    attendance_data = conn.execute(attendance_query, [student_id]).fetchall()
    
    conn.close()
    
    # Convert to dictionary format
    grades = {}
    for grade in grades_data:
        # Include all components in the grade calculation
        mid = grade['mid'] or 0
        final = grade['final'] or 0
        assignment_score = grade['assignment_score'] or 0
        test_score = grade['test_score'] or 0
        attendance_score = grade['attendance_score'] or 0
        
        total = mid + final + assignment_score + test_score + attendance_score
        
        grades[grade['course_id']] = {
            'mid': mid,
            'final': final,
            'assignment': assignment_score,
            'tests': test_score,
            'attendance': attendance_score,
            'total': total,
            'credit_hour': grade['credit_hour']
        }
    
    # Calculate attendance percentage
    attendance = {}
    for att in attendance_data:
        course_id = att['course_id']
        if att['total_classes'] > 0:
            attendance[course_id] = att['attended_classes'] / att['total_classes']
        else:
            attendance[course_id] = 1.0  # Default to 100% if no classes
    
    # Simple prediction model:
    # 1. If completed grades: use actual GPA
    # 2. If partial grades: predict remaining based on current performance
    # 3. Adjust based on attendance
    
    # Get current GPA
    current_gpa = calculate_gpa(grades)
    
    # Simple prediction: use current GPA and adjust slightly based on attendance
    predicted_gpa = current_gpa
    
    # Adjust based on attendance (lower attendance = lower GPA prediction)
    avg_attendance = 1.0
    if attendance:
        avg_attendance = sum(attendance.values()) / len(attendance)
    
    # Attendance below 75% negatively impacts GPA prediction
    if avg_attendance < 0.75:
        attendance_impact = (0.75 - avg_attendance) * 0.5
        predicted_gpa = max(0, predicted_gpa - attendance_impact)
    
    return round(predicted_gpa, 2) 