import streamlit as st
import pandas as pd
import os
import uuid
import random
import string
import base64
import io
from PIL import Image
from database.schema import get_db_connection
from components.header import render_page_title
from utils.auth import generate_credentials
from datetime import datetime

def generate_student_id():
    """Generate a unique student ID with STU prefix followed by 5 digits"""
    # Generate random 5-digit number
    digits = ''.join(random.choices(string.digits, k=5))
    student_id = f"STU{digits}"
    
    # Check if this ID already exists in the database
    conn = get_db_connection()
    existing = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    conn.close()
    
    # If ID exists, generate a new one recursively
    if existing:
        return generate_student_id()
    
    return student_id

def show():
    """Display the student management page"""
    render_page_title("👨‍🎓", "Student Management")
    
    # Create tabs for different operations
    tab1, tab2, tab3, tab4 = st.tabs(["View Students", "Add Student", "Edit/Delete Student", "Credentials Management"])
    
    # Tab 1: View Students
    with tab1:
        # Connect to database
        conn = get_db_connection()
        
        # Get all students with their credentials
        students = conn.execute("""
            SELECT s.id, s.name, s.dept, s.semester, s.photo, s.email, s.phone, s.admission_date,
                   s.student_id, u.username, u.password
            FROM students s
            LEFT JOIN users u ON s.id = u.user_id AND u.role = 'student'
            ORDER BY s.id
        """).fetchall()
        
        if students:
            # Convert to a list of dictionaries for proper display
            student_list = []
            for row in students:
                student_list.append({
                    "ID": row["id"],
                    "StudentID": row["student_id"] or "N/A",
                    "Name": row["name"],
                    "Department": row["dept"],
                    "Semester": row["semester"],
                    "Email": row["email"] or "",
                    "Photo": row["photo"],
                    "Username": row["username"] or "",
                    "Password": row["password"] or ""
                })
            
            # Add a search filter
            search = st.text_input("🔍 Search by name or ID", "")
            
            # Create a more compact table view
            st.markdown("""
            <style>
            .student-table {
                margin-bottom: 10px;
            }
            .student-row {
                display: flex;
                align-items: center;
                padding: 8px 0;
                border-bottom: 1px solid rgba(100, 100, 100, 0.2);
            }
            .profile-pic-container {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                overflow: hidden;
                margin-right: 10px;
            }
            .profile-pic {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Table headers
            headers = st.columns([0.8, 1.2, 1.8, 1.5, 0.8, 1.2])
            headers[0].write("**Photo**")
            headers[1].write("**Student ID**")
            headers[2].write("**Name**")
            headers[3].write("**Department**")
            headers[4].write("**Semester**")
            headers[5].write("**Actions**")
            
            st.markdown("---")
            
            # Filter students based on search
            filtered_students = student_list
            if search:
                search = search.lower()
                filtered_students = [s for s in student_list if search in s['Name'].lower() or search in s['StudentID'].lower()]
            
            if not filtered_students:
                st.info("No students found matching your search criteria.")
            
            # Display each student as a row
            for student in filtered_students:
                row = st.container()
                with row:
                    cols = st.columns([0.8, 1.2, 1.8, 1.5, 0.8, 1.2])
                    
                    # Display profile photo as circular
                    with cols[0]:
                        if student['Photo'] and os.path.exists(student['Photo']):
                            try:
                                img = Image.open(student['Photo'])
                                st.markdown(
                                    f"""
                                    <div class="profile-pic-container">
                                        <img src="data:image/png;base64,{image_to_base64(img)}" class="profile-pic">
                                    </div>
                                    """, 
                                    unsafe_allow_html=True
                                )
                            except:
                                st.image("https://via.placeholder.com/40x40?text=?", width=40)
                        else:
                            st.image("https://via.placeholder.com/40x40?text=?", width=40)
                    
                    # Student ID column
                    cols[1].write(f"**{student['StudentID']}**")
                    
                    # Name column
                    cols[2].write(f"{student['Name']}")
                    
                    cols[3].write(f"{student['Department']}")
                    cols[4].write(f"{student['Semester']}")
                    
                    # Action buttons
                    with cols[5]:
                        action_cols = st.columns(3)
                        if action_cols[0].button("👁️", key=f"view_{student['ID']}", help="View details"):
                            st.session_state.selected_student = student['ID']
                        
                        if action_cols[1].button("🔑", key=f"cred_{student['ID']}", help="View credentials"):
                            st.session_state.show_credentials = student['ID']
                        
                        if action_cols[2].button("🗑️", key=f"del_{student['ID']}", help="Delete student"):
                            st.session_state.delete_student = student['ID']
            
            # Initialize session state variables if not exist
            if 'selected_student' not in st.session_state:
                st.session_state.selected_student = None
                
            if 'show_credentials' not in st.session_state:
                st.session_state.show_credentials = None
                
            if 'delete_student' not in st.session_state:
                st.session_state.delete_student = None
            
            # Show student details
            if st.session_state.selected_student:
                student_data = next((s for s in students if s['id'] == st.session_state.selected_student), None)
                if student_data:
                    st.markdown("---")
                    st.subheader(f"{student_data['name']}")
                    
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        # Display student photo if available
                        if student_data['photo'] and os.path.exists(student_data['photo']):
                            try:
                                img = Image.open(student_data['photo'])
                                st.image(img, width=200)
                            except:
                                st.image("https://via.placeholder.com/200x200?text=No+Photo", width=200)
                        else:
                            st.image("https://via.placeholder.com/200x200?text=No+Photo", width=200)
                    
                    with col2:
                        st.write(f"**Student ID:** {student_data['student_id'] or 'Not assigned'}")
                        st.write(f"**Department:** {student_data['dept']}")
                        st.write(f"**Semester:** {student_data['semester']}")
                        st.write(f"**Email:** {student_data['email'] or 'Not provided'}")
                        st.write(f"**Phone:** {student_data['phone'] or 'Not provided'}")
                        st.write(f"**Admission Date:** {student_data['admission_date'] or 'Not provided'}")
                        
                        # Get enrolled courses
                        courses = conn.execute("""
                            SELECT c.code, c.title, e.semester
                            FROM enrollments e
                            JOIN courses c ON e.course_id = c.id
                            WHERE e.student_id = ?
                            ORDER BY e.semester DESC, c.code
                        """, (student_data['id'],)).fetchall()
                        
                        if courses:
                            st.subheader("Enrolled Courses")
                            for course in courses:
                                st.write(f"• {course['code']} - {course['title']} ({course['semester']})")
                        else:
                            st.info("No enrolled courses")
                    
                    if st.button("Close", key="close_details"):
                        st.session_state.selected_student = None
                        st.rerun()
            
            # Show credentials popup
            if st.session_state.show_credentials:
                student_data = next((s for s in students if s['id'] == st.session_state.show_credentials), None)
                if student_data:
                    st.markdown("---")
                    with st.container(border=True):
                        st.subheader("Login Credentials")
                        st.write(f"**Student:** {student_data['name']}")
                        st.write(f"**Student ID:** {student_data['student_id'] or 'Not assigned'}")
                        st.write(f"**Username:** {student_data['username'] or 'Not set'}")
                        st.write(f"**Password:** {student_data['password'] or 'Not set'}")
                        
                        if st.button("Close", key="close_credentials"):
                            st.session_state.show_credentials = None
                            st.rerun()
            
            # Handle delete student
            if st.session_state.delete_student:
                student_data = next((s for s in students if s['id'] == st.session_state.delete_student), None)
                if student_data:
                    st.markdown("---")
                    with st.container(border=True):
                        st.warning(f"Are you sure you want to delete student: {student_data['name']}?")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("Yes, Delete", type="primary", key="confirm_delete"):
                                # Delete user account if exists
                                user = conn.execute(
                                    "SELECT id FROM users WHERE role = 'student' AND user_id = ?", 
                                    (student_data['id'],)
                                ).fetchone()
                                
                                if user:
                                    conn.execute("DELETE FROM users WHERE id = ?", (user['id'],))
                                
                                # Delete photo if exists
                                if student_data['photo'] and os.path.exists(student_data['photo']):
                                    try:
                                        os.remove(student_data['photo'])
                                    except:
                                        pass
                                
                                # Delete student record
                                conn.execute("DELETE FROM students WHERE id = ?", (student_data['id'],))
                                conn.commit()
                                
                                st.success(f"Student {student_data['name']} deleted successfully!")
                                st.session_state.delete_student = None
                                st.rerun()
                        
                        with col2:
                            if st.button("Cancel", key="cancel_delete"):
                                st.session_state.delete_student = None
                                st.rerun()
        else:
            st.info("No students found in the database")
        
        conn.close()
    
    # Tab 2: Add Student
    with tab2:
        with st.form("add_student_form"):
            st.subheader("Add New Student")
            
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Full Name*")
                dept = st.text_input("Department*")
                semester = st.number_input("Semester*", min_value=1, max_value=12, value=1)
                admission_date = st.date_input("Admission Date", datetime.now())
            
            with col2:
                email = st.text_input("Email")
                phone = st.text_input("Phone")
                address = st.text_area("Address")
                photo = st.file_uploader("Student Photo (Optional)", type=["jpg", "jpeg", "png"])
            
            # Generate student ID
            student_id = generate_student_id()
            st.info(f"Student ID will be: {student_id}")
            
            # Note about credential generation
            st.info("A username and password will be automatically generated for this student.")
            
            submitted = st.form_submit_button("Add Student", use_container_width=True)
            
            if submitted:
                if name and dept:
                    # Save photo if uploaded
                    photo_path = None
                    if photo:
                        # Create directory if it doesn't exist
                        os.makedirs("static/images", exist_ok=True)
                        
                        # Create filename with unique ID
                        filename = f"student_{uuid.uuid4()}.{photo.name.split('.')[-1]}"
                        photo_path = os.path.join("static", "images", filename)
                        
                        # Save image
                        with open(photo_path, "wb") as f:
                            f.write(photo.getbuffer())
                    
                    # Connect to database
                    conn = get_db_connection()
                    
                    # Insert new student
                    cursor = conn.cursor()
                    cursor.execute(
                        """INSERT INTO students 
                        (name, dept, semester, photo, email, phone, address, admission_date, student_id) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (name, dept, semester, photo_path, email, phone, address, 
                         admission_date.strftime("%Y-%m-%d"), student_id)
                    )
                    
                    # Get the ID of the inserted student
                    student_id_db = cursor.lastrowid
                    
                    # Generate username and password
                    username, password = generate_credentials('student', name)
                    
                    # Create user account
                    cursor.execute(
                        "INSERT INTO users (username, password, role, user_id) VALUES (?, ?, ?, ?)",
                        (username, password, 'student', student_id_db)
                    )
                    
                    conn.commit()
                    
                    # Display success message with credentials
                    st.success(f"Student {name} added successfully with ID: {student_id}")
                    st.success(f"Generated Credentials - Username: {username} | Password: {password}")
                    st.warning("Please note down these credentials as they won't be shown again.")
                    
                    conn.close()
                else:
                    st.error("Name and Department are required fields")
    
    # Tab 3: Edit/Delete Student
    with tab3:
        # Connect to database
        conn = get_db_connection()
        
        # Get all students
        students = conn.execute(
            "SELECT * FROM students ORDER BY id"
        ).fetchall()
        
        if students:
            # Select student to edit
            selected_student_id = st.selectbox("Select a student to edit", 
                                            [s['id'] for s in students],
                                            format_func=lambda x: next((f"{s['student_id']} - {s['name']}" for s in students if s['id'] == x), ""),
                                            key="edit_student_select")
            
            if selected_student_id:
                student = next((s for s in students if s['id'] == selected_student_id), None)
                
                if student:
                    with st.form("edit_student_form"):
                        st.subheader(f"Edit Student: {student['name']}")
                        st.write(f"**Student ID:** {student['student_id']}")
                        
                        col1, col2 = st.columns(2)
                        
                        # Parse the admission date string to a datetime object if it exists
                        try:
                            if student['admission_date']:
                                admission_date_obj = datetime.strptime(student['admission_date'], "%Y-%m-%d")
                            else:
                                admission_date_obj = datetime.now()
                        except (ValueError, TypeError):
                            admission_date_obj = datetime.now()
                        
                        with col1:
                            name = st.text_input("Full Name*", value=student['name'])
                            dept = st.text_input("Department*", value=student['dept'])
                            semester = st.number_input("Semester*", min_value=1, max_value=12, value=student['semester'])
                            admission_date = st.date_input("Admission Date", admission_date_obj)
                        
                        with col2:
                            email = st.text_input("Email", value=student['email'] if student['email'] else "")
                            phone = st.text_input("Phone", value=student['phone'] if student['phone'] else "")
                            address = st.text_area("Address", value=student['address'] if student['address'] else "")
                            photo = st.file_uploader("New Student Photo (Optional)", type=["jpg", "jpeg", "png"])
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            update = st.form_submit_button("Update Student", use_container_width=True)
                        with col2:
                            delete = st.form_submit_button("Delete Student", use_container_width=True, type="primary")
                        
                        if update:
                            if name and dept:
                                # Process photo if a new one is uploaded
                                photo_path = student['photo']
                                if photo:
                                    # Delete old photo if exists
                                    if student['photo'] and os.path.exists(student['photo']):
                                        try:
                                            os.remove(student['photo'])
                                        except:
                                            pass
                                    
                                    # Create directory if it doesn't exist
                                    os.makedirs("static/images", exist_ok=True)
                                    
                                    # Create filename with unique ID
                                    filename = f"student_{uuid.uuid4()}.{photo.name.split('.')[-1]}"
                                    photo_path = os.path.join("static", "images", filename)
                                    
                                    # Save image
                                    with open(photo_path, "wb") as f:
                                        f.write(photo.getbuffer())
                                
                                # Update student record
                                conn.execute(
                                    """UPDATE students 
                                    SET name = ?, dept = ?, semester = ?, photo = ?, 
                                    email = ?, phone = ?, address = ?, admission_date = ? 
                                    WHERE id = ?""",
                                    (name, dept, semester, photo_path, email, phone, address, 
                                     admission_date.strftime("%Y-%m-%d"), student['id'])
                                )
                                conn.commit()
                                
                                st.success(f"Student {name} updated successfully!")
                                st.rerun()
                            else:
                                st.error("Name and Department are required fields")
                        
                        if delete:
                            # Check if this student has a user account
                            user = conn.execute(
                                "SELECT id FROM users WHERE role = 'student' AND user_id = ?", 
                                (student['id'],)
                            ).fetchone()
                            
                            # Delete user account if exists
                            if user:
                                conn.execute("DELETE FROM users WHERE id = ?", (user['id'],))
                            
                            # Delete photo if exists
                            if student['photo'] and os.path.exists(student['photo']):
                                try:
                                    os.remove(student['photo'])
                                except:
                                    pass
                            
                            # Delete student record
                            conn.execute("DELETE FROM students WHERE id = ?", (student['id'],))
                            conn.commit()
                            
                            st.success(f"Student {student['name']} deleted successfully!")
                            st.rerun()
        else:
            st.info("No students found in the database")
        
        conn.close()
    
    # Tab 4: Credentials Management
    with tab4:
        st.subheader("Student Credentials Management")
        
        # Connect to database
        conn = get_db_connection()
        
        # Get all student users
        users = conn.execute("""
            SELECT u.id, u.username, u.password, u.user_id, u.last_login, s.name, s.student_id
            FROM users u
            JOIN students s ON u.user_id = s.id
            WHERE u.role = 'student'
            ORDER BY s.name
        """).fetchall()
        
        if users:
            # Convert to DataFrame for display
            user_data = []
            for user in users:
                user_data.append({
                    "ID": user['id'],
                    "Student ID": user['student_id'] or "N/A",
                    "Student Name": user['name'],
                    "Username": user['username'],
                    "Password": user['password'],
                    "Last Login": user['last_login'] or "Never",
                })
            
            df = pd.DataFrame(user_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Select user to manage
            selected_user_id = st.selectbox("Select a user to manage credentials", 
                                         [u['id'] for u in users],
                                         format_func=lambda x: next((f"{u['student_id']} - {u['name']}" for u in users if u['id'] == x), ""))
            
            if selected_user_id:
                user = next((u for u in users if u['id'] == selected_user_id), None)
                
                if user:
                    st.write(f"Managing credentials for **{user['name']}** (ID: {user['student_id']})")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Reset password
                        if st.button("Reset Password", use_container_width=True):
                            # Generate new password
                            import random
                            import string
                            new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                            
                            # Update password in database
                            conn.execute(
                                "UPDATE users SET password = ? WHERE id = ?",
                                (new_password, user['id'])
                            )
                            conn.commit()
                            
                            st.success(f"Password reset successful! New password: {new_password}")
                    
                    with col2:
                        # Reset username
                        if st.button("Reset Username", use_container_width=True):
                            # Get student name
                            student = conn.execute(
                                "SELECT name FROM students WHERE id = ?", 
                                (user['user_id'],)
                            ).fetchone()
                            
                            if student:
                                # Generate new username
                                new_username, _ = generate_credentials('student', student['name'])
                                
                                # Update username in database
                                conn.execute(
                                    "UPDATE users SET username = ? WHERE id = ?",
                                    (new_username, user['id'])
                                )
                                conn.commit()
                                
                                st.success(f"Username reset successful! New username: {new_username}")
        else:
            st.info("No student accounts found in the database")
        
        conn.close()

def image_to_base64(img):
    """Convert PIL Image to base64 string"""
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return img_str 