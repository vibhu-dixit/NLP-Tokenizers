"""
Run this CMD in terminal before you run the code: pip install selenium webdriver-manager
"""
"""
uses Selenium to capture screenshots of specific elements (tables, images, graphs)
from a webpage and saves them in organized directories along with the full page HTML.
"""

# Import core Python modules
import os
import time
import logging
import shutil 
# Import Selenium components
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging system
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),  # Log to file
        logging.StreamHandler()              # Log to console
    ]
)

# ======================
# CONFIGURATION SETTINGS
# ======================
URL = "https://www.bea.gov/news/glance"  # Target webpage URL
OUTPUT_DIR = "webpage_elements"                       # Root directory for outputs

# Element configuration dictionary defining what to capture
ELEMENT_CONFIG = {
    'tables': {'selector': 'table'},  # HTML tables
    'images': {'selector': 'img'},    # All images
    'graphs': {'selector': 'svg, canvas, div[class*="chart"], div[class*="graph"]'}  # Charts/graphs
}

def cleanup():
    """Remove all files and directories before running the scraper"""
    if os.path.exists(OUTPUT_DIR):
        logging.info(f"Cleaning up output directory: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)  # Remove the entire directory and its contents
    logging.info("Cleanup complete")

def setup_driver():
    """
    Configure and initialize Chrome WebDriver with headless options
    Returns: WebDriver instance
    """
    try:
        # Configure Chrome options
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')          # Run browser in background
        chrome_options.add_argument('--no-sandbox')        # Disable sandboxing
        chrome_options.add_argument('--disable-dev-shm-usage')  # Prevent shared memory issues
        chrome_options.add_argument('--window-size=1920x1080')  # Set browser window size

        # Automatic ChromeDriver management
        service = Service(ChromeDriverManager().install())  # Handles driver executable
        
        # Initialize Chrome driver
        driver = webdriver.Chrome(
            service=service,
            options=chrome_options
        )
        driver.set_page_load_timeout(30)  # Set page load timeout to 30 seconds
        logging.info("Chrome driver initialized successfully")
        return driver
    
    except Exception as e:
        logging.error(f"Driver setup failed: {str(e)}")
        raise

def create_directories():
    """
    Create output directory structure:
    - webpage_elements/
      |- tables/
      |- images/
      |- graphs/
    """
    try:
        # Create root directory if not exists
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Create subdirectories for each element type
        for folder in ELEMENT_CONFIG.keys():
            os.makedirs(os.path.join(OUTPUT_DIR, folder), exist_ok=True)
        
        logging.info("Created output directories")
    
    except Exception as e:
        logging.error(f"Directory creation failed: {str(e)}")
        raise

def capture_element_screenshot(driver, element, category, index):
    """
    Capture and save screenshot of a web element
    Args:
        driver: WebDriver instance
        element: WebElement to capture
        category: Type of element (tables/images/graphs)
        index: Numerical identifier for the element
    """
    try:
        # Generate filename and path
        filename = f"{category}_{index}.png"
        filepath = os.path.join(OUTPUT_DIR, category, filename)
        
        # Scroll element into view with smooth animation
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
            element
        )
        time.sleep(0.5)  # Allow time for rendering after scroll
        
        # Capture element screenshot
        element.screenshot(filepath)
        logging.info(f"Saved {category} #{index}")
    
    except Exception as e:
        logging.warning(f"Failed to capture {category} #{index}: {str(e)}")

def process_page(driver):
    """
    Main processing workflow:
    1. Save full page HTML
    2. Capture screenshots of configured elements
    """
    try:
        # Save complete page HTML
        with open(os.path.join(OUTPUT_DIR, 'full_page.html'), 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
            logging.info("Saved full page HTML")
        
        # Process each element category
        for category, config in ELEMENT_CONFIG.items():
            logging.info(f"Processing {category} elements...")
            
            # Wait for elements to be present in DOM
            elements = WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, config['selector']))
            )
            
            if not elements:
                logging.warning(f"No {category} elements found")
                continue
                
            logging.info(f"Found {len(elements)} {category} elements")
            
            # Capture each element
            for idx, element in enumerate(elements, 1):
                capture_element_screenshot(driver, element, category, idx)
                
    except Exception as e:
        logging.error(f"Page processing failed: {str(e)}")
        raise

def main():
    """
    Main execution sequence:
    1. Create directories
    2. Initialize browser
    3. Load webpage
    4. Process elements
    5. Cleanup resources
    """
    try:
        cleanup()  # Clear existing files
        # Initialize directory structure
        create_directories()
        
        # Launch browser
        driver = setup_driver()
        
        # Load target webpage
        logging.info(f"Loading page: {URL}")
        driver.get(URL)
        
        # Wait for full page load
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        logging.info("Page loaded completely")
        
        # Process page elements
        process_page(driver)
        logging.info("Operation completed successfully")
    
    except Exception as e:
        logging.error(f"Main execution failed: {str(e)}")
    
    finally:
        # Cleanup browser instance
        if 'driver' in locals():
            driver.quit()
            logging.info("Browser closed")

if __name__ == "__main__":
    # Entry point of the script
    main()
