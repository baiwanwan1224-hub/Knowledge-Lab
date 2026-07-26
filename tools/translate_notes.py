"""Translate PM skill notes from English to Chinese via 4SAPI GPT-4.1."""
import os, re, json, time

VAULT = r'C:\Users\27224\Documents\Obsidian Vault\Knowledge Lab\00_学习笔记'
API_KEY = 'sk-LDfhGhOrU79TuCKyhinRUqfExxQNMOp2kbLRlx3QPjtciTpb'
API_URL = 'https://4sapi.com/v1/chat/completions'

def translate(text):
    """Send English text to GPT-4.1 for Chinese translation."""
    prompt = f"""Translate the following English text to professional Chinese.
Preserve all markdown formatting, headings, bullet points, and structure.
Keep technical terms in English with Chinese explanation in parentheses on first use.
Output ONLY the Chinese translation, no explanations.

English text:
{text[:4000]}"""

    for attempt in range(3):
        try:
            resp = __import__('requests').post(API_URL,
                headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
                json={'model': 'gpt-4.1', 'messages': [{'role': 'user', 'content': prompt}],
                      'max_tokens': 4000, 'temperature': 0.2}, timeout=120)
            if resp.status_code == 200:
                return resp.json()['choices'][0]['message']['content'].strip()
            elif resp.status_code == 429:
                time.sleep(5 * (attempt + 1))
            else:
                print(f'  API error: {resp.status_code}')
                return None
        except Exception as e:
            print(f'  Request failed: {str(e)[:80]}')
            time.sleep(3)
    return None


def main():
    files = sorted([f for f in os.listdir(VAULT) if f.startswith('2026-07-26_PM_')])
    total = len(files)
    print(f'Found {total} PM skill notes to translate\n')

    success = 0; skip = 0; fail = 0
    for i, fname in enumerate(files):
        fpath = os.path.join(VAULT, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Skip if already bilingual
        if '## 中文翻译' in content or '---\n\n## 中文' in content:
            skip += 1; continue

        # Extract body (after YAML frontmatter)
        parts = content.split('---', 2)
        if len(parts) < 3:
            skip += 1; continue

        frontmatter = parts[1]
        body = parts[2].strip()

        # Skip if body is mostly Chinese already
        chinese_chars = sum(1 for c in body if '\u4e00' <= c <= '\u9fff')
        if chinese_chars > len(body) * 0.3:
            skip += 1; continue

        # Translate
        print(f'[{i+1}/{total}] Translating: {fname[:60]}')
        chinese = translate(body)

        if chinese and len(chinese) > 50:
            # Build bilingual note
            new_content = f'---\n{frontmatter}\n---\n\n{body}\n\n---\n\n## 中文翻译\n\n{chinese}\n'
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            success += 1
        else:
            fail += 1
            print(f'  FAILED: translation too short or API error')

        # Rate limit: 1 request per 2 seconds
        time.sleep(2)

    print(f'\nDone: {success} translated, {skip} skipped, {fail} failed')

if __name__ == '__main__':
    main()
