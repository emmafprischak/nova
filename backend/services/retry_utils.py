"""
FR-11: Retry Logic & Circuit Breakers
Resilient API client utilities with exponential backoff
"""
import asyncio
import httpx
from typing import Callable, Any, Optional
from datetime import datetime, timedelta
from backend.services.logger import StructuredLogger

logger = StructuredLogger(__name__)


# Circuit breaker state
class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail immediately
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def record_success(self):
        """Record successful request"""
        self.failure_count = 0

        if self.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._close_circuit()

    def record_failure(self):
        """Record failed request"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        self.success_count = 0

        if self.failure_count >= self.failure_threshold:
            self._open_circuit()

    def can_attempt(self) -> bool:
        """Check if request should be attempted"""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            # Check if recovery timeout has passed
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self._half_open_circuit()
                    return True
            return False

        # HALF_OPEN state
        return True

    def _open_circuit(self):
        """Open circuit due to failures"""
        self.state = "OPEN"
        logger.warning(
            "Circuit breaker opened",
            failure_count=self.failure_count,
            recovery_timeout_seconds=self.recovery_timeout
        )

    def _half_open_circuit(self):
        """Enter half-open state to test recovery"""
        self.state = "HALF_OPEN"
        self.success_count = 0
        logger.info("Circuit breaker half-open - testing recovery")

    def _close_circuit(self):
        """Close circuit after successful recovery"""
        self.state = "CLOSED"
        self.failure_count = 0
        self.success_count = 0
        logger.info("Circuit breaker closed - service recovered")


# Global circuit breakers for each service
cal_com_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
openai_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)


async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    circuit_breaker: Optional[CircuitBreaker] = None,
    service_name: str = "unknown",
    **kwargs
) -> Any:
    """
    Execute async function with exponential backoff retry.

    Args:
        func: Async function to execute
        max_retries: Maximum retry attempts (default 3)
        initial_delay: Initial retry delay in seconds (default 1.0)
        max_delay: Maximum retry delay in seconds (default 10.0)
        circuit_breaker: Optional circuit breaker instance
        service_name: Service name for logging

    Returns:
        Function result

    Raises:
        Exception: If all retries exhausted
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries + 1):
        # Check circuit breaker
        if circuit_breaker and not circuit_breaker.can_attempt():
            logger.warning(
                "Circuit breaker open - request blocked",
                service=service_name,
                state=circuit_breaker.state
            )
            raise Exception(f"{service_name} circuit breaker is open")

        try:
            logger.debug(
                "Attempting API call",
                service=service_name,
                attempt=attempt + 1,
                max_attempts=max_retries + 1
            )

            result = await func(*args, **kwargs)

            # Success - record in circuit breaker
            if circuit_breaker:
                circuit_breaker.record_success()

            if attempt > 0:
                logger.info(
                    "API call succeeded after retry",
                    service=service_name,
                    attempt=attempt + 1
                )

            return result

        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
            last_exception = e

            # Record failure in circuit breaker
            if circuit_breaker:
                circuit_breaker.record_failure()

            if attempt < max_retries:
                logger.warning(
                    "API call failed - retrying",
                    service=service_name,
                    attempt=attempt + 1,
                    max_attempts=max_retries + 1,
                    error=str(e),
                    retry_in_seconds=delay
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
            else:
                logger.error(
                    "API call failed after all retries",
                    service=service_name,
                    attempts=attempt + 1,
                    error=str(e)
                )

        except httpx.HTTPStatusError as e:
            # Don't retry on 4xx client errors
            if 400 <= e.response.status_code < 500:
                logger.error(
                    "API call failed with client error - no retry",
                    service=service_name,
                    status_code=e.response.status_code,
                    error=str(e)
                )
                raise

            # Retry on 5xx server errors
            last_exception = e

            if circuit_breaker:
                circuit_breaker.record_failure()

            if attempt < max_retries:
                logger.warning(
                    "API call failed with server error - retrying",
                    service=service_name,
                    attempt=attempt + 1,
                    status_code=e.response.status_code,
                    retry_in_seconds=delay
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
            else:
                logger.error(
                    "API call failed after all retries",
                    service=service_name,
                    attempts=attempt + 1,
                    status_code=e.response.status_code
                )

        except Exception as e:
            # Unexpected error - don't retry
            logger.error(
                "API call failed with unexpected error",
                service=service_name,
                error=str(e)
            )
            raise

    # All retries exhausted
    raise last_exception


# Dead letter queue (simple in-memory for now)
dead_letter_queue = []


def add_to_dead_letter_queue(
    operation: str,
    data: dict,
    error: str,
    service: str
):
    """
    Add failed operation to dead letter queue for later processing.

    Args:
        operation: Operation name (e.g., "book_appointment", "generate_summary")
        data: Operation data/payload
        error: Error message
        service: Service name
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "service": service,
        "data": data,
        "error": error
    }
    dead_letter_queue.append(entry)

    logger.error(
        "Operation added to dead letter queue",
        operation=operation,
        service=service,
        queue_size=len(dead_letter_queue),
        error=error
    )


def get_dead_letter_queue() -> list:
    """Get all entries from dead letter queue"""
    return dead_letter_queue.copy()


def clear_dead_letter_queue():
    """Clear dead letter queue"""
    dead_letter_queue.clear()
    logger.info("Dead letter queue cleared")
