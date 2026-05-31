from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import textwrap

from PySide6.QtCore import QPoint, QEvent, Qt, Signal, QRegularExpression
from PySide6.QtGui import QPainter, QPalette, QRegularExpressionValidator, QIntValidator, QFontDatabase
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QMenu,
    QPushButton,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLineEdit,
    QFormLayout,
    QGroupBox,
    QCheckBox,
    QSpinBox,
    QSizePolicy,
    QToolTip,
    QToolButton,
    QTextEdit,
    QStyle,
    QGridLayout,
)


TOOLTIPS: dict[str, str] = {
    "excel_file": "Excel workbook\nSelect the spreadsheet that lists all codes and related data. Only the active sheet is read.",
    "pdf_files": "PDF inputs\nEvery file shown here is scanned for the Excel codes on every page.",
    "add_pdf": "Add PDFs\nOpen a file picker and append one or more PDFs to the list.",
    "remove_pdf": "Remove PDFs\nDelete the currently selected entries from the list.",
    "output_directory": "Output directory\nThe generated report and any annotated PDFs are saved inside this folder.",
    "annotated_pdfs": "Highlighted copies\nEnable to save annotated PDF copies for visual review.\nOtherwise only matching report is created for review.",
    "code_column": "Code column\nExcel column letter(s) that store the codes (e.g., C or AA).",
    "count_column": "Count column\nOptional: Excel column letter with expected occurrence counts (e.g., D).\nIf provided, the tool finds N occurrences per code instead of just 1.",
    "specifier_column": "Specifier column\nOptional: Excel column letter whose value appears near the code in the PDF (e.g., A for room/door numbers).\nUsed to assign the correct PDF location when the same code appears multiple times.",
    "specifier_radius": "Specifier radius\nSearch radius in PDF points when looking for specifier values near a code (default: 80).\nReduce for dense CAD drawings; increase for large A0 sheets.",
    "specifier_radius_hint": "Proximity radius\n80 pt ≈ 1.1 inch. Decrease if codes bleed across rooms; increase for large sheets.",
    "header_row": "Header row\nRow number that contains the column titles; data starts on the next row.",
    "row_limit": "Row ceiling\nEnable if you want to scan only the first N Excel rows.",
    "max_row": "Max row\nHighest Excel row inspected whenever 'Limit rows' is enabled.",
    "advanced_toggle": "Advanced options\nShow or hide OCR and matching tuning controls.",
    "word_span": "Max word span\nHow many adjacent PDF words are concatenated before matching.",
    "word_span_hint": "Word span\nIncrease to catch codes that break across multiple OCR words (e.g., V MP U-1).",
    "ocr_zoom": "OCR zoom\nRendering zoom before OCR; higher values sharpen tiny text but take longer.",
    "ocr_zoom_hint": "Zoom factor\nBoost if codes are tiny; decrease to speed things up when text is large.",
    "ocr_conf": "OCR confidence\nMinimum OCR score accepted; lower it to keep more words (and more noise).",
    "ocr_conf_hint": "Confidence filter\nReduce to keep shaky OCR hits, increase to keep only high-confidence words.",
    "ocr_angles": "OCR angles\nComma-separated rotation angles (degrees) applied during OCR (e.g., 0,90,180).",
    "ocr_angles_hint": "Rotation passes\nUse when labels may appear rotated—add angles like 45 if needed.",
    "enable_ocr": "OCR fallback\nEnable when PDFs lack a text layer; performs slower raster OCR per page.",
    "enable_ocr_hint": "OCR fallback\nTurn on when native text extraction misses labels; expect longer runs.",
    "enable_vector": "Vector OCR\nAttempt to OCR CAD-style vector labels (door tags, etc.).",
    "enable_vector_hint": "Vector labels\nScans likely label rectangles even when there is no text layer.",
    "dark_theme": "Dark theme\nUse a darker palette better suited for Windows and low‑light environments.",
    "process_button": "Process files\nScan PDFs, generate the report, and write annotated copies if enabled.",
    "clear_log": "Clear log\nRemove every log message from this session.",
}


def tooltip_text(key: str) -> str:
    return TOOLTIPS.get(key, "")


class PdfListWidget(QListWidget):
    items_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.placeholder_text = "Drop PDFs here\n(or click Add PDF…)"
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if not self.count():
            painter = QPainter(self.viewport())
            painter.setPen(self.palette().color(QPalette.Disabled, QPalette.Text))
            painter.drawText(
                self.viewport().rect().adjusted(12, 12, -12, -12),
                Qt.AlignCenter | Qt.TextWordWrap,
                self.placeholder_text,
            )

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasUrls():
            return super().dropEvent(event)
        added = False
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path or not path.lower().endswith(".pdf"):
                continue
            if not any(self.item(i).text() == path for i in range(self.count())):
                self.addItem(path)
                added = True
        if added:
            self.sortItems()
            event.acceptProposedAction()
            self.items_changed.emit()

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        clear_action = menu.addAction("Clear list")
        clear_action.setEnabled(self.count() > 0)
        action = menu.exec(event.globalPos())
        if action == clear_action:
            self.clear()
            self.items_changed.emit()


class HintLabel(QLabel):
    def __init__(self, hint_text: str, parent: QWidget | None = None) -> None:
        super().__init__("i", parent)
        self.hint_text = hint_text
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(14, 14)
        self.setStyleSheet(
            "QLabel {"
            "  color: rgba(255,255,255,200);"
            "  background-color: rgba(255,255,255,28);"
            "  border: 1px solid rgba(255,255,255,45);"
            "  border-radius: 7px;"
            "  font-size: 12px;"
            "  font-weight: 700;"
            "}"
            "QLabel:hover {"
            "  color: rgba(255,255,255,245);"
            "  background-color: rgba(255,255,255,48);"
            "  border-color: rgba(255,255,255,80);"
            "}"
        )

    def event(self, event) -> bool:  # type: ignore[override]
        if event.type() == QEvent.ToolTip:
            global_pos = self.mapToGlobal(self.rect().bottomRight()) + QPoint(2, 2)
            parts: list[str] = []
            for line in self.hint_text.splitlines():
                if not line.strip():
                    parts.append("")
                else:
                    parts.append(textwrap.fill(line, width=52))
            wrapped = "\n".join(parts)
            QToolTip.showText(global_pos, wrapped, self, self.rect(), 8000)
            return True
        if event.type() == QEvent.Leave:
            QToolTip.hideText()
        return super().event(event)


@dataclass
class FilesSection:
    group: QGroupBox
    excel_edit: QLineEdit
    pdf_list: PdfListWidget
    add_pdf_btn: QPushButton
    remove_pdf_btn: QPushButton
    output_dir_edit: QLineEdit
    annotated_checkbox: QCheckBox


@dataclass
class OptionsSection:
    layout: QHBoxLayout
    code_column_edit: QLineEdit
    count_column_edit: QLineEdit
    header_row_edit: QLineEdit
    limit_rows_check: QCheckBox
    max_row_spin: QSpinBox


@dataclass
class AdvancedSection:
    box: QGroupBox
    word_span_spin: QSpinBox
    ocr_zoom_spin: QSpinBox
    ocr_conf_spin: QSpinBox
    ocr_angles_edit: QLineEdit
    enable_ocr_check: QCheckBox
    enable_vector_check: QCheckBox
    dark_theme_check: QCheckBox
    specifier_column_edit: QLineEdit
    specifier_radius_spin: QSpinBox


@dataclass
class LogSection:
    container: QWidget
    text_edit: QTextEdit


def build_files_section(
    *,
    pick_excel: Callable[[], None],
    pick_output_dir: Callable[[], None],
    add_pdf: Callable[[], None],
    remove_pdf: Callable[[], None],
    update_pdf_buttons: Callable[[], None],
) -> FilesSection:
    group = QGroupBox("Files")
    group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    form = QFormLayout()
    form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
    form.setFormAlignment(Qt.AlignLeft)
    form.setVerticalSpacing(10)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.DontWrapRows)

    excel_edit = QLineEdit()
    excel_edit.setPlaceholderText("Select Excel workbook…")
    excel_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    excel_edit.setToolTip(tooltip_text("excel_file"))
    excel_row = QWidget()
    excel_layout = QHBoxLayout(excel_row)
    excel_layout.setContentsMargins(0, 0, 0, 0)
    excel_layout.setSpacing(8)
    excel_layout.addWidget(excel_edit)
    excel_btn = QPushButton("Browse…")
    excel_btn.setMinimumWidth(90)
    excel_btn.clicked.connect(pick_excel)
    excel_layout.addWidget(excel_btn)
    excel_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    form.addRow(create_label_with_hint("Excel file:", "excel_file"), excel_row)

    pdf_list = PdfListWidget()
    pdf_list.setMinimumHeight(120)
    pdf_list.setToolTip(tooltip_text("pdf_files"))
    pdf_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    pdf_list.items_changed.connect(update_pdf_buttons)
    pdf_list.itemSelectionChanged.connect(update_pdf_buttons)
    pdf_row = QWidget()
    pdf_row_layout = QHBoxLayout(pdf_row)
    pdf_row_layout.setContentsMargins(0, 0, 0, 0)
    pdf_row_layout.setSpacing(8)
    pdf_row_layout.addWidget(pdf_list)
    pdf_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    buttons = QWidget()
    buttons.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
    btn_layout = QVBoxLayout(buttons)
    btn_layout.setContentsMargins(0, 6, 0, 0)
    btn_layout.setSpacing(6)
    add_pdf_btn = QPushButton("Add PDF…")
    add_pdf_btn.setIcon(buttons.style().standardIcon(QStyle.SP_DialogOpenButton))
    add_pdf_btn.setToolTip(tooltip_text("add_pdf"))
    add_pdf_btn.clicked.connect(add_pdf)
    remove_pdf_btn = QPushButton("Remove Selected")
    remove_pdf_btn.setIcon(buttons.style().standardIcon(QStyle.SP_TrashIcon))
    remove_pdf_btn.setToolTip(tooltip_text("remove_pdf"))
    remove_pdf_btn.clicked.connect(remove_pdf)
    remove_pdf_btn.setEnabled(False)
    btn_layout.addWidget(add_pdf_btn)
    btn_layout.addWidget(remove_pdf_btn)
    btn_layout.addStretch()
    pdf_row_layout.addWidget(buttons)
    pdf_row_layout.setStretch(0, 1)
    form.addRow(create_label_with_hint("PDF files:", "pdf_files"), pdf_row)

    output_dir_edit = QLineEdit()
    output_dir_edit.setPlaceholderText("Select output folder…")
    output_dir_edit.setToolTip(tooltip_text("output_directory"))
    output_row = QWidget()
    output_layout = QHBoxLayout(output_row)
    output_layout.setContentsMargins(0, 0, 0, 0)
    output_layout.setSpacing(8)
    output_layout.addWidget(output_dir_edit)
    output_btn = QPushButton("Browse…")
    output_btn.setMinimumWidth(90)
    output_btn.clicked.connect(pick_output_dir)
    output_layout.addWidget(output_btn)
    form.addRow(create_label_with_hint("Output directory:", "output_directory"), output_row)

    annotated_checkbox = QCheckBox("Also save annotated PDFs in this directory")
    annotated_checkbox.setChecked(True)
    annotated_checkbox.setToolTip(tooltip_text("annotated_pdfs"))
    annotated_row = QWidget()
    annotated_layout = QHBoxLayout(annotated_row)
    annotated_layout.setContentsMargins(0, 0, 0, 0)
    annotated_layout.addWidget(annotated_checkbox)
    annotated_layout.addStretch()
    form.addRow(create_label_with_hint("Annotated PDFs:", "annotated_pdfs"), annotated_row)

    group.setLayout(form)
    return FilesSection(
        group=group,
        excel_edit=excel_edit,
        pdf_list=pdf_list,
        add_pdf_btn=add_pdf_btn,
        remove_pdf_btn=remove_pdf_btn,
        output_dir_edit=output_dir_edit,
        annotated_checkbox=annotated_checkbox,
    )


def build_options_section(toggle_limit_rows: Callable[[bool], None]) -> OptionsSection:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(10)

    code_widget = QWidget()
    code_layout = QHBoxLayout(code_widget)
    code_layout.setContentsMargins(0, 0, 0, 0)
    code_layout.setSpacing(6)
    code_layout.addWidget(QLabel("Code column:"))
    code_column_edit = QLineEdit()
    code_column_edit.setFixedWidth(70)
    code_column_edit.setPlaceholderText("e.g. C")
    code_column_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z]{1,3}$")))
    code_column_edit.setToolTip(tooltip_text("code_column"))
    code_layout.addWidget(code_column_edit)
    code_layout.addWidget(HintLabel(tooltip_text("code_column")))
    code_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

    count_widget = QWidget()
    count_layout = QHBoxLayout(count_widget)
    count_layout.setContentsMargins(0, 0, 0, 0)
    count_layout.setSpacing(6)
    count_layout.addWidget(QLabel("Count column:"))
    count_column_edit = QLineEdit()
    count_column_edit.setFixedWidth(70)
    count_column_edit.setPlaceholderText("(optional)")
    count_column_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z]{0,3}$")))
    count_column_edit.setToolTip(tooltip_text("count_column"))
    count_layout.addWidget(count_column_edit)
    count_layout.addWidget(HintLabel(tooltip_text("count_column")))
    count_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

    header_widget = QWidget()
    header_layout = QHBoxLayout(header_widget)
    header_layout.setContentsMargins(0, 0, 0, 0)
    header_layout.setSpacing(6)
    header_layout.addWidget(QLabel("Header row:"))
    header_row_edit = QLineEdit()
    header_row_edit.setFixedWidth(70)
    header_row_edit.setPlaceholderText("e.g. 1")
    header_row_edit.setValidator(QIntValidator(1, 100000))
    header_row_edit.setToolTip(tooltip_text("header_row"))
    header_layout.addWidget(header_row_edit)
    header_layout.addWidget(HintLabel(tooltip_text("header_row")))
    header_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

    limit_widget = QWidget()
    limit_layout = QHBoxLayout(limit_widget)
    limit_layout.setContentsMargins(0, 0, 0, 0)
    limit_layout.setSpacing(6)
    limit_rows_check = QCheckBox("Limit rows")
    limit_rows_check.setToolTip(tooltip_text("row_limit"))
    limit_rows_check.toggled.connect(toggle_limit_rows)
    max_row_spin = QSpinBox()
    max_row_spin.setMinimum(1)
    max_row_spin.setMaximum(100000)
    max_row_spin.setValue(1)
    max_row_spin.setFixedWidth(90)
    max_row_spin.setEnabled(False)
    max_row_spin.setToolTip(tooltip_text("max_row"))
    limit_layout.addWidget(limit_rows_check)
    limit_layout.addWidget(max_row_spin)
    limit_layout.addWidget(HintLabel(tooltip_text("row_limit")))
    limit_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

    row.addWidget(code_widget)
    row.addSpacing(10)
    row.addWidget(count_widget)
    row.addSpacing(16)
    row.addWidget(header_widget)
    row.addSpacing(16)
    row.addWidget(limit_widget)
    row.addStretch(1)

    return OptionsSection(
        layout=row,
        code_column_edit=code_column_edit,
        count_column_edit=count_column_edit,
        header_row_edit=header_row_edit,
        limit_rows_check=limit_rows_check,
        max_row_spin=max_row_spin,
    )


def build_advanced_section() -> AdvancedSection:
    box = QGroupBox()
    box.setVisible(False)
    layout = QGridLayout(box)

    layout.addWidget(QLabel("Max word span:"), 0, 0)
    word_span_spin = QSpinBox()
    word_span_spin.setMinimum(1)
    word_span_spin.setValue(4)
    word_span_spin.setToolTip(tooltip_text("word_span"))
    word_row = QWidget()
    word_layout = QHBoxLayout(word_row)
    word_layout.setContentsMargins(0, 0, 0, 0)
    word_layout.setSpacing(4)
    word_layout.addWidget(word_span_spin)
    word_layout.addWidget(HintLabel(tooltip_text("word_span_hint")))
    layout.addWidget(word_row, 0, 1)

    layout.addWidget(QLabel("OCR zoom:"), 0, 2)
    ocr_zoom_spin = QSpinBox()
    ocr_zoom_spin.setMinimum(1)
    ocr_zoom_spin.setMaximum(10)
    ocr_zoom_spin.setValue(2)
    ocr_zoom_spin.setToolTip(tooltip_text("ocr_zoom"))
    zoom_row = QWidget()
    zoom_layout = QHBoxLayout(zoom_row)
    zoom_layout.setContentsMargins(0, 0, 0, 0)
    zoom_layout.setSpacing(4)
    zoom_layout.addWidget(ocr_zoom_spin)
    zoom_layout.addWidget(HintLabel(tooltip_text("ocr_zoom_hint")))
    layout.addWidget(zoom_row, 0, 3)

    layout.addWidget(QLabel("OCR confidence:"), 1, 0)
    ocr_conf_spin = QSpinBox()
    ocr_conf_spin.setRange(0, 100)
    ocr_conf_spin.setValue(90)
    ocr_conf_spin.setToolTip(tooltip_text("ocr_conf"))
    conf_row = QWidget()
    conf_layout = QHBoxLayout(conf_row)
    conf_layout.setContentsMargins(0, 0, 0, 0)
    conf_layout.setSpacing(4)
    conf_layout.addWidget(ocr_conf_spin)
    conf_layout.addWidget(HintLabel(tooltip_text("ocr_conf_hint")))
    layout.addWidget(conf_row, 1, 1)

    layout.addWidget(QLabel("OCR angles:"), 1, 2)
    ocr_angles_edit = QLineEdit("0,90,180,270")
    ocr_angles_edit.setToolTip(tooltip_text("ocr_angles"))
    angles_row = QWidget()
    angles_layout = QHBoxLayout(angles_row)
    angles_layout.setContentsMargins(0, 0, 0, 0)
    angles_layout.setSpacing(4)
    angles_layout.addWidget(ocr_angles_edit)
    angles_layout.addWidget(HintLabel(tooltip_text("ocr_angles_hint")))
    layout.addWidget(angles_row, 1, 3)

    enable_ocr_check = QCheckBox("Enable OCR")
    enable_ocr_check.setToolTip(tooltip_text("enable_ocr"))
    ocr_row = QWidget()
    ocr_row_layout = QHBoxLayout(ocr_row)
    ocr_row_layout.setContentsMargins(0, 0, 0, 0)
    ocr_row_layout.setSpacing(4)
    ocr_row_layout.addWidget(enable_ocr_check)
    ocr_row_layout.addWidget(HintLabel(tooltip_text("enable_ocr_hint")))
    ocr_row_layout.addStretch()
    layout.addWidget(ocr_row, 2, 0, 1, 2)

    enable_vector_check = QCheckBox("Enable vector OCR")
    enable_vector_check.setToolTip(tooltip_text("enable_vector"))
    vector_row = QWidget()
    vector_layout = QHBoxLayout(vector_row)
    vector_layout.setContentsMargins(0, 0, 0, 0)
    vector_layout.setSpacing(4)
    vector_layout.addWidget(enable_vector_check)
    vector_layout.addWidget(HintLabel(tooltip_text("enable_vector_hint")))
    vector_layout.addStretch()
    layout.addWidget(vector_row, 2, 2, 1, 2)

    # Appearance
    dark_theme_check = QCheckBox("Use dark theme")
    dark_theme_check.setToolTip(tooltip_text("dark_theme"))
    theme_row = QWidget()
    theme_layout = QHBoxLayout(theme_row)
    theme_layout.setContentsMargins(0, 0, 0, 0)
    theme_layout.setSpacing(4)
    theme_layout.addWidget(dark_theme_check)
    theme_layout.addWidget(HintLabel(tooltip_text("dark_theme")))
    theme_layout.addStretch()
    layout.addWidget(theme_row, 3, 0, 1, 4)

    # Specifier (duplicate-code disambiguation) — placed in Advanced because it's
    # an edge-case feature; keeping it here prevents the main options bar from overflowing.
    layout.addWidget(QLabel("Specifier column:"), 4, 0)
    specifier_column_edit = QLineEdit()
    specifier_column_edit.setFixedWidth(70)
    specifier_column_edit.setPlaceholderText("(optional)")
    specifier_column_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z]{0,3}$")))
    specifier_column_edit.setToolTip(tooltip_text("specifier_column"))
    spec_col_row = QWidget()
    spec_col_layout = QHBoxLayout(spec_col_row)
    spec_col_layout.setContentsMargins(0, 0, 0, 0)
    spec_col_layout.setSpacing(4)
    spec_col_layout.addWidget(specifier_column_edit)
    spec_col_layout.addWidget(HintLabel(tooltip_text("specifier_column")))
    layout.addWidget(spec_col_row, 4, 1)

    layout.addWidget(QLabel("Specifier radius (pt):"), 4, 2)
    specifier_radius_spin = QSpinBox()
    specifier_radius_spin.setMinimum(10)
    specifier_radius_spin.setMaximum(500)
    specifier_radius_spin.setValue(80)
    specifier_radius_spin.setToolTip(tooltip_text("specifier_radius"))
    spec_rad_row = QWidget()
    spec_rad_layout = QHBoxLayout(spec_rad_row)
    spec_rad_layout.setContentsMargins(0, 0, 0, 0)
    spec_rad_layout.setSpacing(4)
    spec_rad_layout.addWidget(specifier_radius_spin)
    spec_rad_layout.addWidget(HintLabel(tooltip_text("specifier_radius_hint")))
    layout.addWidget(spec_rad_row, 4, 3)

    return AdvancedSection(
        box=box,
        word_span_spin=word_span_spin,
        ocr_zoom_spin=ocr_zoom_spin,
        ocr_conf_spin=ocr_conf_spin,
        ocr_angles_edit=ocr_angles_edit,
        enable_ocr_check=enable_ocr_check,
        enable_vector_check=enable_vector_check,
        dark_theme_check=dark_theme_check,
        specifier_column_edit=specifier_column_edit,
        specifier_radius_spin=specifier_radius_spin,
    )


def build_log_section() -> LogSection:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    text_edit = QTextEdit()
    text_edit.setReadOnly(True)
    text_edit.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
    text_edit.setPlainText("Ready. Select Excel + PDFs, then Process.")
    text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    text_edit.setMinimumHeight(120)

    bar = QHBoxLayout()
    bar.setContentsMargins(0, 0, 0, 0)
    bar.addWidget(QLabel("Log"))
    bar.addStretch()
    clear_btn = QToolButton()
    clear_btn.setIcon(container.style().standardIcon(QStyle.SP_TrashIcon))
    clear_btn.setToolTip(tooltip_text("clear_log"))
    clear_btn.clicked.connect(text_edit.clear)
    bar.addWidget(clear_btn)

    layout.addLayout(bar)
    layout.addWidget(text_edit)
    return LogSection(container=container, text_edit=text_edit)


def create_label_with_hint(text: str, key: str) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    label = QLabel(text)
    label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    layout.addWidget(label)
    layout.addWidget(HintLabel(tooltip_text(key)))
    layout.addStretch()
    return container
