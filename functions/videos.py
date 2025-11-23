import asyncio
import aiohttp
from utils.formatting import format_videos
from config.settings import YOUTUBE_API_KEY


async def get_videos(query):
    """
    Search for videos within a specific YouTube channel using direct API calls.
    Avoids googleapiclient discovery which requires credentials.
    """
    print(f"Entered Get Videos for {query.get('topic', 'unknown')}")
    
    topic = query.get("topic", "")
    if not topic:
        return "Please provide a topic."
    
    if not YOUTUBE_API_KEY:
        print("ERROR: YOUTUBE_API_KEY not set")
        return "YouTube API key not configured. Please contact admin."
    
    # Direct API endpoint - no credentials needed!
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "key": YOUTUBE_API_KEY,
        "q": topic,
        "part": "snippet",
        "channelId": "UCsHJyKNfjVMr4EoXPw-8Jxw",
        "type": "video",
        "maxResults": 5
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"YouTube API error ({response.status}): {error_text}")
                    return f"Failed to search videos. Status: {response.status}"
                
                data = await response.json()
                
                results = []
                for item in data.get("items", []):
                    video = {
                        "title": item["snippet"]["title"],
                        "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                    }
                    results.append(video)
                
                return format_videos(results)
                
    except Exception as e:
        print(f"Error searching videos: {e}")
        return f"Error searching videos: {str(e)}"