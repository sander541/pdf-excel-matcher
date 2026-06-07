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
    "annotated_pdfs": "Annotated PDFs\nEnable to save annotated PDF copies with highlighted matches and detail popups.\nOtherwise only the matching report is written.",
    "code_column": "Code column\nExcel column letter that stores the codes to find (e.g., B or AA).",
    "count_column": "Count column\nOptional: Excel column with how many times each code should appear on the drawings (e.g., C).\nIf set, the report shows how many were found vs. expected.",
    "specifier_column": "Specifier column\nOptional: Excel column whose value (e.g., a door number) is printed next to the code on the drawing.\nWhen the same code appears multiple times, this pinpoints which occurrence belongs to which row.",
    "specifier_radius": "Specifier search area\nHow close (in inches, default ≈ 1.1\") the specifier value must be to the code on the drawing.\nDecrease for dense plans where codes are tightly packed; increase for large sheets.",
    "specifier_radius_hint": "Search area\nDefault 80 pt ≈ 1.1 inch. Decrease if nearby codes interfere; increase for large A0 sheets.",
    "header_row": "Header row\nRow number that contains the column titles; data starts on the next row.",
    "row_limit": "Limit rows\nEnable to stop reading the Excel sheet after a set number of rows — useful for testing.",
    "max_row": "Max row\nHighest Excel row to read when 'Limit rows' is checked.",
    "advanced_toggle": "Advanced options\nShow or hide matching and appearance tuning controls.",
    "word_span": "Max word span\nHow many adjacent words in the drawing are joined together when searching for a code.\nIncrease if codes are split across multiple words on the drawing.",
    "word_span_hint": "Word span\nIncrease to catch codes split across multiple text tokens (e.g., 'V MP U-1' found as three words).",
    "dark_theme": "Dark theme\nUse a darker colour scheme — better suited for Windows and low-light environments.",
    "process_button": "Process\nStart scanning — reads the Excel codes, searches all PDFs, writes the report and annotated copies.",
    "clear_log": "Clear log\nRemove all messages from the log panel.",
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
class OptionsGridSection:
    """Combined options + advanced settings in one aligned grid."""
    container: QWidget
    code_column_edit: QLineEdit
    count_column_edit: QLineEdit
    header_row_edit: QLineEdit
    limit_rows_check: QCheckBox
    max_row_spin: QSpinBox
    word_span_spin: QSpinBox
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


def build_options_grid(toggle_limit_rows: Callable[[bool], None]) -> OptionsGridSection:
    """Build options + advanced as a two-row QGridLayout so columns align perfectly."""
    container = QWidget()
    grid = QGridLayout(container)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(8)
    # Last column absorbs leftover space; all input columns are fixed-size.
    grid.setColumnStretch(7, 1)

    INPUT_W = 70

    def _lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return lbl

    def _cell(*widgets) -> QWidget:
        """Wrap input + hint tightly; size policy keeps it from stretching."""
        w = QWidget()
        w.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        for item in widgets:
            lay.addWidget(item)
        return w

    # ── Row 0: Code column | Count column | Header row | Limit rows ──────────

    grid.addWidget(_lbl("Code column:"), 0, 0)
    code_column_edit = QLineEdit()
    code_column_edit.setFixedWidth(INPUT_W)
    code_column_edit.setPlaceholderText("e.g. C")
    code_column_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z]{1,3}$")))
    code_column_edit.setToolTip(tooltip_text("code_column"))
    grid.addWidget(_cell(code_column_edit, HintLabel(tooltip_text("code_column"))), 0, 1)

    grid.addWidget(_lbl("Count column:"), 0, 2)
    count_column_edit = QLineEdit()
    count_column_edit.setFixedWidth(INPUT_W)
    count_column_edit.setPlaceholderText("(optional)")
    count_column_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z]{0,3}$")))
    count_column_edit.setToolTip(tooltip_text("count_column"))
    grid.addWidget(_cell(count_column_edit, HintLabel(tooltip_text("count_column"))), 0, 3)

    grid.addWidget(_lbl("Header row:"), 0, 4)
    header_row_edit = QLineEdit()
    header_row_edit.setFixedWidth(INPUT_W)
    header_row_edit.setPlaceholderText("e.g. 1")
    header_row_edit.setValidator(QIntValidator(1, 100000))
    header_row_edit.setToolTip(tooltip_text("header_row"))
    grid.addWidget(_cell(header_row_edit, HintLabel(tooltip_text("header_row"))), 0, 5)

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
    grid.addWidget(_cell(limit_rows_check, max_row_spin, HintLabel(tooltip_text("row_limit"))), 0, 6)

    # ── Row 1: Max word span | Specifier column | Specifier radius | Dark theme

    grid.addWidget(_lbl("Max word span:"), 1, 0)
    word_span_spin = QSpinBox()
    word_span_spin.setMinimum(1)
    word_span_spin.setValue(4)
    word_span_spin.setFixedWidth(INPUT_W)
    word_span_spin.setToolTip(tooltip_text("word_span"))
    grid.addWidget(_cell(word_span_spin, HintLabel(tooltip_text("word_span_hint"))), 1, 1)

    grid.addWidget(_lbl("Specifier column:"), 1, 2)
    specifier_column_edit = QLineEdit()
    specifier_column_edit.setFixedWidth(INPUT_W)
    specifier_column_edit.setPlaceholderText("(optional)")
    specifier_column_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z]{0,3}$")))
    specifier_column_edit.setToolTip(tooltip_text("specifier_column"))
    grid.addWidget(_cell(specifier_column_edit, HintLabel(tooltip_text("specifier_column"))), 1, 3)

    grid.addWidget(_lbl("Specifier radius (pt):"), 1, 4)
    specifier_radius_spin = QSpinBox()
    specifier_radius_spin.setMinimum(10)
    specifier_radius_spin.setMaximum(500)
    specifier_radius_spin.setValue(80)
    specifier_radius_spin.setFixedWidth(INPUT_W)
    specifier_radius_spin.setToolTip(tooltip_text("specifier_radius"))
    grid.addWidget(_cell(specifier_radius_spin, HintLabel(tooltip_text("specifier_radius_hint"))), 1, 5)

    dark_theme_check = QCheckBox("Dark theme")
    dark_theme_check.setToolTip(tooltip_text("dark_theme"))
    grid.addWidget(_cell(dark_theme_check, HintLabel(tooltip_text("dark_theme"))), 1, 6)

    return OptionsGridSection(
        container=container,
        code_column_edit=code_column_edit,
        count_column_edit=count_column_edit,
        header_row_edit=header_row_edit,
        limit_rows_check=limit_rows_check,
        max_row_spin=max_row_spin,
        word_span_spin=word_span_spin,
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
