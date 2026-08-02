"""HTML Cleaning Pipeline — extracts clean text from raw HTML.

Multi-step pipeline:
  1. Remove <script>, <style>, <noscript>, <iframe> blocks
  2. Remove HTML comments <!-- ... -->
  3. Strip all remaining HTML tags
  4. Decode HTML entities
  5. Collapse whitespace
  6. Remove common boilerplate patterns

Optional: BeautifulSoup-based main content extraction for semantic containers.
"""

import re
import html as html_module

# ── Boilerplate patterns to strip ──
BOILERPLATE_PATTERNS = [
    r'\bAccept (all )?cookies\b[^.?!]*[.?!]',
    r'\bCookie (policy|preferences|settings)\b[^.?!]*[.?!]',
    r'\bSkip to (main )?content\b',
    r'\bSubscribe to our newsletter\b[^.?!]*[.?!]',
    r'\bSign up for our\b[^.?!]*[.?!]',
    r'\bPlease enable JavaScript\b[^.?!]*[.?!]',
    r'\bYour browser does not support\b[^.?!]*[.?!]',
    r'\bShare (this|on|via)\b[^.?!]*[.?!]',
    r'\bFollow us on\b[^.?!]*[.?!]',
    r'\bAll rights reserved\b[^.?!]*[.?!]',
    r'\bCopyright ©?\s*\d{4}\b[^.?!]*[.?!]',
]

BLOCK_TAGS_RE = re.compile(
    r'<(script|style|noscript|iframe|svg|nav|footer|header)\b[^>]*>.*?</\1>',
    re.DOTALL | re.IGNORECASE
)

COMMENT_RE = re.compile(r'<!--.*?-->', re.DOTALL)

TAG_RE = re.compile(r'<[^>]+>')

WHITESPACE_RE = re.compile(r'\s+')


def clean_html(raw_html: str) -> str:
    """Full HTML-to-text cleaning pipeline."""
    if not raw_html or not raw_html.strip():
        return ""

    text = raw_html

    # 1. Remove script/style/noscript/iframe/svg blocks
    text = BLOCK_TAGS_RE.sub(' ', text)

    # 2. Remove HTML comments
    text = COMMENT_RE.sub(' ', text)

    # 3. Strip remaining HTML tags
    text = TAG_RE.sub(' ', text)

    # 4. Decode HTML entities (&amp; &#x4E2D; etc.)
    text = html_module.unescape(text)

    # 5. Collapse whitespace
    text = WHITESPACE_RE.sub(' ', text).strip()

    # 6. Remove boilerplate patterns
    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # 7. Clean up any double spaces or orphaned punctuation
    text = WHITESPACE_RE.sub(' ', text).strip()

    return text


def extract_main_content(raw_html: str) -> str:
    """Extract main content from HTML using semantic containers or heuristics.

    Falls back to clean_html() if no semantic container found.
    """
    if not raw_html or not raw_html.strip():
        return ""

    # Try BeautifulSoup first (optional dependency)
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw_html, 'html.parser')

        # Try semantic containers in priority order
        for tag in ['article', 'main', '[role="main"]']:
            container = soup.select_one(tag)
            if container and len(container.get_text(strip=True)) > 200:
                return clean_html(str(container))

        # Heuristic: find the div with highest text-to-tag ratio
        candidates = []
        for div in soup.find_all(['div', 'section']):
            text_len = len(div.get_text(strip=True))
            if text_len < 200:
                continue
            tag_count = len(div.find_all())
            ratio = text_len / max(tag_count, 1)
            candidates.append((ratio, div))

        if candidates:
            candidates.sort(key=lambda x: -x[0])
            best = candidates[0][1]
            return clean_html(str(best))

        # Fallback: clean the whole page
        return clean_html(raw_html)

    except ImportError:
        # BeautifulSoup not installed, use stdlib HTMLParser

        # Try regex-based extraction of semantic containers
        for tag in ['article', 'main']:
            pattern = re.compile(
                rf'<{tag}\b[^>]*>(.*?)</{tag}>',
                re.DOTALL | re.IGNORECASE
            )
            match = pattern.search(raw_html)
            if match:
                content = match.group(1)
                cleaned = clean_html(content)
                if len(cleaned) > 200:
                    return cleaned

        return clean_html(raw_html)


def is_empty_content(text: str, min_chars: int = 100) -> bool:
    """Check if text is effectively empty after cleaning.

    Returns True if the text has fewer than min_chars meaningful characters.
    """
    cleaned = clean_html(text)
    # Strip markdown formatting characters too
    cleaned = re.sub(r'[#*`\-_>|]', '', cleaned)
    cleaned = cleaned.strip()
    return len(cleaned) < min_chars
