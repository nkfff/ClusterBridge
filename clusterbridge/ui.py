import asyncio
import sys
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QFrame, QHBoxLayout, QListWidget, QMainWindow, QMessageBox, QPushButton,
    QProgressBar, QSpinBox, QVBoxLayout, QWidget, QLineEdit,
)

from . import __version__
from .models import ConnectionProfile, Endpoint, EndpointKind, TransferRequest
from .secrets import delete_password, save_password
from .storage import ProfileStore

LAST_UPDATED = "2026-10-22T16:51:55+08:00"
RELEASES_URL = "https://github.com/nkfff/ClusterBridge/releases"


class ProfileDialog(QDialog):
    def __init__(self, profile: ConnectionProfile | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add SSH connection" if profile is None else "Edit SSH connection")
        self.name = QLineEdit(profile.name if profile else "")
        self.host = QLineEdit(profile.host if profile else "")
        self.username = QLineEdit(profile.username if profile else "")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(profile.port if profile else 22)
        self.default_path = QLineEdit(profile.default_path if profile else "/")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText(
            "Leave blank to keep the saved password" if profile else "Required"
        )

        form = QFormLayout()
        form.addRow("Connection name", self.name)
        form.addRow("SSH host", self.host)
        form.addRow("Username", self.username)
        form.addRow("Port", self.port)
        form.addRow("Default path", self.default_path)
        form.addRow("Password", self.password)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("The password is stored in the system keychain."))
        layout.addWidget(buttons)
        self._profile = profile

    def accept(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.name.text(),
                self.host.text(),
                self.username.text(),
                self.default_path.text(),
            )
        ):
            QMessageBox.warning(self, "Invalid input", "All connection fields are required.")
            return
        if self._profile is None and not self.password.text():
            QMessageBox.warning(self, "Invalid input", "A password is required for a new connection.")
            return
        super().accept()

    def profile(self) -> ConnectionProfile:
        return ConnectionProfile(
            id=self._profile.id if self._profile else str(uuid.uuid4()),
            name=self.name.text().strip(),
            host=self.host.text().strip(),
            username=self.username.text().strip(),
            port=self.port.value(),
            default_path=self.default_path.text().strip(),
        )


class ConnectionManagerDialog(QDialog):
    profiles_changed = Signal()

    def __init__(self, store: ProfileStore, profiles: dict[str, ConnectionProfile], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SSH connection manager")
        self.resize(500, 320)
        self.store = store
        self.profiles = profiles
        self.list = QListWidget()
        self.refresh()

        add = QPushButton("Add")
        edit = QPushButton("Edit")
        remove = QPushButton("Delete")
        add.clicked.connect(self.add_profile)
        edit.clicked.connect(self.edit_profile)
        remove.clicked.connect(self.delete_profile)
        buttons = QHBoxLayout()
        buttons.addWidget(add)
        buttons.addWidget(edit)
        buttons.addWidget(remove)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Saved SSH connections"))
        layout.addWidget(self.list)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        self.list.clear()
        for profile in sorted(self.profiles.values(), key=lambda item: item.name.lower()):
            self.list.addItem(f"{profile.name} — {profile.username}@{profile.host}:{profile.port}")

    def selected_profile(self) -> ConnectionProfile | None:
        row = self.list.currentRow()
        if row < 0:
            return None
        profiles = sorted(self.profiles.values(), key=lambda item: item.name.lower())
        return profiles[row]

    def add_profile(self) -> None:
        dialog = ProfileDialog(parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        profile = dialog.profile()
        self.store.save_profile(profile)
        save_password(profile.id, dialog.password.text())
        self.profiles[profile.id] = profile
        self.refresh()
        self.profiles_changed.emit()

    def edit_profile(self) -> None:
        profile = self.selected_profile()
        if profile is None:
            QMessageBox.information(self, "Edit connection", "Select a connection first.")
            return
        dialog = ProfileDialog(profile, self)
        if dialog.exec() != QDialog.Accepted:
            return
        updated = dialog.profile()
        self.store.save_profile(updated)
        if dialog.password.text():
            save_password(updated.id, dialog.password.text())
        self.profiles[updated.id] = updated
        self.refresh()
        self.profiles_changed.emit()

    def delete_profile(self) -> None:
        profile = self.selected_profile()
        if profile is None:
            QMessageBox.information(self, "Delete connection", "Select a connection first.")
            return
        answer = QMessageBox.question(
            self, "Delete connection", f"Delete saved connection '{profile.name}'?"
        )
        if answer != QMessageBox.Yes:
            return
        self.store.delete_profile(profile.id)
        delete_password(profile.id)
        del self.profiles[profile.id]
        self.refresh()
        self.profiles_changed.emit()


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
            error_text = ""
            if result.errors:
                error_text = " Errors: " + " | ".join(result.errors)
            self.completed.emit(
                f"Completed {result.completed} tasks; {result.failed} failed; "
                f"resumed {result.resumed_from:,} bytes.{error_text}"
            )
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ClusterBridge")
        self.setMinimumSize(760, 620)
        self.resize(860, 700)
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "clusterbridge.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
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

        source_card = self._endpoint_card(
            "SOURCE", "Read from a local file or SSH cluster", source_combo, source_path
        )
        destination_card = self._endpoint_card(
            "DESTINATION", "Write directly without full local staging",
            destination_combo, destination_path
        )
        arrow = QLabel("→")
        arrow.setObjectName("transferArrow")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        endpoint_row = QHBoxLayout()
        endpoint_row.setSpacing(14)
        endpoint_row.addWidget(source_card, 1)
        endpoint_row.addWidget(arrow)
        endpoint_row.addWidget(destination_card, 1)

        self.status = QLabel("Ready — data is relayed through bounded local memory.")
        self.status.setObjectName("statusLabel")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.task_list = QListWidget()
        self.task_list.setObjectName("taskList")
        task_title = QLabel("TRANSFER QUEUE")
        task_title.setObjectName("sectionLabel")
        help_row = QHBoxLayout()
        connections_button = QPushButton("Manage SSH connections")
        connections_button.clicked.connect(self.manage_connections)
        about_button = QPushButton("About")
        about_button.clicked.connect(self.show_about)
        tutorial_button = QPushButton("Open tutorial")
        tutorial_button.clicked.connect(self.open_tutorial)
        help_row.addWidget(connections_button)
        help_row.addWidget(about_button)
        help_row.addWidget(tutorial_button)
        help_row.addStretch()
        brand = QHBoxLayout()
        logo = QLabel()
        if icon_path.exists():
            logo.setPixmap(QPixmap(str(icon_path)).scaled(
                42, 42, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        brand_text = QVBoxLayout()
        brand_name = QLabel("ClusterBridge")
        brand_name.setObjectName("brandName")
        brand_subtitle = QLabel("Private data relay • local memory bridge")
        brand_subtitle.setObjectName("brandSubtitle")
        brand_text.addWidget(brand_name)
        brand_text.addWidget(brand_subtitle)
        brand.addWidget(logo)
        brand.addLayout(brand_text)
        brand.addStretch()
        add_task = QPushButton("+  Add task")
        add_task.setObjectName("secondaryButton")
        add_task.clicked.connect(self.add_task)
        start = QPushButton("Start queued transfers")
        start.setObjectName("primaryButton")
        start.clicked.connect(self.start_transfer)
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)
        layout.addLayout(brand)
        layout.addLayout(help_row)
        layout.addLayout(endpoint_row)
        layout.addWidget(task_title)
        layout.addWidget(add_task)
        layout.addWidget(self.task_list)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addWidget(start)
        container = QWidget()
        container.setObjectName("root")
        container.setLayout(layout)
        self.setCentralWidget(container)
        self._apply_theme()

    def _endpoint_card(
        self, title: str, subtitle: str, combo: QComboBox, path: QLineEdit
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("endpointCard")
        layout = QVBoxLayout(card)
        label = QLabel(title)
        label.setObjectName("cardTitle")
        hint = QLabel(subtitle)
        hint.setObjectName("cardHint")
        path.setPlaceholderText("/absolute/path/to/file")
        layout.addWidget(label)
        layout.addWidget(hint)
        layout.addWidget(combo)
        layout.addWidget(path)
        return card

    def _apply_theme(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget#root {
                background: #f5f8ff;
                color: #172554;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QFrame#endpointCard {
                background: #ffffff;
                border: 1px solid #dbeafe;
                border-radius: 18px;
                padding: 8px;
            }
            QLabel#cardTitle, QLabel#sectionLabel {
                color: #2563eb;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QLabel#brandName {
                color: #172554;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#brandSubtitle {
                color: #64748b;
                font-size: 12px;
            }
            QLabel#cardHint, QLabel#statusLabel {
                color: #64748b;
            }
            QLabel#transferArrow {
                color: #2563eb;
                font-size: 30px;
                font-weight: 700;
                min-width: 34px;
            }
            QComboBox, QLineEdit {
                background: #f8fbff;
                border: 1px solid #bfdbfe;
                border-radius: 9px;
                padding: 8px 10px;
                color: #172554;
            }
            QComboBox:focus, QLineEdit:focus {
                border: 2px solid #60a5fa;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #bfdbfe;
                border-radius: 9px;
                padding: 9px 14px;
                color: #1d4ed8;
                font-weight: 600;
            }
            QPushButton:hover { background: #eff6ff; }
            QPushButton#primaryButton {
                background: #2563eb;
                color: white;
                border: none;
                padding: 13px;
                font-size: 14px;
            }
            QPushButton#primaryButton:hover { background: #1d4ed8; }
            QPushButton#secondaryButton { background: #eff6ff; }
            QListWidget#taskList {
                background: #ffffff;
                border: 1px solid #dbeafe;
                border-radius: 12px;
                padding: 6px;
                color: #334155;
            }
            QProgressBar {
                background: #dbeafe;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: #2563eb;
                border-radius: 4px;
            }
        """)

    def reload_profiles(self) -> None:
        self.profiles = {p.id: p for p in self.store.list_profiles()}
        for combo in (self.source_combo, self.destination_combo):
            current_id = combo.currentData()
            combo.clear()
            combo.addItem("This computer", "")
            for profile in sorted(
                self.profiles.values(), key=lambda item: item.name.lower()
            ):
                combo.addItem(profile.name, profile.id)
            index = combo.findData(current_id)
            combo.setCurrentIndex(index if index >= 0 else 0)

    def manage_connections(self) -> None:
        dialog = ConnectionManagerDialog(self.store, self.profiles, self)
        dialog.profiles_changed.connect(self.reload_profiles)
        dialog.exec()

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
        self.worker.progress.connect(self.update_progress)
        self.worker.completed.connect(self.finish_transfer)
        self.worker.failed.connect(self.fail_transfer)
        self.thread.start()
        self.status.setText("Transferring...")
        self.requests = []

    @Slot(int, int)
    def update_progress(self, current: int, total: int) -> None:
        if total:
            self.progress.setValue(min(100, int(current * 100 / total)))

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
