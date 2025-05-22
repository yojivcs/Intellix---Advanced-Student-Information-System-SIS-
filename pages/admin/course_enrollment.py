import streamlit as st
import pandas as pd
import json
from database.schema import get_db_connection
from components.header import render_page_title
from datetime import datetime

def show():
    """Display the course assignment and enrollment page"""
    render_page_title("📚", "Course Assignment and Enrollment")
    
    # Initialize the database connection
    conn = get_db_connection()
    
    # Get all available sessions or create if not exists
    create_sessions_table_if_not_exists(conn)
    
    # Create tabs for different operations
    tab1, tab2, tab3, tab4 = st.tabs(["Academic Sessions", "Teacher Assignment", "Student Enrollment", "AI Assistant"])
    
    # Tab 1: Academic Sessions Management
    with tab1:
        st.subheader("Academic Session Management")
        
        # Display existing sessions
        sessions = get_all_sessions(conn)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if sessions:
                st.write("**Current Academic Sessions:**")
                
                # Convert to DataFrame for display
                session_data = []
                for session in sessions:
                    session_data.append({
                        "ID": session["id"],
                        "Session Name": session["name"],
                        "Status": "Active" if session["is_active"] else "Inactive"
                    })
                
                # Display sessions
                session_df = pd.DataFrame(session_data)
                st.dataframe(session_df, use_container_width=True, hide_index=True)
                
                # Set active session
                selected_session_id = st.selectbox(
                    "Select session to set as active",
                    options=[s["id"] for s in sessions],
                    format_func=lambda x: next((s["name"] for s in sessions if s["id"] == x), "")
                )
                
                if st.button("Set as Active Session"):
                    # Set selected session as active
                    set_active_session(conn, selected_session_id)
                    st.success(f"Active session updated successfully")
                    st.rerun()
            else:
                st.info("No academic sessions found. Create your first session.")
        
        with col2:
            # Create new session
            st.write("**Create New Session:**")
            
            with st.form("create_session_form"):
                # Get current year and next year
                current_year = datetime.now().year
                years = [str(y) for y in range(current_year-1, current_year+5)]
                
                # Session type and year
                session_type = st.selectbox("Session Type", ["Spring", "Summer", "Fall", "Winter"])
                session_year = st.selectbox("Year", years)
                
                # Create session name
                session_name = f"{session_type} {session_year}"
                
                submitted = st.form_submit_button("Create Session")
                
                if submitted:
                    # Check if session already exists
                    existing = conn.execute(
                        "SELECT id FROM academic_sessions WHERE name = ?", 
                        (session_name,)
                    ).fetchone()
                    
                    if existing:
                        st.error(f"Session {session_name} already exists")
                    else:
                        # Create new session
                        conn.execute(
                            "INSERT INTO academic_sessions (name, is_active) VALUES (?, ?)",
                            (session_name, 0)  # Not active by default
                        )
                        conn.commit()
                        st.success(f"Session {session_name} created successfully")
                        st.rerun()
    
    # Tab 2: Teacher Assignment
    with tab2:
        st.subheader("Teacher Assignment to Courses")
        
        # Get active session
        active_session = get_active_session(conn)
        
        if active_session:
            st.write(f"**Current Active Session:** {active_session['name']}")
            
            # Get all courses
            courses = conn.execute("SELECT id, code, title FROM courses ORDER BY code").fetchall()
            
            if courses:
                # Get all teachers
                teachers = conn.execute("SELECT id, name, dept FROM teachers ORDER BY name").fetchall()
                
                if teachers:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Select a course first
                        course_options = {f"{c['code']} - {c['title']}": c['id'] for c in courses}
                        selected_course_name = st.selectbox("Select Course", options=list(course_options.keys()), key="assign_course")
                        selected_course_id = course_options[selected_course_name]
                        
                        # Get assigned teachers for this course in the active session
                        assigned_teachers = conn.execute("""
                            SELECT t.id, t.name, t.dept
                            FROM teaching te
                            JOIN teachers t ON te.teacher_id = t.id
                            WHERE te.course_id = ? AND te.semester = ?
                            ORDER BY t.name
                        """, (selected_course_id, active_session['name'])).fetchall()
                        
                        if assigned_teachers:
                            st.write(f"**Assigned Teachers ({len(assigned_teachers)}):**")
                            for teacher in assigned_teachers:
                                col1, col2 = st.columns([3, 1])
                                col1.write(f"{teacher['name']} ({teacher['dept']})")
                                if col2.button("Remove", key=f"remove_teacher_{teacher['id']}"):
                                    # Remove assignment
                                    conn.execute(
                                        "DELETE FROM teaching WHERE teacher_id = ? AND course_id = ? AND semester = ?",
                                        (teacher['id'], selected_course_id, active_session['name'])
                                    )
                                    conn.commit()
                                    st.success(f"Teacher {teacher['name']} removed from course")
                                    st.rerun()
                        else:
                            st.info("No teachers assigned to this course for the current session")
                    
                    with col2:
                        st.write("**Assign Teachers:**")
                        
                        # Single teacher assignment
                        teacher_options = {f"{t['name']} ({t['dept']})": t['id'] for t in teachers}
                        selected_teacher_name = st.selectbox("Select Teacher", options=list(teacher_options.keys()))
                        selected_teacher_id = teacher_options[selected_teacher_name]
                        
                        if st.button("Assign Teacher"):
                            # Check if already assigned
                            existing = conn.execute(
                                "SELECT id FROM teaching WHERE teacher_id = ? AND course_id = ? AND semester = ?",
                                (selected_teacher_id, selected_course_id, active_session['name'])
                            ).fetchone()
                            
                            if existing:
                                st.error("Teacher is already assigned to this course for the current session")
                            else:
                                # Add assignment
                                conn.execute(
                                    "INSERT INTO teaching (teacher_id, course_id, semester) VALUES (?, ?, ?)",
                                    (selected_teacher_id, selected_course_id, active_session['name'])
                                )
                                conn.commit()
                                st.success("Teacher assigned successfully")
                                st.rerun()
                        
                        st.markdown("---")
                        
                        # Bulk assignment - teacher to multiple courses
                        st.write("**Bulk Assign Teacher to Multiple Courses:**")
                        
                        bulk_teacher_name = st.selectbox(
                            "Select Teacher for Bulk Assignment", 
                            options=list(teacher_options.keys()), 
                            key="bulk_teacher"
                        )
                        bulk_teacher_id = teacher_options[bulk_teacher_name]
                        
                        st.write("Select courses:")
                        selected_courses = []
                        
                        # Create a container with fixed height for scrolling
                        with st.container(height=200):
                            # Show all courses as checkboxes
                            for course in courses:
                                course_name = f"{course['code']} - {course['title']}"
                                if st.checkbox(course_name, key=f"course_{course['id']}"):
                                    selected_courses.append(course['id'])
                        
                        if st.button("Assign to Selected Courses"):
                            if selected_courses:
                                success_count = 0
                                error_count = 0
                                
                                for course_id in selected_courses:
                                    # Check if already assigned
                                    existing = conn.execute(
                                        "SELECT id FROM teaching WHERE teacher_id = ? AND course_id = ? AND semester = ?",
                                        (bulk_teacher_id, course_id, active_session['name'])
                                    ).fetchone()
                                    
                                    if not existing:
                                        # Add assignment
                                        conn.execute(
                                            "INSERT INTO teaching (teacher_id, course_id, semester) VALUES (?, ?, ?)",
                                            (bulk_teacher_id, course_id, active_session['name'])
                                        )
                                        success_count += 1
                                    else:
                                        error_count += 1
                                
                                conn.commit()
                                
                                if success_count > 0:
                                    st.success(f"Successfully assigned teacher to {success_count} courses.")
                                
                                if error_count > 0:
                                    st.warning(f"Teacher was already assigned to {error_count} of the selected courses.")
                                
                                st.rerun()
                            else:
                                st.info("Select at least one course to assign")
                else:
                    st.warning("No teachers found in the database")
            else:
                st.warning("No courses found in the database")
        else:
            st.warning("No active academic session. Please create and set an active session first.")
    
    # Tab 3: Student Enrollment
    with tab3:
        st.subheader("Student Enrollment Management")
        
        # Get active session
        active_session = get_active_session(conn)
        
        if active_session:
            st.write(f"**Current Active Session:** {active_session['name']}")
            
            # Get all courses
            courses = conn.execute("SELECT id, code, title FROM courses ORDER BY code").fetchall()
            
            if courses:
                # Get all students
                students = conn.execute("SELECT id, student_id, name, dept, semester FROM students ORDER BY name").fetchall()
                
                if students:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Select a course first
                        course_options = {f"{c['code']} - {c['title']}": c['id'] for c in courses}
                        selected_course_name = st.selectbox("Select Course", options=list(course_options.keys()), key="enroll_course")
                        selected_course_id = course_options[selected_course_name]
                        
                        # Display enrolled students for this course in the active session
                        enrolled_students = conn.execute("""
                            SELECT s.id, s.student_id, s.name, s.dept, s.semester
                            FROM enrollments e
                            JOIN students s ON e.student_id = s.id
                            WHERE e.course_id = ? AND e.semester = ?
                            ORDER BY s.name
                        """, (selected_course_id, active_session['name'])).fetchall()
                        
                        if enrolled_students:
                            st.write(f"**Enrolled Students ({len(enrolled_students)}):**")
                            for student in enrolled_students:
                                col1, col2 = st.columns([3, 1])
                                col1.write(f"{student['student_id']} - {student['name']}")
                                if col2.button("Remove", key=f"remove_student_{student['id']}"):
                                    # Remove enrollment
                                    conn.execute(
                                        "DELETE FROM enrollments WHERE student_id = ? AND course_id = ? AND semester = ?",
                                        (student['id'], selected_course_id, active_session['name'])
                                    )
                                    conn.commit()
                                    st.success(f"Student {student['name']} removed from course")
                                    st.rerun()
                        else:
                            st.info("No students enrolled in this course for the current session")
                    
                    with col2:
                        st.write("**Enroll Students:**")
                        
                        # Single student enrollment
                        student_options = {f"{s['student_id']} - {s['name']}": s['id'] for s in students}
                        selected_student_name = st.selectbox("Select Student", options=list(student_options.keys()))
                        selected_student_id = student_options[selected_student_name]
                        
                        if st.button("Enroll Student"):
                            # Check if already enrolled
                            existing = conn.execute(
                                "SELECT id FROM enrollments WHERE student_id = ? AND course_id = ? AND semester = ?",
                                (selected_student_id, selected_course_id, active_session['name'])
                            ).fetchone()
                            
                            if existing:
                                st.error("Student is already enrolled in this course for the current session")
                            else:
                                # Add enrollment
                                conn.execute(
                                    "INSERT INTO enrollments (student_id, course_id, semester) VALUES (?, ?, ?)",
                                    (selected_student_id, selected_course_id, active_session['name'])
                                )
                                conn.commit()
                                st.success("Student enrolled successfully")
                                st.rerun()
                        
                        st.markdown("---")
                        
                        # Bulk enrollment
                        st.write("**Bulk Enroll Students by ID:**")
                        st.write("Select the students to enroll in this course:")
                        selected_students = []
                        
                        # Show all students as checkboxes
                        for student in students:
                            student_name = f"{student['student_id']} - {student['name']}"
                            if st.checkbox(student_name, key=f"student_{student['id']}"):
                                selected_students.append(student['id'])
                        
                        if st.button("Bulk Enroll"):
                            if selected_students:
                                success_count = 0
                                error_count = 0
                                
                                for student_id in selected_students:
                                    # Check if already enrolled
                                    existing = conn.execute(
                                        "SELECT id FROM enrollments WHERE student_id = ? AND course_id = ? AND semester = ?",
                                        (student_id, selected_course_id, active_session['name'])
                                    ).fetchone()
                                    
                                    if not existing:
                                        # Add enrollment
                                        conn.execute(
                                            "INSERT INTO enrollments (student_id, course_id, semester) VALUES (?, ?, ?)",
                                            (student_id, selected_course_id, active_session['name'])
                                        )
                                        success_count += 1
                                    else:
                                        error_count += 1
                                
                                conn.commit()
                                
                                if success_count > 0:
                                    st.success(f"Successfully enrolled {success_count} students.")
                                
                                if error_count > 0:
                                    st.warning(f"{error_count} students were skipped (already enrolled).")
                                
                                st.rerun()
                else:
                    st.warning("No students found in the database")
            else:
                st.warning("No courses found in the database")
        else:
            st.warning("No active academic session. Please create and set an active session first.")
    
    # Tab 4: AI Assistant
    with tab4:
        st.subheader("AI Assistant for Course Management")
        
        # Get active session
        active_session = get_active_session(conn)
        
        if active_session:
            st.write(f"**Current Active Session:** {active_session['name']}")
            
            st.info("""
            Use the AI Assistant to help you with course assignment and enrollment tasks.
            
            **Example commands:**
            - "Assign teacher Jane Smith to courses CSE101, CSE102, and CSE303"
            - "Enroll students STU12345, STU23456, STU34567 to course MAT201"
            - "Show all courses taught by Dr. Johnson"
            - "List all students enrolled in PHY101"
            """)
            
            # AI command input
            ai_command = st.text_area("Enter your command:", height=100, 
                                      placeholder="Example: Assign teacher Jane Smith to courses CSE101, CSE102")
            
            if st.button("Process Command", type="primary"):
                if ai_command:
                    # Simulate AI processing
                    with st.spinner("Processing your command..."):
                        # Check for assignment command
                        if "assign teacher" in ai_command.lower() and "to course" in ai_command.lower():
                            try:
                                # Extract teacher name
                                teacher_parts = ai_command.lower().split("assign teacher ")[1].split(" to course")
                                teacher_name = teacher_parts[0].strip()
                                
                                # Extract course codes
                                course_text = teacher_parts[1]
                                course_codes = [c.strip() for c in course_text.replace(",", " ").replace("and", " ").split() if c.strip()]
                                
                                # Find matching teachers
                                teachers = conn.execute("SELECT id, name FROM teachers WHERE LOWER(name) LIKE ?", 
                                                        (f"%{teacher_name}%",)).fetchall()
                                
                                # Find matching courses
                                courses_found = []
                                for code in course_codes:
                                    course = conn.execute("SELECT id, code, title FROM courses WHERE LOWER(code) LIKE ?", 
                                                        (f"%{code.lower()}%",)).fetchall()
                                    courses_found.extend(course)
                                
                                if teachers and courses_found:
                                    st.success("Command processed successfully!")
                                    
                                    # Show form for confirmation
                                    st.subheader("Please confirm the assignment:")
                                    
                                    # Select teacher
                                    teacher_options = {f"{t['name']}": t['id'] for t in teachers}
                                    selected_teacher = st.selectbox("Select Teacher", options=list(teacher_options.keys()))
                                    selected_teacher_id = teacher_options[selected_teacher]
                                    
                                    # Select courses
                                    st.write("**Select courses to assign:**")
                                    selected_courses = []
                                    
                                    for course in courses_found:
                                        if st.checkbox(f"{course['code']} - {course['title']}", value=True, key=f"ai_course_{course['id']}"):
                                            selected_courses.append(course['id'])
                                    
                                    if st.button("Confirm Assignment"):
                                        if selected_courses:
                                            success_count = 0
                                            error_count = 0
                                            
                                            for course_id in selected_courses:
                                                # Check if already assigned
                                                existing = conn.execute(
                                                    "SELECT id FROM teaching WHERE teacher_id = ? AND course_id = ? AND semester = ?",
                                                    (selected_teacher_id, course_id, active_session['name'])
                                                ).fetchone()
                                                
                                                if not existing:
                                                    # Add assignment
                                                    conn.execute(
                                                        "INSERT INTO teaching (teacher_id, course_id, semester) VALUES (?, ?, ?)",
                                                        (selected_teacher_id, course_id, active_session['name'])
                                                    )
                                                    success_count += 1
                                                else:
                                                    error_count += 1
                                            
                                            conn.commit()
                                            
                                            if success_count > 0:
                                                st.success(f"Successfully assigned teacher to {success_count} courses.")
                                            
                                            if error_count > 0:
                                                st.warning(f"Teacher was already assigned to {error_count} of the selected courses.")
                                                
                                            st.rerun()
                                else:
                                    if not teachers:
                                        st.error(f"No teacher found matching '{teacher_name}'")
                                    if not courses_found:
                                        st.error(f"No courses found matching the provided codes")
                            except Exception as e:
                                st.error(f"Error processing command: {e}")
                        
                        # Check for enrollment command
                        elif "enroll student" in ai_command.lower() and "to course" in ai_command.lower():
                            try:
                                # Extract student IDs
                                student_parts = ai_command.lower().split("enroll student")[1].split("to course")
                                student_ids_text = student_parts[0].strip()
                                student_ids = [s.strip() for s in student_ids_text.replace(",", " ").replace("and", " ").split() if s.strip()]
                                
                                # Extract course code
                                course_code = student_parts[1].strip()
                                
                                # Find matching students
                                students_found = []
                                for sid in student_ids:
                                    student = conn.execute("SELECT id, student_id, name FROM students WHERE LOWER(student_id) LIKE ?", 
                                                        (f"%{sid.lower()}%",)).fetchall()
                                    students_found.extend(student)
                                
                                # Find matching course
                                courses = conn.execute("SELECT id, code, title FROM courses WHERE LOWER(code) LIKE ?", 
                                                    (f"%{course_code.lower()}%",)).fetchall()
                                
                                if students_found and courses:
                                    st.success("Command processed successfully!")
                                    
                                    # Show form for confirmation
                                    st.subheader("Please confirm the enrollment:")
                                    
                                    # Select course
                                    course_options = {f"{c['code']} - {c['title']}": c['id'] for c in courses}
                                    selected_course = st.selectbox("Select Course", options=list(course_options.keys()))
                                    selected_course_id = course_options[selected_course]
                                    
                                    # Select students
                                    st.write("**Select students to enroll:**")
                                    selected_students = []
                                    
                                    for student in students_found:
                                        if st.checkbox(f"{student['student_id']} - {student['name']}", value=True, key=f"ai_student_{student['id']}"):
                                            selected_students.append(student['id'])
                                    
                                    if st.button("Confirm Enrollment"):
                                        if selected_students:
                                            success_count = 0
                                            error_count = 0
                                            
                                            for student_id in selected_students:
                                                # Check if already enrolled
                                                existing = conn.execute(
                                                    "SELECT id FROM enrollments WHERE student_id = ? AND course_id = ? AND semester = ?",
                                                    (student_id, selected_course_id, active_session['name'])
                                                ).fetchone()
                                                
                                                if not existing:
                                                    # Add enrollment
                                                    conn.execute(
                                                        "INSERT INTO enrollments (student_id, course_id, semester) VALUES (?, ?, ?)",
                                                        (student_id, selected_course_id, active_session['name'])
                                                    )
                                                    success_count += 1
                                                else:
                                                    error_count += 1
                                            
                                            conn.commit()
                                            
                                            if success_count > 0:
                                                st.success(f"Successfully enrolled {success_count} students.")
                                            
                                            if error_count > 0:
                                                st.warning(f"{error_count} students were skipped (already enrolled).")
                                                
                                            st.rerun()
                                else:
                                    if not students_found:
                                        st.error(f"No students found matching the provided IDs")
                                    if not courses:
                                        st.error(f"No course found matching '{course_code}'")
                            except Exception as e:
                                st.error(f"Error processing command: {e}")
                        
                        else:
                            st.warning("Command not recognized. Please try with one of the example formats.")
                else:
                    st.warning("Please enter a command to process")
        else:
            st.warning("No active academic session. Please create and set an active session first.")
    
    # Close the database connection
    conn.close()

def create_sessions_table_if_not_exists(conn):
    """Create the academic_sessions table if it doesn't exist"""
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='academic_sessions'")
    if not cursor.fetchone():
        # Create table
        cursor.execute('''
        CREATE TABLE academic_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()

def get_all_sessions(conn):
    """Get all academic sessions"""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, is_active FROM academic_sessions ORDER BY name DESC")
    return cursor.fetchall()

def get_active_session(conn):
    """Get the active academic session"""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM academic_sessions WHERE is_active = 1")
    return cursor.fetchone()

def set_active_session(conn, session_id):
    """Set the active academic session"""
    cursor = conn.cursor()
    
    # First, set all sessions as inactive
    cursor.execute("UPDATE academic_sessions SET is_active = 0")
    
    # Then set the selected session as active
    cursor.execute("UPDATE academic_sessions SET is_active = 1 WHERE id = ?", (session_id,))
    
    conn.commit() 