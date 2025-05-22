import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from components.header import render_page_title
from database.schema import get_db_connection
import random

def create_top_navigation():
    """Create the top navigation bar for student panel"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        st.markdown('<div style="display: flex; align-items: center;"><h2 style="margin: 0;">📚 Intellix</h2></div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown(f'<div style="text-align: center; white-space: nowrap;"><span style="margin: 0; font-size: 1.1rem;">{datetime.now().strftime("%A, %d %B %Y")}</span> <span style="background-color: #7e57c2; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.9rem; margin-left: 10px;">🎓 Student</span></div>', unsafe_allow_html=True)
    
    with col3:
        notification_col, profile_col = st.columns([1, 1])
        
        with notification_col:
            if st.button("📩", help="Notifications"):
                st.session_state.show_notifications = not st.session_state.get('show_notifications', False)
        
        with profile_col:
            profile_options = st.selectbox(
                "👤",
                ["My Profile", "Change Password", "Logout"],
                label_visibility="collapsed"
            )
            
            if profile_options == "Logout":
                st.session_state.authenticated = False
                st.rerun()

def show():
    """Display the enhanced student dashboard"""
    # Initialize session state variables if they don't exist
    if 'show_notifications' not in st.session_state:
        st.session_state.show_notifications = False
    
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
        conn.close()
        return
    
    # Get current active session
    active_session = conn.execute(
        "SELECT name FROM academic_sessions WHERE is_active = 1"
    ).fetchone()
    
    if not active_session:
        st.warning("No active academic session. Please contact an administrator.")
        conn.close()
        return
    
    session_name = active_session['name']
    
    # Get unread messages count
    unread_messages = conn.execute("""
        SELECT COUNT(*) as count
        FROM messages 
        WHERE recipient_id = ? AND recipient_role = 'student' AND is_read = 0
    """, (student_id,)).fetchone()
    
    unread_count = unread_messages['count'] if unread_messages else 0
    
    # Create the top navigation bar
    create_top_navigation()
    
    # Show notifications panel if active
    if st.session_state.show_notifications:
        with st.expander("Notifications", expanded=True):
            notifications = conn.execute("""
                SELECT title, message, created_at, is_read
                FROM notifications
                WHERE user_id = ? AND user_role = 'student'
                ORDER BY created_at DESC
                LIMIT 10
            """, (student_id,)).fetchall()
            
            if notifications:
                for notification in notifications:
                    read_status = "✅" if notification['is_read'] else "🔵"
                    st.markdown(f"**{read_status} {notification['title']}** - {notification['created_at']}")
                    st.markdown(f"{notification['message']}")
                    st.divider()
            else:
                st.info("No notifications yet!")
    
    # Calculate CGPA
    cgpa_data = conn.execute("""
        SELECT AVG(
            CASE
                WHEN (g.mid + g.assignment + g.final) >= 80 THEN 4.0
                WHEN (g.mid + g.assignment + g.final) >= 75 THEN 3.75
                WHEN (g.mid + g.assignment + g.final) >= 70 THEN 3.5
                WHEN (g.mid + g.assignment + g.final) >= 65 THEN 3.25
                WHEN (g.mid + g.assignment + g.final) >= 60 THEN 3.0
                WHEN (g.mid + g.assignment + g.final) >= 55 THEN 2.75
                WHEN (g.mid + g.assignment + g.final) >= 50 THEN 2.5
                WHEN (g.mid + g.assignment + g.final) >= 45 THEN 2.25
                WHEN (g.mid + g.assignment + g.final) >= 40 THEN 2.0
                ELSE 0
            END
        ) as cgpa
        FROM grades g
        WHERE g.student_id = ? AND g.final IS NOT NULL
    """, (student_id,)).fetchone()
    
    cgpa = cgpa_data['cgpa'] if cgpa_data and cgpa_data['cgpa'] else 0
    
    # Get latest semester GPA
    latest_gpa_data = conn.execute("""
        SELECT semester, AVG(
            CASE
                WHEN (g.mid + g.assignment + g.final) >= 80 THEN 4.0
                WHEN (g.mid + g.assignment + g.final) >= 75 THEN 3.75
                WHEN (g.mid + g.assignment + g.final) >= 70 THEN 3.5
                WHEN (g.mid + g.assignment + g.final) >= 65 THEN 3.25
                WHEN (g.mid + g.assignment + g.final) >= 60 THEN 3.0
                WHEN (g.mid + g.assignment + g.final) >= 55 THEN 2.75
                WHEN (g.mid + g.assignment + g.final) >= 50 THEN 2.5
                WHEN (g.mid + g.assignment + g.final) >= 45 THEN 2.25
                WHEN (g.mid + g.assignment + g.final) >= 40 THEN 2.0
                ELSE 0
            END
        ) as semester_gpa
        FROM grades g
        WHERE g.student_id = ? AND g.final IS NOT NULL
        GROUP BY semester
        ORDER BY semester DESC
        LIMIT 1
    """, (student_id,)).fetchone()
    
    latest_gpa = latest_gpa_data['semester_gpa'] if latest_gpa_data and latest_gpa_data['semester_gpa'] else 0
    latest_semester = latest_gpa_data['semester'] if latest_gpa_data else "N/A"
    
    # Get overall attendance rate
    overall_attendance = conn.execute("""
        SELECT COUNT(*) as total, SUM(present) as present
        FROM attendance
        WHERE student_id = ?
    """, (student_id,)).fetchone()
    
    attendance_rate = 0
    if overall_attendance and overall_attendance['total'] > 0:
        attendance_rate = (overall_attendance['present'] / overall_attendance['total']) * 100
    
    # Get risk level based on grades and attendance
    risk_level = "Low"
    risk_color = "green"
    risk_icon = "✅"
    
    if cgpa < 2.0 or attendance_rate < 60:
        risk_level = "High"
        risk_color = "red"
        risk_icon = "⚠️"
    elif cgpa < 3.0 or attendance_rate < 75:
        risk_level = "Medium"
        risk_color = "orange"
        risk_icon = "⚠️"
    
    # Get upcoming deadlines for notices
    recent_notices = conn.execute("""
        SELECT a.title, a.due_date, c.code
        FROM assignments a
        JOIN courses c ON a.course_id = c.id
        JOIN enrollments e ON e.course_id = c.id AND e.student_id = ?
        WHERE a.semester = ? AND a.due_date >= date('now') AND a.due_date <= date('now', '+7 days')
        ORDER BY a.due_date
        LIMIT 3
    """, (student_id, session_name)).fetchall()
    
    # Check if exam_type column exists in exam_schedule table
    check_exam_type = conn.execute("""
        SELECT COUNT(*) as count FROM pragma_table_info('exam_schedule') 
        WHERE name = 'exam_type'
    """).fetchone()
    
    has_exam_type = check_exam_type['count'] > 0 if check_exam_type else False
    
    # Get upcoming exams based on schema
    if has_exam_type:
        upcoming_exams_query = """
            SELECT e.exam_type, e.exam_date, c.code
            FROM exam_schedule e
            JOIN courses c ON e.course_id = c.id
            JOIN enrollments enr ON enr.course_id = c.id AND enr.student_id = ?
            WHERE e.session = ? AND e.exam_date >= date('now') AND e.exam_date <= date('now', '+14 days')
            ORDER BY e.exam_date
            LIMIT 2
        """
    else:
        upcoming_exams_query = """
            SELECT 'Exam' as exam_type, e.exam_date, c.code
            FROM exam_schedule e
            JOIN courses c ON e.course_id = c.id
            JOIN enrollments enr ON enr.course_id = c.id AND enr.student_id = ?
            WHERE e.session = ? AND e.exam_date >= date('now') AND e.exam_date <= date('now', '+14 days')
            ORDER BY e.exam_date
            LIMIT 2
        """
    
    upcoming_exams = conn.execute(upcoming_exams_query, (student_id, session_name)).fetchall()
    
    # Combine notices
    notices = []
    for notice in recent_notices:
        notices.append(f"Assignment '{notice['title']}' for {notice['code']} due on {notice['due_date']}")
    
    for exam in upcoming_exams:
        notices.append(f"{exam['exam_type']} exam for {exam['code']} on {exam['exam_date']}")
    
    if not notices:
        notices = ["No upcoming deadlines or exams in the next 2 weeks."]
    
    # Top Cards Section
    st.markdown("## Dashboard")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        with st.container(border=True):
            st.markdown("<h3 style='white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>📚 GPA Overview</h3>", unsafe_allow_html=True)
            st.markdown(f"**CGPA:** {cgpa:.2f}")
            st.markdown(f"**Latest Semester ({latest_semester}):** {latest_gpa:.2f}")
            
            # Add interactivity
            if st.button("More Details", key="gpa_details"):
                st.session_state.current_page = "student_gpa_prediction"
                st.rerun()
    
    with col2:
        with st.container(border=True):
            st.markdown("<h3 style='white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>📅 Attendance Summary</h3>", unsafe_allow_html=True)
            st.markdown(f"**Overall:** {attendance_rate:.1f}%")
            
            if attendance_rate < 60:
                st.markdown("<span style='color:red'>⚠️ Critical - Immediate improvement needed</span>", unsafe_allow_html=True)
            elif attendance_rate < 75:
                st.markdown("<span style='color:orange'>⚠️ Warning - Needs improvement</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color:green'>✅ Good standing</span>", unsafe_allow_html=True)
            
            # Add interactivity
            if st.button("More Details", key="attendance_details"):
                st.session_state.current_page = "student_attendance"
                st.rerun()
    
    with col3:
        with st.container(border=True):
            st.markdown(f"<h3 style='white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{risk_icon} Risk Status</h3>", unsafe_allow_html=True)
            st.markdown(f"**Level:** <span style='color:{risk_color}'>{risk_level}</span>", unsafe_allow_html=True)
            
            # Risk explanation based on level
            if risk_level == "High":
                st.markdown("<span style='color:red'>Critical attention needed in multiple areas</span>", unsafe_allow_html=True)
            elif risk_level == "Medium":
                st.markdown("<span style='color:orange'>Improvements needed in some areas</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color:green'>Good academic standing</span>", unsafe_allow_html=True)
            
            # Add interactivity
            if st.button("View Suggestions", key="risk_details"):
                st.session_state.current_page = "student_study_plan"
                st.rerun()
    
    with col4:
        with st.container(border=True):
            st.markdown("<h3 style='white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>📣 Notices</h3>", unsafe_allow_html=True)
            for i, notice in enumerate(notices[:2]):
                st.markdown(f"- {notice}")
            
            if len(notices) > 2:
                st.markdown(f"... and {len(notices) - 2} more")
            
            # Add interactivity
            if st.button("View All", key="notices_details"):
                st.session_state.current_page = "student_assignments"
                st.rerun()
    
    st.markdown("---")
    
    # Middle Section - Charts & Dynamic Widgets
    middle_col1, middle_col2 = st.columns([3, 2])
    
    with middle_col1:
        # Fetch semester-wise GPA data
        gpa_history = conn.execute("""
            SELECT semester, AVG(
                CASE
                    WHEN (g.mid + g.assignment + g.final) >= 80 THEN 4.0
                    WHEN (g.mid + g.assignment + g.final) >= 75 THEN 3.75
                    WHEN (g.mid + g.assignment + g.final) >= 70 THEN 3.5
                    WHEN (g.mid + g.assignment + g.final) >= 65 THEN 3.25
                    WHEN (g.mid + g.assignment + g.final) >= 60 THEN 3.0
                    WHEN (g.mid + g.assignment + g.final) >= 55 THEN 2.75
                    WHEN (g.mid + g.assignment + g.final) >= 50 THEN 2.5
                    WHEN (g.mid + g.assignment + g.final) >= 45 THEN 2.25
                    WHEN (g.mid + g.assignment + g.final) >= 40 THEN 2.0
                    ELSE 0
                END
            ) as semester_gpa
            FROM grades g
            WHERE g.student_id = ? AND g.final IS NOT NULL
            GROUP BY semester
            ORDER BY semester
        """, (student_id,)).fetchall()
        
        if gpa_history:
            # Create GPA trend data
            semesters = [gh['semester'] for gh in gpa_history]
            gpas = [gh['semester_gpa'] for gh in gpa_history]
            
            # Add CGPA line
            semesters.append("CGPA")
            gpas.append(cgpa)
            
            # Create line chart
            fig = px.line(
                x=semesters,
                y=gpas,
                labels={"x": "Semester", "y": "GPA"},
                title="GPA Trend Over Semesters",
                markers=True
            )
            
            # Set y-axis range to 0-4.0
            fig.update_layout(yaxis_range=[0, 4.0])
            
            # Add points to the line
            fig.update_traces(mode="lines+markers", marker=dict(size=10))
            
            # Display the chart
            st.plotly_chart(fig, use_container_width=True)
        else:
            # If no GPA history, create a placeholder chart
            st.info("No GPA history available yet. Chart will appear once grades are recorded.")
            
            # Create dummy data for display
            semesters = ["Semester 1", "Semester 2", "Current"]
            gpas = [3.5, 3.7, 3.8]
            
            # Create line chart
            fig = px.line(
                x=semesters,
                y=gpas,
                labels={"x": "Semester", "y": "GPA"},
                title="Sample GPA Trend (Your actual data will appear here)"
            )
            
            # Set y-axis range to 0-4.0
            fig.update_layout(yaxis_range=[0, 4.0])
            fig.update_traces(mode="lines+markers", marker=dict(size=10, opacity=0.3))
            
            # Display the chart
            st.plotly_chart(fig, use_container_width=True)
    
    with middle_col2:
        # AI Study Suggestions Panel
        with st.container(border=True):
            st.markdown("<h3 style='white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>🧠 AI Study Suggestions</h3>", unsafe_allow_html=True)
            
            # Get course performance data
            course_performance = conn.execute("""
                SELECT c.code, c.title, 
                       g.mid, g.assignment, g.final,
                       (SELECT COUNT(*) FROM attendance a 
                        WHERE a.student_id = ? AND a.course_id = c.id) as total_classes,
                       (SELECT COUNT(*) FROM attendance a 
                        WHERE a.student_id = ? AND a.course_id = c.id AND a.present = 1) as attended_classes
                FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                LEFT JOIN grades g ON g.student_id = e.student_id AND g.course_id = e.course_id AND g.semester = e.semester
                WHERE e.student_id = ? AND e.semester = ?
            """, (student_id, student_id, student_id, session_name)).fetchall()
            
            if course_performance:
                # Identify weakest course
                weakest_course = None
                lowest_score = 100
                
                for course in course_performance:
                    midterm = course['mid'] or 0
                    assignment = course['assignment'] or 0
                    attendance_pct = (course['attended_classes'] / course['total_classes'] * 100) if course['total_classes'] > 0 else 0
                    
                    # Calculate a combined score
                    combined_score = midterm + assignment + (attendance_pct * 0.2)
                    
                    if combined_score < lowest_score:
                        lowest_score = combined_score
                        weakest_course = course
                
                if weakest_course:
                    # Generate AI suggestions
                    st.markdown(f"**Focus Area: {weakest_course['code']} - {weakest_course['title']}**")
                    
                    attendance_pct = (weakest_course['attended_classes'] / weakest_course['total_classes'] * 100) if weakest_course['total_classes'] > 0 else 0
                    
                    suggestions = []
                    
                    if attendance_pct < 75:
                        suggestions.append("- Improve your attendance in this course")
                    
                    if weakest_course['mid'] and weakest_course['mid'] < 15:
                        suggestions.append("- Review midterm exam material thoroughly")
                    
                    if weakest_course['assignment'] and weakest_course['assignment'] < 10:
                        suggestions.append("- Focus on assignment quality and completion")
                    
                    # Add generic suggestions
                    suggestions.extend([
                        "- Set aside dedicated study time for this subject",
                        "- Form a study group with classmates",
                        "- Consult with your instructor during office hours"
                    ])
                    
                    for suggestion in suggestions:
                        st.markdown(suggestion)
            else:
                st.info("AI suggestions will appear once course data is available.")
        
        # At-Risk Subjects
        with st.container(border=True):
            st.markdown("<h3 style='white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>🔥 At-Risk Subjects</h3>", unsafe_allow_html=True)
            
            # Get course grades for risk assessment
            at_risk_courses = conn.execute("""
                SELECT c.code, c.title, 
                       g.mid, g.assignment, g.final,
                       (SELECT AVG(a.present) 
                        FROM attendance a 
                        WHERE a.student_id = ? AND a.course_id = c.id) as attendance_rate
                FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                LEFT JOIN grades g ON g.student_id = e.student_id AND g.course_id = e.course_id AND g.semester = e.semester
                WHERE e.student_id = ? AND e.semester = ?
            """, (student_id, student_id, session_name)).fetchall()
            
            if at_risk_courses:
                risk_courses = []
                
                for course in at_risk_courses:
                    midterm = course['mid'] or 0
                    assignment = course['assignment'] or 0
                    attendance = course['attendance_rate'] or 0
                    
                    # Calculate risk level
                    risk_score = (midterm / 30 * 100) + (assignment / 20 * 100) + (attendance * 100)
                    risk_score = risk_score / 3  # Average
                    
                    risk_status = "Low"
                    risk_color = "green"
                    
                    if risk_score < 50:
                        risk_status = "High"
                        risk_color = "red"
                        risk_courses.append((course, risk_status, risk_color))
                    elif risk_score < 70:
                        risk_status = "Medium"
                        risk_color = "orange"
                        risk_courses.append((course, risk_status, risk_color))
                
                if risk_courses:
                    for course, status, color in risk_courses:
                        st.markdown(f"**{course['code']}**: <span style='color:{color}'>{status} Risk</span>", unsafe_allow_html=True)
                        
                        # Show risk factors
                        factors = []
                        if course['mid'] and course['mid'] < 15:
                            factors.append("Low midterm score")
                        if course['assignment'] and course['assignment'] < 10:
                            factors.append("Low assignment score")
                        if course['attendance_rate'] and course['attendance_rate'] < 0.75:
                            factors.append("Poor attendance")
                        
                        if factors:
                            st.markdown(f"Factors: {', '.join(factors)}")
                else:
                    st.success("✅ No courses currently at risk. Keep up the good work!")
            else:
                st.info("Risk assessment will appear once course data is available.")
    
    st.markdown("---")
    
    # Bottom Section - Quick Links / Actions
    st.subheader("Quick Actions")
    
    btn_col1, btn_col2, btn_col3, btn_col4, btn_col5 = st.columns(5)
    
    with btn_col1:
        if st.button("🧾 View Transcript", use_container_width=True):
            st.info("Transcript feature will be available soon.")
    
    with btn_col2:
        if st.button("📈 View Progress Report", use_container_width=True):
            st.session_state.current_page = "student_grades"
            st.rerun()
    
    with btn_col3:
        if st.button("💬 Contact Instructor", use_container_width=True):
            st.session_state.current_page = "student_messages"
            st.rerun()
    
    with btn_col4:
        if st.button("✍️ Instructor Evaluation", use_container_width=True):
            st.info("Instructor evaluation feature will be available soon.")
    
    with btn_col5:
        if st.button("🧠 Generate Study Plan", use_container_width=True):
            st.session_state.current_page = "student_study_plan"
            st.rerun()
    
    # Close the database connection
    conn.close() 