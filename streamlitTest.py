import streamlit as st

col1, col2, col3 = st.columns([2, 2, 2])

# Place a button in each column
with col1:
    st.button("One", key="button_one", use_container_width=True)

with col2:
    st.button("Two", key="button_two", use_container_width=True)

with col3:
    st.button("Three", key="button_three", use_container_width=True)