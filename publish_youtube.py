"""
YouTube Video Publisher for Automated Language Podcasts
Supports OAuth2 refresh token authentication, custom thumbnails, and scheduled publishing days (Tuesday, Thursday, Sunday).
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

# Days allowed for YouTube publishing (Tuesday, Thursday, Sunday)
ALLOWED_YOUTUBE_DAYS = {"Tuesday", "Thursday", "Sunday"}

def get_authenticated_service():
    """
    Returns an authenticated YouTube Data API v3 service client using refresh token credentials.
    """
    token_json_str = (os.getenv('YOUTUBE_TOKEN_JSON') or os.getenv('YT_TOKEN_JSON', '')).strip()
    client_id = (os.getenv('YT_CLIENT_ID') or os.getenv('YOUTUBE_CLIENT_ID', '')).strip()
    client_secret = (os.getenv('YT_CLIENT_SECRET') or os.getenv('YOUTUBE_CLIENT_SECRET', '')).strip()
    refresh_token = (os.getenv('YT_REFRESH_TOKEN') or os.getenv('YOUTUBE_REFRESH_TOKEN', '')).strip()
    token_uri = (os.getenv('YT_TOKEN_URI') or os.getenv('YOUTUBE_TOKEN_URI', 'https://oauth2.googleapis.com/token')).strip()

    if token_json_str:
        try:
            d = json.loads(token_json_str)
            client_id = d.get('client_id', client_id)
            client_secret = d.get('client_secret', client_secret)
            refresh_token = d.get('refresh_token', refresh_token)
            token_uri = d.get('token_uri', token_uri)
        except Exception:
            pass

    if not all([client_id, client_secret, refresh_token]):
        print("[YouTube] Note: YouTube credentials (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN) not set.")
        print("[YouTube] Skipping YouTube publish.")
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials(
            None,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/youtube"]
        )
        creds.refresh(Request())
        return build('youtube', 'v3', credentials=creds)
    except Exception as e:
        print(f"[YouTube Auth Error] Failed to authenticate: {e}")
        return None


def is_youtube_scheduled_day(force: bool = False) -> tuple[bool, str]:
    """
    Checks if today (UTC) is one of the allowed YouTube publishing days:
    Tuesday, Thursday, or Sunday.
    """
    if force:
        return True, "Force Flag Active"

    now_utc = datetime.now(timezone.utc)
    day_name = now_utc.strftime("%A")
    is_allowed = day_name in ALLOWED_YOUTUBE_DAYS
    return is_allowed, day_name


def upload_video_to_youtube(video_path: str, title: str, description: str, thumb_path: str = None, tags: list = None, category_id: str = '27', privacy_status: str = 'public') -> dict:
    """
    Uploads video file to YouTube via YouTube Data API v3 with custom thumbnail.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    youtube = get_authenticated_service()
    if not youtube:
        return None

    from googleapiclient.http import MediaFileUpload

    # Default tags for French learning podcasts if none provided
    if not tags:
        tags = [
            "Apprendre le français", "French listening", "French podcast",
            "Learn French naturally", "French conversation", "Fle",
            "Compréhension orale", "French fluency", "Podcast français"
        ]

    # Ensure title fits YouTube 100 char limit
    clean_title = title.strip()
    if len(clean_title) > 100:
        clean_title = clean_title[:97] + "..."

    body = {
        "snippet": {
            "title": clean_title,
            "description": description.strip(),
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": "fr",
            "defaultAudioLanguage": "fr"
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }

    print(f"[YouTube] Starting upload for '{clean_title}' ({os.path.getsize(video_path) / (1024*1024):.2f} MB)...")
    media = MediaFileUpload(str(video_path), chunksize=8 * 1024 * 1024, resumable=True, mimetype='video/mp4')
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"[YouTube] Upload progress: {pct}%")

    video_id = response.get("id")
    video_url = f"https://youtu.be/{video_id}"
    print(f"[YouTube] Video uploaded successfully! Video ID: {video_id} ({video_url})")

    # Set custom thumbnail if available
    if thumb_path and os.path.exists(thumb_path):
        try:
            print(f"[YouTube] Uploading custom thumbnail: {os.path.basename(thumb_path)}")
            thumb_media = MediaFileUpload(str(thumb_path), mimetype="image/png")
            youtube.thumbnails().set(videoId=video_id, media_body=thumb_media).execute()
            print("[YouTube] Custom thumbnail applied successfully!")
        except Exception as te:
            print(f"[YouTube] Custom thumbnail upload note: {te} (video published with default frame)")

    return {
        "id": video_id,
        "url": video_url,
        "title": clean_title,
        "published_at": datetime.now(timezone.utc).isoformat()
    }


def publish_to_youtube(video_path: str, title: str, description: str, thumb_path: str = None, force: bool = False) -> dict:
    """
    Main entry point for publishing to YouTube:
    - Enforces the Tuesday / Thursday / Sunday schedule (unless force=True).
    - Publishes video and custom thumbnail.
    """
    is_scheduled, day_name = is_youtube_scheduled_day(force=force)
    if not is_scheduled:
        print(f"[YouTube] Today is {day_name}. YouTube publishing is scheduled ONLY for Tuesday, Thursday, and Sunday.")
        print("[YouTube] Skipping YouTube upload for today.")
        return None

    print(f"[YouTube] Today is {day_name} (Scheduled YouTube Day!). Proceeding with upload...")
    return upload_video_to_youtube(video_path, title, description, thumb_path=thumb_path)
