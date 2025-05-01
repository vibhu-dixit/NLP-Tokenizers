# app.py
import streamlit as st
import os
import re
import json
import pandas as pd
from PIL import Image
import google.generativeai as genai
from io import StringIO, BytesIO
import base64
import uuid
import logging
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

# --- Import local modules ---
from getImages import screenshot_tables
from amazonTables import amazon_tables

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger('web_table_extractor')

# --- API Configuration ---
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"  # Replace with your actual API key

if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
    st.warning("Gemini API Key not found or not set. Please set it. AI features will be disabled.", icon="⚠️")
    ai_enabled = False
else:
    ai_enabled = True
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Initialize the model once at app startup
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info("Gemini API initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing Gemini API: {e}")
        st.error(f"Error initializing Gemini API: {e}")
        ai_enabled = False

# --- Page Setup ---
st.set_page_config(
    page_title="Web Table Extractor", 
    layout="wide",
    menu_items={
        'About': "# Web Table Extractor\nExtract tables from websites with AI assistance."
    }
)

st.title("🌐 Web Table Extractor")
st.markdown("Extract data from all tables on webpages. Handles Amazon product comparisons directly, uses AI for table analysis.")

# Initialize session state variables
if 'extraction_method' not in st.session_state:
    st.session_state.extraction_method = None
if 'data_extracted' not in st.session_state:
    st.session_state.data_extracted = False
if 'extraction_in_progress' not in st.session_state:
    st.session_state.extraction_in_progress = False
if 'extracted_tables' not in st.session_state:
    st.session_state.extracted_tables = []
if 'extracted_formats' not in st.session_state:
    st.session_state.extracted_formats = []
if 'extracted_filenames' not in st.session_state:
    st.session_state.extracted_filenames = []
if 'screenshot_captured' not in st.session_state:
    st.session_state.screenshot_captured = False
if 'screenshot_filenames' not in st.session_state:
    st.session_state.screenshot_filenames = []
if 'selected_table_index' not in st.session_state:
    st.session_state.selected_table_index = 0
if 'ai_processed_tables' not in st.session_state:
    st.session_state.ai_processed_tables = {}
if 'current_question' not in st.session_state:
    st.session_state.current_question = ""
if 'question_history' not in st.session_state:
    st.session_state.question_history = []

def get_download_link(content, filename, text, format_type):
    """
    Creates a download link for text content.
    
    Args:
        content: The content to download (string or bytes)
        filename: The filename for the download
        text: The text to display for the download link
        format_type: The format of the content (CSV, JSON, HTML, TEXT)
        
    Returns:
        HTML string with download link
    """
    if isinstance(content, bytes):
        b64 = base64.b64encode(content).decode()
    else:
        b64 = base64.b64encode(str(content).encode('utf-8')).decode() # Ensure UTF-8
    
    mime_type = {
        "CSV": "text/csv",
        "JSON": "application/json",
        "HTML": "text/html",
        "TEXT": "text/plain"
    }.get(format_type, "application/octet-stream")
    
    href = f'<a href="data:{mime_type};base64,{b64}" download="{filename}">{text}</a>'
    return href

def process_with_ai(screenshot_path, format_type):
    """
    Process a table screenshot using Gemini API to extract structured data
    
    Args:
        screenshot_path: Path to the screenshot image
        format_type: Desired output format (CSV, JSON, HTML)
        
    Returns:
        dict: Processed data in the requested format
    """
    if not ai_enabled:
        return {
            "success": False, 
            "error": "AI processing is disabled. Please check your API key."
        }
    
    try:
        # Read the image
        with open(screenshot_path, "rb") as img_file:
            image_bytes = img_file.read()
        
        # Create image for model
        image = genai.Image(image_bytes)
        
        # Create prompt based on format type
        prompt = f"""Extract the table data accurately from the image. 
Output the result ONLY in {format_type} format, without any introductory text, explanations, or markdown formatting like ```. 
Just provide the raw {format_type} data.
For CSV, use commas as separators and include a header row.
For JSON, use a list of objects where each object represents a row.
For HTML, create a proper HTML table with <table>, <tr>, <th>, and <td> tags."""
        
        # Generate content
        response = gemini_model.generate_content([prompt, image], stream=False)
        result = response.text.strip()
        
        # Remove any markdown code blocks if present
        result = re.sub(r'```[a-zA-Z]*\n', '', result)
        result = re.sub(r'```', '', result)
        
        # Process the result based on format
        if format_type == "CSV":
            # Try to parse CSV
            try:
                df = pd.read_csv(StringIO(result))
                return {
                    "success": True,
                    "format": format_type,
                    "raw": result,
                    "dataframe": df
                }
            except Exception as csv_err:
                logger.error(f"Error parsing CSV from AI: {csv_err}")
                return {
                    "success": False,
                    "error": f"AI returned invalid CSV: {str(csv_err)}",
                    "raw": result
                }
                
        elif format_type == "JSON":
            # Try to parse JSON
            try:
                # Clean up any text before or after the JSON
                json_match = re.search(r'(\[.*\]|\{.*\})', result, re.DOTALL)
                if json_match:
                    result = json_match.group(0)
                
                json_data = json.loads(result)
                if isinstance(json_data, list):
                    # Convert JSON to DataFrame
                    df = pd.DataFrame(json_data)
                    return {
                        "success": True,
                        "format": format_type,
                        "raw": result,
                        "dataframe": df
                    }
                else:
                    return {
                        "success": False,
                        "error": "AI returned JSON but not in expected list format",
                        "raw": result
                    }
            except Exception as json_err:
                logger.error(f"Error parsing JSON from AI: {json_err}")
                return {
                    "success": False,
                    "error": f"AI returned invalid JSON: {str(json_err)}",
                    "raw": result
                }
                
        elif format_type == "HTML":
            # Try to extract the table from HTML
            try:
                # Look for table tags
                table_match = re.search(r'<table.*?>.*?</table>', result, re.DOTALL)
                if table_match:
                    table_html = table_match.group(0)
                    # Parse HTML table into DataFrame
                    df = pd.read_html(StringIO(table_html))[0]
                    return {
                        "success": True,
                        "format": format_type,
                        "raw": result,
                        "html": table_html,
                        "dataframe": df
                    }
                else:
                    return {
                        "success": False,
                        "error": "AI returned HTML but no table tags found",
                        "raw": result
                    }
            except Exception as html_err:
                logger.error(f"Error parsing HTML from AI: {html_err}")
                return {
                    "success": False,
                    "error": f"AI returned invalid HTML: {str(html_err)}",
                    "raw": result
                }
        
        # Default fallback
        return {
            "success": False,
            "error": f"Unsupported format type: {format_type}",
            "raw": result
        }
        
    except Exception as e:
        logger.error(f"Error in AI processing: {e}")
        return {
            "success": False,
            "error": f"AI processing error: {str(e)}"
        }

def ask_question_about_table(question, table_data):
    """
    Ask a question about a table using Gemini AI
    
    Args:
        question: User's question about the table
        table_data: Dictionary containing table information
        
    Returns:
        str: AI response to the question
    """
    if not ai_enabled:
        return "AI is not enabled. Please check your API key."
    
    try:
        # Check if we have a DataFrame
        if 'dataframe' not in table_data or table_data['dataframe'] is None:
            return "No table data available to answer questions about."
        
        # Convert DataFrame to string representation
        df = table_data['dataframe']
        df_str = df.to_string(index=False)
        
        # Check for image columns and add context
        has_images = False
        image_columns = []
        for col in df.columns:
            for value in df[col]:
                if isinstance(value, str) and ('<img src=' in value or value.startswith('Image:')):
                    has_images = True
                    if col not in image_columns:
                        image_columns.append(col)
        
        image_context = ""
        if has_images:
            image_context = f"The table contains images in these columns: {', '.join(image_columns)}. "
            image_context += "Image cells are marked with 'Image:' followed by a path, or contain HTML img tags."
        
        # Create context for Gemini
        table_title = table_data.get('title', 'Unknown Table')
        
        context = f"""Table Title: {table_title}
Source URL: {table_data.get('source_url', 'Unknown Source')}
{image_context}

Table Data:
{df_str}

Based on the table data above, answer the following question.
If the question cannot be answered from the provided data, state that clearly.
If the question is unrelated to the table or extracted data, answer with "I can only answer questions about the table data."

User Question: {question}

Answer:"""
        
        # Generate response
        response = gemini_model.generate_content(context)
        answer = response.text.strip()
        
        return answer
    
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        return f"An error occurred while processing your question: {str(e)}"

# --- UI Layout ---

# Sidebar information
with st.sidebar:
    st.header("Instructions")
    st.markdown("""
    1. Enter a webpage URL in the input field
    2. Select your desired output format
    3. Click Extract to process all tables on the page
    4. View and download extracted tables
    5. Ask questions about the data using AI
    """)
    
    st.header("Features")
    st.markdown("""
    - Extracts all tables from any webpage
    - Direct support for Amazon product pages
    - AI-powered data extraction and analysis
    - Multiple export formats: CSV, JSON, HTML
    - Image handling in tables
    """)
    
    # Add info about AI capabilities if enabled
    if ai_enabled:
        st.header("AI Capabilities")
        st.markdown("""
        - AI-assisted table extraction
        - Question answering about table data
        - Data validation and cleaning
        """)

# Main page layout
url = st.text_input("Enter the URL of the webpage:", key="url_input", 
                   help="Enter the full URL including https://")

# Check if it's an Amazon product page
is_amazon_product_page = bool(url and ("amazon.com" in url or "amzn." in url or "amzn.to" in url) and 
                             ("/dp/" in url or "/gp/product/" in url))

if is_amazon_product_page:
    st.info("Amazon product page detected. Direct extraction will be attempted.", icon="🛒")
    button_text = "Extract Amazon Tables"
else:
    st.info("General webpage detected. Extracting all tables from the page.", icon="📄")
    button_text = "Extract All Tables"

col1, col2 = st.columns([3, 1])

with col1:
    format_type = st.selectbox(
        "Select desired output format:",
        options=["CSV", "JSON", "HTML"],
        index=0, # Default to CSV
        help="The format for the extracted table data"
    )

with col2:
    use_ai = st.toggle("Use AI for table extraction", value=True, 
                      help="Enable AI to assist with extracting tables that might be difficult to parse")

# --- Action Button ---
if st.button(button_text, key="main_action_button", disabled=not url or st.session_state.extraction_in_progress):
    # Set extraction in progress flag
    st.session_state.extraction_in_progress = True
    
    # Reset state before action
    st.session_state.update({
        'data_extracted': False, 
        'extracted_tables': [], 
        'extracted_formats': [],
        'extracted_filenames': [], 
        'screenshot_captured': False,
        'screenshot_filenames': [], 
        'extraction_method': None,
        'selected_table_index': 0,
        'ai_processed_tables': {}
    })
    
    progress = st.progress(0)
    status = st.empty()
    
    try:
        if is_amazon_product_page:
            # --- Amazon Direct Extraction Workflow ---
            st.session_state.extraction_method = 'amazon'
            status.text("Attempting direct extraction from Amazon...")
            progress.progress(25)
            
            # Call the imported function
            extracted_result = amazon_tables(url)
            progress.progress(75)
            
            # Check the status returned by the function
            if extracted_result['status'] == 'success':
                status.text("Amazon table extracted successfully!")
                df = extracted_result["dataframe"]
                html_content = extracted_result["html"]
                
                # Save as a table entry
                table_data = {
                    "title": "Amazon Product Comparison",
                    "dataframe": df,
                    "html": html_content,
                    "source_url": url,
                    "has_images": any("<img" in str(cell) for row in df.values for cell in row)
                }
                
                # Process images in the table for display
                if table_data["has_images"]:
                    status.text("Processing images in the Amazon table...")
                    # Extract and save images
                    image_dir = "extracted_images"
                    os.makedirs(image_dir, exist_ok=True)
                    
                    # Process DataFrame to download images and create displayable versions
                    processed_df = df.copy()
                    display_df = df.copy()  # New DataFrame for Streamlit display
                    
                    for i, row in df.iterrows():
                        for col in df.columns:
                            cell_val = str(row[col])
                            if "<img src=" in cell_val:
                                # Extract image URL
                                img_url_match = re.search(r'src="([^"]+)"', cell_val)
                                if img_url_match:
                                    img_url = img_url_match.group(1)
                                    img_filename = f"{image_dir}/amazon_img_{uuid.uuid4().hex[:8]}.jpg"
                                    
                                    try:
                                        import requests
                                        img_response = requests.get(img_url, stream=True, timeout=10)
                                        if img_response.status_code == 200:
                                            with open(img_filename, 'wb') as img_file:
                                                img_file.write(img_response.content)
                                            
                                            # Replace with local path in processed DataFrame (for export)
                                            processed_df.at[i, col] = f"Image: {img_filename}"
                                            
                                            # For Streamlit display, we'll use a special marker that we'll replace later
                                            display_df.at[i, col] = f"IMAGE:{img_filename}"
                                        else:
                                            print(f"Error downloading image {img_url}, status code: {img_response.status_code}")
                                            processed_df.at[i, col] = f"Image URL: {img_url} (download failed, status: {img_response.status_code})"
                                            display_df.at[i, col] = f"Image URL: {img_url} (download failed)"
                                    except Exception as img_err:
                                        print(f"Error downloading image {img_url}: {img_err}")
                                        processed_df.at[i, col] = f"Image URL: {img_url} (download failed)"
                                        display_df.at[i, col] = f"Image URL: {img_url} (download failed)"
                    
                    # Update the table data with processed dataframe and display dataframe
                    table_data["dataframe_with_local_images"] = processed_df
                    table_data["display_dataframe"] = display_df
                else:
                    # If no images, display_dataframe is the same as the original
                    table_data["display_dataframe"] = df
                
                # Format table data for download
                if format_type == "CSV":
                    table_data["content"] = df.to_csv(index=False)
                    table_data["format"] = "CSV"
                    table_data["filename"] = f"amazon_comparison.csv"
                elif format_type == "JSON":
                    table_data["content"] = df.to_json(orient="records", indent=2)
                    table_data["format"] = "JSON"
                    table_data["filename"] = f"amazon_comparison.json"
                else:  # HTML
                    table_data["content"] = f"<html><head><meta charset='UTF-8'><title>Amazon Comparison</title></head><body>\n{html_content}\n</body></html>"
                    table_data["format"] = "HTML"
                    table_data["filename"] = f"amazon_comparison.html"
                
                # Update content based on format with local image paths if images were processed
                if table_data.get("has_images"):
                    if format_type == "CSV":
                        table_data["content_with_local_images"] = processed_df.to_csv(index=False)
                    elif format_type == "JSON":
                        table_data["content_with_local_images"] = processed_df.to_json(orient="records", indent=2)
                    else:  # HTML
                        # Create HTML with image tags for better display
                        html_df = processed_df.copy()
                        for i, row in html_df.iterrows():
                            for col in html_df.columns:
                                cell_val = str(row[col])
                                if cell_val.startswith("Image: "):
                                    img_path = cell_val.replace("Image: ", "")
                                    html_df.at[i, col] = f'<img src="{img_path}" style="max-width:100px; max-height:100px;">'
                        
                        local_html = html_df.to_html(escape=False, index=False)
                        table_data["content_with_local_images"] = f"<html><head><meta charset='UTF-8'><title>Amazon Comparison</title></head><body>\n{local_html}\n</body></html>"
                
                # Add to session state
                st.session_state.extracted_tables.append(table_data)
                st.session_state.extracted_formats.append(format_type)
                st.session_state.extracted_filenames.append(table_data["filename"])
                st.session_state.data_extracted = True
                
                progress.progress(100)
                st.rerun()  # Rerun to show results
            else:
                # Handle different failure statuses from amazon_tables
                status.error(f"Amazon Extraction Failed: {extracted_result.get('message', 'Unknown error')}")
                st.error(f"Details: {extracted_result.get('message', 'No further details.')}")
                progress.progress(100)
                st.session_state.data_extracted = False
            
        else:
            # --- General Webpage Table Extraction Workflow ---
            st.session_state.extraction_method = 'general'
            status.text("Extracting all tables from the webpage...")
            progress.progress(10)
            
            # Create a unique identifier for this extraction
            extraction_id = uuid.uuid4().hex[:8]
            domain_name = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
            safe_domain = re.sub(r'[^\w\s-]', '', domain_name).strip().replace('.', '_')
            
            # Get all tables from the page
            tables_info = screenshot_tables(url)
            
            if not tables_info or len(tables_info) == 0:
                status.warning("No tables found on the webpage.")
                progress.progress(100)
                st.warning("No tables were detected on the provided webpage. Try a different URL.")
                st.session_state.extraction_in_progress = False
                st.stop()
            
            status.text(f"Found {len(tables_info)} tables on the webpage. Processing...")
            progress.progress(30)
            
            # Check if we should use AI for extraction
            if use_ai and ai_enabled:
                ai_extraction = True
                status.text(f"Using AI to enhance table extraction...")
            else:
                ai_extraction = False
            
            # Process each table
            for idx, table_info in enumerate(tables_info):
                progress_value = 30 + int(60 * (idx + 1) / len(tables_info))
                progress.progress(progress_value)
                status.text(f"Processing table {idx+1} of {len(tables_info)}...")
                
                table_title = table_info.get("title", f"Table {idx+1}")
                safe_title = re.sub(r'[^\w\s-]', '', table_title).strip().replace(' ', '_')
                
                if not safe_title:
                    safe_title = f"table_{idx+1}"
                
                # For each table, store screenshot if available
                screenshot_path = table_info.get("screenshot", "")
                if screenshot_path and os.path.exists(screenshot_path):
                    st.session_state.screenshot_filenames.append(screenshot_path)
                
                # Process the table data
                df = table_info.get("dataframe")
                
                # If we have a screenshot but no dataframe or AI is enabled, try AI extraction
                if ai_extraction and screenshot_path and (df is None or df.empty):
                    status.text(f"Using AI to extract data from table {idx+1}...")
                    
                    # Process with AI
                    ai_result = process_with_ai(screenshot_path, format_type)
                    
                    if ai_result.get("success", False):
                        # AI extraction successful
                        df = ai_result.get("dataframe")
                        # Store AI result for later reference
                        st.session_state.ai_processed_tables[safe_title] = ai_result
                        
                        # If original extraction didn't work but AI did, update table info
                        if table_info.get("dataframe") is None or table_info.get("dataframe").empty:
                            table_info["dataframe"] = df
                            table_info["ai_extracted"] = True
                            
                            # Update HTML if we got it from AI
                            if "html" in ai_result:
                                table_info["html"] = ai_result["html"]
                
                if df is not None:
                    # Check for images in the dataframe
                    has_images = any("<img src=" in str(cell) for row in df.values for cell in row)
                    
                    # Prepare table data
                    table_data = {
                        "title": table_title,
                        "dataframe": df,
                        "html": table_info.get("html", df.to_html(escape=False, index=False)),
                        "source_url": url,
                        "has_images": has_images,
                        "screenshot": screenshot_path,
                        "ai_extracted": table_info.get("ai_extracted", False)
                    }
                    
                    # Handle any images in the table
                    if has_images:
                        image_dir = "extracted_images"
                        os.makedirs(image_dir, exist_ok=True)
                        
                        # Process DataFrame to download images and update image paths
                        processed_df = df.copy()
                        for i, row in df.iterrows():
                            for col in df.columns:
                                cell_val = str(row[col])
                                if "<img src=" in cell_val:
                                    # Extract image URL
                                    img_url_match = re.search(r'src="([^"]+)"', cell_val)
                                    if img_url_match:
                                        img_url = img_url_match.group(1)
                                        # Fix URLs that start with // by adding https:
                                        if img_url.startswith("//"):
                                            img_url = "https:" + img_url
                                        # Fix relative URLs
                                        elif not img_url.startswith(('http://', 'https://')):
                                            # Handle relative URLs
                                            domain = re.search(r'https?://[^/]+', url).group(0)
                                            if img_url.startswith('/'):
                                                img_url = f"{domain}{img_url}"
                                            else:
                                                img_url = f"{domain}/{img_url}"
                                                
                                        img_filename = f"{image_dir}/{safe_domain}_{safe_title}_img_{uuid.uuid4().hex[:8]}.jpg"
                                        
                                        try:
                                            import requests
                                            img_response = requests.get(img_url, stream=True, timeout=10)
                                            if img_response.status_code == 200:
                                                with open(img_filename, 'wb') as img_file:
                                                    img_file.write(img_response.content)
                                                # Store image reference - we'll use HTML to display in exports but plain path in DataFrame
                                                processed_df.at[i, col] = f'Image: {img_filename}'
                                            else:
                                                logger.warning(f"Error downloading image {img_url}, status code: {img_response.status_code}")
                                                processed_df.at[i, col] = f"Image URL: {img_url} (download failed, status: {img_response.status_code})"
                                        except Exception as img_err:
                                            logger.error(f"Error downloading image {img_url}: {img_err}")
                                            processed_df.at[i, col] = f"Image URL: {img_url} (download failed)"
                        
                        # Update the table data with processed dataframe
                        table_data["dataframe_with_local_images"] = processed_df
                    
                    # Format table data
                    filename_base = f"{safe_domain}_{safe_title}_{extraction_id}"
                    if format_type == "CSV":
                        table_data["content"] = df.to_csv(index=False)
                        table_data["format"] = "CSV"
                        table_data["filename"] = f"{filename_base}.csv"
                        
                        if has_images:
                            table_data["content_with_local_images"] = processed_df.to_csv(index=False)
                    
                    elif format_type == "JSON":
                        table_data["content"] = df.to_json(orient="records", indent=2)
                        table_data["format"] = "JSON"
                        table_data["filename"] = f"{filename_base}.json"
                        
                        if has_images:
                            table_data["content_with_local_images"] = processed_df.to_json(orient="records", indent=2)
                    
                    else:  # HTML
                        table_html = table_info.get("html", df.to_html(escape=False, index=False))
                        table_data["content"] = f"<html><head><meta charset='UTF-8'><title>{table_title}</title></head><body>\n{table_html}\n</body></html>"
                        table_data["format"] = "HTML"
                        table_data["filename"] = f"{filename_base}.html"
                        
                        if has_images:
                            # Create HTML with image tags for the local files
                            html_df = processed_df.copy()
                            for i, row in html_df.iterrows():
                                for col in html_df.columns:
                                    cell_val = str(row[col])
                                    if cell_val.startswith("Image: "):
                                        img_path = cell_val.replace("Image: ", "")
                                        html_df.at[i, col] = f'<img src="{img_path}" style="max-width:100px; max-height:100px;">'
                            
                            local_html = html_df.to_html(escape=False, index=False)
                            table_data["content_with_local_images"] = f"<html><head><meta charset='UTF-8'><title>{table_title}</title></head><body>\n{local_html}\n</body></html>"
                    
                    # Add to session state
                    st.session_state.extracted_tables.append(table_data)
                    st.session_state.extracted_formats.append(format_type)
                    st.session_state.extracted_filenames.append(table_data["filename"])
            
            # Set flag that data was extracted successfully
            if st.session_state.extracted_tables:
                st.session_state.data_extracted = True
                st.session_state.screenshot_captured = bool(st.session_state.screenshot_filenames)
                status.text(f"Successfully extracted {len(st.session_state.extracted_tables)} tables!")
            else:
                status.warning("No tables could be extracted from the webpage.")
            
            progress.progress(100)
            st.session_state.extraction_in_progress = False
            st.rerun()  # Show results
            
    except Exception as e:
        st.error(f"An error occurred during table extraction: {str(e)}")
        import traceback
        st.expander("Traceback").code(traceback.format_exc())
        progress.progress(100)
        st.session_state.extraction_in_progress = False

# --- Display Results and Download Links ---
if st.session_state.data_extracted and st.session_state.extracted_tables:
    st.markdown("---")
    st.header(f"📊 Extracted Tables ({len(st.session_state.extracted_tables)})")
    
    # Table selection if multiple tables
    if len(st.session_state.extracted_tables) > 1:
        table_titles = [f"{idx+1}. {table['title']}" for idx, table in enumerate(st.session_state.extracted_tables)]
        selected_table_index = st.selectbox(
            "Select a table to view:",
            options=range(len(table_titles)),
            format_func=lambda x: table_titles[x],
            index=st.session_state.selected_table_index
        )
        st.session_state.selected_table_index = selected_table_index
    else:
        selected_table_index = 0
    
    # Get the selected table data
    table_data = st.session_state.extracted_tables[selected_table_index]
    
    # Display table information
    st.subheader(table_data["title"])
    
    # Show extraction method
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"Source URL: {table_data['source_url']}")
    with col2:
        if table_data.get("ai_extracted", False):
            st.caption("⚙️ AI-enhanced extraction")
    
    # Display screenshot if available
    if "screenshot" in table_data and table_data["screenshot"] and os.path.exists(table_data["screenshot"]):
        with st.expander("View Table Screenshot", expanded=True):
            try:
                image = Image.open(table_data["screenshot"])
                st.image(image, caption=f"Screenshot: {table_data['title']}", use_column_width=True)
            except Exception as img_e:
                st.error(f"Error loading screenshot image: {img_e}")
    
    # Display the dataframe with images if available
    if "display_dataframe" in table_data:
        display_df = table_data["display_dataframe"].copy()
        
        # Replace image markers with actual Streamlit image elements
        for i, row in display_df.iterrows():
            for col in display_df.columns:
                cell_val = str(row[col])
                if cell_val.startswith("IMAGE:"):
                    # Extract image path
                    img_path = cell_val.replace("IMAGE:", "")
                    # We'll create a special placeholder in the dataframe
                    display_df.at[i, col] = f"Image {i}-{col}"
        
        # Display the dataframe
        if display_df.shape[0] > 100 or display_df.shape[1] > 20:
            st.warning(f"Large table detected ({display_df.shape[0]} rows, {display_df.shape[1]} columns). Showing first 100 rows.")
            st.dataframe(display_df.head(100), use_container_width=True, hide_index=True)
        else:
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Now display the images separately, after the dataframe
        st.write("### Images from the table:")
        cols = st.columns(3)  # Create 3 columns for the images
        col_idx = 0
        
        for i, row in table_data["display_dataframe"].iterrows():
            for col in table_data["display_dataframe"].columns:
                cell_val = str(row[col])
                if cell_val.startswith("IMAGE:"):
                    # Extract image path
                    img_path = cell_val.replace("IMAGE:", "")
                    # Display the image with caption
                    with cols[col_idx % 3]:
                        try:
                            st.image(img_path, caption=f"Row {i+1}, {col}", width=150)
                            col_idx += 1
                        except Exception as img_err:
                            st.error(f"Error displaying image: {img_err}")
        
        st.caption(f"Table Preview ({display_df.shape[0]} rows, {display_df.shape[1]} columns)")
    else:
        # Fallback to original dataframe if display version not available
        df = table_data["dataframe"]
        if df is not None:
            if df.shape[0] > 100 or df.shape[1] > 20:
                st.warning(f"Large table detected ({df.shape[0]} rows, {df.shape[1]} columns). Showing first 100 rows.")
                st.dataframe(df.head(100), use_container_width=True, hide_index=True)
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.caption(f"Table Preview ({df.shape[0]} rows, {df.shape[1]} columns)")
        
        # Display raw content
        with st.expander(f"View Raw {table_data['format']} Output"):
            display_format = 'json' if table_data['format'] == 'JSON' else table_data['format'].lower()
            try:
                if table_data['format'] == "HTML": 
                    st.code(table_data['content'], language='html')
                elif table_data['format'] == "JSON": 
                    st.json(table_data['content'])
                else: 
                    st.text(table_data['content'])
            except Exception as display_err:
                st.text(f"Raw content:\n{table_data['content']}")
        
        # If table has images that were processed with local paths
        if table_data.get("has_images") and "dataframe_with_local_images" in table_data:
            with st.expander("View Table With Local Image Paths", expanded=False):
                st.dataframe(table_data["dataframe_with_local_images"])
                st.caption("Table with local file paths to downloaded images")
        
        # If we have AI-processed data for this table
        safe_title = re.sub(r'[^\w\s-]', '', table_data["title"]).strip().replace(' ', '_')
        if safe_title in st.session_state.ai_processed_tables:
            with st.expander("View AI Processing Details", expanded=False):
                ai_result = st.session_state.ai_processed_tables[safe_title]
                st.json(ai_result)
    
    # Download links
    st.markdown("---")
    st.subheader("⬇️ Download Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        try:
            download_link = get_download_link(
                table_data['content'],
                table_data['filename'],
                f"Download as {table_data['format']} ({table_data['filename']})",
                table_data['format']
            )
            st.markdown(download_link, unsafe_allow_html=True)
        except Exception as dl_error:
            st.error(f"Error generating download link: {dl_error}")
    
    # Option to download version with local image paths if available
    if table_data.get("has_images") and "content_with_local_images" in table_data:
        with col2:
            try:
                local_img_filename = table_data['filename'].replace(".", "_local_images.")
                download_link = get_download_link(
                    table_data['content_with_local_images'],
                    local_img_filename,
                    f"Download with local image paths ({local_img_filename})",
                    table_data['format']
                )
                st.markdown(download_link, unsafe_allow_html=True)
            except Exception as dl_error:
                st.error(f"Error generating local images download link: {dl_error}")
    
    # Option to download all tables as a zip
    if len(st.session_state.extracted_tables) > 1:
        st.markdown("---")
        if st.button("Prepare ZIP file with all tables", use_container_width=True):
            try:
                # Create a BytesIO object to store the zip file
                zip_buffer = BytesIO()
                
                # Create a ZipFile object
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Add each table to the zip file
                    for idx, table in enumerate(st.session_state.extracted_tables):
                        filename = table['filename']
                        content = table['content']
                        
                        # Make sure content is converted to bytes
                        if isinstance(content, str):
                            content = content.encode('utf-8')
                        
                        # Add the content to the zip file
                        zipf.writestr(filename, content)
                        
                        # If there's a version with local image paths, add it too
                        if table.get("has_images") and "content_with_local_images" in table:
                            local_img_filename = filename.replace(".", "_local_images.")
                            local_content = table['content_with_local_images']
                            
                            # Make sure content is converted to bytes
                            if isinstance(local_content, str):
                                local_content = local_content.encode('utf-8')
                                
                            zipf.writestr(local_img_filename, local_content)
                        
                        # Include screenshot if available
                        if "screenshot" in table and table["screenshot"] and os.path.exists(table["screenshot"]):
                            screenshot_name = f"screenshots/{os.path.basename(table['screenshot'])}"
                            zipf.write(table["screenshot"], screenshot_name)
                        
                    # Include any downloaded images
                    image_dir = "extracted_images"
                    if os.path.exists(image_dir):
                        for img_file in os.listdir(image_dir):
                            img_path = os.path.join(image_dir, img_file)
                            if os.path.isfile(img_path):
                                zipf.write(img_path, f"extracted_images/{img_file}")
                
                # Prepare the download link for the zip file
                zip_buffer.seek(0)
                domain_name = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
                safe_domain = re.sub(r'[^\w\s-]', '', domain_name).strip().replace('.', '_')
                zip_filename = f"{safe_domain}_all_tables.zip"
                
                st.download_button(
                    label=f"Download All Tables as ZIP",
                    data=zip_buffer,
                    file_name=zip_filename,
                    mime="application/zip",
                    use_container_width=True
                )
            except Exception as zip_error:
                st.error(f"Error creating ZIP file: {zip_error}")
    
    # --- Q&A Section ---
    if ai_enabled:
        st.markdown("---")
        st.header("❓ Ask Questions About Your Table")
        st.markdown("Use Gemini AI to analyze and get insights from the extracted table data.")
        
        # Get the appropriate dataframe from table_data
        if "dataframe" in table_data and table_data["dataframe"] is not None:
            df_for_qa = table_data["dataframe"]  # Use this for Q&A            
            col1, col2 = st.columns([4, 1])
            with col1:
                question = st.text_input(
                    "Your question:", 
                    key="table_question_input",
                    placeholder="E.g., What's the highest value in the table? What patterns do you see?",
                    value=st.session_state.current_question
                )
            with col2:
                submit_question = st.button("Ask AI", use_container_width=True, key="ask_button")
            
            if submit_question and question:
                st.session_state.current_question = question
                
                # Add to history if not already there
                if question not in st.session_state.question_history:
                    st.session_state.question_history.append(question)
                
                try:
                    with st.spinner("🧠 Analyzing table data..."):
                        answer = ask_question_about_table(question, table_data)
                        st.success(answer)
                except Exception as e:
                    st.error(f"An error occurred processing your question: {str(e)}")
                    with st.expander("See error details"):
                        st.exception(e)
            
            # Show question history if available
            if st.session_state.question_history:
                with st.expander("Previous Questions", expanded=False):
                    for prev_q in st.session_state.question_history:
                        if st.button(prev_q, key=f"prev_{prev_q[:20]}"):
                            st.session_state.current_question = prev_q
                            st.rerun()
        else:
            st.info("No extracted data available to ask questions about.")
            
    # Add a footer
    st.markdown("---")
    st.caption("Web Table Extractor • Extract and analyze tables from any website")
    
    # Add option to start over
    if st.button("Extract Tables from Another Website", use_container_width=True):
        # Reset the app state
        for key in list(st.session_state.keys()):
            if key != "url_input":  # Keep the URL input to allow editing
                del st.session_state[key]
        st.rerun()

# If no data extracted yet, show a sample of what the app can do
elif not st.session_state.extraction_in_progress and not url:
    st.markdown("---")
    st.subheader("Example Tables")
    st.markdown("""
    Try extracting tables from these example websites:
    
    - Wikipedia articles (e.g., [List of MPs elected in 2005 (UK)](https://en.wikipedia.org/wiki/List_of_MPs_elected_in_the_2005_United_Kingdom_general_election))
    - Sports statistics (e.g., [ESPN](https://www.espn.com/soccer/standings/_/league/esp.1))
    - Amazon product comparisons (e.g., [Amazon iPhones comparison](https://www.amazon.com/Apple-iPhone-13-128GB-Green/dp/B0B5FDB92L/))
    
    Enter a URL above to get started.
    """)

# --- Handle Extraction in Progress ---
if st.session_state.extraction_in_progress:
    st.info("Table extraction in progress. Please wait...", icon="⏳")
    # Add a stop button
    if st.button("Cancel Extraction", use_container_width=True):
        st.session_state.extraction_in_progress = False
        st.rerun()

if __name__ == "__main__":
    # This will only run when the script is executed directly
    logger.info("Web Table Extractor started directly")
