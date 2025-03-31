import requests
from bs4 import BeautifulSoup
from collections import defaultdict

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

            # Extract submission date
            date_text = date_tag.text.strip()
            date_start = date_text.find("Submitted") + len("Submitted ")
            date_end = date_text.find(";")
            submission_date = date_text[date_start:date_end].strip() if date_start != -1 and date_end != -1 else "Unknown"
            
            # Extract year
            year = submission_date.split()[-1] if submission_date != "Unknown" else "Unknown"

            papers.append({
                "title": title,
                "link": link,
                "authors": authors,
                "submission_date": submission_date,
                "year": year
            })

    return papers

def generate_html(papers):
    # Group papers by year
    papers_by_year = defaultdict(list)
    for paper in papers:
        papers_by_year[paper["year"]].append(paper)

    # Sort years (newest first)
    sorted_years = sorted(papers_by_year.keys(), reverse=True)

    html_content = """<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>My arXiv Papers</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; background-color: #fff; color: #333; }
            .navbar { display: flex; align-items: center; padding: 10px 20px; border-bottom: 1px solid #ccc; justify-content: flex-start; }
            .navbar a { text-decoration: none; color: #333; font-size: 1em; margin-right: 20px; }
            .navbar a:nth-child(2) {font-weight: bold; /* Highlight 'Papers' */   }
            .navbar a:hover { text-decoration: underline; }
            .layout { display: flex; height: calc(100vh - 60px); }
            .sidebar { width: 250px; border-right: 1px solid #ccc; padding: 20px; }
            .sidebar img { width: 100%; margin-bottom: 20px; }
            .social-links { list-style: none; padding: 0; }
            .social-links li { margin-bottom: 15px; }
            .social-links a { display: flex; align-items: center; text-decoration: none; color: #333; }
            .social-links a img { width: 14px; height: 14px; margin-right: 10px; position: relative; top: 10px; }
            .content { flex: 1; padding: 20px; }
            .content h1 { font-size: 2em; margin-bottom: 10px; text-align: center; }
            .content h2 { font-size: 1.5em; margin-top: 20px; border-bottom: 2px solid #ccc; padding-bottom: 5px; }
            .paper { margin-bottom: 20px; }
            .bold { font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="navbar">
            <div style="margin-left: 250px;">
                <a href="index.html">Ruben Lier</a>
                <a href="#">Papers</a>
                <a href="talks.html">Talks</a>
            </div>
        </div>
        <div class="layout">
            <div class="sidebar">
                <img src="foto save ruben.PNG" alt="Ruben's Picture">
                <ul class="social-links">
                    <li><a href="                https://www.uva.nl/en/profile/l/i/r.lier/r.lier.html" target="_blank">
                    <img src="uvalogo.png" alt="Contact"><span>Contact</span></a>
                </li>
                     <li><a href="https://scholar.google.com/citations?user=jN3gPNkAAAAJ&hl=nl" target="_blank">
                    <img src="scholarlogo.png" alt="Google Scholar"><span>Google Scholar</span></a>
                </li>
                <li><a href="https://nl.linkedin.com/in/ruben-lier-b228b2182" target="_blank">
                    <img src="https://upload.wikimedia.org/wikipedia/commons/c/ca/LinkedIn_logo_initials.png" alt="LinkedIn"><span>LinkedIn</span></a>
                </li>
                <li><a href="https://www.goodreads.com/user/show/131725587-ruben-lier" target="_blank">
                    <img src="goodreads.png" alt="Goodreads"><span>Goodreads</span></a>
                </li>
                 <li><a href="https://github.com/rubenlier" target="_blank">
                    <img src="https://upload.wikimedia.org/wikipedia/commons/c/c2/GitHub_Invertocat_Logo.svg" alt="GitHub"><span>GitHub</span></a>
                </li>
                 <li><a href="https://open.spotify.com/playlist/4nSMm8TaDVlrNi4u9rzImQ" target="_blank">
                    <img src="spotify.png" alt="Spotify"><span>Spotify</span></a>
                    </li>
                </ul>
            </div>
            <div class="content">
                <h1>My Latest arXiv Papers</h1>
    """

    for year in sorted_years:
        html_content += f"<h2>{year}</h2>\n"
        for paper in papers_by_year[year]:
            authors_formatted = ", ".join(
                f'<span class="bold">{name}</span>' if name == "Ruben Lier" else name for name in paper["authors"]
            )

            html_content += f"""
            <div class="paper">
                <h3><a href="{paper['link']}">{paper['title']}</a></h3>
                <p><strong>Authors:</strong> {authors_formatted}</p>
                <p><strong>Submitted:</strong> {paper['submission_date']}</p>
            </div>
            <hr>
            """

    # Remove the extra closing tags to prevent the grey bar
    html_content += """
            </div>
        </div>
    """

    with open("paper.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print("✅ Generated paper.html successfully!")

if __name__ == "__main__":
    papers = fetch_arxiv_papers()
    generate_html(papers)
