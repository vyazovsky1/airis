import os


class AnalyzerConfig:
    # Default lines to include per file in batch analysis
    BATCH_LINES = int(os.environ.get("BATCH_LINES", 100))
    # Lines to include for files that contain resource signals
    BATCH_SIGNAL_LINES = int(os.environ.get("BATCH_SIGNAL_LINES", 250))


analyzer_config = AnalyzerConfig()
