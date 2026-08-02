"""Transcription Cleaning Pipeline — clean raw YouTube/WAV transcripts.

Steps:
  1. Remove timestamp lines (HH:MM:SS, MM:SS, etc.)
  2. Remove speaker labels ([Speaker A], [Interviewer], etc.)
  3. Remove caption artifacts ([Music], [Applause], [Laughter], etc.)
  4. Deduplicate repeated lines (common in auto-captions)
  5. Merge short fragmented lines (< 30 chars) into paragraphs
  6. Filter standalone filler words
  7. Segment into paragraphs by sentence boundaries
"""

import re

# ── Patterns ──
TIMESTAMP_RE = re.compile(
    r'\b\d{1,3}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?\b'
)

SPEAKER_LABEL_RE = re.compile(
    r'^\[([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\]'
)

CAPTION_ARTIFACT_RE = re.compile(
    r'\[(?:Music|Applause|Laughter|Cheering|Silence|Noise|Phone\s+Ringing'
    r'|Background\s+Noise|Inaudible|Crosstalk|Speaking\s+Foreign\s+Language)\]',
    re.IGNORECASE
)

# Standalone filler words to filter (only when appearing as isolated segments)
FILLER_WORDS = {
    'um', 'uh', 'er', 'ah', 'hmm', 'mmm', 'eh', 'huh',
    'you know', 'i mean', 'like', 'so', 'basically', 'actually',
    'literally', 'right', 'okay', 'well', 'anyway', 'sort of',
}

REPEATED_LINE_THRESHOLD = 0.85  # Jaccard similarity for duplicate detection


def _jaccard_similarity(a: str, b: str) -> float:
    """Simple word-level Jaccard similarity for duplicate detection."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def clean_transcript(raw_text: str, source: str = "youtube") -> str:
    """Clean a raw transcript into readable paragraphs.

    Args:
        raw_text: Raw transcript text (from youtube-transcript-api or Whisper)
        source: Source type — "youtube" for auto-captions, "whisper" for Whisper output

    Returns:
        Cleaned, segmented transcript text
    """
    if not raw_text or not raw_text.strip():
        return ""

    lines = raw_text.strip().split('\n')

    # ── Step 1: Process each line ──
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Remove timestamps
        line = TIMESTAMP_RE.sub('', line)

        # Remove speaker labels
        line = SPEAKER_LABEL_RE.sub('', line)

        # Remove caption artifacts
        line = CAPTION_ARTIFACT_RE.sub('', line)

        # Clean up whitespace
        line = re.sub(r'\s+', ' ', line).strip()

        if line:
            cleaned_lines.append(line)

    if not cleaned_lines:
        return ""

    # ── Step 2: Deduplicate ──
    deduped = []
    for line in cleaned_lines:
        is_dup = False
        for prev in deduped[-3:]:  # Check last 3 lines
            if _jaccard_similarity(line, prev) > REPEATED_LINE_THRESHOLD:
                is_dup = True
                break
        if not is_dup:
            deduped.append(line)

    # ── Step 3: Merge short fragments into paragraphs ──
    merged = []
    buffer = ""

    for line in deduped:
        # Filter standalone filler words
        if line.lower().strip(".,!?;:") in FILLER_WORDS:
            continue

        if len(line) < 30 and not line.rstrip().endswith(('.', '!', '?', ':', '"', ')', ']')):
            # Short fragment — accumulate
            if buffer:
                buffer += ' ' + line
            else:
                buffer = line
        else:
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(line)

    if buffer:
        merged.append(buffer)

    # ── Step 4: Segment into paragraphs ──
    paragraphs = []
    para_buffer = ""
    char_count = 0

    for line in merged:
        if para_buffer:
            para_buffer += ' ' + line
        else:
            para_buffer = line

        char_count += len(line)

        # Break into paragraphs at sentence boundaries or every ~300 chars
        if line.rstrip().endswith(('.', '!', '?', '"', ')', ']')) and char_count > 150:
            paragraphs.append(para_buffer)
            para_buffer = ""
            char_count = 0
        elif char_count > 350:
            paragraphs.append(para_buffer)
            para_buffer = ""
            char_count = 0
        elif line.rstrip().endswith(('.', '!', '?')) and len(para_buffer) > 80:
            paragraphs.append(para_buffer)
            para_buffer = ""
            char_count = 0

    if para_buffer:
        paragraphs.append(para_buffer)

    return '\n\n'.join(paragraphs)


def parse_srt(raw_srt: str) -> str:
    """Parse SRT subtitle content into plain text."""
    if not raw_srt:
        return ""

    # Remove SRT index numbers and timestamps
    lines = raw_srt.strip().split('\n')
    text_lines = []

    for line in lines:
        line = line.strip()
        # Skip index numbers (pure digits)
        if line.isdigit():
            continue
        # Skip timestamp lines (contain -->)
        if '-->' in line:
            continue
        # Skip empty lines
        if not line:
            continue
        # Remove HTML tags from subtitle text
        line = re.sub(r'<[^>]+>', '', line)
        if line:
            text_lines.append(line)

    return ' '.join(text_lines)
