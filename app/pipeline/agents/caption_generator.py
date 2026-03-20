"""Generate an ASS subtitle file with premium word-by-word animation.

Inspired by Captions/CapCut/Submagic — each word pops in with a bouncy
scale + color animation, displayed on a pill-shaped semi-transparent
background, 3-4 words at a time with dynamic grouping.
"""

import logging
import math
from pathlib import Path
from typing import Any

from app.models import AgentResult, JobContext, PipelineStep
from app.pipeline.base import BaseAgent

logger = logging.getLogger(__name__)

PLAY_RES_X = 1080
PLAY_RES_Y = 1920

# --- Dynamic grouping config ---
# Target 3-4 words per group, but adapt to word lengths
MAX_CHARS_PER_GROUP = 22  # max characters before forcing a new group
MAX_WORDS_PER_GROUP = 4
MIN_WORDS_PER_GROUP = 2

# --- Colors (ASS BGR format) ---
HIGHLIGHT_COLOR = "&H0000DDFF"   # warm amber/gold
NORMAL_COLOR = "&H00FFFFFF"      # white
OUTLINE_COLOR = "&H40000000"     # subtle dark outline
BOX_COLOR = "&HC0000000"         # pill background: 75% opaque black

# --- Font config ---
FONT_NAME = "Montserrat"
FONT_SIZE = 68

# Resolve bundled font file for FFmpeg fontsdir
_FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "fonts"


def get_fonts_dir() -> Path:
    """Return the path to the bundled fonts directory."""
    return _FONTS_DIR


ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {PLAY_RES_X}
PlayResY: {PLAY_RES_Y}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Box,{FONT_NAME},{FONT_SIZE},{NORMAL_COLOR},{NORMAL_COLOR},{OUTLINE_COLOR},{BOX_COLOR},-1,0,0,0,100,100,2,0,3,4,0,5,60,60,440,1
Style: Word,{FONT_NAME},{FONT_SIZE},{NORMAL_COLOR},{NORMAL_COLOR},{OUTLINE_COLOR},{BOX_COLOR},-1,0,0,0,100,100,2,0,3,4,0,5,60,60,440,1
Style: WordActive,{FONT_NAME},{FONT_SIZE},{HIGHLIGHT_COLOR},{HIGHLIGHT_COLOR},{OUTLINE_COLOR},{BOX_COLOR},-1,0,0,0,100,100,2,0,3,4,0,5,60,60,440,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _format_ts(seconds: float) -> str:
    """Format seconds as ASS timestamp ``H:MM:SS.cc``."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _group_words(timestamps: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Dynamically group words based on character count and word count.

    Aims for natural reading chunks of 3-4 words, breaking earlier
    if the total character count exceeds MAX_CHARS_PER_GROUP.
    """
    groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = []
    current_chars = 0

    for ts in timestamps:
        word_len = len(ts["word"])

        # Check if adding this word would exceed limits
        would_exceed_chars = (current_chars + word_len + (1 if current_group else 0)) > MAX_CHARS_PER_GROUP
        would_exceed_words = len(current_group) >= MAX_WORDS_PER_GROUP

        if current_group and (would_exceed_chars or would_exceed_words):
            groups.append(current_group)
            current_group = []
            current_chars = 0

        current_group.append(ts)
        current_chars += word_len + (1 if len(current_group) > 1 else 0)

    if current_group:
        # Avoid single-word orphan at end — merge with previous group
        if len(current_group) == 1 and len(groups) > 0 and len(groups[-1]) < MAX_WORDS_PER_GROUP:
            groups[-1].extend(current_group)
        else:
            groups.append(current_group)

    return groups


def _build_dialogue_lines(timestamps: list[dict[str, Any]]) -> list[str]:
    """Build ASS Dialogue lines with premium word-by-word animation.

    For each group of words:
    - Pill-shaped background (via BorderStyle 3 = opaque box)
    - Active word highlighted in gold with bouncy pop-in (overshoot + settle)
    - Inactive words in white at normal scale
    """
    lines: list[str] = []
    groups = _group_words(timestamps)

    for group in groups:
        group_start = group[0]["start"]
        group_end = group[-1]["end"]

        upper_words = [w["word"].upper() for w in group]

        for word_idx, ts in enumerate(group):
            w_start = ts["start"]
            w_end = ts["end"]
            word_duration_ms = (w_end - w_start) * 1000

            # Bouncy pop animation timing
            # Phase 1: quick scale up (overshoot) — ~30% of word duration, max 100ms
            pop_up = min(100, word_duration_ms * 0.3)
            # Phase 2: settle back — ~20% of word duration, max 80ms
            pop_settle = min(80, word_duration_ms * 0.2)

            # Build text with inline overrides for each word
            parts = []
            for j, w in enumerate(upper_words):
                if j == word_idx:
                    # Active word: gold color + bouncy scale (80% → 112% → 100%)
                    parts.append(
                        rf"{{\c{HIGHLIGHT_COLOR}\fscx80\fscy80"
                        rf"\t(0,{pop_up:.0f},\fscx112\fscy112)"
                        rf"\t({pop_up:.0f},{pop_up + pop_settle:.0f},\fscx100\fscy100)"
                        rf"}}{w}"
                    )
                else:
                    # Inactive word: white, steady
                    parts.append(rf"{{\c{NORMAL_COLOR}\fscx100\fscy100}}{w}")

            text = " ".join(parts)

            # Layer 1: active word animation line
            lines.append(
                f"Dialogue: 1,{_format_ts(w_start)},{_format_ts(w_end)},Word,,0,0,0,,{text}"
            )

        # Layer 0: base group text — prevents flicker between word transitions
        base_parts = []
        for w in upper_words:
            base_parts.append(rf"{{\c{NORMAL_COLOR}\fscx100\fscy100}}{w}")
        base_text = " ".join(base_parts)
        lines.append(
            f"Dialogue: 0,{_format_ts(group_start)},{_format_ts(group_end)},Word,,0,0,0,,{base_text}"
        )

    return lines


class CaptionGenerator(BaseAgent):
    @property
    def step(self) -> PipelineStep:
        return PipelineStep.CAPTION_GENERATE

    async def process(self, ctx: JobContext) -> AgentResult:
        if not ctx.timestamps:
            return AgentResult(
                success=False, step=self.step, message="No timestamps available"
            )

        dialogue_lines = _build_dialogue_lines(ctx.timestamps)
        ass_content = ASS_HEADER.lstrip() + "\n".join(dialogue_lines) + "\n"

        captions_path = ctx.job_dir / "captions.ass"
        captions_path.write_text(ass_content, encoding="utf-8")
        logger.info("Wrote %d dialogue lines to %s", len(dialogue_lines), captions_path)

        ctx.captions_path = captions_path
        return AgentResult(
            success=True,
            step=self.step,
            message=f"Generated captions ({len(dialogue_lines)} dialogue events)",
        )
