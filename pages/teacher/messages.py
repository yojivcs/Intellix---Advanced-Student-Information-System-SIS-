import streamlit as st
import pandas as pd
from datetime import datetime
import json

from components.header import render_page_title
from database.schema import get_db_connection

def show():
    """Display the messaging system for teachers"""
    render_page_title("💬", "Messages")
    
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
    
    # Create tabs for inbox, sent, and compose
    tab1, tab2, tab3, tab4 = st.tabs(["📥 Inbox", "📤 Sent", "✏️ Compose", "📋 Templates"])
    
    # Inbox tab
    with tab1:
        st.subheader("Inbox")
        
        # Fetch received messages
        messages = conn.execute("""
            SELECT m.id, m.subject, m.message, m.sent_at, m.is_read, m.sender_role,
                   CASE 
                       WHEN m.sender_role = 'admin' THEN 'Administrator'
                       WHEN m.sender_role = 'teacher' AND t.id IS NOT NULL THEN t.name
                       WHEN m.sender_role = 'student' AND s.id IS NOT NULL THEN s.name
                       ELSE 'Unknown'
                   END as sender_name,
                   c.code as course_code
            FROM messages m
            LEFT JOIN teachers t ON m.sender_id = t.id AND m.sender_role = 'teacher'
            LEFT JOIN students s ON m.sender_id = s.id AND m.sender_role = 'student'
            LEFT JOIN courses c ON m.course_id = c.id
            WHERE m.recipient_id = ? AND m.recipient_role = 'teacher'
            ORDER BY m.sent_at DESC
        """, (teacher_id,)).fetchall()
        
        if not messages:
            st.info("No messages in your inbox.")
        else:
            # Convert to DataFrame for better display
            messages_data = []
            for msg in messages:
                status = "🔵 New" if not msg['is_read'] else "Read"
                course_info = f" ({msg['course_code']})" if msg['course_code'] else ""
                
                messages_data.append({
                    "ID": msg['id'],
                    "From": f"{msg['sender_name']}{course_info}",
                    "Subject": msg['subject'],
                    "Date": msg['sent_at'],
                    "Status": status
                })
            
            df_messages = pd.DataFrame(messages_data)
            
            # Color the Status column
            def color_status(val):
                if '🔵' in val:
                    return 'color: blue; font-weight: bold'
                else:
                    return ''
            
            # Display the styled dataframe with selection
            selection = st.dataframe(
                df_messages.style.applymap(color_status, subset=['Status']),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID": st.column_config.NumberColumn(format="%d", width="small"),
                    "From": st.column_config.TextColumn(width="medium"),
                    "Subject": st.column_config.TextColumn(width="large"),
                    "Date": st.column_config.DatetimeColumn(format="MMM DD, YYYY - hh:mm a", width="medium"),
                    "Status": st.column_config.TextColumn(width="small")
                },
                height=300
            )
            
            # Show selected message
            st.subheader("Message Details")
            selected_msg_id = st.selectbox("Select a message to view", 
                                     options=[msg['id'] for msg in messages],
                                     format_func=lambda x: next((msg['subject'] for msg in messages if msg['id'] == x), ""))
            
            if selected_msg_id:
                selected_msg = next((msg for msg in messages if msg['id'] == selected_msg_id), None)
                
                if selected_msg:
                    # Mark as read if not already
                    if not selected_msg['is_read']:
                        conn.execute(
                            "UPDATE messages SET is_read = 1, read_at = datetime('now') WHERE id = ?",
                            (selected_msg_id,)
                        )
                        conn.commit()
                    
                    # Display message details
                    st.markdown(f"**From:** {selected_msg['sender_name']}")
                    st.markdown(f"**Subject:** {selected_msg['subject']}")
                    st.markdown(f"**Date:** {selected_msg['sent_at']}")
                    
                    # Display the message in a text box
                    st.text_area("Message", selected_msg['message'], height=200, disabled=True)
                    
                    # Reply button
                    if st.button("Reply"):
                        # Store reply info in session state
                        st.session_state.reply_to = {
                            'id': selected_msg_id,
                            'recipient_id': selected_msg['sender_id'],
                            'recipient_role': selected_msg['sender_role'],
                            'recipient_name': selected_msg['sender_name'],
                            'subject': f"Re: {selected_msg['subject']}",
                            'course_id': selected_msg.get('course_id')
                        }
                        # Switch to compose tab
                        st.session_state.active_tab = "compose"
                        st.rerun()
    
    # Sent tab
    with tab2:
        st.subheader("Sent Messages")
        
        # Fetch sent messages
        sent_messages = conn.execute("""
            SELECT m.id, m.subject, m.message, m.sent_at, m.is_read, m.recipient_role,
                   CASE 
                       WHEN m.recipient_role = 'admin' THEN 'Administrator'
                       WHEN m.recipient_role = 'teacher' AND t.id IS NOT NULL THEN t.name
                       WHEN m.recipient_role = 'student' AND s.id IS NOT NULL THEN s.name
                       ELSE 'Unknown'
                   END as recipient_name,
                   c.code as course_code
            FROM messages m
            LEFT JOIN teachers t ON m.recipient_id = t.id AND m.recipient_role = 'teacher'
            LEFT JOIN students s ON m.recipient_id = s.id AND m.recipient_role = 'student'
            LEFT JOIN courses c ON m.course_id = c.id
            WHERE m.sender_id = ? AND m.sender_role = 'teacher'
            ORDER BY m.sent_at DESC
        """, (teacher_id,)).fetchall()
        
        if not sent_messages:
            st.info("No sent messages.")
        else:
            # Convert to DataFrame for better display
            sent_data = []
            for msg in sent_messages:
                status = "Read" if msg['is_read'] else "Unread"
                course_info = f" ({msg['course_code']})" if msg['course_code'] else ""
                
                sent_data.append({
                    "ID": msg['id'],
                    "To": f"{msg['recipient_name']}{course_info}",
                    "Subject": msg['subject'],
                    "Date": msg['sent_at'],
                    "Status": status
                })
            
            df_sent = pd.DataFrame(sent_data)
            
            # Display the dataframe with selection
            st.dataframe(
                df_sent,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID": st.column_config.NumberColumn(format="%d", width="small"),
                    "To": st.column_config.TextColumn(width="medium"),
                    "Subject": st.column_config.TextColumn(width="large"),
                    "Date": st.column_config.DatetimeColumn(format="MMM DD, YYYY - hh:mm a", width="medium"),
                    "Status": st.column_config.TextColumn(width="small")
                },
                height=300
            )
            
            # Show selected message
            st.subheader("Message Details")
            selected_sent_id = st.selectbox("Select a sent message to view", 
                                     options=[msg['id'] for msg in sent_messages],
                                     format_func=lambda x: next((msg['subject'] for msg in sent_messages if msg['id'] == x), ""))
            
            if selected_sent_id:
                selected_sent = next((msg for msg in sent_messages if msg['id'] == selected_sent_id), None)
                
                if selected_sent:
                    # Display message details
                    st.markdown(f"**To:** {selected_sent['recipient_name']}")
                    st.markdown(f"**Subject:** {selected_sent['subject']}")
                    st.markdown(f"**Date:** {selected_sent['sent_at']}")
                    st.markdown(f"**Status:** {'Read' if selected_sent['is_read'] else 'Unread'}")
                    
                    # Display the message in a text box
                    st.text_area("Message", selected_sent['message'], height=200, disabled=True)
    
    # Compose tab
    with tab3:
        st.subheader("Compose New Message")
        
        # Check if replying to a message
        reply_to = st.session_state.get('reply_to', None)
        
        # Get teacher's courses
        teacher_courses = conn.execute("""
            SELECT c.id, c.code, c.title
            FROM courses c
            JOIN teaching t ON c.id = t.course_id
            WHERE t.teacher_id = ? AND t.semester = ?
        """, (teacher_id, session_name)).fetchall()
        
        course_options = {f"{c['code']} - {c['title']}": c['id'] for c in teacher_courses}
        course_options["No specific course"] = None
        
        # Select message type
        message_type = st.radio(
            "Send message to:",
            ["Student(s)", "Teacher(s)", "Administrator"],
            horizontal=True
        )
        
        if message_type == "Student(s)":
            st.markdown("### Select Students")
            
            # Get all students for this teacher's courses
            if course_options:
                selected_course_name = st.selectbox(
                    "Select a course:",
                    options=list(course_options.keys())
                )
                
                selected_course_id = course_options[selected_course_name]
                
                if selected_course_id:
                    # Get students for this course
                    students = conn.execute("""
                        SELECT s.id, s.name, s.student_id as roll_no
                        FROM students s
                        JOIN enrollments e ON s.id = e.student_id
                        WHERE e.course_id = ? AND e.semester = ?
                        ORDER BY s.name
                    """, (selected_course_id, session_name)).fetchall()
                    
                    if students:
                        student_options = {f"{s['name']} ({s['roll_no']})": s['id'] for s in students}
                        
                        # Option to select all students
                        bulk_message = st.checkbox("Send to all students in this course")
                        
                        if bulk_message:
                            selected_students = [s['id'] for s in students]
                            st.info(f"Message will be sent to all {len(students)} students in this course.")
                        else:
                            # Multi-select for students
                            selected_student_names = st.multiselect(
                                "Select students to message:",
                                options=list(student_options.keys())
                            )
                            
                            selected_students = [student_options[name] for name in selected_student_names]
                        
                        if selected_students:
                            # Show compose form
                            subject = st.text_input("Subject", key="subject_student")
                            message = st.text_area("Message", height=200, key="message_student")
                            
                            if st.button("Send", key="send_student"):
                                if subject and message:
                                    # Insert message for each student
                                    for student_id in selected_students:
                                        conn.execute("""
                                            INSERT INTO messages 
                                            (sender_id, sender_role, recipient_id, recipient_role, course_id, subject, message)
                                            VALUES (?, ?, ?, ?, ?, ?, ?)
                                        """, (teacher_id, 'teacher', student_id, 'student', selected_course_id, subject, message))
                                    
                                    conn.commit()
                                    st.success(f"Message sent to {len(selected_students)} student(s)!")
                                    
                                    # Clear form using rerun with a flag instead of direct session state manipulation
                                    st.session_state.message_sent = True
                                    st.rerun()
                                else:
                                    st.warning("Please enter both subject and message.")
                        else:
                            st.info("Please select at least one student.")
                    else:
                        st.info("No students enrolled in this course.")
                else:
                    st.info("Please select a course.")
            else:
                st.warning("You don't have any assigned courses in the current session.")
        
        elif message_type == "Teacher(s)":
            st.markdown("### Select Teachers")
            
            # Get all teachers
            teachers = conn.execute("""
                SELECT id, name, dept
                FROM teachers
                WHERE id != ?
                ORDER BY name
            """, (teacher_id,)).fetchall()
            
            if teachers:
                teacher_options = {f"{t['name']} ({t['dept']})": t['id'] for t in teachers}
                
                # Multi-select for teachers
                selected_teacher_names = st.multiselect(
                    "Select teachers to message:",
                    options=list(teacher_options.keys())
                )
                
                selected_teacher_ids = [teacher_options[name] for name in selected_teacher_names]
                
                if selected_teacher_ids:
                    # Select course (optional)
                    include_course = st.checkbox("Include course reference")
                    
                    selected_course_id = None
                    if include_course and course_options:
                        selected_course_name = st.selectbox(
                            "Related to course:",
                            options=list(course_options.keys())
                        )
                        
                        selected_course_id = course_options[selected_course_name]
                    
                    # Show compose form
                    subject = st.text_input("Subject", key="subject_teacher")
                    message = st.text_area("Message", height=200, key="message_teacher")
                    
                    if st.button("Send", key="send_teacher"):
                        if subject and message:
                            # Insert message for each teacher
                            for rcpt_teacher_id in selected_teacher_ids:
                                conn.execute("""
                                    INSERT INTO messages 
                                    (sender_id, sender_role, recipient_id, recipient_role, course_id, subject, message)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (teacher_id, 'teacher', rcpt_teacher_id, 'teacher', selected_course_id, subject, message))
                            
                            conn.commit()
                            st.success(f"Message sent to {len(selected_teacher_ids)} teacher(s)!")
                            
                            # Clear form using rerun with a flag instead of direct session state manipulation
                            st.session_state.message_sent = True
                            st.rerun()
                        else:
                            st.warning("Please enter both subject and message.")
                else:
                    st.info("Please select at least one teacher.")
            else:
                st.info("No other teachers found in the system.")
        
        elif message_type == "Administrator":
            st.markdown("### Message to Administrator")
            
            # Select course (optional)
            include_course = st.checkbox("Include course reference")
            
            selected_course_id = None
            if include_course and course_options:
                selected_course_name = st.selectbox(
                    "Related to course:",
                    options=list(course_options.keys())
                )
                
                selected_course_id = course_options[selected_course_name]
            
            # Show compose form
            subject = st.text_input("Subject", key="subject_admin")
            message = st.text_area("Message", height=200, key="message_admin")
            
            if st.button("Send", key="send_admin"):
                if subject and message:
                    # Insert message to admin (admin ID is 0)
                    conn.execute("""
                        INSERT INTO messages 
                        (sender_id, sender_role, recipient_id, recipient_role, course_id, subject, message)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (teacher_id, 'teacher', 0, 'admin', selected_course_id, subject, message))
                    
                    conn.commit()
                    st.success("Message sent to administrator!")
                    
                    # Clear form using rerun with a flag instead of direct session state manipulation
                    st.session_state.message_sent = True
                    st.rerun()
                else:
                    st.warning("Please enter both subject and message.")
    
    # Templates tab
    with tab4:
        st.subheader("Message Templates")
        
        # Get available templates
        templates = conn.execute("""
            SELECT id, title, template 
            FROM message_templates
            WHERE role = 'teacher'
            ORDER BY title
        """).fetchall()
        
        if templates:
            # Create expanders for each template to allow viewing and using
            for template in templates:
                with st.expander(template['title']):
                    st.text_area(f"Template: {template['title']}", 
                                template['template'], 
                                height=200, 
                                disabled=True,
                                key=f"template_{template['id']}")
                    
                    if st.button("Use this template", key=f"use_template_{template['id']}"):
                        # Store template in session state
                        st.session_state.selected_template = template['template']
                        st.session_state.selected_template_title = template['title']
                        
                        # Switch to compose tab
                        st.session_state.active_tab = "compose"
                        st.rerun()
            
            # Option to create a new template
            st.markdown("### Create New Template")
            
            template_title = st.text_input("Template Title")
            template_content = st.text_area("Template Content", height=200)
            
            if st.button("Save Template"):
                if template_title and template_content:
                    # Insert new template
                    conn.execute("""
                        INSERT INTO message_templates 
                        (title, template, created_by, role)
                        VALUES (?, ?, ?, ?)
                    """, (template_title, template_content, teacher_id, 'teacher'))
                    
                    conn.commit()
                    st.success(f"Template '{template_title}' saved successfully!")
                    st.rerun()
                else:
                    st.warning("Please enter both title and content for the template.")
        else:
            st.info("No message templates available. Create your first template below.")
            
            template_title = st.text_input("Template Title")
            template_content = st.text_area("Template Content", height=200)
            
            if st.button("Save Template"):
                if template_title and template_content:
                    # Insert new template
                    conn.execute("""
                        INSERT INTO message_templates 
                        (title, template, created_by, role)
                        VALUES (?, ?, ?, ?)
                    """, (template_title, template_content, teacher_id, 'teacher'))
                    
                    conn.commit()
                    st.success(f"Template '{template_title}' saved successfully!")
                    st.rerun()
                else:
                    st.warning("Please enter both title and content for the template.")
    
    # Close the database connection
    conn.close() 