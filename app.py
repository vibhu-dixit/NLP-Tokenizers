import streamlit as st
import os
import re
import json
import pandas as pd
from PIL import Image
import google.generativeai as genai
from getImages import screenshot_table
import base64

# Set your API key here
GEMINI_API_KEY = "AIzaSyBQZ5Dnedsn62074kojZBQKVAUVvuh8Z54"  # Replace with your actual API key

# Set page configuration
st.set_page_config(page_title="Table Extractor", layout="wide")

# App title and description
st.title("Web Table Extractor")
st.markdown("Extract data from tables on any webpage using AI")

# Main input section
url = st.text_input("Enter the URL of the webpage containing the table:")
table_title = st.text_input("Enter the title or caption of the table:")

# Format selection
format_type = st.selectbox(
    "Select output format:",
    options=["JSON", "CSV", "HTML"],
    index=0
)

# Function to create a download link
def get_download_link(content, filename, text):
    b64 = base64.b64encode(content.encode()).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">{text}</a>'
    return href

# Initialize session state for screenshot management
if 'screenshot_captured' not in st.session_state:
    st.session_state.screenshot_captured = False
if 'screenshot_filename' not in st.session_state:
    st.session_state.screenshot_filename = ""
if 'extracted_data' not in st.session_state:
    st.session_state.extracted_data = None
if 'safe_title' not in st.session_state:
    st.session_state.safe_title = ""

# Capture table function
if st.button("Capture Table") and url and table_title:
    try:
        # Create a progress indicator
        progress = st.progress(0)
        status = st.empty()
        
        # Step 1: Capture the screenshot
        status.text("Capturing table from website...")
        progress.progress(50)
        
        # Call your screenshot function
        screenshot_table(url, table_title)
        
        # Construct the expected filename
        safe_title = re.sub(r'[^\w\s-]', '', table_title).strip()
        safe_title = re.sub(r'[-\s]+', '_', safe_title)
        screenshot_filename = f"table_{safe_title}_screenshot.png"
        
        # Store safe_title in session state for later use
        st.session_state.safe_title = safe_title
        
        # Check if file exists or try alternative filenames
        if not os.path.exists(screenshot_filename):
            if os.path.exists(f"full_{screenshot_filename}"):
                screenshot_filename = f"full_{screenshot_filename}"
            elif os.path.exists("full_page_screenshot.png"):
                screenshot_filename = "full_page_screenshot.png"
            elif os.path.exists("error_screenshot.png"):
                screenshot_filename = "error_screenshot.png"
            else:
                st.error("Could not find the screenshot file.")
                st.stop()
        
        st.session_state.screenshot_captured = True
        st.session_state.screenshot_filename = screenshot_filename
        
        progress.progress(100)
        status.text("Table captured successfully!")
        
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        import traceback
        st.text(traceback.format_exc())

# Display screenshot and options if captured
if st.session_state.screenshot_captured:
    # Display the image full width
    image = Image.open(st.session_state.screenshot_filename)
    st.image(image, caption=f"Captured table: {table_title}", use_container_width=True)
    col1, col2, col3 = st.columns([2,2,2]) 
    with col1:
        if st.button("Delete Screenshot", use_container_width=True):
            if os.path.exists(st.session_state.screenshot_filename):
                os.remove(st.session_state.screenshot_filename)
            st.session_state.screenshot_captured = False
            st.session_state.screenshot_filename = ""
            st.experimental_rerun()
    
    with col2:
        if st.button("Capture Again", use_container_width=True):
            st.session_state.screenshot_captured = False
            st.session_state.screenshot_filename = ""
            st.experimental_rerun()
    
    with col3:
        if st.button("Extract Data", use_container_width=True):
            try:
                progress = st.progress(0)
                status = st.empty()
                status.text("Processing with Gemini API...")
                
                # Configure Gemini API
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-2.0-flash-lite-001')
                
                # Open image
                image = Image.open(st.session_state.screenshot_filename)
                
                # Create prompt with format specification
                prompt = f"Extract the table data from the image in {format_type} format."
                
                # Process with Gemini
                response = model.generate_content([prompt, image])
                
                progress.progress(50)
                status.text("Processing table data...")
                
                # Get result
                result_text = response.text
                
                # Process based on format type
                if format_type == "JSON":
                    # Extract JSON if wrapped in code blocks
                    if "```json" in result_text and "```" in result_text:
                        json_content = result_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in result_text:
                        json_content = result_text.split("```")[1].split("```")[0].strip()
                    else:
                        json_content = result_text
                    
                    try:
                        # Parse JSON
                        table_data = json.loads(json_content)
                        st.session_state.extracted_data = {
                            "content": json_content,
                            "filename": f"{st.session_state.safe_title}.json",
                            "format": "JSON"
                        }
                        
                        # Display as dataframe if it's a list
                        if isinstance(table_data, list) and len(table_data) > 0:
                            st.subheader("Extracted Table Data (Preview)")
                            st.dataframe(pd.DataFrame(table_data))
                        else:
                            st.subheader("Extracted Data (JSON Preview)")
                            st.json(table_data)
                    
                    except json.JSONDecodeError:
                        st.warning("Couldn't parse JSON response. Showing raw output.")
                        st.text_area("Raw Response", result_text, height=300)
                        st.session_state.extracted_data = {
                            "content": result_text,
                            "filename": f"{st.session_state.safe_title}.txt",
                            "format": "TEXT"
                        }
                
                elif format_type == "CSV":
                    # Try to extract CSV content
                    if "```csv" in result_text and "```" in result_text:
                        csv_content = result_text.split("```csv")[1].split("```")[0].strip()
                    elif "```" in result_text:
                        csv_content = result_text.split("```")[1].split("```")[0].strip()
                    else:
                        csv_content = result_text
                    
                    try:
                        # Try to load as dataframe
                        df = pd.read_csv(pd.StringIO(csv_content))
                        st.subheader("Extracted Table Data (CSV Preview)")
                        st.dataframe(df)
                        st.session_state.extracted_data = {
                            "content": csv_content,
                            "filename": f"{st.session_state.safe_title}.csv",
                            "format": "CSV"
                        }
                    except:
                        st.warning("Couldn't parse CSV response. Showing raw output.")
                        st.text_area("Raw Response", result_text, height=300)
                        st.session_state.extracted_data = {
                            "content": result_text,
                            "filename": f"{st.session_state.safe_title}.txt",
                            "format": "TEXT"
                        }
                
                elif format_type == "HTML":
                    # Try to extract HTML content
                    if "```html" in result_text and "```" in result_text:
                        html_content = result_text.split("```html")[1].split("```")[0].strip()
                    elif "```" in result_text:
                        html_content = result_text.split("```")[1].split("```")[0].strip()
                    else:
                        html_content = result_text
                    
                    st.subheader("Extracted Table Data (HTML Preview)")
                    st.code(html_content, language="html")
                    
                    # Also try to render it
                    st.subheader("Rendered HTML Table")
                    st.components.v1.html(html_content, height=400)
                    
                    st.session_state.extracted_data = {
                        "content": html_content,
                        "filename": f"{st.session_state.safe_title}.html",
                        "format": "HTML"
                    }
                
                progress.progress(100)
                status.text("Table extraction completed!")
                
            except Exception as e:
                st.error(f"An error occurred during extraction: {str(e)}")
                import traceback
                st.text(traceback.format_exc())

# Download option
if st.session_state.extracted_data:
    st.markdown("### Download Extracted Data")
    data = st.session_state.extracted_data
    download_link = get_download_link(
        data["content"], 
        data["filename"], 
        f"Download as {data['format']}"
    )
    st.markdown(download_link, unsafe_allow_html=True)

# Q&A Section
if st.session_state.extracted_data:
    st.markdown("---")
    st.header("Ask Questions About Your Table")
    st.markdown("Ask questions about the extracted table data. Questions unrelated to the table will not be answered.")
    
    # Create columns for the question input and button
    col1, col2 = st.columns([4, 1])
    with col1:
        question = st.text_input("Your question:", key="table_question")
    with col2:
        submit_question = st.button("Ask", use_container_width=True)
    
    if submit_question and question:
        try:
            # Check if API key is available
            if not GEMINI_API_KEY:
                st.error("Please provide a valid Gemini API key to use the Q&A feature.")
                st.stop()
            
            with st.spinner("Processing your question..."):
                # Configure Gemini API (should already be configured from earlier)
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-2.0-flash-lite-001')
                
                # Create context from the extracted data
                table_content = st.session_state.extracted_data["content"]
                
                # Create prompt for the Q&A
                qa_prompt = f"""
                Table data: 
                {table_content}
                
                Question: {question}
                
                Instructions:
                1. If the question is related to the table data, answer it accurately and concisely.
                2. If the question is NOT related to the table data, respond with "UNRELATED" only.
                """
                
                # Process with Gemini
                response = model.generate_content(qa_prompt)
                answer = response.text.strip()
                
                # Display answer or message about unrelated question
                if answer == "UNRELATED":
                    st.warning("Your question does not appear to be related to the table data.")
                else:
                    st.success("Answer:")
                    st.write(answer)
                    
        except Exception as e:
            st.error(f"An error occurred while processing your question: {str(e)}")
            with st.expander("See error details"):
                st.text(traceback.format_exc())