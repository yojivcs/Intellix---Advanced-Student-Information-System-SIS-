import sqlite3
import os
import json
from datetime import datetime

# Database initialization
def init_db():
    """Initialize the database with the required tables"""
    db_path = os.path.join(os.path.dirname(__file__), 'intellix.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        user_id INTEGER NOT NULL,  -- ID of student/teacher (for reference)
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )
    ''')
    
    # Create students table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE,
        name TEXT NOT NULL,
        photo TEXT,
        dept TEXT NOT NULL,
        semester INTEGER NOT NULL,
        email TEXT,
        phone TEXT,
        address TEXT,
        admission_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create teachers table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        photo TEXT,
        dept TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        address TEXT,
        join_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create courses table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        credit_hour REAL NOT NULL,
        max_students INTEGER DEFAULT 50,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create enrollments table (students assigned to courses)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        semester TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id),
        FOREIGN KEY (course_id) REFERENCES courses (id),
        UNIQUE(student_id, course_id, semester)
    )
    ''')
    
    # Create teaching table (teachers assigned to courses)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS teaching (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        semester TEXT NOT NULL,
        marks_finalized BOOLEAN DEFAULT 0,
        finalized_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (teacher_id) REFERENCES teachers (id),
        FOREIGN KEY (course_id) REFERENCES courses (id),
        UNIQUE(teacher_id, course_id, semester)
    )
    ''')
    
    # Create academic_sessions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS academic_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        start_date DATE,
        end_date DATE,
        is_active BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Insert default academic sessions if not exists
    cursor.execute("SELECT COUNT(*) FROM academic_sessions")
    if cursor.fetchone()[0] == 0:
        sessions = [
            ('Spring 2023', '2023-01-10', '2023-05-20', 0),
            ('Fall 2023', '2023-08-15', '2023-12-20', 0),
            ('Spring 2024', '2024-01-08', '2024-05-15', 1)
        ]
        cursor.executemany(
            "INSERT INTO academic_sessions (name, start_date, end_date, is_active) VALUES (?, ?, ?, ?)",
            sessions
        )
    
    # Create grades table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        mid REAL DEFAULT 0,
        assignment REAL DEFAULT 0,
        final REAL DEFAULT 0,
        semester TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id),
        FOREIGN KEY (course_id) REFERENCES courses (id),
        UNIQUE(student_id, course_id, semester)
    )
    ''')
    
    # Create attendance table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        date DATE NOT NULL,
        present BOOLEAN NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id),
        FOREIGN KEY (course_id) REFERENCES courses (id),
        UNIQUE(student_id, course_id, date)
    )
    ''')
    
    # Create study_plans table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS study_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        plan_json TEXT NOT NULL,
        semester TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id)
    )
    ''')
    
    # Create class_tests table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS class_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        test_date DATE NOT NULL,
        duration_minutes INTEGER DEFAULT 30,
        questions JSON NOT NULL,
        max_marks REAL NOT NULL,
        is_published BOOLEAN DEFAULT 0,
        semester TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (course_id) REFERENCES courses (id)
    )
    ''')
    
    # Create assignments table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        due_date DATE NOT NULL,
        max_marks REAL NOT NULL,
        is_published BOOLEAN DEFAULT 0,
        semester TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (course_id) REFERENCES courses (id)
    )
    ''')
    
    # Create student_assignments table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS student_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        assignment_id INTEGER NOT NULL,
        submission_file TEXT,
        remarks TEXT,
        marks REAL DEFAULT 0,
        status TEXT DEFAULT 'pending',
        submitted_at TIMESTAMP,
        graded_at TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id),
        FOREIGN KEY (assignment_id) REFERENCES assignments (id),
        UNIQUE(student_id, assignment_id)
    )
    ''')
    
    # Create student_test_submissions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS student_test_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        test_id INTEGER NOT NULL,
        answers JSON NOT NULL,
        marks REAL DEFAULT 0,
        status TEXT DEFAULT 'pending',
        submitted_at TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id),
        FOREIGN KEY (test_id) REFERENCES class_tests (id),
        UNIQUE(student_id, test_id)
    )
    ''')
    
    # Insert default admin user if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, role, user_id) VALUES (?, ?, ?, ?)",
            ('admin', 'admin123', 'admin', 0)
        )
    
    conn.commit()
    conn.close()
    
    return db_path

def get_db_connection():
    """Get a connection to the database"""
    db_path = os.path.join(os.path.dirname(__file__), 'intellix.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database on module import
if __name__ == "__main__":
    init_db() 