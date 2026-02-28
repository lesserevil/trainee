"""Rolling context accumulator.

Stores frame descriptions and audio transcripts, compressing older content
into a summary every N frames to keep the context window manageable.
"""

from __future__ import annotations

import asyncio


class ContextAccumulator:
    def __init__(self, vlm, compress_every: int = 10) -> None:
        self._vlm = vlm
        self._compress_every = compress_every
        self._rolling_summary: str = ""          # Compressed summary of older frames
        self._recent_frames: list[str] = []      # Raw descriptions of recent frames
        self._transcripts: list[str] = []        # Audio transcript segments
        self._frame_count = 0

    async def add_frame(self, description: str, loop: asyncio.AbstractEventLoop) -> None:
        """Add a new frame description and compress if threshold is reached."""
        self._recent_frames.append(description)
        self._frame_count += 1

        if len(self._recent_frames) >= self._compress_every:
            await self._compress(loop)

    def add_transcript(self, text: str) -> None:
        if text.strip():
            self._transcripts.append(text.strip())

    async def _compress(self, loop: asyncio.AbstractEventLoop) -> None:
        """Compress recent frames into the rolling summary via a VLM call."""
        new_content = "\n".join(self._recent_frames)
        print(f"[context] Compressing {len(self._recent_frames)} frames into summary...")
        new_summary = await loop.run_in_executor(
            None, self._vlm.compress_context, self._rolling_summary, new_content
        )
        self._rolling_summary = new_summary
        self._recent_frames = []

    def get_summary(self, max_recent: int = 5, max_transcripts: int = 3) -> str:
        """Return the full accumulated context as a formatted string."""
        parts: list[str] = []

        if self._rolling_summary:
            parts.append(f"[Course summary]\n{self._rolling_summary}")

        if self._recent_frames:
            recent = self._recent_frames[-max_recent:]
            parts.append(f"[Recent content]\n" + "\n".join(recent))

        if self._transcripts:
            recent_t = self._transcripts[-max_transcripts:]
            parts.append(f"[Audio transcripts]\n" + "\n".join(recent_t))

        return "\n\n".join(parts) if parts else "No course content captured yet."

    @property
    def frame_count(self) -> int:
        return self._frame_count
