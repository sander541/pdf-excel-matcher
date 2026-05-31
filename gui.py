from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
    QSplitter,
    QToolTip,
)
from PySide6.QtGui import QFontDatabase, QPalette, QColor

from pdf_excel_annotator.config import PipelineOptions
from pdf_excel_annotator.pipeline import run_pipeline
from pdf_excel_annotator.utils import is_valid_code_column
from pdf_excel_annotator.gui_helpers import (
    build_files_section,
    build_options_section,
    build_advanced_section,
    build_log_section,
    tooltip_text,
)
from pdf_excel_annotator.updater import check_for_updates, perform_update
from pdf_excel_annotator.version import __version__


class AnnotatorWorker(QThread):
    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, config: PipelineOptions) -> None:
        super().__init__()
        self.config = config

    def run(self) -> None:  # pragma: no cover - GUI worker
        try:
            options = self.config
            result = run_pipeline(
                options, progress_callback=lambda msg: self.progress.emit(msg)
            )
            output_dir = result.report_path.parent
            lines = [
                f"Files saved to {output_dir}"
            ]
            message = "\n".join(lines)
            if result.notes:
                note_lines = "\n".join(f"- {note}" for note in result.notes)
                message += f"\n\nNotes:\n{note_lines}"
            self.finished.emit(True, message)
        except Exception as exc:  # pragma: no cover - user feedback
            self.finished.emit(False, str(exc))


class UpdateCheckerWorker(QThread):
    update_available = Signal(dict)  # Emits update info if available
    check_complete = Signal()

    def run(self) -> None:  # pragma: no cover - update checker
        try:
            update_info = check_for_updates()
            if update_info:
                self.update_available.emit(update_info)
        except Exception:
            pass  # Silently fail - don't disrupt user workflow
        finally:
            self.check_complete.emit()


class AnnotatorWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"PDF ↔ Excel Annotator v{__version__}")
        self.worker: AnnotatorWorker | None = None
        app = QApplication.instance()
        self._orig_style = app.style().objectName() if app else ""
        self._orig_palette = app.palette() if app else None
        self._orig_stylesheet = app.styleSheet() if app else ""
        self._build_ui()
        self._check_for_updates_async()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        files = build_files_section(
            pick_excel=self._pick_excel,
            pick_output_dir=self._pick_output_dir,
            add_pdf=self._add_pdf,
            remove_pdf=self._remove_pdf,
            update_pdf_buttons=self._update_pdf_buttons,
        )
        self.excel_edit = files.excel_edit
        self.pdf_list = files.pdf_list
        self.add_pdf_btn = files.add_pdf_btn
        self.remove_pdf_btn = files.remove_pdf_btn
        self.output_dir_edit = files.output_dir_edit
        self.annotated_checkbox = files.annotated_checkbox

        options = build_options_section(self._toggle_limit_rows)
        self.code_column_edit = options.code_column_edit
        self.count_column_edit = options.count_column_edit
        self.header_row_edit = options.header_row_edit
        self.limit_rows_check = options.limit_rows_check
        self.max_row_spin = options.max_row_spin
        self.header_row_edit.textChanged.connect(self._sync_limit_rows_min)

        advanced = build_advanced_section()
        self.advanced_box = advanced.box
        self.word_span_spin = advanced.word_span_spin
        self.ocr_zoom_spin = advanced.ocr_zoom_spin
        self.ocr_conf_spin = advanced.ocr_conf_spin
        self.ocr_angles_edit = advanced.ocr_angles_edit
        self.enable_ocr_check = advanced.enable_ocr_check
        self.enable_vector_check = advanced.enable_vector_check
        self.dark_theme_check = advanced.dark_theme_check
        self.specifier_column_edit = advanced.specifier_column_edit
        self.specifier_radius_spin = advanced.specifier_radius_spin

        log_section = build_log_section()
        self.log = log_section.text_edit

        self.top_container = QWidget()
        self.top_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        container_layout = QVBoxLayout(self.top_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(12)
        container_layout.setAlignment(Qt.AlignTop)

        container_layout.addWidget(files.group)
        container_layout.addLayout(options.layout)

        toggle_row = QHBoxLayout()
        self.advanced_toggle = QToolButton(text="Show Advanced Options")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setChecked(False)
        self.advanced_toggle.setToolTip(tooltip_text("advanced_toggle"))
        self.advanced_toggle.clicked.connect(self._toggle_advanced)
        toggle_row.addWidget(self.advanced_toggle)
        toggle_row.addStretch()
        container_layout.addLayout(toggle_row)

        container_layout.addWidget(self.advanced_box)

        run_row = QHBoxLayout()
        self.run_button = QPushButton("Process")
        self.run_button.setToolTip(tooltip_text("process_button"))
        self.run_button.clicked.connect(self._run_job)
        self.run_button.setAutoDefault(True)
        self.run_button.setDefault(True)
        run_row.addWidget(self.run_button)
        run_row.addStretch()
        container_layout.addLayout(run_row)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.top_container)
        splitter.addWidget(log_section.container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([650, 250])
        main_layout.addWidget(splitter)

        self._update_pdf_buttons()
        # Default to dark theme on Windows for better appearance; user can toggle in Advanced.
        if sys.platform.startswith("win"):
            self.dark_theme_check.setChecked(True)
        self.dark_theme_check.toggled.connect(self._toggle_dark_theme)
        # Apply current theme selection immediately
        self._toggle_dark_theme(self.dark_theme_check.isChecked())

    def _toggle_dark_theme(self, enabled: bool) -> None:
        app = QApplication.instance()
        if not app:
            return
        if enabled:
            self._apply_dark_palette(app)
        else:
            # Restore original app visuals
            if self._orig_style:
                app.setStyle(self._orig_style)
            if self._orig_palette is not None:
                app.setPalette(self._orig_palette)
            app.setStyleSheet(self._orig_stylesheet)

    def _apply_dark_palette(self, app: QApplication) -> None:
        app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        app.setPalette(palette)
        # Keep existing tooltip styling and any other rules
        base_css = self._orig_stylesheet or ""
        app.setStyleSheet(base_css)

    def _pick_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Excel file",
            str(Path(self.excel_edit.text()).parent if self.excel_edit.text() else "."),
            "Excel Files (*.xlsx *.xlsm);;All Files (*)",
        )
        if path:
            self.excel_edit.setText(path)

    def _pick_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select output directory",
            self.output_dir_edit.text() or ".",
        )
        if path:
            self.output_dir_edit.setText(path)

    def _add_pdf(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF files",
            ".",
            "PDF Files (*.pdf);;All Files (*)",
        )
        if paths:
            self._add_pdf_paths(paths)

    def _remove_pdf(self) -> None:
        for item in self.pdf_list.selectedItems():
            row = self.pdf_list.row(item)
            self.pdf_list.takeItem(row)
        self._update_pdf_buttons()

    def _add_pdf_paths(self, paths: list[str]) -> None:
        added = False
        for path in paths:
            normalized = Path(path).expanduser()
            if not normalized.exists() or normalized.suffix.lower() != ".pdf":
                continue
            if not any(
                self.pdf_list.item(i).text() == str(normalized)
                for i in range(self.pdf_list.count())
            ):
                self.pdf_list.addItem(str(normalized))
                added = True
        if added:
            self.pdf_list.sortItems()
            self._update_pdf_buttons()
            self.pdf_list.items_changed.emit()

    def _toggle_advanced(self, checked: bool) -> None:
        self.advanced_box.setVisible(checked)
        self.advanced_toggle.setText(
            "Hide Advanced Options" if checked else "Show Advanced Options"
        )

    def _collect_config(self) -> PipelineOptions | None:
        excel_path = Path(self.excel_edit.text()).expanduser()
        if not excel_path.exists():
            QMessageBox.warning(self, "Missing Excel", "Excel file does not exist.")
            return None
        pdf_paths = [
            Path(self.pdf_list.item(i).text()).expanduser()
            for i in range(self.pdf_list.count())
        ]
        if not pdf_paths:
            QMessageBox.warning(self, "Missing PDFs", "Please add at least one PDF.")
            return None
        missing = [str(path) for path in pdf_paths if not path.exists()]
        if missing:
            QMessageBox.warning(
                self, "Missing PDFs", "The following PDFs do not exist:\n" + "\n".join(missing)
            )
            return None
        output_text = self.output_dir_edit.text().strip()
        if not output_text:
            QMessageBox.warning(self, "Output Directory", "Select an output directory.")
            return None
        output_dir = Path(output_text).expanduser()
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                QMessageBox.warning(self, "Output Error", str(exc))
                return None
        output_path = output_dir / "report.txt"
        annotated_dir = output_dir if self.annotated_checkbox.isChecked() else None

        code_column = self.code_column_edit.text().strip().upper()
        if not code_column:
            QMessageBox.warning(self, "Code Column", "Enter the Excel column that contains codes.")
            return None
        if not is_valid_code_column(code_column):
            QMessageBox.warning(
                self,
                "Code Column",
                "Code column must be Excel letters such as C or AA.",
            )
            return None

        count_column = self.count_column_edit.text().strip().upper()
        if count_column and not is_valid_code_column(count_column):
            QMessageBox.warning(
                self,
                "Count Column",
                "Count column must be Excel letters such as D or AA, or leave empty.",
            )
            return None

        specifier_column = self.specifier_column_edit.text().strip().upper()
        if specifier_column and not is_valid_code_column(specifier_column):
            QMessageBox.warning(
                self,
                "Specifier Column",
                "Specifier column must be Excel letters such as A or AA, or leave empty.",
            )
            return None

        header_text = self.header_row_edit.text().strip()
        if not header_text:
            QMessageBox.warning(self, "Header Row", "Enter the header row number.")
            return None
        try:
            header_row = int(header_text)
        except ValueError:
            QMessageBox.warning(self, "Header Row", "Header row must be numeric.")
            return None
        if header_row < 1:
            QMessageBox.warning(self, "Header Row", "Header row must be at least 1.")
            return None
        max_row = self.max_row_spin.value() if self.limit_rows_check.isChecked() else None
        if max_row is not None and max_row < header_row:
            QMessageBox.warning(
                self,
                "Row Limit",
                "Max row must be greater than or equal to the header row.",
            )
            return None

        try:
            angles = [
                int(part.strip())
                for part in self.ocr_angles_edit.text().split(",")
                if part.strip()
            ]
        except ValueError:
            QMessageBox.warning(self, "Invalid OCR Angles", "Angles must be integers.")
            return None

        return PipelineOptions(
            excel_path=excel_path,
            pdf_paths=pdf_paths,
            output_path=output_path,
            annotated_dir=annotated_dir,
            code_column=code_column,
            count_column=count_column or None,
            specifier_column=specifier_column or None,
            specifier_radius=float(self.specifier_radius_spin.value()),
            header_row=header_row,
            max_row=max_row,
            max_word_span=self.word_span_spin.value(),
            ocr_zoom=float(self.ocr_zoom_spin.value()),
            ocr_confidence=self.ocr_conf_spin.value(),
            ocr_angles=angles or [0],
            enable_ocr=self.enable_ocr_check.isChecked(),
            enable_vector_ocr=self.enable_vector_check.isChecked(),
        )

    def _run_job(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        config = self._collect_config()
        if not config:
            return
        self.log.append("\n--- Running pipeline ---")
        self.run_button.setEnabled(False)
        self.run_button.setText("Processing…")
        self.top_container.setEnabled(False)
        self.worker = AnnotatorWorker(config)
        self.worker.progress.connect(self._append_log)
        self.worker.finished.connect(self._job_finished)
        self.worker.start()

    def _append_log(self, message: str) -> None:
        stamp = datetime.now().strftime("[%H:%M:%S] ")
        self.log.append(f"{stamp}{message}")

    def _job_finished(self, success: bool, message: str) -> None:
        self.top_container.setEnabled(True)
        self.run_button.setEnabled(True)
        self.run_button.setText("Process")
        if success:
            QMessageBox.information(self, "Completed", message)
        else:
            QMessageBox.critical(self, "Error", message)
        self._append_log(message)
        self.worker = None

    def _toggle_limit_rows(self, checked: bool) -> None:
        self.max_row_spin.setEnabled(checked)
        self._sync_limit_rows_min()

    def _update_pdf_buttons(self) -> None:
        self.remove_pdf_btn.setEnabled(bool(self.pdf_list.selectedItems()))

    def _sync_limit_rows_min(self, _text: str | None = None) -> None:
        if not self.limit_rows_check.isChecked():
            self.max_row_spin.setMinimum(1)
            return
        try:
            header_row = max(1, int(self.header_row_edit.text().strip()))
        except ValueError:
            header_row = 1
        min_value = header_row + 1
        max_allowed = self.max_row_spin.maximum()
        if min_value > max_allowed:
            min_value = max_allowed
        self.max_row_spin.setMinimum(min_value)
        if self.max_row_spin.value() < min_value:
            self.max_row_spin.setValue(min_value)

    def _check_for_updates_async(self) -> None:
        """Check for updates in background without blocking UI."""
        self.update_checker = UpdateCheckerWorker()
        self.update_checker.update_available.connect(self._on_update_available)
        self.update_checker.start()

    def _on_update_available(self, update_info: dict) -> None:
        """Prompt user when update is available."""
        import webbrowser
        from pdf_excel_annotator.updater import GITHUB_REPO

        new_version = update_info.get("version", "unknown")

        if sys.platform != "win32":
            # Auto-install is Windows-only; direct other platforms to the releases page.
            reply = QMessageBox.question(
                self,
                "Update Available",
                f"A new version ({new_version}) is available.\n\n"
                "Auto-install is only supported on Windows.\n"
                "Would you like to open the releases page to download it manually?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases/latest")
            return

        reply = QMessageBox.question(
            self,
            "Update Available",
            f"A new version ({new_version}) is available.\n\nWould you like to update now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            self._perform_update(update_info)

    def _perform_update(self, update_info: dict) -> None:
        """Download and install the update."""
        try:
            # Get path to current executable
            if getattr(sys, "frozen", False):
                # Running as PyInstaller bundle
                current_exe = Path(sys.executable)
            else:
                # Running as script - this shouldn't happen in production
                QMessageBox.warning(
                    self,
                    "Update Not Available",
                    "Update is only available for packaged releases.",
                )
                return

            # Perform the update
            if perform_update(update_info, current_exe):
                QMessageBox.information(
                    self,
                    "Update Installed",
                    "Update has been installed. The application will restart.",
                )
                from pdf_excel_annotator.updater import restart_application

                restart_application(current_exe)
            else:
                QMessageBox.critical(
                    self,
                    "Update Failed",
                    "Failed to install update. Please try again later.",
                )
        except Exception as exc:
            QMessageBox.critical(self, "Update Error", f"Error during update: {exc}")

def main() -> int:  # pragma: no cover - GUI launcher
    app = QApplication(sys.argv)
    QToolTip.setFont(QFontDatabase.systemFont(QFontDatabase.GeneralFont))
    app.setStyleSheet(
        (app.styleSheet() or "")
        + """
QToolTip {
    background-color: rgba(20, 20, 20, 240);
    color: rgba(255, 255, 255, 235);
    padding: 7px 9px;
    border: 1px solid rgba(255, 255, 255, 60);
    border-radius: 7px;
    font-size: 11px;
    max-width: 420px;
}
"""
    )
    window = AnnotatorWindow()
    window.resize(900, 600)
    window.show()
    return app.exec()

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
