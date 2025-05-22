import streamlit as st
import pandas as pd
from database.schema import get_db_connection
from components.header import render_page_title

def show():
    """Display the student courses page with registered classes for spring session"""
    render_page_title("🎓", "My Courses")
    
    # Get student ID from session
    student_id = st.session_state.user.get('user_id')
    
    # Connect to database
    conn = get_db_connection()
    
    # Ensure required tables exist
    ensure_required_tables(conn)
    
    # Get active academic session
    active_session = conn.execute(
        "SELECT name FROM academic_sessions WHERE is_active = 1"
    ).fetchone()
    
    # If no active session, use "Spring 2023" as the default
    current_session = active_session['name'] if active_session else "Spring 2023"
    
    # Session selector with spring session as default
    available_sessions = conn.execute(
        "SELECT DISTINCT semester FROM enrollments WHERE student_id = ? ORDER BY semester DESC",
        (student_id,)
    ).fetchall()
    
    available_session_list = [session['semester'] for session in available_sessions]
    
    # If there are no available sessions, show message
    if not available_session_list:
        st.warning("You are not enrolled in any courses. Please contact the administration.")
        conn.close()
        return
    
    # Set spring session as default if available
    default_index = 0
    for i, session in enumerate(available_session_list):
        if "Spring" in session:
            default_index = i
            break
    
    selected_session = st.selectbox(
        "Select Academic Session:",
        available_session_list,
        index=default_index
    )
    
    st.write(f"### Registered Classes for {selected_session}")
    
    # Get enrolled courses for the selected session
    enrolled_courses = conn.execute("""
        SELECT 
            c.code, 
            c.title, 
            c.credit_hour,
            t.name as teacher,
            t.dept as department,
            r.day,
            r.time_slot,
            r.room
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        LEFT JOIN teaching te ON c.id = te.course_id AND te.semester = e.semester
        LEFT JOIN teachers t ON te.teacher_id = t.id
        LEFT JOIN class_routine r ON c.id = r.course_id AND r.session = e.semester
        WHERE e.student_id = ? AND e.semester = ?
        ORDER BY c.code
    """, (student_id, selected_session)).fetchall()
    
    if not enrolled_courses:
        st.info(f"You are not enrolled in any courses for {selected_session}.")
    else:
        # Create dataframe for display
        df_courses = pd.DataFrame([dict(course) for course in enrolled_courses])
        
        # Create main course info section
        st.write("#### Course Information")
        course_info = df_courses[['code', 'title', 'credit_hour', 'teacher', 'department']].copy()
        course_info.columns = ['Course Code', 'Course Title', 'Credit Hours', 'Instructor', 'Department']
        st.dataframe(course_info, use_container_width=True, hide_index=True)
        
        # Create class schedule section if routine info exists
        if 'day' in df_courses and df_courses['day'].notna().any():
            st.write("#### Class Schedule")
            schedule_info = df_courses[['code', 'day', 'time_slot', 'room']].copy()
            schedule_info = schedule_info.dropna(subset=['day'])
            
            if not schedule_info.empty:
                schedule_info.columns = ['Course Code', 'Day', 'Time', 'Room']
                st.dataframe(schedule_info, use_container_width=True, hide_index=True)
            else:
                st.info("Class schedule has not been published yet.")
        else:
            st.info("Class schedule has not been published yet.")
        
        # Show total credit hours
        total_credits = df_courses['credit_hour'].sum()
        st.write(f"**Total Credit Hours:** {total_credits}")
        
        # Get exam schedule if available
        exam_schedule = conn.execute("""
            SELECT 
                c.code, 
                c.title,
                e.exam_date,
                e.start_time,
                e.end_time,
                e.room
            FROM enrollments en
            JOIN courses c ON en.course_id = c.id
            LEFT JOIN exam_schedule e ON c.id = e.course_id AND e.session = en.semester
            WHERE en.student_id = ? AND en.semester = ? AND e.exam_date IS NOT NULL
            ORDER BY e.exam_date, e.start_time
        """, (student_id, selected_session)).fetchall()
        
        if exam_schedule:
            st.write("#### Exam Schedule")
            df_exams = pd.DataFrame([dict(exam) for exam in exam_schedule])
            df_exams.columns = ['Course Code', 'Course Title', 'Exam Date', 'Start Time', 'End Time', 'Room']
            st.dataframe(df_exams, use_container_width=True, hide_index=True)
        else:
            st.info("Exam schedule has not been published yet.")
    
    # Close the database connection
    conn.close()

def ensure_required_tables(conn):
    """Ensure that required tables exist"""
    # Create class_routine table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS class_routine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            room TEXT NOT NULL,
            session TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (id),
            FOREIGN KEY (teacher_id) REFERENCES teachers (id)
        )
    """)
    
    # Create exam_schedule table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exam_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            exam_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            room TEXT NOT NULL,
            session TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        )
    """)
    
    conn.commit() 