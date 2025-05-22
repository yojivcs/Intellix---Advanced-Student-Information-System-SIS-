import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database.schema import get_db_connection
from components.header import render_page_title

def show():
    """Display the academic calendar and routine planning page"""
    render_page_title("📅", "Academic Calendar & Routine Planning")
    
    # Initialize database connection
    conn = get_db_connection()
    
    # Ensure tables exist
    create_routine_table_if_not_exists(conn)
    create_exam_schedule_table_if_not_exists(conn)
    
    # Create tabs for different functionality
    tab1, tab2 = st.tabs(["Class Routine", "Exam Schedule"])
    
    # Tab 1: Class Routine
    with tab1:
        st.subheader("Weekly Class Routine")
        
        # Get active session
        active_session = get_active_session(conn)
        
        if not active_session:
            st.warning("No active academic session. Please set an active session in the Course Assignment and Enrollment page.")
            return
            
        st.write(f"**Current Active Session:** {active_session['name']}")
        
        # Get all courses with assigned teachers for the active session
        courses_with_teachers = get_courses_with_teachers(conn, active_session['name'])
        
        if not courses_with_teachers:
            st.warning("No courses with assigned teachers found. Please assign teachers to courses first.")
            return
        
        # Initialize or load existing routine
        routine_exists = check_routine_exists(conn, active_session['name'])
        
        col1, col2 = st.columns([3, 1])
        
        with col2:
            st.write("**Actions:**")
            
            if routine_exists:
                if st.button("Generate New Routine", type="primary"):
                    # Delete existing routine
                    delete_existing_routine(conn, active_session['name'])
                    # Generate new routine
                    generate_routine(conn, courses_with_teachers, active_session['name'])
                    st.success("New routine generated successfully!")
                    st.rerun()
            else:
                if st.button("Generate Routine", type="primary"):
                    # Generate new routine
                    generate_routine(conn, courses_with_teachers, active_session['name'])
                    st.success("Routine generated successfully!")
                    st.rerun()
        
        with col1:
            # Display the routine
            if routine_exists:
                display_routine(conn, active_session['name'])
            else:
                st.info("No routine has been generated yet. Click 'Generate Routine' to create one.")
    
    # Tab 2: Exam Schedule
    with tab2:
        st.subheader("Exam Schedule Planning")
        
        # Get active session
        active_session = get_active_session(conn)
        
        if not active_session:
            st.warning("No active academic session. Please set an active session in the Course Assignment and Enrollment page.")
            return
            
        st.write(f"**Current Active Session:** {active_session['name']}")
        
        # Get all courses for the active session
        courses = get_all_courses(conn)
        
        if not courses:
            st.warning("No courses found. Please add courses first.")
            return
        
        # Initialize or load existing exam schedule
        exam_schedule_exists = check_exam_schedule_exists(conn, active_session['name'])
        
        col1, col2 = st.columns([3, 1])
        
        with col2:
            st.write("**Actions:**")
            
            if exam_schedule_exists:
                if st.button("Generate New Exam Schedule", type="primary"):
                    # Delete existing exam schedule
                    delete_existing_exam_schedule(conn, active_session['name'])
                    # Generate new exam schedule
                    generate_exam_schedule(conn, courses, active_session['name'])
                    st.success("New exam schedule generated successfully!")
                    st.rerun()
            else:
                if st.button("Generate Exam Schedule", type="primary"):
                    # Generate new exam schedule
                    generate_exam_schedule(conn, courses, active_session['name'])
                    st.success("Exam schedule generated successfully!")
                    st.rerun()
        
        with col1:
            # Display the exam schedule
            if exam_schedule_exists:
                display_exam_schedule(conn, active_session['name'])
            else:
                st.info("No exam schedule has been generated yet. Click 'Generate Exam Schedule' to create one.")
    
    # Close the database connection
    conn.close()

def get_active_session(conn):
    """Get the active academic session"""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM academic_sessions WHERE is_active = 1")
    return cursor.fetchone()

def get_courses_with_teachers(conn, session_name):
    """Get all courses with assigned teachers for the current session"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id as course_id, c.code as course_code, c.title as course_title, 
               c.credit_hour as credit, c.max_students as capacity,
               t.id as teacher_id, t.name as teacher_name, t.dept as teacher_dept
        FROM courses c
        JOIN teaching te ON c.id = te.course_id
        JOIN teachers t ON te.teacher_id = t.id
        WHERE te.semester = ?
        ORDER BY c.code
    """, (session_name,))
    return cursor.fetchall()

def get_all_courses(conn):
    """Get all courses"""
    cursor = conn.cursor()
    cursor.execute("SELECT id, code, title, credit_hour as credit, max_students as capacity FROM courses ORDER BY code")
    return cursor.fetchall()

def check_routine_exists(conn, session_name):
    """Check if a routine already exists for the current session"""
    # First, make sure the table exists
    create_routine_table_if_not_exists(conn)
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM class_routine WHERE session = ?", (session_name,))
    count = cursor.fetchone()[0]
    return count > 0

def check_exam_schedule_exists(conn, session_name):
    """Check if an exam schedule already exists for the current session"""
    # First, make sure the table exists
    create_exam_schedule_table_if_not_exists(conn)
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM exam_schedule WHERE session = ?", (session_name,))
    count = cursor.fetchone()[0]
    return count > 0

def delete_existing_routine(conn, session_name):
    """Delete existing routine for the current session"""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM class_routine WHERE session = ?", (session_name,))
    conn.commit()

def delete_existing_exam_schedule(conn, session_name):
    """Delete existing exam schedule for the current session"""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM exam_schedule WHERE session = ?", (session_name,))
    conn.commit()

def create_routine_table_if_not_exists(conn):
    """Create class_routine table if it doesn't exist"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS class_routine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            room TEXT NOT NULL,
            session TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (id),
            FOREIGN KEY (teacher_id) REFERENCES teachers (id)
        )
    """)
    conn.commit()

def create_exam_schedule_table_if_not_exists(conn):
    """Create exam_schedule table if it doesn't exist"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exam_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            exam_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            room TEXT NOT NULL,
            session TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        )
    """)
    conn.commit()

def generate_routine(conn, courses_with_teachers, session_name):
    """Generate a weekly class routine"""
    # Create routine table if it doesn't exist
    create_routine_table_if_not_exists(conn)
    
    # Define days and time slots
    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
    time_slots = [
        "8:00 AM - 9:30 AM",
        "9:45 AM - 11:15 AM", 
        "11:30 AM - 1:00 PM",
        "2:00 PM - 3:30 PM",
        "3:45 PM - 5:15 PM"
    ]
    
    # Prepare room numbers
    rooms = [f"Room {i:03d}" for i in range(101, 121)]
    
    # Track assigned slots for each teacher to avoid conflicts
    teacher_slots = {}
    
    # Track assigned slots for each course to distribute classes
    course_slots = {}
    
    # Initialize random seed for consistent but random-looking assignments
    np.random.seed(42)
    
    # Convert courses to a list for easier manipulation
    courses_list = list(courses_with_teachers)
    
    # Shuffle courses to randomize allocation
    np.random.shuffle(courses_list)
    
    for course in courses_list:
        course_id = course["course_id"]
        teacher_id = course["teacher_id"]
        credit = course["credit"]
        
        # Determine how many classes per week based on credit hours
        classes_per_week = min(int(credit), 3)  # Max 3 classes per week
        
        if teacher_id not in teacher_slots:
            teacher_slots[teacher_id] = set()
        
        if course_id not in course_slots:
            course_slots[course_id] = set()
        
        # Try to assign classes
        for _ in range(classes_per_week):
            # Try to find a suitable day and time slot
            found_slot = False
            
            # Shuffle days and time slots for more balanced allocation
            shuffled_days = days.copy()
            np.random.shuffle(shuffled_days)
            
            for day in shuffled_days:
                if found_slot:
                    break
                
                shuffled_slots = time_slots.copy()
                np.random.shuffle(shuffled_slots)
                
                for time_slot in shuffled_slots:
                    slot_key = f"{day}_{time_slot}"
                    
                    # Check if teacher is available at this slot
                    if slot_key in teacher_slots[teacher_id]:
                        continue
                    
                    # Check if course already has a class at this slot
                    if slot_key in course_slots[course_id]:
                        continue
                    
                    # Assign the slot
                    teacher_slots[teacher_id].add(slot_key)
                    course_slots[course_id].add(slot_key)
                    
                    # Assign a random room
                    room = np.random.choice(rooms)
                    
                    # Save to database
                    conn.execute("""
                        INSERT INTO class_routine 
                        (course_id, teacher_id, day, time_slot, room, session)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (course_id, teacher_id, day, time_slot, room, session_name))
                    
                    found_slot = True
                    break
    
    conn.commit()

def generate_exam_schedule(conn, courses, session_name):
    """Generate an exam schedule"""
    # Create exam schedule table if it doesn't exist
    create_exam_schedule_table_if_not_exists(conn)
    
    # Define start date for exams (2 weeks from now)
    start_date = datetime.now() + timedelta(days=14)
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Only use weekdays (Monday to Friday)
    weekdays = [0, 1, 2, 3, 4]  # Monday is 0, Sunday is 6
    
    # Define exam slots
    exam_slots = [
        ("9:00 AM", "11:00 AM"),
        ("12:00 PM", "2:00 PM"),
        ("3:00 PM", "5:00 PM")
    ]
    
    # Prepare room numbers for exams
    exam_rooms = [f"Exam Hall {i:02d}" for i in range(1, 11)]
    
    # Track used rooms for each slot
    used_rooms = {}
    
    # Track exams per day to limit them
    exams_per_day = {}
    
    # Limit the number of exams per day
    max_exams_per_day = 6
    
    # Convert courses to a list for easier manipulation
    courses_list = list(courses)
    
    # Shuffle courses to randomize allocation
    np.random.seed(42)
    np.random.shuffle(courses_list)
    
    # Current date for scheduling
    current_date = start_date
    
    for course in courses_list:
        course_id = course["id"]
        
        # Find a suitable date and slot
        found_slot = False
        
        while not found_slot:
            # Skip weekends
            while current_date.weekday() not in weekdays:
                current_date += timedelta(days=1)
            
            # Format the date for checking
            date_str = current_date.strftime("%Y-%m-%d")
            
            # Check if we have too many exams on this day
            if date_str in exams_per_day and exams_per_day[date_str] >= max_exams_per_day:
                current_date += timedelta(days=1)
                continue
            
            # Initialize the day if not already
            if date_str not in exams_per_day:
                exams_per_day[date_str] = 0
                used_rooms[date_str] = {}
                for slot_start, slot_end in exam_slots:
                    used_rooms[date_str][f"{slot_start}-{slot_end}"] = set()
            
            # Try to find an available slot and room on this day
            for slot_start, slot_end in exam_slots:
                slot_key = f"{slot_start}-{slot_end}"
                
                # Check available rooms for this slot
                available_rooms = set(exam_rooms) - used_rooms[date_str][slot_key]
                
                if available_rooms:
                    # Assign a random available room
                    room = np.random.choice(list(available_rooms))
                    used_rooms[date_str][slot_key].add(room)
                    
                    # Update exams count for this day
                    exams_per_day[date_str] += 1
                    
                    # Save to database
                    conn.execute("""
                        INSERT INTO exam_schedule 
                        (course_id, exam_date, start_time, end_time, room, session)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (course_id, date_str, slot_start, slot_end, room, session_name))
                    
                    found_slot = True
                    break
            
            # Move to next day if no slot found on this day
            if not found_slot:
                current_date += timedelta(days=1)
    
    conn.commit()

def display_routine(conn, session_name):
    """Display the class routine in a tabular format"""
    # Define days and time slots
    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
    time_slots = [
        "8:00 AM - 9:30 AM",
        "9:45 AM - 11:15 AM", 
        "11:30 AM - 1:00 PM",
        "2:00 PM - 3:30 PM",
        "3:45 PM - 5:15 PM"
    ]
    
    # Fetch all routine entries
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.day, r.time_slot, r.room,
               c.code as course_code, c.title as course_title,
               t.name as teacher_name
        FROM class_routine r
        JOIN courses c ON r.course_id = c.id
        JOIN teachers t ON r.teacher_id = t.id
        WHERE r.session = ?
        ORDER BY 
            CASE r.day
                WHEN 'Sunday' THEN 1
                WHEN 'Monday' THEN 2
                WHEN 'Tuesday' THEN 3
                WHEN 'Wednesday' THEN 4
                WHEN 'Thursday' THEN 5
            END,
            r.time_slot
    """, (session_name,))
    
    routine_entries = cursor.fetchall()
    
    # Create a routine dataframe
    routine_data = {day: {slot: [] for slot in time_slots} for day in days}
    
    # Fill in the routine data
    for entry in routine_entries:
        day = entry["day"]
        time_slot = entry["time_slot"]
        course_code = entry["course_code"]
        course_title = entry["course_title"]
        teacher_name = entry["teacher_name"]
        room = entry["room"]
        
        routine_data[day][time_slot].append({
            "course": f"{course_code}",
            "title": course_title,
            "teacher": teacher_name,
            "room": room
        })
    
    # Display the routine
    st.write("### Weekly Class Schedule")
    
    # Create column headers
    cols = ["Time Slot"] + days
    
    # Create a DataFrame for display
    rows = []
    
    for time_slot in time_slots:
        row = [time_slot]
        
        for day in days:
            classes = routine_data[day][time_slot]
            
            if classes:
                cell_content = ""
                for cls in classes:
                    cell_content += f"**{cls['course']}**<br>{cls['title']}<br>{cls['teacher']}<br>_{cls['room']}_<br><br>"
                row.append(cell_content)
            else:
                row.append("No Class")
        
        rows.append(row)
    
    df = pd.DataFrame(rows, columns=cols)
    
    # Display using HTML to make it more readable
    st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
    
    # Add a download button for the schedule
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Schedule (CSV)",
        data=csv,
        file_name='class_schedule.csv',
        mime='text/csv',
    )

def display_exam_schedule(conn, session_name):
    """Display the exam schedule"""
    # Fetch all exam schedule entries
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.exam_date, e.start_time, e.end_time, e.room,
               c.code as course_code, c.title as course_title
        FROM exam_schedule e
        JOIN courses c ON e.course_id = c.id
        WHERE e.session = ?
        ORDER BY e.exam_date, e.start_time
    """, (session_name,))
    
    exam_entries = cursor.fetchall()
    
    if not exam_entries:
        st.info("No exam schedule found for the current session.")
        return
    
    # Group by date
    exam_dates = {}
    for entry in exam_entries:
        date = entry["exam_date"]
        if date not in exam_dates:
            exam_dates[date] = []
        exam_dates[date].append(entry)
    
    # Display the exam schedule
    st.write("### Exam Schedule")
    
    # Create a dataframe for all exams
    exam_data = []
    
    for date, entries in sorted(exam_dates.items()):
        # Convert date string to datetime for formatting
        exam_date = datetime.strptime(date, "%Y-%m-%d")
        formatted_date = exam_date.strftime("%A, %B %d, %Y")
        
        st.write(f"#### {formatted_date}")
        
        # Create a dataframe for this date's exams
        date_data = []
        
        for entry in entries:
            date_data.append({
                "Course": f"{entry['course_code']} - {entry['course_title']}",
                "Time": f"{entry['start_time']} - {entry['end_time']}",
                "Room": entry["room"]
            })
            
            # Add to overall data
            exam_data.append({
                "Date": formatted_date,
                "Course": f"{entry['course_code']} - {entry['course_title']}",
                "Time": f"{entry['start_time']} - {entry['end_time']}",
                "Room": entry["room"]
            })
        
        # Display this date's exams
        df_date = pd.DataFrame(date_data)
        st.dataframe(df_date, use_container_width=True, hide_index=True)
    
    # Add a download button for the complete schedule
    df_all = pd.DataFrame(exam_data)
    csv = df_all.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Complete Exam Schedule (CSV)",
        data=csv,
        file_name='exam_schedule.csv',
        mime='text/csv',
    ) 