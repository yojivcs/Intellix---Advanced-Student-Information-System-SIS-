import streamlit as st
import pandas as pd
import plotly.express as px
from components.header import render_page_title
from database.schema import get_db_connection

def show():
    """Display the student attendance page with tracking and alerts"""
    render_page_title("📅", "My Attendance")
    
    # Get user ID from session
    student_id = st.session_state.user.get('user_id')
    
    # Connect to database
    conn = get_db_connection()
    
    # Get student information
    student = conn.execute(
        "SELECT * FROM students WHERE id = ?", (student_id,)
    ).fetchone()
    
    if not student:
        st.error("Student profile not found. Please contact an administrator.")
        return
    
    # Get current active session
    active_session = conn.execute(
        "SELECT name FROM academic_sessions WHERE is_active = 1"
    ).fetchone()
    
    if not active_session:
        st.warning("No active academic session. Please contact an administrator.")
        return
    
    session_name = active_session['name']
    
    # Get all sessions for selection
    all_sessions = conn.execute(
        "SELECT name FROM academic_sessions ORDER BY name DESC"
    ).fetchall()
    
    session_options = [session['name'] for session in all_sessions]
    
    # Session selector
    selected_session = st.selectbox(
        "Select Academic Session:",
        options=session_options,
        index=session_options.index(session_name) if session_name in session_options else 0
    )
    
    st.write(f"**Viewing attendance for:** {selected_session}")
    
    # Get enrolled courses for the selected session
    enrolled_courses = conn.execute("""
        SELECT c.id, c.code, c.title
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ? AND e.semester = ?
        ORDER BY c.code
    """, (student_id, selected_session)).fetchall()
    
    if not enrolled_courses:
        st.info(f"You are not enrolled in any courses for the {selected_session} session.")
        return
    
    # Overall attendance summary
    st.write("## Overall Attendance Summary")
    
    # Get overall attendance for all courses
    overall_attendance = conn.execute("""
        SELECT c.code, c.title, COUNT(*) as total_classes, SUM(a.present) as attended_classes
        FROM attendance a
        JOIN courses c ON a.course_id = c.id
        WHERE a.student_id = ? AND c.id IN (
            SELECT course_id FROM enrollments 
            WHERE student_id = ? AND semester = ?
        )
        GROUP BY c.id
        ORDER BY c.code
    """, (student_id, student_id, selected_session)).fetchall()
    
    if overall_attendance:
        # Calculate attendance percentages and create summary table
        attendance_summary = []
        
        for course in overall_attendance:
            code = course['code']
            title = course['title']
            total_classes = course['total_classes']
            attended_classes = course['attended_classes'] or 0
            
            if total_classes > 0:
                attendance_rate = (attended_classes / total_classes) * 100
                
                # Determine status based on attendance rate
                status = "Critical"
                if attendance_rate >= 85:
                    status = "Excellent"
                elif attendance_rate >= 75:
                    status = "Good"
                elif attendance_rate >= 60:
                    status = "Average"
                elif attendance_rate >= 50:
                    status = "Poor"
                
                attendance_summary.append({
                    "Course": f"{code} - {title}",
                    "Total Classes": total_classes,
                    "Classes Attended": attended_classes,
                    "Attendance Rate": f"{attendance_rate:.1f}%",
                    "Status": status
                })
        
        if attendance_summary:
            # Convert to DataFrame and display
            summary_df = pd.DataFrame(attendance_summary)
            
            # Use custom formatting for the Status column
            formatted_df = summary_df.copy()
            
            # Display the table
            st.dataframe(
                formatted_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Attendance Rate": st.column_config.ProgressColumn(
                        "Attendance Rate",
                        help="Percentage of classes attended",
                        format="%{} completed",
                        min_value=0,
                        max_value=100,
                    ),
                    "Status": st.column_config.TextColumn(
                        "Status",
                        help="Attendance status",
                    )
                }
            )
            
            # Create attendance visualization
            st.write("### Attendance Visualization")
            
            # Prepare data for chart
            chart_data = []
            for course in attendance_summary:
                chart_data.append({
                    "Course": course["Course"].split(" - ")[0],
                    "Attendance Rate": float(course["Attendance Rate"].strip("%"))
                })
            
            chart_df = pd.DataFrame(chart_data)
            
            # Create a bar chart
            fig = px.bar(
                chart_df, 
                x="Course", 
                y="Attendance Rate",
                text="Attendance Rate",
                color="Attendance Rate",
                color_continuous_scale=["red", "orange", "green"],
                range_color=[0, 100],
                title="Attendance Rate by Course"
            )
            
            fig.update_traces(texttemplate="%{y:.1f}%", textposition="outside")
            fig.update_layout(yaxis_range=[0, 105])
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Display attendance alerts
            st.write("## Attendance Alerts")
            
            # Filter courses with attendance issues
            low_attendance = [course for course in attendance_summary if float(course["Attendance Rate"].strip("%")) < 75]
            
            if low_attendance:
                for course in low_attendance:
                    attendance_rate = float(course["Attendance Rate"].strip("%"))
                    course_name = course["Course"]
                    
                    if attendance_rate < 50:
                        st.error(f"🔴 **Critical Alert:** Your attendance in {course_name} is dangerously low at {attendance_rate:.1f}%. You may be barred from the final exam.")
                    elif attendance_rate < 60:
                        st.warning(f"🟠 **Warning:** Your attendance in {course_name} is very low at {attendance_rate:.1f}%. Please improve to avoid academic penalties.")
                    elif attendance_rate < 75:
                        st.warning(f"🟡 **Caution:** Your attendance in {course_name} is below recommended at {attendance_rate:.1f}%. Try to attend more classes.")
            else:
                st.success("👍 Your attendance is satisfactory in all courses. Keep it up!")
    else:
        st.info("No attendance records found for the selected session.")
    
    # Detailed attendance records
    st.write("## Detailed Attendance Records")
    
    # Course selector
    course_options = {f"{c['code']} - {c['title']}": c['id'] for c in enrolled_courses}
    selected_course_name = st.selectbox("Select Course:", options=list(course_options.keys()))
    selected_course_id = course_options[selected_course_name]
    
    # Get detailed attendance records for the selected course
    attendance_records = conn.execute("""
        SELECT a.date, a.present
        FROM attendance a
        WHERE a.student_id = ? AND a.course_id = ?
        ORDER BY a.date DESC
    """, (student_id, selected_course_id)).fetchall()
    
    if attendance_records:
        # Create attendance detail table
        attendance_details = []
        
        for record in attendance_records:
            attendance_details.append({
                "Date": record['date'],
                "Status": "Present" if record['present'] else "Absent"
            })
        
        # Display detailed records
        st.dataframe(
            pd.DataFrame(attendance_details),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn(
                    "Status",
                    help="Attendance status",
                ),
                "Date": st.column_config.DateColumn(
                    "Date",
                    help="Class date",
                    format="YYYY-MM-DD"
                )
            }
        )
        
        # Calculate attendance stats for selected course
        total_classes = len(attendance_records)
        attended_classes = sum(1 for record in attendance_records if record['present'])
        attendance_percentage = (attended_classes / total_classes) * 100 if total_classes > 0 else 0
        
        # Display attendance rate
        st.write(f"**Attendance Rate for {selected_course_name}:** {attendance_percentage:.1f}%")
        
        # Progress bar for visual representation
        st.progress(attendance_percentage / 100)
        
        # Display appropriate message based on attendance rate
        if attendance_percentage < 50:
            st.error("⚠️ Your attendance is critically low for this course. Please attend classes regularly.")
        elif attendance_percentage < 75:
            st.warning("⚠️ Your attendance needs improvement. Try to attend more classes.")
        else:
            st.success("✅ Your attendance is good. Keep it up!")
    else:
        st.info("No attendance records found for the selected course.")
    
    # Close database connection
    conn.close() 