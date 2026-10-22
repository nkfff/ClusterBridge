import asyncio
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QLabel, QLineEdit,
    QHBoxLayout, QListWidget, QMainWindow, QMessageBox, QPushButton,
    QProgressBar, QVBoxLayout, QWidget,
)

from . import __version__
from .models import Endpoint, EndpointKind, TransferRequest
from .storage import ProfileStore

LAST_UPDATED = "2026-10-22T16:51:55+08:00"
RELEASES_URL = "https://github.com/nkfff/ClusterBridge/releases"


class TransferWorker(QObject):
    progress = Signal(int, int)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, requests: list[TransferRequest], profiles: dict) -> None:
        super().__init__()
        self.requests = requests
        self.profiles = profiles

    def run(self) -> None:
        async def progress(current: int, total: int) -> None:
            self.progress.emit(current, total)

        try:
            from .transfer import transfer_many

            result = asyncio.run(
                transfer_many(self.requests, self.profiles, progress)
            )
            self.completed.emit(
                f"Completed {result.completed} tasks; {result.failed} failed; "
                f"resumed {result.resumed_from:,} bytes"
            )
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ClusterBridge - Local Relay")
        self.resize(620, 300)
        self.store = ProfileStore()
        self.profiles = {p.id: p for p in self.store.list_profiles()}

        source_path = QLineEdit()
        destination_path = QLineEdit()
        source_combo = QComboBox()
        destination_combo = QComboBox()
        for combo in (source_combo, destination_combo):
            combo.addItem("This computer", "")
            for profile in self.profiles.values():
                combo.addItem(profile.name, profile.id)
        self.source_combo, self.destination_combo = source_combo, destination_combo
        self.source_path, self.destination_path = source_path, destination_path
        self.requests = []

        form = QFormLayout()
        form.addRow("Source", source_combo)
        form.addRow("Source path", source_path)
        form.addRow("Destination", destination_combo)
        form.addRow("Destination path", destination_path)

        self.status = QLabel("Data is relayed through memory and is not stored as a complete local file.")
        self.progress = QProgressBar()
        self.task_list = QListWidget()
        help_row = QHBoxLayout()
        about_button = QPushButton("About")
        about_button.clicked.connect(self.show_about)
        tutorial_button = QPushButton("Open tutorial")
        tutorial_button.clicked.connect(self.open_tutorial)
        help_row.addWidget(about_button)
        help_row.addWidget(tutorial_button)
        help_row.addStretch()
        add_task = QPushButton("Add task")
        add_task.clicked.connect(self.add_task)
        start = QPushButton("Start queued tasks")
        start.clicked.connect(self.start_transfer)
        layout = QVBoxLayout()
        layout.addLayout(help_row)
        layout.addLayout(form)
        layout.addWidget(add_task)
        layout.addWidget(self.task_list)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addWidget(start)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _build_request(self) -> TransferRequest:
        source_id = self.source_combo.currentData()
        destination_id = self.destination_combo.currentData()
        source_kind = EndpointKind.SSH if source_id else EndpointKind.LOCAL
        destination_kind = EndpointKind.SSH if destination_id else EndpointKind.LOCAL
        request = TransferRequest(
            Endpoint(source_kind, self.source_path.text(), source_id or None),
            Endpoint(destination_kind, self.destination_path.text(), destination_id or None),
        )
        request.validate()
        return request

    def add_task(self) -> None:
        try:
            request = self._build_request()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid input", str(exc))
            return
        self.requests.append(request)
        self.task_list.addItem(f"{request.source.path} -> {request.destination.path}")
        self.status.setText(f"{len(self.requests)} task(s) queued")

    def start_transfer(self) -> None:
        if not self.requests:
            self.add_task()
        if not self.requests:
            return
        self.thread = QThread()
        self.worker = TransferWorker(self.requests, self.profiles)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(
            lambda current, total: self.progress.setValue(
                int(current * 100 / total) if total else 0
            )
        )
        self.worker.completed.connect(self.finish_transfer)
        self.worker.failed.connect(self.fail_transfer)
        self.thread.start()
        self.status.setText("Transferring...")
        self.requests = []

    def finish_transfer(self, message: str) -> None:
        self.status.setText(message)
        self.thread.quit()

    def fail_transfer(self, message: str) -> None:
        self.status.setText("Transfer failed")
        QMessageBox.critical(self, "Transfer failed", message)
        self.thread.quit()

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About ClusterBridge",
            (
                f"<b>ClusterBridge</b><br>"
                f"Version: {__version__}<br>"
                f"Last updated: {LAST_UPDATED}<br><br>"
                "A lightweight SSH relay app for cluster-to-cluster and "
                "cluster-to-local data transfer through bounded local memory.<br><br>"
                f"Releases: <a href=\"{RELEASES_URL}\">{RELEASES_URL}</a>"
            ),
        )

    def open_tutorial(self) -> None:
        tutorial_path = (
            Path(__file__).resolve().parent.parent / "docs" / "tutorial.html"
        )
        if tutorial_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(tutorial_path)))
            return
        QDesktopServices.openUrl(QUrl(RELEASES_URL))

    def closeEvent(self, event) -> None:  # noqa: N802
        self.store.close()
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
