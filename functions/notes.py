import os
import json
from pathlib import Path
from utils.formatting import format_notes, escape_markdown

async def get_notes(query):
    """
    Retrieve the notes based on the provided query.
    The query should be a dict with keys like 'class', 'subject', 'type', and optionally 'topic'.
    """
    print("Entered Get Notes, Query is:", query, type(query))

    if isinstance(query, str):
        query = json.loads(query)

    # Portable path resolution for Windows/local and container
    env_index = os.getenv("INDEX_PATH")
    if env_index:
        index_path = Path(env_index)
    else:
        # Try repo-relative data path; fall back to container path
        repo_data_path = Path(__file__).resolve().parents[1] / "data" / "index.json"
        index_path = repo_data_path if repo_data_path.exists() else Path("/app/data/index.json")
    if not index_path.exists():
        return "Notes index file not found!"

    with open(index_path) as f:
        index = json.load(f)

    class_name = query.get("class")
    subject = query.get("subject")
    query_type = query.get("type")

    if not class_name or not subject or not query_type:
        return "Missing required parameters (class, subject, or type)."

    try:
        data = index[class_name][subject][query_type]
    except KeyError:
        return "Not available, Please try with other inputs or contact the admin!"

    topic = query.get("topic")
    if topic and topic in data:
        return format_notes(data[topic])
    else:
        return format_notes(data)