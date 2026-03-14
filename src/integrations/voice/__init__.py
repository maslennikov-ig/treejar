"""Voice message processing utilities."""

from src.integrations.voice.voxtral import MAX_AUDIO_SIZE, transcribe_audio

__all__ = ["transcribe_audio", "MAX_AUDIO_SIZE"]
