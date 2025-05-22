import sqlite3
import os
from pathlib import Path
from database.schema import init_db

def update_database():
    """Update the database schema to include missing tables and fields"""
    # Call the init_db function from schema.py to create any missing tables
    db_path = init_db()
    print(f"Database updated at {db_path}")
    
    # Get database connection
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Check if tables exist and report status
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [table['name'] for table in cursor.fetchall()]
    
    print("\nExisting tables:")
    for table in tables:
        print(f" - {table}")
    
    # Check if academic_sessions table exists, create if not
    if 'academic_sessions' not in tables:
        print("\nCreating academic_sessions table...")
        cursor.execute('''
        CREATE TABLE academic_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            is_active BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        print("Academic sessions table created")
        
        # Insert a default session
        cursor.execute('''
        INSERT INTO academic_sessions (name, start_date, end_date, is_active) 
        VALUES ('Fall 2023', '2023-09-01', '2023-12-31', 1)
        ''')
        print("Default academic session added")
    
    # Check if class_routine table exists, create if not
    if 'class_routine' not in tables:
        print("\nCreating class_routine table...")
        cursor.execute('''
        CREATE TABLE class_routine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            room TEXT NOT NULL,
            session TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id),
            FOREIGN KEY (teacher_id) REFERENCES teachers (id),
            UNIQUE(course_id, day, time_slot, session)
        )
        ''')
        print("Class routine table created")
    
    # Check if programs table exists, create if not
    if 'programs' not in tables:
        print("\nCreating programs table...")
        cursor.execute('''
        CREATE TABLE programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL,
            degree_level TEXT NOT NULL,
            duration_years INTEGER NOT NULL,
            total_credit_hours INTEGER NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        print("Programs table created")
        
        # Insert default programs
        cursor.executemany('''
        INSERT INTO programs (name, code, department, degree_level, duration_years, total_credit_hours, description) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', [
            ('Bachelor of Computer Science', 'BCS', 'Computer Science', 'Bachelor', 4, 130, 'Bachelor degree in Computer Science'),
            ('Bachelor of Business Administration', 'BBA', 'Business Administration', 'Bachelor', 4, 120, 'Bachelor degree in Business Administration'),
            ('Master of Computer Science', 'MCS', 'Computer Science', 'Master', 2, 36, 'Master degree in Computer Science')
        ])
        print("Default programs added")
    
    # Check if student_programs table exists, create if not
    if 'student_programs' not in tables:
        print("\nCreating student_programs table...")
        cursor.execute('''
        CREATE TABLE student_programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            program_id INTEGER NOT NULL,
            enrollment_date DATE NOT NULL,
            expected_graduation DATE,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id),
            FOREIGN KEY (program_id) REFERENCES programs (id),
            UNIQUE(student_id, program_id)
        )
        ''')
        print("Student programs table created")
    
    # Check if exam_schedule table exists, create if not
    if 'exam_schedule' not in tables:
        print("\nCreating exam_schedule table...")
        cursor.execute('''
        CREATE TABLE exam_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            exam_date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            room TEXT NOT NULL,
            exam_type TEXT NOT NULL,
            session TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id),
            UNIQUE(course_id, exam_date, exam_type, session)
        )
        ''')
        print("Exam schedule table created")
        
        # Insert sample exam schedule
        cursor.executemany('''
        INSERT INTO exam_schedule (course_id, exam_date, start_time, end_time, room, exam_type, session) 
        VALUES ((SELECT id FROM courses WHERE code = ? LIMIT 1), ?, ?, ?, ?, ?, ?)
        ''', [
            ('CSE101', '2023-12-10', '09:00', '11:00', 'Room 101', 'Final', 'Fall 2023'),
            ('CSE102', '2023-12-12', '09:00', '11:00', 'Room 102', 'Final', 'Fall 2023'),
            ('CSE103', '2023-12-14', '09:00', '11:00', 'Room 103', 'Final', 'Fall 2023'),
            ('CSE101', '2023-10-15', '09:00', '10:30', 'Room 101', 'Midterm', 'Fall 2023'),
            ('CSE102', '2023-10-17', '09:00', '10:30', 'Room 102', 'Midterm', 'Fall 2023')
        ])
        print("Sample exam schedule added")
    
    # Check if messages table exists, create if not
    if 'messages' not in tables:
        print("\nCreating messages table...")
        cursor.execute('''
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            sender_role TEXT NOT NULL,
            recipient_id INTEGER NOT NULL,
            recipient_role TEXT NOT NULL,
            course_id INTEGER,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read BOOLEAN DEFAULT 0,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            read_at TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        )
        ''')
        print("Messages table created")
        
        # Create message templates table
        cursor.execute('''
        CREATE TABLE message_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            template TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        print("Message templates table created")
        
        # Insert default message templates
        cursor.executemany('''
        INSERT INTO message_templates (title, template, created_by, role) 
        VALUES (?, ?, ?, ?)
        ''', [
            ('Missed Assignment', 'Dear [STUDENT_NAME],\n\nI noticed you have not submitted the assignment for [COURSE_CODE]. The deadline was [DUE_DATE].\n\nPlease contact me as soon as possible to discuss this matter.\n\nRegards,\n[TEACHER_NAME]', 1, 'teacher'),
            ('Attendance Warning', 'Dear [STUDENT_NAME],\n\nThis is to inform you that your attendance in [COURSE_CODE] is below the required threshold.\n\nPlease improve your attendance to avoid academic penalties.\n\nRegards,\n[TEACHER_NAME]', 1, 'teacher'),
            ('Grade Improvement', 'Dear [STUDENT_NAME],\n\nI wanted to congratulate you on your recent improvement in [COURSE_CODE].\n\nKeep up the good work!\n\nRegards,\n[TEACHER_NAME]', 1, 'teacher'),
            ('Class Cancellation', 'Dear Students,\n\nPlease note that the class for [COURSE_CODE] scheduled on [DATE] has been cancelled.\n\nThe class will be rescheduled and you will be notified accordingly.\n\nRegards,\n[TEACHER_NAME]', 1, 'teacher'),
            ('Assignment Reminder', 'Dear Students,\n\nThis is a reminder that the assignment for [COURSE_CODE] is due on [DUE_DATE].\n\nPlease ensure timely submission.\n\nRegards,\n[TEACHER_NAME]', 1, 'teacher')
        ])
        print("Default message templates added")
    
    # Check if notifications table exists, create if not
    if 'notifications' not in tables:
        print("\nCreating notifications table...")
        cursor.execute('''
        CREATE TABLE notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_role TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            link TEXT,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            read_at TIMESTAMP
        )
        ''')
        print("Notifications table created")
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    print("\nDatabase update completed")

if __name__ == "__main__":
    update_database() 