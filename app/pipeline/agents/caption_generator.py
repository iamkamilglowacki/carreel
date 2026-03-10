"""Generate an ASS subtitle file with Captions-app-style word-by-word animation.

Each word pops in with a scale animation and gets a colored highlight,
one or two words at a time, large and centered — similar to the Captions app.
"""

import logging
from typing import Any

from app.models import AgentResult, JobContext, PipelineStep
from app.pipeline.base import BaseAgent

logger = logging.getLogger(__name__)

PLAY_RES_X = 1080
PLAY_RES_Y = 1920

# How many words to show at once
WORDS_PER_GROUP = 2

# Highlight color (yellow-orange like Captions app) in ASS BGR: &H00aaFF = orange
HIGHLIGHT_COLOR = "&H0000CCFF"  # bright yellow-orange
NORMAL_COLOR = "&H00FFFFFF"     # white
SHADOW_COLOR = "&H80000000"     # semi-transparent black

ASS_HEADER = rf"""[Script Info]
ScriptType: v4.00+
PlayResX: {PLAY_RES_X}
PlayResY: {PLAY_RES_Y}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,Montserrat,90,{NORMAL_COLOR},{NORMAL_COLOR},&H00000000,{SHADOW_COLOR},-1,0,0,0,100,100,2,0,1,4,2,2,40,40,460,1
Style: WordActive,Montserrat,90,{HIGHLIGHT_COLOR},{HIGHLIGHT_COLOR},&H00000000,{SHADOW_COLOR},-1,0,0,0,100,100,2,0,1,4,2,2,40,40,460,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _format_ts(seconds: float) -> str:
    """Format seconds as ASS timestamp ``H:MM:SS.cc``."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _build_dialogue_lines(timestamps: list[dict[str, Any]]) -> list[str]:
    """Build ASS Dialogue lines with Captions-style word animation.

    For each group of words:
    - All words show in white
    - The currently spoken word gets highlighted in color with a pop-in scale effect
    """
    lines: list[str] = []

    # Group words into display groups (1-2 words at a time)
    groups: list[list[dict[str, Any]]] = []
    for i in range(0, len(timestamps), WORDS_PER_GROUP):
        groups.append(timestamps[i : i + WORDS_PER_GROUP])

    for group in groups:
        group_start = group[0]["start"]
        group_end = group[-1]["end"]

        # Build the full display text for this group
        upper_words = [w["word"].upper() for w in group]
        full_text = " ".join(upper_words)

        for word_idx, ts in enumerate(group):
            w_start = ts["start"]
            w_end = ts["end"]
            word_upper = ts["word"].upper()

            # Pop-in animation: scale from 85% to 105% then settle at 100%
            # \t(t1,t2,\fscx105\fscy105) then \t(t2,t3,\fscx100\fscy100)
            pop_duration = min(80, (w_end - w_start) * 1000 * 0.3)

            # Build text with inline color override for the active word
            parts = []
            for j, w in enumerate(upper_words):
                if j == word_idx:
                    # Active word: highlight color + pop scale
                    parts.append(
                        rf"{{\c{HIGHLIGHT_COLOR}\fscx85\fscy85"
                        rf"\t(0,{pop_duration:.0f},\fscx107\fscy107)"
                        rf"\t({pop_duration:.0f},{pop_duration * 2:.0f},\fscx100\fscy100)"
                        rf"}}{w}"
                    )
                else:
                    # Inactive word: white, normal scale
                    parts.append(rf"{{\c{NORMAL_COLOR}\fscx100\fscy100}}{w}")

            text = " ".join(parts)

            lines.append(
                f"Dialogue: 1,{_format_ts(w_start)},{_format_ts(w_end)},Word,,0,0,0,,{text}"
            )

        # Also show the group text in white as a base layer during gaps
        # (prevents flicker between words in the same group)
        base_text = rf"{{\c{NORMAL_COLOR}}}" + full_text
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
