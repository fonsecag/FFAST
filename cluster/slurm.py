import asyncio
import os
import re
import tempfile
from typing import Optional

from .backend import ClusterBackend, ClusterError, JobSpec, JobStatus


class SlurmBackend(ClusterBackend):
    async def submit_job(self, spec: JobSpec) -> str:
        script = self._build_script(spec)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as f:
            f.write(script)
            script_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "sbatch",
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise ClusterError(
                    f"sbatch failed (exit {proc.returncode})",
                    stderr.decode(),
                )
            match = re.search(r"(\d+)", stdout.decode())
            if not match:
                raise ClusterError(
                    "Could not parse job ID from sbatch output",
                    stdout.decode(),
                )
            return match.group(1)
        finally:
            os.unlink(script_path)

    async def poll_status(self, job_id: str) -> JobStatus:
        proc = await asyncio.create_subprocess_exec(
            "squeue",
            "--noheader",
            "-o",
            "%T",
            "-j",
            job_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode().strip()

        if output:
            return self._squeue_state_to_status(output.split()[0])

        # Job gone from squeue — resolve terminal state via sacct
        proc = await asyncio.create_subprocess_exec(
            "sacct",
            "-j",
            job_id,
            "--noheader",
            "--format=State",
            "-X",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode().strip()

        if not output:
            raise ClusterError(
                f"Job {job_id} not found in squeue or sacct"
            )

        state = output.split()[0].upper()
        if state == "COMPLETED":
            return JobStatus.COMPLETED
        return JobStatus.FAILED

    async def get_node_address(self, job_id: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "squeue",
            "--noheader",
            "-o",
            "%N",
            "-j",
            job_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode().strip()

        if not output:
            raise ClusterError(
                f"Job {job_id} is not running or does not exist"
            )

        return self._parse_first_node(output)

    async def cancel_job(self, job_id: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            "scancel",
            job_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

    def _build_script(self, spec: JobSpec) -> str:
        lines = ["#!/bin/bash -l"]  # -l = login shell, loads modules
        lines.append("#SBATCH --nodes=1")
        lines.append(f"#SBATCH --ntasks={spec.cores}")
        lines.append(f"#SBATCH --mem={spec.memory_mb}M")
        lines.append(f"#SBATCH --time={spec.time_limit}")
        if spec.cpus_per_task > 0:
            lines.append(f"#SBATCH --cpus-per-task={spec.cpus_per_task}")
        if spec.ntasks_per_node > 0:
            lines.append(f"#SBATCH --ntasks-per-node={spec.ntasks_per_node}")
        if spec.gpus_per_task > 0:
            lines.append(f"#SBATCH --gpus-per-task={spec.gpus_per_task}")
        elif spec.gpu_count > 0:
            lines.append(f"#SBATCH --gres=gpu:{spec.gpu_count}")
        if spec.partition:
            lines.append(f"#SBATCH --partition={spec.partition}")
        if spec.account:
            lines.append(f"#SBATCH --account={spec.account}")
        if spec.qos:
            lines.append(f"#SBATCH --qos={spec.qos}")
        if spec.job_name:
            lines.append(f"#SBATCH --job-name={spec.job_name}")
        lines.append("")
        lines.append(spec.command)
        return "\n".join(lines)

    def _squeue_state_to_status(self, state: str) -> JobStatus:
        state = state.upper()
        if state in (
            "PENDING",
            "CONFIGURING",
            "REQUEUED",
            "REQUEUE_FED",
            "REQUEUE_HOLD",
        ):
            return JobStatus.PENDING
        if state in ("RUNNING", "COMPLETING"):
            return JobStatus.RUNNING
        if state in (
            "FAILED",
            "CANCELLED",
            "TIMEOUT",
            "OUT_OF_MEMORY",
            "NODE_FAIL",
            "BOOT_FAIL",
            "DEADLINE",
        ):
            return JobStatus.FAILED
        if state == "COMPLETED":
            return JobStatus.COMPLETED
        return JobStatus.PENDING

    def _parse_first_node(self, node_list: str) -> str:
        # "node01,node02" → "node01"
        # "node[01-04]" → "node01"
        first = node_list.split(",")[0]
        match = re.match(r"^(.*?)\[(\d+)", first)
        if match:
            return f"{match.group(1)}{match.group(2)}"
        return first


class RemoteSlurmBackend(SlurmBackend):
    """
    SlurmBackend that runs sbatch/squeue/sacct/scancel on a remote login node
    via SSH instead of locally.  Inherits all script-building helpers.

    Parameters
    ----------
    host : str
        Login node hostname (e.g. "login.lxp.lu").
    username : str
        SSH username.  Omit to use the system default (~/.ssh/config, etc.).
    identity_file : str
        Path to the SSH private key.  Expanded with os.path.expanduser().
        Omit to rely on ssh-agent / default keys.
    """

    def __init__(
        self,
        host: str,
        username: str = "",
        identity_file: str = "",
    ):
        self._host = host
        self._username = username
        self._identity_file = (
            os.path.expanduser(identity_file) if identity_file else ""
        )

    # ── SSH helpers ───────────────────────────────────────────────────────

    def _ssh_prefix(self) -> list[str]:
        """Return the ssh base command (without the remote command args)."""
        cmd = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=15",
        ]
        if self._identity_file:
            cmd += ["-i", self._identity_file]
        target = (
            f"{self._username}@{self._host}"
            if self._username
            else self._host
        )
        cmd.append(target)
        return cmd

    async def _run_remote(
        self,
        *remote_args: str,
        stdin: Optional[str] = None,
    ) -> tuple[str, str, int]:
        """
        Run *remote_args on the login node via SSH.
        If stdin is given, pipe it to the process (used for sbatch script).
        Returns (stdout, stderr, returncode).
        """
        cmd = self._ssh_prefix() + list(remote_args)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=(
                asyncio.subprocess.PIPE if stdin is not None
                else asyncio.subprocess.DEVNULL
            ),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        input_bytes = stdin.encode() if stdin is not None else None
        stdout, stderr = await proc.communicate(input=input_bytes)
        return stdout.decode(), stderr.decode(), proc.returncode

    # ── ClusterBackend interface (remote overrides) ───────────────────────

    async def submit_job(self, spec: JobSpec) -> str:
        script = self._build_script(spec)
        stdout, stderr, rc = await self._run_remote("sbatch", stdin=script)
        if rc != 0:
            raise ClusterError(
                f"sbatch failed on {self._host} (exit {rc})", stderr
            )
        match = re.search(r"(\d+)", stdout)
        if not match:
            raise ClusterError(
                "Could not parse job ID from sbatch output", stdout
            )
        return match.group(1)

    async def poll_status(self, job_id: str) -> JobStatus:
        stdout, _, _ = await self._run_remote(
            "squeue", "--noheader", "-o", "%T", "-j", job_id
        )
        output = stdout.strip()
        if output:
            return self._squeue_state_to_status(output.split()[0])

        # Job gone from squeue — resolve terminal state via sacct
        stdout, _, _ = await self._run_remote(
            "sacct", "-j", job_id, "--noheader", "--format=State", "-X"
        )
        output = stdout.strip()
        if not output:
            raise ClusterError(
                f"Job {job_id} not found in squeue or sacct on {self._host}"
            )
        state = output.split()[0].upper()
        if state == "COMPLETED":
            return JobStatus.COMPLETED
        return JobStatus.FAILED

    async def get_node_address(self, job_id: str) -> str:
        stdout, _, _ = await self._run_remote(
            "squeue", "--noheader", "-o", "%N", "-j", job_id
        )
        output = stdout.strip()
        if not output:
            raise ClusterError(
                f"Job {job_id} is not running or does not exist on {self._host}"
            )
        return self._parse_first_node(output)

    async def cancel_job(self, job_id: str) -> None:
        await self._run_remote("scancel", job_id)
