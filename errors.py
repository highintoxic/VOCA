"""
errors.py — Custom exception classes for the Voca pipeline.
"""

class PipelineError(Exception):
    """
    Exception raised when a pipeline stage encounters a hard failure.

    Attributes:
        stage (str): The name of the stage (e.g., "stt", "intent", "tool").
        message (str): A user-friendly error message.
    """
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.message = message
