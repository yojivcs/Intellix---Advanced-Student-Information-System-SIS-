import streamlit as st
from utils.auth import logout

def render_sidebar():
    """Render the sidebar navigation based on user role"""
    with st.sidebar:
        st.markdown("<h1 style='font-size:36px;'>Intellix</h1>", unsafe_allow_html=True)
        
        user_role = st.session_state.user.get('role', 'guest')
        
        st.write(f"Welcome, **{st.session_state.user.get('username', 'Guest')}**")
        st.write(f"Role: **{user_role.capitalize()}**")
        
        st.divider()
        
        # Common navigation for all roles
        if st.sidebar.button("Dashboard", use_container_width=True):
            st.session_state.current_page = "dashboard"
            st.rerun()
            
        # Role-specific navigation
        if user_role == 'admin':
            # Admin navigation
            if st.sidebar.button("Students", use_container_width=True):
                st.session_state.current_page = "students"
                st.rerun()
                
            if st.sidebar.button("Teachers", use_container_width=True):
                st.session_state.current_page = "teachers"
                st.rerun()
                
            if st.sidebar.button("Course Management System", use_container_width=True):
                st.session_state.current_page = "courses"
                st.rerun()
                
            if st.sidebar.button("Course Assignment and Enrollment", use_container_width=True):
                st.session_state.current_page = "course_enrollment"
                st.rerun()
                
            if st.sidebar.button("Academic Calendar & Routine", use_container_width=True):
                st.session_state.current_page = "academic_calendar"
                st.rerun()
                
            if st.sidebar.button("Assignments", use_container_width=True):
                st.session_state.current_page = "assignments"
                st.rerun()
            
            if st.sidebar.button("Student Transcript Viewer", use_container_width=True):
                st.session_state.current_page = "student_transcript_viewer"
                st.rerun()
                
            if st.sidebar.button("AI Tools", use_container_width=True):
                st.session_state.current_page = "ai_tools"
                st.rerun()
                
            if st.sidebar.button("Analytics", use_container_width=True):
                st.session_state.current_page = "analytics"
                st.rerun()
                
        elif user_role == 'teacher':
            # Teacher navigation
            if st.sidebar.button("My Courses", use_container_width=True):
                st.session_state.current_page = "teacher_courses"
                st.rerun()
                
            if st.sidebar.button("Grades", use_container_width=True):
                st.session_state.current_page = "teacher_grades"
                st.rerun()
                
            if st.sidebar.button("Attendance", use_container_width=True):
                st.session_state.current_page = "teacher_attendance"
                st.rerun()
                
            if st.sidebar.button("Assignments & Class Tests", use_container_width=True):
                st.session_state.current_page = "teacher_assignments"
                st.rerun()
                
            if st.sidebar.button("Class Analytics", use_container_width=True):
                st.session_state.current_page = "teacher_analytics"
                st.rerun()
                
            if st.sidebar.button("💬 Messages", use_container_width=True):
                st.session_state.current_page = "teacher_messages"
                st.rerun()
                
        elif user_role == 'student':
            # Student navigation according to the specified structure
            if st.sidebar.button("🏠 Dashboard", use_container_width=True):
                st.session_state.current_page = "dashboard"
                st.rerun()
            
            if st.sidebar.button("✅ Instructor Evaluation", use_container_width=True):
                st.info("Instructor evaluation feature will be available soon.")
                
            if st.sidebar.button("🧾 Transcript", use_container_width=True):
                st.info("Transcript feature will be available soon.")
                
            if st.sidebar.button("📊 Progress Report", use_container_width=True):
                st.session_state.current_page = "student_grades"
                st.rerun()
                
            if st.sidebar.button("📅 Semester Report", use_container_width=True):
                st.info("Semester report feature will be available soon.")
                
            if st.sidebar.button("🧑‍🏫 Classes", use_container_width=True):
                st.session_state.current_page = "student_courses"
                st.rerun()
                
            if st.sidebar.button("📚 Assignments & Tests", use_container_width=True):
                st.session_state.current_page = "student_assignments"
                st.rerun()
                
            if st.sidebar.button("📈 GPA Prediction", use_container_width=True):
                st.session_state.current_page = "student_gpa_prediction"
                st.rerun()
                
            if st.sidebar.button("📝 Study Plan", use_container_width=True):
                st.session_state.current_page = "student_study_plan"
                st.rerun()
                
            if st.sidebar.button("💬 Messages", use_container_width=True):
                st.session_state.current_page = "student_messages"
                st.rerun()
        
        st.divider()
        if st.sidebar.button("Logout", use_container_width=True, type="primary"):
            logout()
            st.rerun() 