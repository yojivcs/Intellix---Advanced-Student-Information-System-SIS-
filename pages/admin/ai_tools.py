import streamlit as st
import pandas as pd
import plotly.express as px
from database.schema import get_db_connection
from components.header import render_page_title
from models.command_parser import parse_command, execute_command
from models.gpa_predictor import predict_gpa
from models.study_plan import generate_study_plan
from datetime import datetime, timedelta

def show():
    """Display the AI tools page"""
    render_page_title("🤖", "AI Tools")
    
    # Create tabs for different AI tools
    tab1, tab2, tab3, tab4 = st.tabs(["Command Assistant", "Risk Analysis", "GPA Predictor", "Study Plan Generator"])
    
    # Tab 1: Command Assistant (Enhanced)
    with tab1:
        st.subheader("AI Command Assistant")
        st.write("""
        Use natural language to perform administrative tasks. Examples:
        
        - "Assign student 101 to CSE303"
        - "Enroll students 101, 102 to courses CSE303, CSE304 for Fall 2023"
        - "Assign teacher 10 to CSE402"
        - "Show all students in CSE101"
        - "Move students from CSE201 to CSE202"
        - "Create a new course CSE450 - Advanced AI with 3 credit hours"
        """)
        
        # Add some quick command templates
        st.write("**Quick Command Templates:**")
        command_templates = [
            "Enroll student [ID] to [COURSE]",
            "Assign teacher [ID] to [COURSE]",
            "Create course [CODE] - [TITLE] with [N] credit hours",
            "Show all students with GPA below 2.5",
            "Move all students from [COURSE1] to [COURSE2]"
        ]
        
        selected_template = st.selectbox("Select a template", ["Select template..."] + command_templates)
        
        if selected_template != "Select template...":
            command_text = st.text_area("Edit command", selected_template, height=100)
        else:
            command_text = st.text_area("Enter your command", height=100)
        
        # Add voice input option
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("Parse Command", use_container_width=True):
                if command_text:
                    # Parse command
                    parsed_command = parse_command(command_text)
                    
                    if parsed_command["valid"]:
                        st.success(f"Command parsed successfully: {parsed_command['message']}")
                        
                        # Show command details
                        st.json(parsed_command)
                        
                        # Ask for confirmation
                        if st.button("Execute Command", type="primary"):
                            result = execute_command(parsed_command)
                            
                            if result["success"]:
                                st.success(result["message"])
                                
                                # Show operation details
                                if "details" in result:
                                    for detail in result["details"]:
                                        st.write(f"- {detail}")
                            else:
                                st.error(result["message"])
                                
                                # Show operation details
                                if "details" in result:
                                    for detail in result["details"]:
                                        st.write(f"- {detail}")
                    else:
                        st.error("Invalid command. Please check the examples and try again.")
                else:
                    st.warning("Please enter a command")
        
        with col2:
            st.button("🎤 Voice Input", use_container_width=True, help="Click to speak your command (not implemented yet)")
        
        # Command history
        with st.expander("Command History"):
            st.info("Recent commands will appear here after execution")
            # This would be populated from a database of previous commands
    
    # Tab 2: Risk Analysis (New)
    with tab2:
        st.subheader("AI-Powered Academic Risk Alerts")
        st.write("This tool identifies students at risk of academic failure and provides recommendations.")
        
        # Connect to database
        conn = get_db_connection()
        
        # Get active session
        active_session = conn.execute(
            "SELECT id, name FROM academic_sessions WHERE is_active = 1"
        ).fetchone()
        
        active_session_name = active_session['name'] if active_session else None
        
        if active_session_name:
            st.write(f"Analyzing risk factors for **{active_session_name}**")
            
            # Query for at-risk students
            risk_query = """
            SELECT s.id, s.student_id, s.name, s.dept,
                   COUNT(DISTINCT e.course_id) as total_courses,
                   SUM(CASE WHEN (g.mid + g.assignment) < 30 THEN 1 ELSE 0 END) as critical_courses,
                   SUM(CASE WHEN (g.mid + g.assignment) BETWEEN 30 AND 40 THEN 1 ELSE 0 END) as at_risk_courses,
                   AVG(CASE WHEN a.present IS NOT NULL THEN a.present ELSE NULL END) as avg_attendance
            FROM students s
            JOIN enrollments e ON s.id = e.student_id
            LEFT JOIN grades g ON s.id = g.student_id AND e.course_id = g.course_id AND g.semester = e.semester
            LEFT JOIN attendance a ON s.id = a.student_id AND e.course_id = a.course_id
            WHERE e.semester = ?
            GROUP BY s.id
            HAVING critical_courses > 0 OR at_risk_courses > 0 OR avg_attendance < 0.75
            ORDER BY critical_courses DESC, at_risk_courses DESC
            LIMIT 50
            """
            
            at_risk_students = conn.execute(risk_query, (active_session_name,)).fetchall()
            
            if at_risk_students:
                # Create risk dataframe
                risk_data = []
                
                for student in at_risk_students:
                    # Convert attendance to percentage
                    attendance_pct = round((student['avg_attendance'] or 0) * 100, 1)
                    
                    # Determine overall risk level
                    if student['critical_courses'] > 1:
                        risk_level = "Critical"
                        risk_color = "🔴"
                    elif student['critical_courses'] == 1 or student['at_risk_courses'] > 1:
                        risk_level = "High"
                        risk_color = "🟠"
                    else:
                        risk_level = "Moderate"
                        risk_color = "🟡"
                    
                    risk_data.append({
                        "Student ID": student['student_id'],
                        "Name": student['name'],
                        "Department": student['dept'],
                        "Risk Level": f"{risk_color} {risk_level}",
                        "Critical Courses": student['critical_courses'],
                        "At-Risk Courses": student['at_risk_courses'],
                        "Attendance": f"{attendance_pct}%",
                        "Student ID (DB)": student['id']  # Hidden column for reference
                    })
                
                # Display risk data
                df_risk = pd.DataFrame(risk_data)
                st.dataframe(df_risk.drop(columns=["Student ID (DB)"]), use_container_width=True, hide_index=True)
                
                # Risk distribution chart
                risk_counts = {
                    "Critical": len([r for r in risk_data if "Critical" in r["Risk Level"]]),
                    "High": len([r for r in risk_data if "High" in r["Risk Level"]]),
                    "Moderate": len([r for r in risk_data if "Moderate" in r["Risk Level"]])
                }
                
                fig = px.pie(
                    names=list(risk_counts.keys()),
                    values=list(risk_counts.values()),
                    title="Risk Distribution",
                    color=list(risk_counts.keys()),
                    color_discrete_map={"Critical": "red", "High": "orange", "Moderate": "gold"}
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Student details section
                st.subheader("Student Risk Details")
                
                selected_student_option = st.selectbox(
                    "Select a student to analyze:",
                    [f"{s['Student ID']} - {s['Name']}" for s in risk_data]
                )
                
                if selected_student_option:
                    selected_student_id = next(
                        (s["Student ID (DB)"] for s in risk_data 
                         if f"{s['Student ID']} - {s['Name']}" == selected_student_option),
                        None
                    )
                    
                    if selected_student_id:
                        # Get detailed course info for this student
                        course_query = """
                        SELECT c.code, c.title, c.credit_hour,
                               g.mid, g.assignment, g.final,
                               (SELECT COUNT(*) FROM attendance a 
                                WHERE a.student_id = ? AND a.course_id = c.id) as total_classes,
                               (SELECT COUNT(*) FROM attendance a 
                                WHERE a.student_id = ? AND a.course_id = c.id AND a.present = 1) as attended_classes
                        FROM enrollments e
                        JOIN courses c ON e.course_id = c.id
                        LEFT JOIN grades g ON e.student_id = g.student_id AND e.course_id = g.course_id AND e.semester = g.semester
                        WHERE e.student_id = ? AND e.semester = ?
                        """
                        
                        courses = conn.execute(
                            course_query, 
                            (selected_student_id, selected_student_id, selected_student_id, active_session_name)
                        ).fetchall()
                        
                        if courses:
                            course_data = []
                            intervention_needed = []
                            
                            for course in courses:
                                # Calculate attendance
                                attendance_pct = round(
                                    (course['attended_classes'] / course['total_classes'] * 100) 
                                    if course['total_classes'] > 0 else 0, 
                                    1
                                )
                                
                                # Calculate pre-final total
                                prefinal_total = (course['mid'] or 0) + (course['assignment'] or 0)
                                
                                # Calculate minimum final needed to pass (40%)
                                min_final_needed = max(0, 40 - prefinal_total)
                                
                                # Determine risk status
                                if prefinal_total < 30:
                                    risk_status = "🔴 Critical"
                                    intervention_needed.append({
                                        "course": course['code'],
                                        "reason": f"Very low score ({prefinal_total}/50)",
                                        "action": f"Needs at least {min_final_needed}/50 on final"
                                    })
                                elif prefinal_total < 40:
                                    risk_status = "🟠 At Risk"
                                    intervention_needed.append({
                                        "course": course['code'],
                                        "reason": f"Below passing threshold ({prefinal_total}/50)",
                                        "action": f"Needs at least {min_final_needed}/50 on final"
                                    })
                                else:
                                    risk_status = "✅ Good"
                                
                                # Check attendance
                                if attendance_pct < 75:
                                    attendance_status = "🔴 Low"
                                    if not any(i["course"] == course['code'] for i in intervention_needed):
                                        intervention_needed.append({
                                            "course": course['code'],
                                            "reason": f"Poor attendance ({attendance_pct}%)",
                                            "action": "Attendance improvement needed"
                                        })
                                else:
                                    attendance_status = "✅ Good"
                                
                                course_data.append({
                                    "Course": f"{course['code']} - {course['title']}",
                                    "Credits": course['credit_hour'],
                                    "Midterm": course['mid'] or 0,
                                    "Assignments": course['assignment'] or 0,
                                    "Pre-Final Total": prefinal_total,
                                    "Status": risk_status,
                                    "Attendance": f"{attendance_pct}% ({attendance_status})",
                                    "Min Final Needed": min_final_needed
                                })
                            
                            # Display course data
                            st.dataframe(pd.DataFrame(course_data), use_container_width=True, hide_index=True)
                            
                            # Intervention recommendations
                            if intervention_needed:
                                st.subheader("Recommended Interventions")
                                
                                for intervention in intervention_needed:
                                    st.warning(
                                        f"**{intervention['course']}**: {intervention['reason']} — {intervention['action']}"
                                    )
                                
                                st.subheader("Contact Options")
                                
                                contact_col1, contact_col2 = st.columns(2)
                                with contact_col1:
                                    if st.button("📧 Send Email Alert", use_container_width=True):
                                        st.success("Email alert drafted (feature pending)")
                                
                                with contact_col2:
                                    if st.button("📱 Send SMS Alert", use_container_width=True):
                                        st.success("SMS alert drafted (feature pending)")
                            
                            # Generate intervention plan
                            if st.button("Generate Intervention Plan", use_container_width=True):
                                st.subheader("AI-Generated Intervention Plan")
                                
                                student_name = next(
                                    (s['Name'] for s in risk_data 
                                     if f"{s['Student ID']} - {s['Name']}" == selected_student_option),
                                    "Student"
                                )
                                
                                # Get critical courses
                                critical_courses = [c for c in course_data if "Critical" in c["Status"]]
                                at_risk_courses = [c for c in course_data if "At Risk" in c["Status"]]
                                low_attendance = [c for c in course_data if "Low" in c["Attendance"]]
                                
                                st.markdown(f"""
                                ## Intervention Plan for {student_name}
                                
                                ### Assessment Summary
                                This student is currently at risk in {len(critical_courses) + len(at_risk_courses)} course(s) 
                                with {len(low_attendance)} course(s) showing attendance concerns.
                                
                                ### Recommended Actions
                                
                                1. **Academic Counseling**: Schedule an immediate academic counseling session to discuss:
                                   - Current academic standing
                                   - Study habits and time management
                                   - Resources available for assistance
                                
                                2. **Course-Specific Interventions**:
                                """)
                                
                                for course in critical_courses + at_risk_courses:
                                    course_name = course["Course"].split(" - ")[0]
                                    st.markdown(f"""
                                    - **{course_name}**: 
                                      - Assign a peer tutor
                                      - Provide supplementary materials
                                      - Schedule weekly check-ins with course instructor
                                      - Current marks: {course["Pre-Final Total"]}/50, needs {course["Min Final Needed"]}/50 on final
                                    """)
                                
                                st.markdown("""
                                3. **Attendance Improvement Plan**:
                                   - Set up attendance contract
                                   - Daily check-in system
                                   - Address barriers to attendance
                                
                                4. **Follow-up Timeline**:
                                   - Initial meeting: Within 48 hours
                                   - First progress check: 1 week
                                   - Comprehensive review: 2 weeks
                                """)
                            
                            # Show historical performance
                            with st.expander("View Historical Performance"):
                                st.info("Feature in development - will show performance trends across semesters")
                        else:
                            st.info("No course data available for this student")
                    else:
                        st.error("Student ID not found")
                
                # Bulk actions
                with st.expander("Bulk Actions"):
                    st.write("Apply interventions to multiple students at once")
                    
                    # Filter options
                    risk_filter = st.multiselect(
                        "Filter by risk level:",
                        ["Critical", "High", "Moderate"],
                        default=["Critical"]
                    )
                    
                    filtered_students = [
                        s for s in risk_data
                        if any(r in s["Risk Level"] for r in risk_filter)
                    ]
                    
                    st.write(f"Selected {len(filtered_students)} students")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("📧 Bulk Email Alert", use_container_width=True):
                            st.success(f"Email alerts drafted for {len(filtered_students)} students (feature pending)")
                    
                    with col2:
                        if st.button("📝 Generate Reports", use_container_width=True):
                            st.success(f"Reports generated for {len(filtered_students)} students (feature pending)")
            else:
                st.success("No students identified as academically at-risk. All students are performing well!")
        else:
            st.warning("No active academic session found. Please set an active session first.")
    
    # Tab 3: GPA Predictor
    with tab3:
        st.subheader("GPA Predictor")
        st.write("Predict student GPA based on current grades and attendance.")
        
        # Connect to database
        conn = get_db_connection()
        
        # Get all students
        students = conn.execute(
            "SELECT id, name FROM students ORDER BY name"
        ).fetchall()
        
        if students:
            # Select student
            selected_student_id = st.selectbox("Select Student", 
                                            [s['id'] for s in students],
                                            format_func=lambda x: next((s['name'] for s in students if s['id'] == x), ""))
            
            if selected_student_id:
                # Get student info
                student = next((s for s in students if s['id'] == selected_student_id), None)
                
                # Get all semesters for this student
                semesters = conn.execute(
                    "SELECT DISTINCT semester FROM enrollments WHERE student_id = ? ORDER BY semester DESC",
                    (selected_student_id,)
                ).fetchall()
                
                semester_list = [s['semester'] for s in semesters] if semesters else ["Current"]
                selected_semester = st.selectbox("Select Semester", semester_list)
                
                if st.button("Predict GPA", use_container_width=True):
                    with st.spinner("Calculating GPA prediction..."):
                        # Calculate prediction
                        predicted_gpa = predict_gpa(selected_student_id, selected_semester if selected_semester != "Current" else None)
                        
                        # Show prediction
                        st.metric("Predicted GPA", predicted_gpa)
                        
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
                        
                        semester_param = selected_semester if selected_semester != "Current" else semester_list[0] if semester_list else "Fall 2023"
                        courses = conn.execute(courses_query, (selected_student_id, selected_student_id, selected_student_id, semester_param)).fetchall()
                        
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
                            at_risk = [c for c in course_data if c['Total'] < 60 and c['Attendance'] < "75%"]
                            
                            if at_risk:
                                st.warning("At-risk courses identified:")
                                for course in at_risk:
                                    st.write(f"- {course['Course']} (Total: {course['Total']}, Attendance: {course['Attendance']})")
                        else:
                            st.info("No course data available for the selected semester")
        else:
            st.info("No students found in the database")
        
        conn.close()
    
    # Tab 4: Study Plan Generator
    with tab4:
        st.subheader("Study Plan Generator")
        st.write("Generate personalized study plans for students based on their performance.")
        
        # Connect to database
        conn = get_db_connection()
        
        # Get all students
        students = conn.execute(
            "SELECT id, name FROM students ORDER BY name"
        ).fetchall()
        
        if students:
            # Select student
            selected_student_id = st.selectbox("Select Student",
                                             [s['id'] for s in students],
                                             format_func=lambda x: next((s['name'] for s in students if s['id'] == x), ""),
                                             key="study_plan_student_select")
            
            if selected_student_id:
                # Get student info
                student = next((s for s in students if s['id'] == selected_student_id), None)
                
                # Get all semesters for this student
                semesters = conn.execute(
                    "SELECT DISTINCT semester FROM enrollments WHERE student_id = ? ORDER BY semester DESC",
                    (selected_student_id,)
                ).fetchall()
                
                semester_list = [s['semester'] for s in semesters] if semesters else ["Current"]
                selected_semester = st.selectbox("Select Semester", semester_list, key="study_plan_semester_select")
                
                if st.button("Generate Study Plan", use_container_width=True):
                    with st.spinner("Generating study plan..."):
                        # Generate plan
                        plan = generate_study_plan(selected_student_id, selected_semester if selected_semester != "Current" else None)
                        
                        if "error" in plan:
                            st.error(plan["error"])
                        else:
                            # Show plan
                            st.success(f"Study plan generated for {plan['student_name']}")
                            
                            # Show student info
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Student", plan['student_name'])
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
        else:
            st.info("No students found in the database")
        
        conn.close() 