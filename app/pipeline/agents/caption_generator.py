"""Generate an ASS subtitle file with word-by-word highlight animation.

Uses ASS drawing mode to render rounded-rectangle backgrounds behind
the currently spoken word.
"""

import logging
from typing import Any

from app.models import AgentResult, JobContext, PipelineStep
from app.pipeline.base import BaseAgent

logger = logging.getLogger(__name__)

# Resolution constants (must match ffmpeg output)
PLAY_RES_X = 1080
PLAY_RES_Y = 1920

ASS_HEADER = r"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,2,60,60,500,1
Style: Box,Arial,1,&H0000CCFF,&H0000CCFF,&H0000CCFF,&H0000CCFF,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

WORDS_PER_LINE = 3

# Approximate character width for Arial Bold 60pt (uppercase) in ASS coords.
# This is an empirical value — tweak if highlights are misaligned.
CHAR_WIDTH = 37
SPACE_WIDTH = 18
FONT_HEIGHT = 64
PAD_X = 16
PAD_Y = 10
RADIUS = 18
MARGIN_V = 500
MARGIN_H = 60


def _format_ts(seconds: float) -> str:
    """Format seconds as ASS timestamp ``H:MM:SS.cc``."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _rounded_rect(w: int, h: int, r: int) -> str:
    """Return an ASS drawing-mode path for a rounded rectangle.

    Origin is top-left (0, 0), size is w x h, corner radius r.
    Uses cubic Bezier curves (``b`` command) for rounded corners.
    """
    r = min(r, w // 2, h // 2)
    # ASS drawing: m = move, l = line, b = cubic bezier
    return (
        f"m {r} 0 "
        f"l {w - r} 0 "
        f"b {w} 0 {w} 0 {w} {r} "
        f"l {w} {h - r} "
        f"b {w} {h} {w} {h} {w - r} {h} "
        f"l {r} {h} "
        f"b 0 {h} 0 {h} 0 {h - r} "
        f"l 0 {r} "
        f"b 0 0 0 0 {r} 0"
    )


def _estimate_word_width(word: str) -> int:
    """Rough pixel width of an uppercase word in the configured font."""
    return len(word) * CHAR_WIDTH


def _build_dialogue_lines(timestamps: list[dict[str, Any]]) -> list[str]:
    """Build ASS Dialogue lines with word-by-word rounded-rect highlight.

    For each word's time interval two events are emitted:
      - Layer 0: a rounded-rectangle background shape (Box style + \\p1 drawing)
      - Layer 1: the full text line with the current word in white (Default style)
    """
    lines: list[str] = []

    # Group words into display lines
    groups: list[list[dict[str, Any]]] = []
    for i in range(0, len(timestamps), WORDS_PER_LINE):
        groups.append(timestamps[i : i + WORDS_PER_LINE])

    for group in groups:
        upper_words = [w["word"].upper() for w in group]

        # Total line width (for centering calculations)
        word_widths = [_estimate_word_width(w) for w in upper_words]
        total_line_w = sum(word_widths) + SPACE_WIDTH * (len(upper_words) - 1)

        # Line is bottom-center aligned (Alignment=2, MarginV=500)
        # Baseline Y in script coords
        line_y = PLAY_RES_Y - MARGIN_V
        line_x_start = (PLAY_RES_X - total_line_w) // 2

        for idx, ts in enumerate(group):
            start = _format_ts(ts["start"])
            end = _format_ts(ts["end"])

            # --- Layer 1: text line (all words white) ---
            text = " ".join(upper_words)
            lines.append(
                f"Dialogue: 1,{start},{end},Default,,0,0,0,,{text}"
            )

            # --- Layer 0: rounded-rect highlight behind current word ---
            # Compute x offset of the highlighted word
            x_offset = line_x_start
            for j in range(idx):
                x_offset += word_widths[j] + SPACE_WIDTH

            ww = word_widths[idx]
            box_x = x_offset - PAD_X
            box_y = line_y - FONT_HEIGHT - PAD_Y
            box_w = ww + PAD_X * 2
            box_h = FONT_HEIGHT + PAD_Y * 2

            shape = _rounded_rect(box_w, box_h, RADIUS)
            pos_tag = rf"{{\pos({box_x},{box_y})\p1}}"
            lines.append(
                f"Dialogue: 0,{start},{end},Box,,0,0,0,,{pos_tag}{shape}"
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
