import re
from pathlib import Path

QUALITY = re.compile(
    r'(?i)(?<![a-z0-9])'
    r'(2160p|1440p|1080p|900p|720p|576p|540p|480p|360p|4k)'
    r'(?![a-z0-9])'
)

LANGUAGE = re.compile(
    r'(?i)(?<![a-z])'
    r'(malayalam|english|hindi|tamil|telugu|kannada|'
    r'bengali|marathi|punjabi|multi[\s._-]*audio)'
    r'(?![a-z])'
)

SE = re.compile(
    r'(?i)\bS(?:eason)?[\s._-]*(\d{1,2})'
    r'[\s._-]*E(?:pisode)?[\s._-]*(\d{1,3})\b'
)

SEASON = re.compile(
    r'(?i)\b(?:Season|S)[\s._-]*(\d{1,2})\b'
)

EPISODE = re.compile(
    r'(?i)\b(?:Episode|E)[\s._-]*(\d{1,3})\b'
)

YEAR = re.compile(r'\b(?:19|20)\d{2}\b')

TECH = re.compile(
    r'(?i)\b(?:HDRip|WEBRip|WEB[\s._-]*DL|'
    r'BluRay|BDRip|DVDRip|HEVC|AVC|'
    r'x264|x265|H264|H265|AAC|DDP?|'
    r'NF|AMZN|HQ|10bit|8bit|'
    r'ESub|ESubs|Dual[\s._-]*Audio)\b'
)


def parse_name(name):
    filename = Path(name or "Unknown").name
    stem = re.sub(
        r'(?i)\.(mkv|mp4|avi|mov|webm|m4v)$',
        '',
        filename
    )

    normalized = re.sub(r'[._]+', ' ', stem)

    se = SE.search(normalized)
    season = int(se.group(1)) if se else None
    episode = int(se.group(2)) if se else None

    if season is None:
        match = SEASON.search(normalized)
        season = int(match.group(1)) if match else None

    if episode is None:
        match = EPISODE.search(normalized)
        episode = int(match.group(1)) if match else None

    quality_match = QUALITY.search(normalized)
    language_match = LANGUAGE.search(normalized)

    quality = (
        quality_match.group(1).upper()
        if quality_match else None
    )

    language = (
        language_match.group(1).title()
        if language_match else None
    )

    is_series = season is not None or episode is not None

    # For series, the title normally precedes S01E01.
    if is_series:
        markers = [
            m.start() for m in (
                SE.search(normalized),
                SEASON.search(normalized),
                EPISODE.search(normalized)
            ) if m
        ]
        title = normalized[:min(markers)] if markers else normalized
    else:
        # For movies, remove release information after title.
        markers = [
            m.start() for m in (
                YEAR.search(normalized),
                QUALITY.search(normalized),
                TECH.search(normalized)
            ) if m
        ]
        title = normalized[:min(markers)] if markers else normalized

    title = re.sub(r'[\[\](){}_-]+', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()

    if not title:
        title = normalized.strip() or "Unknown"

    return {
        "title": title[:512],
        "kind": "series" if is_series else "movie",
        "season": season,
        "episode": episode,
        "quality": quality,
        "language": language
    }
