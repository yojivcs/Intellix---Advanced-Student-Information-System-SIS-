import streamlit as st
from components.header import render_page_title
from models.gpa_predictor import predict_gpa
from database.schema import get_db_connection
import pandas as pd

def show():
    """Display the GPA prediction page"""
    render_page_title("📈", "GPA Prediction")
    
    # Get student ID from session
    student_id = st.session_state.user.get('user_id')
    
    if not student_id:
        st.error("Unable to identify student. Please log in again.")
        return
    
    # Connect to database
    conn = get_db_connection()
    
    # Get student info
    student = conn.execute(
        "SELECT name, student_id as display_id FROM students WHERE id = ?", 
        (student_id,)
    ).fetchone()
    
    if not student:
        st.error("Student record not found.")
        conn.close()
        return
    
    st.write(f"### Welcome, {student['name']}!")
    st.write(f"**Student ID:** {student['display_id']}")
    st.write("This tool uses AI to predict your GPA based on your current grades and attendance.")
    
    # Get all semesters for this student
    semesters = conn.execute(
        "SELECT DISTINCT semester FROM enrollments WHERE student_id = ? ORDER BY semester DESC",
        (student_id,)
    ).fetchall()
    
    if not semesters:
        st.warning("You are not enrolled in any courses yet.")
        conn.close()
        return
    
    # Select semester
    semester_list = [s['semester'] for s in semesters]
    selected_semester = st.selectbox("Select Semester", semester_list)
    
    if st.button("Predict My GPA", use_container_width=True):
        with st.spinner("Analyzing your performance..."):
            # Calculate prediction
            predicted_gpa = predict_gpa(student_id, selected_semester)
            
            # Show prediction
            st.metric("Predicted GPA", predicted_gpa)
            
            # Display the grade scale for reference
            with st.expander("Grade Scale Reference"):
                grade_scale = {
                    "Numerical Grade": ["80% and above", "75% to less than 80%", "70% to less than 75%", 
                                      "65% to less than 70%", "60% to less than 65%", "55% to less than 60%",
                                      "50% to less than 55%", "45% to less than 50%", "40% to less than 45%",
                                      "Less than 40%"],
                    "Letter Grade": ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D", "F"],
                    "Grade Point": [4.00, 3.75, 3.50, 3.25, 3.00, 2.75, 2.50, 2.25, 2.00, 0.00]
                }
                
                st.table(pd.DataFrame(grade_scale))
            
            # Get student's courses and grades
            courses_query = """
                SELECT c.code, c.title, g.mid, g.assignment, g.final,
                    (SELECT COUNT(*) FROM attendance a 
                    WHERE a.student_id = ? AND a.course_id = c.id) as total_classes,
                    (SELECT COUNT(*) FROM attendance a 
                    WHERE a.student_id = ? AND a.course_id = c.id AND a.present = 1) as attended_classes
                FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                LEFT JOIN grades g ON e.student_id = g.student_id AND e.course_id = g.course_id AND e.semester = g.semester
                WHERE e.student_id = ? AND e.semester = ?
            """
            
            courses = conn.execute(courses_query, (student_id, student_id, student_id, selected_semester)).fetchall()
            
            if courses:
                # Show course grades
                st.subheader("Course Performance")
                
                course_data = []
                for course in courses:
                    attendance_pct = round((course['attended_classes'] / course['total_classes'] * 100) if course['total_classes'] > 0 else 0, 1)
                    total_score = (course['mid'] or 0) + (course['assignment'] or 0) + (course['final'] or 0)
                    
                    course_data.append({
                        "Course": f"{course['code']} - {course['title']}",
                        "Midterm": course['mid'] or 0,
                        "Assignment": course['assignment'] or 0,
                        "Final": course['final'] or 0,
                        "Total": total_score,
                        "Attendance": f"{attendance_pct}%"
                    })
                
                df = pd.DataFrame(course_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Identify at-risk courses
                at_risk = [c for c in course_data if c['Total'] < 60 or c['Attendance'] < "75%"]
                
                if at_risk:
                    st.warning("Courses that may need attention:")
                    for course in at_risk:
                        st.write(f"- {course['Course']} (Total: {course['Total']}, Attendance: {course['Attendance']})")
                    
                    st.info("💡 Tip: Consider generating a study plan to improve your performance in these courses.")
            else:
                st.info("No course data available for the selected semester")
    
    # Show GPA improvement tips
    with st.expander("Tips to Improve Your GPA"):
        st.write("""
        1. **Consistent Attendance**: Attend all classes regularly.
        2. **Active Participation**: Engage in class discussions and activities.
        3. **Regular Study Schedule**: Create and follow a study plan.
        4. **Seek Help Early**: Don't wait to ask for help with difficult concepts.
        5. **Review Material Frequently**: Regular review helps retention.
        6. **Form Study Groups**: Collaborate with peers for better understanding.
        7. **Practice Self-Assessment**: Regularly test your knowledge.
        8. **Balanced Approach**: Allocate time to all subjects.
        """)
    
    conn.close() 