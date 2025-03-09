import requests
from bs4 import BeautifulSoup

# Define the arXiv search URL
search_url = "https://arxiv.org/search/?query=ruben+Lier&searchtype=all&source=header"

# Set a User-Agent to prevent blocking
headers = {"User-Agent": "Mozilla/5.0"}

def fetch_arxiv_papers():
    response = requests.get(search_url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to fetch arXiv page: HTTP {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    papers = []
    for result in soup.find_all("li", class_="arxiv-result"):
        title_tag = result.find("p", class_="title is-5 mathjax")
        link_tag = result.find("p", class_="list-title is-inline-block")
        authors_tag = result.find("p", class_="authors")
        date_tag = result.find("p", class_="is-size-7")

        if title_tag and link_tag and authors_tag and date_tag:
            title = title_tag.text.strip()
            link = link_tag.find("a")["href"]
            authors = [a.text.strip() for a in authors_tag.find_all("a")]

            date_text = date_tag.text.strip()
            date_start = date_text.find("Submitted") + len("Submitted ")
            date_end = date_text.find(";")
            submission_date = date_text[date_start:date_end].strip() if date_start != -1 and date_end != -1 else "Unknown"

            papers.append({"title": title, "link": link, "authors": authors, "submission_date": submission_date})

    return papers

def generate_html(papers):
    html_content = """<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>My arXiv Papers</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            h1 { text-align: center; }
            .paper { margin-bottom: 20px; }
            .bold { font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>My Latest arXiv Papers</h1>
    """

    for paper in papers:
        authors_formatted = ", ".join(
            f'<span class="bold">{name}</span>' if name == "Ruben Lier" else name for name in paper["authors"]
        )

        html_content += f"""
        <div class="paper">
            <h2><a href="{paper['link']}">{paper['title']}</a></h2>
            <p><strong>Authors:</strong> {authors_formatted}</p>
            <p><strong>Submitted:</strong> {paper['submission_date']}</p>
        </div>
        <hr>
        """

    html_content += "</body></html>"

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print("✅ Generated index.html successfully!")

if __name__ == "__main__":
    papers = fetch_arxiv_papers()
    generate_html(papers)
