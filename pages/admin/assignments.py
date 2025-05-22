import streamlit as st
from components.header import render_page_title

def show():
    """Display the assignments management page"""
    render_page_title("📝", "Assignments")
    
    st.info("This page is under development. Check back soon for assignment management features.") 