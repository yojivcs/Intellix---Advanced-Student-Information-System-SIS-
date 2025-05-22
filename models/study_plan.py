import json
from datetime import datetime, timedelta
from database.schema import get_db_connection
from models.gpa_predictor import calculate_gpa

def generate_study_plan(student_id, semester=None):
    """Generate a study plan for a student based on their current grades and attendance
    
    Args:
        student_id: ID of the student
        semester: Semester to generate plan for, if None uses current semester
        
    Returns:
        dict: Study plan with recommendations
    """
    conn = get_db_connection()
    
    # Get student info
    student = conn.execute(
        "SELECT * FROM students WHERE id = ?", 
        (student_id,)
    ).fetchone()
    
    if not student:
        conn.close()
        return {"error": "Student not found"}
    
    # Verify student info is correct
    if not student['name']:
        conn.close()
        return {"error": "Invalid student record - missing name"}
    
    # Get current semester if not provided
    if not semester:
        # Use latest semester from enrollments
        semester_data = conn.execute(
            "SELECT semester FROM enrollments WHERE student_id = ? ORDER BY created_at DESC LIMIT 1",
            (student_id,)
        ).fetchone()
        
        if semester_data:
            semester = semester_data['semester']
        else:
            semester = f"Fall {datetime.now().year}"  # Default
    
    # Get student's courses for this semester
    courses_query = """
        SELECT c.id, c.code, c.title, c.credit_hour,
               g.mid, g.assignment, g.final
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        LEFT JOIN grades g ON e.student_id = g.student_id AND e.course_id = g.course_id AND e.semester = g.semester
        WHERE e.student_id = ? AND e.semester = ?
    """
    courses = conn.execute(courses_query, (student_id, semester)).fetchall()
    
    # Get attendance data
    attendance_query = """
        SELECT a.course_id, COUNT(*) as total_classes,
               SUM(CASE WHEN a.present = 1 THEN 1 ELSE 0 END) as attended_classes
        FROM attendance a
        JOIN enrollments e ON a.student_id = e.student_id AND a.course_id = e.course_id
        WHERE a.student_id = ? AND e.semester = ?
        GROUP BY a.course_id
    """
    attendance_data = conn.execute(attendance_query, (student_id, semester)).fetchall()
    
    # Double-check that we're generating a plan for the correct student
    verification_check = conn.execute(
        "SELECT id, name FROM students WHERE id = ?", 
        (student_id,)
    ).fetchone()
    
    if not verification_check or verification_check['id'] != student_id:
        conn.close()
        return {"error": "Student verification failed"}
        
    student_name = verification_check['name']
    
    # Close the database connection after all data retrieval
    conn.close()
    
    # Process course data
    course_analysis = []
    grades = {}
    
    for course in courses:
        course_id = course['id']
        
        # Get attendance for this course
        attendance_pct = None
        for att in attendance_data:
            if att['course_id'] == course_id and att['total_classes'] > 0:
                attendance_pct = (att['attended_classes'] / att['total_classes']) * 100
                break
        
        # Calculate total score so far
        mid_score = course['mid'] or 0
        assignment_score = course['assignment'] or 0
        final_score = course['final'] or 0
        total_score = mid_score + assignment_score + final_score
        
        # Determine status and recommendations
        status = "On Track"
        priority = "Low"
        recommendations = []
        
        # Check if midterm marks are available but final is not
        if mid_score > 0 and final_score == 0:
            if mid_score < 15:  # Below 50% of midterm (assuming midterm is 30%)
                status = "At Risk"
                priority = "High"
                recommendations.append("Focus on understanding core concepts")
                recommendations.append("Attend all remaining classes")
                recommendations.append("Schedule weekly review sessions")
            elif mid_score < 20:  # Below 70% of midterm
                status = "Needs Improvement"
                priority = "Medium"
                recommendations.append("Review weak areas from midterm")
                recommendations.append("Allocate extra practice time")
        
        # Check attendance
        if attendance_pct is not None:
            if attendance_pct < 75:
                status = "At Risk" if status == "On Track" else status
                priority = "High" if priority == "Low" else priority
                recommendations.append("Improve attendance immediately")
                recommendations.append("Get notes from missed classes")
            
        # Store analyzed data
        course_analysis.append({
            "course_id": course_id,
            "code": course['code'],
            "title": course['title'],
            "credit_hour": course['credit_hour'],
            "mid_score": mid_score,
            "assignment_score": assignment_score,
            "final_score": final_score,
            "total_score": total_score,
            "attendance": attendance_pct,
            "status": status,
            "priority": priority,
            "recommendations": recommendations
        })
        
        # Add to grades dict for GPA calculation
        grades[course_id] = {
            "mid": mid_score,
            "assignment": assignment_score,
            "final": final_score
        }
    
    # Calculate current GPA
    current_gpa = calculate_gpa(grades)
    
    # Generate weekly study plan
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    weekly_plan = []
    
    # Prioritize courses by status
    high_priority = [c for c in course_analysis if c['priority'] == 'High']
    medium_priority = [c for c in course_analysis if c['priority'] == 'Medium']
    low_priority = [c for c in course_analysis if c['priority'] == 'Low']
    
    # Days of the week
    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Assign study hours based on priority
    for i, day in enumerate(weekdays):
        day_date = start_of_week + timedelta(days=i)
        day_plan = {
            "day": day,
            "date": day_date.strftime("%Y-%m-%d"),
            "study_blocks": []
        }
        
        # Assign morning hours to high priority
        if high_priority and i < 5:  # Weekdays
            course = high_priority[i % len(high_priority)]
            day_plan["study_blocks"].append({
                "time": "9:00 AM - 11:00 AM",
                "course": course['code'],
                "focus": course['recommendations'][0] if course['recommendations'] else "Review content"
            })
        
        # Assign afternoon to medium priority
        if medium_priority and i < 6:  # Including Saturday
            course = medium_priority[i % len(medium_priority)]
            day_plan["study_blocks"].append({
                "time": "2:00 PM - 4:00 PM",
                "course": course['code'],
                "focus": course['recommendations'][0] if course['recommendations'] else "Practice problems"
            })
        
        # Assign evening to rotate through all courses
        if i < 6:  # All days except Sunday
            all_courses = course_analysis
            if all_courses:
                course = all_courses[i % len(all_courses)]
                day_plan["study_blocks"].append({
                    "time": "7:00 PM - 8:30 PM",
                    "course": course['code'],
                    "focus": "Review and practice"
                })
        
        weekly_plan.append(day_plan)
    
    # Create final study plan
    study_plan = {
        "student_id": student_id,
        "student_name": student_name,  # Use verified student name
        "semester": semester,
        "current_gpa": current_gpa,
        "generated_date": datetime.now().strftime("%Y-%m-%d"),
        "course_analysis": course_analysis,
        "weekly_plan": weekly_plan,
        "general_recommendations": [
            "Balance study time across all courses",
            "Take regular breaks to maintain focus",
            "Form study groups for difficult courses",
            "Reach out to professors during office hours",
            "Review material within 24 hours of each class"
        ]
    }
    
    # Store in database
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO study_plans (student_id, plan_json, semester) VALUES (?, ?, ?)",
        (student_id, json.dumps(study_plan), semester)
    )
    conn.commit()
    conn.close()
    
    return study_plan 