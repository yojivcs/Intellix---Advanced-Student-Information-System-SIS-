import re
from database.schema import get_db_connection

def parse_command(command_text):
    """Parse natural language command text into actionable operations
    
    Args:
        command_text: The command text to parse
        
    Returns:
        dict: Parsed command with operation type and parameters
    """
    command_text = command_text.strip().lower()
    
    # Initialize result
    result = {
        "valid": False,
        "operation": None,
        "params": {},
        "message": "Invalid command"
    }
    
    # Extract student IDs (handles both "student 101, 102" and just "101, 102")
    student_ids = re.findall(r'student\s+(\d+(?:\s*,\s*\d+)*)', command_text)
    if not student_ids:
        student_ids = re.findall(r'(\d+(?:\s*,\s*\d+)*)\s+to\s+', command_text)
    
    if student_ids:
        # Split comma-separated IDs and convert to integers
        student_id_list = [int(id.strip()) for id in re.split(r'\s*,\s*', student_ids[0])]
        result["params"]["student_ids"] = student_id_list
    
    # Extract teacher IDs
    teacher_ids = re.findall(r'teacher\s+(\d+(?:\s*,\s*\d+)*)', command_text)
    if not teacher_ids:
        teacher_ids = re.findall(r'teacher\s+t(\d+(?:\s*,\s*\d+)*)', command_text)
    
    if teacher_ids:
        # Split comma-separated IDs and convert to integers
        teacher_id_list = [int(id.strip()) for id in re.split(r'\s*,\s*', teacher_ids[0])]
        result["params"]["teacher_ids"] = teacher_id_list
    
    # Extract course codes (handles both "CSE303, CSE304" and "cse303, cse304")
    course_pattern = r'([a-zA-Z]{2,4}\s*\d{3}(?:\s*,\s*[a-zA-Z]{2,4}\s*\d{3})*)'
    course_codes = re.findall(course_pattern, command_text)
    
    if course_codes:
        # Split comma-separated codes and normalize format
        course_code_list = []
        for code_group in course_codes:
            codes = re.split(r'\s*,\s*', code_group)
            for code in codes:
                # Normalize format (e.g., "cse 303" to "CSE303")
                normalized = re.sub(r'\s+', '', code.upper())
                course_code_list.append(normalized)
        
        result["params"]["course_codes"] = course_code_list
    
    # Detect operation type
    if "assign" in command_text or "enroll" in command_text:
        if "student" in command_text or any(str(i) in command_text for i in result.get("params", {}).get("student_ids", [])):
            if "course" in command_text or any(code in command_text.upper() for code in result.get("params", {}).get("course_codes", [])):
                result["operation"] = "enroll_students"
                result["valid"] = bool(result.get("params", {}).get("student_ids") and result.get("params", {}).get("course_codes"))
                result["message"] = f"Enroll students {result.get('params', {}).get('student_ids', [])} to courses {result.get('params', {}).get('course_codes', [])}"
        
        if "teacher" in command_text or any(str(i) in command_text for i in result.get("params", {}).get("teacher_ids", [])):
            if "course" in command_text or any(code in command_text.upper() for code in result.get("params", {}).get("course_codes", [])):
                result["operation"] = "assign_teachers"
                result["valid"] = bool(result.get("params", {}).get("teacher_ids") and result.get("params", {}).get("course_codes"))
                result["message"] = f"Assign teachers {result.get('params', {}).get('teacher_ids', [])} to courses {result.get('params', {}).get('course_codes', [])}"
    
    # Extract semester information
    semester_pattern = r'(spring|summer|fall|winter)\s+(\d{4})'
    semester_match = re.search(semester_pattern, command_text, re.IGNORECASE)
    
    if semester_match:
        semester_term = semester_match.group(1).capitalize()
        semester_year = semester_match.group(2)
        result["params"]["semester"] = f"{semester_term} {semester_year}"
    else:
        # Default to current semester
        from datetime import datetime
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        if 1 <= current_month <= 4:
            term = "Spring"
        elif 5 <= current_month <= 7:
            term = "Summer"
        elif 8 <= current_month <= 12:
            term = "Fall"
            
        result["params"]["semester"] = f"{term} {current_year}"
    
    return result

def execute_command(parsed_command):
    """Execute a parsed command
    
    Args:
        parsed_command: The parsed command dict
        
    Returns:
        dict: Result of the operation
    """
    if not parsed_command.get("valid", False):
        return {
            "success": False,
            "message": parsed_command.get("message", "Invalid command")
        }
    
    operation = parsed_command.get("operation")
    params = parsed_command.get("params", {})
    
    conn = get_db_connection()
    result = {
        "success": False,
        "message": "Operation not implemented",
        "details": []
    }
    
    try:
        if operation == "enroll_students":
            student_ids = params.get("student_ids", [])
            course_codes = params.get("course_codes", [])
            semester = params.get("semester")
            
            # Verify students exist
            for student_id in student_ids:
                student = conn.execute("SELECT id, name FROM students WHERE id = ?", (student_id,)).fetchone()
                if not student:
                    result["details"].append(f"Student ID {student_id} not found")
                    continue
                
                # Get course IDs from codes
                for course_code in course_codes:
                    course = conn.execute("SELECT id, title FROM courses WHERE code = ?", (course_code,)).fetchone()
                    if not course:
                        result["details"].append(f"Course {course_code} not found")
                        continue
                    
                    # Check if enrollment already exists
                    existing = conn.execute(
                        "SELECT id FROM enrollments WHERE student_id = ? AND course_id = ? AND semester = ?", 
                        (student_id, course['id'], semester)
                    ).fetchone()
                    
                    if existing:
                        result["details"].append(f"Student {student['name']} already enrolled in {course_code}")
                        continue
                    
                    # Enroll student
                    conn.execute(
                        "INSERT INTO enrollments (student_id, course_id, semester) VALUES (?, ?, ?)",
                        (student_id, course['id'], semester)
                    )
                    result["details"].append(f"Enrolled student {student['name']} in {course_code}")
            
            result["success"] = True
            result["message"] = f"Enrollment processed for {len(student_ids)} students in {len(course_codes)} courses"
        
        elif operation == "assign_teachers":
            teacher_ids = params.get("teacher_ids", [])
            course_codes = params.get("course_codes", [])
            semester = params.get("semester")
            
            # Verify teachers exist
            for teacher_id in teacher_ids:
                teacher = conn.execute("SELECT id, name FROM teachers WHERE id = ?", (teacher_id,)).fetchone()
                if not teacher:
                    result["details"].append(f"Teacher ID {teacher_id} not found")
                    continue
                
                # Get course IDs from codes
                for course_code in course_codes:
                    course = conn.execute("SELECT id, title FROM courses WHERE code = ?", (course_code,)).fetchone()
                    if not course:
                        result["details"].append(f"Course {course_code} not found")
                        continue
                    
                    # Check if teaching assignment already exists
                    existing = conn.execute(
                        "SELECT id FROM teaching WHERE teacher_id = ? AND course_id = ? AND semester = ?", 
                        (teacher_id, course['id'], semester)
                    ).fetchone()
                    
                    if existing:
                        result["details"].append(f"Teacher {teacher['name']} already assigned to {course_code}")
                        continue
                    
                    # Assign teacher
                    conn.execute(
                        "INSERT INTO teaching (teacher_id, course_id, semester) VALUES (?, ?, ?)",
                        (teacher_id, course['id'], semester)
                    )
                    result["details"].append(f"Assigned teacher {teacher['name']} to {course_code}")
            
            result["success"] = True
            result["message"] = f"Teacher assignment processed for {len(teacher_ids)} teachers to {len(course_codes)} courses"
            
        conn.commit()
    except Exception as e:
        result["success"] = False
        result["message"] = f"Error executing command: {str(e)}"
    finally:
        conn.close()
    
    return result 