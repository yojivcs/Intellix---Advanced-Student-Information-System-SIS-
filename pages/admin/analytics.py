import streamlit as st
from components.header import render_page_title

def show():
    """Display the analytics page"""
    render_page_title("📊", "Analytics")
    
    st.info("This page is under development. Check back soon for advanced analytics features.") 