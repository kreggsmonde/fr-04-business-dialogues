"""
Facebook Page Video Publisher (Meta Graph API v20.0)
Supports Chunked Resumable Upload for large videos with automatic fallback to direct upload.
"""
import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()
GRAPH_API_VERSION = "v20.0"

def get_facebook_credentials():
    page_id = (os.getenv('FB_PAGE_ID') or os.getenv('FACEBOOK_PAGE_ID') or '').strip()
    access_token = (os.getenv('FB_PAGE_ACCESS_TOKEN') or os.getenv('FACEBOOK_PAGE_ACCESS_TOKEN') or '').strip()

    if not page_id or not access_token:
        print("[facebook] Note: FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN not yet set.")
        print("[facebook] Please configure them in your .env file or environment when ready to publish.")
        return None, None
    return page_id, access_token

def upload_video_resumable(video_path, title, description, page_id, access_token):
    file_size = os.path.getsize(video_path)
    print(f"[facebook] Starting resumable upload for '{title}' ({file_size / (1024 * 1024):.2f} MB)...")

    start_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}/videos"
    start_payload = {
        "upload_phase": "start",
        "file_size": file_size,
        "access_token": access_token
    }
    resp = requests.post(start_url, data=start_payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"START failed ({resp.status_code}): {resp.text}")

    start_data = resp.json()
    upload_session_id = start_data["upload_session_id"]
    video_id = start_data.get("video_id")
    start_offset = int(start_data.get("start_offset", 0))
    end_offset = int(start_data.get("end_offset", 0))

    chunk_size = end_offset - start_offset if end_offset > start_offset else (4 * 1024 * 1024)
    with open(video_path, "rb") as f:
        while start_offset < file_size:
            f.seek(start_offset)
            chunk_data = f.read(chunk_size)
            if not chunk_data:
                break

            transfer_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}/videos"
            t_data = {
                "upload_phase": "transfer",
                "upload_session_id": upload_session_id,
                "start_offset": start_offset,
                "access_token": access_token
            }
            t_files = {"video_file_chunk": ("chunk.mp4", chunk_data, "video/mp4")}
            t_resp = requests.post(transfer_url, data=t_data, files=t_files, timeout=120)
            if t_resp.status_code != 200:
                raise RuntimeError(f"TRANSFER failed at {start_offset} ({t_resp.status_code}): {t_resp.text}")

            res = t_resp.json()
            new_start = int(res.get("start_offset", start_offset + len(chunk_data)))
            new_end = int(res.get("end_offset", new_start + chunk_size))
            chunk_size = new_end - new_start if new_end > new_start else chunk_size
            pct = min(100, int((new_start / file_size) * 100))
            print(f"[facebook] Upload progress: {pct}%")
            start_offset = new_start

    finish_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}/videos"
    finish_payload = {
        "upload_phase": "finish",
        "upload_session_id": upload_session_id,
        "title": title,
        "description": description,
        "access_token": access_token
    }
    f_resp = requests.post(finish_url, data=finish_payload, timeout=60)
    if f_resp.status_code != 200:
        raise RuntimeError(f"FINISH failed ({f_resp.status_code}): {f_resp.text}")

    result = f_resp.json()
    final_video_id = result.get("id") or video_id
    print(f"[facebook] Video uploaded successfully! Video ID: {final_video_id}")
    return {"id": final_video_id, "success": True, "data": result}

def upload_video_direct(video_path, title, description, page_id, access_token):
    print(f"[facebook] Direct uploading: {title}")
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}/videos"
    payload = {"title": title, "description": description, "access_token": access_token}
    with open(video_path, "rb") as f:
        files = {"source": (os.path.basename(video_path), f, "video/mp4")}
        resp = requests.post(url, data=payload, files=files, timeout=600)
    if resp.status_code != 200:
        raise RuntimeError(f"Direct upload failed ({resp.status_code}): {resp.text}")
    return resp.json()

def upload_to_facebook(video_path, title, description):
    page_id, access_token = get_facebook_credentials()
    if not page_id or not access_token:
        print("[facebook] Credentials not provided. Skipping publish.")
        return None
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    # Enforce single-call direct multipart stream (exactly 1 API call to prevent rate limiting / blocks)
    print(f"[facebook] Uploading via direct single-request stream (1 API call)...")
    return upload_video_direct(video_path, title, description, page_id, access_token)

def main():
    if len(sys.argv) < 2:
        print("Usage: python publish_facebook.py <video_path> [title|metadata.json] [description]")
        sys.exit(1)

    video_path = sys.argv[1]
    title = "Learn English Naturally"
    description = "Improve your English fluency and listening skills. Follow our page for daily lessons! ????"

    if len(sys.argv) > 2:
        arg2 = sys.argv[2]
        if arg2.endswith(".json") and os.path.exists(arg2):
            with open(arg2, "r", encoding="utf-8") as f:
                meta = json.load(f)
                title = meta.get("title") or meta.get("selected_title") or title
                description = meta.get("description") or description
        else:
            title = arg2
            if len(sys.argv) > 3:
                description = sys.argv[3]

    result = upload_to_facebook(video_path, title, description)
    if result:
        video_dir = Path(video_path).parent
        out_file = video_dir / "facebook_upload_result.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[facebook] Result recorded to {out_file}")

if __name__ == '__main__':
    main()
