import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from components.header import render_page_title
from database.schema import get_db_connection

def show():
    """Display the teacher assignments and class tests page"""
    render_page_title("📝", "Assignments & Class Tests")
    
    # Get user ID from session
    teacher_id = st.session_state.user.get('user_id')
    
    # Connect to database
    conn = get_db_connection()
    
    # Get current active session
    active_session = conn.execute(
        "SELECT name FROM academic_sessions WHERE is_active = 1"
    ).fetchone()
    
    if not active_session:
        st.warning("No active academic session. Please contact an administrator.")
        return
    
    session_name = active_session['name']
    st.write(f"**Current Academic Session:** {session_name}")
    
    # Get all courses assigned to the teacher for the current session
    courses = conn.execute("""
        SELECT c.id, c.code, c.title
        FROM courses c
        JOIN teaching t ON c.id = t.course_id
        WHERE t.teacher_id = ? AND t.semester = ?
        ORDER BY c.code
    """, (teacher_id, session_name)).fetchall()
    
    if not courses:
        st.info(f"No courses assigned to you for the {session_name} session.")
        return
    
    # Select a course
    course_options = {f"{c['code']} - {c['title']}": c['id'] for c in courses}
    selected_course_name = st.selectbox(
        "Select a course:",
        options=list(course_options.keys())
    )
    
    selected_course_id = course_options[selected_course_name]
    selected_course_code = selected_course_name.split(" - ")[0]
    
    # Create tabs for assignments and class tests
    assign_tab, class_test_tab, grade_tab = st.tabs(["Assignments", "Class Tests", "Grading Center"])
    
    # Tab 1: Assignments
    with assign_tab:
        st.write("### Assignments")
        
        # Create two columns - one for existing assignments, one for creating new
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Display existing assignments
            assignments = conn.execute("""
                SELECT a.id, a.title, a.description, a.due_date, a.max_marks, a.is_published,
                       (SELECT COUNT(*) FROM student_assignments sa WHERE sa.assignment_id = a.id) as submission_count
                FROM assignments a
                WHERE a.course_id = ? AND a.semester = ?
                ORDER BY a.due_date DESC
            """, (selected_course_id, session_name)).fetchall()
            
            if assignments:
                # Convert to DataFrame for display
                assignments_df = pd.DataFrame([
                    {
                        "Title": a['title'],
                        "Due Date": a['due_date'],
                        "Max Marks": a['max_marks'],
                        "Status": "Published" if a['is_published'] else "Draft",
                        "Submissions": a['submission_count'],
                        "ID": a['id']  # Hidden column for reference
                    } for a in assignments
                ])
                
                # Display assignments table
                st.dataframe(
                    assignments_df.drop(columns=["ID"]), 
                    use_container_width=True,
                    hide_index=True
                )
                
                # Detail view and actions for selected assignment
                if assignments:
                    # Select an assignment to view/edit
                    selected_assignment_idx = st.selectbox(
                        "Select an assignment to view or edit:",
                        options=range(len(assignments)),
                        format_func=lambda i: assignments[i]['title']
                    )
                    
                    selected_assignment = assignments[selected_assignment_idx]
                    
                    # Show assignment details
                    st.write(f"#### {selected_assignment['title']}")
                    st.write(f"**Due Date:** {selected_assignment['due_date']}")
                    st.write(f"**Max Marks:** {selected_assignment['max_marks']}")
                    st.write(f"**Description:**")
                    st.write(selected_assignment['description'])
                    
                    # Action buttons for the assignment
                    col1a, col2a, col3a = st.columns(3)
                    
                    with col1a:
                        # Publish/Unpublish button
                        if selected_assignment['is_published']:
                            if st.button("Unpublish", key="unpublish_assignment"):
                                conn.execute(
                                    "UPDATE assignments SET is_published = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                    (selected_assignment['id'],)
                                )
                                conn.commit()
                                st.success("Assignment unpublished!")
                                st.rerun()
                        else:
                            if st.button("Publish", key="publish_assignment"):
                                conn.execute(
                                    "UPDATE assignments SET is_published = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                    (selected_assignment['id'],)
                                )
                                conn.commit()
                                st.success("Assignment published!")
                                st.rerun()
                    
                    with col2a:
                        # Delete button with confirmation
                        if st.button("Delete", key="delete_assignment"):
                            # Check if there are submissions
                            if selected_assignment['submission_count'] > 0:
                                st.warning("Cannot delete assignment with submissions!")
                            else:
                                conn.execute(
                                    "DELETE FROM assignments WHERE id = ?",
                                    (selected_assignment['id'],)
                                )
                                conn.commit()
                                st.success("Assignment deleted!")
                                st.rerun()
                    
                    with col3a:
                        # View submissions button
                        if st.button("View Submissions", key="view_submissions"):
                            st.session_state.view_assignment_id = selected_assignment['id']
                            st.session_state.view_assignment_title = selected_assignment['title']
                            st.rerun()
                    
                    # If viewing submissions
                    if hasattr(st.session_state, 'view_assignment_id') and st.session_state.view_assignment_id == selected_assignment['id']:
                        st.write(f"#### Submissions for: {st.session_state.view_assignment_title}")
                        
                        # Get submissions
                        submissions = conn.execute("""
                            SELECT sa.id, s.student_id as display_id, s.name, sa.submission_file, sa.marks, sa.status, sa.submitted_at
                            FROM student_assignments sa
                            JOIN students s ON sa.student_id = s.id
                            WHERE sa.assignment_id = ?
                            ORDER BY sa.submitted_at DESC
                        """, (st.session_state.view_assignment_id,)).fetchall()
                        
                        if submissions:
                            # Convert to DataFrame for display
                            submissions_df = pd.DataFrame([
                                {
                                    "Student ID": sub['display_id'],
                                    "Name": sub['name'],
                                    "Submission": "Yes" if sub['submission_file'] else "No",
                                    "Status": sub['status'].capitalize(),
                                    "Marks": sub['marks'],
                                    "Submitted At": sub['submitted_at'] if sub['submitted_at'] else "Not submitted"
                                } for sub in submissions
                            ])
                            
                            # Display submissions
                            st.dataframe(submissions_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("No submissions yet.")
                        
                        # Close button
                        if st.button("Close Submissions View"):
                            del st.session_state.view_assignment_id
                            del st.session_state.view_assignment_title
                            st.rerun()
            else:
                st.info("No assignments created yet for this course.")
        
        with col2:
            # Form to create a new assignment
            st.write("#### Create New Assignment")
            
            with st.form("new_assignment_form"):
                title = st.text_input("Assignment Title")
                description = st.text_area("Assignment Description")
                due_date = st.date_input("Due Date", min_value=datetime.now().date())
                max_marks = st.number_input("Maximum Marks", min_value=1.0, max_value=100.0, value=10.0)
                publish_now = st.checkbox("Publish Immediately")
                
                submit_button = st.form_submit_button("Create Assignment")
                
                if submit_button:
                    if title and description:
                        try:
                            # Insert the new assignment
                            conn.execute("""
                                INSERT INTO assignments 
                                (course_id, title, description, due_date, max_marks, is_published, semester, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            """, (selected_course_id, title, description, due_date, max_marks, 
                                  1 if publish_now else 0, session_name))
                            
                            conn.commit()
                            st.success("Assignment created successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creating assignment: {str(e)}")
                    else:
                        st.warning("Please fill in all required fields.")
    
    # Tab 2: Class Tests
    with class_test_tab:
        st.write("### Class Tests")
        
        # Create two columns - one for existing tests, one for creating new
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Display existing class tests
            tests = conn.execute("""
                SELECT ct.id, ct.title, ct.description, ct.test_date, ct.max_marks, ct.duration_minutes, 
                       ct.is_published, ct.questions,
                       (SELECT COUNT(*) FROM student_test_submissions sts WHERE sts.test_id = ct.id) as submission_count
                FROM class_tests ct
                WHERE ct.course_id = ? AND ct.semester = ?
                ORDER BY ct.test_date DESC
            """, (selected_course_id, session_name)).fetchall()
            
            if tests:
                # Convert to DataFrame for display
                tests_df = pd.DataFrame([
                    {
                        "Title": t['title'],
                        "Test Date": t['test_date'],
                        "Duration": f"{t['duration_minutes']} min",
                        "Max Marks": t['max_marks'],
                        "Status": "Published" if t['is_published'] else "Draft",
                        "Submissions": t['submission_count'],
                        "ID": t['id']  # Hidden column for reference
                    } for t in tests
                ])
                
                # Display tests table
                st.dataframe(
                    tests_df.drop(columns=["ID"]), 
                    use_container_width=True,
                    hide_index=True
                )
                
                # Detail view and actions for selected test
                if tests:
                    # Select a test to view/edit
                    selected_test_idx = st.selectbox(
                        "Select a class test to view or edit:",
                        options=range(len(tests)),
                        format_func=lambda i: tests[i]['title']
                    )
                    
                    selected_test = tests[selected_test_idx]
                    
                    # Parse questions JSON
                    questions = json.loads(selected_test['questions'])
                    
                    # Show test details
                    st.write(f"#### {selected_test['title']}")
                    st.write(f"**Test Date:** {selected_test['test_date']}")
                    st.write(f"**Duration:** {selected_test['duration_minutes']} minutes")
                    st.write(f"**Max Marks:** {selected_test['max_marks']}")
                    st.write(f"**Description:**")
                    st.write(selected_test['description'])
                    
                    # Display questions
                    st.write("#### Questions:")
                    for i, q in enumerate(questions):
                        st.write(f"**{i+1}. {q['question']}** ({q['marks']} marks)")
                        if q['type'] == 'mcq':
                            for j, option in enumerate(q['options']):
                                is_correct = "✓" if j == q['answer'] else ""
                                st.write(f"   {chr(97+j)}) {option} {is_correct}")
                    
                    # Action buttons for the test
                    col1a, col2a, col3a = st.columns(3)
                    
                    with col1a:
                        # Publish/Unpublish button
                        if selected_test['is_published']:
                            if st.button("Unpublish", key="unpublish_test"):
                                conn.execute(
                                    "UPDATE class_tests SET is_published = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                    (selected_test['id'],)
                                )
                                conn.commit()
                                st.success("Class test unpublished!")
                                st.rerun()
                        else:
                            if st.button("Publish", key="publish_test"):
                                conn.execute(
                                    "UPDATE class_tests SET is_published = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                    (selected_test['id'],)
                                )
                                conn.commit()
                                st.success("Class test published!")
                                st.rerun()
                    
                    with col2a:
                        # Delete button with confirmation
                        if st.button("Delete", key="delete_test"):
                            # Check if there are submissions
                            if selected_test['submission_count'] > 0:
                                st.warning("Cannot delete test with submissions!")
                            else:
                                conn.execute(
                                    "DELETE FROM class_tests WHERE id = ?",
                                    (selected_test['id'],)
                                )
                                conn.commit()
                                st.success("Class test deleted!")
                                st.rerun()
                    
                    with col3a:
                        # View results button
                        if st.button("View Results", key="view_results"):
                            st.session_state.view_test_id = selected_test['id']
                            st.session_state.view_test_title = selected_test['title']
                            st.rerun()
                    
                    # If viewing results
                    if hasattr(st.session_state, 'view_test_id') and st.session_state.view_test_id == selected_test['id']:
                        st.write(f"#### Results for: {st.session_state.view_test_title}")
                        
                        # Get submissions
                        submissions = conn.execute("""
                            SELECT sts.id, s.student_id as display_id, s.name, sts.marks, sts.status, sts.submitted_at
                            FROM student_test_submissions sts
                            JOIN students s ON sts.student_id = s.id
                            WHERE sts.test_id = ?
                            ORDER BY sts.marks DESC
                        """, (st.session_state.view_test_id,)).fetchall()
                        
                        if submissions:
                            # Convert to DataFrame for display
                            submissions_df = pd.DataFrame([
                                {
                                    "Student ID": sub['display_id'],
                                    "Name": sub['name'],
                                    "Status": sub['status'].capitalize(),
                                    "Marks": f"{sub['marks']}/{selected_test['max_marks']}",
                                    "Percentage": f"{(sub['marks']/selected_test['max_marks'])*100:.1f}%",
                                    "Submitted At": sub['submitted_at']
                                } for sub in submissions
                            ])
                            
                            # Display submissions
                            st.dataframe(submissions_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("No submissions yet.")
                        
                        # Close button
                        if st.button("Close Results View"):
                            del st.session_state.view_test_id
                            del st.session_state.view_test_title
                            st.rerun()
            else:
                st.info("No class tests created yet for this course.")
        
        with col2:
            # Form to create a new class test
            st.write("#### Create New Class Test")
            
            with st.form("new_test_form"):
                title = st.text_input("Test Title")
                description = st.text_area("Test Description")
                test_date = st.date_input("Test Date", min_value=datetime.now().date())
                duration = st.number_input("Duration (minutes)", min_value=5, max_value=180, value=30)
                max_marks = st.number_input("Maximum Marks", min_value=1.0, max_value=100.0, value=10.0)
                
                # Number of questions
                num_questions = st.number_input("Number of Questions", min_value=1, max_value=20, value=5)
                
                # Placeholder for questions
                questions = []
                for i in range(num_questions):
                    st.write(f"#### Question {i+1}")
                    question_text = st.text_input(f"Question", key=f"q_{i}")
                    question_type = st.selectbox(f"Type", ["MCQ", "Short Answer"], key=f"q_type_{i}")
                    question_marks = st.number_input(f"Marks", min_value=1.0, max_value=max_marks, value=max_marks/num_questions, key=f"q_marks_{i}")
                    
                    if question_type == "MCQ":
                        options = []
                        for j in range(4):  # 4 options for MCQ
                            option = st.text_input(f"Option {j+1}", key=f"q_{i}_opt_{j}")
                            options.append(option)
                        
                        correct_answer = st.selectbox(f"Correct Answer", [0, 1, 2, 3], 
                                                     format_func=lambda x: f"Option {x+1}", key=f"q_{i}_ans")
                        
                        questions.append({
                            "question": question_text,
                            "type": "mcq",
                            "options": options,
                            "answer": correct_answer,
                            "marks": question_marks
                        })
                    else:
                        expected_answer = st.text_input(f"Expected Answer", key=f"q_{i}_ans_sa")
                        questions.append({
                            "question": question_text,
                            "type": "short_answer",
                            "expected_answer": expected_answer,
                            "marks": question_marks
                        })
                
                publish_now = st.checkbox("Publish Immediately")
                
                submit_button = st.form_submit_button("Create Class Test")
                
                if submit_button:
                    if title and description and questions:
                        try:
                            # Validate questions
                            total_marks = sum(q.get('marks', 0) for q in questions)
                            if abs(total_marks - max_marks) > 0.01:
                                st.warning(f"Total question marks ({total_marks}) don't match maximum marks ({max_marks}).")
                            else:
                                # Insert the new class test
                                conn.execute("""
                                    INSERT INTO class_tests 
                                    (course_id, title, description, test_date, duration_minutes, questions, max_marks, 
                                     is_published, semester, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                """, (selected_course_id, title, description, test_date, duration, 
                                      json.dumps(questions), max_marks, 1 if publish_now else 0, session_name))
                                
                                conn.commit()
                                st.success("Class test created successfully!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error creating class test: {str(e)}")
                    else:
                        st.warning("Please fill in all required fields.")
    
    # Tab 3: Grading Center
    with grade_tab:
        st.write("### Grading Center")
        st.write("View and grade student submissions")
        
        # Choose what to grade
        grade_type = st.radio("Select what to grade:", ["Assignments", "Class Tests"])
        
        if grade_type == "Assignments":
            # Show pending assignment submissions
            pending_submissions = conn.execute("""
                SELECT sa.id, a.title as assignment_title, s.student_id as display_id, s.name, 
                       sa.submission_file, sa.submitted_at, a.max_marks
                FROM student_assignments sa
                JOIN assignments a ON sa.assignment_id = a.id
                JOIN students s ON sa.student_id = s.id
                WHERE a.course_id = ? AND a.semester = ? AND sa.status = 'pending'
                ORDER BY sa.submitted_at ASC
            """, (selected_course_id, session_name)).fetchall()
            
            if pending_submissions:
                st.write(f"#### Pending Assignment Submissions ({len(pending_submissions)})")
                
                for sub in pending_submissions:
                    with st.expander(f"{sub['display_id']} - {sub['name']} - {sub['assignment_title']}"):
                        st.write(f"**Submitted at:** {sub['submitted_at']}")
                        
                        # Display submission file link if available
                        if sub['submission_file']:
                            st.write(f"**Submission File:**")
                            
                            # Get file path and name
                            file_path = sub['submission_file']
                            file_name = os.path.basename(file_path)
                            
                            # Check if file exists on disk
                            if os.path.exists(file_path):
                                # Display download button for the file
                                with open(file_path, "rb") as file:
                                    file_content = file.read()
                                    st.download_button(
                                        label="Download Submission", 
                                        data=file_content,
                                        file_name=file_name,
                                        mime="application/pdf"
                                    )
                                
                                # If PDF, show a preview using an iframe
                                if file_path.lower().endswith('.pdf'):
                                    # Create a relative path for the iframe
                                    relative_path = os.path.relpath(file_path, os.getcwd())
                                    st.write("**Preview:**")
                                    st.write(f"<iframe src='{relative_path}' width='100%' height='500'></iframe>", 
                                             unsafe_allow_html=True)
                            else:
                                st.error(f"File not found on server: {file_name}")
                        else:
                            st.info("No file was submitted.")
                        
                        # Grading form
                        with st.form(f"grade_assignment_{sub['id']}"):
                            marks = st.number_input("Marks", min_value=0.0, max_value=float(sub['max_marks']), 
                                                   value=0.0, step=0.5)
                            remarks = st.text_area("Remarks/Feedback")
                            
                            grade_button = st.form_submit_button("Submit Grade")
                            
                            if grade_button:
                                # Update the submission with grades
                                conn.execute("""
                                    UPDATE student_assignments
                                    SET marks = ?, status = 'graded', remarks = ?, graded_at = CURRENT_TIMESTAMP
                                    WHERE id = ?
                                """, (marks, remarks, sub['id']))
                                
                                conn.commit()
                                st.success("Assignment graded successfully!")
                                st.rerun()
            else:
                st.info("No pending assignment submissions to grade.")
            
            # Show recently graded submissions
            graded_submissions = conn.execute("""
                SELECT sa.id, a.title as assignment_title, s.student_id as display_id, s.name, 
                       sa.marks, sa.remarks, sa.graded_at, a.max_marks
                FROM student_assignments sa
                JOIN assignments a ON sa.assignment_id = a.id
                JOIN students s ON sa.student_id = s.id
                WHERE a.course_id = ? AND a.semester = ? AND sa.status = 'graded'
                ORDER BY sa.graded_at DESC
                LIMIT 10
            """, (selected_course_id, session_name)).fetchall()
            
            if graded_submissions:
                st.write("#### Recently Graded Assignments")
                
                graded_df = pd.DataFrame([
                    {
                        "Student ID": sub['display_id'],
                        "Name": sub['name'],
                        "Assignment": sub['assignment_title'],
                        "Marks": f"{sub['marks']}/{sub['max_marks']}",
                        "Percentage": f"{(sub['marks']/sub['max_marks'])*100:.1f}%",
                        "Graded At": sub['graded_at']
                    } for sub in graded_submissions
                ])
                
                st.dataframe(graded_df, use_container_width=True, hide_index=True)
        
        else:  # Class Tests
            # Auto-graded class tests don't need manual grading, so show results instead
            test_results = conn.execute("""
                SELECT ct.title, COUNT(sts.id) as total_submissions, 
                       AVG(sts.marks) as avg_marks, MAX(sts.marks) as max_marks,
                       MIN(sts.marks) as min_marks, ct.max_marks
                FROM class_tests ct
                LEFT JOIN student_test_submissions sts ON sts.test_id = ct.id
                WHERE ct.course_id = ? AND ct.semester = ? AND ct.is_published = 1
                GROUP BY ct.id
                ORDER BY ct.test_date DESC
            """, (selected_course_id, session_name)).fetchall()
            
            if test_results:
                st.write("#### Class Test Statistics")
                
                test_stats_df = pd.DataFrame([
                    {
                        "Test Name": t['title'],
                        "Submissions": t['total_submissions'],
                        "Average Score": f"{t['avg_marks'] or 0:.1f}/{t['max_marks']}",
                        "Highest Score": f"{t['max_marks'] or 0}/{t['max_marks']}",
                        "Lowest Score": f"{t['min_marks'] or 0}/{t['max_marks']}",
                        "Average Percentage": f"{((t['avg_marks'] if t['avg_marks'] is not None else 0)/t['max_marks'])*100:.1f}%"
                    } for t in test_results
                ])
                
                st.dataframe(test_stats_df, use_container_width=True, hide_index=True)
            else:
                st.info("No class test results available yet.")
    
    # Close the database connection
    conn.close() 