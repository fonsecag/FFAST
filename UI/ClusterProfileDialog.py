"""Dialog for managing cluster connection profiles and initiating a connection.

Opens via File → Connect to Cluster…

Layout
------
  Profile:  [combo ▼]   [Save Profile]  [Delete]
  ─────────────────────────────────────────────
  SSH
    Host:             [_____________________]
    Username:         [_____________________]
    Identity file:    [_____________________] [Browse]
    Server command:   [_____________________]
  Scheduler
    Partition:        [_________]
    Account:          [_________]
    QoS:              [_________]
    Job name:         [_________]
  Resources
    Cores:   [__]  CPUs/task: [__]  Ntasks/node: [__]  GPUs/task: [__]
    Mem(MB): [____]   Time (HH:MM:SS): [_______]
  ─────────────────────────────────────────────
                            [Cancel]   [Connect]
"""

import logging
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from cluster.config import ClusterConfig, ClusterProfile

logger = logging.getLogger("FFAST")

_NEW_LABEL = "— New Profile —"


def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    return line


class ClusterConnectDialog(QDialog):
    """
    Returns accepted with `get_profile()` containing current field values.
    Caller is responsible for actually opening the SSH connection.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to Cluster")
        self.setModal(True)
        self.resize(480, 520)

        self._config = ClusterConfig()

        self._build_ui()
        self._refresh_combo(select=None)

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # ── profile row ──────────────────────────────────────────────────
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Profile:"))
        self._combo = QComboBox()
        self._combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._combo.currentIndexChanged.connect(self._on_profile_selected)
        profile_row.addWidget(self._combo)

        self._btn_save = QPushButton("Save Profile")
        self._btn_save.setFixedWidth(110)
        self._btn_save.clicked.connect(self._on_save_profile)
        profile_row.addWidget(self._btn_save)

        self._btn_delete = QPushButton("Delete")
        self._btn_delete.setFixedWidth(60)
        self._btn_delete.clicked.connect(self._on_delete_profile)
        profile_row.addWidget(self._btn_delete)

        root.addLayout(profile_row)
        root.addWidget(_hline())

        # ── SSH ──────────────────────────────────────────────────────────
        ssh_box = QGroupBox("SSH")
        ssh_form = QFormLayout(ssh_box)

        self._f_host = QLineEdit()
        self._f_host.setPlaceholderText("login.example.com")
        self._f_username = QLineEdit()
        self._f_username.setPlaceholderText("your_username")

        # identity file row: text field + browse button
        identity_row = QHBoxLayout()
        self._f_identity_file = QLineEdit()
        self._f_identity_file.setPlaceholderText(
            "~/.ssh/id_ed25519  (leave blank for ssh-agent / default)"
        )
        self._btn_browse_key = QPushButton("Browse…")
        self._btn_browse_key.setFixedWidth(70)
        self._btn_browse_key.clicked.connect(self._on_browse_identity)
        identity_row.addWidget(self._f_identity_file)
        identity_row.addWidget(self._btn_browse_key)

        self._f_ffast_server_cmd = QLineEdit()
        self._f_ffast_server_cmd.setPlaceholderText(
            "ffast-server  (or: source ~/venv/bin/activate && ffast-server)"
        )

        ssh_form.addRow("Host:", self._f_host)
        ssh_form.addRow("Username:", self._f_username)
        ssh_form.addRow("Identity file:", identity_row)
        ssh_form.addRow("Server command:", self._f_ffast_server_cmd)
        root.addWidget(ssh_box)

        # ── Scheduler ────────────────────────────────────────────────────
        sched_box = QGroupBox("Scheduler")
        sched_form = QFormLayout(sched_box)
        self._f_partition = QLineEdit()
        self._f_account = QLineEdit()
        self._f_qos = QLineEdit()
        self._f_job_name = QLineEdit()
        self._f_job_name.setPlaceholderText("ffast")
        sched_form.addRow("Partition:", self._f_partition)
        sched_form.addRow("Account:", self._f_account)
        sched_form.addRow("QoS:", self._f_qos)
        sched_form.addRow("Job name:", self._f_job_name)
        root.addWidget(sched_box)

        # ── Resources ────────────────────────────────────────────────────
        res_box = QGroupBox("Resources")
        res_layout = QVBoxLayout(res_box)

        row1 = QHBoxLayout()
        self._f_cores = self._int_field(1, 1024)
        self._f_cpus_per_task = self._int_field(0, 1024)
        self._f_ntasks_per_node = self._int_field(0, 1024)
        self._f_gpus_per_task = self._int_field(0, 64)
        for label, widget in [
            ("Cores:", self._f_cores),
            ("CPUs/task:", self._f_cpus_per_task),
            ("Ntasks/node:", self._f_ntasks_per_node),
            ("GPUs/task:", self._f_gpus_per_task),
        ]:
            row1.addWidget(QLabel(label))
            row1.addWidget(widget)

        row2 = QHBoxLayout()
        self._f_memory_mb = self._int_field(1, 1_000_000)
        self._f_memory_mb.setFixedWidth(80)
        self._f_time_limit = QLineEdit()
        self._f_time_limit.setPlaceholderText("HH:MM:SS")
        self._f_time_limit.setFixedWidth(90)
        row2.addWidget(QLabel("Memory (MB):"))
        row2.addWidget(self._f_memory_mb)
        row2.addSpacing(16)
        row2.addWidget(QLabel("Time limit:"))
        row2.addWidget(self._f_time_limit)
        row2.addStretch()

        res_layout.addLayout(row1)
        res_layout.addLayout(row2)
        root.addWidget(res_box)

        root.addWidget(_hline())

        # ── buttons ──────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok
        )
        btn_box.button(QDialogButtonBox.Ok).setText("Connect")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    @staticmethod
    def _int_field(lo: int, hi: int) -> QLineEdit:
        le = QLineEdit()
        le.setValidator(QIntValidator(lo, hi))
        le.setFixedWidth(55)
        return le

    def _on_browse_identity(self):
        start = os.path.expanduser("~/.ssh")
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SSH Private Key", start, "All files (*)"
        )
        if path:
            # Collapse $HOME back to ~ for readability
            try:
                path = "~" + os.sep + os.path.relpath(
                    path, os.path.expanduser("~")
                )
            except ValueError:
                pass
            self._f_identity_file.setText(path)

    # ------------------------------------------------------------------ combo

    def _refresh_combo(self, select: str | None):
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem(_NEW_LABEL)
        for name in self._config.names():
            self._combo.addItem(name)

        if select and select in self._config.names():
            idx = self._combo.findText(select)
            self._combo.setCurrentIndex(idx)
        else:
            self._combo.setCurrentIndex(0)
        self._combo.blockSignals(False)
        self._on_profile_selected(self._combo.currentIndex())

    def _on_profile_selected(self, index: int):
        is_new = index == 0 or self._combo.currentText() == _NEW_LABEL
        self._btn_delete.setEnabled(not is_new)
        if is_new:
            self._clear_fields()
        else:
            name = self._combo.currentText()
            p = self._config.get(name)
            if p:
                self._fill_fields(p)

    # ------------------------------------------------------------------ CRUD

    def _on_save_profile(self):
        current = self._combo.currentText()
        default_name = "" if current == _NEW_LABEL else current
        name, ok = QInputDialog.getText(
            self, "Save Profile", "Profile name:", text=default_name
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        p = self._read_fields(name)
        self._config.add(p)
        self._refresh_combo(select=name)

    def _on_delete_profile(self):
        name = self._combo.currentText()
        if name == _NEW_LABEL:
            return
        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f'Delete profile "{name}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._config.delete(name)
            self._refresh_combo(select=None)

    # ------------------------------------------------------------------ fields

    def _clear_fields(self):
        for w in [
            self._f_host,
            self._f_username,
            self._f_identity_file,
            self._f_ffast_server_cmd,
            self._f_partition,
            self._f_account,
            self._f_qos,
            self._f_job_name,
            self._f_time_limit,
        ]:
            w.clear()
        for w, default in [
            (self._f_cores, "1"),
            (self._f_cpus_per_task, "0"),
            (self._f_ntasks_per_node, "0"),
            (self._f_gpus_per_task, "0"),
            (self._f_memory_mb, "4096"),
        ]:
            w.setText(default)
        self._f_time_limit.setText("01:00:00")

    def _fill_fields(self, p: ClusterProfile):
        self._f_host.setText(p.host)
        self._f_username.setText(p.username)
        self._f_identity_file.setText(p.identity_file)
        self._f_ffast_server_cmd.setText(p.ffast_server_cmd)
        self._f_partition.setText(p.partition)
        self._f_account.setText(p.account)
        self._f_qos.setText(p.qos)
        self._f_job_name.setText(p.job_name)
        self._f_cores.setText(str(p.cores))
        self._f_cpus_per_task.setText(str(p.cpus_per_task))
        self._f_ntasks_per_node.setText(str(p.ntasks_per_node))
        self._f_gpus_per_task.setText(str(p.gpus_per_task))
        self._f_memory_mb.setText(str(p.memory_mb))
        self._f_time_limit.setText(p.time_limit)

    def _read_fields(self, name: str = "") -> ClusterProfile:
        def _int(w, default=0):
            t = w.text().strip()
            try:
                return int(t)
            except ValueError:
                return default

        return ClusterProfile(
            name=name,
            host=self._f_host.text().strip(),
            username=self._f_username.text().strip(),
            identity_file=self._f_identity_file.text().strip(),
            ffast_server_cmd=(
                self._f_ffast_server_cmd.text().strip() or "ffast-server"
            ),
            partition=self._f_partition.text().strip(),
            account=self._f_account.text().strip(),
            qos=self._f_qos.text().strip(),
            job_name=self._f_job_name.text().strip() or "ffast",
            cores=_int(self._f_cores, 1),
            cpus_per_task=_int(self._f_cpus_per_task, 0),
            ntasks_per_node=_int(self._f_ntasks_per_node, 0),
            gpus_per_task=_int(self._f_gpus_per_task, 0),
            gpu_count=0,
            memory_mb=_int(self._f_memory_mb, 4096),
            time_limit=self._f_time_limit.text().strip() or "01:00:00",
        )

    # ------------------------------------------------------------------ result

    def get_profile(self) -> ClusterProfile:
        """Return profile built from current field values (unsaved unless user saved)."""
        name = self._combo.currentText()
        if name == _NEW_LABEL:
            name = ""
        return self._read_fields(name)
