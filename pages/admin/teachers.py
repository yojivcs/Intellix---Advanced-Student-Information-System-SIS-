import streamlit as st
import pandas as pd
import os
import uuid
import base64
import io
from PIL import Image
from database.schema import get_db_connection
from components.header import render_page_title
from utils.auth import generate_credentials
from datetime import datetime

def image_to_base64(img):
    """Convert PIL Image to base64 string"""
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return img_str

def show():
    """Display the teacher management page"""
    render_page_title("👩‍🏫", "Teacher Management")
    
    # Create tabs for different operations
    tab1, tab2, tab3, tab4 = st.tabs(["View Teachers", "Add Teacher", "Edit/Delete Teacher", "Credentials Management"])
    
    # Tab 1: View Teachers
    with tab1:
        # Connect to database
        conn = get_db_connection()
        
        # Get all teachers with their credentials
        teachers = conn.execute("""
            SELECT t.id, t.name, t.dept, t.photo, t.email, t.phone, t.join_date,
                   u.username, u.password
            FROM teachers t
            LEFT JOIN users u ON t.id = u.user_id AND u.role = 'teacher'
            ORDER BY t.id
        """).fetchall()
        
        if teachers:
            # Convert to a list of dictionaries for proper display
            teacher_list = []
            for row in teachers:
                teacher_list.append({
                    "ID": row["id"],
                    "Name": row["name"],
                    "Department": row["dept"],
                    "Photo": row["photo"],
                    "Email": row["email"] or "",
                    "Phone": row["phone"] or "",
                    "JoinDate": row["join_date"],
                    "Username": row["username"] or "",
                    "Password": row["password"] or ""
                })
            
            # Add a search filter
            search = st.text_input("🔍 Search by name or department", "")
            
            # Create a more compact table view
            st.markdown("""
            <style>
            .teacher-table {
                margin-bottom: 10px;
            }
            .teacher-row {
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
            headers = st.columns([0.8, 2.0, 1.8, 1.0, 1.2])
            headers[0].write("**Photo**")
            headers[1].write("**Name**")
            headers[2].write("**Department**")
            headers[3].write("**Join Date**")
            headers[4].write("**Actions**")
            
            st.markdown("---")
            
            # Filter teachers based on search
            filtered_teachers = teacher_list
            if search:
                search = search.lower()
                filtered_teachers = [t for t in teacher_list if search in t['Name'].lower() or search in t['Department'].lower()]
            
            if not filtered_teachers:
                st.info("No teachers found matching your search criteria.")
            
            # Display each teacher as a row
            for teacher in filtered_teachers:
                row = st.container()
                with row:
                    cols = st.columns([0.8, 2.0, 1.8, 1.0, 1.2])
                    
                    # Display profile photo as circular
                    with cols[0]:
                        if teacher['Photo'] and os.path.exists(teacher['Photo']):
                            try:
                                img = Image.open(teacher['Photo'])
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
                    
                    cols[1].write(f"**{teacher['Name']}**")
                    cols[2].write(f"{teacher['Department']}")
                    cols[3].write(f"{teacher['JoinDate'] or 'N/A'}")
                    
                    # Action buttons
                    with cols[4]:
                        action_cols = st.columns(3)
                        if action_cols[0].button("👁️", key=f"view_{teacher['ID']}", help="View details"):
                            st.session_state.selected_teacher = teacher['ID']
                        
                        if action_cols[1].button("🔑", key=f"cred_{teacher['ID']}", help="View credentials"):
                            st.session_state.show_credentials = teacher['ID']
                        
                        if action_cols[2].button("🗑️", key=f"del_{teacher['ID']}", help="Delete teacher"):
                            st.session_state.delete_teacher = teacher['ID']
            
            # Initialize session state variables if not exist
            if 'selected_teacher' not in st.session_state:
                st.session_state.selected_teacher = None
                
            if 'show_credentials' not in st.session_state:
                st.session_state.show_credentials = None
                
            if 'delete_teacher' not in st.session_state:
                st.session_state.delete_teacher = None
            
            # Show teacher details
            if st.session_state.selected_teacher:
                teacher_data = next((t for t in teachers if t['id'] == st.session_state.selected_teacher), None)
                if teacher_data:
                    st.markdown("---")
                    st.subheader(f"{teacher_data['name']}")
                    
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        # Display teacher photo if available
                        if teacher_data['photo'] and os.path.exists(teacher_data['photo']):
                            try:
                                img = Image.open(teacher_data['photo'])
                                st.image(img, width=200)
                            except:
                                st.image("https://via.placeholder.com/200x200?text=No+Photo", width=200)
                        else:
                            st.image("https://via.placeholder.com/200x200?text=No+Photo", width=200)
                    
                    with col2:
                        st.write(f"**Department:** {teacher_data['dept']}")
                        st.write(f"**Email:** {teacher_data['email'] or 'Not provided'}")
                        st.write(f"**Phone:** {teacher_data['phone'] or 'Not provided'}")
                        st.write(f"**Join Date:** {teacher_data['join_date'] or 'Not provided'}")
                        
                        # Get assigned courses
                        courses = conn.execute("""
                            SELECT c.code, c.title, t.semester
                            FROM teaching t
                            JOIN courses c ON t.course_id = c.id
                            WHERE t.teacher_id = ?
                            ORDER BY t.semester DESC, c.code
                        """, (teacher_data['id'],)).fetchall()
                        
                        if courses:
                            st.subheader("Assigned Courses")
                            for course in courses:
                                st.write(f"• {course['code']} - {course['title']} ({course['semester']})")
                        else:
                            st.info("No assigned courses")
                    
                    if st.button("Close", key="close_details"):
                        st.session_state.selected_teacher = None
                        st.rerun()
            
            # Show credentials popup
            if st.session_state.show_credentials:
                teacher_data = next((t for t in teachers if t['id'] == st.session_state.show_credentials), None)
                if teacher_data:
                    st.markdown("---")
                    with st.container(border=True):
                        st.subheader("Login Credentials")
                        st.write(f"**Teacher:** {teacher_data['name']}")
                        st.write(f"**Username:** {teacher_data['username'] or 'Not set'}")
                        st.write(f"**Password:** {teacher_data['password'] or 'Not set'}")
                        
                        if st.button("Close", key="close_credentials"):
                            st.session_state.show_credentials = None
                            st.rerun()
            
            # Handle delete teacher
            if st.session_state.delete_teacher:
                teacher_data = next((t for t in teachers if t['id'] == st.session_state.delete_teacher), None)
                if teacher_data:
                    st.markdown("---")
                    with st.container(border=True):
                        st.warning(f"Are you sure you want to delete teacher: {teacher_data['name']}?")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("Yes, Delete", type="primary", key="confirm_delete"):
                                # Delete user account if exists
                                user = conn.execute(
                                    "SELECT id FROM users WHERE role = 'teacher' AND user_id = ?", 
                                    (teacher_data['id'],)
                                ).fetchone()
                                
                                if user:
                                    conn.execute("DELETE FROM users WHERE id = ?", (user['id'],))
                                
                                # Delete photo if exists
                                if teacher_data['photo'] and os.path.exists(teacher_data['photo']):
                                    try:
                                        os.remove(teacher_data['photo'])
                                    except:
                                        pass
                                
                                # Delete teacher record
                                conn.execute("DELETE FROM teachers WHERE id = ?", (teacher_data['id'],))
                                conn.commit()
                                
                                st.success(f"Teacher {teacher_data['name']} deleted successfully!")
                                st.session_state.delete_teacher = None
                                st.rerun()
                        
                        with col2:
                            if st.button("Cancel", key="cancel_delete"):
                                st.session_state.delete_teacher = None
                                st.rerun()
        else:
            st.info("No teachers found in the database")
        
        conn.close()
    
    # Tab 2: Add Teacher
    with tab2:
        with st.form("add_teacher_form"):
            st.subheader("Add New Teacher")
            
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Full Name*")
                dept = st.text_input("Department*")
                join_date = st.date_input("Join Date", datetime.now())
            
            with col2:
                email = st.text_input("Email")
                phone = st.text_input("Phone")
                address = st.text_area("Address")
                photo = st.file_uploader("Teacher Photo (Optional)", type=["jpg", "jpeg", "png"])
            
            # Note about credential generation
            st.info("A username and password will be automatically generated for this teacher.")
            
            submitted = st.form_submit_button("Add Teacher", use_container_width=True)
            
            if submitted:
                if name and dept:
                    # Save photo if uploaded
                    photo_path = None
                    if photo:
                        # Create directory if it doesn't exist
                        os.makedirs("static/images", exist_ok=True)
                        
                        # Create filename with unique ID
                        filename = f"teacher_{uuid.uuid4()}.{photo.name.split('.')[-1]}"
                        photo_path = os.path.join("static", "images", filename)
                        
                        # Save image
                        with open(photo_path, "wb") as f:
                            f.write(photo.getbuffer())
                    
                    # Connect to database
                    conn = get_db_connection()
                    
                    # Insert new teacher
                    cursor = conn.cursor()
                    cursor.execute(
                        """INSERT INTO teachers 
                        (name, dept, photo, email, phone, address, join_date) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (name, dept, photo_path, email, phone, address, join_date.strftime("%Y-%m-%d"))
                    )
                    
                    # Get the ID of the inserted teacher
                    teacher_id = cursor.lastrowid
                    
                    # Generate username and password
                    username, password = generate_credentials('teacher', name)
                    
                    # Create user account
                    cursor.execute(
                        "INSERT INTO users (username, password, role, user_id) VALUES (?, ?, ?, ?)",
                        (username, password, 'teacher', teacher_id)
                    )
                    
                    conn.commit()
                    
                    # Display success message with credentials
                    st.success(f"Teacher {name} added successfully!")
                    st.success(f"Generated Credentials - Username: {username} | Password: {password}")
                    st.warning("Please note down these credentials as they won't be shown again.")
                    
                    conn.close()
                else:
                    st.error("Name and Department are required fields")
    
    # Tab 3: Edit/Delete Teacher
    with tab3:
        # Connect to database
        conn = get_db_connection()
        
        # Get all teachers
        teachers = conn.execute(
            "SELECT * FROM teachers ORDER BY id"
        ).fetchall()
        
        if teachers:
            # Select teacher to edit
            selected_teacher_id = st.selectbox("Select a teacher to edit", 
                                            [t['id'] for t in teachers],
                                            format_func=lambda x: next((t['name'] for t in teachers if t['id'] == x), ""),
                                            key="edit_teacher_select")
            
            if selected_teacher_id:
                teacher = next((t for t in teachers if t['id'] == selected_teacher_id), None)
                
                if teacher:
                    with st.form("edit_teacher_form"):
                        st.subheader(f"Edit Teacher: {teacher['name']}")
                        
                        col1, col2 = st.columns(2)
                        
                        # Parse the join date string to a datetime object if it exists
                        try:
                            if teacher['join_date']:
                                join_date_obj = datetime.strptime(teacher['join_date'], "%Y-%m-%d")
                            else:
                                join_date_obj = datetime.now()
                        except (ValueError, TypeError):
                            join_date_obj = datetime.now()
                        
                        with col1:
                            name = st.text_input("Full Name*", value=teacher['name'])
                            dept = st.text_input("Department*", value=teacher['dept'])
                            join_date = st.date_input("Join Date", join_date_obj)
                        
                        with col2:
                            email = st.text_input("Email", value=teacher['email'] if teacher['email'] else "")
                            phone = st.text_input("Phone", value=teacher['phone'] if teacher['phone'] else "")
                            address = st.text_area("Address", value=teacher['address'] if teacher['address'] else "")
                            photo = st.file_uploader("New Teacher Photo (Optional)", type=["jpg", "jpeg", "png"])
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            update = st.form_submit_button("Update Teacher", use_container_width=True)
                        with col2:
                            delete = st.form_submit_button("Delete Teacher", use_container_width=True, type="primary")
                        
                        if update:
                            if name and dept:
                                # Process photo if a new one is uploaded
                                photo_path = teacher['photo']
                                if photo:
                                    # Delete old photo if exists
                                    if teacher['photo'] and os.path.exists(teacher['photo']):
                                        try:
                                            os.remove(teacher['photo'])
                                        except:
                                            pass
                                    
                                    # Create directory if it doesn't exist
                                    os.makedirs("static/images", exist_ok=True)
                                    
                                    # Create filename with unique ID
                                    filename = f"teacher_{uuid.uuid4()}.{photo.name.split('.')[-1]}"
                                    photo_path = os.path.join("static", "images", filename)
                                    
                                    # Save image
                                    with open(photo_path, "wb") as f:
                                        f.write(photo.getbuffer())
                                
                                # Update teacher record
                                conn.execute(
                                    """UPDATE teachers 
                                    SET name = ?, dept = ?, photo = ?, 
                                    email = ?, phone = ?, address = ?, join_date = ? 
                                    WHERE id = ?""",
                                    (name, dept, photo_path, email, phone, address, 
                                     join_date.strftime("%Y-%m-%d"), teacher['id'])
                                )
                                conn.commit()
                                
                                st.success(f"Teacher {name} updated successfully!")
                                st.rerun()
                            else:
                                st.error("Name and Department are required fields")
                        
                        if delete:
                            # Check if this teacher has a user account
                            user = conn.execute(
                                "SELECT id FROM users WHERE role = 'teacher' AND user_id = ?", 
                                (teacher['id'],)
                            ).fetchone()
                            
                            # Delete user account if exists
                            if user:
                                conn.execute("DELETE FROM users WHERE id = ?", (user['id'],))
                            
                            # Delete photo if exists
                            if teacher['photo'] and os.path.exists(teacher['photo']):
                                try:
                                    os.remove(teacher['photo'])
                                except:
                                    pass
                            
                            # Delete teacher record
                            conn.execute("DELETE FROM teachers WHERE id = ?", (teacher['id'],))
                            conn.commit()
                            
                            st.success(f"Teacher {teacher['name']} deleted successfully!")
                            st.rerun()
        else:
            st.info("No teachers found in the database")
        
        conn.close()
    
    # Tab 4: Credentials Management
    with tab4:
        st.subheader("Teacher Credentials Management")
        
        # Connect to database
        conn = get_db_connection()
        
        # Get all teacher users
        users = conn.execute("""
            SELECT u.id, u.username, u.user_id, u.last_login, t.name 
            FROM users u
            JOIN teachers t ON u.user_id = t.id
            WHERE u.role = 'teacher'
            ORDER BY t.name
        """).fetchall()
        
        if users:
            # Convert to DataFrame for display
            user_data = []
            for user in users:
                user_data.append({
                    "ID": user['id'],
                    "Teacher Name": user['name'],
                    "Username": user['username'],
                    "Last Login": user['last_login'] or "Never",
                })
            
            df = pd.DataFrame(user_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Select user to manage
            selected_user_id = st.selectbox("Select a user to manage credentials", 
                                         [u['id'] for u in users],
                                         format_func=lambda x: next((u['name'] for u in users if u['id'] == x), ""))
            
            if selected_user_id:
                user = next((u for u in users if u['id'] == selected_user_id), None)
                
                if user:
                    st.write(f"Managing credentials for **{user['name']}**")
                    
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
                            # Get teacher name
                            teacher = conn.execute(
                                "SELECT name FROM teachers WHERE id = ?", 
                                (user['user_id'],)
                            ).fetchone()
                            
                            if teacher:
                                # Generate new username
                                new_username, _ = generate_credentials('teacher', teacher['name'])
                                
                                # Update username in database
                                conn.execute(
                                    "UPDATE users SET username = ? WHERE id = ?",
                                    (new_username, user['id'])
                                )
                                conn.commit()
                                
                                st.success(f"Username reset successful! New username: {new_username}")
        else:
            st.info("No teacher accounts found in the database")
        
        conn.close() 