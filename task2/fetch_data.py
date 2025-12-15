import asyncio
import aiohttp
import argparse
import async_timeout
import json
import os
import re
import logging
from urllib.parse import urlparse, unquote, quote
from datetime import datetime
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s"
)
log = logging.getLogger("fetch_starwars")

API = "https://starwars.fandom.com/ru/api.php"
BASE_URL = "https://starwars.fandom.com/ru"
OK_HOSTS = {"starwars.fandom.com", "www.starwars.fandom.com"}

# Ключевые сущности Star Wars для поиска
STARWARS_ENTITIES = {
    "characters": [
        "Люк Скайуокер",
        "Дарт Вейдер",
        "Лея Органа",
        "Хан Соло",
        "Оби-Ван Кеноби",
        "Йода",
        "Дарт Сидиус",
        "Боба Фетт",
        "Рей",
        "Кайло Рен",
        "Чубакка",
        "R2-D2",
        "C-3PO"
    ],
    "objects": [
        "Световой меч",
        "Тысячелетний сокол",
        "Кайбер-кристалл",
    ],
    "technologies": [
        "Гипердвигатель",
        "Сила",        
        "Бластер"
    ],
    "events": [
        "Битва при Явине",
        "Битва при Эндоре",
        "Войны клонов",
        "Галактическая гражданская война"
    ]
}

# Маркеры для фильтрации Star Wars контента
STARWARS_MARKERS = [
    "звёздные войны", "джедай", "ситх", "сила", "световой меч",
    "скайуокер", "орден джедаев", "галактическая империя",
    "повстанцы", "республика", "дроид", "штурмовик",
    "звезда смерти", "тысячелетний сокол", "медхут",
    "мандалорец", "боба фетт", "кибер-кристалл"
]

MIN_STARWARS_MARKERS = 2

# Заголовки для обрезки контента
CUTOFF_HEADINGS = {
    "источники",
    "появления",
    "примечания",
    "ссылки",
    "внешние ссылки",
    "навигация",
    "см. также",
    "галерея",
    "трейлеры",
    "видео",
    "кулуарная информация",
    "за кадром",
    "факты",
    "транскрипты",
    "литература",
    "библиография",
    "шаблоны",
    "темы сообщества",
    "сообщество",
    "обсуждение",
    "история изменений",
    "категории",
    "категория",
    "комментарии",
    "комменты",
    "дополнительная информация",
    "источники и примечания",
    "примечания и ссылки",
    "игровые параметры",
    "характеристики",
    "за кадром",
    "в культуре",
    "официальная информация",
    "неканоничные сведения",
    "канон",
    "легенды",
    "навигация по страницам",
    "навигация по вселенной",
    "хронология",
    "публикации",
    "дата выхода",
    "авторы",
    "пародии",
    "озвучивание",
    "анимация",
    "за кулисами"
}

REFNUM_RE = re.compile(r"\s*\[\d{1,3}\]")
WS_RE = re.compile(r"[ \t]+")
BLANKS_RE = re.compile(r"\n{3,}")
PUNCT_SPACE = re.compile(r"\s+([,.;:!?])")

# Lines like "↑ ..." (optionally with a bullet before)
UP_ARROW_LINE_RE = re.compile(r"(?m)^\s*(?:[-–—]\s*)?↑.*(?:\n|$)")

# Tighten quotes and parentheses spacing
OPEN_QUOTE_SPACE_RE = re.compile(r"«\s+")
CLOSE_QUOTE_SPACE_RE = re.compile(r"\s+»")
OPEN_PAREN_SPACE_RE = re.compile(r"\(\s+")
CLOSE_PAREN_SPACE_RE = re.compile(r"\s+\)")
CLOSE_PUNCT_SPACE_RE = re.compile(r"\s+([\)\]\»])")


def make_headers(ua):
    """Build HTTP headers for Star Wars Fandom requests."""
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }


def seed_to_title(seed_url: str) -> str:
    """Extract and decode the page title from a seed URL."""
    p = urlparse(seed_url.strip())
    if p.netloc not in OK_HOSTS or not p.path.startswith("/ru/wiki/"):
        raise ValueError(f"Not a Star Wars Fandom RU URL: {seed_url}")
    title = p.path[len("/ru/wiki/"):].split("#", 1)[0]
    return unquote(title)


def slugify(title: str) -> str:
    """Create a filesystem-safe slug from a page title."""
    name = title.replace("/", "／")
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^\w\-\s]", "", name)
    return name[:100]


def normkey(s: str) -> str:
    """Normalize strings for comparison."""
    s = s.replace("_", " ").strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r"[^\w\s\-]", " ", s, flags=re.U)
    s = re.sub(r"\s+", " ", s)
    return s


async def api(session, **params):
    """Call the Star Wars Fandom API and decode the JSON payload."""
    async with session.get(API, params=params) as r:
        txt = await r.text()
        if r.status != 200:
            raise aiohttp.ClientResponseError(
                r.request_info, r.history, status=r.status, message=txt[:200]
            )
        try:
            return json.loads(txt)
        except Exception:
            raise RuntimeError(f"Non-JSON response for params={params}: {txt[:200]}")


async def resolve_page(session, title: str):
    """Resolve a title to a main namespace page."""
    params = dict(
        action="query", 
        format="json", 
        formatversion=2, 
        redirects=1, 
        titles=title, 
        prop="info", 
        inprop="url"
    )
    data = await api(session, **params)
    pages = (data.get("query") or {}).get("pages") or []
    if not pages:
        return None
    page = pages[0]
    if page.get("missing") or page.get("invalid"):
        return None
    return {"pageid": page.get("pageid"), "title": page.get("title")}


def strip_fandom_chrome(soup: BeautifulSoup):
    """Remove navigation, infoboxes and other Fandom-specific chrome."""
    for sel in [
        ".navbox", ".infobox", ".metadata", ".edit-link",
        ".references", ".quote", ".notice", ".toc",
        ".wikia-gallery", ".portable-infobox", ".pi-background",
        ".shared-uploads", ".page-footer", ".page-header",
        ".wds-global-navigation", ".fandom-community-header"
    ]:
        for tag in soup.select(sel):
            tag.decompose()


def html_to_text(html: str):
    """Convert article HTML into clean text with Markdown-style headings."""
    soup = BeautifulSoup(html, "lxml")
    strip_fandom_chrome(soup)

    def norm(t: str) -> str:
        return re.sub(r"[ \t]+", " ", t).strip()

    lines = []
    paras = 0
    lists = 0

    # Основной контент
    content = soup.select_one(".mw-parser-output, .page-content, #content")
    if not content:
        return "", {"paras": 0, "list_items": 0, "chars": 0}

    current_heading = None
    current_block = []

    def flush_block():
        nonlocal current_heading, current_block, lines
        if current_heading is not None:
            body = "\n".join([b for b in current_block if b.strip()]).strip()
            if body:
                lines.append(current_heading)
                lines.append(body)
        current_heading, current_block = None, []

    for tag in content.find_all(["h1", "h2", "h3", "h4", "p", "ul", "ol"], recursive=True):
        if tag.name in ("h1", "h2", "h3", "h4"):
            htxt = norm(tag.get_text(" "))
            hclean = re.sub(r"\[.*?\]", "", htxt).strip().lower()
            if hclean in CUTOFF_HEADINGS:
                break
            flush_block()
            level = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}[tag.name]
            current_heading = f"{level} {hclean.strip().capitalize()}"
        elif tag.name == "p":
            txt = norm(tag.get_text(" "))
            if txt and len(txt) > 20:
                current_block.append(txt)
                paras += 1
        elif tag.name in ("ul", "ol"):
            items = [norm(li.get_text(" ")) for li in tag.find_all("li", recursive=False)]
            items = [f"- {it}" for it in items if it]
            if items:
                current_block.append("\n".join(items))
                lists += len(items)
    
    flush_block()

    text = "\n\n".join([ln for ln in lines if ln.strip()])
 
    text = normalize_text(text)

    stats = {"paras": paras, "list_items": lists, "chars": len(text)}
    return text, stats


def looks_like_stub(text: str, stats: dict) -> bool:
    """Heuristic to detect stub pages."""
    return stats.get("paras", 0) < 2 and stats.get("chars", 0) < 500


def strip_empty_headings(text: str) -> str:
    """Drop headings that are followed only by blank lines."""
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^(##|###|####)\s+\S", line):
            j = i + 1
            buf = []
            while j < len(lines) and not re.match(r"^(##|###|####)\s+\S", lines[j]):
                buf.append(lines[j])
                j += 1
            if any(x.strip() for x in buf):
                out.append(line)
                out.extend(buf)
            i = j
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def normalize_text(text: str) -> str:
    """Apply typography fixes, strip references and compact whitespace."""

    # typographic fixes
    text = text.replace("\u00a0", " ")  # NBSP -> space
    text = text.replace("➤", "")  # nav arrows
    text = PUNCT_SPACE.sub(r"\1", text)  # tighten spaces before punctuation

    # content cleanup
    text = REFNUM_RE.sub("", text)  # drop [1] style refs

    # cosmetic cleanup
    text = UP_ARROW_LINE_RE.sub("", text)
    text = OPEN_QUOTE_SPACE_RE.sub("«", text)
    text = CLOSE_QUOTE_SPACE_RE.sub("»", text)
    text = OPEN_PAREN_SPACE_RE.sub("(", text)
    text = CLOSE_PAREN_SPACE_RE.sub(")", text)
    text = CLOSE_PUNCT_SPACE_RE.sub(r"\1", text)

    # whitespace compaction
    text = WS_RE.sub(" ", text)
    text = BLANKS_RE.sub("\n\n", text)
    text = text.strip()
    text = strip_empty_headings(text)

    text = text.replace("\r\n", "\n")
    text = re.sub(r"\s*\[\d{1,3}\]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)           # убираем пробелы перед \n
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\[\s*?\d*?\s*?\]", "", text).strip()

    return text


async def fetch_html(session, title: str):
    """Fetch raw HTML for a Star Wars Fandom page."""
    params = dict(action="parse", page=title, prop="text", format="json", formatversion=2, redirects=1)
    data = await api(session, **params)
    parse = data.get("parse") or {}
    html = parse.get("text") or ""
    if isinstance(html, dict):
        html = html.get("*", "")
    if not html:
        raise RuntimeError("Empty HTML from parse API")
    return html


async def fetch_one(session, seed_url, out_dir):
    """Process a single seed URL and persist the cleaned text."""
    seed_title = None
    try:
        seed_title = seed_to_title(seed_url)
    except Exception as e:
        return {"seed": seed_url, "status": f"bad_seed:{e}"}

    page = await resolve_page(session, seed_title)
    if not page:
        return {"seed": seed_url, "status": "resolve_failed"}
    canonical = page["title"]
    pageid = page["pageid"]

    try:
        async with async_timeout.timeout(30):
            html = await fetch_html(session, canonical)
    except Exception as e:
        return {"seed": seed_url, "canonical": canonical, "pageid": pageid, "status": f"fetch_html_error:{e}"}

    text, stats = html_to_text(html)
    
    if looks_like_stub(text, stats):
        return {"seed": seed_url, "canonical": canonical, "pageid": pageid, "status": "stub_page"}

    if len(text.split()) < 100 or stats["chars"] < 800:
        return {"seed": seed_url, "canonical": canonical, "pageid": pageid, "status": "too_short"}

    # Проверяем релевантность Star Wars
    low = text.lower()
    if sum(1 for m in STARWARS_MARKERS if m in low) < MIN_STARWARS_MARKERS:
        return {"seed": seed_url, "canonical": canonical, "pageid": pageid, "status": "not_starwars"}

    # Сохраняем в формате базы знаний
    out_name = slugify(canonical) + ".md"
    out_path = os.path.join(out_dir, out_name)
    
    # Форматируем как базу знаний
    kb_content = f"""# {canonical}

{text}
"""
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(kb_content)

    res = {"seed": seed_url, "canonical": canonical, "pageid": pageid, "status": "ok", "path": out_path, "stats": stats}
    return res


async def generate_seeds(out_dir: str):
    """Generate seed URLs by searching for entities."""
    seeds = []
    for category, entities in STARWARS_ENTITIES.items():
        for entity in entities:
            title = quote(entity.replace(" ", "_"))
            page_url = f"{BASE_URL}/wiki/{title}"
            seeds.append(page_url)

    seeds_file = os.path.join(out_dir, "_seeds.txt")
    with open(seeds_file, "w", encoding="utf-8") as f:
        for seed in seeds:
            f.write(seed + "\n")
    
    return seeds


async def run(out_dir, concurrency, user_agent):
    """Entry point for fetching Star Wars knowledge base."""
    os.makedirs(out_dir, exist_ok=True)
    
    # Генерируем seed URLs
    log.info("Generating seed URLs...")
    seeds = await generate_seeds(out_dir)
    log.info(f"Generated {len(seeds)} seed URLs")
    
    timeout = aiohttp.ClientTimeout(total=120)
    headers = make_headers(user_agent)
    connector = aiohttp.TCPConnector(limit=concurrency, limit_per_host=concurrency)
    sem = asyncio.Semaphore(concurrency)

    async with aiohttp.ClientSession(headers=headers, timeout=timeout, connector=connector, trust_env=True) as session:

        async def bounded(u):
            async with sem:
                try:
                    return await fetch_one(session, u, out_dir)
                except Exception as e:
                    return {"seed": u, "status": f"fatal:{e}"}

        tasks = [asyncio.create_task(bounded(u)) for u in seeds]
        results = []
        for fut in asyncio.as_completed(tasks):
            result = await fut
            results.append(result)
            if result.get("status") == "ok":
                log.info(f"✓ {result['canonical']}")
            else:
                log.warning(f"✗ {result['seed']} - {result['status']}")

    # Сохраняем отчет
    with open(os.path.join(out_dir, "_fetch_report.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    ok = len([r for r in results if r.get("status") == "ok"])
    log.info("ok=%d total=%d", ok, len(results))
    
    return 0 if ok >= 30 else 1


def main():
    """Parse CLI arguments and launch the fetch pipeline."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output directory", default="raw")
    ap.add_argument("--concurrency", type=int, default=5, help="Number of concurrent requests")
    ap.add_argument("--ua", type=str, default="StarWars-Knowledge-Base-RU/1.0", help="User-Agent string")
    
    args = ap.parse_args()
    
    return asyncio.run(run(args.out, args.concurrency, args.ua))


if __name__ == "__main__":
    raise SystemExit(main())