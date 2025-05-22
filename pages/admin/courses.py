import streamlit as st
import pandas as pd
import os
import uuid
import csv
import io
from PIL import Image
from database.schema import get_db_connection
from components.header import render_page_title
from datetime import datetime

def show():
    """Display the course management page"""
    render_page_title("🎓", "Course Management Panel")
    
    # Create tabs for different operations
    tab1, tab2, tab3, tab4 = st.tabs(["View Courses", "Add Course", "Student Enrollment", "Teacher Assignment"])
    
    # Tab 1: View Courses
    with tab1:
        # Connect to database
        conn = get_db_connection()
        
        # Ensure academic sessions table exists
        create_sessions_table_if_not_exists(conn)
        
        # Get all courses with enrollment count
        courses = conn.execute("""
            SELECT c.id, c.code, c.title, c.credit_hour, c.max_students,
                   COUNT(e.id) as enrolled_students
            FROM courses c
            LEFT JOIN enrollments e ON c.id = e.course_id
            GROUP BY c.id
            ORDER BY c.code
        """).fetchall()
        
        # Get active session for display
        active_session = get_active_session(conn)
        if active_session:
            st.info(f"Current Active Session: {active_session['name']}")
        
        if courses:
            # Convert to a list of dictionaries for proper display
            course_list = []
            for row in courses:
                course_list.append({
                    "ID": row["id"],
                    "Code": row["code"],
                    "Title": row["title"],
                    "Credit Hours": row["credit_hour"],
                    "Capacity": row["max_students"],
                    "Enrolled": row["enrolled_students"],
                })
            
            # Add a search filter
            search = st.text_input("🔍 Search by course code or title", "")
            
            # Table headers
            headers = st.columns([1.2, 2.5, 1, 1, 1, 1.2])
            headers[0].write("**Course Code**")
            headers[1].write("**Course Title**")
            headers[2].write("**Credits**")
            headers[3].write("**Capacity**")
            headers[4].write("**Enrolled**")
            headers[5].write("**Actions**")
            
            st.markdown("---")
            
            # Filter courses based on search
            filtered_courses = course_list
            if search:
                search = search.lower()
                filtered_courses = [c for c in course_list if search in c['Code'].lower() or search in c['Title'].lower()]
            
            if not filtered_courses:
                st.info("No courses found matching your search criteria.")
            
            # Display each course as a row
            for course in filtered_courses:
                row = st.container()
                with row:
                    cols = st.columns([1.2, 2.5, 1, 1, 1, 1.2])
                    
                    cols[0].write(f"**{course['Code']}**")
                    cols[1].write(f"{course['Title']}")
                    cols[2].write(f"{course['Credit Hours']}")
                    cols[3].write(f"{course['Capacity']}")
                    cols[4].write(f"{course['Enrolled']}/{course['Capacity']}")
                    
                    # Action buttons
                    with cols[5]:
                        action_cols = st.columns(3)
                        if action_cols[0].button("👁️", key=f"view_{course['ID']}", help="View details"):
                            st.session_state.selected_course = course['ID']
                        
                        if action_cols[1].button("✏️", key=f"edit_{course['ID']}", help="Edit course"):
                            st.session_state.edit_course = course['ID']
                        
                        if action_cols[2].button("🗑️", key=f"del_{course['ID']}", help="Delete course"):
                            st.session_state.delete_course = course['ID']
            
            # Initialize session state variables if not exist
            if 'selected_course' not in st.session_state:
                st.session_state.selected_course = None
                
            if 'edit_course' not in st.session_state:
                st.session_state.edit_course = None
                
            if 'delete_course' not in st.session_state:
                st.session_state.delete_course = None
            
            # Show course details
            if st.session_state.selected_course:
                course_data = next((c for c in courses if c['id'] == st.session_state.selected_course), None)
                if course_data:
                    st.markdown("---")
                    st.subheader(f"{course_data['code']} - {course_data['title']}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Credit Hours:** {course_data['credit_hour']}")
                        st.write(f"**Maximum Students:** {course_data['max_students']}")
                        st.write(f"**Currently Enrolled:** {course_data['enrolled_students']}")
                        
                        # Get enrolled students
                        students = conn.execute("""
                            SELECT s.id, s.student_id, s.name, s.dept, s.semester, e.semester as enrollment_semester
                            FROM enrollments e
                            JOIN students s ON e.student_id = s.id
                            WHERE e.course_id = ?
                            ORDER BY s.name
                        """, (course_data['id'],)).fetchall()
                        
                        if students:
                            st.subheader("Enrolled Students")
                            for student in students:
                                st.write(f"• {student['student_id']} - {student['name']} ({student['enrollment_semester']})")
                        else:
                            st.info("No students enrolled in this course")
                    
                    with col2:
                        # Get assigned teachers
                        teachers = conn.execute("""
                            SELECT t.id, t.name, t.dept, te.semester
                            FROM teaching te
                            JOIN teachers t ON te.teacher_id = t.id
                            WHERE te.course_id = ?
                            ORDER BY t.name
                        """, (course_data['id'],)).fetchall()
                        
                        if teachers:
                            st.subheader("Assigned Teachers")
                            for teacher in teachers:
                                st.write(f"• {teacher['name']} ({teacher['semester']})")
                        else:
                            st.info("No teachers assigned to this course")
                    
                    if st.button("Close", key="close_details"):
                        st.session_state.selected_course = None
                        st.rerun()
            
            # Edit course form
            if st.session_state.edit_course:
                course_data = next((c for c in courses if c['id'] == st.session_state.edit_course), None)
                if course_data:
                    st.markdown("---")
                    with st.container(border=True):
                        st.subheader(f"Edit Course: {course_data['code']}")
                        
                        with st.form("edit_course_form"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                code = st.text_input("Course Code*", value=course_data['code'])
                                title = st.text_input("Course Title*", value=course_data['title'])
                            
                            with col2:
                                credit_hour = st.number_input("Credit Hours*", min_value=0.5, max_value=12.0, value=float(course_data['credit_hour']), step=0.5)
                                max_students = st.number_input("Maximum Students*", min_value=1, max_value=500, value=int(course_data['max_students']))
                            
                            update = st.form_submit_button("Update Course", use_container_width=True)
                            
                            if update:
                                if code and title:
                                    # Check if code already exists but is not this course
                                    existing = conn.execute(
                                        "SELECT id FROM courses WHERE code = ? AND id != ?", 
                                        (code, course_data['id'])
                                    ).fetchone()
                                    
                                    if existing:
                                        st.error(f"Course code {code} already exists. Please use a unique code.")
                                    else:
                                        # Update course in database
                                        conn.execute(
                                            """UPDATE courses 
                                            SET code = ?, title = ?, credit_hour = ?, max_students = ? 
                                            WHERE id = ?""",
                                            (code, title, credit_hour, max_students, course_data['id'])
                                        )
                                        conn.commit()
                                        
                                        st.success("Course updated successfully!")
                                        st.session_state.edit_course = None
                                        st.rerun()
                                else:
                                    st.error("Course Code and Title are required fields")
                        
                        if st.button("Cancel", key="cancel_edit"):
                            st.session_state.edit_course = None
                            st.rerun()
            
            # Handle delete course
            if st.session_state.delete_course:
                course_data = next((c for c in courses if c['id'] == st.session_state.delete_course), None)
                if course_data:
                    st.markdown("---")
                    with st.container(border=True):
                        st.warning(f"Are you sure you want to delete course: {course_data['code']} - {course_data['title']}?")
                        
                        if course_data['enrolled_students'] > 0:
                            st.error(f"This course has {course_data['enrolled_students']} enrolled students. Please remove all enrollments before deleting.")
                            delete_disabled = True
                        else:
                            delete_disabled = False
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("Yes, Delete", type="primary", key="confirm_delete", disabled=delete_disabled):
                                # Delete course from database
                                conn.execute("DELETE FROM courses WHERE id = ?", (course_data['id'],))
                                conn.commit()
                                
                                st.success(f"Course {course_data['code']} deleted successfully!")
                                st.session_state.delete_course = None
                                st.rerun()
                        
                        with col2:
                            if st.button("Cancel", key="cancel_delete"):
                                st.session_state.delete_course = None
                                st.rerun()
        else:
            st.info("No courses found in the database")
        
        conn.close()
    
    # Tab 2: Add Course
    with tab2:
        st.subheader("Add New Course")
        
        # Connect to database
        conn = get_db_connection()
        
        # Ensure academic sessions table exists
        create_sessions_table_if_not_exists(conn)
        
        # Get all available sessions
        sessions = get_all_sessions(conn)
        
        # Get active session
        active_session = get_active_session(conn)
        
        if active_session:
            st.info(f"Current Active Session: {active_session['name']}")
        
        # Single course form
        with st.expander("Add Single Course", expanded=True):
            with st.form("add_course_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    code = st.text_input("Course Code*")
                    title = st.text_input("Course Title*")
                
                with col2:
                    credit_hour = st.number_input("Credit Hours*", min_value=0.5, max_value=12.0, value=3.0, step=0.5)
                    max_students = st.number_input("Maximum Students*", min_value=1, max_value=500, value=40)
                
                # Add session selection
                if sessions:
                    session_options = {s["name"]: s["id"] for s in sessions}
                    selected_session_name = st.selectbox(
                        "Academic Session*", 
                        options=list(session_options.keys()),
                        index=next((i for i, s in enumerate(sessions) if s["is_active"]), 0) if sessions else 0
                    )
                    selected_session_id = session_options[selected_session_name]
                else:
                    st.warning("No academic sessions found. Please create a session in the Course Assignment and Enrollment page first.")
                    selected_session_id = None
                
                submit = st.form_submit_button("Add Course", use_container_width=True)
                
                if submit:
                    if code and title and selected_session_id:
                        # Check if code already exists
                        existing = conn.execute("SELECT id FROM courses WHERE code = ?", (code,)).fetchone()
                        
                        if existing:
                            st.error(f"Course code {code} already exists. Please use a unique code.")
                        else:
                            # Insert new course
                            cursor = conn.execute(
                                "INSERT INTO courses (code, title, credit_hour, max_students) VALUES (?, ?, ?, ?)",
                                (code, title, credit_hour, max_students)
                            )
                            course_id = cursor.lastrowid
                            conn.commit()
                            
                            # Get the session name
                            session_name = next((s["name"] for s in sessions if s["id"] == selected_session_id), "")
                            
                            st.success(f"Course {code} - {title} added successfully!")
                            st.info(f"Course will be available for the {session_name} academic session.")
                    else:
                        if not selected_session_id:
                            st.error("Please create an academic session first.")
                        else:
                            st.error("Course Code and Title are required fields")
        
        # Bulk import form
        with st.expander("Bulk Import Courses from CSV"):
            st.markdown("""
            Upload a CSV file with the following columns:
            - Code (required)
            - Title (required)
            - CreditHours (required)
            - MaxStudents (optional, default is 40)
            
            Example CSV format:
            ```
            Code,Title,CreditHours,MaxStudents
            CS101,Introduction to Computer Science,3.0,50
            MATH201,Calculus I,4.0,60
            ```
            """)
            
            # Add session selection for bulk import
            if sessions:
                bulk_session_options = {s["name"]: s["id"] for s in sessions}
                bulk_selected_session_name = st.selectbox(
                    "Academic Session for Bulk Import*", 
                    options=list(bulk_session_options.keys()),
                    index=next((i for i, s in enumerate(sessions) if s["is_active"]), 0) if sessions else 0,
                    key="bulk_session"
                )
                bulk_selected_session_id = bulk_session_options[bulk_selected_session_name]
            else:
                st.warning("No academic sessions found. Please create a session in the Course Assignment and Enrollment page first.")
                bulk_selected_session_id = None
                
            uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'])
            
            if uploaded_file:
                try:
                    # Read CSV file
                    df = pd.read_csv(uploaded_file)
                    
                    # Check required columns
                    required_columns = ['Code', 'Title', 'CreditHours']
                    if not all(col in df.columns for col in required_columns):
                        st.error("CSV file must contain columns: Code, Title, CreditHours")
                    else:
                        # Display preview
                        st.write("Preview of data to be imported:")
                        st.dataframe(df.head(5))
                        
                        if st.button("Import Courses") and bulk_selected_session_id:
                            # Process each row
                            success_count = 0
                            error_count = 0
                            
                            for _, row in df.iterrows():
                                code = row['Code']
                                title = row['Title']
                                credit_hour = row['CreditHours']
                                max_students = row.get('MaxStudents', 40)
                                
                                # Check if code already exists
                                existing = conn.execute("SELECT id FROM courses WHERE code = ?", (code,)).fetchone()
                                
                                if not existing:
                                    # Insert new course
                                    conn.execute(
                                        "INSERT INTO courses (code, title, credit_hour, max_students) VALUES (?, ?, ?, ?)",
                                        (code, title, credit_hour, max_students)
                                    )
                                    success_count += 1
                                else:
                                    error_count += 1
                            
                            conn.commit()
                            
                            # Get the session name
                            session_name = next((s["name"] for s in sessions if s["id"] == bulk_selected_session_id), "")
                            
                            if success_count > 0:
                                st.success(f"Successfully imported {success_count} courses for the {session_name} academic session.")
                            
                            if error_count > 0:
                                st.warning(f"{error_count} courses were skipped because their course codes already exist.")
                except Exception as e:
                    st.error(f"Error processing CSV file: {e}")
        
        conn.close()
    
    # Tab 3: Student Enrollment
    with tab3:
        st.subheader("Student Enrollment Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Connect to database
            conn = get_db_connection()
            
            # Get all courses
            courses = conn.execute("SELECT id, code, title FROM courses ORDER BY code").fetchall()
            
            if courses:
                course_options = {f"{c['code']} - {c['title']}": c['id'] for c in courses}
                selected_course_name = st.selectbox("Select Course", options=list(course_options.keys()))
                selected_course_id = course_options[selected_course_name]
                
                # Get semester options
                current_year = datetime.now().year
                semester_options = [f"Spring {current_year}", f"Summer {current_year}", f"Fall {current_year}"]
                selected_semester = st.selectbox("Select Semester", options=semester_options)
                
                # Display enrolled students for this course and semester
                enrolled_students = conn.execute("""
                    SELECT s.id, s.student_id, s.name, s.dept, s.semester
                    FROM enrollments e
                    JOIN students s ON e.student_id = s.id
                    WHERE e.course_id = ? AND e.semester = ?
                    ORDER BY s.name
                """, (selected_course_id, selected_semester)).fetchall()
                
                if enrolled_students:
                    st.write(f"**Enrolled Students ({len(enrolled_students)}):**")
                    for student in enrolled_students:
                        col1, col2 = st.columns([3, 1])
                        col1.write(f"{student['student_id']} - {student['name']}")
                        if col2.button("Remove", key=f"remove_{student['id']}"):
                            # Remove enrollment
                            conn.execute(
                                "DELETE FROM enrollments WHERE student_id = ? AND course_id = ? AND semester = ?",
                                (student['id'], selected_course_id, selected_semester)
                            )
                            conn.commit()
                            st.success("Student removed from course")
                            st.rerun()
                else:
                    st.info("No students enrolled in this course for the selected semester")
            else:
                st.warning("No courses found in the database")
        
        with col2:
            if courses:  # Only show if courses exist
                st.subheader("Enroll Students")
                
                # Get all students
                students = conn.execute("SELECT id, student_id, name FROM students ORDER BY name").fetchall()
                
                if students:
                    # Single student enrollment
                    with st.expander("Enroll Single Student", expanded=True):
                        student_options = {f"{s['student_id']} - {s['name']}": s['id'] for s in students}
                        selected_student_name = st.selectbox("Select Student", options=list(student_options.keys()))
                        selected_student_id = student_options[selected_student_name]
                        
                        if st.button("Enroll Student"):
                            # Check if already enrolled
                            existing = conn.execute(
                                "SELECT id FROM enrollments WHERE student_id = ? AND course_id = ? AND semester = ?",
                                (selected_student_id, selected_course_id, selected_semester)
                            ).fetchone()
                            
                            if existing:
                                st.error("Student is already enrolled in this course for the selected semester")
                            else:
                                # Add enrollment
                                conn.execute(
                                    "INSERT INTO enrollments (student_id, course_id, semester) VALUES (?, ?, ?)",
                                    (selected_student_id, selected_course_id, selected_semester)
                                )
                                conn.commit()
                                st.success("Student enrolled successfully")
                                st.rerun()
                    
                    # Bulk enrollment
                    with st.expander("Bulk Enroll Students"):
                        st.write("Enter student IDs (one per line) to enroll multiple students at once:")
                        student_ids = st.text_area("Student IDs", height=150)
                        
                        if st.button("Bulk Enroll"):
                            if student_ids:
                                student_id_list = [sid.strip() for sid in student_ids.split('\n') if sid.strip()]
                                
                                if student_id_list:
                                    success_count = 0
                                    error_count = 0
                                    
                                    for sid in student_id_list:
                                        # Find student by student_id
                                        student = conn.execute(
                                            "SELECT id FROM students WHERE student_id = ?", 
                                            (sid,)
                                        ).fetchone()
                                        
                                        if student:
                                            # Check if already enrolled
                                            existing = conn.execute(
                                                "SELECT id FROM enrollments WHERE student_id = ? AND course_id = ? AND semester = ?",
                                                (student['id'], selected_course_id, selected_semester)
                                            ).fetchone()
                                            
                                            if not existing:
                                                # Add enrollment
                                                conn.execute(
                                                    "INSERT INTO enrollments (student_id, course_id, semester) VALUES (?, ?, ?)",
                                                    (student['id'], selected_course_id, selected_semester)
                                                )
                                                success_count += 1
                                            else:
                                                error_count += 1
                                        else:
                                            error_count += 1
                                    
                                    conn.commit()
                                    
                                    if success_count > 0:
                                        st.success(f"Successfully enrolled {success_count} students.")
                                    
                                    if error_count > 0:
                                        st.warning(f"{error_count} students were skipped (either not found or already enrolled).")
                                        
                                    st.rerun()
                else:
                    st.warning("No students found in the database")
        
            conn.close()
    
    # Tab 4: Teacher Assignment
    with tab4:
        st.subheader("Teacher Assignment Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Connect to database
            conn = get_db_connection()
            
            # Get all courses
            courses = conn.execute("SELECT id, code, title FROM courses ORDER BY code").fetchall()
            
            if courses:
                course_options = {f"{c['code']} - {c['title']}": c['id'] for c in courses}
                selected_course_name = st.selectbox("Select Course", options=list(course_options.keys()), key="teacher_course")
                selected_course_id = course_options[selected_course_name]
                
                # Get semester options
                current_year = datetime.now().year
                semester_options = [f"Spring {current_year}", f"Summer {current_year}", f"Fall {current_year}"]
                selected_semester = st.selectbox("Select Semester", options=semester_options, key="teacher_semester")
                
                # Display assigned teachers for this course and semester
                assigned_teachers = conn.execute("""
                    SELECT t.id, t.name, t.dept
                    FROM teaching te
                    JOIN teachers t ON te.teacher_id = t.id
                    WHERE te.course_id = ? AND te.semester = ?
                    ORDER BY t.name
                """, (selected_course_id, selected_semester)).fetchall()
                
                if assigned_teachers:
                    st.write(f"**Assigned Teachers ({len(assigned_teachers)}):**")
                    for teacher in assigned_teachers:
                        col1, col2 = st.columns([3, 1])
                        col1.write(f"{teacher['name']} ({teacher['dept']})")
                        if col2.button("Remove", key=f"remove_teacher_{teacher['id']}"):
                            # Remove assignment
                            conn.execute(
                                "DELETE FROM teaching WHERE teacher_id = ? AND course_id = ? AND semester = ?",
                                (teacher['id'], selected_course_id, selected_semester)
                            )
                            conn.commit()
                            st.success("Teacher removed from course")
                            st.rerun()
                else:
                    st.info("No teachers assigned to this course for the selected semester")
            else:
                st.warning("No courses found in the database")
        
        with col2:
            if courses:  # Only show if courses exist
                st.subheader("Assign Teachers")
                
                # Get all teachers
                teachers = conn.execute("SELECT id, name, dept FROM teachers ORDER BY name").fetchall()
                
                if teachers:
                    # Single teacher assignment
                    st.write("**Assign Single Teacher:**")
                    teacher_options = {f"{t['name']} ({t['dept']})": t['id'] for t in teachers}
                    selected_teacher_name = st.selectbox("Select Teacher", options=list(teacher_options.keys()))
                    selected_teacher_id = teacher_options[selected_teacher_name]
                    
                    if st.button("Assign Teacher"):
                        # Check if already assigned
                        existing = conn.execute(
                            "SELECT id FROM teaching WHERE teacher_id = ? AND course_id = ? AND semester = ?",
                            (selected_teacher_id, selected_course_id, selected_semester)
                        ).fetchone()
                        
                        if existing:
                            st.error("Teacher is already assigned to this course for the selected semester")
                        else:
                            # Add assignment
                            conn.execute(
                                "INSERT INTO teaching (teacher_id, course_id, semester) VALUES (?, ?, ?)",
                                (selected_teacher_id, selected_course_id, selected_semester)
                            )
                            conn.commit()
                            st.success("Teacher assigned successfully")
                            st.rerun()
                    
                    st.markdown("---")
                    
                    # Bulk assignment
                    st.write("**Bulk Assign Teachers to Multiple Courses:**")
                    bulk_teacher_name = st.selectbox("Select Teacher", options=list(teacher_options.keys()), key="bulk_teacher")
                    bulk_teacher_id = teacher_options[bulk_teacher_name]
                    
                    st.write("Select the courses to assign this teacher:")
                    selected_courses = []
                    
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
                                    (bulk_teacher_id, course_id, selected_semester)
                                ).fetchone()
                                
                                if not existing:
                                    # Add assignment
                                    conn.execute(
                                        "INSERT INTO teaching (teacher_id, course_id, semester) VALUES (?, ?, ?)",
                                        (bulk_teacher_id, course_id, selected_semester)
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
                    st.warning("No teachers found in the database")
        
            conn.close() 

# Helper functions from course_enrollment.py
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