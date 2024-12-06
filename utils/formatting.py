import re

def escape_markdown(text: str, version: str = "MarkdownV2") -> str:
    if version == "MarkdownV2":
        escape_chars = r"\_*[]()~`>#+-=|{}.!"
    else:
        escape_chars = r"\_*[]()"

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
                escaped_name = escape_markdown(display_name)
                formatted_notes.append(f"[{escaped_name}]({value})")

    recurse_format(data)
    return "\n".join(formatted_notes)

def format_videos(video_data):
    if not isinstance(video_data, list):
        return "Video data not in expected format."

    formatted_videos = []
    for video in video_data:
        title = video.get("title", "No Title")
        url = video.get("url", "#")
        escaped_title = escape_markdown(title)
        formatted_videos.append(f"[{escaped_title}]({url})")

    return "\n\n".join(formatted_videos)
