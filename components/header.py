import streamlit as st

def render_header(title, subtitle=None):
    """Render a consistent header with title and optional subtitle"""
    st.title(title)
    if subtitle:
        st.subheader(subtitle)
    st.divider()

def render_page_title(icon, title):
    """Render a styled page title with an icon"""
    st.markdown(f"# {icon} {title}")
    st.divider() 