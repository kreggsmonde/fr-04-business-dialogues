import os, sys, argparse, asyncio, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform == 'win32':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass

import config
from story_generator import generate_full_podcast_story, generate_metadata, load_history_topics
from tts_engine import generate_podcast_audio
from thumbnail_generator import generate_thumbnail
from video_composer import render_podcast_video
from publish_facebook import upload_to_facebook

def save_episode_history(record: dict):
    """Synchronously saves episode history to published_videos.json, history.json, and history.js."""
    base_dir = config.BASE_DIR
    p1 = os.path.join(base_dir, "published_videos.json")
    history = []
    if os.path.exists(p1):
        try:
            with open(p1, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    history.append(record)

    # 1. published_videos.json
    with open(p1, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    # 2. history.json
    p2 = os.path.join(base_dir, "history.json")
    with open(p2, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    # 3. history.js
    p3 = os.path.join(base_dir, "history.js")
    with open(p3, "w", encoding="utf-8") as f:
        f.write("// Daily Video History Log & Topic Registry\n")
        f.write("const PODCAST_HISTORY = " + json.dumps(history, indent=2, ensure_ascii=False) + ";\n")
        f.write("if (typeof module !== 'undefined' && module.exports) { module.exports = PODCAST_HISTORY; }\n")
        f.write("if (typeof window !== 'undefined') { window.PODCAST_HISTORY = PODCAST_HISTORY; }\n")

    print(f"[History] Recorded episode #{record['episode']} to published_videos.json, history.json, and history.js")

def run_auto_pipeline(target_minutes: float = 20.0, topic: str = None, dry_run: bool = False, preview_seconds: float = None):
    print("=" * 70)
    print(f"    [PODCAST] {config.CHANNEL_NAME} - AUTOMATED PIPELINE")
    print(f"    Target Duration: {target_minutes:.1f} minutes")
    print("=" * 70)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    past_topics = load_history_topics()
    ep_num = len(past_topics) + 1

    # Step 1: Story & Acts (20 mins, dynamic non-repeating topic)
    print(f"\n[Step 1/5] Generating Podcast Story (Target: {target_minutes:.1f} mins)...")
    story = generate_full_podcast_story(target_minutes=target_minutes, topic=topic, ep_num=ep_num)

    # Step 2: Speech Synthesis
    print(f"\n[Step 2/5] Synthesizing Neural Voices...")
    master_audio, subtitle_chunks, total_dur = asyncio.run(generate_podcast_audio(story["dialogue"]))

    # Calculate chapter start times
    for ch in story["chapters"]:
        start_turn = ch["start_turn"]
        ch_time = 0.0
        for c in subtitle_chunks:
            if c.get("turn_idx") == start_turn:
                ch_time = c["start"]
                break
        ch["start_time"] = ch_time

    # Step 3: High-CTR Thumbnail
    print(f"\n[Step 3/5] Generating Thumbnail...")
    thumb_path = os.path.join(config.OUTPUT_DIR, f"thumb_ep{ep_num}_{timestamp}.jpg")
    generate_thumbnail(
        config.DEFAULT_IMAGE_PATH,
        story["thumbnail_title_1"],
        story["thumbnail_title_2"],
        story["thumbnail_hook"],
        thumb_path,
        ep_number=ep_num
    )

    # Step 4: Render Video
    print(f"\n[Step 4/5] Rendering 1080p Video via FFmpeg Pipe...")
    video_path = os.path.join(config.OUTPUT_DIR, f"podcast_ep{ep_num}_{timestamp}.mp4")
    render_podcast_video(
        config.DEFAULT_IMAGE_PATH,
        master_audio,
        subtitle_chunks,
        video_path,
        fps=config.VIDEO_FPS,
        preview_seconds=preview_seconds
    )

    # Step 5: Publish & Record
    meta = generate_metadata(story["topic"], total_dur, story["chapters"], ep_num=ep_num)
    if dry_run:
        print("[DRY RUN] Skipping Facebook upload.")
    else:
        print(f"\n[Step 5/5] Uploading to Facebook Page '{config.CHANNEL_NAME}'...")
        try:
            upload_to_facebook(video_path, meta["title"], meta["description"])
        except Exception as e:
            print(f"[Facebook Upload Error] {e}")

    # Append to all history registries
    record = {
        "episode": ep_num,
        "topic": story["topic"],
        "date": datetime.now().isoformat(),
        "duration_sec": round(total_dur, 2),
        "duration_min": round(total_dur / 60.0, 2),
        "video_file": os.path.basename(video_path),
        "platform": "Facebook"
    }
    save_episode_history(record)

    print("\n" + "=" * 70)
    print(f"       PIPELINE RUN COMPLETE! Ep. #{ep_num} ({total_dur/60:.1f} mins)")
    print("=" * 70)
    return video_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"{config.CHANNEL_NAME} Automation Pipeline")
    parser.add_argument("--duration", type=float, default=20.0, help="Target duration in minutes (default: 20.0)")
    parser.add_argument("--topic", type=str, default=None, help="Custom topic override")
    parser.add_argument("--dry-run", action="store_true", help="Skip social uploads")
    parser.add_argument("--preview", type=float, default=None, help="Render preview seconds only")
    args = parser.parse_args()

    run_auto_pipeline(target_minutes=args.duration, topic=args.topic, dry_run=args.dry_run, preview_seconds=args.preview)
