"""
Structured logging system for GGRevealer
Provides logging with different levels and database persistence
"""

import json
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class LogLevel(Enum):
    """Log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Logger:
    """Structured logger with console and database output"""

    def __init__(self, job_id: Optional[int] = None):
        self.job_id = job_id
        self.logs_buffer = []  # Buffer logs for later persistence

    def _format_message(self, level: LogLevel, message: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Format log entry as structured dict"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level.value,
            "message": message,
            "job_id": self.job_id
        }

        if extra:
            log_entry["extra"] = extra

        return log_entry

    def _print_console(self, level: LogLevel, message: str, extra: Optional[Dict[str, Any]] = None):
        """Print formatted log to console"""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        job_prefix = f"[JOB {self.job_id}]" if self.job_id else "[SYSTEM]"

        # Color codes for different levels
        colors = {
            LogLevel.DEBUG: "\033[36m",      # Cyan
            LogLevel.INFO: "\033[32m",       # Green
            LogLevel.WARNING: "\033[33m",    # Yellow
            LogLevel.ERROR: "\033[31m",      # Red
            LogLevel.CRITICAL: "\033[35m"    # Magenta
        }
        reset = "\033[0m"

        color = colors.get(level, "")
        level_str = f"{color}[{level.value}]{reset}"

        # Build console message
        console_msg = f"{timestamp} {job_prefix} {level_str} {message}"

        # Add extra data if present
        if extra:
            console_msg += f" | {json.dumps(extra, ensure_ascii=False)}"

        print(console_msg, file=sys.stdout)

    def _save_to_buffer(self, log_entry: Dict[str, Any]):
        """Save log entry to buffer for later persistence"""
        self.logs_buffer.append(log_entry)

    def debug(self, message: str, **extra):
        """Log DEBUG level message"""
        log_entry = self._format_message(LogLevel.DEBUG, message, extra or None)
        self._print_console(LogLevel.DEBUG, message, extra or None)
        self._save_to_buffer(log_entry)

    def info(self, message: str, **extra):
        """Log INFO level message"""
        log_entry = self._format_message(LogLevel.INFO, message, extra or None)
        self._print_console(LogLevel.INFO, message, extra or None)
        self._save_to_buffer(log_entry)

    def warning(self, message: str, **extra):
        """Log WARNING level message"""
        log_entry = self._format_message(LogLevel.WARNING, message, extra or None)
        self._print_console(LogLevel.WARNING, message, extra or None)
        self._save_to_buffer(log_entry)

    def error(self, message: str, **extra):
        """Log ERROR level message"""
        log_entry = self._format_message(LogLevel.ERROR, message, extra or None)
        self._print_console(LogLevel.ERROR, message, extra or None)
        self._save_to_buffer(log_entry)

    def critical(self, message: str, **extra):
        """Log CRITICAL level message"""
        log_entry = self._format_message(LogLevel.CRITICAL, message, extra or None)
        self._print_console(LogLevel.CRITICAL, message, extra or None)
        self._save_to_buffer(log_entry)

    def get_logs(self) -> list:
        """Get all buffered logs"""
        return self.logs_buffer

    def flush_to_db(self):
        """Persist buffered logs to database"""
        if not self.job_id or not self.logs_buffer:
            return

        # Import here to avoid circular dependency
        from database import save_logs_batch

        try:
            save_logs_batch(self.job_id, self.logs_buffer)
            self.logs_buffer.clear()
        except Exception as e:
            print(f"Failed to persist logs to database: {e}", file=sys.stderr)


# Global logger for system-level logs
system_logger = Logger()


def get_job_logger(job_id: int) -> Logger:
    """Get a logger instance for a specific job"""
    return Logger(job_id)
