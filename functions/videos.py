import asyncio
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from utils.formatting import format_videos, escape_markdown
from config.settings import YOUTUBE_API_KEY


async def get_videos(query):
    """
    Search for videos within a specific YouTube channel.
    The query should be a dict containing 'topic'.
    """
    print("Entered Get Videos for", query.get("topic", "unknown"))
    max_results = 5

    YOUTUBE_API_SERVICE_NAME = "youtube"
    YOUTUBE_API_VERSION = "v3"

    topic = query.get("topic", "")
    if not topic:
        return "Please provide a topic."

    try:
        youtube = await asyncio.to_thread(
            build,
            YOUTUBE_API_SERVICE_NAME,
            YOUTUBE_API_VERSION,
            developerKey=YOUTUBE_API_KEY
        )

        request = youtube.search().list(
            q=topic,
            part="snippet",
            channelId="UCsHJyKNfjVMr4EoXPw-8Jxw",
            type="video",
            maxResults=max_results,
        )
        response = await asyncio.to_thread(request.execute)

        results = []
        for item in response.get("items", []):
            video = {
                "title": item["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
            }
            results.append(video)

        return format_videos(results)
    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred: {e.content}")
        return []