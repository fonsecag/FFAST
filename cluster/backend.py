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
    cores: int          # --ntasks
    memory_mb: int
    time_limit: str     # HH:MM:SS
    command: str
    # optional resource fields
    cpus_per_task: int = 0      # --cpus-per-task
    ntasks_per_node: int = 0    # --ntasks-per-node
    gpus_per_task: int = 0      # --gpus-per-task
    gpu_count: int = 0          # --gres=gpu:N (legacy, use gpus_per_task)
    partition: str = ""
    account: str = ""
    qos: str = ""
    job_name: str = ""


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
