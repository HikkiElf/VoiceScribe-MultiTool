import os
import time
from PyQt6.QtCore import pyqtSlot, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QCheckBox, QTextEdit,
    QFileDialog, QMessageBox, QFrame, QProgressBar, QSpinBox, QLineEdit,
    QListWidget, QStackedWidget
)
from .style import MODERN_STYLE

class VoiceScribeView(QMainWindow):
    """
    View class responsible for laying out widgets, applying styling,
    and rendering state. It contains no business logic.
    """
    
    # Custom signals for complex close events if needed
    close_requested = pyqtSignal(object) # passes the close event
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VoiceScribe-MultiTool")
        self.resize(1000, 800)
        self.setMinimumSize(900, 700)
        
        self.setup_ui()
        self.setStyleSheet(MODERN_STYLE)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # Top Configuration Block: Hugging Face Key Setup
        token_frame = QFrame()
        token_frame.setObjectName("Card")
        token_layout = QHBoxLayout(token_frame)
        token_layout.setContentsMargins(12, 10, 12, 10)
        
        token_label = QLabel("<b>Hugging Face Token (HF_TOKEN):</b>")
        token_label.setStyleSheet("color: #e1e1e6; font-size: 13px;")
        token_layout.addWidget(token_label)

        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Вставьте ваш hf_... токен для работы диаризации")
        token_layout.addWidget(self.token_input, 1)

        self.btn_toggle_token = QPushButton("Показать")
        token_layout.addWidget(self.btn_toggle_token)

        self.btn_save_token = QPushButton("Сохранить в .env")
        token_layout.addWidget(self.btn_save_token)

        main_layout.addWidget(token_frame)

        # Main Split Layout
        split_layout = QHBoxLayout()
        split_layout.setSpacing(16)

        # Left Sidebar (Navigation)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(240)

        self.sidebar.addItem("🎙️ Живая запись (GigaAM)")
        self.sidebar.addItem("👥 Разделение (GigaAM)")
        self.sidebar.addItem("👥 Разделение (WhisperX)")

        split_layout.addWidget(self.sidebar)

        # Right Working Area
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(14)

        self.stack = QStackedWidget()

        self.tab_giga = QWidget()
        self.tab_giga_diarize = QWidget()
        self.tab_whisper = QWidget()

        self.stack.addWidget(self.tab_giga)
        self.stack.addWidget(self.tab_giga_diarize)
        self.stack.addWidget(self.tab_whisper)

        right_layout.addWidget(self.stack, 1)

        # System Activity Logs Dashboard Terminal
        log_frame = QFrame()
        log_frame.setObjectName("Card")
        log_layout = QVBoxLayout(log_frame)

        log_header_layout = QHBoxLayout()
        log_title = QLabel("📊 Мониторинг и вывод в реальном времени")
        log_title.setStyleSheet("font-weight: bold; color: #9871ff; font-size: 13px;")
        log_header_layout.addWidget(log_title)

        self.btn_copy_log = QPushButton("📋 Скопировать лог")
        log_header_layout.addWidget(self.btn_copy_log, 0, Qt.AlignmentFlag.AlignRight)
        log_layout.addLayout(log_header_layout)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        right_layout.addWidget(log_frame, 1)

        split_layout.addLayout(right_layout, 1)
        main_layout.addLayout(split_layout, 1)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        self.setup_giga_tab()
        self.setup_giga_diarize_tab()
        self.setup_whisper_tab()

    def setup_giga_tab(self):
        layout = QVBoxLayout(self.tab_giga)
        layout.setSpacing(12)
        layout.setContentsMargins(14, 14, 14, 14)

        dev_frame = QFrame()
        dev_frame.setObjectName("Card")
        dev_layout = QVBoxLayout(dev_frame)
        dev_layout.addWidget(QLabel("<b>Микрофон / Входной источник</b>"))

        dev_row = QHBoxLayout()
        self.device_dropdown = QComboBox()
        dev_row.addWidget(self.device_dropdown, 1)

        self.btn_refresh_devices = QPushButton("Обновить")
        dev_row.addWidget(self.btn_refresh_devices)
        dev_layout.addLayout(dev_row)
        layout.addWidget(dev_frame)

        txt_frame = QFrame()
        txt_frame.setObjectName("Card")
        txt_layout = QVBoxLayout(txt_frame)
        txt_layout.addWidget(QLabel("<b>Куда сохранять текст (.txt)</b>"))

        txt_row = QHBoxLayout()
        self.txt_file_lbl = QLabel("Файл не выбран...")
        self.txt_file_lbl.setStyleSheet("color: #7c7c82;")
        txt_row.addWidget(self.txt_file_lbl, 1)

        self.btn_browse_txt = QPushButton("Обзор...")
        txt_row.addWidget(self.btn_browse_txt)
        txt_layout.addLayout(txt_row)
        layout.addWidget(txt_frame)

        wav_frame = QFrame()
        wav_frame.setObjectName("Card")
        wav_layout = QVBoxLayout(wav_frame)

        self.save_audio_chk = QCheckBox("Параллельно записывать чистый звук в файл")
        wav_layout.addWidget(self.save_audio_chk)

        wav_row = QHBoxLayout()
        self.wav_file_lbl = QLabel("Запись звука отключена...")
        self.wav_file_lbl.setStyleSheet("color: #5c5c62;")
        wav_row.addWidget(self.wav_file_lbl, 1)

        self.btn_browse_wav = QPushButton("Обзор...")
        self.btn_browse_wav.setEnabled(False)
        wav_row.addWidget(self.btn_browse_wav)
        wav_layout.addLayout(wav_row)
        layout.addWidget(wav_frame)

        self.btn_start_transcription = QPushButton("Запустить транскрибацию")
        self.btn_start_transcription.setObjectName("PrimaryAction")
        self.btn_start_transcription.setEnabled(False)
        self.btn_start_transcription.setMinimumHeight(45)
        layout.addWidget(self.btn_start_transcription)
        layout.addStretch()

    def setup_giga_diarize_tab(self):
        layout = QVBoxLayout(self.tab_giga_diarize)
        layout.setSpacing(12)
        layout.setContentsMargins(14, 14, 14, 14)

        in_frame = QFrame()
        in_frame.setObjectName("Card")
        in_layout = QVBoxLayout(in_frame)
        in_layout.addWidget(QLabel("<b>Исходный аудиофайл для постобработки</b>"))

        in_row = QHBoxLayout()
        self.gd_audio_lbl = QLabel("Файл не выбран...")
        self.gd_audio_lbl.setStyleSheet("color: #7c7c82;")
        in_row.addWidget(self.gd_audio_lbl, 1)

        self.btn_gd_browse_audio = QPushButton("Выбрать...")
        in_row.addWidget(self.btn_gd_browse_audio)
        in_layout.addLayout(in_row)
        layout.addWidget(in_frame)

        out_frame = QFrame()
        out_frame.setObjectName("Card")
        out_layout = QVBoxLayout(out_frame)
        out_layout.addWidget(QLabel("<b>Целевой текстовый файл результата (.txt)</b>"))

        out_row = QHBoxLayout()
        self.gd_txt_lbl = QLabel("Файл не выбран...")
        self.gd_txt_lbl.setStyleSheet("color: #7c7c82;")
        out_row.addWidget(self.gd_txt_lbl, 1)

        self.btn_gd_browse_txt = QPushButton("Обзор...")
        out_row.addWidget(self.btn_gd_browse_txt)
        out_layout.addLayout(out_row)
        layout.addWidget(out_frame)

        spk_frame = QFrame()
        spk_frame.setObjectName("Card")
        spk_layout = QVBoxLayout(spk_frame)
        spk_layout.addWidget(QLabel("<b>Конфигурация количества спикеров</b>"))

        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("Мин. спикеров:"))
        self.spin_min_spk = QSpinBox()
        self.spin_min_spk.setRange(1, 20)
        self.spin_min_spk.setValue(1)
        range_layout.addWidget(self.spin_min_spk)

        range_layout.addWidget(QLabel("Макс. спикеров:"))
        self.spin_max_spk = QSpinBox()
        self.spin_max_spk.setRange(1, 20)
        self.spin_max_spk.setValue(6)
        range_layout.addWidget(self.spin_max_spk)
        spk_layout.addLayout(range_layout)

        exact_layout = QHBoxLayout()
        self.chk_exact_spk = QCheckBox("Использовать точное количество спикеров")
        exact_layout.addWidget(self.chk_exact_spk)

        self.spin_exact_spk = QSpinBox()
        self.spin_exact_spk.setRange(1, 20)
        self.spin_exact_spk.setValue(2)
        self.spin_exact_spk.setEnabled(False)
        exact_layout.addWidget(self.spin_exact_spk)
        spk_layout.addLayout(exact_layout)
        layout.addWidget(spk_frame)

        self.gd_progress = QProgressBar()
        self.gd_progress.setRange(0, 100)
        self.gd_progress.setValue(0)
        self.gd_progress.setTextVisible(True)
        layout.addWidget(self.gd_progress)

        self.btn_gd_start = QPushButton("🚀 Запустить разделение спикеров (GigaAM)")
        self.btn_gd_start.setObjectName("PrimaryAction")
        self.btn_gd_start.setMinimumHeight(45)
        layout.addWidget(self.btn_gd_start)
        layout.addStretch()

    def setup_whisper_tab(self):
        layout = QVBoxLayout(self.tab_whisper)
        layout.setSpacing(14)
        layout.setContentsMargins(14, 14, 14, 14)

        wx_frame = QFrame()
        wx_frame.setObjectName("Card")
        wx_layout = QVBoxLayout(wx_frame)

        wx_layout.addWidget(QLabel("<b>Постобработка готовой записи</b>"))
        desc = QLabel("Выберите аудиофайл (.wav), отметьте необходимые форматы документов ниже и запустите WhisperX.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8c8c92; font-size: 12px;")
        wx_layout.addWidget(desc)

        file_row = QHBoxLayout()
        self.wx_file_lbl = QLabel("Файл для обработки не выбран...")
        self.wx_file_lbl.setStyleSheet("color: #7c7c82;")
        file_row.addWidget(self.wx_file_lbl, 1)

        self.btn_wx_browse_audio = QPushButton("Выбрать файл...")
        file_row.addWidget(self.btn_wx_browse_audio)
        wx_layout.addLayout(file_row)
        layout.addWidget(wx_frame)

        fmt_frame = QFrame()
        fmt_frame.setObjectName("Card")
        fmt_layout = QVBoxLayout(fmt_frame)
        fmt_layout.addWidget(QLabel("<b>Какие файлы вам нужны на выходе?</b>"))

        grid_layout = QHBoxLayout()
        self.wx_txt_var = QCheckBox("TXT (С ролями)")
        self.wx_srt_var = QCheckBox("SRT (Субтитры)")
        self.wx_tsv_var = QCheckBox("TSV (Excel)")
        self.wx_json_var = QCheckBox("JSON (Слова)")
        self.wx_vtt_var = QCheckBox("VTT (Web)")

        for chk in [self.wx_txt_var, self.wx_srt_var, self.wx_tsv_var, self.wx_json_var, self.wx_vtt_var]:
            chk.setChecked(True)
            grid_layout.addWidget(chk)

        fmt_layout.addLayout(grid_layout)
        layout.addWidget(fmt_frame)

        self.btn_wx_start = QPushButton("🚀 Запустить разделение спикеров (WhisperX)")
        self.btn_wx_start.setObjectName("PrimaryAction")
        self.btn_wx_start.setMinimumHeight(45)
        layout.addWidget(self.btn_wx_start)
        layout.addStretch()

    # Log and Feedback UI Actions
    def log(self, message: str):
        timestamp = time.strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {message}")

    def show_info(self, title: str, text: str):
        QMessageBox.information(self, title, text)

    def show_warning(self, title: str, text: str):
        QMessageBox.warning(self, title, text)

    def show_critical(self, title: str, text: str):
        QMessageBox.critical(self, title, text)

    def show_question(self, title: str, text: str) -> bool:
        reply = QMessageBox.question(
            self, title, text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    def closeEvent(self, event):
        # Delegate close decision to the controller
        self.close_requested.emit(event)
