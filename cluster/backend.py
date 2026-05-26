from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class JobStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


@dataclass
class JobSpec:
    cores: int
    memory_mb: int
    time_limit: str
    command: str
    gpu_count: int = 0
    partition: str = ""


class ClusterError(Exception):
    def __init__(self, message: str, stderr: str = ""):
        super().__init__(message)
        self.stderr = stderr


class ClusterBackend(ABC):
    @abstractmethod
    async def submit_job(self, spec: JobSpec) -> str:
        """Submit a job. Returns job ID string."""

    @abstractmethod
    async def poll_status(self, job_id: str) -> JobStatus:
        """Return current status of job_id."""

    @abstractmethod
    async def get_node_address(self, job_id: str) -> str:
        """Return hostname of the first allocated node. Raises ClusterError if not RUNNING."""

    @abstractmethod
    async def cancel_job(self, job_id: str) -> None:
        """Cancel job_id. Silently succeeds if already finished."""
