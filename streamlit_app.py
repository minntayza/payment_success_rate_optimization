"""Root entry point for Streamlit Community Cloud.

When Streamlit Cloud runs this file, the project root is the working
directory, so payment_dashboard is a normal importable package.
"""
from payment_dashboard.app import render_app

render_app()
