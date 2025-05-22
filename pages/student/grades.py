import streamlit as st
import pandas as pd
from components.header import render_page_title
from database.schema import get_db_connection

def show():
    """Display the student transcript page with semester-by-semester GPA calculation"""
    render_page_title("📝", "Academic Transcript")
    
    # Get user ID from session
    student_id = st.session_state.user.get('user_id')
    
    # Connect to database
    conn = get_db_connection()
    
    # Get student information
    student = conn.execute(
        "SELECT * FROM students WHERE id = ?", (student_id,)
    ).fetchone()
    
    if not student:
        st.error("Student profile not found. Please contact an administrator.")
        return
    
    # Get all academic sessions
    academic_sessions = conn.execute(
        "SELECT name, is_active FROM academic_sessions ORDER BY name DESC"
    ).fetchall()
    
    if not academic_sessions:
        st.warning("No academic sessions found. Please contact an administrator.")
        return
    
    # Display student information at the top
    st.markdown("### Student Transcript")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Student ID:** {student['student_id']}")
        st.write(f"**Student Name:** {student['name']}")
        
        # Get total credits earned
        total_credits = conn.execute("""
            SELECT SUM(c.credit_hour) as total_credits
            FROM enrollments e
            JOIN courses c ON e.course_id = c.id
            JOIN grades g ON g.student_id = e.student_id AND g.course_id = e.course_id
            WHERE e.student_id = ? AND g.final IS NOT NULL
        """, (student_id,)).fetchone()
        
        earned_credits = total_credits['total_credits'] if total_credits and total_credits['total_credits'] else 0
        st.write(f"**Earned Credits:** {earned_credits}")
    
    with col2:
        # Get department from student info instead of querying programs table
        dept = student['dept'] if student['dept'] else "Not specified"
        st.write(f"**Department:** {dept}")
        
        # Calculate overall CGPA
        cgpa_data = conn.execute("""
            SELECT AVG(
                CASE
                    WHEN (g.mid + g.final) >= 80 THEN 4.0
                    WHEN (g.mid + g.final) >= 75 THEN 3.75
                    WHEN (g.mid + g.final) >= 70 THEN 3.5
                    WHEN (g.mid + g.final) >= 65 THEN 3.25
                    WHEN (g.mid + g.final) >= 60 THEN 3.0
                    WHEN (g.mid + g.final) >= 55 THEN 2.75
                    WHEN (g.mid + g.final) >= 50 THEN 2.5
                    WHEN (g.mid + g.final) >= 45 THEN 2.25
                    WHEN (g.mid + g.final) >= 40 THEN 2.0
                    ELSE 0
                END
            ) as cgpa
            FROM grades g
            WHERE g.student_id = ? AND g.final IS NOT NULL
        """, (student_id,)).fetchone()
        
        cgpa = cgpa_data['cgpa'] if cgpa_data and cgpa_data['cgpa'] else 0
        st.write(f"**Earned CGPA:** {cgpa:.2f}")
    
    # Grade point scale reference
    with st.expander("Grade Scale Reference"):
        grade_scale = {
            "Numerical Grade": ["80% and above", "75% to less than 80%", "70% to less than 75%", 
                               "65% to less than 70%", "60% to less than 65%", "55% to less than 60%",
                               "50% to less than 55%", "45% to less than 50%", "40% to less than 45%",
                               "Less than 40%"],
            "Letter Grade": ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D", "F"],
            "Grade Point": [4.00, 3.75, 3.50, 3.25, 3.00, 2.75, 2.50, 2.25, 2.00, 0.00]
        }
        
        st.table(pd.DataFrame(grade_scale))
    
    # Define grade components and their max values
    grade_components = {
        "Attendance": 5,
        "Class Tests": 10,
        "Assignments": 5,
        "Midterm": 30,
        "Final Exam": 50
    }
    
    # Get all semesters with enrolled courses
    enrolled_semesters = conn.execute("""
        SELECT DISTINCT e.semester
        FROM enrollments e
        WHERE e.student_id = ?
        ORDER BY e.semester DESC
    """, (student_id,)).fetchall()
    
    if not enrolled_semesters:
        st.info("You are not enrolled in any courses yet.")
        return
    
    # Show transcript for each semester
    all_semesters_gpa = []
    cumulative_points = 0
    cumulative_credits = 0
    
    for semester in enrolled_semesters:
        semester_name = semester['semester']
        
        st.markdown(f"## {semester_name}")
        
        # Get all courses for this semester
        courses_with_grades = conn.execute("""
            SELECT c.code, c.title, c.credit_hour,
                   g.mid, g.final,
                   (SELECT AVG(sa.marks/a.max_marks)*100 
                    FROM student_assignments sa 
                    JOIN assignments a ON sa.assignment_id = a.id 
                    WHERE sa.student_id = ? AND a.course_id = c.id AND a.semester = ?) as assignment_percent,
                   (SELECT AVG(sts.marks/ct.max_marks)*100 
                    FROM student_test_submissions sts 
                    JOIN class_tests ct ON sts.test_id = ct.id 
                    WHERE sts.student_id = ? AND ct.course_id = c.id AND ct.semester = ?) as test_percent,
                   (SELECT AVG(a.present)*100 
                    FROM attendance a 
                    WHERE a.student_id = ? AND a.course_id = c.id) as attendance_percent,
                   t.marks_finalized
            FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            LEFT JOIN grades g ON g.student_id = ? AND g.course_id = c.id AND g.semester = ?
            JOIN teaching t ON t.course_id = c.id AND t.semester = ?
            WHERE e.student_id = ? AND e.semester = ?
            ORDER BY c.code
        """, (student_id, semester_name, student_id, semester_name, student_id, 
              student_id, semester_name, semester_name, student_id, semester_name)).fetchall()
        
        if not courses_with_grades:
            st.info(f"No courses found for {semester_name}.")
            continue
        
        # Calculate grades and create a table
        grades_data = []
        semester_credit_hours = 0
        semester_grade_points = 0
        
        for course in courses_with_grades:
            # Calculate auto grades
            attendance_grade = 0
            if course['attendance_percent'] is not None:
                attendance_grade = min(grade_components["Attendance"], 
                                      course['attendance_percent'] * grade_components["Attendance"] / 100)
            
            test_grade = 0
            if course['test_percent'] is not None:
                test_grade = min(grade_components["Class Tests"], 
                                course['test_percent'] * grade_components["Class Tests"] / 100)
            
            assign_grade = 0
            if course['assignment_percent'] is not None:
                assign_grade = min(grade_components["Assignments"], 
                                  course['assignment_percent'] * grade_components["Assignments"] / 100)
            
            # Get midterm and final marks
            midterm = course['mid'] if course['mid'] is not None else 0
            final = course['final'] if course['final'] is not None else 0
            
            # Calculate total numerical grade
            total_grade = midterm + final + attendance_grade + test_grade + assign_grade
            
            # Determine letter grade and GPA
            letter_grade = "F"
            grade_point = 0.00
            
            # New grading system based on percentage
            if total_grade >= 80:
                letter_grade = "A+"
                grade_point = 4.00
            elif total_grade >= 75:
                letter_grade = "A"
                grade_point = 3.75
            elif total_grade >= 70:
                letter_grade = "A-"
                grade_point = 3.50
            elif total_grade >= 65:
                letter_grade = "B+"
                grade_point = 3.25
            elif total_grade >= 60:
                letter_grade = "B"
                grade_point = 3.00
            elif total_grade >= 55:
                letter_grade = "B-"
                grade_point = 2.75
            elif total_grade >= 50:
                letter_grade = "C+"
                grade_point = 2.50
            elif total_grade >= 45:
                letter_grade = "C"
                grade_point = 2.25
            elif total_grade >= 40:
                letter_grade = "D"
                grade_point = 2.00
            
            # Calculate points earned for this course
            credit_hour = course['credit_hour']
            points_earned = credit_hour * grade_point
            
            # Add to grade data
            if course['mid'] is not None or course['final'] is not None:
                grades_data.append({
                    "Course Code": course['code'],
                    "Course Name": course['title'],
                    "Grade": letter_grade,
                    "Credit Hours": credit_hour,
                    "Credit Attempted": credit_hour,
                    "Grade Point": grade_point,
                    "Points Earned": points_earned,
                })
                
                # Add to semester GPA calculation
                semester_credit_hours += credit_hour
                semester_grade_points += points_earned
        
        # Create DataFrame for semester
        if grades_data:
            df = pd.DataFrame(grades_data)
            
            # Display semester courses and grades
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Calculate semester GPA
            if semester_credit_hours > 0:
                semester_gpa = semester_grade_points / semester_credit_hours
                
                # Display semester totals
                st.markdown(f"**Semester Credits: {semester_credit_hours:.1f}** | **Semester GPA: {semester_gpa:.2f}**")
                
                # Add to overall GPA calculation
                all_semesters_gpa.append({
                    "Semester": semester_name, 
                    "GPA": semester_gpa,
                    "Credits": semester_credit_hours
                })
                
                # Update cumulative calculations
                cumulative_points += semester_grade_points
                cumulative_credits += semester_credit_hours
        
        st.markdown("---")
    
    # Display cumulative GPA
    if cumulative_credits > 0:
        cumulative_gpa = cumulative_points / cumulative_credits
        st.markdown(f"### Cumulative GPA: {cumulative_gpa:.2f}")
        st.markdown(f"### Total Credits Earned: {cumulative_credits:.1f}")
    
    # Display semester-by-semester GPA summary
    if all_semesters_gpa:
        st.markdown("### GPA Summary by Semester")
        summary_df = pd.DataFrame(all_semesters_gpa)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
    
    # Close database connection
    conn.close() 