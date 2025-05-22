import streamlit as st
import pandas as pd
import numpy as np
import io
from components.header import render_page_title
from database.schema import get_db_connection

def show():
    """Display the teacher grades submission page"""
    render_page_title("📝", "Grade Submission")
    
    # Get user ID from session
    teacher_id = st.session_state.user.get('user_id')
    
    # Connect to database
    conn = get_db_connection()
    
    # Add a cache-busting parameter to force refresh
    st.session_state.grades_last_refresh = pd.Timestamp.now().isoformat()
    
    # Get current active session
    active_session = conn.execute(
        "SELECT name FROM academic_sessions WHERE is_active = 1"
    ).fetchone()
    
    if not active_session:
        st.warning("No active academic session. Please contact an administrator.")
        return
    
    active_session_name = active_session['name']
    
    # Get all available sessions
    all_sessions = conn.execute(
        "SELECT name FROM academic_sessions ORDER BY name DESC"
    ).fetchall()
    
    session_options = [session['name'] for session in all_sessions]
    
    # Add session selector
    session_name = st.selectbox(
        "Select Academic Session:",
        options=session_options,
        index=session_options.index(active_session_name) if active_session_name in session_options else 0
    )
    
    st.write(f"**Selected Academic Session:** {session_name}")
    
    # Get all courses assigned to the teacher for the selected session
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
    
    # Select a course for grade submission
    course_options = {f"{c['code']} - {c['title']}": c['id'] for c in courses}
    selected_course_name = st.selectbox(
        "Select a course for grade submission:",
        options=list(course_options.keys())
    )
    
    selected_course_id = course_options[selected_course_name]
    selected_course_code = selected_course_name.split(" - ")[0]
    
    # Create tabs for different grading functions
    grade_tab, import_tab, analytics_tab, finalize_tab = st.tabs(["Enter Grades", "Import Grades", "Grade Analytics", "Finalize Grades"])
    
    # Check if grades for this course are already finalized
    finalization_status = conn.execute("""
        SELECT marks_finalized, finalized_at
        FROM teaching
        WHERE teacher_id = ? AND course_id = ? AND semester = ?
    """, (teacher_id, selected_course_id, session_name)).fetchone()
    
    grades_finalized = False
    finalized_date = None
    
    if finalization_status and finalization_status['marks_finalized']:
        grades_finalized = True
        finalized_date = finalization_status['finalized_at']
        
        # Show warning if grades are already finalized
        st.warning(f"⚠️ Grades for this course have been finalized on {finalized_date} and cannot be modified.")
    
    # Get enrolled students for the selected course
    students = conn.execute("""
        SELECT s.id, s.student_id, s.name, 
               g.id as grade_id, g.mid, g.assignment, g.final, g.updated_at,
               (SELECT AVG(sa.marks/a.max_marks)*100 
                FROM student_assignments sa 
                JOIN assignments a ON sa.assignment_id = a.id 
                WHERE sa.student_id = s.id AND a.course_id = ? AND a.semester = ?) as assignment_percent,
               (SELECT AVG(sts.marks/ct.max_marks)*100 
                FROM student_test_submissions sts 
                JOIN class_tests ct ON sts.test_id = ct.id 
                WHERE sts.student_id = s.id AND ct.course_id = ? AND ct.semester = ?) as test_percent,
               (SELECT AVG(a.present)*100 
                FROM attendance a 
                WHERE a.student_id = s.id AND a.course_id = ?) as attendance_percent
        FROM students s
        JOIN enrollments e ON s.id = e.student_id
        LEFT JOIN grades g ON g.student_id = s.id AND g.course_id = ? AND g.semester = ?
        WHERE e.course_id = ? AND e.semester = ?
        ORDER BY s.name
    """, (selected_course_id, session_name, selected_course_id, session_name, selected_course_id, 
           selected_course_id, session_name, selected_course_id, session_name)).fetchall()
    
    if not students:
        st.info(f"No students enrolled in {selected_course_name} for the {session_name} session.")
        return
    
    # Define grade components and their max values
    grade_components = {
        "Attendance": 5,
        "Class Tests": 10,
        "Assignments": 5,
        "Midterm": 30,
        "Final Exam": 50
    }
    
    # Tab 1: Manual Grade Entry
    with grade_tab:
        st.write(f"### Grade Entry for {selected_course_name}")
        
        # Add a refresh button to force reload data
        if st.button("🔄 Refresh Grades Data"):
            st.rerun()
        
        if grades_finalized:
            st.info("Grades for this course have been finalized and cannot be modified.")
            
            # Just display the grades without edit functionality
            grade_data = []
            
            for student in students:
                # Get existing grades
                midterm = student['mid'] if student['mid'] is not None else 0
                final = student['final'] if student['final'] is not None else 0
                
                # Calculate auto grades
                attendance_grade = 0
                if student['attendance_percent'] is not None:
                    attendance_grade = min(grade_components["Attendance"], 
                                          student['attendance_percent'] * grade_components["Attendance"] / 100)
                
                test_grade = 0
                if student['test_percent'] is not None:
                    test_grade = min(grade_components["Class Tests"], 
                                    student['test_percent'] * grade_components["Class Tests"] / 100)
                
                assign_grade = 0
                if student['assignment_percent'] is not None:
                    assign_grade = min(grade_components["Assignments"], 
                                      student['assignment_percent'] * grade_components["Assignments"] / 100)
                
                # Calculate total
                total = midterm + final + attendance_grade + test_grade + assign_grade
                
                grade_data.append({
                    "student_id": student['id'],
                    "display_id": student['student_id'],
                    "name": student['name'],
                    "attendance": round(attendance_grade, 1),
                    "class_tests": round(test_grade, 1),
                    "assignments": round(assign_grade, 1),
                    "midterm": midterm,
                    "final": final,
                    "total": round(total, 1),
                    "grade_id": student['grade_id']
                })
            
            grade_df = pd.DataFrame(grade_data)
            
            # Display grades table (read-only)
            st.dataframe(
                grade_df[['display_id', 'name', 'attendance', 'class_tests', 'assignments', 'midterm', 'final', 'total']].rename(columns={
                    'display_id': 'Student ID',
                    'name': 'Name',
                    'attendance': f'Attendance (/{grade_components["Attendance"]})',
                    'class_tests': f'Class Tests (/{grade_components["Class Tests"]})',
                    'assignments': f'Assignments (/{grade_components["Assignments"]})',
                    'midterm': f'Midterm (/{grade_components["Midterm"]})',
                    'final': f'Final Exam (/{grade_components["Final Exam"]})',
                    'total': 'Total (/100)'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Special verification section for Tahasin
            st.write("### Verify Student STU55508's Grades")
            
            # Get Tahasin's grades directly from the database
            tahasin_grade = conn.execute("""
                SELECT g.mid, g.final, g.updated_at FROM grades g
                JOIN students s ON g.student_id = s.id
                WHERE s.student_id = 'STU55508' AND g.course_id = ?
            """, (selected_course_id,)).fetchone()
            
            if tahasin_grade:
                st.info(f"""
                **Direct verification from database:**
                - Student: Tahasin Ibnath (STU55508)
                - Midterm: {tahasin_grade['mid']} out of 30
                - Final Exam: {tahasin_grade['final']} out of 50
                - Last Updated: {tahasin_grade['updated_at']}
                """)
            else:
                st.warning("Could not find grades for student STU55508 in the database.")
        else:
            st.write("Enter grades for each assessment component. The total grade is calculated automatically.")
            
            # Create a form for grade submission
            with st.form("grade_submission_form"):
                # Create a DataFrame to display and edit grades
                grade_data = []
                
                for student in students:
                    # Get existing grades or set defaults
                    midterm = student['mid'] if student['mid'] is not None else 0
                    final = student['final'] if student['final'] is not None else 0
                    
                    # Calculate auto grades
                    attendance_grade = 0
                    if student['attendance_percent'] is not None:
                        attendance_grade = min(grade_components["Attendance"], 
                                              student['attendance_percent'] * grade_components["Attendance"] / 100)
                    
                    test_grade = 0
                    if student['test_percent'] is not None:
                        test_grade = min(grade_components["Class Tests"], 
                                        student['test_percent'] * grade_components["Class Tests"] / 100)
                    
                    assign_grade = 0
                    if student['assignment_percent'] is not None:
                        assign_grade = min(grade_components["Assignments"], 
                                          student['assignment_percent'] * grade_components["Assignments"] / 100)
                    
                    # Calculate total
                    total = midterm + final + attendance_grade + test_grade + assign_grade
                    
                    grade_data.append({
                        "student_id": student['id'],
                        "display_id": student['student_id'],
                        "name": student['name'],
                        "attendance": round(attendance_grade, 1),
                        "class_tests": round(test_grade, 1),
                        "assignments": round(assign_grade, 1),
                        "midterm": midterm,
                        "final": final,
                        "total": round(total, 1),
                        "grade_id": student['grade_id']
                    })
                
                grade_df = pd.DataFrame(grade_data)
                
                # Display editable grade table
                st.dataframe(
                    grade_df[['display_id', 'name', 'attendance', 'class_tests', 'assignments', 'midterm', 'final', 'total']].rename(columns={
                        'display_id': 'Student ID',
                        'name': 'Name',
                        'attendance': f'Attendance (/{grade_components["Attendance"]})',
                        'class_tests': f'Class Tests (/{grade_components["Class Tests"]})',
                        'assignments': f'Assignments (/{grade_components["Assignments"]})',
                        'midterm': f'Midterm (/{grade_components["Midterm"]})',
                        'final': f'Final Exam (/{grade_components["Final Exam"]})',
                        'total': 'Total (/100)'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Create input fields for each student's grades
                st.write("### Update Grades")
                st.write("Enter the Student ID and the grades you want to update:")
                
                # Add clear explanation about auto-calculated components
                st.info("""
                **Note:** 
                - Attendance (5%), Class Tests (10%), and Assignments (5%) are automatically calculated based on student participation and submissions
                - Only Midterm (30%) and Final Exam (50%) grades can be manually entered
                - All grades will be locked after finalizing the course grades
                """)
                
                # Simple form for updating a single student's grades
                student_id = st.text_input("Student ID")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    midterm_grade = st.number_input(f"Midterm (max {grade_components['Midterm']})", 
                                                   min_value=0.0, 
                                                   max_value=float(grade_components['Midterm']), 
                                                   step=0.5)
                
                with col2:
                    final_grade = st.number_input(f"Final Exam (max {grade_components['Final Exam']})", 
                                                 min_value=0.0, 
                                                 max_value=float(grade_components['Final Exam']), 
                                                 step=0.5)
                
                # Auto calculated components display
                if student_id:
                    student_row = grade_df[grade_df['display_id'] == student_id]
                    if not student_row.empty:
                        st.write("### Auto-calculated Components")
                        attendance_grade = student_row.iloc[0]['attendance']
                        test_grade = student_row.iloc[0]['class_tests']
                        assign_grade = student_row.iloc[0]['assignments']
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Attendance (Auto)", f"{attendance_grade}/{grade_components['Attendance']}")
                        with col2:
                            st.metric("Class Tests (Auto)", f"{test_grade}/{grade_components['Class Tests']}")
                        with col3:
                            st.metric("Assignments (Auto)", f"{assign_grade}/{grade_components['Assignments']}")
                        
                        total_grade = midterm_grade + final_grade + attendance_grade + test_grade + assign_grade
                        
                        st.write(f"**Total Grade:** {total_grade}/100")
                    else:
                        # If student not found, calculate without auto components
                        total_grade = midterm_grade + final_grade
                        st.warning(f"Student with ID {student_id} not found or has no auto-calculated components yet.")
                        st.write(f"**Total Grade:** {total_grade}/100 (excludes auto-calculated components)")
                else:
                    # If no student ID entered
                    total_grade = midterm_grade + final_grade
                    st.write("Enter a Student ID to see auto-calculated components and total grade.")
                    st.write(f"**Manual Components Total:** {total_grade}/{grade_components['Midterm'] + grade_components['Final Exam']}")
                
                # Determine the letter grade
                letter_grade = "F"
                grade_point = 0.00
                
                # New grading system based on percentage
                if total_grade >= 80:
                    letter_grade = "A+"
                    grade_point = 4.00
                elif total_grade >= 75:
                    letter_grade = "A"
                    grade_point = 3.75
                elif total_grade >= 70:
                    letter_grade = "A-"
                    grade_point = 3.50
                elif total_grade >= 65:
                    letter_grade = "B+"
                    grade_point = 3.25
                elif total_grade >= 60:
                    letter_grade = "B"
                    grade_point = 3.00
                elif total_grade >= 55:
                    letter_grade = "B-"
                    grade_point = 2.75
                elif total_grade >= 50:
                    letter_grade = "C+"
                    grade_point = 2.50
                elif total_grade >= 45:
                    letter_grade = "C"
                    grade_point = 2.25
                elif total_grade >= 40:
                    letter_grade = "D"
                    grade_point = 2.00
                else:
                    letter_grade = "F"
                    grade_point = 0.00
                
                if total_grade < 40:
                    st.warning(f"Letter Grade: {letter_grade} (Failing) - GPA: {grade_point:.2f}")
                else:
                    st.success(f"Letter Grade: {letter_grade} (Passing) - GPA: {grade_point:.2f}")
                
                # Submit button
                submit_button = st.form_submit_button("Update Grades")
                
                if submit_button and student_id:
                    # Find the student in our data
                    student_row = grade_df[grade_df['display_id'] == student_id]
                    
                    if student_row.empty:
                        st.error(f"No student found with ID {student_id}")
                    else:
                        student_data = student_row.iloc[0]
                        internal_student_id = student_data['student_id']
                        grade_id = student_data['grade_id']
                        
                        # Check if grade record exists
                        if grade_id:
                            # Update existing record
                            conn.execute("""
                                UPDATE grades
                                SET mid = ?, final = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            """, (midterm_grade, final_grade, grade_id))
                        else:
                            # Create new record
                            conn.execute("""
                                INSERT INTO grades (student_id, course_id, mid, assignment, final, semester)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (internal_student_id, selected_course_id, midterm_grade, 0, 
                                  final_grade, session_name))
                        
                        conn.commit()
                        
                        # Special check for Tahasin
                        if student_id == "STU55508":
                            st.info(f"Checking Tahasin's (STU55508) grades were properly updated...")
                            tahasin_grade = conn.execute("""
                                SELECT g.mid, g.final FROM grades g
                                WHERE g.student_id = (SELECT id FROM students WHERE student_id = 'STU55508')
                                AND g.course_id = ?
                            """, (selected_course_id,)).fetchone()
                            
                            if tahasin_grade:
                                st.success(f"Verified Tahasin's grades in database: Midterm = {tahasin_grade['mid']}, Final = {tahasin_grade['final']}")
                        
                        st.success(f"Grades updated for {student_id}")
                        st.rerun()
    
    # Tab 2: Import Grades
    with import_tab:
        st.write(f"### Import Grades for {selected_course_name}")
        
        if grades_finalized:
            st.info("Grades for this course have been finalized and cannot be modified.")
        else:
            st.write("Upload a CSV file with grades. The file should contain columns for Student ID, Midterm, and Final Exam.")
            
            # Add clear explanation about auto-calculated components
            st.info("""
            **Note:** 
            - This import only updates the manually entered Midterm (30%) and Final Exam (50%) grades
            - Attendance (5%), Class Tests (10%), and Assignments (5%) are automatically calculated and won't be affected by the import
            - All grades will be locked after finalizing the course grades
            """)
          
          # Sample template
        st.write("#### CSV Template Format")
        sample_data = {
            "Student ID": [s['student_id'] for s in students[:3]] + ["..."],
            f"Midterm (/{grade_components['Midterm']})": ["20", "25", "22", "..."],
            f"Final Exam (/{grade_components['Final Exam']})": ["40", "45", "43", "..."]
        }
        
        sample_df = pd.DataFrame(sample_data)
        st.dataframe(sample_df, use_container_width=True, hide_index=True)
        
        # Generate template button
        template_df = pd.DataFrame({
            "Student ID": [s['student_id'] for s in students],
            "Midterm": [""] * len(students),
            "Final Exam": [""] * len(students)
        })
        
        template_csv = template_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Grade Template",
            data=template_csv,
            file_name=f"grade_template_{selected_course_code}_{session_name}.csv",
            mime="text/csv"
        )
        
        # File uploader
        uploaded_file = st.file_uploader("Upload grades CSV file", type="csv")
        
        if uploaded_file is not None:
            try:
                # Read the CSV file
                import_df = pd.read_csv(uploaded_file)
                
                # Validate columns
                required_columns = ["Student ID"]
                valid_grade_columns = ["Midterm", "Final Exam"]
                
                # Check for required columns
                missing_columns = [col for col in required_columns if col not in import_df.columns]
                
                # Check for at least one grade column
                available_grade_columns = [col for col in valid_grade_columns if col in import_df.columns]
                
                if missing_columns:
                    st.error(f"Missing required columns: {', '.join(missing_columns)}")
                elif not available_grade_columns:
                    st.error(f"CSV must include at least one of: {', '.join(valid_grade_columns)}")
                else:
                    # Display preview
                    st.write("#### Grade Import Preview")
                    st.dataframe(import_df, use_container_width=True, hide_index=True)
                    
                    # Process and validate the data
                    if st.button("Process and Save Grades"):
                        # Convert Student IDs to strings for matching
                        import_df["Student ID"] = import_df["Student ID"].astype(str)
                        
                        success_count = 0
                        error_count = 0
                        
                        # Mapping between display IDs and actual database IDs
                        student_id_map = {s['student_id']: (s['id'], s['grade_id']) for s in students}
                        
                        for _, row in import_df.iterrows():
                            student_display_id = row["Student ID"]
                            
                            if student_display_id in student_id_map:
                                student_id, grade_id = student_id_map[student_display_id]
                                
                                # Get grade values or use None if not in the import file
                                midterm = float(row["Midterm"]) if "Midterm" in import_df.columns and pd.notna(row["Midterm"]) else None
                                final_exam = float(row["Final Exam"]) if "Final Exam" in import_df.columns and pd.notna(row["Final Exam"]) else None
                                
                                try:
                                    if grade_id:
                                        # Update query parts based on which columns are provided
                                        set_parts = []
                                        params = []
                                        
                                        if midterm is not None:
                                            set_parts.append("mid = ?")
                                            params.append(min(midterm, grade_components["Midterm"]))
                                        
                                        if final_exam is not None:
                                            set_parts.append("final = ?")
                                            params.append(min(final_exam, grade_components["Final Exam"]))
                                        
                                        set_parts.append("updated_at = CURRENT_TIMESTAMP")
                                        
                                        if set_parts:
                                            # Update existing record
                                            update_query = f"UPDATE grades SET {', '.join(set_parts)} WHERE id = ?"
                                            params.append(grade_id)
                                            conn.execute(update_query, params)
                                            success_count += 1
                                    else:
                                        # Initialize grade components with default values
                                        mid_val = 0 if midterm is None else min(midterm, grade_components["Midterm"])
                                        final_val = 0 if final_exam is None else min(final_exam, grade_components["Final Exam"])
                                        
                                        # Insert new record
                                        conn.execute("""
                                            INSERT INTO grades (student_id, course_id, mid, assignment, final, semester)
                                            VALUES (?, ?, ?, ?, ?, ?)
                                        """, (student_id, selected_course_id, mid_val, 0, final_val, session_name))
                                        success_count += 1
                                except Exception as e:
                                    error_count += 1
                                    st.error(f"Error updating grades for {student_display_id}: {str(e)}")
                            else:
                                error_count += 1
                                st.error(f"Student ID {student_display_id} not found in this course")
                        
                        conn.commit()
                        
                        if success_count > 0:
                            st.success(f"Successfully updated grades for {success_count} students")
                        
                        if error_count > 0:
                            st.warning(f"Failed to update grades for {error_count} students")
                        
                        if success_count > 0:
                            st.rerun()
            
            except Exception as e:
                st.error(f"Error processing CSV file: {str(e)}")
    
    # Tab 3: Grade Analytics
    with analytics_tab:
        st.write(f"### Grade Analytics for {selected_course_name}")
        
        # Create analytics data
        grade_data = []
        
        for student in students:
            # Get existing grades or set defaults
            midterm = student['mid'] if student['mid'] is not None else 0
            final = student['final'] if student['final'] is not None else 0
            
            # Calculate auto grades
            attendance_grade = 0
            if student['attendance_percent'] is not None:
                attendance_grade = min(grade_components["Attendance"], 
                                      student['attendance_percent'] * grade_components["Attendance"] / 100)
            
            test_grade = 0
            if student['test_percent'] is not None:
                test_grade = min(grade_components["Class Tests"], 
                                student['test_percent'] * grade_components["Class Tests"] / 100)
            
            assign_grade = 0
            if student['assignment_percent'] is not None:
                assign_grade = min(grade_components["Assignments"], 
                                  student['assignment_percent'] * grade_components["Assignments"] / 100)
            
            # Calculate total
            total = midterm + final + attendance_grade + test_grade + assign_grade
            
            grade_data.append({
                "student_id": student['id'],
                "display_id": student['student_id'],
                "name": student['name'],
                "attendance": round(attendance_grade, 1),
                "class_tests": round(test_grade, 1),
                "assignments": round(assign_grade, 1),
                "midterm": midterm,
                "final": final,
                "total": round(total, 1)
            })
        
        if not grade_data:
            st.info("No grades available for analysis yet.")
        else:
            # Convert to DataFrame
            grade_df = pd.DataFrame(grade_data)
            
            # Create columns for different analytics
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("#### Grade Distribution")
                
                # Create histogram of total grades
                histogram_data = []
                bins = ['<50', '50-60', '60-70', '70-80', '80-90', '90-100']
                
                # Count grades in each bin
                counts = [
                    sum(grade_df['total'] < 50),
                    sum((grade_df['total'] >= 50) & (grade_df['total'] < 60)),
                    sum((grade_df['total'] >= 60) & (grade_df['total'] < 70)),
                    sum((grade_df['total'] >= 70) & (grade_df['total'] < 80)),
                    sum((grade_df['total'] >= 80) & (grade_df['total'] < 90)),
                    sum(grade_df['total'] >= 90)
                ]
                
                # Create histogram
                hist_df = pd.DataFrame({'Grade Range': bins, 'Count': counts})
                st.bar_chart(hist_df.set_index('Grade Range'))
            
            with col2:
                st.write("#### Component Averages")
                
                # Calculate averages
                component_avgs = {
                    "Component": ["Attendance", "Class Tests", "Assignments", "Midterm", "Final Exam", "Total"],
                    "Average": [
                        grade_df['attendance'].mean() if 'attendance' in grade_df.columns else 0,
                        grade_df['class_tests'].mean() if 'class_tests' in grade_df.columns else 0,
                        grade_df['assignments'].mean() if 'assignments' in grade_df.columns else 0,
                        grade_df['midterm'].mean() if 'midterm' in grade_df.columns else 0,
                        grade_df['final'].mean() if 'final' in grade_df.columns else 0,
                        grade_df['total'].mean()
                    ],
                    "Maximum": [
                        grade_components["Attendance"],
                        grade_components["Class Tests"],
                        grade_components["Assignments"],
                        grade_components["Midterm"],
                        grade_components["Final Exam"],
                        100
                    ]
                }
                
                # Display averages
                avg_df = pd.DataFrame(component_avgs)
                
                # Calculate percentage of maximum
                avg_df['Percentage'] = (avg_df['Average'] / avg_df['Maximum'] * 100).round(1)
                
                # Format the average column to 1 decimal place
                avg_df['Average'] = avg_df['Average'].round(1)
                
                # Display the table
                st.dataframe(avg_df, use_container_width=True, hide_index=True)
            
            # Show at-risk students
            st.write("#### Students at Risk of Failing")
            
            at_risk_data = conn.execute("""
                SELECT s.student_id, s.name, 
                       g.mid, g.final,
                       (g.mid + g.final) as total,
                       (SELECT AVG(sa.marks/a.max_marks)*100 
                        FROM student_assignments sa 
                        JOIN assignments a ON sa.assignment_id = a.id 
                        WHERE sa.student_id = s.id AND a.course_id = ? AND a.semester = ?) as assignment_percent,
                       (SELECT AVG(sts.marks/ct.max_marks)*100 
                        FROM student_test_submissions sts 
                        JOIN class_tests ct ON sts.test_id = ct.id 
                        WHERE sts.student_id = s.id AND ct.course_id = ? AND ct.semester = ?) as test_percent,
                       (SELECT AVG(a.present)*100 
                        FROM attendance a 
                        WHERE a.student_id = s.id AND a.course_id = ?) as attendance_percent
                FROM students s
                JOIN grades g ON s.id = g.student_id
                WHERE g.course_id = ? AND g.semester = ? AND (g.mid + g.final) < 40
                ORDER BY total ASC
            """, (selected_course_id, session_name, selected_course_id, session_name, 
                  selected_course_id, selected_course_id, session_name)).fetchall()
            
            if at_risk_data:
                # Calculate final grades with all components
                at_risk_grades = []
                
                for student in at_risk_data:
                    # Calculate auto grades
                    attendance_grade = 0
                    if student['attendance_percent'] is not None:
                        attendance_grade = min(grade_components["Attendance"], 
                                              student['attendance_percent'] * grade_components["Attendance"] / 100)
                    
                    test_grade = 0
                    if student['test_percent'] is not None:
                        test_grade = min(grade_components["Class Tests"], 
                                        student['test_percent'] * grade_components["Class Tests"] / 100)
                    
                    assign_grade = 0
                    if student['assignment_percent'] is not None:
                        assign_grade = min(grade_components["Assignments"], 
                                          student['assignment_percent'] * grade_components["Assignments"] / 100)
                    
                    # Get midterm and final marks
                    midterm = student['mid'] or 0
                    final = student['final'] or 0
                    
                    # Calculate total
                    total = midterm + final + attendance_grade + test_grade + assign_grade
                    
                    at_risk_grades.append({
                        "Student ID": student['student_id'],
                        "Name": student['name'],
                        "Midterm": f"{midterm}/{grade_components['Midterm']}",
                        "Final": f"{final}/{grade_components['Final Exam']}",
                        "Auto Components": f"{attendance_grade + test_grade + assign_grade}/20",
                        "Total Grade": f"{total}/100",
                        "Risk Level": "High" if total < 40 else "Medium"
                    })
                
                # Display at-risk students
                at_risk_df = pd.DataFrame(at_risk_grades)
                st.dataframe(at_risk_df, use_container_width=True, hide_index=True)
                
                # AI recommendations for at-risk students
                st.write("#### AI Insights")
                
                for _, student in at_risk_df.iterrows():
                    student_name = student['Name']
                    total_grade = float(student['Total Grade'].split('/')[0])
                    
                    if total_grade < 40:
                        st.error(f"🔴 {student_name} is significantly below passing grade. Consider scheduling a meeting.")
                    else:
                        st.warning(f"🟠 {student_name} is close to passing. Additional support may help them succeed.")
            else:
                st.success("No students currently at risk of failing!")
            
            # Grade insights
            st.write("#### Grade Insights")
            
            # Calculate statistics
            passing_rate = (grade_df['total'] >= 50).mean() * 100
            highest_grade = grade_df['total'].max()
            lowest_grade = grade_df['total'].min()
            
            # Display metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Passing Rate", f"{passing_rate:.1f}%")
            col2.metric("Highest Grade", f"{highest_grade:.1f}")
            col3.metric("Lowest Grade", f"{lowest_grade:.1f}")
    
    # Tab 4: Finalize Grades
    with finalize_tab:
        st.write("### Finalize Course Grades")
        st.write("This action locks all grades and makes them permanent for official records.")
        
        # Add a prominent warning
        st.warning("""
        ### ⚠️ IMPORTANT
        - Once grades are finalized, they CANNOT be modified
        - This action is typically done at the end of the semester after all assessments are complete
        - Make sure all manual grades (Midterm and Final) are correctly entered
        - Verify that all students have completed their assignments and tests
        """)
        
        if grades_finalized:
            st.info(f"Grades for {selected_course_name} were finalized on {finalized_date}.")
            
            # Display finalized grades
            finalized_grades = conn.execute("""
                SELECT s.student_id as display_id, s.name, g.mid, g.final,
                       (SELECT AVG(sa.marks/a.max_marks)*100 
                        FROM student_assignments sa 
                        JOIN assignments a ON sa.assignment_id = a.id 
                        WHERE sa.student_id = s.id AND a.course_id = ? AND a.semester = ?) as assignment_percent,
                       (SELECT AVG(sts.marks/ct.max_marks)*100 
                        FROM student_test_submissions sts 
                        JOIN class_tests ct ON sts.test_id = ct.id 
                        WHERE sts.student_id = s.id AND ct.course_id = ? AND ct.semester = ?) as test_percent,
                       (SELECT AVG(a.present)*100 
                        FROM attendance a 
                        WHERE a.student_id = s.id AND a.course_id = ?) as attendance_percent
                FROM students s
                JOIN enrollments e ON s.id = e.student_id
                LEFT JOIN grades g ON g.student_id = s.id AND g.course_id = e.course_id AND g.semester = e.semester
                WHERE e.course_id = ? AND e.semester = ?
                ORDER BY s.name
            """, (selected_course_id, session_name, selected_course_id, session_name, 
                  selected_course_id, selected_course_id, session_name)).fetchall()
            
            if finalized_grades:
                # Create grades summary
                grades_summary = []
                
                for student in finalized_grades:
                    # Calculate auto grades
                    attendance_grade = 0
                    if student['attendance_percent'] is not None:
                        attendance_grade = min(grade_components["Attendance"], 
                                               student['attendance_percent'] * grade_components["Attendance"] / 100)
                    
                    test_grade = 0
                    if student['test_percent'] is not None:
                        test_grade = min(grade_components["Class Tests"], 
                                          student['test_percent'] * grade_components["Class Tests"] / 100)
                    
                    assign_grade = 0
                    if student['assignment_percent'] is not None:
                        assign_grade = min(grade_components["Assignments"], 
                                           student['assignment_percent'] * grade_components["Assignments"] / 100)
                    
                    # Get midterm and final marks
                    midterm = student['mid'] or 0
                    final = student['final'] or 0
                    
                    # Calculate total
                    total = midterm + final + attendance_grade + test_grade + assign_grade
                    
                    # Determine letter grade
                    letter_grade = "F"
                    grade_point = 0.00
                    
                    # New grading system based on percentage
                    if total >= 80:
                        letter_grade = "A+"
                        grade_point = 4.00
                    elif total >= 75:
                        letter_grade = "A"
                        grade_point = 3.75
                    elif total >= 70:
                        letter_grade = "A-"
                        grade_point = 3.50
                    elif total >= 65:
                        letter_grade = "B+"
                        grade_point = 3.25
                    elif total >= 60:
                        letter_grade = "B"
                        grade_point = 3.00
                    elif total >= 55:
                        letter_grade = "B-"
                        grade_point = 2.75
                    elif total >= 50:
                        letter_grade = "C+"
                        grade_point = 2.50
                    elif total >= 45:
                        letter_grade = "C"
                        grade_point = 2.25
                    elif total >= 40:
                        letter_grade = "D"
                        grade_point = 2.00
                    else:
                        letter_grade = "F"
                        grade_point = 0.00
                    
                    grades_summary.append({
                        "Student ID": student['display_id'],
                        "Name": student['name'],
                        "Total Grade": f"{total:.1f}/100",
                        "Letter Grade": letter_grade,
                        "Status": "Pass" if total >= 50 else "Fail"
                    })
                
                # Display finalized grades
                st.dataframe(pd.DataFrame(grades_summary), use_container_width=True, hide_index=True)
                
                # Option to generate report
                if st.button("Generate Final Grade Report"):
                    # Create a CSV file with the grades
                    grades_df = pd.DataFrame(grades_summary)
                    csv = grades_df.to_csv(index=False).encode('utf-8')
                    
                    st.download_button(
                        label="Download Final Grade Report (CSV)",
                        data=csv,
                        file_name=f"{selected_course_code}_{session_name}_final_grades.csv",
                        mime="text/csv"
                    )
            else:
                st.info("No students found in this course.")
            
        else:
            st.write("#### Current Grade Summary")
            
            # Display current grades before finalization
            current_grades = conn.execute("""
                SELECT s.student_id as display_id, s.name, g.mid, g.final,
                       (SELECT AVG(sa.marks/a.max_marks)*100 
                        FROM student_assignments sa 
                        JOIN assignments a ON sa.assignment_id = a.id 
                        WHERE sa.student_id = s.id AND a.course_id = ? AND a.semester = ?) as assignment_percent,
                       (SELECT AVG(sts.marks/ct.max_marks)*100 
                        FROM student_test_submissions sts 
                        JOIN class_tests ct ON sts.test_id = ct.id 
                        WHERE sts.student_id = s.id AND ct.course_id = ? AND ct.semester = ?) as test_percent,
                       (SELECT AVG(a.present)*100 
                        FROM attendance a 
                        WHERE a.student_id = s.id AND a.course_id = ?) as attendance_percent
                FROM students s
                JOIN enrollments e ON s.id = e.student_id
                LEFT JOIN grades g ON g.student_id = s.id AND g.course_id = e.course_id AND g.semester = e.semester
                WHERE e.course_id = ? AND e.semester = ?
                ORDER BY s.name
            """, (selected_course_id, session_name, selected_course_id, session_name, 
                  selected_course_id, selected_course_id, session_name)).fetchall()
            
            if current_grades:
                # Create grades summary
                grades_summary = []
                has_incomplete_grades = False
                
                for student in current_grades:
                    # Check if grades are complete (midterm and final both entered)
                    grades_complete = (student['mid'] is not None and student['final'] is not None)
                    if not grades_complete:
                        has_incomplete_grades = True
                    
                    # Calculate auto grades
                    attendance_grade = 0
                    if student['attendance_percent'] is not None:
                        attendance_grade = min(grade_components["Attendance"], 
                                               student['attendance_percent'] * grade_components["Attendance"] / 100)
                    
                    test_grade = 0
                    if student['test_percent'] is not None:
                        test_grade = min(grade_components["Class Tests"], 
                                          student['test_percent'] * grade_components["Class Tests"] / 100)
                    
                    assign_grade = 0
                    if student['assignment_percent'] is not None:
                        assign_grade = min(grade_components["Assignments"], 
                                           student['assignment_percent'] * grade_components["Assignments"] / 100)
                    
                    # Get midterm and final marks
                    midterm = student['mid'] or 0
                    final = student['final'] or 0
                    
                    # Calculate total
                    total = midterm + final + attendance_grade + test_grade + assign_grade
                    
                    grades_summary.append({
                        "Student ID": student['display_id'],
                        "Name": student['name'],
                        "Midterm": student['mid'] or "Not graded",
                        "Final": student['final'] or "Not graded",
                        "Total Grade": f"{total:.1f}/100",
                        "Status": "Complete" if grades_complete else "Incomplete"
                    })
                
                # Display current grades
                st.dataframe(pd.DataFrame(grades_summary), use_container_width=True, hide_index=True)
                
                # Warning if incomplete grades
                if has_incomplete_grades:
                    st.warning("⚠️ Some students have incomplete grades. Please complete all grades before finalizing.")
                
                # Finalization form
                with st.form("finalize_grades_form"):
                    st.write("#### Finalize Grades")
                    st.write("Please confirm that you want to finalize grades for this course. This action cannot be undone.")
                    
                    # Add a reason field
                    reason = st.text_area("Reason for finalization (optional)", 
                                          placeholder="e.g., End of semester, Final grades submission")
                    
                    # Confirmation checkbox
                    confirm = st.checkbox("I confirm that all grades are complete and accurate, and I want to finalize them.")
                    
                    # Submit button
                    submit_button = st.form_submit_button("Finalize Grades")
                    
                    if submit_button:
                        if not confirm:
                            st.error("Please confirm that you want to finalize the grades.")
                        elif has_incomplete_grades:
                            st.error("Cannot finalize grades while some students have incomplete grades.")
                        else:
                            # Update teaching record to mark grades as finalized
                            conn.execute("""
                                UPDATE teaching
                                SET marks_finalized = 1, finalized_at = CURRENT_TIMESTAMP
                                WHERE teacher_id = ? AND course_id = ? AND semester = ?
                            """, (teacher_id, selected_course_id, session_name))
                            
                            conn.commit()
                            st.success("Grades have been finalized successfully!")
                            st.rerun()
            else:
                st.info("No students found in this course.")
    
    # Close the database connection
    conn.close() 