from bs4 import BeautifulSoup
import json

# Load HTML file
with open("publications.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

publications = {}

for section in soup.find_all("h3"):
    section_name = section.get_text(strip=True)
    publications[section_name] = []

    ul = section.find_next_sibling("ul")
    if not ul:
        continue

    for li in ul.find_all("li", recursive=False):
        year_span = li.find("span", class_="year")
        year = year_span.get_text(strip=True) if year_span else None

        authors = li.find("span", class_="authors")
        title = li.find("span", class_="title")
        journal = li.find("span", class_="journal")
        sci_info = li.find("span", class_="sci-info")
        award = li.find("span", class_="award")

        entry = {
            "year": int(year) if year and year.isdigit() else year,
            "authors": authors.get_text(strip=True).split(", ") if authors else [],
            "title": title.get_text(strip=True).strip('"') if title else None,
            "journal": journal.get_text(strip=True) if journal else None,
            "sci_info": sci_info.get_text(strip=True) if sci_info else None,
            "award": award.get_text(strip=True) if award else None
        }

        publications[section_name].append(entry)

# Save JSON
with open("publications.json", "w", encoding="utf-8") as f:
    json.dump(publications, f, indent=2, ensure_ascii=False)

print("✅ Publications saved to publications.json")
