import numpy as np
from pydub import AudioSegment
from PIL import ImageDraw
import config

class AudioSpectrumVisualizer:
    def __init__(self, audio_path: str, fps: int = 30):
        self.fps = fps
        self.audio_path = audio_path
        self.num_bars = config.VIS_NUM_BARS
        self.min_height = config.VIS_MIN_HEIGHT
        self.max_height = config.VIS_MAX_HEIGHT
        self.center_x = config.VIS_CENTER_X
        self.base_y = config.VIS_BASE_Y
        self.bar_width = config.VIS_BAR_WIDTH
        self.bar_spacing = config.VIS_BAR_SPACING
        self.color = config.VIS_COLOR
        self._precompute_spectrum()

    def _precompute_spectrum(self):
        seg = AudioSegment.from_file(self.audio_path)
        samples = np.array(seg.get_array_of_samples(), dtype=np.float32)
        if seg.channels == 2:
            samples = samples.reshape((-1, 2)).mean(axis=1)

        sr = seg.frame_rate
        total_duration = len(samples) / float(sr)
        self.total_frames = int(np.ceil(total_duration * self.fps))

        win_size = 2048
        half_win = win_size // 2
        hanning = np.hanning(win_size)

        freqs = np.fft.rfftfreq(win_size, 1.0 / sr)
        valid_indices = np.where((freqs >= 100) & (freqs <= 4500))[0]
        band_edges = np.logspace(np.log10(valid_indices[0]), np.log10(valid_indices[-1]), self.num_bars + 1).astype(int)

        raw_frames = np.zeros((self.total_frames, self.num_bars), dtype=np.float32)

        for frame_idx in range(self.total_frames):
            center_sample = int(frame_idx * (sr / self.fps))
            start_sample = max(0, center_sample - half_win)
            end_sample = min(len(samples), start_sample + win_size)

            chunk = samples[start_sample:end_sample]
            if len(chunk) < win_size:
                chunk = np.pad(chunk, (0, win_size - len(chunk)))

            fft_vals = np.abs(np.fft.rfft(chunk * hanning))

            for b in range(self.num_bars):
                low_idx = band_edges[b]
                high_idx = max(low_idx + 1, band_edges[b + 1])
                val = np.mean(fft_vals[low_idx:high_idx])
                raw_frames[frame_idx, b] = val

        p95 = np.percentile(raw_frames, 95)
        norm_frames = (raw_frames / p95) if p95 > 0 else raw_frames
        norm_frames = np.clip(norm_frames, 0.0, 1.8)

        smoothed = np.zeros_like(norm_frames)
        prev_vals = np.zeros(self.num_bars, dtype=np.float32)

        for f in range(self.total_frames):
            curr = norm_frames[f]
            center_weight = 0.75 + 0.4 * np.sin(np.linspace(0, np.pi, self.num_bars))
            curr = curr * center_weight

            for b in range(self.num_bars):
                if curr[b] > prev_vals[b]:
                    prev_vals[b] = prev_vals[b] * 0.35 + curr[b] * 0.65
                else:
                    prev_vals[b] = prev_vals[b] * 0.75 + curr[b] * 0.25
            smoothed[f] = prev_vals

        self.heights = self.min_height + (smoothed * (self.max_height - self.min_height)).astype(int)
        self.heights = np.clip(self.heights, self.min_height, self.max_height)

    def draw_frame(self, draw: ImageDraw.ImageDraw, frame_idx: int):
        if frame_idx >= len(self.heights):
            h_vals = np.full(self.num_bars, self.min_height)
        else:
            h_vals = self.heights[frame_idx]

        total_w = self.num_bars * self.bar_width + (self.num_bars - 1) * self.bar_spacing
        start_x = self.center_x - (total_w // 2)

        # Plate pill container
        plate_w = total_w + 50
        plate_h = self.max_height + 22
        draw.rounded_rectangle([
            (self.center_x - plate_w // 2, self.base_y - plate_h // 2),
            (self.center_x + plate_w // 2, self.base_y + plate_h // 2)
        ], radius=16, fill=(14, 16, 26, 220), outline=(255, 215, 0, 180), width=2)

        for b in range(self.num_bars):
            bh = int(h_vals[b])
            bx = start_x + b * (self.bar_width + self.bar_spacing)
            by_top = self.base_y - (bh // 2)
            by_bot = self.base_y + (bh // 2)
            draw.rounded_rectangle([(bx, by_top), (bx + self.bar_width, by_bot)], radius=6, fill=self.color)
