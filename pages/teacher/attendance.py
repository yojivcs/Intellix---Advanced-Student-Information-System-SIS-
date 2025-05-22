import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import calendar
from components.header import render_page_title
from database.schema import get_db_connection

def show():
    """Display the teacher attendance management page"""
    render_page_title("✅", "Attendance Management")
    
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
    
    # Create tabs for mark attendance and view records
    mark_tab, view_tab, analytics_tab = st.tabs(["Mark Attendance", "View Records", "Attendance Analytics"])
    
    # Tab 1: Mark Attendance
    with mark_tab:
        st.write("### Mark Attendance")
        
        # Select a course
        course_options = {f"{c['code']} - {c['title']}": c['id'] for c in courses}
        selected_course_name = st.selectbox(
            "Select Course:", 
            options=list(course_options.keys()),
            key="mark_attendance_course"
        )
        
        selected_course_id = course_options[selected_course_name]
        
        # Select date
        today = datetime.now().date()
        selected_date = st.date_input(
            "Select Date:", 
            value=today,
            max_value=today
        )
        
        # Format the date for display
        formatted_date = selected_date.strftime("%Y-%m-%d")
        
        # Get enrolled students for the selected course
        students = conn.execute("""
            SELECT s.id, s.student_id, s.name,
                   (SELECT present FROM attendance 
                    WHERE student_id = s.id AND course_id = ? AND date = ?) as is_present
            FROM students s
            JOIN enrollments e ON s.id = e.student_id
            WHERE e.course_id = ? AND e.semester = ?
            ORDER BY s.name
        """, (selected_course_id, formatted_date, selected_course_id, session_name)).fetchall()
        
        if not students:
            st.info(f"No students enrolled in {selected_course_name} for the {session_name} session.")
            return
        
        # Check if attendance was already marked for this course and date
        attendance_exists = conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE course_id = ? AND date = ?",
            (selected_course_id, formatted_date)
        ).fetchone()[0]
        
        # Create a form for attendance submission
        with st.form("attendance_form"):
            st.write(f"#### Mark Attendance for {selected_course_name} on {formatted_date}")
            
            # Create columns for the attendance checkboxes
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                st.write("**Student ID**")
                for student in students:
                    st.write(student['student_id'])
            
            with col2:
                st.write("**Student Name**")
                for student in students:
                    st.write(student['name'])
            
            with col3:
                st.write("**Present**")
                
                # Store the attendance status in a dictionary
                attendance_status = {}
                
                for i, student in enumerate(students):
                    # Default to present (True) if new, otherwise use existing value
                    default_value = True if student['is_present'] is None else bool(student['is_present'])
                    attendance_status[student['id']] = st.checkbox(
                        f"Present_{student['id']}",
                        value=default_value,
                        label_visibility="collapsed",
                        key=f"attendance_{student['id']}_{formatted_date}"
                    )
            
            # Add a "Mark All Present" button
            if st.checkbox("Mark All Present"):
                for student in students:
                    attendance_status[student['id']] = True
            
            # Submit button
            submit_button = st.form_submit_button("Save Attendance")
            
            if submit_button:
                # Delete existing attendance records for this date and course
                conn.execute(
                    "DELETE FROM attendance WHERE course_id = ? AND date = ?",
                    (selected_course_id, formatted_date)
                )
                
                # Insert new attendance records
                for student_id, is_present in attendance_status.items():
                    conn.execute(
                        "INSERT INTO attendance (student_id, course_id, date, present) VALUES (?, ?, ?, ?)",
                        (student_id, selected_course_id, formatted_date, 1 if is_present else 0)
                    )
                
                conn.commit()
                st.success(f"Attendance for {selected_course_name} on {formatted_date} has been saved!")
                st.rerun()
        
        # Display additional information
        if attendance_exists > 0:
            st.info(f"Attendance for {selected_course_name} on {formatted_date} has already been marked. You can update it if needed.")
        
        # Quick stats
        total_students = len(students)
        present_students = sum(1 for s in students if s['is_present'] == 1)
        absent_students = sum(1 for s in students if s['is_present'] == 0)
        
        if attendance_exists > 0:
            st.write(f"**Total Students:** {total_students}")
            st.write(f"**Present:** {present_students}")
            st.write(f"**Absent:** {absent_students}")
    
    # Tab 2: View Attendance Records
    with view_tab:
        st.write("### View Attendance Records")
        
        # Select a course
        course_options = {f"{c['code']} - {c['title']}": c['id'] for c in courses}
        selected_course_name = st.selectbox(
            "Select Course:", 
            options=list(course_options.keys()),
            key="view_attendance_course"
        )
        
        selected_course_id = course_options[selected_course_name]
        
        # Get dates with attendance records
        attendance_dates = conn.execute("""
            SELECT DISTINCT date
            FROM attendance
            WHERE course_id = ?
            ORDER BY date DESC
        """, (selected_course_id,)).fetchall()
        
        if not attendance_dates:
            st.info(f"No attendance records found for {selected_course_name}.")
            return
        
        # Select date or calendar view
        view_type = st.radio("View Type:", ["By Date", "Calendar View"])
        
        if view_type == "By Date":
            # Select a date from the available records
            date_options = [d['date'] for d in attendance_dates]
            selected_date = st.selectbox(
                "Select Date:", 
                options=date_options,
                key="view_attendance_date"
            )
            
            # Get attendance for the selected date
            attendance_records = conn.execute("""
                SELECT s.id, s.student_id, s.name, a.present
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                WHERE a.course_id = ? AND a.date = ?
                ORDER BY s.name
            """, (selected_course_id, selected_date)).fetchall()
            
            # Create a DataFrame for display
            attendance_data = []
            for record in attendance_records:
                attendance_data.append({
                    "Student ID": record['student_id'],
                    "Name": record['name'],
                    "Status": "Present" if record['present'] == 1 else "Absent"
                })
            
            attendance_df = pd.DataFrame(attendance_data)
            
            # Display attendance records
            st.write(f"#### Attendance for {selected_date}")
            st.dataframe(attendance_df, use_container_width=True, hide_index=True)
            
            # Calculate attendance statistics
            total_students = len(attendance_records)
            present_students = sum(1 for r in attendance_records if r['present'] == 1)
            absent_students = sum(1 for r in attendance_records if r['present'] == 0)
            attendance_rate = (present_students / total_students) * 100 if total_students > 0 else 0
            
            st.write(f"**Attendance Rate:** {attendance_rate:.1f}%")
            st.write(f"**Present:** {present_students} students")
            st.write(f"**Absent:** {absent_students} students")
            
        else:  # Calendar View
            st.write("#### Attendance Calendar View")
            
            # Get all enrolled students for the selected course
            students = conn.execute("""
                SELECT s.id, s.student_id, s.name
                FROM students s
                JOIN enrollments e ON s.id = e.student_id
                WHERE e.course_id = ? AND e.semester = ?
                ORDER BY s.name
            """, (selected_course_id, session_name)).fetchall()
            
            # Get all attendance records for the selected course
            all_attendance = conn.execute("""
                SELECT a.student_id, a.date, a.present
                FROM attendance a
                WHERE a.course_id = ?
                ORDER BY a.date
            """, (selected_course_id,)).fetchall()
            
            # Create a lookup dictionary for attendance status
            attendance_lookup = {}
            for att in all_attendance:
                student_id = att['student_id']
                date = att['date']
                present = att['present']
                
                if student_id not in attendance_lookup:
                    attendance_lookup[student_id] = {}
                
                attendance_lookup[student_id][date] = present
            
            # Select a student to view calendar
            student_options = {f"{s['student_id']} - {s['name']}": s['id'] for s in students}
            selected_student_name = st.selectbox(
                "Select Student:", 
                options=list(student_options.keys()),
                key="view_calendar_student"
            )
            
            selected_student_id = student_options[selected_student_name]
            
            # Get attendance records for the selected student
            student_attendance = [a for a in all_attendance if a['student_id'] == selected_student_id]
            
            if not student_attendance:
                st.info(f"No attendance records found for this student in {selected_course_name}.")
            else:
                # Build attendance calendar
                # First, get the range of dates
                min_date = min(datetime.strptime(a['date'], '%Y-%m-%d').date() for a in student_attendance)
                max_date = max(datetime.strptime(a['date'], '%Y-%m-%d').date() for a in student_attendance)
                
                # Create a monthly calendar view
                for month_offset in range(0, (max_date.year - min_date.year) * 12 + max_date.month - min_date.month + 1):
                    month_date = min_date.replace(day=1) + timedelta(days=32 * month_offset)
                    month_date = month_date.replace(day=1)
                    
                    # Display month header
                    st.write(f"##### {month_date.strftime('%B %Y')}")
                    
                    # Get calendar for this month
                    cal = calendar.monthcalendar(month_date.year, month_date.month)
                    
                    # Create a table for this month
                    headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    
                    # Convert calendar data to format for display
                    rows = []
                    for week in cal:
                        row = []
                        for day in week:
                            if day == 0:
                                # Empty cell for days not in this month
                                row.append("")
                            else:
                                # Create date string for this day
                                date_str = f"{month_date.year}-{month_date.month:02d}-{day:02d}"
                                
                                # Check if attendance was marked for this date
                                if selected_student_id in attendance_lookup and date_str in attendance_lookup[selected_student_id]:
                                    present = attendance_lookup[selected_student_id][date_str]
                                    if present == 1:
                                        row.append(f"{day} ✅")
                                    else:
                                        row.append(f"{day} ❌")
                                else:
                                    row.append(str(day))
                        rows.append(row)
                    
                    # Create a DataFrame for the calendar
                    calendar_df = pd.DataFrame(rows, columns=headers)
                    st.dataframe(calendar_df, use_container_width=True, hide_index=True)
                
                # Calculate attendance statistics for this student
                total_days = len(student_attendance)
                present_days = sum(1 for a in student_attendance if a['present'] == 1)
                absent_days = sum(1 for a in student_attendance if a['present'] == 0)
                attendance_rate = (present_days / total_days) * 100 if total_days > 0 else 0
                
                st.write(f"**Attendance Summary for {selected_student_name}:**")
                st.write(f"- Total Classes: {total_days}")
                st.write(f"- Present: {present_days} ({attendance_rate:.1f}%)")
                st.write(f"- Absent: {absent_days} ({100-attendance_rate:.1f}%)")
                
                if attendance_rate < 75:
                    st.warning("⚠️ This student's attendance is below 75%, which may impact their academic standing.")
    
    # Tab 3: Attendance Analytics
    with analytics_tab:
        st.write("### Attendance Analytics")
        
        # Select a course
        course_options = {f"{c['code']} - {c['title']}": c['id'] for c in courses}
        selected_course_name = st.selectbox(
            "Select Course:", 
            options=list(course_options.keys()),
            key="analytics_course"
        )
        
        selected_course_id = course_options[selected_course_name]
        
        # Get attendance data for the selected course
        attendance_data = conn.execute("""
            SELECT s.id, s.student_id, s.name, a.date, a.present
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.course_id = ?
            ORDER BY a.date, s.name
        """, (selected_course_id,)).fetchall()
        
        if not attendance_data:
            st.info(f"No attendance data available for {selected_course_name}.")
            return
        
        # Create columns for different analytics
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("#### Overall Attendance Rate")
            
            # Calculate overall attendance rate
            total_records = len(attendance_data)
            present_records = sum(1 for r in attendance_data if r['present'] == 1)
            overall_rate = (present_records / total_records) * 100 if total_records > 0 else 0
            
            st.metric("Overall Attendance", f"{overall_rate:.1f}%")
            
            # Create attendance data by date
            date_attendance = {}
            for record in attendance_data:
                date = record['date']
                present = record['present']
                
                if date not in date_attendance:
                    date_attendance[date] = {'total': 0, 'present': 0}
                
                date_attendance[date]['total'] += 1
                if present == 1:
                    date_attendance[date]['present'] += 1
            
            # Convert to DataFrame for chart
            date_df = pd.DataFrame([
                {
                    'Date': date,
                    'Attendance Rate': (data['present'] / data['total']) * 100 if data['total'] > 0 else 0
                }
                for date, data in date_attendance.items()
            ])
            
            # Sort by date
            date_df['Date'] = pd.to_datetime(date_df['Date'])
            date_df = date_df.sort_values('Date')
            
            # Plot attendance trend
            st.write("#### Attendance Trend")
            st.line_chart(date_df.set_index('Date'))
        
        with col2:
            st.write("#### Student Attendance Rates")
            
            # Calculate attendance rate by student
            student_attendance = {}
            for record in attendance_data:
                student_id = record['student_id']
                student_name = record['name']
                present = record['present']
                
                if student_id not in student_attendance:
                    student_attendance[student_id] = {
                        'name': student_name,
                        'total': 0,
                        'present': 0
                    }
                
                student_attendance[student_id]['total'] += 1
                if present == 1:
                    student_attendance[student_id]['present'] += 1
            
            # Convert to DataFrame for display
            student_df = pd.DataFrame([
                {
                    'Student ID': student_id,
                    'Name': data['name'],
                    'Classes Attended': data['present'],
                    'Total Classes': data['total'],
                    'Attendance Rate': (data['present'] / data['total']) * 100 if data['total'] > 0 else 0
                }
                for student_id, data in student_attendance.items()
            ])
            
            # Sort by attendance rate
            student_df = student_df.sort_values('Attendance Rate')
            
            # Display student attendance rates
            st.dataframe(student_df, use_container_width=True, hide_index=True)
        
        # Student attendance heatmap
        st.write("#### Attendance Heatmap")
        
        # Convert attendance data to wide format for heatmap
        heatmap_data = []
        for record in attendance_data:
            heatmap_data.append({
                'Student': f"{record['student_id']} - {record['name']}",
                'Date': record['date'],
                'Present': record['present']
            })
        
        heatmap_df = pd.DataFrame(heatmap_data)
        
        # Convert to wide format
        heatmap_wide = heatmap_df.pivot(index='Student', columns='Date', values='Present')
        
        # Fill missing values with NaN
        heatmap_wide = heatmap_wide.fillna(-1)  # -1 means no record (not marked)
        
        # Create a custom color scale
        color_scale = [
            (0, 'red'),     # 0 (absent) as red
            (0.5, 'gray'),  # -1 (not marked) as gray
            (1, 'green')    # 1 (present) as green
        ]
        
        # Display the heatmap
        fig = px.imshow(
            heatmap_wide,
            labels=dict(x="Date", y="Student", color="Attendance"),
            color_continuous_scale=color_scale,
            range_color=[-1, 1]
        )
        
        # Update layout
        fig.update_layout(
            height=500, 
            margin=dict(l=50, r=50, b=100, t=50),
            xaxis_side="top"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Identify chronically absent students
        st.write("#### Chronically Absent Students")
        
        # Filter students with attendance rate below 75%
        at_risk_students = student_df[student_df['Attendance Rate'] < 75].copy()
        
        if not at_risk_students.empty:
            at_risk_students = at_risk_students.sort_values('Attendance Rate')
            
            # Add a risk level column
            at_risk_students['Risk Level'] = 'Low'
            at_risk_students.loc[at_risk_students['Attendance Rate'] < 60, 'Risk Level'] = 'Medium'
            at_risk_students.loc[at_risk_students['Attendance Rate'] < 50, 'Risk Level'] = 'High'
            
            # Display the at-risk students
            st.dataframe(at_risk_students, use_container_width=True, hide_index=True)
            
            # AI insights for chronically absent students
            st.write("#### AI Insights")
            
            high_risk_count = sum(at_risk_students['Risk Level'] == 'High')
            medium_risk_count = sum(at_risk_students['Risk Level'] == 'Medium')
            
            if high_risk_count > 0:
                st.error(f"🔴 {high_risk_count} students have critically low attendance (below 50%). Consider scheduling meetings with these students.")
            
            if medium_risk_count > 0:
                st.warning(f"🟠 {medium_risk_count} students have attendance between 50-60%. Monitor their progress closely.")
            
            # Correlation between attendance and grades if available
            grades_data = conn.execute("""
                SELECT g.student_id, AVG(g.mid + g.assignment + g.final) as avg_grade
                FROM grades g
                WHERE g.course_id = ? AND g.semester = ?
                GROUP BY g.student_id
            """, (selected_course_id, session_name)).fetchall()
            
            if grades_data:
                # Create a dictionary of student grades
                student_grades = {g['student_id']: g['avg_grade'] for g in grades_data}
                
                # Add grades to the student attendance DataFrame
                correlation_data = []
                for student_id, data in student_attendance.items():
                    if student_id in student_grades:
                        correlation_data.append({
                            'Attendance Rate': (data['present'] / data['total']) * 100 if data['total'] > 0 else 0,
                            'Grade': student_grades[student_id]
                        })
                
                if correlation_data:
                    correlation_df = pd.DataFrame(correlation_data)
                    
                    # Calculate correlation
                    correlation = correlation_df['Attendance Rate'].corr(correlation_df['Grade'])
                    
                    st.write("#### Attendance-Grade Correlation")
                    
                    # Plot scatter chart
                    fig = px.scatter(
                        correlation_df,
                        x='Attendance Rate',
                        y='Grade',
                        trendline='ols',
                        labels={'Attendance Rate': 'Attendance Rate (%)', 'Grade': 'Average Grade (/100)'}
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.write(f"**Correlation Coefficient:** {correlation:.2f}")
                    
                    if correlation > 0.7:
                        st.success("There is a strong positive correlation between attendance and grades in this course.")
                    elif correlation > 0.4:
                        st.info("There is a moderate correlation between attendance and grades in this course.")
                    else:
                        st.info("There appears to be a weak correlation between attendance and grades in this course.")
        else:
            st.success("No students are chronically absent. Great job!")
    
    # Close the database connection
    conn.close() 