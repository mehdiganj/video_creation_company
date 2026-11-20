class VideogenError(Exception):
    """Base error for problems that should print a clean message, not a traceback."""


class ConfigError(VideogenError):
    """A project/brand YAML file is missing, malformed, or references a missing asset."""


class RenderError(VideogenError):
    """ffmpeg, the TTS provider, or a compositing step failed."""


class MissingDependencyError(VideogenError):
    """A required binary (ffmpeg) or credential (AZURE_SPEECH_KEY) is not available."""
