"""
Formatting utilities for Telegram bot messages.
Provides markdown escaping, message splitting, and content formatting.
"""

import re
from typing import List


def split_message(text: str, max_length: int = 4000) -> List[str]:
    """
    Split a long message into chunks that fit within Telegram's limit.
    
    Splits at paragraph boundaries first, then line boundaries.
    Telegram's max is 4096, using 4000 for safety margin.
    
    Args:
        text: The message text to split
        max_length: Maximum length per chunk (default 4000)
        
    Returns:
        List of message chunks
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    remaining = text
    
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break
        
        # Find best split point within max_length
        chunk = remaining[:max_length]
        
        # Try to split at paragraph boundary first
        para_split = chunk.rfind('\n\n')
        if para_split > max_length // 2:  # Only use if reasonably far in
            chunks.append(remaining[:para_split].rstrip())
            remaining = remaining[para_split:].lstrip()
            continue
        
        # Fall back to line boundary
        line_split = chunk.rfind('\n')
        if line_split > max_length // 2:
            chunks.append(remaining[:line_split].rstrip())
            remaining = remaining[line_split:].lstrip()
            continue
        
        # Last resort: split at space
        space_split = chunk.rfind(' ')
        if space_split > max_length // 2:
            chunks.append(remaining[:space_split])
            remaining = remaining[space_split:].lstrip()
            continue
        
        # No good split point, hard cut
        chunks.append(remaining[:max_length])
        remaining = remaining[max_length:]
    
    return chunks


def escape_markdown(text: str, version: str = "Markdown") -> str:
    """
    Escape special characters for Telegram Markdown.
    
    For standard Markdown mode, only escape: _ * [ ] ( )
    Preserves markdown links [text](url) without escaping.
    
    Args:
        text: Text to escape
        version: "Markdown" (default) or "MarkdownV2"
        
    Returns:
        Escaped text safe for Telegram
    """
    if version == "MarkdownV2":
        escape_chars = r"\_*[]()~`>#+-=|{}.!"
    else:
        # Standard Markdown - fewer chars to escape
        escape_chars = r"_*"
    
    # Preserve markdown links - don't escape inside them
    link_pattern = re.compile(r"(\[.*?\]\(.*?\))")
    parts = link_pattern.split(text)
    escaped_parts = [
        part if link_pattern.match(part)
        else "".join(f"\\{char}" if char in escape_chars else char for char in part)
        for part in parts
    ]
    return "".join(escaped_parts)

def format_notes(data):
    if not isinstance(data, dict):
        return "Notes data not in expected format."

    formatted_notes = []

    def recurse_format(d, parent_keys=[]):
        for key, value in d.items():
            if isinstance(value, dict):
                recurse_format(value, parent_keys + [key])
            else:
                display_name = " > ".join(parent_keys + [key])
                # Clean formatting for Telegram without markdown escaping
                formatted_notes.append(f"📄 {display_name}\n🔗 {value}\n")

    recurse_format(data)
    return "\n".join(formatted_notes)

def format_videos(video_data):
    """
    Format video search results for Telegram display.
    
    Creates a clean, readable list with visual hierarchy.
    
    Args:
        video_data: List of video dicts with 'title' and 'url' keys
        
    Returns:
        Formatted string for Telegram message
    """
    if not isinstance(video_data, list):
        return "🤔 Video data not in expected format."
    
    if not video_data:
        return (
            "🔍 No videos found for this topic.\n\n"
            "Try searching for:\n"
            "• A broader topic (e.g., 'Python' instead of 'Python decorators')\n"
            "• A different keyword"
        )
    
    # Header with count
    count = len(video_data)
    formatted_videos = [f"🎬 *Found {count} video{'s' if count > 1 else ''}:*\n"]
    
    # Format each video with full title
    for idx, video in enumerate(video_data, 1):
        title = video.get("title", "No Title")
        url = video.get("url", "#")
        
        # Escape special markdown characters in title
        escaped_title = escape_markdown(title)
        
        formatted_videos.append(f"{idx}. 📺 [{escaped_title}]({url})")
    
    # Add helpful tip
    formatted_videos.append("\n💡 _Tap any link to watch!_")
    
    return "\n".join(formatted_videos)
