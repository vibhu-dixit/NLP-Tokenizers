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

def accept_cookies(driver, max_attempts=3):
    """
    Detect and accept common cookie consent banners and overlays

    Args:
        driver: Selenium WebDriver instance
        max_attempts: Maximum number of attempts to find and click consent buttons
    """
    print("Checking for cookie consent banners...")

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

        # Links or anchor tags
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consent')]",

        # Input buttons
        "//input[@type='button' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
        "//input[@type='button' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",

        # Div and span elements acting as buttons
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept') and (@role='button' or contains(@class, 'btn') or contains(@class, 'button'))]",
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree') and (@role='button' or contains(@class, 'btn') or contains(@class, 'button'))]",
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept') and (@role='button' or contains(@class, 'btn') or contains(@class, 'button'))]",

        # IDs and classes
        "//*[contains(@id, 'cookie-accept') or contains(@id, 'accept-cookie') or contains(@id, 'cookieAccept')]",
        "//*[contains(@class, 'cookie-accept') or contains(@class, 'accept-cookie') or contains(@class, 'cookieAccept')]",
        "//*[contains(@id, 'cookie-agree') or contains(@id, 'agree-cookie') or contains(@id, 'cookieAgree')]",
        "//*[contains(@id, 'cookie-consent') or contains(@id, 'consent-cookie') or contains(@id, 'cookieConsent')]"
    ]

    # Try each attempt
    for attempt in range(max_attempts):
        for xpath in consent_button_patterns:
            try:
                # Short wait to find the element
                buttons = driver.find_elements(By.XPATH, xpath)
                for button in buttons:
                    # Check if element is visible
                    if button.is_displayed():
                        print(f"Found consent button: {button.text or button.get_attribute('value') or button.get_attribute('id') or 'unnamed button'}")
                        button.click()
                        print("Clicked consent button")
                        time.sleep(1)  # Wait for overlay to disappear
                        return True
            except Exception as e:
                # Just continue to the next pattern
                pass

        # If no button found on this attempt, wait a bit and try again
        if attempt < max_attempts - 1:
            time.sleep(1)

    # Special cases for iframes (some consent banners are in iframes)
    try:
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        for frame in frames:
            try:
                # Check if the frame might be a cookie consent frame
                frame_id = frame.get_attribute("id") or ""
                frame_name = frame.get_attribute("name") or ""

                if ("cookie" in frame_id.lower() or
                    "consent" in frame_id.lower() or
                    "cookie" in frame_name.lower() or
                    "consent" in frame_name.lower()):

                    # Switch to this frame
                    driver.switch_to.frame(frame)
                    print(f"Switched to frame: {frame_id or frame_name}")

                    # Try all our patterns in this frame
                    for xpath in consent_button_patterns:
                        try:
                            buttons = driver.find_elements(By.XPATH, xpath)
                            for button in buttons:
                                if button.is_displayed():
                                    button.click()
                                    print(f"Clicked consent button in iframe: {button.text or 'unnamed button'}")
                                    time.sleep(1)
                                    driver.switch_to.default_content()
                                    return True
                        except:
                            pass

                    # Switch back to main content
                    driver.switch_to.default_content()
            except:
                driver.switch_to.default_content()
                continue
    except Exception as e:
        print(f"Error checking frames: {e}")

    print("No cookie consent buttons found or unable to interact with them")
    return False

def screenshot_table(url, table_title):
    """
    Capture a screenshot of a specific table identified by its title.

    Args:
        url (str): The URL of the webpage containing the table
        table_title (str): The title or caption of the table to screenshot
    """
    # Set up Chrome options for Colab environment
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # Initialize WebDriver with specific Colab settings
    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Load the webpage
        driver.get(url)
        print(f"Loaded page: {url}")

        # Wait for the page to load
        time.sleep(3)

        # Handle cookie consent overlays
        accept_cookies(driver)

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

def screenshot_chart(url, chart_title):
    """
    Capture a screenshot of a specific chart or graph identified by its title.

    Args:
        url (str): The URL of the webpage containing the chart/graph
        chart_title (str): The title or caption of the chart/graph to screenshot
    """
    # Set up Chrome options for Colab environment
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # Initialize WebDriver with specific Colab settings
    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Load the webpage
        driver.get(url)
        print(f"Loaded page: {url}")

        # Wait for the page to load
        time.sleep(3)

        # Handle cookie consent overlays
        accept_cookies(driver)

        # Find the chart element
        chart_element = None

        # Strategy 1: Find by title in chart/graph containers
        try:
            # Common chart container classes and attributes
            chart_xpath = (
                f"//div[contains(@class, 'chart') and contains(., '{chart_title}')] | " +
                f"//div[contains(@class, 'graph') and contains(., '{chart_title}')] | " +
                f"//div[contains(@class, 'visualization') and contains(., '{chart_title}')] | " +
                f"//div[contains(@class, 'figure') and contains(., '{chart_title}')] | " +
                f"//figure[contains(., '{chart_title}')] | " +
                f"//div[@data-highcharts-chart and contains(., '{chart_title}')] | " +
                f"//div[contains(@class, 'plotly') and contains(., '{chart_title}')] | " +
                f"//div[contains(@class, 'd3') and contains(., '{chart_title}')]"
            )
            
            charts = driver.find_elements(By.XPATH, chart_xpath)
            if charts:
                chart_element = charts[0]
                print(f"Found chart container with title '{chart_title}'")
        except Exception as e:
            print(f"Error in strategy 1: {e}")

        # Strategy 2: Find heading elements containing the title, then look for nearby charts
        if not chart_element:
            try:
                # Find elements containing the title text
                title_xpath = f"//*[contains(text(), '{chart_title}')]"
                title_elements = driver.find_elements(By.XPATH, title_xpath)

                for title_el in title_elements:
                    print(f"Examining title element: {title_el.tag_name} with text: {title_el.text[:50]}...")

                    # Look for charts near this title element
                    try:
                        # Try following siblings first (most common pattern)
                        following_charts = driver.find_elements(By.XPATH,
                            f"//h1[contains(text(), '{chart_title}')]/following::svg[1] | " +
                            f"//h2[contains(text(), '{chart_title}')]/following::svg[1] | " +
                            f"//h3[contains(text(), '{chart_title}')]/following::svg[1] | " +
                            f"//h4[contains(text(), '{chart_title}')]/following::svg[1] | " +
                            f"//div[contains(text(), '{chart_title}')]/following::svg[1] | " +
                            f"//h1[contains(text(), '{chart_title}')]/following::canvas[1] | " +
                            f"//h2[contains(text(), '{chart_title}')]/following::canvas[1] | " +
                            f"//h3[contains(text(), '{chart_title}')]/following::canvas[1] | " +
                            f"//h4[contains(text(), '{chart_title}')]/following::canvas[1] | " +
                            f"//div[contains(text(), '{chart_title}')]/following::canvas[1]")

                        if following_charts:
                            chart_element = following_charts[0]
                            print(f"Found chart after title element")
                            break

                        # Try looking for div-based charts
                        following_div_charts = driver.find_elements(By.XPATH,
                            f"//h1[contains(text(), '{chart_title}')]/following::div[contains(@class, 'chart')][1] | " +
                            f"//h2[contains(text(), '{chart_title}')]/following::div[contains(@class, 'chart')][1] | " +
                            f"//h3[contains(text(), '{chart_title}')]/following::div[contains(@class, 'chart')][1] | " +
                            f"//h4[contains(text(), '{chart_title}')]/following::div[contains(@class, 'chart')][1] | " +
                            f"//div[contains(text(), '{chart_title}')]/following::div[contains(@class, 'chart')][1] | " +
                            f"//h1[contains(text(), '{chart_title}')]/following::div[contains(@class, 'graph')][1] | " +
                            f"//h2[contains(text(), '{chart_title}')]/following::div[contains(@class, 'graph')][1] | " +
                            f"//h3[contains(text(), '{chart_title}')]/following::div[contains(@class, 'graph')][1] | " +
                            f"//h4[contains(text(), '{chart_title}')]/following::div[contains(@class, 'graph')][1] | " +
                            f"//div[contains(text(), '{chart_title}')]/following::div[contains(@class, 'graph')][1] | " +
                            f"//h1[contains(text(), '{chart_title}')]/following::div[contains(@class, 'visualization')][1] | " +
                            f"//h2[contains(text(), '{chart_title}')]/following::div[contains(@class, 'visualization')][1] | " +
                            f"//h3[contains(text(), '{chart_title}')]/following::div[contains(@class, 'visualization')][1] | " +
                            f"//h4[contains(text(), '{chart_title}')]/following::div[contains(@class, 'visualization')][1] | " +
                            f"//div[contains(text(), '{chart_title}')]/following::div[contains(@class, 'visualization')][1] | " +
                            f"//h1[contains(text(), '{chart_title}')]/following::figure[1] | " +
                            f"//h2[contains(text(), '{chart_title}')]/following::figure[1] | " +
                            f"//h3[contains(text(), '{chart_title}')]/following::figure[1] | " +
                            f"//h4[contains(text(), '{chart_title}')]/following::figure[1] | " +
                            f"//div[contains(text(), '{chart_title}')]/following::figure[1]")

                        if following_div_charts:
                            chart_element = following_div_charts[0]
                            print(f"Found div-based chart after title element")
                            break

                        # Try to find a chart in the parent container
                        parent = title_el.find_element(By.XPATH, "..")

                        # Look for chart elements in parent
                        chart_in_parent = parent.find_elements(By.XPATH, 
                            ".//svg | .//canvas | " +
                            ".//div[contains(@class, 'chart')] | " + 
                            ".//div[contains(@class, 'graph')] | " + 
                            ".//div[contains(@class, 'visualization')] | " +
                            ".//div[contains(@class, 'highcharts')] | " +
                            ".//div[contains(@class, 'plotly')] | " +
                            ".//figure")
                        
                        if chart_in_parent:
                            chart_element = chart_in_parent[0]
                            print(f"Found chart within title element's parent")
                            break
                    except NoSuchElementException:
                        continue
            except Exception as e:
                print(f"Error in strategy 2: {e}")

        # Strategy 3: Look directly for SVG or Canvas elements that might be charts
        if not chart_element:
            try:
                print("Looking for SVG or Canvas elements")
                
                # Check for SVG elements
                svg_elements = driver.find_elements(By.TAG_NAME, "svg")
                
                # Filter SVGs to find those likely to be charts (having paths, circles, rects)
                for svg in svg_elements:
                    try:
                        # Check if this SVG has chart-like elements
                        paths = svg.find_elements(By.TAG_NAME, "path")
                        circles = svg.find_elements(By.TAG_NAME, "circle")
                        rects = svg.find_elements(By.TAG_NAME, "rect")
                        
                        # SVG with multiple paths/shapes is likely a chart
                        if (len(paths) > 5) or (len(circles) > 5) or (len(rects) > 5):
                            chart_element = svg
                            print(f"Found SVG chart with {len(paths)} paths, {len(circles)} circles, {len(rects)} rectangles")
                            break
                    except:
                        continue
                
                # If no SVG charts found, check for canvas elements
                if not chart_element:
                    canvas_elements = driver.find_elements(By.TAG_NAME, "canvas")
                    if canvas_elements:
                        # Look for canvas elements with proper dimensions
                        for canvas in canvas_elements:
                            width = canvas.get_attribute("width")
                            height = canvas.get_attribute("height")
                            if width and height and int(width) > 100 and int(height) > 100:
                                chart_element = canvas
                                print(f"Found canvas element with dimensions {width}x{height}")
                                break
            except Exception as e:
                print(f"Error in strategy 3: {e}")

        # Strategy 4: Look for div elements with chart library classes
        if not chart_element:
            try:
                print("Looking for chart library containers")
                
                chart_library_xpath = (
                    "//div[contains(@class, 'highcharts')] | " +
                    "//div[contains(@class, 'plotly')] | " +
                    "//div[contains(@class, 'nvd3')] | " +  # NVD3 (built on D3)
                    "//div[contains(@class, 'c3')] | " +  # C3.js
                    "//div[contains(@class, 'chartjs')] | " +
                    "//div[contains(@class, 'apex')] | " +  # ApexCharts
                    "//div[contains(@class, 'echarts')] | " +  # ECharts
                    "//div[contains(@class, 'recharts')] | " +  # Recharts (React)
                    "//div[contains(@class, 'vis')] | " +  # Various visualization libs
                    "//div[@data-highcharts-chart] | " +  # Highcharts specific attribute
                    "//div[@data-echarts-chart]"  # ECharts specific attribute
                )
                
                chart_containers = driver.find_elements(By.XPATH, chart_library_xpath)
                if chart_containers:
                    chart_element = chart_containers[0]
                    print(f"Found chart library container")
            except Exception as e:
                print(f"Error in strategy 4: {e}")

        # Strategy 5: Special handling for common chart websites (e.g., statista, ourworldindata)
        if not chart_element:
            try:
                print("Using chart website specific strategy")
                
                if "statista.com" in url:
                    statista_xpath = "//div[contains(@class, 'statisticContainer')] | //div[@id='statisticContainer']"
                    statista_charts = driver.find_elements(By.XPATH, statista_xpath)
                    if statista_charts:
                        chart_element = statista_charts[0]
                        print("Found Statista chart container")
                
                elif "ourworldindata.org" in url:
                    owid_xpath = "//figure[contains(@class, 'grapherContainer')] | //div[contains(@class, 'chart')]"
                    owid_charts = driver.find_elements(By.XPATH, owid_xpath)
                    if owid_charts:
                        chart_element = owid_charts[0]
                        print("Found Our World in Data chart container")
                
                elif "tradingview.com" in url:
                    tv_xpath = "//div[contains(@class, 'chart-container')]"
                    tv_charts = driver.find_elements(By.XPATH, tv_xpath)
                    if tv_charts:
                        chart_element = tv_charts[0]
                        print("Found TradingView chart container")
            except Exception as e:
                print(f"Error in chart website strategy: {e}")

        # If we still don't have a chart element, take a screenshot of the whole page
        if not chart_element:
            print("No chart found. Taking screenshot of the entire page.")
            driver.save_screenshot("full_page_screenshot.png")
            print("Full page screenshot saved as full_page_screenshot.png")
            return

        # Scroll to the chart element to make sure it's visible
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", chart_element)
        time.sleep(1)

        # Ensure the chart is fully visible
        try:
            # Expand charts that might be in containers with fixed sizes
            driver.execute_script("""
                // For SVG charts, ensure they're fully visible
                if (arguments[0].tagName.toLowerCase() === 'svg') {
                    arguments[0].setAttribute('width', '100%');
                    arguments[0].setAttribute('height', 'auto');
                    arguments[0].style.maxWidth = 'none';
                }
                
                // For container elements, make sure they're expanded
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
                
                // Wait for any animations to complete
                if (arguments[0].classList.contains('animated') || 
                    arguments[0].classList.contains('animation')) {
                    // Add a small delay for animations
                    setTimeout(() => {}, 1000);
                }
            """, chart_element)
            
            # Wait for changes to apply
            time.sleep(2)
        except Exception as e:
            print(f"Error ensuring chart visibility: {e}")

        # Create a clean filename from the chart title
        safe_title = re.sub(r'[^\w\s-]', '', chart_title).strip()
        safe_title = re.sub(r'[-\s]+', '_', safe_title)
        screenshot_filename = f"chart_{safe_title}_screenshot.png"

        # Take the screenshot
        try:
            # First attempt: regular screenshot
            chart_element.screenshot(screenshot_filename)
            print(f"Chart screenshot saved as {screenshot_filename}")
            
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            # Fallback to a different approach if the first one fails
            try:
                # Try full page screenshot with highlighted chart
                driver.execute_script("""
                    // Highlight the chart with a border
                    arguments[0].style.border = '3px solid red';
                """, chart_element)
                
                driver.save_screenshot(f"full_{screenshot_filename}")
                print(f"Full page screenshot with highlighted chart saved as full_{screenshot_filename}")
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

def screenshot_element(url, element_title, element_type="auto"):
    """
    Capture a screenshot of a specific table or chart/graph identified by its title.
    
    Args:
        url (str): The URL of the webpage containing the element
        element_title (str): The title or caption of the element to screenshot
        element_type (str): The type of element to look for: "table", "chart", or "auto" (detect automatically)
    """
    if element_type.lower() == "table":
        screenshot_table(url, element_title)
    elif element_type.lower() == "chart" or element_type.lower() == "graph":
        screenshot_chart(url, element_title)
    else:
        # Auto-detect whether to look for a table or chart
        # Start by looking for both
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=chrome_options)
        try:
            # Load the webpage
            driver.get(url)
            print(f"Loaded page: {url}")
            time.sleep(3)
            accept_cookies(driver)
            
            # Look for indicators to determine if element is a table or chart
            # First check if there's a table with this title
            table_indicators = driver.find_elements(By.XPATH, 
                f"//table[./caption[contains(text(), '{element_title}')] or @title[contains(., '{element_title}')]] | " +
                f"//div[contains(@class, 'table') and contains(., '{element_title}')]")
                
            # Then check for chart indicators
            chart_indicators = driver.find_elements(By.XPATH,
                f"//svg[contains(., '{element_title}')] | " +
                f"//div[contains(@class, 'chart') and contains(., '{element_title}')] | " +
                f"//div[contains(@class, 'graph') and contains(., '{element_title}')] | " +
                f"//figure[contains(., '{element_title}')]")
            
            driver.quit()
            
            # Decide which function to call based on findings
            if table_indicators and not chart_indicators:
                print(f"Detected '{element_title}' as a table")
                screenshot_table(url, element_title)
            elif chart_indicators and not table_indicators:
                print(f"Detected '{element_title}' as a chart/graph")
                screenshot_chart(url, element_title)
            elif table_indicators and chart_indicators:
                # If we found both, use heuristics to decide
                # Check if the title contains words often used for charts
                chart_keywords = ["chart", "graph", "plot", "figure", "visualization", "trend", "diagram"]
                table_keywords = ["table", "grid", "matrix", "standings", "rankings", "list", "data"]
                
                if any(keyword in element_title.lower() for keyword in chart_keywords):
                    print(f"Title suggests '{element_title}' is a chart/graph")
                    screenshot_chart(url, element_title)
                elif any(keyword in element_title.lower() for keyword in table_keywords):
                    print(f"Title suggests '{element_title}' is a table")
                    screenshot_table(url, element_title)
                else:
                    # Default to screenshot_table if we can't determine
                    print(f"Ambiguous element type, trying table first")
                    screenshot_table(url, element_title)
            else:
                # If we didn't find clear indicators, try table first (more common)
                print(f"No clear element type detected, trying table first")
                screenshot_table(url, element_title)
                
        except Exception as e:
            print(f"Error during auto-detection: {e}")
            driver.quit()
            # Default to screenshot_table as fallback
            print("Using table detection as fallback")
            screenshot_table(url, element_title)

# Modified main to use hardcoded URL and table title
if __name__ == "__main__":
    # Hardcoded example - Wikipedia periodic table (more likely to work in Colab)
    url = "https://www.worldometers.info/world-population/"
    table_title = "World Population by Religion"

    print(f"Capturing screenshot of '{table_title}' from {url}")
    screenshot_element(url, table_title)