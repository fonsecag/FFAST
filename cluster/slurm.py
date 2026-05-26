import asyncio
import os
import re
import tempfile

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
        lines = ["#!/bin/bash"]
        lines.append("#SBATCH --nodes=1")
        lines.append(f"#SBATCH --ntasks={spec.cores}")
        lines.append(f"#SBATCH --mem={spec.memory_mb}M")
        lines.append(f"#SBATCH --time={spec.time_limit}")
        if spec.gpu_count > 0:
            lines.append(f"#SBATCH --gres=gpu:{spec.gpu_count}")
        if spec.partition:
            lines.append(f"#SBATCH --partition={spec.partition}")
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
