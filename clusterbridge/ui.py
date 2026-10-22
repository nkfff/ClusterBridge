import asyncio
import sys

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QProgressBar, QVBoxLayout, QWidget,
)

from .models import Endpoint, EndpointKind, TransferRequest
from .storage import ProfileStore
from .transfer import transfer_file


class TransferWorker(QObject):
    progress = Signal(int, int)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, request: TransferRequest, profiles: dict) -> None:
        super().__init__()
        self.request = request
        self.profiles = profiles

    def run(self) -> None:
        async def progress(current: int, total: int) -> None:
            self.progress.emit(current, total)

        try:
            result = asyncio.run(transfer_file(self.request, self.profiles, progress))
            self.completed.emit(
                f"Completed: {result.bytes_transferred:,} bytes; "
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

        form = QFormLayout()
        form.addRow("Source", source_combo)
        form.addRow("Source path", source_path)
        form.addRow("Destination", destination_combo)
        form.addRow("Destination path", destination_path)

        self.status = QLabel("Data is relayed through memory and is not stored as a complete local file.")
        self.progress = QProgressBar()
        start = QPushButton("Start transfer")
        start.clicked.connect(self.start_transfer)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addWidget(start)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def start_transfer(self) -> None:
        source_id = self.source_combo.currentData()
        destination_id = self.destination_combo.currentData()
        source_kind = EndpointKind.SSH if source_id else EndpointKind.LOCAL
        destination_kind = EndpointKind.SSH if destination_id else EndpointKind.LOCAL
        try:
            request = TransferRequest(
                Endpoint(source_kind, self.source_path.text(), source_id or None),
                Endpoint(destination_kind, self.destination_path.text(), destination_id or None),
            )
            request.validate()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid input", str(exc))
            return
        self.thread = QThread()
        self.worker = TransferWorker(request, self.profiles)
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

    def finish_transfer(self, message: str) -> None:
        self.status.setText(message)
        self.thread.quit()

    def fail_transfer(self, message: str) -> None:
        self.status.setText("Transfer failed")
        QMessageBox.critical(self, "Transfer failed", message)
        self.thread.quit()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.store.close()
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
