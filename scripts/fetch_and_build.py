import feedparser
import google.generativeai as genai
import os
import json
from datetime import datetime, timezone, timedelta

# ─── Config ───────────────────────────────────────────────
THAI_TZ = timezone(timedelta(hours=7))
TODAY = datetime.now(THAI_TZ).strftime("%Y-%m-%d")
DISPLAY_DATE = datetime.now(THAI_TZ).strftime("%d %B %Y")

RSS_FEEDS = {
    "Droidsan":      "https://www.droidsan.com/feed/",
    "NotebookSpec":  "https://www.notebookspec.com/web/feed/",
    "TechTalkThai":  "https://www.techtalkthai.com/feed/",
    "Blognone":      "https://www.blognone.com/node/feed",
    "Thaiware":      "https://thaiware.com/rss/rss_latestProducts.xml",
    "Siamphone":     "https://www.siamphone.com/feed/",
}

MAX_PER_FEED = 10  # ดึงสูงสุด 10 ข่าวต่อเว็บ

# ─── Gemini Setup ──────────────────────────────────────────
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

# ─── Step 1: ดึงข่าวจาก RSS ────────────────────────────────
def fetch_news():
    all_news = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries:
            if count >= MAX_PER_FEED:
                break
            # กรองเฉพาะข่าวใน 24 ชม. (ถ้า feed มี published date)
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if pub < cutoff:
                    continue
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "")[:300].strip()
            link = entry.get("link", "")
            if title:
                all_news.append({
                    "source": source,
                    "title": title,
                    "summary": summary,
                    "link": link
                })
                count += 1

    return all_news

# ─── Step 2: สรุปด้วย Gemini ───────────────────────────────
def summarize_with_ai(news_list):
    if not news_list:
        return []

    news_text = "\n".join([
        f"[{i+1}] ({item['source']}) {item['title']} — {item['summary']}"
        for i, item in enumerate(news_list)
    ])

    prompt = f"""คุณคือบรรณาธิการข่าว IT ภาษาไทย

ข้อมูลข่าวดิบต่อไปนี้มาจากเว็บข่าว IT ไทยหลายแหล่ง:

{news_text}

งานของคุณ:
1. รวมข่าวที่มีเนื้อหาคล้ายหรือซ้ำกันให้เป็นข่าวเดียว
2. สรุปแต่ละข่าว 2-3 ประโยค ภาษาไทยที่อ่านง่าย
3. ตั้งหัวข่าวใหม่ที่กระชับและน่าสนใจ
4. ระบุแหล่งข่าวทั้งหมดที่เกี่ยวข้อง
5. คืนค่าเป็น JSON array เท่านั้น ห้ามมี text อื่น

Format JSON ที่ต้องการ:
[
  {{
    "headline": "หัวข่าว",
    "summary": "สรุป 2-3 ประโยค",
    "sources": ["Source1", "Source2"],
    "links": ["url1", "url2"],
    "category": "หมวดหมู่ เช่น Mobile, AI, Security, Gadget, Software"
  }}
]"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    # ลบ markdown backticks ถ้ามี
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    return json.loads(text)

# ─── Step 3: สร้าง HTML ────────────────────────────────────
def build_html(articles, date_str, display_date):
    cards = ""
    category_colors = {
        "Mobile":   "#3b82f6",
        "AI":       "#8b5cf6",
        "Security": "#ef4444",
        "Gadget":   "#f59e0b",
        "Software": "#10b981",
        "Other":    "#6b7280",
    }

    for art in articles:
        color = category_colors.get(art.get("category", "Other"), "#6b7280")
        sources_html = " · ".join(art.get("sources", []))
        links = art.get("links", [])
        link_html = ""
        for i, src in enumerate(art.get("sources", [])):
            if i < len(links):
                link_html += f'<a href="{links[i]}" target="_blank">{src}</a> '

        cards += f"""
        <div class="card">
            <span class="category" style="background:{color}">{art.get('category','Other')}</span>
            <h2>{art.get('headline','')}</h2>
            <p>{art.get('summary','')}</p>
            <div class="sources">🔗 {link_html}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IT News Digest — {display_date}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #f1f5f9; color: #1e293b; }}
  header {{ background: #0f172a; color: white; padding: 24px 32px; }}
  header h1 {{ font-size: 1.5rem; font-weight: 700; }}
  header p {{ color: #94a3b8; margin-top: 4px; font-size: 0.9rem; }}
  nav {{ background: white; padding: 12px 32px; border-bottom: 1px solid #e2e8f0; }}
  nav a {{ color: #3b82f6; text-decoration: none; margin-right: 16px; font-size: 0.9rem; }}
  .container {{ max-width: 860px; margin: 32px auto; padding: 0 16px; }}
  .card {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px;
           box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .category {{ display: inline-block; color: white; font-size: 0.72rem; font-weight: 600;
               padding: 3px 10px; border-radius: 20px; margin-bottom: 10px; }}
  h2 {{ font-size: 1.1rem; line-height: 1.5; margin-bottom: 10px; }}
  p {{ color: #475569; line-height: 1.75; font-size: 0.95rem; }}
  .sources {{ margin-top: 14px; font-size: 0.82rem; color: #94a3b8; }}
  .sources a {{ color: #3b82f6; text-decoration: none; margin-right: 8px; }}
  footer {{ text-align: center; padding: 32px; color: #94a3b8; font-size: 0.8rem; }}
</style>
</head>
<body>
<header>
  <h1>📰 IT News Digest</h1>
  <p>สรุปข่าว IT รายวัน — {display_date}</p>
</header>
<nav>
  <a href="index.html">🏠 วันนี้</a>
  <a href="archive.html">📅 ย้อนหลัง</a>
</nav>
<div class="container">
  {cards}
</div>
<footer>สรุปโดย Gemini AI · ดึงข้อมูลจาก Droidsan, NotebookSpec, TechTalkThai, Blognone, Thaiware, Siamphone</footer>
</body>
</html>"""
    return html

# ─── Step 4: อัปเดต Archive ────────────────────────────────
def update_archive(date_str, display_date, article_count):
    archive_path = "docs/archive.html"
    entry = f'<li><a href="{date_str}.html">{display_date}</a> — {article_count} ข่าว</li>\n'

    if os.path.exists(archive_path):
        with open(archive_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("<!-- ENTRIES -->", f"{entry}<!-- ENTRIES -->")
    else:
        content = f"""<!DOCTYPE html>
<html lang="th"><head><meta charset="UTF-8"><title>Archive</title>
<style>body{{font-family:'Segoe UI',sans-serif;max-width:600px;margin:40px auto;padding:0 16px}}
h1{{margin-bottom:24px}}li{{margin-bottom:8px}}a{{color:#3b82f6}}</style>
</head><body>
<h1>📅 IT News Archive</h1>
<ul>
{entry}<!-- ENTRIES -->
</ul>
</body></html>"""

    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(content)

# ─── Main ──────────────────────────────────────────────────
def main():
    os.makedirs("docs", exist_ok=True)

    print(f"📡 ดึงข่าว RSS ({TODAY})...")
    raw_news = fetch_news()
    print(f"   ได้ {len(raw_news)} ข่าว raw")

    print("🤖 ส่งให้ Gemini สรุป...")
    articles = summarize_with_ai(raw_news)
    print(f"   สรุปเหลือ {len(articles)} ข่าว")

    print("🏗 สร้าง HTML...")
    html = build_html(articles, TODAY, DISPLAY_DATE)

    # บันทึกหน้าวันนี้
    with open(f"docs/{TODAY}.html", "w", encoding="utf-8") as f:
        f.write(html)

    # อัปเดต index.html (หน้าหลัก)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    # อัปเดต archive
    update_archive(TODAY, DISPLAY_DATE, len(articles))

    print(f"✅ เสร็จแล้ว — {len(articles)} ข่าว → docs/{TODAY}.html")

if __name__ == "__main__":
    main()
