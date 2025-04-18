# amazon_scraper.py
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re # For regex selector
from io import StringIO # Potentially needed if pandas uses it internally

def amazon_tables(url):
    """
    Scrapes the product comparison table from an Amazon product page.

    Args:
        url (str): The URL of the Amazon product page.

    Returns:
        dict: A dictionary containing:
              - 'status': 'success', 'not_found', 'request_error', 'parse_error', 'no_rows', 'empty_df'
              - 'dataframe': pandas DataFrame (if status is 'success')
              - 'html': HTML string of the table (if status is 'success')
              - 'message': Error or status message (if status is not 'success')
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Upgrade-Insecure-Requests': '1',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
    }

    print(f"Requesting Amazon URL: {url}") # Keep print for console feedback
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        print(f"Response Status Code: {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")

        comparison_div = soup.find("div", id="comparison-chart")
        table = comparison_div.find("table") if comparison_div else None
        if not table:
            table = soup.find("table", class_=re.compile(r'_product-comparison-.*comparisonTable'))

        if table:
            print("Comparison table found in HTML.")
            rows_data = []
            table_rows = table.find_all("tr")

            if not table_rows:
                print("Warning: Table element found, but it contains no 'tr' (row) elements.")
                return {'status': 'no_rows', 'message': "Amazon table element found, but it contains no 'tr' (row) elements."}

            print(f"Found {len(table_rows)} 'tr' elements in the table.")
            for tr in table_rows:
                row = []
                for cell in tr.find_all(["td", "th"]):
                    img = cell.find("img")
                    if img:
                        image_url = img.get("data-a-hires") or img.get("src") or ""
                        row.append(f'<img src="{image_url}" style="max-width:50px; max-height:50px;">')
                    else:
                        cell_text = ' '.join(cell.get_text(strip=True).split())
                        row.append(cell_text)
                if row and any(c for c in row if str(c).strip()):
                    rows_data.append(row)

            if not rows_data:
                print("Warning: Table found, but no data rows could be extracted.")
                return {'status': 'no_rows', 'message': "Amazon table found, but no data rows could be extracted."}

            headers_list = []
            header_row_element = table.find("thead")
            if header_row_element:
                header_cells = header_row_element.find_all("th")
                if header_cells:
                    headers_list = [' '.join(th.get_text(strip=True).split()) for th in header_cells]
                    print(f"Extracted headers from thead: {headers_list}")

            df = None
            if rows_data:
                if not headers_list:
                    first_row_cells = rows_data[0]
                    if not any('<img' in str(cell) for cell in first_row_cells) and any(isinstance(cell, str) and cell for cell in first_row_cells):
                        print("Assuming first extracted row is the header.")
                        headers_list = first_row_cells
                        rows_data = rows_data[1:]

                if rows_data:
                    if headers_list and len(headers_list) == len(rows_data[0]):
                        df = pd.DataFrame(rows_data, columns=headers_list)
                    else:
                        print(f"Header count mismatch or headers missing. Creating DF with generic headers.")
                        df = pd.DataFrame(rows_data)
                        df.columns = [f"Column {i+1}" for i in range(df.shape[1])]

            if df is not None and not df.empty:
                print("DataFrame created successfully.")
                html_table = df.to_html(escape=False, index=False, border=1, classes='dataframe table table-striped table-hover')
                return {'status': 'success', 'dataframe': df, 'html': html_table}
            else:
                 print("Could not create a valid DataFrame from the extracted Amazon table data.")
                 return {'status': 'empty_df', 'message': "Could not create a valid DataFrame from the extracted Amazon table data."}
        else:
            print("No comparison table found on the Amazon page using known selectors.")
            return {'status': 'not_found', 'message': "No comparison table found on the Amazon page using known selectors."}

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch the Amazon page. Error: {e}")
        return {'status': 'request_error', 'message': f"Failed to fetch the Amazon page. Error: {e}"}
    except Exception as e:
        print(f"An unexpected error occurred during Amazon table extraction: {e}")
        # Consider logging the full traceback here if needed for debugging
        # import traceback
        # traceback.print_exc()
        return {'status': 'parse_error', 'message': f"An unexpected error occurred during Amazon table extraction: {e}"}