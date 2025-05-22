import streamlit as st
import pandas as pd
from components.header import render_page_title
from database.schema import get_db_connection

def show():
    """Display the teacher courses page"""
    render_page_title("🎓", "My Courses")
    
    # Get user ID from session
    teacher_id = st.session_state.user.get('user_id')
    
    # Connect to database
    conn = get_db_connection()
    
    # Get current active session
    active_session = conn.execute(
        "SELECT name FROM academic_sessions WHERE is_active = 1"
    ).fetchone()
    
    # Get all sessions for filter
    all_sessions = conn.execute(
        "SELECT name FROM academic_sessions ORDER BY name DESC"
    ).fetchall()
    
    # Filter by session
    if all_sessions:
        session_options = [session['name'] for session in all_sessions]
        default_index = session_options.index(active_session['name']) if active_session else 0
        
        selected_session = st.selectbox(
            "Select Academic Session:", 
            options=session_options,
            index=default_index
        )
    else:
        selected_session = "No sessions available"
        st.warning("No academic sessions found. Please contact an administrator.")
    
    # Get all courses assigned to the teacher for the selected session
    courses = conn.execute("""
        SELECT c.id, c.code, c.title, c.credit_hour, t.semester,
               (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = c.id AND e.semester = t.semester) as enrolled_students
        FROM courses c
        JOIN teaching t ON c.id = t.course_id
        WHERE t.teacher_id = ? AND t.semester = ?
        ORDER BY c.code
    """, (teacher_id, selected_session)).fetchall()
    
    if not courses:
        st.info(f"No courses assigned to you for the {selected_session} session.")
    else:
        # Create a DataFrame for display
        courses_data = []
        for course in courses:
            courses_data.append({
                "Code": course['code'],
                "Title": course['title'],
                "Credit Hours": course['credit_hour'],
                "Enrolled Students": course['enrolled_students'],
                "Academic Session": course['semester']
            })
        
        df = pd.DataFrame(courses_data)
        
        # Display the courses table
        st.write(f"### Your Courses for {selected_session}")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Section for viewing student roster
        st.divider()
        st.write("### Student Roster")
        
        # Select a course to view the roster
        course_options = {f"{c['code']} - {c['title']}": c['id'] for c in courses}
        selected_course_name = st.selectbox(
            "Select a course to view the student roster:",
            options=list(course_options.keys())
        )
        
        selected_course_id = course_options[selected_course_name]
        
        # Get student roster for the selected course
        students = conn.execute("""
            SELECT s.id, s.student_id, s.name, s.dept, s.semester,
                   (SELECT (g.mid + g.assignment + g.final) 
                    FROM grades g 
                    WHERE g.student_id = s.id AND g.course_id = ? AND g.semester = ?) as total_marks,
                   (SELECT COUNT(*) 
                    FROM attendance a 
                    WHERE a.student_id = s.id AND a.course_id = ? AND a.present = 0) as absences
            FROM students s
            JOIN enrollments e ON s.id = e.student_id
            WHERE e.course_id = ? AND e.semester = ?
            ORDER BY s.name
        """, (selected_course_id, selected_session, selected_course_id, selected_course_id, selected_session)).fetchall()
        
        if not students:
            st.info(f"No students enrolled in this course for the {selected_session} session.")
        else:
            # Create tabs for different roster views
            roster_tab, stats_tab = st.tabs(["Student List", "Class Statistics"])
            
            with roster_tab:
                # Create a DataFrame for the student roster
                roster_data = []
                for student in students:
                    # Calculate a simple GPA based on total marks (if available)
                    gpa = None
                    if student['total_marks'] is not None:
                        if student['total_marks'] >= 90:
                            gpa = "4.0 (A)"
                        elif student['total_marks'] >= 80:
                            gpa = "3.7 (A-)"
                        elif student['total_marks'] >= 75:
                            gpa = "3.3 (B+)"
                        elif student['total_marks'] >= 70:
                            gpa = "3.0 (B)"
                        elif student['total_marks'] >= 65:
                            gpa = "2.7 (B-)"
                        elif student['total_marks'] >= 60:
                            gpa = "2.3 (C+)"
                        elif student['total_marks'] >= 50:
                            gpa = "2.0 (C)"
                        else:
                            gpa = "F"
                    
                    roster_data.append({
                        "Student ID": student['student_id'],
                        "Name": student['name'],
                        "Department": student['dept'],
                        "Semester": student['semester'],
                        "Absences": student['absences'] or 0,
                        "Current Grade": gpa if gpa else "Not graded yet"
                    })
                
                roster_df = pd.DataFrame(roster_data)
                
                # Display the roster
                st.dataframe(roster_df, use_container_width=True, hide_index=True)
                
                # Download button for the roster
                csv = roster_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Roster (CSV)",
                    data=csv,
                    file_name=f'student_roster_{selected_course_name.split(" - ")[0]}_{selected_session}.csv',
                    mime='text/csv',
                )
            
            with stats_tab:
                # Calculate class statistics
                total_students = len(students)
                
                # Get the number of students with grades
                graded_students = sum(1 for s in students if s['total_marks'] is not None)
                
                # Calculate attendance statistics
                attendance_data = conn.execute("""
                    SELECT 
                        COUNT(*) as total_attendance_records,
                        SUM(CASE WHEN present = 1 THEN 1 ELSE 0 END) as present_count,
                        SUM(CASE WHEN present = 0 THEN 1 ELSE 0 END) as absent_count
                    FROM attendance a
                    WHERE a.course_id = ? AND a.student_id IN (
                        SELECT e.student_id FROM enrollments e 
                        WHERE e.course_id = ? AND e.semester = ?
                    )
                """, (selected_course_id, selected_course_id, selected_session)).fetchone()
                
                # Create columns for stats display
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Students", total_students)
                    
                with col2:
                    st.metric("Graded Students", graded_students, f"{(graded_students/total_students)*100:.1f}%" if total_students > 0 else "0%")
                    
                with col3:
                    if attendance_data and attendance_data['total_attendance_records'] > 0:
                        attendance_rate = (attendance_data['present_count'] / attendance_data['total_attendance_records']) * 100
                        st.metric("Attendance Rate", f"{attendance_rate:.1f}%")
                    else:
                        st.metric("Attendance Rate", "No data")
                
                # Show at-risk students
                st.write("### At-Risk Students")
                
                at_risk_students = [s for s in students if 
                                   (s['total_marks'] is not None and s['total_marks'] < 50) or
                                   (s['absences'] is not None and s['absences'] > 3)]
                
                if at_risk_students:
                    at_risk_data = []
                    for student in at_risk_students:
                        at_risk_data.append({
                            "Student ID": student['student_id'],
                            "Name": student['name'],
                            "Current Grade": f"{student['total_marks']}" if student['total_marks'] is not None else "Not graded",
                            "Absences": student['absences'] or 0,
                            "Risk Factor": "Low grades" if (student['total_marks'] is not None and student['total_marks'] < 50) else 
                                          "Poor attendance" if (student['absences'] is not None and student['absences'] > 3) else
                                          "Multiple factors"
                        })
                    
                    at_risk_df = pd.DataFrame(at_risk_data)
                    st.dataframe(at_risk_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No at-risk students identified.")
    
    # Close the database connection
    conn.close() 