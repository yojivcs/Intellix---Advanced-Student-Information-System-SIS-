import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database.schema import get_db_connection
from components.header import render_page_title
from datetime import datetime, timedelta

def show():
    """Display the admin dashboard"""
    render_page_title("📊", "Admin Dashboard")
    
    # Connect to database
    conn = get_db_connection()
    
    # Get active session
    active_session = get_active_session(conn)
    active_session_name = active_session['name'] if active_session else "No active session"
    
    st.write(f"**Active Academic Session:** {active_session_name}")
    
    # Create dashboard metrics (Top Row Widgets)
    col1, col2, col3, col4 = st.columns(4)
    
    # Total Students
    total_students = conn.execute("SELECT COUNT(*) as count FROM students").fetchone()['count']
    col1.metric("👨‍🎓 Total Students", total_students)
    
    # Total Teachers
    total_teachers = conn.execute("SELECT COUNT(*) as count FROM teachers").fetchone()['count']
    col2.metric("👩‍🏫 Total Teachers", total_teachers)
    
    # Total Courses
    total_courses = conn.execute("SELECT COUNT(*) as count FROM courses").fetchone()['count']
    col3.metric("📚 Total Courses", total_courses)
    
    # Active Enrollments
    if active_session:
        active_enrollments = conn.execute(
            "SELECT COUNT(*) as count FROM enrollments WHERE semester = ?", 
            (active_session_name,)
        ).fetchone()['count']
    else:
        active_enrollments = 0
    col4.metric("📖 Active Enrollments", active_enrollments)
    
    # Second row of metrics
    col1, col2, col3, col4 = st.columns(4)
    
    # At-Risk Students
    at_risk_query = """
    SELECT COUNT(DISTINCT s.id) as count
    FROM students s
    JOIN enrollments e ON s.id = e.student_id
    JOIN grades g ON s.id = g.student_id AND e.course_id = g.course_id
    WHERE (g.mid + g.assignment) < 40 AND g.final = 0
    """
    at_risk_students = conn.execute(at_risk_query).fetchone()['count']
    col1.metric("🚨 Students at Risk", at_risk_students, delta_color="inverse")
    
    # Average GPA
    avg_gpa_query = """
    SELECT AVG(
        CASE
            WHEN (g.mid + g.final) >= 80 THEN 4.0
            WHEN (g.mid + g.final) >= 75 THEN 3.75
            WHEN (g.mid + g.final) >= 70 THEN 3.5
            WHEN (g.mid + g.final) >= 65 THEN 3.25
            WHEN (g.mid + g.final) >= 60 THEN 3.0
            WHEN (g.mid + g.final) >= 55 THEN 2.75
            WHEN (g.mid + g.final) >= 50 THEN 2.5
            WHEN (g.mid + g.final) >= 45 THEN 2.25
            WHEN (g.mid + g.final) >= 40 THEN 2.0
            ELSE 0
        END
    ) as avg_gpa
    FROM grades g
    WHERE g.semester = ? AND g.final IS NOT NULL
    """
    if active_session:
        avg_gpa_data = conn.execute(avg_gpa_query, (active_session_name,)).fetchone()
        avg_gpa = avg_gpa_data['avg_gpa'] if avg_gpa_data and avg_gpa_data['avg_gpa'] else 0
    else:
        avg_gpa = 0
    col2.metric("📊 Average GPA", f"{avg_gpa:.2f}")
    
    # Pending evaluations
    pending_evals_query = """
    SELECT COUNT(*) as count FROM teaching 
    WHERE marks_finalized = 0 AND semester = ?
    """
    if active_session:
        pending_evals = conn.execute(pending_evals_query, (active_session_name,)).fetchone()['count']
    else:
        pending_evals = 0
    col3.metric("📝 Pending Evaluations", pending_evals)
    
    # Today's classes
    today = datetime.now().strftime("%A")  # Get current day name
    classes_today_query = """
    SELECT COUNT(*) as count FROM class_routine 
    WHERE day = ? AND session = ?
    """
    if active_session:
        classes_today = conn.execute(classes_today_query, (today, active_session_name,)).fetchone()
        classes_count = classes_today['count'] if classes_today else 0
    else:
        classes_count = 0
    col4.metric("🕑 Classes Today", classes_count)
    
    # Add spacing
    st.markdown("---")
    
    # Academic Activity Snapshots
    st.subheader("📅 Academic Activity Snapshots")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Upcoming exams
        st.write("**Upcoming Exam Events:**")
        if active_session:
            # Check if exam_schedule table exists and if exam_type column exists
            check_exam_type = """
            SELECT COUNT(*) as count FROM pragma_table_info('exam_schedule') 
            WHERE name = 'exam_type'
            """
            has_exam_type = conn.execute(check_exam_type).fetchone()['count'] > 0
            
            if has_exam_type:
                upcoming_exams_query = """
                SELECT e.exam_date, e.start_time, c.code, c.title, e.room, e.exam_type
                FROM exam_schedule e
                JOIN courses c ON e.course_id = c.id
                WHERE e.session = ? AND e.exam_date >= date('now')
                ORDER BY e.exam_date, e.start_time
                LIMIT 5
                """
                upcoming_exams = conn.execute(upcoming_exams_query, (active_session_name,)).fetchall()
                
                if upcoming_exams:
                    for exam in upcoming_exams:
                        st.write(f"📆 **{exam['exam_date']}** - {exam['code']} ({exam['exam_type']}) in Room {exam['room']} at {exam['start_time']}")
                else:
                    st.info("No upcoming exams scheduled.")
            else:
                # Fallback query without exam_type
                upcoming_exams_query = """
                SELECT e.exam_date, e.start_time, c.code, c.title, e.room
                FROM exam_schedule e
                JOIN courses c ON e.course_id = c.id
                WHERE e.session = ? AND e.exam_date >= date('now')
                ORDER BY e.exam_date, e.start_time
                LIMIT 5
                """
                upcoming_exams = conn.execute(upcoming_exams_query, (active_session_name,)).fetchall()
                
                if upcoming_exams:
                    for exam in upcoming_exams:
                        st.write(f"📆 **{exam['exam_date']}** - {exam['code']} in Room {exam['room']} at {exam['start_time']}")
                else:
                    st.info("No upcoming exams scheduled.")
                
                # Show message to run update_db.py
                st.warning("The exam_schedule table needs to be updated. Run update_db.py to add missing columns.")
        else:
            st.info("No active session to display exams.")
    
    with col2:
        # Today's classes
        st.write("**Classes Scheduled Today:**")
        if active_session:
            today_classes_query = """
            SELECT r.time_slot, c.code, c.title, t.name as teacher, r.room
            FROM class_routine r
            JOIN courses c ON r.course_id = c.id
            JOIN teachers t ON r.teacher_id = t.id
            WHERE r.day = ? AND r.session = ?
            ORDER BY r.time_slot
            """
            today_classes = conn.execute(today_classes_query, (today, active_session_name,)).fetchall()
            
            if today_classes:
                for class_info in today_classes:
                    st.write(f"🕒 **{class_info['time_slot']}** - {class_info['code']} ({class_info['teacher']}) in Room {class_info['room']}")
            else:
                st.info(f"No classes scheduled for {today}.")
        else:
            st.info("No active session to display classes.")
    
    # Visual Charts Section
    st.markdown("---")
    st.subheader("📈 Visual Charts Section")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Risk Distribution Pie Chart
        st.write("**Risk Distribution**")
        
        # Get risk distribution data
        risk_data_query = """
        SELECT 
            SUM(CASE WHEN (g.mid + g.assignment) < 30 THEN 1 ELSE 0 END) as failing,
            SUM(CASE WHEN (g.mid + g.assignment) BETWEEN 30 AND 40 THEN 1 ELSE 0 END) as at_risk,
            SUM(CASE WHEN (g.mid + g.assignment) > 40 OR g.mid IS NULL THEN 1 ELSE 0 END) as safe
        FROM students s
        JOIN enrollments e ON s.id = e.student_id
        LEFT JOIN grades g ON s.id = g.student_id AND e.course_id = g.course_id
        WHERE e.semester = ? OR ? IS NULL
        """
        
        if active_session:
            risk_data = conn.execute(risk_data_query, (active_session_name, active_session_name)).fetchone()
        else:
            risk_data = conn.execute(risk_data_query, (None, None)).fetchone()
        
        if risk_data:
            risk_labels = ['Safe', 'At Risk', 'Failing']
            risk_values = [risk_data['safe'], risk_data['at_risk'], risk_data['failing']]
            risk_colors = ['green', 'orange', 'red']
            
            fig = px.pie(
                names=risk_labels, 
                values=risk_values, 
                color=risk_labels,
                color_discrete_map={'Safe': 'green', 'At Risk': 'orange', 'Failing': 'red'},
                title="Student Risk Distribution"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No risk data available")
    
    with col2:
        # Course Load by Department
        st.write("**Course Load by Department**")
        dept_course_query = """
        SELECT c.dept, COUNT(DISTINCT co.id) as course_count
        FROM teachers c
        JOIN teaching t ON c.id = t.teacher_id
        JOIN courses co ON t.course_id = co.id
        WHERE t.semester = ? OR ? IS NULL
        GROUP BY c.dept
        ORDER BY course_count DESC
        """
        
        if active_session:
            dept_course_data = conn.execute(dept_course_query, (active_session_name, active_session_name)).fetchall()
        else:
            dept_course_data = conn.execute(dept_course_query, (None, None)).fetchall()
        
        if dept_course_data:
            # Convert to a list of dictionaries for proper column names
            dept_course_list = []
            for row in dept_course_data:
                dept_course_list.append({
                    "Department": row["dept"],
                    "Courses": row["course_count"]
                })
            df_dept_course = pd.DataFrame(dept_course_list)
            fig = px.bar(df_dept_course, x='Department', y='Courses', title="Course Load by Department")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No department course load data available")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Teacher Course Assignment Chart
        st.write("**Teacher Course Assignments**")
        teacher_course_query = """
        SELECT t.name, COUNT(te.course_id) as course_count
        FROM teachers t
        JOIN teaching te ON t.id = te.teacher_id
        WHERE te.semester = ? OR ? IS NULL
        GROUP BY t.id
        ORDER BY course_count DESC
        LIMIT 10
        """
        
        if active_session:
            teacher_course_data = conn.execute(teacher_course_query, (active_session_name, active_session_name)).fetchall()
        else:
            teacher_course_data = conn.execute(teacher_course_query, (None, None)).fetchall()
        
        if teacher_course_data:
            # Convert to a list of dictionaries for proper column names
            teacher_course_list = []
            for row in teacher_course_data:
                teacher_course_list.append({
                    "Teacher": row["name"],
                    "Courses": row["course_count"]
                })
            df_teacher_course = pd.DataFrame(teacher_course_list)
            fig = px.bar(df_teacher_course, x='Teacher', y='Courses', title="Teacher Course Assignments")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No teacher course assignment data available")
    
    with col2:
        # GPA Trend Line Chart (for demo, generate some sample data)
        st.write("**GPA Trend Across Sessions**")
        
        # Get all sessions
        sessions_query = "SELECT name FROM academic_sessions ORDER BY id DESC LIMIT 3"
        sessions = conn.execute(sessions_query).fetchall()
        
        if sessions:
            # Get average GPA for each session
            gpa_trend_data = []
            for session in sessions:
                session_name = session['name']
                avg_gpa_data = conn.execute(avg_gpa_query, (session_name,)).fetchone()
                session_gpa = avg_gpa_data['avg_gpa'] if avg_gpa_data and avg_gpa_data['avg_gpa'] else 0
                gpa_trend_data.append({
                    "Session": session_name,
                    "GPA": session_gpa
                })
            
            if gpa_trend_data:
                df_gpa_trend = pd.DataFrame(gpa_trend_data)
                fig = px.line(df_gpa_trend, x='Session', y='GPA', markers=True, title="GPA Trend")
                fig.update_layout(yaxis_range=[0, 4.0])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No GPA trend data available")
        else:
            st.info("Not enough sessions to display GPA trend")
    
    # Quick Access Modules
    st.markdown("---")
    st.subheader("🔎 Quick Access Modules")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Recent Registrations", "Course Assignments", "Top Performers", "AI Insights"])
    
    # Tab 1: Recent Student Registrations
    with tab1:
        st.write("**👥 Recent Student Registrations**")
        recent_students_query = """
        SELECT s.id, s.student_id, s.name, s.dept, s.admission_date, s.created_at
        FROM students s
        ORDER BY s.created_at DESC
        LIMIT 10
        """
        recent_students = conn.execute(recent_students_query).fetchall()
        
        if recent_students:
            student_data = []
            for student in recent_students:
                student_data.append({
                    "ID": student['student_id'],
                    "Name": student['name'],
                    "Department": student['dept'],
                    "Joined Date": student['admission_date'] or student['created_at']
                })
            
            st.dataframe(pd.DataFrame(student_data), use_container_width=True, hide_index=True)
        else:
            st.info("No recent student registrations")
    
    # Tab 2: Recent Teacher Assignments
    with tab2:
        st.write("**📦 Recent Teacher Assignments**")
        if active_session:
            recent_assignments_query = """
            SELECT t.name as teacher_name, c.code as course_code, c.title as course_title, 
                   t.dept as department, te.created_at
            FROM teaching te
            JOIN teachers t ON te.teacher_id = t.id
            JOIN courses c ON te.course_id = c.id
            WHERE te.semester = ?
            ORDER BY te.created_at DESC
            LIMIT 10
            """
            recent_assignments = conn.execute(recent_assignments_query, (active_session_name,)).fetchall()
            
            if recent_assignments:
                assignment_data = []
                for assignment in recent_assignments:
                    assignment_data.append({
                        "Teacher": assignment['teacher_name'],
                        "Course": f"{assignment['course_code']} - {assignment['course_title']}",
                        "Department": assignment['department'],
                        "Status": "Active"
                    })
                
                st.dataframe(pd.DataFrame(assignment_data), use_container_width=True, hide_index=True)
            else:
                st.info("No recent teacher assignments")
        else:
            st.info("No active session to display recent assignments")
    
    # Tab 3: Top 5 Highest GPA Students
    with tab3:
        st.write("**🧮 Top 5 Highest GPA Students**")
        if active_session:
            top_students_query = """
            SELECT s.name, s.student_id, s.dept,
                AVG(
                    CASE
                        WHEN (g.mid + g.final) >= 80 THEN 4.0
                        WHEN (g.mid + g.final) >= 75 THEN 3.75
                        WHEN (g.mid + g.final) >= 70 THEN 3.5
                        WHEN (g.mid + g.final) >= 65 THEN 3.25
                        WHEN (g.mid + g.final) >= 60 THEN 3.0
                        WHEN (g.mid + g.final) >= 55 THEN 2.75
                        WHEN (g.mid + g.final) >= 50 THEN 2.5
                        WHEN (g.mid + g.final) >= 45 THEN 2.25
                        WHEN (g.mid + g.final) >= 40 THEN 2.0
                        ELSE 0
                    END
                ) as gpa
            FROM students s
            JOIN enrollments e ON s.id = e.student_id
            JOIN grades g ON s.id = g.student_id AND e.course_id = g.course_id
            WHERE g.semester = ? AND g.final IS NOT NULL
            GROUP BY s.id
            ORDER BY gpa DESC
            LIMIT 5
            """
            top_students = conn.execute(top_students_query, (active_session_name,)).fetchall()
            
            if top_students:
                top_students_data = []
                for i, student in enumerate(top_students):
                    top_students_data.append({
                        "Rank": i + 1,
                        "Name": student['name'],
                        "ID": student['student_id'],
                        "Department": student['dept'],
                        "GPA": f"{student['gpa']:.2f}"
                    })
                
                st.dataframe(pd.DataFrame(top_students_data), use_container_width=True, hide_index=True)
            else:
                st.info("No GPA data available for students in this session")
        else:
            st.info("No active session to display top performers")
    
    # Tab 4: AI Study Plan Requests
    with tab4:
        st.write("**🧾 AI Study Plan Requests**")
        study_plan_query = """
        SELECT s.name, s.student_id, s.dept, sp.created_at
        FROM study_plans sp
        JOIN students s ON sp.student_id = s.id
        ORDER BY sp.created_at DESC
        LIMIT 10
        """
        study_plans = conn.execute(study_plan_query).fetchall()
        
        if study_plans:
            study_plan_data = []
            for plan in study_plans:
                study_plan_data.append({
                    "Student": plan['name'],
                    "ID": plan['student_id'],
                    "Department": plan['dept'],
                    "Date Requested": plan['created_at']
                })
            
            st.dataframe(pd.DataFrame(study_plan_data), use_container_width=True, hide_index=True)
        else:
            st.info("No AI study plan requests found")
    
    # Alerts & AI Insights
    st.markdown("---")
    st.subheader("⚠️ Alerts & AI Insights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**❗ Low Performance Alert Panel**")
        if active_session:
            low_performance_query = """
            SELECT s.id, s.name, s.student_id, c.code, c.title,
                (g.mid + g.assignment) as current_score,
                (50 - (g.mid + g.assignment)) as required_final
            FROM students s
            JOIN enrollments e ON s.id = e.student_id
            JOIN courses c ON e.course_id = c.id
            JOIN grades g ON s.id = g.student_id AND c.id = g.course_id
            WHERE e.semester = ? AND (g.mid + g.assignment) < 40 AND g.final = 0
            ORDER BY current_score ASC
            LIMIT 10
            """
            low_performance = conn.execute(low_performance_query, (active_session_name,)).fetchall()
            
            if low_performance:
                for student in low_performance:
                    required_final = max(0, student['required_final'])
                    
                    # Determine severity based on current score
                    if student['current_score'] < 20:
                        severity = "🔴 Critical"
                    elif student['current_score'] < 30:
                        severity = "🟠 High Risk"
                    else:
                        severity = "🟡 At Risk"
                    
                    st.error(
                        f"{severity}: {student['name']} ({student['student_id']}) - " +
                        f"{student['code']} - Current: {student['current_score']}/50, " +
                        f"Needs: {required_final}/50 on final"
                    )
            else:
                st.success("No students at risk in the current session. Great job!")
        else:
            st.info("No active session to display low performance alerts")
    
    with col2:
        st.write("**🤖 AI Suggestions Summary**")
        # For demo purposes, generate some AI insights
        if active_session and at_risk_students > 0:
            # Get departments with most at-risk students
            dept_risk_query = """
            SELECT s.dept, COUNT(DISTINCT s.id) as at_risk_count
            FROM students s
            JOIN enrollments e ON s.id = e.student_id
            JOIN grades g ON s.id = g.student_id AND e.course_id = g.course_id
            WHERE e.semester = ? AND (g.mid + g.assignment) < 40 AND g.final = 0
            GROUP BY s.dept
            ORDER BY at_risk_count DESC
            LIMIT 3
            """
            dept_risk = conn.execute(dept_risk_query, (active_session_name,)).fetchall()
            
            # Get courses with most at-risk students
            course_risk_query = """
            SELECT c.code, c.title, COUNT(DISTINCT s.id) as at_risk_count,
                   (COUNT(DISTINCT s.id) * 100.0 / 
                    (SELECT COUNT(*) FROM enrollments WHERE course_id = c.id AND semester = ?)) as percentage
            FROM students s
            JOIN enrollments e ON s.id = e.student_id
            JOIN courses c ON e.course_id = c.id
            JOIN grades g ON s.id = g.student_id AND c.id = g.course_id
            WHERE e.semester = ? AND (g.mid + g.assignment) < 40 AND g.final = 0
            GROUP BY c.id
            ORDER BY at_risk_count DESC
            LIMIT 3
            """
            course_risk = conn.execute(course_risk_query, (active_session_name, active_session_name)).fetchall()
            
            if dept_risk:
                st.info(f"👉 Department {dept_risk[0]['dept']} needs attention with {dept_risk[0]['at_risk_count']} at-risk students.")
            
            if course_risk:
                for course in course_risk:
                    st.info(f"👉 Consider additional support for {course['code']}. {course['percentage']:.1f}% of students are at risk.")
            
            st.info("👉 Schedule additional review sessions before final exams for at-risk students.")
        else:
            st.success("All students are performing well. No specific recommendations at this time.")
    
    # Quick Actions / Shortcuts
    st.markdown("---")
    st.subheader("🔄 Quick Actions / Shortcuts")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("➕ Add Student", use_container_width=True):
            st.session_state.current_page = "students"
            st.rerun()
    
    with col2:
        if st.button("➕ Add Teacher", use_container_width=True):
            st.session_state.current_page = "teachers"
            st.rerun()
    
    with col3:
        if st.button("➕ Add Course", use_container_width=True):
            st.session_state.current_page = "courses"
            st.rerun()
    
    with col4:
        if st.button("⚙️ Configure Routine", use_container_width=True):
            st.session_state.current_page = "academic_calendar"
            st.rerun()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🧠 Run GPA Prediction", use_container_width=True):
            st.session_state.current_page = "ai_tools"
            st.rerun()
    
    with col2:
        if st.button("📥 Bulk Import", use_container_width=True):
            st.session_state.current_page = "course_enrollment"
            st.rerun()
    
    with col3:
        if st.button("📤 Export Reports", use_container_width=True):
            st.info("Report generation feature will be added soon")
    
    with col4:
        if st.button("📊 View Analytics", use_container_width=True):
            st.session_state.current_page = "analytics"
            st.rerun()
    
    # Close connection
    conn.close()

def get_active_session(conn):
    """Get the active academic session"""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM academic_sessions WHERE is_active = 1")
    return cursor.fetchone() 