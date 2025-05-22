import streamlit as st
import os
import pandas as pd
import numpy as np
import plotly.express as px
from PIL import Image

# Import modules
from utils.auth import check_login, login_required, logout, init_session
from components.sidebar import render_sidebar
from components.header import render_header, render_page_title
from database.schema import get_db_connection

# Import page modules
from pages.admin import dashboard, students, teachers, courses, assignments, ai_tools, analytics, course_enrollment, academic_calendar, student_transcript_viewer
from pages.teacher import courses as teacher_courses, grades as teacher_grades, attendance as teacher_attendance, analytics as teacher_analytics, assignments as teacher_assignments
from pages.student import courses as student_courses, grades as student_grades, attendance as student_attendance, study_plan, gpa_prediction, assignments as student_assignments

# Add the import for the new message modules
import pages.teacher.messages
import pages.student.messages

# Set page config
st.set_page_config(
    page_title="Intellix - AI-Enhanced SIS",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
init_session()

# Check if static/images directory exists, create if not
os.makedirs("static/images", exist_ok=True)

# Check if logo exists, create a placeholder if not
logo_path = "static/images/intellix_logo.png"
if not os.path.exists(logo_path):
    # Create a simple placeholder logo
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 2))
    ax.text(0.5, 0.5, 'Intellix', fontsize=30, ha='center', va='center', color='black')
    ax.axis('off')
    plt.savefig(logo_path, bbox_inches='tight', pad_inches=0.1)
    plt.close()

# Page routing
def main():
    # Show login page if not authenticated
    if not login_required():
        show_login_page()
        return
    
    # Show appropriate page based on current_page
    render_sidebar()
    
    # Get current page from session state
    current_page = st.session_state.current_page
    
    # Route to the appropriate page function
    user_role = st.session_state.user.get('role')
    
    # Admin pages
    if user_role == 'admin':
        if current_page == 'dashboard':
            dashboard.show()
        elif current_page == 'students':
            students.show()
        elif current_page == 'teachers':
            teachers.show()
        elif current_page == 'courses':
            courses.show()
        elif current_page == 'course_enrollment':
            course_enrollment.show()
        elif current_page == 'academic_calendar':
            academic_calendar.show()
        elif current_page == 'assignments':
            assignments.show()
        elif current_page == 'ai_tools':
            ai_tools.show()
        elif current_page == 'analytics':
            analytics.show()
        elif current_page == 'student_transcript_viewer':
            student_transcript_viewer.show()
    
    # Teacher pages
    elif user_role == 'teacher':
        if current_page == 'dashboard':
            teacher_dashboard()
        elif current_page == 'teacher_courses':
            teacher_courses.show()
        elif current_page == 'teacher_grades':
            teacher_grades.show()
        elif current_page == 'teacher_attendance':
            teacher_attendance.show()
        elif current_page == 'teacher_analytics':
            teacher_analytics.show()
        elif current_page == 'teacher_assignments':
            teacher_assignments.show()
        elif current_page == 'teacher_messages':
            pages.teacher.messages.show()
    
    # Student pages
    elif user_role == 'student':
        if current_page == 'dashboard':
            student_dashboard()
        elif current_page == 'student_courses':
            student_courses.show()
        elif current_page == 'student_grades':
            student_grades.show()
        elif current_page == 'student_attendance':
            student_attendance.show()
        elif current_page == 'student_study_plan':
            study_plan.show()
        elif current_page == 'student_gpa_prediction':
            gpa_prediction.show()
        elif current_page == 'student_assignments':
            student_assignments.show()
        elif current_page == 'student_messages':
            pages.student.messages.show()

def show_login_page():
    """Display the login page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        render_header("Intellix", "AI-Enhanced Student Information System")
        
        # Login form
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit:
                if username and password:
                    user = check_login(username, password)
                    if user:
                        st.session_state.user = user
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                else:
                    st.warning("Please enter username and password")
        
        # Display demo credentials
        with st.expander("Demo Credentials"):
            st.info("""
            **Admin:**
            - Username: admin
            - Password: admin123
            
            **Teacher:**
            - Username: achowdhury
            - Password: YZm0Xq92
            
            **Student:**
            - Username: vbarua
            - Password: CXQ7JIqw
            """)

def teacher_dashboard():
    """Display the teacher dashboard"""
    render_page_title("👩‍🏫", "Teacher Dashboard")
    
    # Get user ID from session
    teacher_id = st.session_state.user.get('user_id')
    
    # Connect to database
    conn = get_db_connection()
    
    # Get teacher information
    teacher = conn.execute(
        "SELECT * FROM teachers WHERE id = ?", (teacher_id,)
    ).fetchone()
    
    if not teacher:
        st.error("Teacher profile not found. Please contact an administrator.")
        return
    
    # Get current active session
    active_session = conn.execute(
        "SELECT name FROM academic_sessions WHERE is_active = 1"
    ).fetchone()
    
    session_name = active_session['name'] if active_session else "No active session"
    
    # Create layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Welcome message
        st.write(f"### Welcome, {teacher['name']}!")
        st.write(f"**Department:** {teacher['dept']}")
        st.write(f"**Current Session:** {session_name}")
        
        # Recent activities
        st.write("### Recent Activities")
        
        # Get recent grade entries
        recent_grades = conn.execute("""
            SELECT g.updated_at, c.code, c.title
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            JOIN teaching t ON t.course_id = c.id
            WHERE t.teacher_id = ? AND g.semester = ?
            ORDER BY g.updated_at DESC
            LIMIT 5
        """, (teacher_id, session_name)).fetchall()
        
        if recent_grades:
            st.write("**Recent Grade Entries:**")
            for grade in recent_grades:
                st.write(f"- {grade['updated_at']}: Updated grades for {grade['code']} - {grade['title']}")
        else:
            st.info("No recent grade entries found.")
        
        # Get recent attendance entries
        recent_attendance = conn.execute("""
            SELECT a.date, c.code, c.title, COUNT(a.id) as count
            FROM attendance a
            JOIN courses c ON a.course_id = c.id
            JOIN teaching t ON t.course_id = c.id
            WHERE t.teacher_id = ? AND t.semester = ?
            GROUP BY a.date, c.code
            ORDER BY a.date DESC
            LIMIT 5
        """, (teacher_id, session_name)).fetchall()
        
        if recent_attendance:
            st.write("**Recent Attendance Records:**")
            for att in recent_attendance:
                st.write(f"- {att['date']}: Marked attendance for {att['code']} - {att['title']} ({att['count']} students)")
        else:
            st.info("No recent attendance records found.")
    
    with col2:
        # Stats cards
        st.write("### Quick Stats")
        
        # Count assigned courses
        course_count = conn.execute("""
            SELECT COUNT(DISTINCT c.id) as count
            FROM courses c
            JOIN teaching t ON c.id = t.course_id
            WHERE t.teacher_id = ? AND t.semester = ?
        """, (teacher_id, session_name)).fetchone()
        
        courses_assigned = course_count['count'] if course_count else 0
        
        # Count pending grades (students without final grades)
        pending_grades = conn.execute("""
            SELECT COUNT(*) as count
            FROM enrollments e
            JOIN courses c ON e.course_id = c.id
            JOIN teaching t ON t.course_id = c.id
            LEFT JOIN grades g ON g.student_id = e.student_id AND g.course_id = e.course_id AND g.semester = e.semester
            WHERE t.teacher_id = ? AND e.semester = ? AND (g.final IS NULL OR g.final = 0)
        """, (teacher_id, session_name)).fetchone()
        
        pending_grade_count = pending_grades['count'] if pending_grades else 0
        
        # Calculate attendance completion percentage
        attendance_stats = conn.execute("""
            SELECT COUNT(DISTINCT e.student_id) as total_students,
                  (SELECT COUNT(*) FROM attendance a 
                   JOIN teaching t2 ON t2.course_id = a.course_id 
                   WHERE t2.teacher_id = ? AND t2.semester = ?) as attendance_entries
            FROM enrollments e
            JOIN teaching t ON t.course_id = e.course_id
            WHERE t.teacher_id = ? AND e.semester = ?
        """, (teacher_id, session_name, teacher_id, session_name)).fetchone()
        
        attendance_percentage = 0
        if attendance_stats and attendance_stats['total_students'] > 0:
            attendance_percentage = min(100, (attendance_stats['attendance_entries'] / attendance_stats['total_students']) * 100)
        
        # Identify at-risk students (less than 70% attendance or failing grades)
        at_risk_students = conn.execute("""
            SELECT COUNT(DISTINCT e.student_id) as count
            FROM enrollments e
            JOIN teaching t ON t.course_id = e.course_id
            LEFT JOIN grades g ON g.student_id = e.student_id AND g.course_id = e.course_id AND g.semester = e.semester
            WHERE t.teacher_id = ? AND e.semester = ? AND 
                  ((g.mid + g.assignment + g.final) < 50 OR g.mid < 15 OR
                   e.student_id IN (
                       SELECT DISTINCT a.student_id
                       FROM attendance a
                       JOIN teaching t2 ON t2.course_id = a.course_id
                       WHERE t2.teacher_id = ? AND t2.semester = ? AND a.present = 0
                       GROUP BY a.student_id
                       HAVING COUNT(*) > 3
                   ))
        """, (teacher_id, session_name, teacher_id, session_name)).fetchone()
        
        at_risk_count = at_risk_students['count'] if at_risk_students else 0
        
        # Display stats in cards
        st.info(f"**Assigned Courses:** {courses_assigned}")
        st.warning(f"**Pending Grades:** {pending_grade_count}")
        st.success(f"**Attendance Completion:** {attendance_percentage:.1f}%")
        st.error(f"**At-Risk Students:** {at_risk_count}")
        
        # Upcoming deadlines
        st.write("### Upcoming Events")
        
        # Get upcoming exams
        upcoming_exams = conn.execute("""
            SELECT e.exam_date, e.start_time, c.code, c.title
            FROM exam_schedule e
            JOIN courses c ON e.course_id = c.id
            JOIN teaching t ON t.course_id = c.id
            WHERE t.teacher_id = ? AND e.session = ? AND e.exam_date >= date('now')
            ORDER BY e.exam_date
            LIMIT 3
        """, (teacher_id, session_name)).fetchall()
        
        if upcoming_exams:
            for exam in upcoming_exams:
                st.write(f"📅 **{exam['exam_date']}** - Exam for {exam['code']} at {exam['start_time']}")
        else:
            st.write("No upcoming exams scheduled.")
    
    # Show notifications
    st.write("### Notifications")
    
    # Example notifications - this would be connected to a notifications table in a real implementation
    st.info("📬 Admin has uploaded new teaching materials for your courses.")
    st.info("📬 Grade submission for Mid-term will be open from next week.")
    
    # Close the database connection
    conn.close()

def student_dashboard():
    """Display the student dashboard"""
    from pages.student import dashboard as student_dash
    student_dash.show()

if __name__ == "__main__":
    main() 