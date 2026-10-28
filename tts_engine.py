import os, json, asyncio, random, edge_tts
from pydub import AudioSegment
import config

EDGE_ENDPOINTS = [
    "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1?Ocp-Apim-Subscription-Key=6A5AA1D4EAFF4E9FB37E23D68491D6F4",
    "wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken=6A5AA1D4EAFF4E9FB37E23D68491D6F4"
]

def set_edge_tts_endpoint(url: str):
    try:
        import edge_tts.constants
        import edge_tts.communicate
        edge_tts.constants.WSS_URL = url
        edge_tts.communicate.WSS_URL = url
    except Exception:
        pass

async def synthesize_turn(text: str, voice: str, pitch: str, rate: str, turn_index: int) -> dict:
    last_err = None
    temp_turn_path = os.path.join(config.TEMP_DIR, f"turn_{turn_index}.mp3")

    for attempt in range(5):
        target_endpoint = EDGE_ENDPOINTS[attempt % len(EDGE_ENDPOINTS)]
        set_edge_tts_endpoint(target_endpoint)

        try:
            kwargs = {"rate": rate}
            if pitch and pitch != "+0Hz":
                kwargs["pitch"] = pitch
            comm = edge_tts.Communicate(text, voice, boundary="WordBoundary", **kwargs)
            audio_data = bytearray()
            words = []

            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    audio_data.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    w_text = chunk["text"].strip()
                    start_s = chunk["offset"] / 10_000_000.0
                    dur_s = chunk["duration"] / 10_000_000.0
                    words.append({
                        "word": w_text,
                        "rel_start": start_s,
                        "rel_end": start_s + dur_s,
                        "duration": dur_s
                    })

            if len(audio_data) > 500:
                with open(temp_turn_path, "wb") as f:
                    f.write(audio_data)

                seg = AudioSegment.from_file(temp_turn_path)
                dur_sec = len(seg) / 1000.0
                return {
                    "audio_segment": seg,
                    "duration": dur_sec,
                    "words": words,
                    "turn_index": turn_index
                }
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            if "429" in err_str or "rate" in err_str or "invalid response status" in err_str:
                backoff = (2 ** (attempt % 3)) * 1.5 + random.uniform(1.0, 2.5)
                print(f"  [TTS 429 Throttle] Turn {turn_index}. Backing off {backoff:.1f}s...")
                await asyncio.sleep(backoff)
            else:
                await asyncio.sleep(1.0)

    # gTTS Fallback
    try:
        from gtts import gTTS
        print(f"  [TTS Fallback] Using gTTS for turn {turn_index}...")
        tts = gTTS(text=text, lang="en")
        tts.save(temp_turn_path)
        seg = AudioSegment.from_file(temp_turn_path)
        dur_sec = len(seg) / 1000.0
        words_list = text.split()
        w_dur = dur_sec / max(1, len(words_list))
        words = [{"word": w, "rel_start": round(i * w_dur, 3), "rel_end": round((i + 1) * w_dur, 3), "duration": round(w_dur, 3)} for i, w in enumerate(words_list)]
        return {"audio_segment": seg, "duration": dur_sec, "words": words, "turn_index": turn_index}
    except Exception as fb_err:
        print(f"  [TTS Emergency] Generating silent segment: {fb_err}")
        est_dur = max(2.0, len(text.split()) * 0.35)
        seg = AudioSegment.silent(duration=int(est_dur * 1000))
        seg.export(temp_turn_path, format="mp3")
        return {"audio_segment": seg, "duration": est_dur, "words": [], "turn_index": turn_index}

def chunk_turn_words(words: list, speaker: str, global_turn_offset: float, turn_duration: float, max_words_per_line: int = None, max_chars_per_line: int = None) -> list:
    if not words:
        return []

    if max_words_per_line is None:
        max_words_per_line = getattr(config, "MAX_WORDS_PER_LINE", 3)
    if max_chars_per_line is None:
        max_chars_per_line = getattr(config, "MAX_CHARS_PER_LINE", 22)

    chunks = []
    curr = []
    for w in words:
        curr.append(w)
        line_chars = sum(len(x["word"]) for x in curr) + len(curr) - 1
        if len(curr) >= max_words_per_line or line_chars >= max_chars_per_line or w["word"].endswith(('.', '?', '!', ';', ':', ',')):
            chunks.append(curr)
            curr = []
    if curr:
        chunks.append(curr)

    formatted_chunks = []
    for i, c_words in enumerate(chunks):
        c_start = global_turn_offset + c_words[0]["rel_start"]
        c_end = global_turn_offset + c_words[-1]["rel_end"]
        if i + 1 < len(chunks):
            next_start = global_turn_offset + chunks[i+1][0]["rel_start"]
            c_end = min(next_start, c_end + 0.15)
        else:
            c_end = min(global_turn_offset + turn_duration, c_end + 0.3)

        chunk_words_data = [{
            "word": w["word"],
            "start": global_turn_offset + w["rel_start"],
            "end": global_turn_offset + w["rel_end"]
        } for w in c_words]

        formatted_chunks.append({
            "line_text": " ".join(w["word"] for w in c_words),
            "start": round(c_start, 3),
            "end": round(c_end, 3),
            "speaker": speaker,
            "words": chunk_words_data
        })

    return formatted_chunks

async def generate_podcast_audio(dialogue: list) -> tuple:
    print(f"[TTS] Synthesizing speech for {len(dialogue)} turns with concurrency limit (2 workers)...")
    semaphore = asyncio.Semaphore(2)

    async def worker(idx: int, turn: dict):
        async with semaphore:
            spk = turn.get("speaker", "female").lower()
            if config.IS_SOLO:
                voice = config.VOICE_HOST1
                pitch = config.HOST1_PITCH
            elif "female" in spk or turn.get("name") == config.HOST1_NAME:
                voice = config.VOICE_HOST1
                pitch = config.HOST1_PITCH
            else:
                voice = config.VOICE_HOST2
                pitch = config.HOST2_PITCH

            text = turn.get("text", "").strip()
            res = await synthesize_turn(text, voice, pitch, config.TTS_RATE, idx)
            res["speaker"] = spk
            res["name"] = turn.get("name", "Host")
            res["turn_text"] = text
            res["en"] = turn.get("en", "")
            if (idx + 1) % 25 == 0 or idx == len(dialogue) - 1:
                print(f"  [TTS Progress] Synthesized {idx + 1}/{len(dialogue)} turns")
            await asyncio.sleep(0.4)  # Inter-turn rate-limit buffer
            return idx, res

    tasks = [worker(i, t) for i, t in enumerate(dialogue)]
    results = await asyncio.gather(*tasks)
    results.sort(key=lambda x: x[0])
    ordered_turns = [r[1] for r in results]

    print(f"[TTS] Assembling master audio track...")
    master_audio = AudioSegment.silent(duration=200)
    current_offset = 0.2
    all_chunks = []

    for idx, turn_res in enumerate(ordered_turns):
        speaker = turn_res["speaker"]
        turn_chunks = chunk_turn_words(
            turn_res["words"],
            speaker=speaker,
            global_turn_offset=current_offset,
            turn_duration=turn_res["duration"],
            max_words_per_line=config.MAX_WORDS_PER_LINE,
            max_chars_per_line=getattr(config, "MAX_CHARS_PER_LINE", 22)
        )
        for c in turn_chunks:
            c["turn_idx"] = idx
            c["en"] = turn_res.get("en", "")
            all_chunks.append(c)

        master_audio += turn_res["audio_segment"]
        pause_dur = int(config.PAUSE_BETWEEN_TURNS * 1000)
        master_audio += AudioSegment.silent(duration=pause_dur)
        current_offset += turn_res["duration"] + config.PAUSE_BETWEEN_TURNS

    master_path = os.path.join(config.OUTPUT_DIR, "master_podcast_audio.mp3")
    master_audio.export(master_path, format="mp3", bitrate="192k")
    total_duration = len(master_audio) / 1000.0
    print(f"[TTS] Master audio generated: {total_duration:.2f}s ({total_duration/60:.1f} mins)")
    return master_path, all_chunks, total_duration
