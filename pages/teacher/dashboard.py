import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.figure_factory as ff
from datetime import datetime, timedelta
import json
import random
import io
import base64
import numpy as np
import calendar
from components.header import render_page_title
from database.schema import get_db_connection

# Helper function for CSV download
def get_csv_download_link(df, filename, link_text):
    """Generate a link to download dataframe as CSV"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">{link_text}</a>'
    return href

# GPA calculator function
def calculate_gpa(grades):
    """Calculate GPA based on grades"""
    if not grades or len(grades) == 0:
        return 0.0
    
    grade_points = {
        'A+': 4.0, 'A': 4.0, 'A-': 3.7,
        'B+': 3.3, 'B': 3.0, 'B-': 2.7,
        'C+': 2.3, 'C': 2.0, 'C-': 1.7,
        'D+': 1.3, 'D': 1.0, 'F': 0.0
    }
    
    total_points = 0
    total_credits = 0
    
    for grade in grades:
        letter_grade = grade['letter_grade']
        credit = grade['credit_hour']
        
        if letter_grade in grade_points:
            total_points += grade_points[letter_grade] * credit
            total_credits += credit
    
    if total_credits == 0:
        return 0.0
    
    return round(total_points / total_credits, 2)

def show():
    """Display the enhanced teacher dashboard"""
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
        conn.close()
        return
    
    # Get current active session
    active_session = conn.execute(
        "SELECT name FROM academic_sessions WHERE is_active = 1"
    ).fetchone()
    
    session_name = active_session['name'] if active_session else "No active session"
    
    # Get unread messages count
    unread_messages = conn.execute("""
        SELECT COUNT(*) as count
        FROM messages
        WHERE recipient_id = ? AND recipient_role = 'teacher' AND is_read = 0
    """, (teacher_id,)).fetchone()
    
    unread_count = unread_messages['count'] if unread_messages else 0
    
    # Welcome message
    st.write(f"### Welcome, {teacher['name']}!")
    st.write(f"**Department:** {teacher['dept']} | **Current Session:** {session_name} | **Unread Messages:** {unread_count}")
    
    st.markdown("---")
    
    # Section 1: Quick Stats Cards
    st.subheader("📊 Quick Stats")
    
    # Create a row of metrics cards
    col1, col2, col3, col4 = st.columns(4)
    
    # Card 1: Total Courses Assigned
    course_count = conn.execute("""
        SELECT COUNT(DISTINCT c.id) as count
        FROM courses c
        JOIN teaching t ON c.id = t.course_id
        WHERE t.teacher_id = ? AND t.semester = ?
    """, (teacher_id, session_name)).fetchone()
    
    courses_assigned = course_count['count'] if course_count else 0
    
    with col1:
        st.metric("🧮 Total Courses", courses_assigned)
        if st.button("View Courses", key="view_courses", use_container_width=True):
            st.session_state.current_page = "teacher_courses"
            st.rerun()
    
    # Card 2: Grades Pending Submission
    pending_grades = conn.execute("""
        SELECT COUNT(*) as count
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        JOIN teaching t ON t.course_id = c.id
        LEFT JOIN grades g ON g.student_id = e.student_id AND g.course_id = e.course_id AND g.semester = e.semester
        WHERE t.teacher_id = ? AND e.semester = ? AND (g.final IS NULL OR g.final = 0)
    """, (teacher_id, session_name)).fetchone()
    
    pending_grade_count = pending_grades['count'] if pending_grades else 0
    
    with col2:
        st.metric("📝 Pending Grades", pending_grade_count)
        if st.button("Enter Grades", key="enter_grades", use_container_width=True):
            st.session_state.current_page = "teacher_grades"
            st.rerun()
    
    # Card 3: Attendance Completion
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
        attendance_percentage = min(100, (attendance_stats['attendance_entries'] / (attendance_stats['total_students'] * 5)) * 100)
    
    with col3:
        st.metric("✅ Attendance", f"{attendance_percentage:.1f}%")
        if st.button("Mark Attendance", key="mark_attendance", use_container_width=True):
            st.session_state.current_page = "teacher_attendance"
            st.rerun()
    
    # Card 4: Enhanced At-Risk Students using AI flagging
    # Combines multiple risk factors: grades, attendance, assignment submissions, participation
    at_risk_students = conn.execute("""
        WITH student_stats AS (
            SELECT 
                e.student_id,
                -- Grade risk (midterm + assignments below threshold)
                CASE WHEN (COALESCE(g.mid, 0) + COALESCE(g.assignment, 0)) < 30 THEN 1 ELSE 0 END as grade_risk,
                -- Attendance risk (more than 3 absences)
                CASE WHEN (
                    SELECT COUNT(*) 
                    FROM attendance a 
                    WHERE a.student_id = e.student_id
                    AND a.course_id = e.course_id
                    AND a.present = 0
                ) > 3 THEN 1 ELSE 0 END as attendance_risk,
                -- Overall grade progress
                COALESCE(g.mid, 0) + COALESCE(g.assignment, 0) + COALESCE(g.final, 0) as current_score
            FROM enrollments e
            JOIN teaching t ON t.course_id = e.course_id
            LEFT JOIN grades g ON g.student_id = e.student_id AND g.course_id = e.course_id AND g.semester = e.semester
            WHERE t.teacher_id = ? AND e.semester = ?
        )
        SELECT 
            COUNT(DISTINCT student_id) as count,
            SUM(CASE WHEN grade_risk = 1 AND attendance_risk = 1 THEN 1 ELSE 0 END) as critical_count,
            SUM(CASE WHEN grade_risk = 1 OR attendance_risk = 1 THEN 1 ELSE 0 END) as moderate_count,
            AVG(current_score) as avg_score
        FROM student_stats
        WHERE grade_risk = 1 OR attendance_risk = 1
    """, (teacher_id, session_name)).fetchone()
    
    at_risk_count = at_risk_students['count'] if at_risk_students else 0
    critical_count = at_risk_students['critical_count'] if at_risk_students else 0
    
    # Add color coding based on severity
    risk_color = "normal"
    if critical_count > 0:
        risk_color = "inverse"  # Red
    
    with col4:
        st.metric("⚠️ At-Risk Students", at_risk_count, delta=f"{critical_count} critical", delta_color=risk_color)
        if st.button("View Analysis", key="view_analysis", use_container_width=True):
            st.session_state.current_page = "teacher_analytics"
            st.rerun()
    
    st.markdown("---")
    
    # Section 2: Timeline & Upcoming Table
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📅 Recent Activities")
        
        # Create tabs for different activity types
        activity_tab1, activity_tab2, activity_tab3 = st.tabs(["All Activities", "Grades", "Attendance"])
        
        # Get recent activities combined (grades, attendance, and messages)
        recent_grades = conn.execute("""
            SELECT g.updated_at as timestamp, 
                   c.code, c.title, 
                   'grade' as activity_type,
                   s.name as student_name,
                   g.mid, g.assignment, g.final
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            JOIN teaching t ON t.course_id = c.id
            JOIN students s ON s.id = g.student_id
            WHERE t.teacher_id = ? AND g.semester = ?
            ORDER BY g.updated_at DESC
            LIMIT 20
        """, (teacher_id, session_name)).fetchall()
        
        recent_attendance = conn.execute("""
            SELECT a.date as timestamp, 
                   c.code, c.title,
                   'attendance' as activity_type,
                   COUNT(*) as total_students,
                   SUM(CASE WHEN a.present = 1 THEN 1 ELSE 0 END) as present_count
            FROM attendance a
            JOIN courses c ON a.course_id = c.id
            JOIN teaching t ON t.course_id = c.id
            WHERE t.teacher_id = ? AND t.semester = ?
            GROUP BY a.date, c.code
            ORDER BY a.date DESC
            LIMIT 20
        """, (teacher_id, session_name)).fetchall()
        
        recent_messages = conn.execute("""
            SELECT m.sent_at as timestamp,
                   c.code, c.title,
                   'message' as activity_type,
                   CASE 
                       WHEN m.recipient_role = 'student' THEN (SELECT name FROM students WHERE id = m.recipient_id)
                       WHEN m.recipient_role = 'teacher' THEN (SELECT name FROM teachers WHERE id = m.recipient_id)
                       ELSE 'Administrator'
                   END as recipient_name,
                   m.subject
            FROM messages m
            LEFT JOIN courses c ON m.course_id = c.id
            WHERE m.sender_id = ? AND m.sender_role = 'teacher'
            ORDER BY m.sent_at DESC
            LIMIT 10
        """, (teacher_id,)).fetchall()
        
        # Combine all activities and sort by date
        all_activities = []
        
        for grade in recent_grades:
            all_activities.append({
                "timestamp": grade['timestamp'],
                "code": grade['code'],
                "title": grade['title'],
                "activity_type": grade['activity_type'],
                "details": f"Updated grades for {grade['student_name']}"
            })
        
        for att in recent_attendance:
            attendance_rate = (att['present_count'] / att['total_students'] * 100) if att['total_students'] > 0 else 0
            all_activities.append({
                "timestamp": att['timestamp'],
                "code": att['code'],
                "title": att['title'],
                "activity_type": att['activity_type'],
                "details": f"Marked attendance ({attendance_rate:.1f}% present)"
            })
        
        for msg in recent_messages:
            all_activities.append({
                "timestamp": msg['timestamp'],
                "code": msg['code'] if msg['code'] else "N/A",
                "title": msg['title'] if msg['title'] else "No course",
                "activity_type": msg['activity_type'],
                "details": f"Sent message to {msg['recipient_name']}: {msg['subject']}"
            })
        
        # Sort activities by date
        sorted_activities = sorted(all_activities, key=lambda x: x['timestamp'] if x['timestamp'] else "", reverse=True)
        
        # Filter activities for each tab
        with activity_tab1:  # All Activities
            if sorted_activities:
                # Create a dataframe for better visualization
                activity_data = []
                for activity in sorted_activities[:10]:  # Show top 10
                    icon = "📝" if activity['activity_type'] == 'grade' else "✅" if activity['activity_type'] == 'attendance' else "💬"
                    activity_data.append({
                        "Date": activity['timestamp'],
                        "Course": activity['code'],
                        "Activity": f"{icon} {activity['details']}"
                    })
                
                activity_df = pd.DataFrame(activity_data)
                st.dataframe(
                    activity_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Date": st.column_config.DatetimeColumn(format="MMM DD, YYYY - hh:mm a"),
                        "Course": st.column_config.TextColumn(width="small"),
                        "Activity": st.column_config.TextColumn(width="medium")
                    }
                )
            else:
                st.info("No recent activities found.")
        
        with activity_tab2:  # Grades
            grade_activities = [a for a in sorted_activities if a['activity_type'] == 'grade']
            if grade_activities:
                for activity in grade_activities[:10]:
                    st.markdown(f"📝 **{activity['timestamp']}**: {activity['details']} for **{activity['code']}**")
            else:
                st.info("No recent grade activities found.")
        
        with activity_tab3:  # Attendance
            attendance_activities = [a for a in sorted_activities if a['activity_type'] == 'attendance']
            if attendance_activities:
                for activity in attendance_activities[:10]:
                    st.markdown(f"✅ **{activity['timestamp']}**: {activity['details']} for **{activity['code']}**")
            else:
                st.info("No recent attendance activities found.")
    
    with col2:
        st.subheader("📆 Upcoming Deadlines")
        
        # Get upcoming exams with more details
        upcoming_exams = conn.execute("""
            SELECT e.exam_date, e.start_time, e.end_time, e.exam_type, c.code, c.title, e.room,
                   CASE WHEN e.exam_date < date('now') THEN 'Past'
                        WHEN e.exam_date = date('now') THEN 'Today'
                        ELSE 'Upcoming' END as status
            FROM exam_schedule e
            JOIN courses c ON e.course_id = c.id
            JOIN teaching t ON t.course_id = c.id
            WHERE t.teacher_id = ? AND e.session = ? 
            AND date(e.exam_date) <= date('now', '+21 days')
            ORDER BY e.exam_date
            LIMIT 10
        """, (teacher_id, session_name)).fetchall()
        
        # Get assignment deadlines
        assignment_deadlines = conn.execute("""
            SELECT a.id, a.title, a.due_date, c.code, c.title as course_title,
                   CASE WHEN a.due_date < date('now') THEN 'Past'
                        WHEN a.due_date = date('now') THEN 'Today'
                        ELSE 'Upcoming' END as status,
                   (SELECT COUNT(*) FROM student_assignments sa WHERE sa.assignment_id = a.id) as submission_count,
                   (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = a.course_id AND e.semester = a.semester) as enrolled_count
            FROM assignments a
            JOIN courses c ON a.course_id = c.id
            JOIN teaching t ON t.course_id = c.id
            WHERE t.teacher_id = ? AND a.semester = ?
            AND date(a.due_date) <= date('now', '+21 days')
            ORDER BY a.due_date
            LIMIT 10
        """, (teacher_id, session_name)).fetchall()
        
        # Add grade submission deadlines (simulated)
        # In a real system, these would come from a deadlines table
        upcoming_deadlines = []
        
        if active_session:
            today = datetime.now()
            
            # For demonstration, create deadlines relative to today
            midterm_deadline = today + timedelta(days=5)
            final_deadline = today + timedelta(days=12)
            
            upcoming_deadlines.append({
                "date": midterm_deadline.strftime("%Y-%m-%d"),
                "task": "Midterm Grade Submission",
                "course": "All Courses",
                "status": "Upcoming",
                "type": "grade_deadline"
            })
            
            upcoming_deadlines.append({
                "date": final_deadline.strftime("%Y-%m-%d"),
                "task": "Final Grade Submission",
                "course": "All Courses",
                "status": "Upcoming",
                "type": "grade_deadline"
            })
        
        # Add exam schedules to deadlines
        for exam in upcoming_exams:
            upcoming_deadlines.append({
                "date": exam['exam_date'],
                "task": f"{exam['exam_type']} Exam ({exam['start_time']} - {exam['end_time']})",
                "course": exam['code'],
                "status": exam['status'],
                "location": exam['room'],
                "type": "exam"
            })
        
        # Add assignment deadlines
        for assignment in assignment_deadlines:
            submission_ratio = f"{assignment['submission_count']}/{assignment['enrolled_count']}"
            upcoming_deadlines.append({
                "date": assignment['due_date'],
                "task": f"Assignment: {assignment['title']}",
                "course": assignment['code'],
                "status": assignment['status'],
                "submission": submission_ratio,
                "type": "assignment"
            })
        
        # Sort by date
        upcoming_deadlines = sorted(upcoming_deadlines, key=lambda x: x['date'])
        
        if upcoming_deadlines:
            # Create a dataframe for better display
            deadline_data = []
            for deadline in upcoming_deadlines:
                if deadline['type'] == 'exam':
                    deadline_data.append({
                        "Date": deadline['date'],
                        "Task": deadline['task'],
                        "Course": deadline['course'],
                        "Location": deadline.get('location', 'N/A'),
                        "Status": deadline['status']
                    })
                elif deadline['type'] == 'assignment':
                    deadline_data.append({
                        "Date": deadline['date'],
                        "Task": deadline['task'],
                        "Course": deadline['course'],
                        "Submissions": deadline.get('submission', 'N/A'),
                        "Status": deadline['status']
                    })
                else:  # grade_deadline
                    deadline_data.append({
                        "Date": deadline['date'],
                        "Task": deadline['task'],
                        "Course": deadline['course'],
                        "Status": deadline['status']
                    })
            
            # Create the dataframe
            df_deadlines = pd.DataFrame(deadline_data)
            
            # Color the Status column
            def color_status(val):
                if val == 'Past':
                    return 'color: gray'
                elif val == 'Today':
                    return 'color: red; font-weight: bold'
                else:
                    return 'color: green'
            
            # Display the styled dataframe
            st.dataframe(
                df_deadlines.style.applymap(color_status, subset=['Status']),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Date": st.column_config.DateColumn(format="MMM DD, YYYY"),
                    "Task": st.column_config.TextColumn(width="large"),
                    "Course": st.column_config.TextColumn(width="small"),
                    "Location": st.column_config.TextColumn(width="small"),
                    "Submissions": st.column_config.TextColumn(width="small"),
                    "Status": st.column_config.TextColumn(width="small")
                }
            )
            
            # Add calendar download button
            if st.button("📅 Export to Calendar", use_container_width=True):
                st.success("Calendar export feature will be implemented soon!")
        else:
            st.info("No upcoming deadlines or exams found.")
        
        # Notifications section
        with st.expander("🔔 Notifications", expanded=True):
            # Get unread messages
            unread_notifications = conn.execute("""
                SELECT m.id, m.subject, m.sent_at, 
                       CASE 
                           WHEN m.sender_role = 'admin' THEN 'Administrator'
                           WHEN m.sender_role = 'teacher' AND t.id IS NOT NULL THEN t.name
                           WHEN m.sender_role = 'student' AND s.id IS NOT NULL THEN s.name
                           ELSE 'Unknown'
                       END as sender_name
                FROM messages m
                LEFT JOIN teachers t ON m.sender_id = t.id AND m.sender_role = 'teacher'
                LEFT JOIN students s ON m.sender_id = s.id AND m.sender_role = 'student'
                WHERE m.recipient_id = ? AND m.recipient_role = 'teacher' AND m.is_read = 0
                ORDER BY m.sent_at DESC
                LIMIT 5
            """, (teacher_id,)).fetchall()
            
            if unread_notifications:
                for notification in unread_notifications:
                    st.info(f"📬 **{notification['sender_name']}** sent you a message: {notification['subject']} ({notification['sent_at']})")
                
                if st.button("📨 View All Messages", use_container_width=True):
                    st.session_state.current_page = "teacher_messages"
                    st.rerun()
            else:
                st.info("No new notifications.")
    
    st.markdown("---")
    
    # Section 3: AI Insights & Section 4: Charts Section
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("🤖 AI Insights")
        
        # Create tabs for different insight types
        insight_tab1, insight_tab2, insight_tab3 = st.tabs(["At-Risk Students", "Performance Trends", "Smart Recommendations"])
        
        # Tab 1: At-Risk Students with comprehensive analysis
        with insight_tab1:
            # Get at-risk students with detailed analysis
            at_risk_details = conn.execute("""
                WITH student_performance AS (
                    SELECT 
                        s.id, s.student_id as roll_no, s.name, c.id as course_id, c.code, c.title,
                        COALESCE(g.mid, 0) as midterm,
                        COALESCE(g.assignment, 0) as assignment,
                        COALESCE(g.final, 0) as final,
                        (COALESCE(g.mid, 0) + COALESCE(g.assignment, 0) + COALESCE(g.final, 0)) as total_score,
                        (SELECT COUNT(*) FROM attendance a 
                         WHERE a.student_id = s.id AND a.course_id = c.id AND a.present = 0) as absences,
                        (SELECT COUNT(*) FROM attendance a 
                         WHERE a.student_id = s.id AND a.course_id = c.id) as total_classes,
                        CASE 
                            WHEN (COALESCE(g.mid, 0) + COALESCE(g.assignment, 0)) < 15 THEN 'Critical'
                            WHEN (COALESCE(g.mid, 0) + COALESCE(g.assignment, 0)) < 25 THEN 'High'
                            WHEN (COALESCE(g.mid, 0) + COALESCE(g.assignment, 0)) < 30 THEN 'Moderate'
                            ELSE 'Good'
                        END as risk_level,
                        CASE 
                            WHEN (SELECT COUNT(*) FROM attendance a 
                                 WHERE a.student_id = s.id AND a.course_id = c.id AND a.present = 0) > 5 THEN 'Critical'
                            WHEN (SELECT COUNT(*) FROM attendance a 
                                 WHERE a.student_id = s.id AND a.course_id = c.id AND a.present = 0) > 3 THEN 'High'
                            ELSE 'Good'
                        END as attendance_status
                    FROM students s
                    JOIN enrollments e ON s.id = e.student_id
                    JOIN courses c ON e.course_id = c.id
                    JOIN teaching t ON t.course_id = c.id
                    LEFT JOIN grades g ON g.student_id = s.id AND g.course_id = c.id AND g.semester = e.semester
                    WHERE t.teacher_id = ? AND e.semester = ?
                )
                SELECT * FROM student_performance
                WHERE risk_level IN ('Critical', 'High', 'Moderate') OR attendance_status IN ('Critical', 'High')
                ORDER BY 
                    CASE risk_level 
                        WHEN 'Critical' THEN 1 
                        WHEN 'High' THEN 2 
                        WHEN 'Moderate' THEN 3 
                        ELSE 4 
                    END,
                    CASE attendance_status
                        WHEN 'Critical' THEN 1
                        WHEN 'High' THEN 2
                        ELSE 3
                    END
                LIMIT 20
            """, (teacher_id, session_name)).fetchall()
            
            if at_risk_details:
                # Create DataFrame for better visualization
                at_risk_data = []
                for student in at_risk_details:
                    current_score = student['midterm'] + student['assignment']
                    attendance_rate = ((student['total_classes'] - student['absences']) / student['total_classes'] * 100) if student['total_classes'] > 0 else 0
                    
                    at_risk_data.append({
                        "Student": f"{student['name']} ({student['roll_no']})",
                        "Course": student['code'],
                        "Current Score": current_score,
                        "Attendance": f"{attendance_rate:.1f}%",
                        "Risk Level": student['risk_level'],
                        "Att. Status": student['attendance_status']
                    })
                
                df_at_risk = pd.DataFrame(at_risk_data)
                
                # Color the risk columns
                def color_risk(val):
                    if val == 'Critical':
                        return 'background-color: #ffcccc; color: darkred; font-weight: bold'
                    elif val == 'High':
                        return 'background-color: #fff2cc; color: #7f6000; font-weight: bold'
                    elif val == 'Moderate':
                        return 'background-color: #e6f2ff; color: #004d99'
                    else:
                        return ''
                
                # Display styled dataframe
                st.dataframe(
                    df_at_risk.style.applymap(color_risk, subset=['Risk Level', 'Att. Status']),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Student": st.column_config.TextColumn(width="large"),
                        "Course": st.column_config.TextColumn(width="small"),
                        "Current Score": st.column_config.NumberColumn(format="%.1f", width="small"),
                        "Attendance": st.column_config.TextColumn(width="small"),
                        "Risk Level": st.column_config.TextColumn(width="small"),
                        "Att. Status": st.column_config.TextColumn(width="small")
                    }
                )
                
                # CSV Export
                df_csv = df_at_risk.copy()
                csv = df_csv.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Download At-Risk Student Report",
                    csv,
                    "at_risk_students.csv",
                    "text/csv",
                    key='download-risk-csv',
                    use_container_width=True
                )
                
                # Individual student recommendations
                st.markdown("### AI Recommended Interventions")
                
                # Select a student for detailed review
                selected_student_name = st.selectbox(
                    "Select a student for intervention suggestions:",
                    options=df_at_risk["Student"].tolist()
                )
                
                selected_risk_student = df_at_risk[df_at_risk["Student"] == selected_student_name].iloc[0]
                
                st.markdown(f"#### Intervention for {selected_risk_student['Student']}")
                st.markdown(f"**Course:** {selected_risk_student['Course']}")
                st.markdown(f"**Current Score:** {selected_risk_student['Current Score']}/50")
                st.markdown(f"**Attendance:** {selected_risk_student['Attendance']}")
                
                intervention_col1, intervention_col2 = st.columns(2)
                
                with intervention_col1:
                    if selected_risk_student['Risk Level'] == 'Critical':
                        st.error("**Critical Academic Risk**")
                        st.markdown("Recommended actions:")
                        st.markdown("- Schedule an immediate one-on-one meeting")
                        st.markdown("- Provide supplementary assignments to improve scores")
                        st.markdown("- Consider recommending remedial sessions")
                    elif selected_risk_student['Risk Level'] == 'High':
                        st.warning("**High Academic Risk**")
                        st.markdown("Recommended actions:")
                        st.markdown("- Schedule a progress review meeting")
                        st.markdown("- Provide focused study materials")
                        st.markdown("- Email regular progress check-ins")
                
                with intervention_col2:
                    if selected_risk_student['Att. Status'] == 'Critical':
                        st.error("**Critical Attendance Risk**")
                        st.markdown("Recommended actions:")
                        st.markdown("- Issue formal attendance warning")
                        st.markdown("- Request explanation for absences")
                        st.markdown("- Check for pattern in missed classes")
                    elif selected_risk_student['Att. Status'] == 'High':
                        st.warning("**High Attendance Risk**")
                        st.markdown("Recommended actions:")
                        st.markdown("- Send attendance reminder")
                        st.markdown("- Provide missed lecture notes")
                        st.markdown("- Monitor closely in coming weeks")
                
                # Action buttons
                contact_col1, contact_col2 = st.columns(2)
                with contact_col1:
                    if st.button("📧 Send Alert Email", use_container_width=True):
                        st.session_state.student_to_contact = {
                            "name": selected_student_name,
                            "type": "email",
                            "subject": f"Academic Alert: {selected_risk_student['Course']}"
                        }
                        st.success(f"Email draft prepared for {selected_student_name}")
                
                with contact_col2:
                    if st.button("💬 Send Message", use_container_width=True):
                        st.session_state.current_page = "teacher_messages"
                        st.rerun()
            else:
                st.info("No at-risk students identified. All students are performing well!")
        
        # Tab 2: Performance Trends
        with insight_tab2:
            # Get overall performance metrics
            performance_metrics = conn.execute("""
                WITH course_metrics AS (
                    SELECT 
                        c.id as course_id, c.code, c.title,
                        COUNT(DISTINCT e.student_id) as enrolled_students,
                        AVG(g.mid) as avg_midterm,
                        AVG(g.assignment) as avg_assignment,
                        AVG(g.final) as avg_final,
                        AVG(g.mid + g.assignment + g.final) as avg_total,
                        (SELECT COUNT(*) FROM grades 
                         WHERE course_id = c.id AND semester = ? AND (mid + assignment + final) >= 80) as a_grade_count,
                        (SELECT COUNT(*) FROM grades 
                         WHERE course_id = c.id AND semester = ? AND (mid + assignment + final) >= 70 AND (mid + assignment + final) < 80) as b_grade_count,
                        (SELECT COUNT(*) FROM grades 
                         WHERE course_id = c.id AND semester = ? AND (mid + assignment + final) >= 60 AND (mid + assignment + final) < 70) as c_grade_count,
                        (SELECT COUNT(*) FROM grades 
                         WHERE course_id = c.id AND semester = ? AND (mid + assignment + final) >= 50 AND (mid + assignment + final) < 60) as d_grade_count,
                        (SELECT COUNT(*) FROM grades 
                         WHERE course_id = c.id AND semester = ? AND (mid + assignment + final) < 50) as f_grade_count
                    FROM courses c
                    JOIN teaching t ON c.id = t.course_id
                    JOIN enrollments e ON c.id = e.course_id
                    LEFT JOIN grades g ON g.student_id = e.student_id AND g.course_id = c.id AND g.semester = e.semester
                    WHERE t.teacher_id = ? AND e.semester = ?
                    GROUP BY c.id, c.code, c.title
                )
                SELECT * FROM course_metrics
            """, (session_name, session_name, session_name, session_name, session_name, teacher_id, session_name)).fetchall()
            
            if performance_metrics:
                # Create selectbox for course selection
                course_options = {f"{m['code']} - {m['title']}": i for i, m in enumerate(performance_metrics)}
                
                selected_course_name = st.selectbox(
                    "Select a course to view performance metrics:",
                    options=list(course_options.keys()),
                    key="perf_course_select"
                )
                
                selected_idx = course_options[selected_course_name]
                selected_metrics = performance_metrics[selected_idx]
                
                # Display key metrics
                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                
                with metric_col1:
                    st.metric("Students", selected_metrics['enrolled_students'])
                
                with metric_col2:
                    st.metric("Avg. Midterm", f"{selected_metrics['avg_midterm']:.1f}/30")
                
                with metric_col3:
                    st.metric("Avg. Assignment", f"{selected_metrics['avg_assignment']:.1f}/20")
                
                with metric_col4:
                    st.metric("Avg. Total", f"{selected_metrics['avg_total']:.1f}/100")
                
                # Create grade distribution chart
                grades = ['A/A+', 'B/B+', 'C/C+', 'D/D+', 'F']
                values = [
                    selected_metrics['a_grade_count'] or 0,
                    selected_metrics['b_grade_count'] or 0,
                    selected_metrics['c_grade_count'] or 0,
                    selected_metrics['d_grade_count'] or 0,
                    selected_metrics['f_grade_count'] or 0
                ]
                
                # Create grade distribution chart
                fig = px.bar(
                    x=grades, 
                    y=values,
                    labels={'x': 'Grade', 'y': 'Number of Students'},
                    title=f"Grade Distribution for {selected_course_name.split(' - ')[0]}",
                    color=grades,
                    color_discrete_map={
                        'A/A+': 'darkgreen',
                        'B/B+': 'green',
                        'C/C+': 'yellow',
                        'D/D+': 'orange',
                        'F': 'red'
                    }
                )
                
                # Display the chart
                st.plotly_chart(fig, use_container_width=True)
                
                # Show performance insights
                st.markdown("### 📊 Performance Insights")
                
                total_students = selected_metrics['enrolled_students']
                passing_students = (
                    selected_metrics['a_grade_count'] + 
                    selected_metrics['b_grade_count'] + 
                    selected_metrics['c_grade_count'] + 
                    selected_metrics['d_grade_count']
                )
                
                passing_rate = (passing_students / total_students * 100) if total_students > 0 else 0
                
                st.write(f"**Pass Rate:** {passing_rate:.1f}% ({passing_students} of {total_students} students)")
                
                # Generate insights
                insights = []
                
                # Grade distribution insight
                if selected_metrics['a_grade_count'] > total_students * 0.4:
                    insights.append("Class performance is excellent with a high percentage of A grades.")
                elif selected_metrics['f_grade_count'] > total_students * 0.2:
                    insights.append("Class has a concerning number of failing grades.")
                
                # Midterm vs Assignment insight
                if selected_metrics['avg_midterm'] < 15 and selected_metrics['avg_assignment'] > 15:
                    insights.append("Students performed better on assignments than midterms, suggesting exam preparation challenges.")
                elif selected_metrics['avg_midterm'] > 20 and selected_metrics['avg_assignment'] < 10:
                    insights.append("Students performed better on midterms than assignments, suggesting potential homework support needs.")
                
                # Display insights
                for insight in insights:
                    st.info(f"🔍 {insight}")
                
                # Add export button
                course_data = {
                    "Course": selected_course_name.split(" - ")[0],
                    "Total Students": total_students,
                    "Average Midterm": selected_metrics['avg_midterm'],
                    "Average Assignment": selected_metrics['avg_assignment'],
                    "Average Final": selected_metrics['avg_final'],
                    "Average Total": selected_metrics['avg_total'],
                    "A Grades": selected_metrics['a_grade_count'],
                    "B Grades": selected_metrics['b_grade_count'],
                    "C Grades": selected_metrics['c_grade_count'],
                    "D Grades": selected_metrics['d_grade_count'],
                    "F Grades": selected_metrics['f_grade_count'],
                    "Passing Rate": f"{passing_rate:.1f}%"
                }
                
                course_df = pd.DataFrame([course_data])
                csv = course_df.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    "📥 Download Course Performance Report",
                    csv,
                    f"{selected_course_name.split(' - ')[0]}_performance.csv",
                    "text/csv",
                    key='download-performance-csv',
                    use_container_width=True
                )
            else:
                st.info("No performance data available for your courses.")
        
        # Tab 3: Smart Recommendations
        with insight_tab3:
            st.markdown("### 💡 Smart Teaching Recommendations")
            
            # Get overall course recommendations
            all_courses = conn.execute("""
                SELECT c.id, c.code, c.title,
                       COUNT(DISTINCT e.student_id) as enrolled_count,
                       AVG(COALESCE(g.mid, 0) + COALESCE(g.assignment, 0) + COALESCE(g.final, 0)) as avg_score,
                       (SELECT COUNT(*) FROM attendance a
                        JOIN teaching t2 ON t2.course_id = a.course_id
                        WHERE t2.teacher_id = ? AND a.course_id = c.id AND a.present = 0) as total_absences
                FROM courses c
                JOIN teaching t ON c.id = t.course_id
                JOIN enrollments e ON c.id = e.course_id
                LEFT JOIN grades g ON g.student_id = e.student_id AND g.course_id = c.id AND g.semester = e.semester
                WHERE t.teacher_id = ? AND e.semester = ?
                GROUP BY c.id, c.code, c.title
            """, (teacher_id, teacher_id, session_name)).fetchall()
            
            if all_courses:
                # Group recommendations by category
                teaching_recs = [
                    {
                        "category": "Exam Preparation",
                        "recommendations": [
                            "Provide practice quizzes and sample questions before exams",
                            "Schedule review sessions for upcoming exams",
                            "Create study guides highlighting key concepts"
                        ]
                    },
                    {
                        "category": "Student Engagement",
                        "recommendations": [
                            "Implement interactive class activities and discussions",
                            "Incorporate real-world applications into lessons",
                            "Use polls and quick feedback mechanisms during lectures"
                        ]
                    },
                    {
                        "category": "Course Materials",
                        "recommendations": [
                            "Break complex topics into smaller, digestible modules",
                            "Provide supplementary resources for challenging concepts",
                            "Create short video explanations for difficult topics"
                        ]
                    }
                ]
                
                # Course-specific recommendations
                for course in all_courses:
                    avg_score = course['avg_score'] or 0
                    enrolled_count = course['enrolled_count'] or 0
                    absences = course['total_absences'] or 0
                    
                    # Generate targeted recommendations based on metrics
                    course_recs = {
                        "course": f"{course['code']} - {course['title']}",
                        "recommendations": []
                    }
                    
                    if avg_score < 60 and enrolled_count > 0:
                        course_recs["recommendations"].append(f"Consider providing additional support materials for {course['code']} as the class average is below 60%")
                    
                    if absences > enrolled_count * 3:
                        course_recs["recommendations"].append(f"Address attendance issues in {course['code']} - consider making lectures more interactive or reviewing scheduling")
                    
                    if course_recs["recommendations"]:
                        teaching_recs.append(course_recs)
                
                # Display recommendations by category
                for rec_group in teaching_recs:
                    if "category" in rec_group:
                        # General category recommendations
                        with st.expander(f"🔍 {rec_group['category']}", expanded=True):
                            for rec in rec_group['recommendations']:
                                st.markdown(f"• {rec}")
                    else:
                        # Course-specific recommendations
                        with st.expander(f"📘 {rec_group['course']}", expanded=False):
                            for rec in rec_group['recommendations']:
                                st.markdown(f"• {rec}")
                
                # Add a text area for teachers to save their own teaching notes
                st.markdown("### 📝 Teaching Notes")
                
                if "teaching_notes" not in st.session_state:
                    st.session_state.teaching_notes = ""
                
                notes = st.text_area(
                    "Enter your teaching notes and ideas here:",
                    value=st.session_state.teaching_notes,
                    height=150
                )
                
                if notes != st.session_state.teaching_notes:
                    st.session_state.teaching_notes = notes
                    st.success("Notes saved!")
            else:
                st.info("No course data available for recommendations.")
    
    with col2:
        st.subheader("📈 Performance Overview")
        
        # Get all courses for the teacher
        teacher_courses = conn.execute("""
            SELECT c.id, c.code, c.title
            FROM courses c
            JOIN teaching t ON c.id = t.course_id
            WHERE t.teacher_id = ? AND t.semester = ?
            ORDER BY c.code
        """, (teacher_id, session_name)).fetchall()
        
        if teacher_courses:
            # Create selectbox for course selection
            course_options = {f"{c['code']} - {c['title']}": c['id'] for c in teacher_courses}
            selected_course_name = st.selectbox(
                "Select a course to view performance:",
                options=list(course_options.keys()),
                key="performance_course_select"
            )
            
            selected_course_id = course_options[selected_course_name]
            
            # Create tabs for different visualizations
            viz_tab1, viz_tab2, viz_tab3 = st.tabs(["Grade Distribution", "Attendance Trends", "Student Performance"])
            
            # Tab 1: Grade Distribution
            with viz_tab1:
                # Get grade distribution for the selected course
                grades_data = conn.execute("""
                    SELECT 
                        COUNT(CASE WHEN (g.mid + g.assignment + g.final) >= 90 THEN 1 END) as A_plus,
                        COUNT(CASE WHEN (g.mid + g.assignment + g.final) >= 80 AND (g.mid + g.assignment + g.final) < 90 THEN 1 END) as A,
                        COUNT(CASE WHEN (g.mid + g.assignment + g.final) >= 70 AND (g.mid + g.assignment + g.final) < 80 THEN 1 END) as B,
                        COUNT(CASE WHEN (g.mid + g.assignment + g.final) >= 60 AND (g.mid + g.assignment + g.final) < 70 THEN 1 END) as C,
                        COUNT(CASE WHEN (g.mid + g.assignment + g.final) >= 50 AND (g.mid + g.assignment + g.final) < 60 THEN 1 END) as D,
                        COUNT(CASE WHEN (g.mid + g.assignment + g.final) < 50 THEN 1 END) as F,
                        COUNT(CASE WHEN g.mid IS NULL OR g.final IS NULL THEN 1 END) as not_graded
                    FROM grades g
                    JOIN enrollments e ON g.student_id = e.student_id AND g.course_id = e.course_id AND g.semester = e.semester
                    WHERE g.course_id = ? AND g.semester = ?
                """, (selected_course_id, session_name)).fetchone()
                
                if grades_data:
                    # Create data for the grade distribution chart
                    grades = ['A+', 'A', 'B', 'C', 'D', 'F', 'Not Graded']
                    values = [
                        grades_data['A_plus'] or 0,
                        grades_data['A'] or 0,
                        grades_data['B'] or 0,
                        grades_data['C'] or 0,
                        grades_data['D'] or 0,
                        grades_data['F'] or 0,
                        grades_data['not_graded'] or 0
                    ]
                    
                    # Create a pie chart for better visualization
                    fig_pie = px.pie(
                        values=values,
                        names=grades,
                        title=f"Grade Distribution for {selected_course_name.split(' - ')[0]}",
                        color=grades,
                        color_discrete_map={
                            'A+': 'darkgreen',
                            'A': 'green',
                            'B': 'lightgreen',
                            'C': 'yellow',
                            'D': 'orange',
                            'F': 'red',
                            'Not Graded': 'gray'
                        },
                        hole=0.4
                    )
                    
                    # Display the pie chart
                    st.plotly_chart(fig_pie, use_container_width=True)
                    
                    # Add a bar chart showing component scores
                    component_data = conn.execute("""
                        SELECT 
                            AVG(g.mid) as avg_midterm,
                            AVG(g.assignment) as avg_assignment,
                            AVG(g.final) as avg_final
                        FROM grades g
                        WHERE g.course_id = ? AND g.semester = ?
                    """, (selected_course_id, session_name)).fetchone()
                    
                    if component_data:
                        components = ['Midterm', 'Assignment', 'Final']
                        component_values = [
                            component_data['avg_midterm'] or 0,
                            component_data['avg_assignment'] or 0,
                            component_data['avg_final'] or 0
                        ]
                        
                        # Create bar chart
                        fig_components = px.bar(
                            x=components,
                            y=component_values,
                            labels={'x': 'Component', 'y': 'Average Score'},
                            title=f"Average Component Scores for {selected_course_name.split(' - ')[0]}",
                            color=components,
                            text=component_values
                        )
                        
                        # Update layout to show score values
                        fig_components.update_traces(texttemplate='%{y:.1f}', textposition='outside')
                        
                        # Display the chart
                        st.plotly_chart(fig_components, use_container_width=True)
                else:
                    st.info("No grade data available for this course.")
            
            # Tab 2: Attendance Trends
            with viz_tab2:
                # Get attendance data for the selected course
                attendance_data = conn.execute("""
                    SELECT a.date, 
                           SUM(CASE WHEN a.present = 1 THEN 1 ELSE 0 END) as present,
                           COUNT(*) as total
                    FROM attendance a
                    WHERE a.course_id = ?
                    GROUP BY a.date
                    ORDER BY a.date
                """, (selected_course_id,)).fetchall()
                
                if attendance_data:
                    # Create data for the attendance chart
                    att_dates = []
                    att_rates = []
                    present_counts = []
                    absent_counts = []
                    
                    for att in attendance_data:
                        att_dates.append(att['date'])
                        att_rates.append((att['present'] / att['total']) * 100 if att['total'] > 0 else 0)
                        present_counts.append(att['present'])
                        absent_counts.append(att['total'] - att['present'])
                    
                    # Create attendance trend line chart
                    fig_att_trend = px.line(
                        x=att_dates, 
                        y=att_rates,
                        labels={'x': 'Date', 'y': 'Attendance Rate (%)'},
                        title=f"Attendance Trend for {selected_course_name.split(' - ')[0]}",
                        markers=True
                    )
                    
                    # Update layout
                    fig_att_trend.update_layout(yaxis_range=[0, 100])
                    
                    # Display the chart
                    st.plotly_chart(fig_att_trend, use_container_width=True)
                    
                    # Create stacked bar chart showing present/absent counts
                    attendance_df = pd.DataFrame({
                        'Date': att_dates,
                        'Present': present_counts,
                        'Absent': absent_counts
                    })
                    
                    # Melt the dataframe for easier plotting
                    attendance_melted = pd.melt(
                        attendance_df,
                        id_vars=['Date'],
                        value_vars=['Present', 'Absent'],
                        var_name='Status',
                        value_name='Count'
                    )
                    
                    # Create stacked bar chart
                    fig_att_stack = px.bar(
                        attendance_melted,
                        x='Date',
                        y='Count',
                        color='Status',
                        title=f"Attendance Breakdown for {selected_course_name.split(' - ')[0]}",
                        color_discrete_map={
                            'Present': 'green',
                            'Absent': 'red'
                        }
                    )
                    
                    # Display the chart
                    st.plotly_chart(fig_att_stack, use_container_width=True)
                    
                    # Create a heatmap of student attendance
                    student_attendance = conn.execute("""
                        SELECT s.name, a.date, a.present
                        FROM attendance a
                        JOIN students s ON a.student_id = s.id
                        WHERE a.course_id = ?
                        ORDER BY s.name, a.date
                    """, (selected_course_id,)).fetchall()
                    
                    if student_attendance:
                        # Create a pivot table for the heatmap
                        att_records = []
                        for record in student_attendance:
                            att_records.append({
                                'Student': record['name'],
                                'Date': record['date'],
                                'Present': 1 if record['present'] else 0
                            })
                        
                        att_df = pd.DataFrame(att_records)
                        
                        # Get unique dates and students for cleaner pivoting
                        unique_dates = sorted(att_df['Date'].unique())
                        unique_students = sorted(att_df['Student'].unique())
                        
                        # Create pivot table only if we have enough data
                        if len(unique_dates) > 1 and len(unique_students) > 1:
                            pivot_df = att_df.pivot_table(
                                index='Student',
                                columns='Date',
                                values='Present',
                                fill_value=0
                            )
                            
                            # Create heatmap
                            fig_heatmap = px.imshow(
                                pivot_df,
                                labels=dict(x="Date", y="Student", color="Present"),
                                x=pivot_df.columns,
                                y=pivot_df.index,
                                color_continuous_scale=['red', 'green'],
                                title=f"Attendance Heatmap for {selected_course_name.split(' - ')[0]}"
                            )
                            
                            # Update layout
                            fig_heatmap.update_layout(height=400)
                            
                            # Display the heatmap
                            st.plotly_chart(fig_heatmap, use_container_width=True)
                else:
                    st.info("No attendance data available for this course.")
            
            # Tab 3: Student Performance
            with viz_tab3:
                # Get student performance details
                student_performance = conn.execute("""
                    SELECT s.id, s.name, s.student_id as roll_no, 
                           g.mid, g.assignment, g.final,
                           (g.mid + g.assignment + g.final) as total,
                           (SELECT COUNT(*) FROM attendance a 
                            WHERE a.student_id = s.id AND a.course_id = ? AND a.present = 1) as present_count,
                           (SELECT COUNT(*) FROM attendance a 
                            WHERE a.student_id = s.id AND a.course_id = ?) as total_classes
                    FROM students s
                    JOIN enrollments e ON s.id = e.student_id
                    LEFT JOIN grades g ON g.student_id = s.id AND g.course_id = e.course_id AND g.semester = e.semester
                    WHERE e.course_id = ? AND e.semester = ?
                    ORDER BY s.name
                """, (selected_course_id, selected_course_id, selected_course_id, session_name)).fetchall()
                
                if student_performance:
                    # Create DataFrame for better display
                    performance_data = []
                    for student in student_performance:
                        midterm = student['mid'] or 0
                        assignment = student['assignment'] or 0
                        final = student['final'] or 0
                        total = student['total'] or 0
                        
                        attendance_rate = 0
                        if student['total_classes']:
                            attendance_rate = (student['present_count'] / student['total_classes']) * 100
                        
                        # Calculate letter grade
                        letter_grade = 'N/A'
                        if student['total'] is not None:
                            if total >= 90:
                                letter_grade = 'A+'
                            elif total >= 80:
                                letter_grade = 'A'
                            elif total >= 70:
                                letter_grade = 'B'
                            elif total >= 60:
                                letter_grade = 'C'
                            elif total >= 50:
                                letter_grade = 'D'
                            else:
                                letter_grade = 'F'
                        
                        performance_data.append({
                            'Student': f"{student['name']} ({student['roll_no']})",
                            'Midterm': midterm,
                            'Assignment': assignment,
                            'Final': final,
                            'Total': total,
                            'Grade': letter_grade,
                            'Attendance': f"{attendance_rate:.1f}%"
                        })
                    
                    # Create DataFrame
                    perf_df = pd.DataFrame(performance_data)
                    
                    # Apply conditional formatting for grades
                    def color_grade(val):
                        if val == 'A+' or val == 'A':
                            return 'background-color: #d4f7d4; color: darkgreen'
                        elif val == 'B':
                            return 'background-color: #e6f7d4; color: green'
                        elif val == 'C':
                            return 'background-color: #fff7d4; color: darkorange'
                        elif val == 'D':
                            return 'background-color: #ffebd4; color: #cc5500'
                        elif val == 'F':
                            return 'background-color: #ffd4d4; color: darkred'
                        else:
                            return ''
                    
                    # Display styled dataframe
                    st.dataframe(
                        perf_df.style.applymap(color_grade, subset=['Grade']),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            'Student': st.column_config.TextColumn(width='large'),
                            'Midterm': st.column_config.NumberColumn(format="%.1f", width='small'),
                            'Assignment': st.column_config.NumberColumn(format="%.1f", width='small'),
                            'Final': st.column_config.NumberColumn(format="%.1f", width='small'),
                            'Total': st.column_config.NumberColumn(format="%.1f", width='small'),
                            'Grade': st.column_config.TextColumn(width='small'),
                            'Attendance': st.column_config.TextColumn(width='small')
                        }
                    )
                    
                    # Add CSV Export
                    csv = perf_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Download Student Performance Data",
                        csv,
                        f"{selected_course_name.split(' - ')[0]}_student_data.csv",
                        "text/csv",
                        key='download-student-csv',
                        use_container_width=True
                    )
                    
                    # Create a correlation chart between attendance and grades
                    corr_data = []
                    for student in student_performance:
                        if student['total'] is not None and student['total_classes']:
                            attendance_rate = (student['present_count'] / student['total_classes']) * 100
                            corr_data.append({
                                'Student': student['name'],
                                'Attendance Rate': attendance_rate,
                                'Grade Score': student['total'] or 0
                            })
                    
                    if corr_data:
                        corr_df = pd.DataFrame(corr_data)
                        
                        # Create scatter plot
                        fig_corr = px.scatter(
                            corr_df,
                            x='Attendance Rate',
                            y='Grade Score',
                            hover_name='Student',
                            title=f"Attendance vs Grade Correlation for {selected_course_name.split(' - ')[0]}",
                            trendline='ols'
                        )
                        
                        # Display the chart
                        st.plotly_chart(fig_corr, use_container_width=True)
                        
                        # Calculate correlation
                        correlation = corr_df['Attendance Rate'].corr(corr_df['Grade Score'])
                        
                        if correlation > 0.7:
                            st.success(f"**Strong positive correlation** ({correlation:.2f}) between attendance and grades!")
                        elif correlation > 0.3:
                            st.info(f"**Moderate correlation** ({correlation:.2f}) between attendance and grades.")
                        else:
                            st.warning(f"**Weak correlation** ({correlation:.2f}) between attendance and grades for this course.")
                else:
                    st.info("No student performance data available for this course.")
        else:
            st.info("No courses assigned to you for this session.")
    
    st.markdown("---")
    
    # Section 5: Action Shortcuts
    st.subheader("⚡ Quick Actions")
    
    # Create two rows of action shortcuts for better organization
    row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
    row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)
    
    with row1_col1:
        if st.button("🧑‍🎓 View Students", use_container_width=True):
            st.session_state.current_page = "teacher_courses"
            st.rerun()
    
    with row1_col2:
        if st.button("✅ Mark Attendance", use_container_width=True):
            st.session_state.current_page = "teacher_attendance"
            st.rerun()
    
    with row1_col3:
        if st.button("📝 Submit Grades", use_container_width=True):
            st.session_state.current_page = "teacher_grades"
            st.rerun()
    
    with row1_col4:
        if st.button("📒 Assignments", use_container_width=True):
            st.session_state.current_page = "teacher_assignments"
            st.rerun()
    
    with row2_col1:
        if st.button("💬 Messages", use_container_width=True):
            st.session_state.current_page = "teacher_messages"
            st.rerun()
    
    with row2_col2:
        if st.button("📊 Analytics", use_container_width=True):
            st.session_state.current_page = "teacher_analytics"
            st.rerun()
    
    with row2_col3:
        if st.button("📅 Schedule", use_container_width=True):
            st.success("Course schedule feature coming soon!")
    
    with row2_col4:
        if st.button("👤 My Profile", use_container_width=True):
            st.session_state.current_page = "teacher_profile"
            st.success("Profile settings feature coming soon!")
    
    # AI Assistant
    with st.expander("🤖 AI Teaching Assistant", expanded=False):
        st.markdown("### AI-Powered Teaching Assistant")
        ai_prompt = st.text_area(
            "How can I help you with your teaching?", 
            placeholder="e.g. 'Help me create a study plan for my students who are struggling with midterms'",
            key="ai_assistant_prompt"
        )
        
        if st.button("Get AI Help", use_container_width=True):
            with st.spinner("Thinking..."):
                # In a real implementation, this would call an AI model
                # For demonstration, provide canned responses based on keywords
                if "study plan" in ai_prompt.lower() or "struggling" in ai_prompt.lower():
                    ai_response = """
                    Here's a suggested study plan for struggling students:
                    
                    1. **Identify the specific topics** where students are struggling using quiz data
                    2. **Schedule a weekly review session** focused on these topics
                    3. **Create supplementary materials** breaking down complex concepts
                    4. **Implement a peer tutoring system** pairing struggling students with top performers
                    5. **Set up regular check-ins** to monitor progress
                    
                    Would you like me to help create materials for any of these steps?
                    """
                elif "quiz" in ai_prompt.lower() or "test" in ai_prompt.lower():
                    ai_response = """
                    Here are some effective quiz creation strategies:
                    
                    1. **Mix question types** (multiple choice, short answer, long answer)
                    2. **Include questions of varying difficulty** to assess different levels of understanding
                    3. **Focus on application rather than memorization** to test deeper comprehension
                    4. **Provide clear grading rubrics** for open-ended questions
                    5. **Allow partial credit** for multi-step problems
                    
                    I can help you draft sample questions if you specify the topic.
                    """
                else:
                    ai_response = """
                    I'd be happy to help you with your teaching needs. Here are some areas I can assist with:
                    
                    1. Creating lesson plans and study materials
                    2. Designing effective assessments and quizzes
                    3. Developing strategies for student engagement
                    4. Analyzing student performance data
                    5. Suggesting interventions for struggling students
                    
                    Please provide more details about what you need help with.
                    """
                
                st.session_state.ai_response = ai_response
            
            st.markdown(st.session_state.ai_response)
            
            # Add buttons for common follow-up actions
            follow_col1, follow_col2 = st.columns(2)
            with follow_col1:
                if st.button("Create Materials", use_container_width=True):
                    st.info("This feature will generate customized teaching materials based on your needs.")
            
            with follow_col2:
                if st.button("Analyze Student Data", use_container_width=True):
                    st.session_state.current_page = "teacher_analytics"
                    st.rerun()
    
    # Close the database connection
    conn.close() 