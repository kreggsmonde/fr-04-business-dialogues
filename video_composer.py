import os, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import config
from audio_visualizer import AudioSpectrumVisualizer

def render_podcast_video(image_path: str, audio_path: str, subtitle_chunks: list, output_video_path: str, fps: int = 30, preview_seconds: float = None) -> str:
    print(f"[VideoComposer] Initializing video render: {output_video_path}...")
    visualizer = AudioSpectrumVisualizer(audio_path, fps=fps)
    total_frames = visualizer.total_frames
    if preview_seconds:
        total_frames = min(total_frames, int(preview_seconds * fps))
        print(f"[VideoComposer] Preview active: rendering {total_frames} frames ({preview_seconds:.1f}s)...")

    base_img = Image.open(image_path).convert("RGBA")
    if base_img.size != (config.VIDEO_WIDTH, config.VIDEO_HEIGHT):
        base_img = base_img.resize((config.VIDEO_WIDTH, config.VIDEO_HEIGHT), Image.Resampling.LANCZOS)

    # Static Branding Ribbon & Footer
    draw_base = ImageDraw.Draw(base_img)
    font_path = config.FONT_PATH if os.path.exists(config.FONT_PATH) else config.FALLBACK_FONT_PATH
    sub_font = ImageFont.truetype(font_path, config.SUBTITLE_FONT_SIZE)
    f_brand = ImageFont.truetype(font_path, 28)
    # Bilingual subtitles: smaller English translation line below the native line.
    en_font_size = max(28, int(config.SUBTITLE_FONT_SIZE * 0.72))
    en_font = ImageFont.truetype(font_path, en_font_size)
    en_color = (176, 196, 222)
    en_line_h = en_font_size + 12

    def wrap_en(text, font, max_w):
        sp = draw_base.textbbox((0, 0), " ", font=font)[2]
        out, cur, cur_w = [], [], 0
        for w in text.split():
            ww = draw_base.textbbox((0, 0), w, font=font)[2]
            add = ww if not cur else sp + ww
            if cur and cur_w + add > max_w:
                out.append(" ".join(cur))
                cur, cur_w = [w], ww
            else:
                cur.append(w)
                cur_w += add
        if cur:
            out.append(" ".join(cur))
        return out

    # 1. Circular Channel Logo Badge with Antialiased Mask & Gold Rim
    logo_size = 104
    logo_x, logo_y = 50, 35
    if os.path.exists(config.LOGO_PATH):
        try:
            raw_logo = Image.open(config.LOGO_PATH).convert("RGBA")
            raw_logo = raw_logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

            mask = Image.new("L", (logo_size * 4, logo_size * 4), 0)
            m_draw = ImageDraw.Draw(mask)
            m_draw.ellipse((0, 0, logo_size * 4, logo_size * 4), fill=255)
            mask = mask.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

            circular_logo = Image.new("RGBA", (logo_size, logo_size), (0, 0, 0, 0))
            circular_logo.paste(raw_logo, (0, 0), mask)
            base_img.paste(circular_logo, (logo_x, logo_y), circular_logo)

            draw_base.ellipse(
                [(logo_x - 2, logo_y - 2), (logo_x + logo_size + 2, logo_y + logo_size + 2)],
                outline=(255, 215, 0, 240),
                width=3
            )
        except Exception:
            pass

    # 2. Dynamic Auto-Wrapping Top Branding Pill
    bbox = draw_base.textbbox((0, 0), config.CHANNEL_NAME, font=f_brand)
    text_w = bbox[2] - bbox[0]
    pill_start_x = 168
    text_start_x = pill_start_x + 48
    pill_end_x = text_start_x + text_w + 32

    draw_base.rounded_rectangle(
        [(pill_start_x, 50), (pill_end_x, 112)],
        radius=30,
        fill=(16, 20, 32, 230),
        outline=(255, 215, 0, 220),
        width=2
    )
    # Glowing green live indicator
    dot_cx = pill_start_x + 24
    draw_base.ellipse([(dot_cx - 8, 81 - 8), (dot_cx + 8, 81 + 8)], fill=(34, 197, 94))
    # Channel name text perfectly inside container
    draw_base.text((text_start_x, 66), config.CHANNEL_NAME, fill=(255, 255, 255), font=f_brand)

    # Footer
    draw_base.line([(0, 1025), (config.VIDEO_WIDTH, 1025)], fill=(45, 50, 70), width=2)
    draw_base.text((config.SUBTITLE_CENTER_X, 1052), config.TAGLINE, fill=(235, 225, 200), font=f_brand, anchor="mm")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "-",
        "-i", audio_path,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_video_path
    ]

    pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    total_audio_sec = total_frames / float(fps)

    # Pre-render & layout subtitle chunks (Bulletproof Auto-Wrap & Auto-Scale)
    pill_pad = 32
    if getattr(config, "IS_SOLO", False):
        safe_left = 980
        safe_right = 1780
    else:
        # Dual hosts: Left host face is X<500, Right host face is X>1450.
        # Safe center zone strictly [620, 1300] ensures >170px clearance from both faces.
        safe_left = 620
        safe_right = 1300

    max_container_w = safe_right - safe_left
    max_text_w = max_container_w - pill_pad * 2
    base_font_size = config.SUBTITLE_FONT_SIZE
    processed_chunks = []

    for c in subtitle_chunks:
        words = c["words"]
        if not words:
            continue

        c_font = sub_font
        space_w = draw_base.textbbox((0, 0), " ", font=c_font)[2]
        w_metrics = [{"word": w["word"], "start": w["start"], "end": w["end"], "width": draw_base.textbbox((0, 0), w["word"], font=c_font)[2]} for w in words]
        total_w = sum(wm["width"] for wm in w_metrics) + max(0, len(w_metrics) - 1) * space_w

        # Case 1: Fits comfortably on 1 line
        if total_w <= max_text_w:
            pill_w = total_w + pill_pad * 2
            ideal_left = config.SUBTITLE_CENTER_X - (pill_w // 2)
            pill_left = max(safe_left, min(ideal_left, safe_right - pill_w))
            pill_right = pill_left + pill_w
            pill_top = config.SUBTITLE_Y - 14
            pill_bot = config.SUBTITLE_Y + base_font_size + 22
            lines = [{
                "words": w_metrics,
                "line_w": total_w,
                "sx": pill_left + pill_pad,
                "sy": config.SUBTITLE_Y
            }]
        # Case 2: Multi-word chunk exceeds max_text_w -> Split into 2 balanced lines
        elif len(words) > 1:
            best_split = len(words) // 2
            min_max_w = float("inf")
            best_lines = None
            for split in range(1, len(words)):
                l1 = w_metrics[:split]
                l2 = w_metrics[split:]
                w1 = sum(wm["width"] for wm in l1) + max(0, len(l1) - 1) * space_w
                w2 = sum(wm["width"] for wm in l2) + max(0, len(l2) - 1) * space_w
                if max(w1, w2) < min_max_w:
                    min_max_w = max(w1, w2)
                    best_lines = (l1, w1, l2, w2)
            l1, w1, l2, w2 = best_lines

            # If both lines fit:
            if max(w1, w2) <= max_text_w:
                pill_w = max(w1, w2) + pill_pad * 2
                ideal_left = config.SUBTITLE_CENTER_X - (pill_w // 2)
                pill_left = max(safe_left, min(ideal_left, safe_right - pill_w))
                pill_right = pill_left + pill_w
                line_h = base_font_size + 10
                pill_top = config.SUBTITLE_Y - 20
                pill_bot = pill_top + line_h * 2 + 25
                lines = [
                    {"words": l1, "line_w": w1, "sx": config.SUBTITLE_CENTER_X - (w1 // 2), "sy": pill_top + 12},
                    {"words": l2, "line_w": w2, "sx": config.SUBTITLE_CENTER_X - (w2 // 2), "sy": pill_top + 12 + line_h}
                ]
            else:
                scale = (max_text_w - 10) / float(max(w1, w2))
                scaled_size = max(28, int(base_font_size * scale))
                c_font = ImageFont.truetype(font_path, scaled_size)
                space_w = draw_base.textbbox((0, 0), " ", font=c_font)[2]
                l1_sc = [{"word": w["word"], "start": w["start"], "end": w["end"], "width": draw_base.textbbox((0, 0), w["word"], font=c_font)[2]} for w in words[:len(l1)]]
                l2_sc = [{"word": w["word"], "start": w["start"], "end": w["end"], "width": draw_base.textbbox((0, 0), w["word"], font=c_font)[2]} for w in words[len(l1):]]
                w1_sc = sum(wm["width"] for wm in l1_sc) + max(0, len(l1_sc) - 1) * space_w
                w2_sc = sum(wm["width"] for wm in l2_sc) + max(0, len(l2_sc) - 1) * space_w
                pill_w = max(w1_sc, w2_sc) + pill_pad * 2
                ideal_left = config.SUBTITLE_CENTER_X - (pill_w // 2)
                pill_left = max(safe_left, min(ideal_left, safe_right - pill_w))
                pill_right = pill_left + pill_w
                line_h = scaled_size + 10
                pill_top = config.SUBTITLE_Y - 20
                pill_bot = pill_top + line_h * 2 + 25
                lines = [
                    {"words": l1_sc, "line_w": w1_sc, "sx": config.SUBTITLE_CENTER_X - (w1_sc // 2), "sy": pill_top + 12},
                    {"words": l2_sc, "line_w": w2_sc, "sx": config.SUBTITLE_CENTER_X - (w2_sc // 2), "sy": pill_top + 12 + line_h}
                ]
        # Case 3: Single gigantic word exceeds max_text_w -> Auto-scale font
        else:
            scale = (max_text_w - 10) / float(total_w)
            scaled_size = max(28, int(base_font_size * scale))
            c_font = ImageFont.truetype(font_path, scaled_size)
            space_w = draw_base.textbbox((0, 0), " ", font=c_font)[2]
            sc_metrics = [{"word": w["word"], "start": w["start"], "end": w["end"], "width": draw_base.textbbox((0, 0), w["word"], font=c_font)[2]} for w in words]
            sc_total_w = sum(wm["width"] for wm in sc_metrics) + max(0, len(sc_metrics) - 1) * space_w
            pill_w = sc_total_w + pill_pad * 2
            ideal_left = config.SUBTITLE_CENTER_X - (pill_w // 2)
            pill_left = max(safe_left, min(ideal_left, safe_right - pill_w))
            pill_right = pill_left + pill_w
            pill_top = config.SUBTITLE_Y - 14
            pill_bot = config.SUBTITLE_Y + scaled_size + 22
            lines = [{
                "words": sc_metrics,
                "line_w": sc_total_w,
                "sx": pill_left + pill_pad,
                "sy": config.SUBTITLE_Y
            }]

        # Fit English translation line(s) under the native subtitle.
        en_text = (c.get("en") or "").strip()
        en_draw_lines = []
        if en_text:
            for en_line in wrap_en(en_text, en_font, max_text_w):
                en_w = draw_base.textbbox((0, 0), en_line, font=en_font)[2]
                en_draw_lines.append({"text": en_line, "w": en_w})
        if en_draw_lines:
            pill_w = max(pill_right - pill_left, max(d["w"] for d in en_draw_lines) + pill_pad * 2)
            ideal_left = config.SUBTITLE_CENTER_X - (pill_w // 2)
            pill_left = max(safe_left, min(ideal_left, safe_right - pill_w))
            pill_right = pill_left + pill_w
            # Re-center native lines inside the (possibly widened) pill.
            for ld in lines:
                ld["sx"] = pill_left + (pill_w - ld["line_w"]) // 2
            en_sy = pill_bot - 2
            for d in en_draw_lines:
                d["sx"] = pill_left + (pill_w - d["w"]) // 2
                d["sy"] = en_sy
                en_sy += en_line_h
            pill_bot = en_sy - en_line_h + en_font_size + 16

        processed_chunks.append({
            "start": c["start"],
            "end": c["end"],
            "speaker": c.get("speaker", "female"),
            "font": c_font,
            "space_w": space_w,
            "pill_box": (pill_left, pill_top, pill_right, pill_bot),
            "lines": lines,
            "en_lines": en_draw_lines,
            "en_font": en_font
        })

    active_chunk_idx = 0
    num_chunks = len(processed_chunks)

    for f_idx in range(total_frames):
        t_sec = f_idx / float(fps)
        while active_chunk_idx < num_chunks - 1 and t_sec > processed_chunks[active_chunk_idx]["end"]:
            active_chunk_idx += 1

        chunk = processed_chunks[active_chunk_idx] if active_chunk_idx < num_chunks and processed_chunks[active_chunk_idx]["start"] <= t_sec <= processed_chunks[active_chunk_idx]["end"] else None

        frame_img = base_img.copy()
        draw = ImageDraw.Draw(frame_img)

        # Draw audio visualizer
        visualizer.draw_frame(draw, f_idx)

        # Draw progress line
        ratio = min(1.0, t_sec / max(1.0, total_audio_sec))
        draw.line([(0, 1025), (int(config.VIDEO_WIDTH * ratio), 1025)], fill=(255, 215, 0), width=4)

        # Draw subtitle strictly inside pill container
        if chunk:
            p_left, p_top, p_right, p_bot = chunk["pill_box"]
            draw.rounded_rectangle(
                [(p_left, p_top), (p_right, p_bot)],
                radius=20,
                fill=(12, 14, 22, 215),
                outline=(255, 215, 0, 180),
                width=2
            )

            c_font = chunk["font"]
            space_w = chunk["space_w"]
            for line_data in chunk["lines"]:
                curr_x = line_data["sx"]
                sy = line_data["sy"]
                for wm in line_data["words"]:
                    is_active = (wm["start"] <= t_sec <= wm["end"])
                    color = (255, 215, 0) if is_active else (255, 255, 255)
                    # Drop shadow
                    draw.text((curr_x + 3, sy + 3), wm["word"], fill=(0, 0, 0, 220), font=c_font)
                    draw.text((curr_x, sy), wm["word"], fill=color, font=c_font)
                    curr_x += wm["width"] + space_w
            for ed in chunk.get("en_lines", []):
                draw.text((ed["sx"] + 2, ed["sy"] + 2), ed["text"], fill=(0, 0, 0, 220), font=chunk["en_font"])
                draw.text((ed["sx"], ed["sy"]), ed["text"], fill=en_color, font=chunk["en_font"])

        raw_bgr = np.array(frame_img.convert("RGB"))[:, :, ::-1].tobytes()
        pipe.stdin.write(raw_bgr)

        if (f_idx + 1) % (fps * 30) == 0:
            print(f"  [Video Render] Progress: {f_idx + 1}/{total_frames} frames ({(f_idx+1)/fps:.1f}s)")

    pipe.stdin.close()
    pipe.wait()
    print(f"[VideoComposer] Video rendered successfully: {output_video_path}")
    return output_video_path
