"""
FR-10: Structured Logging with Trace IDs
Provides correlation IDs for request/call/error tracking
"""
import logging
import json
import uuid
from datetime import datetime
from typing import Optional, Any, Dict
from contextvars import ContextVar

# Context variable to store trace ID across async calls
trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)

class StructuredLogger:
    """Logger that outputs JSON-formatted logs with trace IDs"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # Only add handler if not already present
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(handler)

    def _format_log(self, level: str, message: str, **kwargs) -> str:
        """Format log entry as JSON with trace ID"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": message,
            "trace_id": trace_id_var.get(),
            **kwargs
        }
        return json.dumps(log_entry)

    def info(self, message: str, **kwargs):
        """Log info level message"""
        self.logger.info(self._format_log("INFO", message, **kwargs))

    def error(self, message: str, **kwargs):
        """Log error level message"""
        self.logger.error(self._format_log("ERROR", message, **kwargs))

    def warning(self, message: str, **kwargs):
        """Log warning level message"""
        self.logger.warning(self._format_log("WARNING", message, **kwargs))

    def debug(self, message: str, **kwargs):
        """Log debug level message"""
        self.logger.debug(self._format_log("DEBUG", message, **kwargs))


class TraceContext:
    """Context manager for setting trace IDs"""

    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.token = None

    def __enter__(self):
        self.token = trace_id_var.set(self.trace_id)
        return self.trace_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        trace_id_var.reset(self.token)


def set_trace_id(trace_id: str):
    """Manually set trace ID for current context"""
    trace_id_var.set(trace_id)


def get_trace_id() -> Optional[str]:
    """Get current trace ID"""
    return trace_id_var.get()


def generate_trace_id() -> str:
    """Generate new trace ID (UUID)"""
    return str(uuid.uuid4())
