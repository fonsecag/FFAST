"""Cluster connection profiles — load/save named profiles from clusters.json."""

import json
import logging
import os
from dataclasses import asdict, dataclass, field

from .backend import JobSpec

logger = logging.getLogger("FFAST")

_CLUSTERS_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "clusters.json",
)


@dataclass
class ClusterProfile:
    """One named connection profile.  All fields map 1-to-1 to JobSpec."""

    name: str
    host: str = ""
    username: str = ""
    # scheduler
    partition: str = ""
    account: str = ""
    qos: str = ""
    job_name: str = "ffast"
    # resources
    cores: int = 1
    cpus_per_task: int = 0
    ntasks_per_node: int = 0
    gpus_per_task: int = 0
    gpu_count: int = 0
    memory_mb: int = 4096
    time_limit: str = "01:00:00"

    def to_job_spec(self, command: str) -> JobSpec:
        return JobSpec(
            cores=self.cores,
            memory_mb=self.memory_mb,
            time_limit=self.time_limit,
            command=command,
            cpus_per_task=self.cpus_per_task,
            ntasks_per_node=self.ntasks_per_node,
            gpus_per_task=self.gpus_per_task,
            gpu_count=self.gpu_count,
            partition=self.partition,
            account=self.account,
            qos=self.qos,
            job_name=self.job_name,
        )


class ClusterConfig:
    """Load/save cluster profiles from config/clusters.json."""

    def __init__(self, path: str = _CLUSTERS_JSON):
        self._path = path
        self._profiles: dict[str, ClusterProfile] = {}
        self.load()

    # ------------------------------------------------------------------ IO

    def load(self) -> None:
        if not os.path.exists(self._path):
            logger.debug(
                "clusters.json not found at %s — starting empty", self._path
            )
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            self._profiles = {}
            for raw in data.get("profiles", []):
                try:
                    p = ClusterProfile(**raw)
                    self._profiles[p.name] = p
                except TypeError as e:
                    logger.warning(
                        "Skipping malformed profile %s: %s", raw, e
                    )
        except Exception as e:
            logger.error("Failed to load clusters.json: %s", e)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        data = {"profiles": [asdict(p) for p in self._profiles.values()]}
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save clusters.json: %s", e)

    # ------------------------------------------------------------------ CRUD

    def add(self, profile: ClusterProfile) -> None:
        """Add or overwrite a profile (keyed by name)."""
        self._profiles[profile.name] = profile
        self.save()

    def delete(self, name: str) -> None:
        if name in self._profiles:
            del self._profiles[name]
            self.save()

    def get(self, name: str) -> ClusterProfile | None:
        return self._profiles.get(name)

    def names(self) -> list[str]:
        return list(self._profiles.keys())

    def all_profiles(self) -> list[ClusterProfile]:
        return list(self._profiles.values())
