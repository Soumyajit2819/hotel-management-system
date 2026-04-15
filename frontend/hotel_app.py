import streamlit as st

from app import main

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None


if __name__ == "__main__":
    main()
