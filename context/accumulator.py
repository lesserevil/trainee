"""Rolling context accumulator.

Stores frame descriptions and audio transcripts, compressing older content
into a summary every N frames to keep the context window manageable.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ContextAccumulator:
    def __init__(
        self,
        vlm,
        compress_every: int = 10,
        knowledge_base_path: str | Path | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        self._vlm = vlm
        self._compress_every = compress_every
        self._rolling_summary: str = ""          # Compressed summary of older frames
        self._recent_frames: list[str] = []      # Raw descriptions of recent frames
        self._transcripts: list[str] = []        # Recent uncompressed audio segments
        self._frame_history: list[tuple[int, str]] = []
        self._transcript_history: list[tuple[int, str]] = []
        self._frame_count = 0
        self._knowledge_base_path = (
            Path(knowledge_base_path).expanduser() if knowledge_base_path else None
        )
        self._metadata = dict(metadata or {})
        self._started_at = _utc_timestamp()
        self._status = "running"
        self._write_warning_shown = False
        self.write_knowledge_base()

    async def add_frame(self, description: str, loop: asyncio.AbstractEventLoop) -> None:
        """Add a new frame description and compress if threshold is reached."""
        self._recent_frames.append(description)
        self._frame_count += 1
        self._frame_history.append((self._frame_count, description))

        if len(self._recent_frames) >= self._compress_every:
            await self._compress(loop)

        self.write_knowledge_base()

    def add_transcript(self, text: str) -> None:
        clean = text.strip()
        if clean:
            self._transcripts.append(clean)
            self._transcript_history.append((len(self._transcript_history) + 1, clean))
            self.write_knowledge_base()

    async def _compress(self, loop: asyncio.AbstractEventLoop) -> None:
        """Compress recent frames into the rolling summary via a VLM call."""
        parts: list[str] = []
        if self._recent_frames:
            parts.append("[Visual frame notes]\n" + "\n".join(self._recent_frames))
        if self._transcripts:
            parts.append("[Audio transcript segments]\n" + "\n".join(self._transcripts))

        new_content = "\n\n".join(parts)
        print(
            f"[context] Compressing {len(self._recent_frames)} frames and "
            f"{len(self._transcripts)} transcript segments into summary..."
        )
        new_summary = await loop.run_in_executor(
            None, self._vlm.compress_context, self._rolling_summary, new_content
        )
        self._rolling_summary = new_summary
        self._recent_frames = []
        self._transcripts = []
        print(f"\n[context] Knowledge base updated:\n{new_summary}\n")

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

    def mark_finished(self, status: str = "finished") -> None:
        """Record the final session status and flush the knowledge base file."""
        self._status = status
        self.write_knowledge_base()

    @property
    def knowledge_base_path(self) -> Path | None:
        return self._knowledge_base_path

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def write_knowledge_base(self) -> None:
        """Write the current knowledge base as Markdown, if configured."""
        if self._knowledge_base_path is None:
            return

        path = self._knowledge_base_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_name(path.name + ".tmp")
            tmp_path.write_text(self.to_markdown(), encoding="utf-8")
            tmp_path.replace(path)
        except OSError as exc:
            if not self._write_warning_shown:
                print(f"[knowledge] Warning: could not write {path}: {exc}")
                self._write_warning_shown = True

    def to_markdown(self) -> str:
        """Render the current knowledge base as a Markdown document."""
        lines: list[str] = [
            "# trainee Knowledge Base",
            "",
            "## Run Metadata",
            "",
            f"- Status: {self._status}",
            f"- Started: {self._started_at}",
            f"- Last updated: {_utc_timestamp()}",
            f"- Frames analyzed: {self._frame_count}",
            f"- Transcript segments captured: {len(self._transcript_history)}",
        ]

        for key, value in self._metadata.items():
            if value:
                lines.append(f"- {key}: {value}")

        lines.extend([
            "",
            "## Current Quiz Context",
            "",
            "This is the context trainee currently uses when answering quizzes.",
            "",
            self.get_summary(),
            "",
            "## Compressed Course Summary",
            "",
            self._rolling_summary or "No compressed course summary yet.",
            "",
            "## Recent Uncompressed Visual Notes",
            "",
        ])

        if self._recent_frames:
            start = self._frame_count - len(self._recent_frames) + 1
            for offset, text in enumerate(self._recent_frames):
                lines.extend([f"### Frame {start + offset}", "", text, ""])
        else:
            lines.extend(["No uncompressed visual notes.", ""])

        lines.extend(["## Recent Uncompressed Audio Transcripts", ""])
        if self._transcripts:
            start = len(self._transcript_history) - len(self._transcripts) + 1
            for offset, text in enumerate(self._transcripts):
                lines.extend([f"### Transcript Segment {start + offset}", "", text, ""])
        else:
            lines.extend(["No uncompressed audio transcripts.", ""])

        lines.extend(["## Appendix: All Visual Frame Notes", ""])
        if self._frame_history:
            for frame_num, text in self._frame_history:
                lines.extend([f"### Frame {frame_num}", "", text, ""])
        else:
            lines.extend(["No visual frame notes captured yet.", ""])

        lines.extend(["## Appendix: All Audio Transcript Segments", ""])
        if self._transcript_history:
            for segment_num, text in self._transcript_history:
                lines.extend([f"### Transcript Segment {segment_num}", "", text, ""])
        else:
            lines.extend(["No audio transcript segments captured yet.", ""])

        return "\n".join(lines).rstrip() + "\n"
