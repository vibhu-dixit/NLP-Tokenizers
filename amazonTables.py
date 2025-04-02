import requests
from bs4 import BeautifulSoup
import pandas as pd
from IPython.display import HTML, display

# Amazon Product URL
url = "https://www.amazon.com/Sony-WH-1000XM4-Canceling-Headphones-Phone-Call/dp/B08MVGF24M/..."
headers = {
    "User-Agent": "Mozilla/5.0 ...",
    "Accept-Language": "en-US,en;q=0.9",
}

# Fetch page content
response = requests.get(url, headers=headers)
if response.status_code == 200:
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", class_="a-bordered a-horizontal-stripes a-spacing-none a-size-small _product-comparison-desktop_desktopFaceoutStyle_comparisonTable__hYFf4")
    if table:
        rows = []
        for tr in table.find_all("tr"):
            row = []
            for cell in tr.find_all(["td", "th"]):
                img = cell.find("img")
                if img:
                    image_url = img.get("data-a-hires") or img.get("src")
                    row.append(f'')
                else:
                    row.append(cell.get_text(strip=True))
            if row:
                rows.append(row)

        df = pd.DataFrame(rows)
        df.columns = [f"Column {i}" for i in range(df.shape[1])]

        csv_filename = "amazon_comparison_table.csv"
        df.to_csv(csv_filename, index=False)
        print(f"Data saved to {csv_filename}")

        html_table = df.to_html(escape=False)
        with open("table.html", "w", encoding="utf-8") as f:
            f.write(html_table)
        print("HTML table saved to table.html")

        display(HTML(html_table))
    else:
        print("Table not found. It may be dynamically loaded via JavaScript.")
else:
    print("Failed to fetch the page. Status Code:", response.status_code)


from tabulate import tabulate

# Check if DataFrame is not empty
if not df.empty:
    # Convert DataFrame to tabulated format
    table_str = tabulate(df, headers='keys', tablefmt='grid')

    # Print the tabulated table
    print(table_str)

    # Save the table to a CSV file
    csv_filename = "amazon_comparison_table.csv"
    df.to_csv(csv_filename, index=False)
    print(f"Data saved successfully to {csv_filename}")
else:
    print("No data available to tabulate.")
     