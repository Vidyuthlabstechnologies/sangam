"""Phone audio helpers: 8 kHz 16-bit mono PCM, WAV wrapping, simple voice detection."""
from __future__ import annotations

import io
import math
import struct
import wave
from dataclasses import dataclass, field

RATE = 8000
SAMPLE_BYTES = 2
FRAME_MS = 20
FRAME_BYTES = RATE * SAMPLE_BYTES * FRAME_MS // 1000  # 320


def pcm_to_wav(pcm: bytes, rate: int = RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(SAMPLE_BYTES)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def wav_to_pcm(data: bytes, target_rate: int = RATE) -> bytes:
    """Decode a WAV (any rate, mono or stereo, 16-bit) into mono PCM at target_rate."""
    with wave.open(io.BytesIO(data), "rb") as w:
        channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        frames = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError("only 16-bit WAV is supported")
    samples = list(struct.unpack(f"<{len(frames) // 2}h", frames))
    if channels == 2:
        samples = [(samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples) - 1, 2)]
    if rate != target_rate:
        samples = resample(samples, rate, target_rate)
    return struct.pack(f"<{len(samples)}h", *samples)


def resample(samples: list[int], src: int, dst: int) -> list[int]:
    """Linear interpolation. Fine for speech on a phone line."""
    if not samples or src == dst:
        return samples
    n = int(len(samples) * dst / src)
    out = []
    step = src / dst
    for i in range(n):
        pos = i * step
        j = int(pos)
        frac = pos - j
        a = samples[j]
        b = samples[j + 1] if j + 1 < len(samples) else a
        out.append(int(a + (b - a) * frac))
    return out


def rms(frame: bytes) -> float:
    count = len(frame) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", frame[: count * 2])
    return math.sqrt(sum(s * s for s in samples) / count)


def chunks(pcm: bytes, size: int = FRAME_BYTES * 10) -> list[bytes]:
    """Split PCM into chunks that are multiples of 320 bytes (what phone streams expect)."""
    out = [pcm[i:i + size] for i in range(0, len(pcm), size)]
    if out and len(out[-1]) % FRAME_BYTES:
        out[-1] = out[-1] + b"\x00" * (FRAME_BYTES - len(out[-1]) % FRAME_BYTES)
    return out


@dataclass
class UtteranceDetector:
    """Collects caller audio and says when they have finished a sentence.

    Energy-based: speech is a 20 ms frame louder than `threshold`. An utterance
    ends after `silence_ms` of quiet following at least `min_speech_ms` of speech.
    """
    threshold: float = 450.0
    silence_ms: int = 800
    min_speech_ms: int = 300
    max_ms: int = 15000
    _buf: bytearray = field(default_factory=bytearray)
    _pending: bytearray = field(default_factory=bytearray)
    _speech_ms: int = 0
    _silence_ms: int = 0
    speaking: bool = False

    def feed(self, pcm: bytes) -> list[bytes]:
        """Add audio; return any finished utterances."""
        done: list[bytes] = []
        self._pending.extend(pcm)
        while len(self._pending) >= FRAME_BYTES:
            frame = bytes(self._pending[:FRAME_BYTES])
            del self._pending[:FRAME_BYTES]
            loud = rms(frame) >= self.threshold
            if loud:
                self.speaking = True
                self._speech_ms += FRAME_MS
                self._silence_ms = 0
                self._buf.extend(frame)
            elif self.speaking:
                self._silence_ms += FRAME_MS
                self._buf.extend(frame)
            total_ms = len(self._buf) * 1000 // (RATE * SAMPLE_BYTES)
            if self.speaking and (self._silence_ms >= self.silence_ms or total_ms >= self.max_ms):
                if self._speech_ms >= self.min_speech_ms:
                    done.append(bytes(self._buf))
                self.reset()
        return done

    def reset(self) -> None:
        self._buf.clear()
        self._speech_ms = 0
        self._silence_ms = 0
        self.speaking = False
