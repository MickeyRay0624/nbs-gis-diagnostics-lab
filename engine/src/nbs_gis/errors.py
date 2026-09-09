class NbsGisError(Exception):
    """Base exception for expected NbS GIS failures."""


class ConfigError(NbsGisError):
    """Raised when the analysis configuration is invalid."""


class PreflightBlocked(NbsGisError):
    """Raised when mandatory preflight checks do not pass."""


class PipelineError(NbsGisError):
    """Raised when deterministic GIS processing cannot continue."""
