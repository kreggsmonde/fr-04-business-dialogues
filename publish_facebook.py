"""
Facebook Page Video Publisher (Meta Graph API v20.0)
High-efficiency video upload with dynamic chunking:
- Direct single-request stream for small clips (<= 25 MB)
- High-efficiency Resumable Upload (32 MB chunks, ~5-8 API calls total) for full-length episodes
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
CHUNK_SIZE_BYTES = 32 * 1024 * 1024  # 32 MB chunks: only ~6-8 API calls for a full 200MB podcast episode

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
    print(f"[facebook] Starting high-efficiency resumable upload for '{title}' ({file_size / (1024 * 1024):.2f} MB)...")

    # Phase 1: Start
    start_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}/videos"
    start_payload = {
        "upload_phase": "start",
        "file_size": file_size,
        "access_token": access_token
    }
    resp = requests.post(start_url, data=start_payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"START phase failed ({resp.status_code}): {resp.text}")

    start_data = resp.json()
    upload_session_id = start_data.get("upload_session_id")
    video_id = start_data.get("video_id")
    start_offset = int(start_data.get("start_offset", 0))
    end_offset = int(start_data.get("end_offset", 0))

    chunk_size = end_offset - start_offset if end_offset > start_offset else CHUNK_SIZE_BYTES
    chunk_count = 0

    # Phase 2: Transfer Chunks
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
            t_resp = requests.post(transfer_url, data=t_data, files=t_files, timeout=300)
            if t_resp.status_code != 200:
                raise RuntimeError(f"TRANSFER failed at offset {start_offset} ({t_resp.status_code}): {t_resp.text}")

            res = t_resp.json()
            chunk_count += 1
            new_start = int(res.get("start_offset", start_offset + len(chunk_data)))
            new_end = int(res.get("end_offset", new_start + CHUNK_SIZE_BYTES))
            chunk_size = new_end - new_start if new_end > new_start else CHUNK_SIZE_BYTES
            pct = min(100, int((new_start / file_size) * 100))
            print(f"[facebook] Chunk #{chunk_count} uploaded ({pct}%)")
            start_offset = new_start

    # Phase 3: Finish
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
        raise RuntimeError(f"FINISH phase failed ({f_resp.status_code}): {f_resp.text}")

    result = f_resp.json()
    final_video_id = result.get("id") or video_id
    total_calls = chunk_count + 2
    print(f"[facebook] Video uploaded successfully! Video ID: {final_video_id} (Total API calls: {total_calls})")
    return {"id": final_video_id, "success": True, "data": result}

def upload_video_direct(video_path, title, description, page_id, access_token):
    print(f"[facebook] Direct single-request uploading: {title}")
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}/videos"
    payload = {"title": title, "description": description, "access_token": access_token}
    with open(video_path, "rb") as f:
        files = {"source": (os.path.basename(video_path), f, "video/mp4")}
        resp = requests.post(url, data=payload, files=files, timeout=600)
    if resp.status_code != 200:
        raise RuntimeError(f"Direct upload failed ({resp.status_code}): {resp.text}")
    data = resp.json()
    print(f"[facebook] Direct video upload complete! Video ID: {data.get('id')}")
    return data

def upload_to_facebook(video_path, title, description):
    page_id, access_token = get_facebook_credentials()
    if not page_id or not access_token:
        print("[facebook] Credentials not provided. Skipping publish.")
        return None
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    file_size = os.path.getsize(video_path)
    # Direct upload (1 API call) for small files <= 25 MB
    if file_size <= 25 * 1024 * 1024:
        print(f"[facebook] Video size is {file_size / (1024 * 1024):.1f} MB (<= 25 MB). Using direct upload (1 API call)...")
        try:
            return upload_video_direct(video_path, title, description, page_id, access_token)
        except Exception as e:
            if "413" in str(e):
                print("[facebook] Gateway returned 413 Payload Too Large. Seamlessly falling back to resumable upload...")
            else:
                raise e

    # Large episodes (> 25 MB): Resumable upload with 32MB chunks (only ~5-8 calls total, prevents 413 errors)
    print(f"[facebook] Video size is {file_size / (1024 * 1024):.1f} MB. Using resumable upload with 32MB chunks...")
    return upload_video_resumable(video_path, title, description, page_id, access_token)

def main():
    if len(sys.argv) < 2:
        print("Usage: python publish_facebook.py <video_path> [title|metadata.json] [description]")
        sys.exit(1)

    video_path = sys.argv[1]
    title = "Podcast Episode"
    description = "Daily episode. Follow our page for more lessons!"

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
