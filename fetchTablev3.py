import sys
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

def screenshot_table(url, table_title):
    """
    Capture a screenshot of a specific table identified by its title.
    
    Args:
        url (str): The URL of the webpage containing the table
        table_title (str): The title or caption of the table to screenshot
    """
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    # Initialize WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        # Load the webpage
        driver.get(url)
        print(f"Loaded page: {url}")
        
        # Wait for the page to load
        time.sleep(3)
        
        # Find the table element
        table_element = None
        
        # Strategy 1: Find by title in standard table elements
        try:
            # Look for tables with captions or titles
            tables = driver.find_elements(By.XPATH, 
                f"//table[./caption[contains(text(), '{table_title}')] or @title[contains(., '{table_title}')]]")
            if tables:
                table_element = tables[0]
                print(f"Found table with caption/title containing '{table_title}'")
        except Exception as e:
            print(f"Error in strategy 1: {e}")
        
        # Strategy 2: Find heading elements containing the title, then look for nearby tables
        if not table_element:
            try:
                # Find elements containing the title text
                title_xpath = f"//*[contains(text(), '{table_title}')]"
                title_elements = driver.find_elements(By.XPATH, title_xpath)
                
                for title_el in title_elements:
                    print(f"Examining title element: {title_el.tag_name} with text: {title_el.text[:50]}...")
                    
                    # Look for tables near this title element
                    try:
                        # Try following siblings first (most common pattern)
                        following_tables = driver.find_elements(By.XPATH, 
                            f"//h1[contains(text(), '{table_title}')]/following::table[1] | " +
                            f"//h2[contains(text(), '{table_title}')]/following::table[1] | " +
                            f"//h3[contains(text(), '{table_title}')]/following::table[1] | " +
                            f"//h4[contains(text(), '{table_title}')]/following::table[1] | " +
                            f"//div[contains(text(), '{table_title}')]/following::table[1]")
                        
                        if following_tables:
                            table_element = following_tables[0]
                            print(f"Found table after title element")
                            break
                        
                        # Try looking for div-based tables
                        following_div_tables = driver.find_elements(By.XPATH, 
                            f"//h1[contains(text(), '{table_title}')]/following::div[contains(@class, 'table')][1] | " +
                            f"//h2[contains(text(), '{table_title}')]/following::div[contains(@class, 'table')][1] | " +
                            f"//h3[contains(text(), '{table_title}')]/following::div[contains(@class, 'table')][1] | " +
                            f"//h4[contains(text(), '{table_title}')]/following::div[contains(@class, 'table')][1] | " +
                            f"//div[contains(text(), '{table_title}')]/following::div[contains(@class, 'table')][1] | " +
                            f"//h1[contains(text(), '{table_title}')]/following::div[contains(@class, 'standings')][1] | " +
                            f"//h2[contains(text(), '{table_title}')]/following::div[contains(@class, 'standings')][1] | " +
                            f"//h3[contains(text(), '{table_title}')]/following::div[contains(@class, 'standings')][1] | " +
                            f"//h4[contains(text(), '{table_title}')]/following::div[contains(@class, 'standings')][1] | " +
                            f"//div[contains(text(), '{table_title}')]/following::div[contains(@class, 'standings')][1]")
                        
                        if following_div_tables:
                            table_element = following_div_tables[0]
                            print(f"Found div-based table after title element")
                            break
                        
                        # Try to find a table in the parent container
                        parent = title_el.find_element(By.XPATH, "..")
                        
                        # First look for standard tables
                        tables_in_parent = parent.find_elements(By.TAG_NAME, "table")
                        if tables_in_parent:
                            table_element = tables_in_parent[0]
                            print(f"Found table within title element's parent")
                            break
                        
                        # Then look for div-based tables
                        div_tables_in_parent = parent.find_elements(By.XPATH, 
                            ".//div[contains(@class, 'table') or contains(@class, 'standings') or contains(@class, 'grid')]")
                        if div_tables_in_parent:
                            table_element = div_tables_in_parent[0]
                            print(f"Found div-based table within title element's parent")
                            break
                    except NoSuchElementException:
                        continue
            except Exception as e:
                print(f"Error in strategy 2: {e}")
        
        # Strategy 3: Specific handling for ESPN and similar sports sites
        if not table_element and ("espn.com" in url or "standings" in url.lower()):
            try:
                print("Using sports website specific strategy")
                
                # Look for tabs or filters that might match our title
                filter_xpath = "//div[contains(@class, 'filters')]//div | " + \
                              "//div[contains(@class, 'tablist')]//div | " + \
                              "//div[contains(@class, 'tabs')]//div | " + \
                              "//ul[contains(@class, 'tabs')]//li"
                
                filters = driver.find_elements(By.XPATH, filter_xpath)
                
                clicked = False
                for filter_el in filters:
                    try:
                        filter_text = filter_el.text.strip().lower()
                        if table_title.lower() in filter_text or filter_text in table_title.lower():
                            # This filter seems to match our title, try clicking it
                            filter_el.click()
                            clicked = True
                            print(f"Clicked filter/tab: {filter_text}")
                            time.sleep(2)  # Wait for content to update
                            break
                    except:
                        continue
                
                # Now look for standings containers
                standings_xpath = "//div[contains(@class, 'standings')] | " + \
                                 "//div[contains(@class, 'StandingsTable')] | " + \
                                 "//div[contains(@class, 'Table')] | " + \
                                 "//section[contains(@class, 'standings')]"
                
                standings_containers = driver.find_elements(By.XPATH, standings_xpath)
                
                if standings_containers:
                    # If we clicked a filter, take the first container (most likely to be relevant)
                    if clicked:
                        table_element = standings_containers[0]
                        print("Found standings container after clicking filter")
                    else:
                        # Try to find a container that might match our title
                        for container in standings_containers:
                            container_text = container.text.lower()
                            if table_title.lower() in container_text:
                                table_element = container
                                print("Found standings container matching title")
                                break
                        
                        # If no specific match, take the first one
                        if not table_element and standings_containers:
                            table_element = standings_containers[0]
                            print("Using first standings container")
            except Exception as e:
                print(f"Error in sports website strategy: {e}")
        
        # Strategy 4: Fallback to any table-like element
        if not table_element:
            try:
                print("Using fallback strategy")
                
                # Try to find any HTML table
                tables = driver.find_elements(By.TAG_NAME, "table")
                if tables:
                    table_element = tables[0]
                    print(f"Fallback: Using first HTML table (of {len(tables)})")
                else:
                    # Try to find any div that looks like a table
                    table_like_divs = driver.find_elements(By.XPATH,
                        "//div[contains(@class, 'table') or " +
                        "contains(@class, 'standings') or " +
                        "contains(@class, 'grid') or " +
                        "contains(@class, 'data')]")
                    
                    if table_like_divs:
                        table_element = table_like_divs[0]
                        print(f"Fallback: Using first div-based table (of {len(table_like_divs)})")
            except Exception as e:
                print(f"Error in fallback strategy: {e}")
        
        # If we still don't have a table element, take a screenshot of the whole page
        if not table_element:
            print("No table found. Taking screenshot of the entire page.")
            driver.save_screenshot("full_page_screenshot.png")
            print("Full page screenshot saved as full_page_screenshot.png")
            return
        
        # Scroll to the table element to make sure it's visible
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", table_element)
        time.sleep(1)
        
        # Special handling for ESPN tables
        if "espn.com" in url:
            try:
                print("Applying ESPN-specific table handling")
                
                # For ESPN, we may need to find the parent container that holds the full table
                # since ESPN often has separate containers for different parts of the table
                espn_table_container = table_element
                
                # Try to find a larger container by going up in the DOM
                for _ in range(5):  # Try up to 5 levels up
                    parent = driver.execute_script("return arguments[0].parentElement", espn_table_container)
                    if parent:
                        # Check if this parent is wider and contains the full table
                        parent_size = driver.execute_script("return {width: arguments[0].offsetWidth, height: arguments[0].offsetHeight}", parent)
                        current_size = driver.execute_script("return {width: arguments[0].offsetWidth, height: arguments[0].offsetHeight}", espn_table_container)
                        
                        # If parent is significantly wider, use it instead
                        if parent_size['width'] > current_size['width'] * 1.3:  # 30% wider
                            espn_table_container = parent
                            print(f"Found wider parent container: {parent_size['width']}px vs {current_size['width']}px")
                        else:
                            # If we didn't find a wider container, stop looking
                            break
                    else:
                        break
                
                # Check if we found a better container
                if espn_table_container != table_element:
                    table_element = espn_table_container
                    print("Using wider container for ESPN table")
                
                # Try to find specific standings table container class names
                try:
                    full_standings = driver.find_element(By.XPATH, "//div[contains(@class, 'ResponsiveTable') or contains(@class, 'Standings')]")
                    if full_standings:
                        table_element = full_standings
                        print("Found ESPN ResponsiveTable/Standings container")
                except:
                    pass
                
                # Find if there's a container with all the stats (the one with column headers)
                try:
                    headers = driver.find_elements(By.XPATH, "//tr[th[contains(text(), 'GP') or contains(text(), 'W') or contains(text(), 'L') or contains(text(), 'P')]]")
                    if headers:
                        # Find the closest table or div containing this header
                        for header in headers:
                            parent = header
                            for _ in range(5):  # Look up to 5 levels up
                                parent = driver.execute_script("return arguments[0].parentElement", parent)
                                if parent and (parent.tag_name == 'table' or 
                                              ('table' in parent.get_attribute('class') or 
                                               'Table' in parent.get_attribute('class'))):
                                    table_element = parent
                                    print("Found table with proper headers (GP, W, L, P)")
                                    break
                except:
                    pass
            except Exception as e:
                print(f"Error in ESPN-specific handling: {e}")
        
        # Ensure the table is fully visible (if possible)
        try:
            # Adjust the window size to be large enough
            driver.set_window_size(2000, 1500)  # Use a larger window
            
            # Check if table is larger than viewport and adjust accordingly
            driver.execute_script("""
                var rect = arguments[0].getBoundingClientRect();
                if (rect.height > window.innerHeight) {
                    window.scrollTo(0, window.pageYOffset + rect.top - 100);
                }
                // If there are horizontal scrollbars, try to capture the full width
                if (rect.width > window.innerWidth) {
                    arguments[0].style.maxWidth = "none";
                    arguments[0].style.width = "auto";
                }
            """, table_element)
            time.sleep(1)
        except:
            pass
        
        # Create a clean filename from the table title
        safe_title = re.sub(r'[^\w\s-]', '', table_title).strip()
        safe_title = re.sub(r'[-\s]+', '_', safe_title)
        screenshot_filename = f"table_{safe_title}_screenshot.png"
        
        # For ESPN tables, try to ensure we get the full table by manipulating the page
        if "espn.com" in url:
            try:
                # Try to make table fully visible by adjusting CSS
                driver.execute_script("""
                    // Force table to be fully visible and expanded
                    arguments[0].style.overflow = 'visible';
                    arguments[0].style.maxWidth = 'none';
                    arguments[0].style.width = 'auto';
                    
                    // If there are any parent containers with overflow:hidden, fix them
                    let parent = arguments[0].parentElement;
                    for (let i = 0; i < 10 && parent; i++) {
                        if (window.getComputedStyle(parent).overflow === 'hidden' || 
                            window.getComputedStyle(parent).overflowX === 'hidden') {
                            parent.style.overflow = 'visible';
                            parent.style.overflowX = 'visible';
                        }
                        parent = parent.parentElement;
                    }
                    
                    // If there are any parent containers with fixed width, expand them
                    parent = arguments[0].parentElement;
                    for (let i = 0; i < 10 && parent; i++) {
                        if (window.getComputedStyle(parent).width !== 'auto') {
                            parent.style.width = 'auto';
                            parent.style.maxWidth = 'none';
                        }
                        parent = parent.parentElement;
                    }
                """, table_element)
                
                # Wait for changes to apply
                time.sleep(2)
            except Exception as e:
                print(f"Error adjusting table for ESPN: {e}")
        
        # Take the screenshot
        try:
            # First attempt: regular screenshot
            table_element.screenshot(screenshot_filename)
            print(f"Table screenshot saved as {screenshot_filename}")
            
            
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            # Fallback to a different approach if the first one fails
            try:
                # Try full page screenshot instead
                driver.save_screenshot(f"full_{screenshot_filename}")
                print(f"Full page screenshot saved as full_{screenshot_filename}")
            except:
                pass
    
    except Exception as e:
        print(f"An error occurred: {e}")
        # Take screenshot of the entire page as a fallback
        try:
            driver.save_screenshot("error_screenshot.png")
            print("Error occurred, full page screenshot saved as error_screenshot.png")
        except:
            pass
    
    finally:
        driver.quit()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <url> <table_title>")
        sys.exit(1)
    
    url = sys.argv[1]
    table_title = sys.argv[2]
    screenshot_table(url, table_title)