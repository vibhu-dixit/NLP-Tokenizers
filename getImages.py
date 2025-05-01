import sys
import time
import re
import os
import pandas as pd
import uuid
import logging
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from PIL import Image

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('table_extractor.log')
    ]
)
logger = logging.getLogger('table_extractor')

def setup_driver():
    """
    Set up and configure Chrome WebDriver with optimal settings for web scraping
    
    Returns:
        webdriver: Configured Chrome WebDriver instance
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    
    # Set a user agent that looks like a regular browser
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    
    # Add performance preferences
    chrome_options.add_experimental_option('prefs', {
        'profile.default_content_setting_values.notifications': 2,
        'profile.managed_default_content_settings.images': 1,  # Load images
        'disk-cache-size': 4096,
        'intl.accept_languages': 'en-US,en',
    })
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(60)  # 60 second timeout for page loads
        driver.set_window_size(1920, 1080)
        logger.info("Chrome WebDriver initialized successfully")
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Chrome driver: {e}")
        raise

def wait_for_page_load(driver, timeout=30):
    """
    Wait for the page to completely load with robust checking
    
    Args:
        driver: Selenium WebDriver instance
        timeout: Maximum time to wait in seconds
    """
    try:
        # Wait for document ready state
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        
        # Wait for jQuery to load (if present)
        jquery_check = "return typeof jQuery !== 'undefined' && jQuery.active === 0"
        try:
            WebDriverWait(driver, 5).until(lambda d: d.execute_script(jquery_check))
        except:
            pass  # jQuery might not be present
        
        # Check if page has completely loaded by looking for body
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except:
            pass  # May already be loaded
        
        # Allow time for any animations or delayed content to finish loading
        time.sleep(2)
        
        logger.info("Page fully loaded")
    except Exception as e:
        logger.warning(f"Page load wait timed out: {e}")

def accept_cookies(driver, max_attempts=3):
    """
    Detect and accept common cookie consent banners and overlays
    
    Args:
        driver: Selenium WebDriver instance
        max_attempts: Maximum number of attempts to find and click consent buttons
    """
    logger.info("Checking for cookie consent banners...")
    # Common terms found in cookie acceptance buttons and their containing elements
    consent_button_patterns = [
        # Button text patterns (case insensitive)
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consent')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'got it')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'i agree')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ok')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'allow')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept all')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cookies')]",
        # Links or anchor tags
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consent')]",
        # Input buttons
        "//input[@type='button' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
        "//input[@type='button' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
        # Common IDs and classes
        "//*[contains(@id, 'cookie-accept') or contains(@id, 'accept-cookie') or contains(@id, 'cookieAccept') or contains(@id, 'cookie-banner')]",
        "//*[contains(@class, 'cookie-accept') or contains(@class, 'accept-cookie') or contains(@class, 'cookieAccept') or contains(@class, 'cookie-banner')]",
        # Common cookie banner close buttons
        "//*[contains(@class, 'cookie') and .//button[contains(@class, 'close')]]//button[contains(@class, 'close')]",
        "//*[contains(@id, 'cookie') and .//button[contains(@class, 'close')]]//button[contains(@class, 'close')]"
    ]
    
    # Try different patterns to find and click consent buttons
    for attempt in range(max_attempts):
        for xpath in consent_button_patterns:
            try:
                buttons = driver.find_elements(By.XPATH, xpath)
                for button in buttons:
                    if button.is_displayed():
                        button.click()
                        logger.info("Clicked consent button")
                        time.sleep(1)
                        return True
            except Exception:
                # Continue to next pattern if error occurs
                pass
        
        # Wait before trying again
        if attempt < max_attempts - 1:
            time.sleep(1)
    
    # Check for cookie banners in iframes
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes:
            try:
                # Check if iframe might contain cookie consent
                iframe_id = iframe.get_attribute("id") or ""
                iframe_name = iframe.get_attribute("name") or ""
                
                if any(term in iframe_id.lower() or term in iframe_name.lower() 
                       for term in ["cookie", "consent", "privacy", "gdpr"]):
                    driver.switch_to.frame(iframe)
                    
                    # Try to find consent buttons in the iframe
                    for xpath in consent_button_patterns:
                        try:
                            buttons = driver.find_elements(By.XPATH, xpath)
                            for button in buttons:
                                if button.is_displayed():
                                    button.click()
                                    driver.switch_to.default_content()
                                    logger.info("Clicked consent button in iframe")
                                    return True
                        except:
                            pass
                    
                    driver.switch_to.default_content()
            except:
                driver.switch_to.default_content()
    except:
        pass
    
    # Try generic dialog handling
    try:
        dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog'], .modal, .popup, .overlay")
        for dialog in dialogs:
            if dialog.is_displayed():
                # Try to click any button within this dialog
                try:
                    buttons = dialog.find_elements(By.TAG_NAME, "button")
                    for button in buttons:
                        # Look for "accept" type buttons first
                        button_text = button.text.lower()
                        if any(term in button_text for term in ["accept", "agree", "ok", "yes", "got it"]):
                            button.click()
                            logger.info("Clicked button in dialog")
                            time.sleep(1)
                            return True
                except:
                    pass
    except:
        pass
    
    logger.info("No cookie consent buttons found or handled")
    return False

def dismiss_banners_and_popups(driver):
    """
    Attempt to dismiss common banners, popups and overlays that might interfere with table extraction
    
    Args:
        driver: Selenium WebDriver instance
    """
    try:
        # List of common selectors for popups, modals, and banners
        popup_selectors = [
            "[class*='popup']", "[class*='modal']", "[class*='overlay']", 
            "[class*='banner']", "[id*='popup']", "[id*='modal']", 
            "[id*='overlay']", "[id*='banner']", "[role='dialog']",
            "[aria-modal='true']"
        ]
        
        # Try each selector
        for selector in popup_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        # Try to find close buttons within this element
                        close_buttons = element.find_elements(By.CSS_SELECTOR, 
                            "button.close, .close, .dismiss, .cancel, [class*='close'], [class*='dismiss'], [aria-label='Close']")
                        
                        for button in close_buttons:
                            if button.is_displayed():
                                try:
                                    button.click()
                                    logger.info(f"Dismissed a popup/banner using selector: {selector}")
                                    time.sleep(0.5)
                                    break
                                except:
                                    pass
            except:
                continue
        
        # If we have grid row/column info, organize by row
        if any(p['grid_row'] is not None for p in positions):
            # Group by grid row
            row_groups = {}
            for pos in positions:
                row = pos['grid_row'] if pos['grid_row'] is not None else 999
                if row not in row_groups:
                    row_groups[row] = []
                row_groups[row].append(pos)
            
            # Sort each row by column
            for row in row_groups:
                row_groups[row].sort(key=lambda p: p['grid_column'] if p['grid_column'] is not None else 999)
            
            # Convert to list of rows
            sorted_rows = [row_groups[row] for row in sorted(row_groups.keys())]
            return [
                [p['element'] for p in row]
                for row in sorted_rows
            ]
        
        # If we don't have grid info, try to organize visually
        # This is a simplified approach that assumes a typical left-to-right, top-to-bottom layout
        # For a more accurate approach, we'd need to inspect CSS and layout in the browser
        
        # Just convert flat list to rows based on a guess of columns
        # Determine likely number of columns
        if len(elements) >= 3:
            # Guess number of columns based on overall layout
            # This is just a heuristic; for real grid detection, we'd need browser rendering info
            if len(elements) % 2 == 0:
                cols = 2
            elif len(elements) % 3 == 0:
                cols = 3
            elif len(elements) % 4 == 0:
                cols = 4
            else:
                cols = 3  # Default guess
                
            # Group elements into rows
            result = []
            for i in range(0, len(elements), cols):
                row = elements[i:i+cols]
                if row:  # Skip empty rows
                    result.append(row)
            return result
                
        # Fallback: return original flat list
        return [elements]
    except Exception as e:
        logger.warning(f"Error organizing grid elements: {e}")
        return [elements]  # Return as single row

def extract_list_table_data(soup):
    """
    Extract data from a list-based table (ul/li structure)
    
    Args:
        soup: BeautifulSoup object of the list HTML
    
    Returns:
        tuple: (headers, rows) where headers is a list of column names and rows is a list of data rows
    """
    headers = []
    rows = []
    
    # Find the list element
    ul = soup.find('ul')
    if not ul:
        return headers, rows
    
    # Check for a header before the list
    prev = ul.find_previous_sibling(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'p'])
    if prev and (prev.name.startswith('h') or 'header' in prev.get('class', [])):
        # Try to extract headers from the previous element
        if prev.find_all(['span', 'strong', 'b']):
            # If it has multiple emphasized elements, use those as headers
            headers = [clean_text(el.get_text(strip=True)) for el in prev.find_all(['span', 'strong', 'b'])]
        else:
            # Otherwise try to split the text into header parts
            text = prev.get_text(strip=True)
            parts = re.split(r'[|,;:]', text)
            if len(parts) > 1:
                headers = [clean_text(p) for p in parts]
    
    # Get all list items
    items = ul.find_all('li')
    
    # Check if first list item might be a header
    if items and not headers:
        first_item = items[0]
        
        # Check if it has different styling or structure
        if (first_item.get('class') and 'header' in ' '.join(first_item.get('class'))) or \
           first_item.find(['strong', 'b', 'em', 'i']) or \
           first_item.name in ['th', 'header']:
            
            # Extract header cells
            if first_item.find_all(['span', 'strong', 'b']):
                headers = [clean_text(el.get_text(strip=True)) for el in first_item.find_all(['span', 'strong', 'b'])]
            else:
                # Try to split text into header columns
                text = first_item.get_text(strip=True)
                parts = re.split(r'[|,;:]', text)
                if len(parts) > 1:
                    headers = [clean_text(p) for p in parts]
                else:
                    headers = [clean_text(text)]
            
            # Skip first item in processing
            items = items[1:]
    
    # Process each list item
    for item in items:
        row = []
        
        # Check if item has child elements we can use as cells
        cells = item.find_all(['span', 'div', 'a'])
        
        if cells and len(cells) > 1:
            # Item has multiple child elements - use these as cells
            for cell in cells:
                # Check for images
                img = cell.find('img')
                if img:
                    img_src = img.get('src', '')
                    img_alt = img.get('alt', '')
                    
                    # Fix URLs that start with //
                    if img_src.startswith('//'):
                        img_src = f"https:{img_src}"
                        
                    if img_src:
                        img_html = f'<img src="{img_src}" alt="{img_alt}" style="max-width:100px; max-height:100px;">'
                        row.append(img_html)
                    else:
                        row.append(clean_text(cell.get_text(strip=True)))
                else:
                    row.append(clean_text(cell.get_text(strip=True)))
        else:
            # Try to split item text into cells
            text = item.get_text(strip=True)
            parts = re.split(r'[|,;:]', text)
            
            if len(parts) > 1:
                # Item text can be split into multiple cells
                row = [clean_text(p) for p in parts]
            else:
                # Single cell item
                row = [clean_text(text)]
                
            # Check for images
            img = item.find('img')
            if img:
                img_src = img.get('src', '')
                img_alt = img.get('alt', '')
                
                # Fix URLs that start with //
                if img_src.startswith('//'):
                    img_src = f"https:{img_src}"
                    
                if img_src:
                    img_html = f'<img src="{img_src}" alt="{img_alt}" style="max-width:100px; max-height:100px;">'
                    if len(row) > 0:
                        row[0] = img_html
                    else:
                        row = [img_html]
        
        # Only add non-empty rows
        if row and any(str(cell).strip() for cell in row):
            rows.append(row)
    
    return headers, rows

def extract_row_container_data(soup):
    """
    Extract data from a generic container with row-like elements
    
    Args:
        soup: BeautifulSoup object of the container HTML
    
    Returns:
        tuple: (headers, rows) where headers is a list of column names and rows is a list of data rows
    """
    headers = []
    rows = []
    
    # Try to find rows
    row_selectors = [
        'li', 'tr', 'div.row', '[role="row"]', 
        '[class*="row"]', '[class*="item"]', '.item'
    ]
    
    row_elements = []
    for selector in row_selectors:
        elements = soup.select(selector)
        if len(elements) > 2:  # Need multiple rows
            row_elements = elements
            break
    
    if not row_elements:
        # Try to find direct children of the main container
        container = soup.find()  # First element
        row_elements = [child for child in container.children if child.name]
    
    if not row_elements:
        return headers, rows
    
    # Check if first element might be header
    first_row = row_elements[0]
    
    # Check if it looks like a header
    is_header = (
        first_row.find('th') or
        'header' in (first_row.get('class', []) or []) or
        first_row.select_one('[class*="header"], [class*="heading"]') or
        first_row.name in ['th', 'thead']
    )
    
    if is_header:
        # Extract header cells
        cell_elements = first_row.find_all(['th', 'td', 'div', 'span'])
        if not cell_elements:
            cell_elements = [child for child in first_row.children if child.name]
            
        headers = [clean_text(cell.get_text(strip=True)) for cell in cell_elements]
        
        # Process remaining rows
        for row_el in row_elements[1:]:
            row = []
            
            # Find cells in this row
            cell_elements = row_el.find_all(['td', 'div', 'span'])
            if not cell_elements:
                cell_elements = [child for child in row_el.children if child.name]
                
            for cell in cell_elements:
                # Check for images
                img = cell.find('img')
                if img:
                    img_src = img.get('src', '')
                    img_alt = img.get('alt', '')
                    
                    # Fix URLs that start with //
                    if img_src.startswith('//'):
                        img_src = f"https:{img_src}"
                        
                    if img_src:
                        img_html = f'<img src="{img_src}" alt="{img_alt}" style="max-width:100px; max-height:100px;">'
                        row.append(img_html)
                    else:
                        row.append(clean_text(cell.get_text(strip=True)))
                else:
                    row.append(clean_text(cell.get_text(strip=True)))
            
            # Only add non-empty rows
            if row and any(str(cell).strip() for cell in row):
                rows.append(row)
    else:
        # No clear header, treat all rows as data
        for row_el in row_elements:
            row = []
            
            # Find cells in this row
            cell_elements = row_el.find_all(['td', 'div', 'span'])
            if not cell_elements:
                cell_elements = [child for child in row_el.children if child.name]
                
            for cell in cell_elements:
                # Check for images
                img = cell.find('img')
                if img:
                    img_src = img.get('src', '')
                    img_alt = img.get('alt', '')
                    
                    # Fix URLs that start with //
                    if img_src.startswith('//'):
                        img_src = f"https:{img_src}"
                        
                    if img_src:
                        img_html = f'<img src="{img_src}" alt="{img_alt}" style="max-width:100px; max-height:100px;">'
                        row.append(img_html)
                    else:
                        row.append(clean_text(cell.get_text(strip=True)))
                else:
                    row.append(clean_text(cell.get_text(strip=True)))
            
            # Only add non-empty rows
            if row and any(str(cell).strip() for cell in row):
                rows.append(row)
    
    return headers, rows

def clean_text(text):
    """
    Clean and normalize text from HTML
    
    Args:
        text: Text to clean
    
    Returns:
        str: Cleaned text
    """
    if not text:
        return ""
        
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Replace common HTML entities
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    
    # Trim
    return text.strip()

def check_for_images(soup, df):
    """
    Check if the table contains images
    
    Args:
        soup: BeautifulSoup object
        df: DataFrame of the table data
    
    Returns:
        bool: True if images are found
    """
    # Check if the HTML contains any img tags
    images = soup.find_all('img')
    if images:
        return True
    
    # Check if any cell in the DataFrame contains an image tag
    for column in df.columns:
        for value in df[column]:
            if isinstance(value, str) and '<img src=' in value:
                return True
    
    return False

def download_image(img_url, base_domain, safe_title, index, base_dir="extracted_images"):
    """
    Download an image from a URL and save it to a local file
    
    Args:
        img_url: URL of the image
        base_domain: Domain of the source page for context
        safe_title: Safe version of the table title for filename
        index: Index for uniqueness
        base_dir: Directory to save images
    
    Returns:
        tuple: (success, local_path or error_message)
    """
    try:
        # Create image directory if needed
        os.makedirs(base_dir, exist_ok=True)
        
        # Fix URLs that start with //
        if img_url.startswith('//'):
            img_url = f"https:{img_url}"
        
        # Generate unique image filename
        img_extension = os.path.splitext(img_url.split('?')[0])[1] or '.jpg'
        if img_extension.lower() not in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.avif']:
            img_extension = '.jpg'  # Default extension
        
        img_filename = f"{base_dir}/{base_domain}_{safe_title}_{index}{img_extension}"
        
        # Download the image with a timeout
        response = requests.get(img_url, stream=True, timeout=10)
        if response.status_code == 200:
            with open(img_filename, 'wb') as img_file:
                img_file.write(response.content)
            return True, img_filename
        else:
            return False, f"Error: HTTP status {response.status_code}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

def process_table_images(table_data, url, base_dir="extracted_images"):
    """
    Process and download all images in a table
    
    Args:
        table_data: Table data dictionary
        url: Source URL of the webpage
        base_dir: Directory to save downloaded images
    
    Returns:
        Updated table data with local image paths
    """
    if not table_data.get('has_images', False) or 'dataframe' not in table_data:
        return table_data
    
    # Create image directory if needed
    os.makedirs(base_dir, exist_ok=True)
    
    # Get base URL for resolving relative paths
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    base_domain = parsed_url.netloc.replace("www.", "").split('.')[0]
    
    # Create safe filename prefix
    safe_title = re.sub(r'[^\w\s-]', '', table_data['title']).strip().replace(' ', '_')
    safe_title = re.sub(r'[-_]+', '_', safe_title)[:30]  # Limit length
    
    # Create copy of the DataFrame
    df = table_data['dataframe'].copy()
    processed = False
    
    # Process each cell
    img_index = 1
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Create a list to store futures
        futures = []
        cell_locations = []
        
        # First pass: collect all image URLs to download
        for i, row in df.iterrows():
            for col in df.columns:
                cell_val = str(row[col])
                if '<img src=' in cell_val:
                    # Extract image URL
                    img_url_match = re.search(r'src="([^"]+)"', cell_val)
                    if img_url_match:
                        img_url = img_url_match.group(1)
                        
                        # Handle relative URLs and protocol-relative URLs
                        if img_url.startswith('//'):
                            img_url = f"https:{img_url}"
                        elif img_url.startswith('/'):
                            img_url = f"{base_url}{img_url}"
                        elif not img_url.startswith(('http://', 'https://')):
                            img_url = urljoin(base_url, img_url)
                        
                        # Submit download task
                        future = executor.submit(
                            download_image, 
                            img_url, 
                            base_domain, 
                            safe_title, 
                            img_index,
                            base_dir
                        )
                        futures.append(future)
                        cell_locations.append((i, col, img_url))
                        img_index += 1
        
        # Process results as they complete
        for future, (i, col, img_url) in zip(futures, cell_locations):
            success, result = future.result()
            if success:
                # Update cell with local image path
                df.at[i, col] = f"Image: {result}"
                processed = True
            else:
                # Update cell with error message
                df.at[i, col] = f"Image URL: {img_url} (download failed: {result})"
                processed = True
    
    # Update table data with processed DataFrame if changes were made
    if processed:
        table_data['dataframe_with_local_images'] = df
    
    return table_data

def screenshot_tables(url):
    """
    Find and extract all tables from a webpage with screenshots
    
    Args:
        url (str): URL of the webpage to analyze
    
    Returns:
        list: List of dictionaries containing table data
    """
    # Set up Chrome driver
    try:
        driver = setup_driver()
    except Exception as e:
        logger.error(f"Failed to initialize Chrome driver: {e}")
        return []
    
    # Track results
    tables_info = []
    
    try:
        # Load the webpage
        logger.info(f"Loading webpage: {url}")
        driver.get(url)
        
        # Check if we loaded the correct page
        actual_url = driver.current_url
        parsed_original = urlparse(url)
        parsed_actual = urlparse(actual_url)
        
        if parsed_original.netloc != parsed_actual.netloc:
            logger.warning(f"Redirected to {actual_url}")
        
        # Wait for page to fully load
        wait_for_page_load(driver)
        
        # Handle any cookie consent popups
        accept_cookies(driver)
        
        # Dismiss any other banners or popups
        dismiss_banners_and_popups(driver)
        
        # Create a safe domain name for filenames
        domain_name = re.sub(r'^https?://(www\.)?', '', actual_url).split('/')[0]
        safe_domain = re.sub(r'[^\w\s-]', '', domain_name).strip().replace('.', '_')
        
        # Ensure screenshots directory exists
        screenshots_dir = 'screenshots'
        os.makedirs(screenshots_dir, exist_ok=True)
        
        # Take full page screenshot for reference
        full_page_file = f"{screenshots_dir}/{safe_domain}_full_page.png"
        capture_full_page_screenshot(driver, full_page_file)
        
        # Find all potential table containers
        containers = get_all_tables(driver)
        
        # Process each potential table container
        for idx, container in enumerate(containers):
            try:
                # Get element and check if it's still valid and visible
                element = container['element']
                
                try:
                    element_still_valid = driver.execute_script("return arguments[0].isConnected", element)
                    if not element_still_valid:
                        logger.warning(f"Element for container {idx+1} is no longer connected to the DOM, skipping")
                        continue
                except:
                    logger.warning(f"Could not check if element {idx+1} is still valid, skipping")
                    continue
                
                # Scroll element into view
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.5)
                
                if not element.is_displayed():
                    logger.warning(f"Skipping container {idx+1} because it's not displayed")
                    continue
                
                # Create a clean title for this table
                table_title = get_table_title(driver, element)
                if not table_title:
                    table_title = f"Table {idx+1}"
                
                safe_title = re.sub(r'[^\w\s-]', '', table_title).strip().replace(' ', '_')
                safe_title = re.sub(r'[-_]+', '_', safe_title)[:30]  # Limit length
                
                # Take a screenshot of this container
                screenshot_file = f"{screenshots_dir}/{safe_domain}_{safe_title}_{idx+1}.png"
                if capture_element_screenshot(driver, element, screenshot_file):
                    # Extract data from the container
                    table_data = extract_table_data(driver, container)
                    
                    if table_data:
                        # Add source URL and screenshot info
                        table_data['source_url'] = actual_url
                        table_data['screenshot'] = screenshot_file
                        
                        # Check for real data (more than just headers)
                        if 'dataframe' in table_data and len(table_data['dataframe']) > 0:
                            # Filter out tables that don't have much data
                            df = table_data['dataframe']
                            
                            # Skip tables that are too small and might be navigation or metadata
                            if (len(df) <= 1 and len(df.columns) <= 1) or \
                               (len(df) <= 2 and len(df.columns) <= 2 and container['confidence'] == 'low'):
                                logger.info(f"Skipping table {idx+1} because it's too small")
                                continue
                                
                            # Process images if present
                            if table_data.get('has_images', False):
                                table_data = process_table_images(table_data, actual_url)
                            
                            tables_info.append(table_data)
                            logger.info(f"Successfully extracted table {idx+1}: {table_data['title']}")
                        else:
                            logger.warning(f"Skipping table {idx+1} because it has no data")
                    else:
                        logger.warning(f"Failed to extract data from container {idx+1}")
            
            except Exception as e:
                logger.error(f"Error processing container {idx+1}: {e}")
                continue
        
        logger.info(f"Total tables extracted: {len(tables_info)}")
        
        # If no tables were extracted, use the full page screenshot for reference
        if not tables_info:
            logger.warning("No tables were successfully extracted. Returning full page screenshot.")
            tables_info.append({
                'title': f"Full page - {domain_name}",
                'screenshot': full_page_file,
                'source_url': actual_url,
                'dataframe': None,
                'full_page': True
            })
        
        return tables_info
    
    except Exception as e:
        logger.error(f"Error during table extraction: {e}")
        traceback.print_exc()
        
        # Create error screenshot
        try:
            os.makedirs('screenshots', exist_ok=True)
            error_file = f"screenshots/error_{safe_domain}.png"
            driver.save_screenshot(error_file)
            logger.info(f"Error screenshot saved: {error_file}")
            
            # Return error info
            return [{
                'title': f"Error - {domain_name}",
                'screenshot': error_file,
                'source_url': url,
                'dataframe': None,
                'error': str(e),
                'full_page': True
            }]
        except:
            return []
    
    finally:
        # Always close the browser
        try:
            driver.quit()
            logger.info("WebDriver closed successfully")
        except:
            logger.warning("Error closing WebDriver")

# For testing purposes
if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://en.wikipedia.org/wiki/Chemical_element"
        
    print(f"Extracting tables from {url}")
    tables = screenshot_tables(url)
    print(f"Extracted {len(tables)} tables")
    
    # Print information about extracted tables
    for i, table in enumerate(tables):
        print(f"\nTable {i+1}: {table['title']}")
        if 'dataframe' in table and table['dataframe'] is not None:
            print(f"Columns: {list(table['dataframe'].columns)}")
            print(f"Rows: {len(table['dataframe'])}")
        if 'screenshot' in table:
            print(f"Screenshot: {table['screenshot']}")
        if table.get('has_images', False):
            print("Table contains images")
            if 'dataframe_with_local_images' in table:
                print("Images processed with local paths")
                
        # Look for and click any "x" or close buttons visible on the page
        close_xpath = "//*[text()='×' or text()='✕' or text()='✖']"
        try:
            close_elements = driver.find_elements(By.XPATH, close_xpath)
            for close_element in close_elements:
                if close_element.is_displayed():
                    close_element.click()
                    logger.info("Clicked an X close button")
                    time.sleep(0.5)
        except:
            pass

def capture_full_page_screenshot(driver, filename):
    """
    Capture a screenshot of the entire page
    
    Args:
        driver: Selenium WebDriver instance
        filename: File path to save the screenshot
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Scroll to top first
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
        
        # Take screenshot
        driver.save_screenshot(filename)
        logger.info(f"Full page screenshot saved: {filename}")
        return True
    except Exception as e:
        logger.error(f"Error capturing full page screenshot: {e}")
        return False

def capture_element_screenshot(driver, element, filename):
    """
    Capture a screenshot of a specific element with improved handling for full visibility
    
    Args:
        driver: Selenium WebDriver instance
        element: WebElement to screenshot
        filename: File path to save the screenshot
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
        
        # Ensure the element is in the viewport
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", element)
        time.sleep(0.5)
        
        # Try to ensure the whole element is visible
        driver.execute_script("""
            // Make element fully visible
            arguments[0].style.overflow = 'visible';
            
            // Fix parent containers with overflow issues
            let parent = arguments[0].parentElement;
            for (let i = 0; i < 5 && parent; i++) {
                if (window.getComputedStyle(parent).overflow === 'hidden' ||
                    window.getComputedStyle(parent).overflowX === 'hidden' ||
                    window.getComputedStyle(parent).overflowY === 'hidden') {
                    parent.style.overflow = 'visible';
                    parent.style.overflowX = 'visible';
                    parent.style.overflowY = 'visible';
                }
                parent = parent.parentElement;
            }
            
            // Handle fixed-width containers
            arguments[0].style.maxWidth = 'none';
            arguments[0].style.width = 'auto';
        """, element)
        
        time.sleep(0.5)
        
        # Get element dimensions and position
        location = element.location
        size = element.size
        
        # Sometimes we need to add a bit of margin to ensure we capture everything
        margin = 10
        
        # Take the full page screenshot
        driver.save_screenshot(filename + ".temp.png")
        
        # Crop the screenshot to just the element
        try:
            full_img = Image.open(filename + ".temp.png")
            left = location['x'] - margin
            top = location['y'] - margin
            right = location['x'] + size['width'] + margin
            bottom = location['y'] + size['height'] + margin
            
            # Ensure we don't go out of bounds
            left = max(0, left)
            top = max(0, top)
            right = min(full_img.width, right)
            bottom = min(full_img.height, bottom)
            
            element_img = full_img.crop((left, top, right, bottom))
            element_img.save(filename)
            
            # Remove temp file
            os.remove(filename + ".temp.png")
            
            logger.info(f"Element screenshot saved: {filename}")
            return True
        except Exception as crop_error:
            logger.error(f"Error cropping screenshot: {crop_error}")
            # Fallback: use the element's screenshot method directly
            element.screenshot(filename)
            logger.info(f"Fallback screenshot saved: {filename}")
            return True
        
    except Exception as e:
        logger.error(f"Error capturing element screenshot: {e}")
        try:
            # Last resort: try to just use Selenium's built-in screenshot
            element.screenshot(filename)
            logger.info(f"Last resort screenshot saved: {filename}")
            return True
        except:
            return False

def get_all_tables(driver):
    """
    Find all tables and table-like structures on a webpage with high accuracy
    
    Args:
        driver: Selenium WebDriver instance
    
    Returns:
        list: List of dictionaries containing information about each table container
    """
    all_containers = []
    processed_elements = set()  # To avoid duplicates
    
    # Capture all actual HTML tables first (highest confidence)
    logger.info("Looking for HTML tables...")
    try:
        tables = driver.find_elements(By.TAG_NAME, "table")
        logger.info(f"Found {len(tables)} HTML tables")
        
        for table in tables:
            try:
                if not table.is_displayed():
                    continue
                
                # Skip already processed elements
                table_id = driver.execute_script("return arguments[0].outerHTML.length", table)
                if table_id in processed_elements:
                    continue
                
                processed_elements.add(table_id)
                
                # Verify it's a data table and not a layout table
                # Check if it has multiple rows or appropriate structure
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) < 2:  # Need at least two rows to be considered a data table
                    continue
                
                # Check if table has reasonable size
                size = table.size
                if size['width'] < 50 or size['height'] < 30:  # Too small to be a data table
                    continue
                    
                # Check if it has headers or cells
                if not table.find_elements(By.TAG_NAME, "th") and not table.find_elements(By.TAG_NAME, "td"):
                    continue
                
                # Get position to help with duplicates
                position = f"{table.location['x']}-{table.location['y']}"
                
                all_containers.append({
                    'element': table,
                    'type': 'html_table',
                    'tag': 'table',
                    'position': position,
                    'confidence': 'high',
                    'has_rows': len(rows)
                })
            except Exception as e:
                logger.warning(f"Error evaluating table: {e}")
                continue
    except Exception as e:
        logger.error(f"Error finding HTML tables: {e}")
    
    # Find table containers with ARIA roles
    logger.info("Looking for ARIA tables...")
    try:
        aria_tables = driver.find_elements(By.CSS_SELECTOR, "[role='table'], [role='grid']")
        for table in aria_tables:
            try:
                if not table.is_displayed():
                    continue
                
                # Skip already processed elements
                table_id = driver.execute_script("return arguments[0].outerHTML.length", table)
                if table_id in processed_elements:
                    continue
                    
                processed_elements.add(table_id)
                
                # Check for rows
                rows = table.find_elements(By.CSS_SELECTOR, "[role='row']")
                if len(rows) < 2:  # Need at least two rows to be considered a data table
                    continue
                
                # Get position
                position = f"{table.location['x']}-{table.location['y']}"
                
                all_containers.append({
                    'element': table,
                    'type': 'aria_table',
                    'tag': table.tag_name,
                    'position': position,
                    'confidence': 'high',
                    'has_rows': len(rows)
                })
            except Exception as e:
                logger.warning(f"Error evaluating ARIA table: {e}")
                continue
    except Exception as e:
        logger.error(f"Error finding ARIA tables: {e}")
    
    # Find div-based tables by common class names
    logger.info("Looking for div-based tables...")
    try:
        table_selectors = [
            ".table", ".datatable", ".data-table", ".grid-table", 
            ".table-responsive", ".table-container", ".tableWrapper",
            "[class*='table-']", "[class*='Table']", "[class*='grid']",
            ".data-grid", ".datagrid", "[class*='data-grid']", "[class*='datagrid']"
        ]
        
        for selector in table_selectors:
            try:
                div_tables = driver.find_elements(By.CSS_SELECTOR, selector)
                for table in div_tables:
                    try:
                        if not table.is_displayed():
                            continue
                        
                        # Skip already processed elements
                        table_id = driver.execute_script("return arguments[0].outerHTML.length", table)
                        if table_id in processed_elements:
                            continue
                            
                        processed_elements.add(table_id)
                        
                        # Skip if this element contains a table we've already found
                        if has_child_in_containers(driver, table, all_containers):
                            continue
                        
                        # Check if it has children that look like rows
                        # Check for various types of child elements that could be rows
                        rows = (
                            table.find_elements(By.CSS_SELECTOR, ".row, [class*='row']") or
                            table.find_elements(By.CSS_SELECTOR, "li") or 
                            table.find_elements(By.CSS_SELECTOR, "div")
                        )
                        
                        if len(rows) < 2:  # Need at least two rows to be considered a data table
                            continue
                            
                        # Check if rows have similar structure
                        if not rows_have_similar_structure(rows):
                            continue
                        
                        # Get position
                        position = f"{table.location['x']}-{table.location['y']}"
                        
                        all_containers.append({
                            'element': table,
                            'type': 'div_table',
                            'tag': table.tag_name,
                            'position': position,
                            'class': table.get_attribute('class'),
                            'confidence': 'medium',
                            'has_rows': len(rows)
                        })
                    except Exception as e:
                        logger.warning(f"Error evaluating div table: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Error searching for div tables with {selector}: {e}")
                continue
    except Exception as e:
        logger.error(f"Error finding div-based tables: {e}")
    
    # Find containers with CSS Grid layout
    logger.info("Looking for CSS Grid containers...")
    try:
        grid_selectors = [
            "[style*='display: grid']", 
            "[style*='display:grid']"
        ]
        
        for selector in grid_selectors:
            try:
                grid_containers = driver.find_elements(By.CSS_SELECTOR, selector)
                for grid in grid_containers:
                    try:
                        if not grid.is_displayed():
                            continue
                        
                        # Skip already processed elements
                        grid_id = driver.execute_script("return arguments[0].outerHTML.length", grid)
                        if grid_id in processed_elements:
                            continue
                            
                        processed_elements.add(grid_id)
                        
                        # Skip if this element contains a table we've already found
                        if has_child_in_containers(driver, grid, all_containers):
                            continue
                            
                        # Check if it has enough child elements to be a table
                        children = grid.find_elements(By.XPATH, "./*")
                        if len(children) < 4:  # Need at least a handful of cells to be a table
                            continue
                        
                        # Detect rows programmatically
                        computed_rows = detect_grid_rows(driver, grid)
                        if computed_rows < 2:  # Need at least two rows to be a table
                            continue
                        
                        # Get position
                        position = f"{grid.location['x']}-{grid.location['y']}"
                        
                        all_containers.append({
                            'element': grid,
                            'type': 'grid',
                            'tag': grid.tag_name,
                            'position': position,
                            'class': grid.get_attribute('class'),
                            'confidence': 'medium',
                            'has_rows': computed_rows
                        })
                    except Exception as e:
                        logger.warning(f"Error evaluating grid container: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Error searching for grid containers with {selector}: {e}")
                continue
    except Exception as e:
        logger.error(f"Error finding grid containers: {e}")
    
    # Process any layouts that look like tables with <ul> and <li> elements
    logger.info("Looking for list-based tables...")
    try:
        list_containers = driver.find_elements(By.TAG_NAME, "ul")
        for list_element in list_containers:
            try:
                if not list_element.is_displayed():
                    continue
                
                # Skip already processed elements
                list_id = driver.execute_script("return arguments[0].outerHTML.length", list_element)
                if list_id in processed_elements:
                    continue
                    
                processed_elements.add(list_id)
                
                # Check for list items
                items = list_element.find_elements(By.TAG_NAME, "li")
                if len(items) < 3:  # Need several list items
                    continue
                
                # Check if list items have similar structure (potential table rows)
                if not rows_have_similar_structure(items):
                    continue
                    
                # Check if list items contain multiple elements (potential cells)
                child_counts = [len(item.find_elements(By.XPATH, "./*")) for item in items[:5]]
                if max(child_counts) < 2:  # Need at least 2 elements per row
                    continue
                
                # Get position
                position = f"{list_element.location['x']}-{list_element.location['y']}"
                
                all_containers.append({
                    'element': list_element,
                    'type': 'list_table',
                    'tag': 'ul',
                    'position': position,
                    'confidence': 'medium',
                    'has_rows': len(items)
                })
            except Exception as e:
                logger.warning(f"Error evaluating list container: {e}")
                continue
    except Exception as e:
        logger.error(f"Error finding list-based tables: {e}")
    
    # Last resort: find elements with children that look like table rows
    if len(all_containers) == 0:
        logger.info("Looking for any elements with table-like structure...")
        try:
            potential_containers = driver.find_elements(By.CSS_SELECTOR, "div, section, article")
            for container in potential_containers:
                try:
                    if not container.is_displayed():
                        continue
                    
                    # Skip already processed elements
                    container_id = driver.execute_script("return arguments[0].outerHTML.length", container)
                    if container_id in processed_elements:
                        continue
                        
                    processed_elements.add(container_id)
                    
                    # Check if this element is small
                    size = container.size
                    if size['width'] < 100 or size['height'] < 50:  # Too small to be a table
                        continue
                    
                    # Check for elements that look like rows
                    for row_selector in [".//div[contains(@class, 'row')]", ".//li", ".//tr"]:
                        rows = container.find_elements(By.XPATH, row_selector)
                        if len(rows) >= 3:  # Need several rows to be a table
                            # Check if rows have similar structure
                            if rows_have_similar_structure(rows):
                                # Get position
                                position = f"{container.location['x']}-{container.location['y']}"
                                
                                all_containers.append({
                                    'element': container,
                                    'type': 'structured_container',
                                    'tag': container.tag_name,
                                    'position': position,
                                    'class': container.get_attribute('class'),
                                    'confidence': 'low',
                                    'has_rows': len(rows)
                                })
                                break
                except Exception as e:
                    logger.warning(f"Error evaluating potential container: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error finding structured containers: {e}")
    
    # Remove duplicate tables that are too close to each other
    logger.info(f"Found {len(all_containers)} potential table containers before deduplication")
    deduplicated_containers = deduplicate_tables(driver, all_containers)
    logger.info(f"Deduplicated to {len(deduplicated_containers)} table containers")
    
    # Sort by confidence level and position
    sorted_containers = sorted(
        deduplicated_containers, 
        key=lambda x: (
            {'high': 0, 'medium': 1, 'low': 2}[x.get('confidence', 'low')],
            x.get('position', '')
        )
    )
    
    return sorted_containers

def has_child_in_containers(driver, element, containers):
    """
    Check if an element is a parent of any element in the containers list
    
    Args:
        driver: Selenium WebDriver instance
        element: Potential parent element
        containers: List of container dictionaries
    
    Returns:
        bool: True if element is a parent of any container element
    """
    try:
        for container in containers:
            child_element = container['element']
            # Use JavaScript to check parent-child relationship
            is_parent = driver.execute_script("""
                function isAncestor(parent, child) {
                    let node = child;
                    while (node != null) {
                        if (node == parent) {
                            return true;
                        }
                        node = node.parentNode;
                    }
                    return false;
                }
                return isAncestor(arguments[0], arguments[1]);
            """, element, child_element)
            if is_parent:
                return True
        return False
    except Exception as e:
        logger.warning(f"Error checking parent-child relationship: {e}")
        return False

def rows_have_similar_structure(rows):
    """
    Check if a set of rows have similar structure to qualify as table rows
    
    Args:
        rows: List of WebElements representing potential table rows
    
    Returns:
        bool: True if rows have similar structure
    """
    try:
        # Check only first few rows to save time
        sample_rows = rows[:5] if len(rows) > 5 else rows
        
        # Get child count for each row
        child_counts = []
        for row in sample_rows:
            # Get all child elements
            children = row.find_elements(By.XPATH, "./*")
            child_counts.append(len(children))
        
        # Check if child counts are similar (possibly the same or ±1)
        if not child_counts:
            return False
            
        # If all rows have 0 or 1 children, this isn't table-like
        if max(child_counts) <= 1:
            return False
            
        # Calculate how consistent the child counts are
        unique_counts = set(child_counts)
        
        # If all or most rows have same number of children, likely a table
        if len(unique_counts) <= 2:
            return True
            
        # Or if predominant number of children is consistent (allows for header row difference)
        from collections import Counter
        count_frequency = Counter(child_counts)
        most_common = count_frequency.most_common(1)[0][1]
        if most_common >= len(child_counts) * 0.6:  # More than 60% have same count
            return True
            
        return False
    except Exception as e:
        logger.warning(f"Error checking row structure: {e}")
        return False

def detect_grid_rows(driver, grid_element):
    """
    Detect how many logical rows exist in a CSS grid container
    
    Args:
        driver: Selenium WebDriver instance
        grid_element: WebElement for a grid container
    
    Returns:
        int: Estimated number of rows in the grid
    """
    try:
        # Get grid-template-rows or grid-template-columns from style
        result = driver.execute_script("""
            const gridEl = arguments[0];
            const style = window.getComputedStyle(gridEl);
            const gridRows = style.getPropertyValue('grid-template-rows');
            const gridCols = style.getPropertyValue('grid-template-columns');
            const childCount = gridEl.children.length;
            
            // If grid-template-rows is set, count the number of row definitions
            if (gridRows && gridRows !== 'none') {
                return gridRows.trim().split(/\\s+/).length;
            }
            
            // If grid-template-columns is set, estimate rows based on column count
            if (gridCols && gridCols !== 'none') {
                const colCount = gridCols.trim().split(/\\s+/).length;
                if (colCount > 0) {
                    return Math.ceil(childCount / colCount);
                }
            }
            
            // Fallback: Try to detect rows visually by y-position
            const positions = [];
            Array.from(gridEl.children).forEach(child => {
                const rect = child.getBoundingClientRect();
                positions.push(Math.round(rect.top));
            });
            
            // Count unique y-positions (allowing for small variations)
            const uniquePositions = new Set();
            positions.forEach(pos => {
                let found = false;
                for (const existing of uniquePositions) {
                    if (Math.abs(existing - pos) < 5) {
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    uniquePositions.add(pos);
                }
            });
            
            return uniquePositions.size;
        """, grid_element)
        
        return int(result) if result else 0
    except Exception as e:
        logger.warning(f"Error detecting grid rows: {e}")
        return 0

def deduplicate_tables(driver, containers):
    """
    Remove duplicate table containers that represent the same logical table
    
    Args:
        driver: Selenium WebDriver instance
        containers: List of container dictionaries
    
    Returns:
        list: Deduplicated list of container dictionaries
    """
    if not containers:
        return []
        
    result = []
    skip_indices = set()
    
    for i, container1 in enumerate(containers):
        if i in skip_indices:
            continue
            
        # Add this container to results
        result.append(container1)
        
        # Check for duplicates
        for j, container2 in enumerate(containers):
            if i == j or j in skip_indices:
                continue
                
            try:
                # Check if containers are the same or overlapping significantly
                element1 = container1['element']
                element2 = container2['element']
                
                # Skip if types are very different (e.g., don't compare html_table with list_table)
                if container1['type'] == 'html_table' and container2['type'] != 'html_table':
                    continue
                
                # Check if elements are the same or close to each other
                are_same = driver.execute_script("""
                    const el1 = arguments[0];
                    const el2 = arguments[1];
                    
                    // Check if they're the same element
                    if (el1 === el2) {
                        return true;
                    }
                    
                    // Check if one is a child of the other
                    let node = el2;
                    while (node) {
                        if (node === el1) {
                            return true;
                        }
                        node = node.parentNode;
                    }
                    
                    node = el1;
                    while (node) {
                        if (node === el2) {
                            return true;
                        }
                        node = node.parentNode;
                    }
                    
                    // Check if they overlap significantly
                    const rect1 = el1.getBoundingClientRect();
                    const rect2 = el2.getBoundingClientRect();
                    
                    // Calculate overlap area
                    const xOverlap = Math.max(0, Math.min(rect1.right, rect2.right) - Math.max(rect1.left, rect2.left));
                    const yOverlap = Math.max(0, Math.min(rect1.bottom, rect2.bottom) - Math.max(rect1.top, rect2.top));
                    const overlapArea = xOverlap * yOverlap;
                    
                    // Calculate smaller area
                    const area1 = rect1.width * rect1.height;
                    const area2 = rect2.width * rect2.height;
                    const smallerArea = Math.min(area1, area2);
                    
                    // If overlap is significant (>70% of the smaller element)
                    return overlapArea > 0.7 * smallerArea;
                """, element1, element2)
                
                if are_same:
                    # Keep the one with higher confidence or more rows
                    confidence_ranks = {'high': 0, 'medium': 1, 'low': 2}
                    container1_rank = confidence_ranks.get(container1.get('confidence', 'low'), 2)
                    container2_rank = confidence_ranks.get(container2.get('confidence', 'low'), 2)
                    
                    if (container2_rank < container1_rank or 
                        (container2_rank == container1_rank and 
                         container2.get('has_rows', 0) > container1.get('has_rows', 0))):
                        # container2 is better, replace container1 with it
                        result[-1] = container2
                    
                    # Mark the duplicate for skipping
                    skip_indices.add(j)
            except Exception as e:
                logger.warning(f"Error comparing containers {i} and {j}: {e}")
                continue
    
    return result

def extract_table_data(driver, container):
    """
    Extract structured data from a table container
    
    Args:
        driver: Selenium WebDriver instance
        container: Dictionary with information about the table container
    
    Returns:
        dict: Table data including DataFrame, or None if extraction failed
    """
    try:
        element = container['element']
        element_type = container['type']
        
        # Get container's HTML
        html = element.get_attribute('outerHTML')
        
        # Find table title from nearby headings
        title = get_table_title(driver, element)
        
        # Use BeautifulSoup to parse the HTML structure
        soup = BeautifulSoup(html, 'html.parser')
        
        # Different extraction strategies based on container type
        if element_type == 'html_table':
            headers, rows = extract_html_table_data(soup)
        elif element_type == 'aria_table':
            headers, rows = extract_aria_table_data(soup)
        elif element_type in ['div_table', 'grid']:
            headers, rows = extract_div_table_data(soup, element_type)
        elif element_type == 'list_table':
            headers, rows = extract_list_table_data(soup)
        else:
            # Generic row-based container extraction
            headers, rows = extract_row_container_data(soup)
        
        # Create DataFrame from extracted data
        df = None
        if rows:
            # Check if we have reasonable data
            if len(rows) > 0 and max(len(row) for row in rows) > 1:  # At least 1 row and 2 columns
                if headers and len(headers) == len(rows[0]):
                    df = pd.DataFrame(rows, columns=headers)
                else:
                    # Create generic headers if needed
                    max_cols = max(len(row) for row in rows)
                    headers = [f"Column {i+1}" for i in range(max_cols)]
                    # Pad rows with empty strings if needed
                    padded_rows = [row + [''] * (max_cols - len(row)) for row in rows]
                    df = pd.DataFrame(padded_rows, columns=headers)
                    
                # Clean the dataframe
                df = clean_dataframe(df)
        
        # Only return if we have a valid DataFrame with data
        if df is not None and not df.empty:
            # Check if table contains images
            has_images = check_for_images(soup, df)
            
            return {
                'title': title,
                'dataframe': df,
                'html': html,
                'has_images': has_images,
                'container_type': element_type
            }
        
        return None
    
    except Exception as e:
        logger.error(f"Error extracting table data: {e}")
        return None

def clean_dataframe(df):
    """
    Clean a DataFrame for better presentation and data quality
    
    Args:
        df: pandas DataFrame to clean
    
    Returns:
        pandas DataFrame: Cleaned DataFrame
    """
    # Remove completely empty rows
    df = df.dropna(how='all')
    
    # Remove completely empty columns
    df = df.dropna(axis=1, how='all')
    
    # Clean column names
    df.columns = [str(col).strip() for col in df.columns]
    
    # Remove duplicate columns
    df = df.loc[:, ~df.columns.duplicated()]
    
    # Clean cell values, but preserve HTML for images
    for col in df.columns:
        df[col] = df[col].apply(lambda x: str(x).strip() if not (isinstance(x, str) and '<img' in x) else x)
    
    return df

def get_table_title(driver, element):
    """
    Find the title for a table element by looking for nearby headings
    
    Args:
        driver: Selenium WebDriver instance
        element: Table container element
    
    Returns:
        str: Table title or generic title if none found
    """
    # Try to find a caption or title directly
    try:
        caption = element.find_element(By.TAG_NAME, "caption")
        if caption:
            return caption.text.strip()
    except:
        pass
    
    # Look for nearby headings using JavaScript
    try:
        title = driver.execute_script("""
            function findTableHeading(element) {
                // Check for caption within table
                const caption = element.querySelector('caption');
                if (caption && caption.textContent.trim()) {
                    return caption.textContent.trim();
                }
                
                // Check for ARIA label or title
                if (element.getAttribute('aria-label')) {
                    return element.getAttribute('aria-label');
                }
                
                if (element.getAttribute('title')) {
                    return element.getAttribute('title');
                }
                
                // Check for heading elements before the table
                let prevEl = element.previousElementSibling;
                let checkCount = 0;
                while (prevEl && checkCount < 3) {
                    if (prevEl.tagName && prevEl.tagName.match(/^H[1-6]$/)) {
                        return prevEl.textContent.trim();
                    }
                    prevEl = prevEl.previousElementSibling;
                    checkCount++;
                }
                
                // Check parent container for headings before this element
                let parent = element.parentElement;
                if (parent) {
                    for (let i = 0; i < parent.children.length; i++) {
                        let child = parent.children[i];
                        if (child === element) {
                            break;
                        }
                        if (child.tagName && child.tagName.match(/^H[1-6]$/)) {
                            return child.textContent.trim();
                        }
                    }
                }
                
                // Check for closest heading anywhere above
                const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
                let closestHeading = null;
                let closestDistance = Infinity;
                
                const rect = element.getBoundingClientRect();
                const tableTop = rect.top + window.scrollY;
                
                for (let heading of headings) {
                    const headingRect = heading.getBoundingClientRect();
                    const headingTop = headingRect.top + window.scrollY;
                    
                    if (headingTop < tableTop) {
                        const distance = tableTop - headingTop;
                        if (distance < 300) {  // Limit to headings relatively close
                            if (distance < closestDistance) {
                                closestDistance = distance;
                                closestHeading = heading;
                            }
                        }
                    }
                }
                
                if (closestHeading) {
                    return closestHeading.textContent.trim();
                }
                
                // Look for figcaption
                const parentFigure = element.closest('figure');
                if (parentFigure) {
                    const figCaption = parentFigure.querySelector('figcaption');
                    if (figCaption) {
                        return figCaption.textContent.trim();
                    }
                }
                
                return "";
            }
            return findTableHeading(arguments[0]);
        """, element)
        
        if title:
            return title
    except:
        pass
    
    # If no title found, use element attributes or generate one
    try:
        # Check for table ID
        element_id = element.get_attribute('id')
        if element_id and not element_id.startswith('_'):
            # Convert camelCase or snake_case to readable text
            readable_id = re.sub(r'([a-z])([A-Z])', r'\1 \2', element_id)  # camelCase to spaces
            readable_id = readable_id.replace('_', ' ').replace('-', ' ')  # snake_case to spaces
            return f"Table: {readable_id.title()}"
        
        # Check for descriptive class
        element_class = element.get_attribute('class')
        if element_class and element_class.strip():
            classes = element_class.split()
            descriptive_classes = [c for c in classes if len(c) > 3 and not c.startswith('_')]
            if descriptive_classes:
                readable_class = re.sub(r'([a-z])([A-Z])', r'\1 \2', descriptive_classes[0])
                readable_class = readable_class.replace('_', ' ').replace('-', ' ')
                return f"Table: {readable_class.title()}"
        
        # Use parent container id/class if available
        parent = driver.execute_script("return arguments[0].parentElement", element)
        if parent:
            parent_id = parent.get_attribute('id')
            if parent_id and not parent_id.startswith('_'):
                readable_id = re.sub(r'([a-z])([A-Z])', r'\1 \2', parent_id)
                readable_id = readable_id.replace('_', ' ').replace('-', ' ')
                return f"Table in {readable_id.title()}"
    except:
        pass
    
    # Get page title and use that as context
    try:
        page_title = driver.title
        if page_title:
            page_title = page_title.split(' - ')[0].split(' | ')[0].strip()
            return f"Table from {page_title}"
    except:
        pass
    
    # Generate a unique title as fallback
    return f"Data Table {uuid.uuid4().hex[:4]}"

def extract_html_table_data(soup):
    """
    Extract data from standard HTML table
    
    Args:
        soup: BeautifulSoup object of the table HTML
    
    Returns:
        tuple: (headers, rows) where headers is a list of column names and rows is a list of data rows
    """
    headers = []
    rows = []
    
    # Find the table element
    table = soup.find('table')
    if not table:
        return headers, rows
    
    # Extract headers from thead
    thead = table.find('thead')
    if thead:
        th_rows = thead.find_all('tr')
        if th_rows:
            # Use the last row in thead as it usually has the most specific column headers
            last_th_row = th_rows[-1]
            headers = [clean_text(cell.get_text(strip=True)) for cell in last_th_row.find_all(['th', 'td'])]
    
    # If no headers in thead, try first row
    if not headers:
        first_row = table.find('tr')
        if first_row:
            # Check if first row looks like a header (has th elements or different styling)
            cells = first_row.find_all(['th', 'td'])
            if any(cell.name == 'th' for cell in cells):
                headers = [clean_text(cell.get_text(strip=True)) for cell in cells]
    
    # If still no headers, try first row of tbody
    if not headers and table.find('tbody'):
        first_body_row = table.find('tbody').find('tr')
        if first_body_row:
            cells = first_body_row.find_all(['th', 'td'])
            if any(cell.name == 'th' for cell in cells) or any('header' in cell.get('class', []) for cell in cells):
                headers = [clean_text(cell.get_text(strip=True)) for cell in cells]
    
    # Extract data rows from tbody or table
    tbody = table.find('tbody') or table
    
    # Process all rows
    for tr in tbody.find_all('tr'):
        # Skip if this is the header row we already processed
        if headers and tr == table.find('tr') and any(cell.name == 'th' for cell in tr.find_all(['th', 'td'])):
            continue
        
        # Skip if this row is part of thead
        if thead and tr in thead.find_all('tr'):
            continue
            
        row = []
        for cell in tr.find_all(['td', 'th']):
            # Handle colspan
            colspan = 1
            try:
                colspan_attr = cell.get('colspan')
                if colspan_attr:
                    colspan = int(colspan_attr)
            except (ValueError, TypeError):
                colspan = 1
            
            # Check for images
            img = cell.find('img')
            if img:
                img_src = img.get('src', '')
                img_alt = img.get('alt', '')
                
                # Fix URLs that start with //
                if img_src.startswith('//'):
                    img_src = f"https:{img_src}"
                
                # Fix relative URLs
                if img_src and not img_src.startswith(('http://', 'https://')):
                    # Just store the path - we'll resolve it later
                    img_src = img_src
                
                if img_src:
                    # Include alt text with image for better context
                    img_html = f'<img src="{img_src}" alt="{img_alt}" style="max-width:100px; max-height:100px;">'
                    for _ in range(colspan):
                        row.append(img_html)
                else:
                    cell_text = clean_text(cell.get_text(strip=True))
                    for _ in range(colspan):
                        row.append(cell_text)
            else:
                # Handle text content
                cell_text = clean_text(cell.get_text(strip=True))
                for _ in range(colspan):
                    row.append(cell_text)
                
        # Only add non-empty rows
        if row and any(str(cell).strip() for cell in row):
            rows.append(row)
    
    return headers, rows

def extract_aria_table_data(soup):
    """
    Extract data from a table with ARIA roles
    
    Args:
        soup: BeautifulSoup object of the table HTML
    
    Returns:
        tuple: (headers, rows) where headers is a list of column names and rows is a list of data rows
    """
    headers = []
    rows = []
    
    # Find the table container
    table = soup.find(['div', 'table'], attrs={'role': ['table', 'grid']})
    if not table:
        return headers, rows
    
    # Extract headers from role="columnheader" elements
    header_cells = table.find_all(attrs={'role': 'columnheader'})
    if header_cells:
        headers = [clean_text(cell.get_text(strip=True)) for cell in header_cells]
    
    # Extract rows with role="row"
    row_elements = table.find_all(attrs={'role': 'row'})
    
    # If first row might be header row and we don't have headers yet
    if row_elements and not headers:
        first_row = row_elements[0]
        # Check if it has columnheader children or differs from other rows
        if first_row.find_all(attrs={'role': 'columnheader'}):
            headers = [clean_text(cell.get_text(strip=True)) for cell in first_row.find_all(['div', 'span', 'td', 'th'])]
            row_elements = row_elements[1:]  # Skip first row in data processing
    
    # Process rows
    for row_el in row_elements:
        row = []
        
        # Find cells (role="cell" or role="gridcell")
        cell_elements = row_el.find_all(attrs={'role': ['cell', 'gridcell']})
        
        # If no specific role cells, try direct children
        if not cell_elements:
            cell_elements = [child for child in row_el.children if child.name]
        
        for cell in cell_elements:
            # Check for images
            img = cell.find('img')
            if img:
                img_src = img.get('src', '')
                img_alt = img.get('alt', '')
                
                # Fix URLs that start with //
                if img_src.startswith('//'):
                    img_src = f"https:{img_src}"
                
                if img_src:
                    # Include alt text with image
                    img_html = f'<img src="{img_src}" alt="{img_alt}" style="max-width:100px; max-height:100px;">'
                    row.append(img_html)
                else:
                    row.append(clean_text(cell.get_text(strip=True)))
            else:
                row.append(clean_text(cell.get_text(strip=True)))
        
        # Only add non-empty rows
        if row and any(str(cell).strip() for cell in row):
            rows.append(row)
    
    return headers, rows

def extract_div_table_data(soup, element_type='div_table'):
    """
    Extract data from a div-based table or grid
    
    Args:
        soup: BeautifulSoup object of the container HTML
        element_type: Type of element ('div_table' or 'grid')
    
    Returns:
        tuple: (headers, rows) where headers is a list of column names and rows is a list of data rows
    """
    headers = []
    rows = []
    
    # Look for headers in various ways
    header_selectors = ['.header', '.heading', '.headers', 'th', '[role="columnheader"]', 
                       '.thead', '.table-header', '[class*="header"]', 'thead']
    
    # Build appropriate selector string for BeautifulSoup
    header_selector = ', '.join(header_selectors)
    header_elements = soup.select(header_selector)
    
    if header_elements:
        # If many header elements found, they might be individual cells
        # Look for a parent container first
        header_parent = None
        for header in header_elements:
            parent_classes = header.parent.get('class', [])
            if any('header' in cls.lower() for cls in parent_classes):
                header_parent = header.parent
                break
        
        if header_parent:
            # Get headers from cells in the header parent
            headers = [clean_text(h.get_text(strip=True)) for h in header_parent.find_all(['div', 'span', 'th', 'td'])]
        else:
            # Use header elements directly
            headers = [clean_text(h.get_text(strip=True)) for h in header_elements]
    
    # If we have too many headers, it might be picking up the wrong elements
    if len(headers) > 20:  # Arbitrary threshold
        headers = []
    
    # Look for rows
    row_selectors = ['.row', '.data-row', 'tr', 'li', '[role="row"]', 
                     '[class*="row"]', '[class*="item"]']
    
    # For grids, look for direct children
    if element_type == 'grid':
        parent = soup.find()  # First element, the container
        row_elements = [child for child in parent.children if child.name]
        
        # Check if these children have a grid layout
        if row_elements and all(len(list(el.children)) <= 1 for el in row_elements[:5]):
            # This might be a flat grid, reorganize into rows
            row_elements = organize_grid_elements(row_elements)
    else:
        # Get all row elements matching selectors
        row_elements = []
        for selector in row_selectors:
            elements = soup.select(selector)
            if elements:
                # Choose the most plentiful row type
                if len(elements) > len(row_elements):
                    row_elements = elements
    
    # Process rows
    for row_el in row_elements:
        # Skip if this looks like a header row and we have headers already
        if headers and (
            'header' in row_el.get('class', []) or 
            row_el.select_one('.header, .heading, th, [role="columnheader"]')
        ):
            # If we don't have headers yet, extract them from this row
            if not headers:
                headers = [clean_text(cell.get_text(strip=True)) for cell in row_el.select('.cell, .column, td, th, div, span')]
            continue
            
        # Get cell data
        cell_elements = row_el.select('.cell, .column, td, th, div, span')
        
        # If no specific cell markers, try direct children
        if not cell_elements:
            cell_elements = [child for child in row_el.children if child.name]
        
        row = []
        for cell in cell_elements:
            # Check for images
            img = cell.find('img')
            if img:
                img_src = img.get('src', '')
                img_alt = img.get('alt', '')
                
                # Fix URLs that start with //
                if img_src.startswith('//'):
                    img_src = f"https:{img_src}"
                    
                if img_src:
                    # Include alt text with image
                    img_html = f'<img src="{img_src}" alt="{img_alt}" style="max-width:100px; max-height:100px;">'
                    row.append(img_html)
                else:
                    row.append(clean_text(cell.get_text(strip=True)))
            else:
                row.append(clean_text(cell.get_text(strip=True)))
        
        # Only add non-empty rows
        if row and any(str(cell).strip() for cell in row):
            rows.append(row)
    
    return headers, rows

def organize_grid_elements(elements):
    """
    Reorganize flat grid elements into rows based on their visual position
    
    Args:
        elements: List of elements that are direct children of a grid container
    
    Returns:
        list: Organized elements as rows
    """
    try:
        # Get coordinates of each element
        positions = []
        for i, el in enumerate(elements):
            try:
                # Extract style and position information
                style = el.get('style', '')
                
                # Try to extract grid column and row if available
                grid_column = None
                grid_row = None
                
                # Check style attributes
                if 'grid-column:' in style:
                    match = re.search(r'grid-column:\s*(\d+)', style)
                    if match:
                        grid_column = int(match.group(1))
                
                if 'grid-row:' in style:
                    match = re.search(r'grid-row:\s*(\d+)', style)
                    if match:
                        grid_row = int(match.group(1))
                
                positions.append({
                    'index': i,
                    'element': el,
                    'grid_column': grid_column,
                    'grid_row': grid_row
                })
            except Exception as e:
                logger.warning(f"Error processing grid element position: {e}")
                continue
        
        # If we have grid row/column info, organize by row
        if any(p['grid_row'] is not None for p in positions):
            # Group by grid row
            row_groups = {}
            for pos in positions:
                row = pos['grid_row'] if pos['grid_row'] is not None else 999
                if row not in row_groups:
                    row_groups[row] = []
                row_groups[row].append(pos)
            
            # Sort each row by column
            for row in row_groups:
                row_groups[row].sort(key=lambda p: p['grid_column'] if p['grid_column'] is not None else 999)
            
            # Convert to list of rows
            sorted_rows = [row_groups[row] for row in sorted(row_groups.keys())]
            return [
                [p['element'] for p in row]
                for row in sorted_rows
            ]
        
        # If we don't have grid info, try to organize visually
        # This is a simplified approach that assumes a typical left-to-right, top-to-bottom layout
        # For a more accurate approach, we'd need to inspect CSS and layout in the browser
        
        # Just convert flat list to rows based on a guess of columns
        # Determine likely number of columns
        if len(elements) >= 3:
            # Guess number of columns based on overall layout
            # This is just a heuristic; for real grid detection, we'd need browser rendering info
            if len(elements) % 2 == 0:
                cols = 2
            elif len(elements) % 3 == 0:
                cols = 3
            elif len(elements) % 4 == 0:
                cols = 4
            else:
                cols = 3  # Default guess
                
            # Group elements into rows
            result = []
            for i in range(0, len(elements), cols):
                row = elements[i:i+cols]
                if row:  # Skip empty rows
                    result.append(row)
            return result
                
        # Fallback: return original flat list
        return [elements]
    except Exception as e:
        logger.warning(f"Error organizing grid elements: {e}")
        return [elements]  # Return as single row
