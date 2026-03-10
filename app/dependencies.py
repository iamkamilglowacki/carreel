"""Agent factory -- build the pipeline agent list based on config."""

from app.config import settings
from app.pipeline.base import BaseAgent


def build_agents() -> list[BaseAgent]:
    agents: list[BaseAgent] = []

    # Transcriber
    if settings.transcriber_provider == "mock":
        from app.pipeline.mocks.mock_transcriber import MockTranscriber

        agents.append(MockTranscriber())
    elif settings.transcriber_provider == "elevenlabs":
        from app.pipeline.agents.elevenlabs_transcriber import ElevenLabsTranscriber

        agents.append(ElevenLabsTranscriber())

    # Scriptwriter
    if settings.scriptwriter_provider == "mock":
        from app.pipeline.mocks.mock_scriptwriter import MockScriptwriter

        agents.append(MockScriptwriter())

    # Voiceover
    if settings.voiceover_provider == "mock":
        from app.pipeline.mocks.mock_voiceover import MockVoiceover

        agents.append(MockVoiceover())
    elif settings.voiceover_provider == "elevenlabs":
        from app.pipeline.agents.elevenlabs_voiceover import ElevenLabsVoiceover

        agents.append(ElevenLabsVoiceover())

    # FFmpeg-based agents (always real)
    from app.pipeline.agents.media_processor import MediaProcessor
    from app.pipeline.agents.caption_generator import CaptionGenerator
    from app.pipeline.agents.video_assembler import VideoAssembler

    agents.extend([MediaProcessor(), CaptionGenerator(), VideoAssembler()])
    return agents
