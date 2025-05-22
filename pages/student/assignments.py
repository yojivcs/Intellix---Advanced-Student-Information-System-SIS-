import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from components.header import render_page_title
from database.schema import get_db_connection

def show():
    """Display the student assignments and class tests page"""
    render_page_title("📝", "My Assignments & Tests")
    
    # Get user ID from session
    student_id = st.session_state.user.get('user_id')
    
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
    
    # Get all courses the student is enrolled in for the current session
    courses = conn.execute("""
        SELECT c.id, c.code, c.title
        FROM courses c
        JOIN enrollments e ON c.id = e.course_id
        WHERE e.student_id = ? AND e.semester = ?
        ORDER BY c.code
    """, (student_id, session_name)).fetchall()
    
    if not courses:
        st.info(f"You are not enrolled in any courses for the {session_name} session.")
        return
    
    # Create tabs for assignments and class tests
    assign_tab, class_test_tab, grade_tab = st.tabs(["Assignments", "Class Tests", "My Grades"])
    
    # Tab 1: Assignments
    with assign_tab:
        st.write("### My Assignments")
        
        # Get all published assignments for courses the student is enrolled in
        assignments = conn.execute("""
            SELECT a.id, a.title, a.description, a.due_date, a.max_marks, c.code, c.title as course_title,
                   sa.id as submission_id, sa.submission_file, sa.status, sa.marks, sa.remarks
            FROM assignments a
            JOIN courses c ON a.course_id = c.id
            JOIN enrollments e ON c.id = e.course_id AND e.student_id = ? AND e.semester = ?
            LEFT JOIN student_assignments sa ON a.id = sa.assignment_id AND sa.student_id = ?
            WHERE a.semester = ? AND a.is_published = 1
            ORDER BY a.due_date DESC
        """, (student_id, session_name, student_id, session_name)).fetchall()
        
        if assignments:
            # Group assignments by status
            pending_assignments = []
            completed_assignments = []
            graded_assignments = []
            
            for a in assignments:
                if not a['submission_id']:
                    pending_assignments.append(a)
                elif a['status'] == 'pending':
                    completed_assignments.append(a)
                else:  # graded
                    graded_assignments.append(a)
            
            # Pending Assignments
            if pending_assignments:
                st.write("#### Pending Assignments")
                for assignment in pending_assignments:
                    with st.expander(f"{assignment['code']} - {assignment['title']}"):
                        st.write(f"**Course:** {assignment['course_title']}")
                        st.write(f"**Due Date:** {assignment['due_date']}")
                        st.write(f"**Max Marks:** {assignment['max_marks']}")
                        st.write(f"**Description:**")
                        st.write(assignment['description'])
                        
                        # Form for submission
                        with st.form(f"submit_assignment_{assignment['id']}"):
                            # Replace text input with file uploader
                            uploaded_file = st.file_uploader("Upload your assignment (PDF)", type="pdf")
                            
                            submit_button = st.form_submit_button("Submit Assignment")
                            
                            if submit_button and uploaded_file:
                                try:
                                    # Create directory for uploads if it doesn't exist
                                    upload_dir = os.path.join("static", "uploads", "assignments")
                                    os.makedirs(upload_dir, exist_ok=True)
                                    
                                    # Save the uploaded file
                                    file_path = os.path.join(upload_dir, f"{student_id}_{assignment['id']}_{uploaded_file.name}")
                                    with open(file_path, "wb") as f:
                                        f.write(uploaded_file.getbuffer())
                                    
                                    # Insert submission record
                                    conn.execute("""
                                        INSERT INTO student_assignments 
                                        (student_id, assignment_id, submission_file, status, submitted_at)
                                        VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)
                                    """, (student_id, assignment['id'], file_path))
                                    
                                    conn.commit()
                                    st.success("Assignment submitted successfully!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error submitting assignment: {str(e)}")
                            elif submit_button:
                                st.warning("Please upload a file before submitting.")
            else:
                st.info("No pending assignments available.")
            
            # Submitted (but not graded) Assignments
            if completed_assignments:
                st.write("#### Submitted Assignments (Awaiting Grading)")
                completed_df = pd.DataFrame([
                    {
                        "Course": f"{a['code']} - {a['course_title']}",
                        "Assignment": a['title'],
                        "Due Date": a['due_date'],
                        "Submitted File": a['submission_file'],
                        "Status": "Submitted, awaiting grading"
                    } for a in completed_assignments
                ])
                
                st.dataframe(completed_df, use_container_width=True, hide_index=True)
            
            # Graded Assignments
            if graded_assignments:
                st.write("#### Graded Assignments")
                graded_df = pd.DataFrame([
                    {
                        "Course": f"{a['code']} - {a['course_title']}",
                        "Assignment": a['title'],
                        "Marks": f"{a['marks']}/{a['max_marks']}",
                        "Percentage": f"{(a['marks']/a['max_marks'])*100:.1f}%",
                        "Status": "Graded"
                    } for a in graded_assignments
                ])
                
                st.dataframe(graded_df, use_container_width=True, hide_index=True)
                
                # View detailed feedback
                if st.checkbox("View detailed feedback"):
                    selected_idx = st.selectbox(
                        "Select assignment to view feedback:",
                        options=range(len(graded_assignments)),
                        format_func=lambda i: f"{graded_assignments[i]['code']} - {graded_assignments[i]['title']}"
                    )
                    
                    selected_assignment = graded_assignments[selected_idx]
                    
                    st.write(f"#### Feedback for: {selected_assignment['title']}")
                    st.write(f"**Marks:** {selected_assignment['marks']}/{selected_assignment['max_marks']}")
                    st.write(f"**Remarks:**")
                    st.write(selected_assignment['remarks'] or "No specific remarks provided.")
        else:
            st.info("No assignments available for your courses.")
    
    # Tab 2: Class Tests
    with class_test_tab:
        st.write("### My Class Tests")
        
        # Get all published class tests for courses the student is enrolled in
        tests = conn.execute("""
            SELECT ct.id, ct.title, ct.description, ct.test_date, ct.max_marks, ct.duration_minutes,
                   c.code, c.title as course_title, ct.questions,
                   sts.id as submission_id, sts.marks, sts.status, sts.submitted_at
            FROM class_tests ct
            JOIN courses c ON ct.course_id = c.id
            JOIN enrollments e ON c.id = e.course_id AND e.student_id = ? AND e.semester = ?
            LEFT JOIN student_test_submissions sts ON ct.id = sts.test_id AND sts.student_id = ?
            WHERE ct.semester = ? AND ct.is_published = 1
            ORDER BY ct.test_date DESC
        """, (student_id, session_name, student_id, session_name)).fetchall()
        
        if tests:
            # Group tests by status
            upcoming_tests = []
            completed_tests = []
            
            for t in tests:
                # Check if test has been taken
                if not t['submission_id']:
                    # Check if test date is in the future
                    test_date = datetime.strptime(t['test_date'], '%Y-%m-%d').date()
                    if test_date >= datetime.now().date():
                        upcoming_tests.append(t)
                    else:
                        # Missed test
                        pass
                else:
                    completed_tests.append(t)
            
            # Upcoming Tests
            if upcoming_tests:
                st.write("#### Upcoming Tests")
                upcoming_df = pd.DataFrame([
                    {
                        "Course": f"{t['code']} - {t['course_title']}",
                        "Test": t['title'],
                        "Date": t['test_date'],
                        "Duration": f"{t['duration_minutes']} minutes",
                        "Max Marks": t['max_marks']
                    } for t in upcoming_tests
                ])
                
                st.dataframe(upcoming_df, use_container_width=True, hide_index=True)
                
                # Take a test
                st.write("#### Take a Test")
                test_options = {f"{t['code']} - {t['title']}": t for t in upcoming_tests}
                
                if test_options:
                    selected_test_name = st.selectbox(
                        "Select a test to take:",
                        options=list(test_options.keys())
                    )
                    
                    selected_test = test_options[selected_test_name]
                    
                    st.write(f"**Test:** {selected_test['title']}")
                    st.write(f"**Course:** {selected_test['course_title']}")
                    st.write(f"**Duration:** {selected_test['duration_minutes']} minutes")
                    st.write(f"**Max Marks:** {selected_test['max_marks']}")
                    
                    # Start test button
                    if st.button("Start Test"):
                        st.session_state.test_in_progress = True
                        st.session_state.current_test = selected_test
                        st.session_state.test_answers = {}
                        st.session_state.test_start_time = datetime.now()
                        st.rerun()
            
            # Handle test in progress
            if hasattr(st.session_state, 'test_in_progress') and st.session_state.test_in_progress:
                test = st.session_state.current_test
                
                # Check if time is up
                elapsed_time = (datetime.now() - st.session_state.test_start_time).total_seconds() / 60
                remaining_time = max(0, test['duration_minutes'] - elapsed_time)
                
                st.write(f"#### {test['title']} (In Progress)")
                st.write(f"**Time Remaining:** {int(remaining_time)} minutes")
                
                if remaining_time <= 0:
                    st.warning("Time's up! Your test will be submitted automatically.")
                    # Auto-submit logic would go here
                
                # Display questions and collect answers
                questions = json.loads(test['questions'])
                
                with st.form("test_submission_form"):
                    for i, q in enumerate(questions):
                        st.write(f"**Question {i+1}:** {q['question']} ({q['marks']} marks)")
                        
                        if q['type'] == 'mcq':
                            options = q['options']
                            selected_option = st.radio(
                                f"Select answer for Question {i+1}:",
                                options=range(len(options)),
                                format_func=lambda j: f"{chr(97+j)}) {options[j]}",
                                key=f"q_{i}"
                            )
                            
                            # Store answer in session state
                            if f"q_{i}" not in st.session_state.test_answers:
                                st.session_state.test_answers[f"q_{i}"] = selected_option
                        else:  # short answer
                            answer = st.text_input(f"Your answer for Question {i+1}:", key=f"q_{i}")
                            
                            # Store answer in session state
                            if f"q_{i}" not in st.session_state.test_answers:
                                st.session_state.test_answers[f"q_{i}"] = answer
                    
                    submit_test = st.form_submit_button("Submit Test")
                    
                    if submit_test or remaining_time <= 0:
                        # Calculate score
                        total_marks = 0
                        
                        for i, q in enumerate(questions):
                            if q['type'] == 'mcq':
                                student_answer = st.session_state.test_answers.get(f"q_{i}")
                                if student_answer == q['answer']:
                                    total_marks += q['marks']
                            else:  # short answer - simplified for example
                                student_answer = st.session_state.test_answers.get(f"q_{i}", "").strip().lower()
                                expected_answer = q['expected_answer'].strip().lower()
                                
                                if student_answer == expected_answer:
                                    total_marks += q['marks']
                                # In a real app, you might use more sophisticated matching
                        
                        # Save submission to database
                        answers_json = json.dumps(st.session_state.test_answers)
                        
                        try:
                            conn.execute("""
                                INSERT INTO student_test_submissions
                                (student_id, test_id, answers, marks, status, submitted_at)
                                VALUES (?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP)
                            """, (student_id, test['id'], answers_json, total_marks))
                            
                            conn.commit()
                            
                            # Clear test session state
                            st.session_state.test_in_progress = False
                            del st.session_state.current_test
                            del st.session_state.test_answers
                            del st.session_state.test_start_time
                            
                            st.success(f"Test submitted successfully! Your score: {total_marks}/{test['max_marks']}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error submitting test: {str(e)}")
            
            # Completed Tests
            if completed_tests:
                st.write("#### Completed Tests")
                completed_df = pd.DataFrame([
                    {
                        "Course": f"{t['code']} - {t['course_title']}",
                        "Test": t['title'],
                        "Marks": f"{t['marks']}/{t['max_marks']}",
                        "Percentage": f"{(t['marks']/t['max_marks'])*100:.1f}%",
                        "Date Taken": t['submitted_at']
                    } for t in completed_tests
                ])
                
                st.dataframe(completed_df, use_container_width=True, hide_index=True)
        else:
            st.info("No class tests available for your courses.")
    
    # Tab 3: My Grades Summary
    with grade_tab:
        st.write("### Grade Summary")
        
        # Get student's grade data for all enrolled courses
        grades_data = conn.execute("""
            SELECT c.id, c.code, c.title, 
                   g.mid, g.assignment, g.final,
                   (SELECT AVG(sa.marks/a.max_marks)*100 
                    FROM student_assignments sa 
                    JOIN assignments a ON sa.assignment_id = a.id 
                    WHERE sa.student_id = ? AND a.course_id = c.id AND a.semester = ?) as assignment_percent,
                   (SELECT AVG(sts.marks/ct.max_marks)*100 
                    FROM student_test_submissions sts 
                    JOIN class_tests ct ON sts.test_id = ct.id 
                    WHERE sts.student_id = ? AND ct.course_id = c.id AND ct.semester = ?) as test_percent,
                   (SELECT AVG(a.present)*100 
                    FROM attendance a 
                    WHERE a.student_id = ? AND a.course_id = c.id) as attendance_percent
            FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            LEFT JOIN grades g ON g.student_id = e.student_id AND g.course_id = e.course_id AND g.semester = e.semester
            WHERE e.student_id = ? AND e.semester = ?
            ORDER BY c.code
        """, (student_id, session_name, student_id, session_name, student_id, student_id, session_name)).fetchall()
        
        if grades_data:
            # Create DataFrame for grades display
            grades_summary = []
            
            for course in grades_data:
                # Calculate assignment grade (5%)
                assignment_grade = 0
                if course['assignment_percent'] is not None:
                    assignment_grade = min(5, course['assignment_percent'] * 0.05)
                
                # Calculate class test grade (10%)
                test_grade = 0
                if course['test_percent'] is not None:
                    test_grade = min(10, course['test_percent'] * 0.1)
                
                # Calculate attendance grade (5%)
                attendance_grade = 0
                if course['attendance_percent'] is not None:
                    attendance_grade = min(5, course['attendance_percent'] * 0.05)
                
                # Get midterm and final marks
                midterm = course['mid'] or 0
                final = course['final'] or 0
                
                # Calculate total grade
                total = midterm + final + assignment_grade + test_grade + attendance_grade
                
                grades_summary.append({
                    "Course": f"{course['code']} - {course['title']}",
                    "Attendance (5%)": f"{attendance_grade:.1f}",
                    "Class Tests (10%)": f"{test_grade:.1f}",
                    "Assignments (5%)": f"{assignment_grade:.1f}",
                    "Midterm (30%)": course['mid'] or "Not graded",
                    "Final (50%)": course['final'] or "Not graded",
                    "Total": f"{total:.1f}/100"
                })
            
            # Display grades summary
            st.dataframe(pd.DataFrame(grades_summary), use_container_width=True, hide_index=True)
            
            # Calculate GPA
            total_grade_points = 0
            total_courses = len(grades_summary)
            
            for course in grades_data:
                # Calculate total grade as above
                assignment_grade = 0
                if course['assignment_percent'] is not None:
                    assignment_grade = min(5, course['assignment_percent'] * 0.05)
                
                test_grade = 0
                if course['test_percent'] is not None:
                    test_grade = min(10, course['test_percent'] * 0.1)
                
                attendance_grade = 0
                if course['attendance_percent'] is not None:
                    attendance_grade = min(5, course['attendance_percent'] * 0.05)
                
                midterm = course['mid'] or 0
                final = course['final'] or 0
                
                total = midterm + final + assignment_grade + test_grade + attendance_grade
                
                # Convert to grade points (simplified)
                if total >= 90:
                    grade_points = 4.0
                elif total >= 80:
                    grade_points = 3.7
                elif total >= 75:
                    grade_points = 3.3
                elif total >= 70:
                    grade_points = 3.0
                elif total >= 65:
                    grade_points = 2.7
                elif total >= 60:
                    grade_points = 2.3
                elif total >= 50:
                    grade_points = 2.0
                else:
                    grade_points = 0.0
                
                total_grade_points += grade_points
            
            if total_courses > 0:
                gpa = total_grade_points / total_courses
                st.metric("Current GPA", f"{gpa:.2f}/4.00")
        else:
            st.info("No grade data available yet.")
    
    # Close the database connection
    conn.close() 