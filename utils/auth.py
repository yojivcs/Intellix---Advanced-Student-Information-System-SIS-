import streamlit as st
from database.schema import get_db_connection
from datetime import datetime

def check_login(username, password):
    """Check if the login credentials are valid"""
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, password)
    ).fetchone()
    
    if user:
        # Update last login time
        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user['id'])
        )
        conn.commit()
        
        user_data = {'id': user['id'], 'username': user['username'], 'role': user['role'], 'user_id': user['user_id']}
        
        # If it's a student or teacher, get additional info
        if user['role'] == 'student':
            student = conn.execute("SELECT * FROM students WHERE id = ?", (user['user_id'],)).fetchone()
            if student:
                user_data['name'] = student['name']
                user_data['dept'] = student['dept']
                user_data['semester'] = student['semester']
        elif user['role'] == 'teacher':
            teacher = conn.execute("SELECT * FROM teachers WHERE id = ?", (user['user_id'],)).fetchone()
            if teacher:
                user_data['name'] = teacher['name']
                user_data['dept'] = teacher['dept']
                
        conn.close()
        return user_data
    
    conn.close()
    return None

def login_required():
    """Check if the user is logged in, redirect to login page if not"""
    if 'user' not in st.session_state:
        st.session_state.user = None
        st.session_state.authenticated = False
        return False
    return st.session_state.authenticated

def logout():
    """Log out the user"""
    st.session_state.user = None
    st.session_state.authenticated = False

def init_session():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if 'user' not in st.session_state:
        st.session_state.user = None
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'dashboard'
    
    # Ensure academic sessions exist
    check_academic_sessions()

def check_academic_sessions():
    """Ensure default academic sessions exist"""
    conn = get_db_connection()
    
    # Check if academic_sessions table exists and has data
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='academic_sessions'")
    if not cursor.fetchone():
        conn.execute('''
        CREATE TABLE IF NOT EXISTS academic_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            start_date DATE,
            end_date DATE,
            is_active BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Insert default academic sessions
        sessions = [
            ('Spring 2023', '2023-01-10', '2023-05-20', 0),
            ('Fall 2023', '2023-08-15', '2023-12-20', 0),
            ('Spring 2024', '2024-01-08', '2024-05-15', 1)
        ]
        conn.executemany(
            "INSERT INTO academic_sessions (name, start_date, end_date, is_active) VALUES (?, ?, ?, ?)",
            sessions
        )
        conn.commit()
    else:
        # Check if there are any sessions
        cursor = conn.execute("SELECT COUNT(*) FROM academic_sessions")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Insert default academic sessions
            sessions = [
                ('Spring 2023', '2023-01-10', '2023-05-20', 0),
                ('Fall 2023', '2023-08-15', '2023-12-20', 0),
                ('Spring 2024', '2024-01-08', '2024-05-15', 1)
            ]
            conn.executemany(
                "INSERT INTO academic_sessions (name, start_date, end_date, is_active) VALUES (?, ?, ?, ?)",
                sessions
            )
            conn.commit()
        
        # Ensure at least one session is active
        cursor = conn.execute("SELECT COUNT(*) FROM academic_sessions WHERE is_active = 1")
        active_count = cursor.fetchone()[0]
        
        if active_count == 0:
            # Set the most recent session as active
            conn.execute("UPDATE academic_sessions SET is_active = 1 WHERE id = (SELECT MAX(id) FROM academic_sessions)")
            conn.commit()
    
    conn.close()
    
def generate_credentials(role, name):
    """Generate username and password for new users"""
    import random
    import string
    
    # Create username (first letter of first name + last name, all lowercase)
    name_parts = name.strip().split()
    
    if len(name_parts) > 1:
        username = (name_parts[0][0] + name_parts[-1]).lower()
    else:
        username = name_parts[0].lower()
    
    # Remove spaces and special characters
    username = ''.join(c for c in username if c.isalnum())
    
    # Generate random password (8 characters)
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    # Check if username already exists, add numbers if needed
    conn = get_db_connection()
    existing = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    
    counter = 1
    original_username = username
    while existing:
        username = f"{original_username}{counter}"
        counter += 1
        existing = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    
    conn.close()
    
    return username, password 