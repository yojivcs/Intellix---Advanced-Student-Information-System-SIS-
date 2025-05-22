import streamlit as st
from components.header import render_page_title
from models.study_plan import generate_study_plan
from database.schema import get_db_connection
import pandas as pd

def show():
    """Display the student study plan page"""
    render_page_title("📚", "My Study Plan")
    
    # Get student ID from session
    student_id = st.session_state.user.get('user_id')
    
    if not student_id:
        st.error("Unable to identify student. Please log in again.")
        return
    
    # Connect to database
    conn = get_db_connection()
    
    # Get student info
    student = conn.execute(
        "SELECT name FROM students WHERE id = ?", 
        (student_id,)
    ).fetchone()
    
    if not student:
        st.error("Student record not found.")
        conn.close()
        return
    
    # Get student name from current session - this ensures correct name display
    student_name = st.session_state.user.get('name')
    
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
    
    # Check if a study plan already exists
    existing_plan = conn.execute(
        "SELECT id, plan_json FROM study_plans WHERE student_id = ? AND semester = ? ORDER BY created_at DESC LIMIT 1",
        (student_id, selected_semester)
    ).fetchone()
    
    if existing_plan:
        st.success("Your study plan is ready!")
        st.button("Generate New Plan", key="new_plan")
    else:
        st.info("You don't have a study plan for this semester yet.")
        generate_new = st.button("Generate Study Plan", key="first_plan")
        
        if generate_new:
            with st.spinner("Generating your personalized study plan..."):
                plan = generate_study_plan(student_id, selected_semester)
                
                if "error" in plan:
                    st.error(plan["error"])
                else:
                    st.rerun()
    
    # Display the study plan if it exists
    if existing_plan:
        import json
        plan = json.loads(existing_plan['plan_json'])
        
        # Show student info and GPA - use current user's name from session
        col1, col2, col3 = st.columns(3)
        col1.metric("Student", student_name)  # Use session name instead of plan['student_name']
        col2.metric("Semester", plan['semester'])
        col3.metric("Current GPA", plan['current_gpa'])
        
        # Show course analysis
        st.subheader("Course Analysis")
        
        course_data = []
        for course in plan['course_analysis']:
            course_data.append({
                "Course": f"{course['code']} - {course['title']}",
                "Status": course['status'],
                "Priority": course['priority'],
                "Attendance": f"{course['attendance']}%" if course['attendance'] is not None else "N/A",
                "Total Score": course['total_score']
            })
        
        df = pd.DataFrame(course_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Show weekly plan
        st.subheader("Weekly Study Plan")
        
        for day_plan in plan['weekly_plan']:
            if day_plan['study_blocks']:
                with st.expander(f"{day_plan['day']} ({day_plan['date']})"):
                    for block in day_plan['study_blocks']:
                        st.write(f"**{block['time']}**: {block['course']} - {block['focus']}")
        
        # Show general recommendations
        st.subheader("General Recommendations")
        for rec in plan['general_recommendations']:
            st.write(f"- {rec}")
    
    conn.close() 