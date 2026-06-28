import os
import time
import sounddevice as sd
from PyQt6.QtCore import QThread, pyqtSlot, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QCheckBox, QTextEdit,
    QFileDialog, QMessageBox, QFrame, QProgressBar, QSpinBox, QLineEdit,
    QListWidget, QStackedWidget
)
# Import dependencies from our backend and style config
from .style import MODERN_STYLE
from backend.workers import (
    ModelLoader, LiveTranscriptionWorker, WhisperXWorker, GigaAMDiarizeWorker,
    MLX_AVAILABLE
)

class VoiceScribeMultiToolApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VoiceScribe-MultiTool")
        self.resize(1000, 800)
        self.setMinimumSize(900, 700)

        self.model = None
        self.device_mapping = {}

        # Path States
        self.output_txt_path = ""
        self.output_wav_path = ""
        self.whisper_audio_path = ""
        self.giga_diarize_audio_path = ""
        self.giga_diarize_txt_path = ""

        # Thread States
        self.live_thread = None
        self.live_worker = None
        self.whisper_thread = None
        self.whisper_worker = None
        self.giga_diarize_thread = None
        self.giga_diarize_worker = None

        self.setup_ui()
        self.setStyleSheet(MODERN_STYLE)

        self.log("Инициализация базовой модели GigaAM... Пожалуйста, подождите.")
        self.load_model_async()

        if not MLX_AVAILABLE:
            self.gd_start_btn.setEnabled(False)
            self.gd_start_btn.setText("❌ GigaAM MLX недоступен на этой ОС (нужен Apple Silicon)")
            self.log("⚠️ Внимание: библиотека gigaam_mlx не найдена. Вторая вкладка будет заблокирована.")

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
        token_layout.addWidget(QLabel("<b>Hugging Face Token (HF_TOKEN):</b>"))

        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Вставьте ваш hf_... токен для работы диаризации")

        saved_token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_READ_TOKEN") or ""
        self.token_input.setText(saved_token)
        token_layout.addWidget(self.token_input, 1)

        self.btn_toggle_token = QPushButton("Показать")
        self.btn_toggle_token.setFixedWidth(75)
        self.btn_toggle_token.clicked.connect(self.toggle_token_visibility)
        token_layout.addWidget(self.btn_toggle_token)

        btn_save_token = QPushButton("Сохранить в .env")
        btn_save_token.clicked.connect(self.save_token_to_env)
        token_layout.addWidget(btn_save_token)

        main_layout.addWidget(token_frame)

        # Main Split Layout
        split_layout = QHBoxLayout()
        split_layout.setSpacing(16)

        # Left Sidebar (Navigation)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(240)

        self.sidebar.addItem("🎙️ Живая запись (GigaAM)")
        self.sidebar.addItem("👥 Разделение (GigaAM MLX)")
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
        log_title.setStyleSheet("font-weight: bold; color: #9871ff;")
        log_header_layout.addWidget(log_title)

        copy_btn = QPushButton("📋 Скопировать лог")
        copy_btn.clicked.connect(self.copy_log_to_clipboard)
        log_header_layout.addWidget(copy_btn, 0, Qt.AlignmentFlag.AlignRight)
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

        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.populate_devices)
        dev_row.addWidget(refresh_btn)
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

        browse_txt_btn = QPushButton("Обзор...")
        browse_txt_btn.clicked.connect(self.browse_txt_file)
        txt_row.addWidget(browse_txt_btn)
        txt_layout.addLayout(txt_row)
        layout.addWidget(txt_frame)

        wav_frame = QFrame()
        wav_frame.setObjectName("Card")
        wav_layout = QVBoxLayout(wav_frame)

        self.save_audio_chk = QCheckBox("Параллельно записывать чистый звук в файл")
        self.save_audio_chk.stateChanged.connect(self.toggle_audio_fields)
        wav_layout.addWidget(self.save_audio_chk)

        wav_row = QHBoxLayout()
        self.wav_file_lbl = QLabel("Запись звука отключена...")
        self.wav_file_lbl.setStyleSheet("color: #5c5c62;")
        wav_row.addWidget(self.wav_file_lbl, 1)

        self.browse_wav_btn = QPushButton("Обзор...")
        self.browse_wav_btn.setEnabled(False)
        self.browse_wav_btn.clicked.connect(self.browse_wav_file)
        wav_row.addWidget(self.browse_wav_btn)
        wav_layout.addLayout(wav_row)
        layout.addWidget(wav_frame)

        self.start_btn = QPushButton("Запустить транскрибацию")
        self.start_btn.setObjectName("PrimaryAction")
        self.start_btn.setEnabled(False)
        self.start_btn.setMinimumHeight(45)
        self.start_btn.clicked.connect(self.toggle_transcription)
        layout.addWidget(self.start_btn)
        layout.addStretch()

        self.populate_devices()

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

        gd_browse_audio_btn = QPushButton("Выбрать...")
        gd_browse_audio_btn.clicked.connect(self.browse_giga_diarize_audio)
        in_row.addWidget(gd_browse_audio_btn)
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

        gd_browse_txt_btn = QPushButton("Обзор...")
        gd_browse_txt_btn.clicked.connect(self.browse_giga_diarize_txt)
        out_row.addWidget(gd_browse_txt_btn)
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
        self.chk_exact_spk.stateChanged.connect(self.toggle_exact_speaker_lock)
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

        self.gd_start_btn = QPushButton("🚀 Запустить разделение спикеров (GigaAM MLX)")
        self.gd_start_btn.setObjectName("PrimaryAction")
        self.gd_start_btn.setMinimumHeight(45)
        self.gd_start_btn.clicked.connect(self.start_giga_diarization)
        layout.addWidget(self.gd_start_btn)
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

        wx_browse_btn = QPushButton("Выбрать файл...")
        wx_browse_btn.clicked.connect(self.browse_whisper_file)
        file_row.addWidget(wx_browse_btn)
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

        self.whisper_btn = QPushButton("🚀 Запустить разделение спикеров (WhisperX)")
        self.whisper_btn.setObjectName("PrimaryAction")
        self.whisper_btn.setMinimumHeight(45)
        self.whisper_btn.clicked.connect(self.start_whisperx)
        layout.addWidget(self.whisper_btn)
        layout.addStretch()

    def log(self, message):
        timestamp = time.strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {message}")

    def copy_log_to_clipboard(self):
        content = self.log_text.toPlainText().strip()
        if content:
            QApplication.clipboard().setText(content)
            QMessageBox.information(self, "Успех", "Лог успешно скопирован в буфер обмена!")

    def load_model_async(self):
        self.loader_thread = QThread()
        self.loader_worker = ModelLoader()
        self.loader_worker.moveToThread(self.loader_thread)

        self.loader_thread.started.connect(self.loader_worker.run)
        self.loader_worker.finished.connect(self.on_model_loaded)
        self.loader_worker.error.connect(self.on_model_error)

        self.loader_thread.start()

    @pyqtSlot(object)
    def on_model_loaded(self, model):
        self.model = model
        self.log("Базовая модель GigaAM загружена в память.")
        self.start_btn.setEnabled(True)
        self.loader_thread.quit()
        self.loader_thread.wait()

    @pyqtSlot(str)
    def on_model_error(self, error_msg):
        self.log(f"Ошибка загрузки модели GigaAM: {error_msg}")
        QMessageBox.critical(self, "Критическая ошибка", f"Не удалось загрузить модель GigaAM:\n{error_msg}")
        self.loader_thread.quit()
        self.loader_thread.wait()

    def populate_devices(self):
        try:
            self.device_dropdown.clear()
            self.device_mapping.clear()
            devices = sd.query_devices()
            default_input = sd.query_devices(kind="input")
            default_index = default_input.get("index", -1)

            select_idx = 0
            for i, dev in enumerate(devices):
                if dev["max_input_channels"] > 0:
                    display_name = f"{dev['name']} (ID: {i})"
                    self.device_dropdown.addItem(display_name)
                    self.device_mapping[display_name] = i
                    if i == default_index:
                        select_idx = self.device_dropdown.count() - 1

            if self.device_dropdown.count() > 0:
                self.device_dropdown.setCurrentIndex(select_idx)
        except Exception as e:
            self.log(f"Ошибка сканирования устройств: {e}")

    def toggle_audio_fields(self, state):
        is_checked = (state == 2)
        self.browse_wav_btn.setEnabled(is_checked)
        self.wav_file_lbl.setStyleSheet(f"color: {'#e1e1e6' if is_checked else '#5c5c62'};")
        if not is_checked:
            self.wav_file_lbl.setText("Запись звука отключена...")
            self.output_wav_path = ""
        else:
            self.wav_file_lbl.setText("Файл аудио не выбран...")

    def toggle_exact_speaker_lock(self, state):
        is_checked = (state == 2)
        self.spin_exact_spk.setEnabled(is_checked)
        self.spin_min_spk.setEnabled(not is_checked)
        self.spin_max_spk.setEnabled(not is_checked)

    def browse_txt_file(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить текст", "", "Text Files (*.txt)")
        if file_path:
            self.output_txt_path = file_path
            self.txt_file_lbl.setText(os.path.basename(file_path))

    def browse_wav_file(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить аудиозапись", "", "WAV Audio (*.wav)")
        if file_path:
            self.output_wav_path = file_path
            self.wav_file_lbl.setText(os.path.basename(file_path))

    def browse_whisper_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выбрать аудиофайл", "", "Audio Files (*.wav *.mp3 *.m4a)")
        if file_path:
            self.whisper_audio_path = file_path
            self.wx_file_lbl.setText(os.path.basename(file_path))

    def browse_giga_diarize_audio(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выбрать аудио для диризации", "", "Audio Files (*.wav *.mp3 *.m4a)")
        if file_path:
            self.giga_diarize_audio_path = file_path
            self.gd_audio_lbl.setText(os.path.basename(file_path))

    def browse_giga_diarize_txt(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить результат диаризации", "", "Text Files (*.txt)")
        if file_path:
            self.giga_diarize_txt_path = file_path
            self.gd_txt_lbl.setText(os.path.basename(file_path))

    def toggle_token_visibility(self):
        if self.token_input.echoMode() == QLineEdit.EchoMode.Password:
            self.token_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_token.setText("Скрыть")
        else:
            self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_token.setText("Показать")

    def save_token_to_env(self):
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Внимание", "Поле токена пустое.")
            return

        os.environ["HF_TOKEN"] = token
        env_lines = []
        has_token = False

        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("HF_TOKEN=") or line.strip().startswith("HUGGING_FACE_READ_TOKEN="):
                        if not has_token:
                            env_lines.append(f"HF_TOKEN={token}\n")
                            has_token = True
                    else:
                        env_lines.append(line)
        else:
            env_lines.append(f"HF_TOKEN={token}\n")

        if not has_token and os.path.exists(".env"):
            env_lines.append(f"HF_TOKEN={token}\n")

        try:
            with open(".env", "w", encoding="utf-8") as f:
                f.writelines(env_lines)
            QMessageBox.information(self, "Успех", "Токен успешно сохранен в .env и обновлен в памяти!")
            self.log("HF_TOKEN успешно перезаписан.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить .env файл: {e}")

    def toggle_transcription(self):
        if self.live_thread and self.live_thread.isRunning():
            self.start_btn.setEnabled(False)
            self.live_worker.stop()
            return

        if not self.output_txt_path or self.device_dropdown.count() == 0:
            QMessageBox.warning(self, "Внимание", "Заполните настройки: укажите выходной текстовый файл и выберите устройство.")
            return
        if self.save_audio_chk.isChecked() and not self.output_wav_path:
            QMessageBox.warning(self, "Внимание", "Укажите путь для сохранения мастер-файла .wav.")
            return

        device_name = self.device_dropdown.currentText()
        device_id = self.device_mapping[device_name]

        try:
            device_info = sd.query_devices(device_id, 'input')
            channels = int(device_info['max_input_channels'])
        except Exception:
            channels = 1

        self.live_thread = QThread()
        self.live_worker = LiveTranscriptionWorker(
            model=self.model, device_id=device_id, channels=channels,
            output_txt=self.output_txt_path, save_audio=self.save_audio_chk.isChecked(),
            output_wav=self.output_wav_path
        )
        self.live_worker.moveToThread(self.live_thread)

        self.live_thread.started.connect(self.live_worker.run)
        self.live_worker.log_signal.connect(self.log)
        self.live_worker.finished_signal.connect(self.on_transcription_stopped)

        self.live_thread.start()

        self.start_btn.setText("⏹️ Остановить и сохранить всё")
        self.start_btn.setStyleSheet("background-color: #e02424; color: white;")
        self.device_dropdown.setEnabled(False)
        self.save_audio_chk.setEnabled(False)
        self.browse_wav_btn.setEnabled(False)
        self.log("🏁 Потоковая транскрибация запущена...")

    def on_transcription_stopped(self):
        self.live_thread.quit()
        self.live_thread.wait()

        self.start_btn.setText("Запустить транскрибацию")
        self.start_btn.setStyleSheet("")
        self.start_btn.setEnabled(True)
        self.device_dropdown.setEnabled(True)
        self.save_audio_chk.setEnabled(True)
        if self.save_audio_chk.isChecked():
            self.browse_wav_btn.setEnabled(True)

        self.log("🏁 Процесс записи и сохранения полностью завершен.")

    def start_whisperx(self):
        if not self.whisper_audio_path:
            QMessageBox.warning(self, "Внимание", "Выберите аудиофайл для постобработки.")
            return

        selected_formats = []
        if self.wx_txt_var.isChecked(): selected_formats.append("txt")
        if self.wx_srt_var.isChecked(): selected_formats.append("srt")
        if self.wx_tsv_var.isChecked(): selected_formats.append("tsv")
        if self.wx_json_var.isChecked(): selected_formats.append("json")
        if self.wx_vtt_var.isChecked(): selected_formats.append("vtt")

        if not selected_formats:
            QMessageBox.warning(self, "Внимание", "Выберите хотя бы один формат на выходе!")
            return

        hf_token = self.token_input.text().strip()
        if not hf_token or hf_token.startswith("hf_какой_то_ваш"):
            QMessageBox.critical(self, "Ошибка токена", "Проверьте валидность HF_TOKEN в верхней строке интерфейса.")
            return

        self.whisper_btn.setEnabled(False)
        self.whisper_btn.setText("⏳ Выполняется обработка WhisperX...")

        self.whisper_thread = QThread()
        self.whisper_worker = WhisperXWorker(self.whisper_audio_path, hf_token, selected_formats)
        self.whisper_worker.moveToThread(self.whisper_thread)

        self.whisper_thread.started.connect(self.whisper_worker.run)
        self.whisper_worker.log_signal.connect(self.log)
        self.whisper_worker.finished_signal.connect(self.on_whisper_finished)

        self.whisper_thread.start()

    @pyqtSlot(bool)
    def on_whisper_finished(self, success):
        self.whisper_thread.quit()
        self.whisper_thread.wait()

        self.whisper_btn.setEnabled(True)
        self.whisper_btn.setText("🚀 Запустить разделение спикеров (WhisperX)")

        if success:
            output_dir = os.path.dirname(self.whisper_audio_path)
            self.log(f"🎉 Успех! Файлы сохранены в папку: {output_dir}")
            QMessageBox.information(self, "Готово", f"WhisperX успешно завершил обработку файла!\nПапка: {output_dir}")
        else:
            self.log("💥 Обработка WhisperX завершилась с ошибкой.")
            QMessageBox.critical(self, "Ошибка", "Произошла ошибка при выполнении сценария WhisperX. Проверьте консоль логов.")

    def start_giga_diarization(self):
        if not MLX_AVAILABLE:
            QMessageBox.critical(self, "Ошибка ОС", "Данный функционал доступен исключительно на macOS с чипами Apple Silicon (M1/M2/M3...).")
            return

        if not self.giga_diarize_audio_path or not self.giga_diarize_txt_path:
            QMessageBox.warning(self, "Внимание", "Заполните пути: выберите входной аудиофайл и целевой файл сохранения .txt")
            return

        hf_token = self.token_input.text().strip()
        if not hf_token or hf_token.startswith("hf_какой_то_ваш"):
            QMessageBox.critical(self, "Ошибка токена", "Проверьте валидность HF_TOKEN в верхней строке интерфейса.")
            return

        if self.chk_exact_spk.isChecked():
            num_spk = self.spin_exact_spk.value()
            min_spk, max_spk = None, None
        else:
            num_spk = None
            min_spk = self.spin_min_spk.value()
            max_spk = self.spin_max_spk.value()

        self.gd_progress.setValue(0)
        self.gd_start_btn.setEnabled(False)
        self.gd_start_btn.setText("⏳ Выполняется обработка GigaAM MLX...")

        self.giga_diarize_thread = QThread()
        self.giga_diarize_worker = GigaAMDiarizeWorker(
            audio_path=self.giga_diarize_audio_path,
            output_txt=self.giga_diarize_txt_path,
            hf_token=hf_token,
            min_speakers=min_spk,
            max_speakers=max_spk,
            num_speakers=num_spk
        )
        self.giga_diarize_worker.moveToThread(self.giga_diarize_thread)

        self.giga_diarize_thread.started.connect(self.giga_diarize_worker.run)
        self.giga_diarize_worker.log_signal.connect(self.log)
        self.giga_diarize_worker.progress_signal.connect(self.gd_progress.setValue)
        self.giga_diarize_worker.finished_signal.connect(self.on_giga_diarize_finished)

        self.giga_diarize_thread.start()

    @pyqtSlot(bool)
    def on_giga_diarize_finished(self, success):
        self.giga_diarize_thread.quit()
        self.giga_diarize_thread.wait()

        self.gd_start_btn.setEnabled(True)
        self.gd_start_btn.setText("🚀 Запустить разделение спикеров (GigaAM MLX)")

        if success:
            self.gd_progress.setValue(100)
            self.log(f"🎉 Успех! Результат сохранен: {self.giga_diarize_txt_path}")
            QMessageBox.information(self, "Готово", f"Разделение ролей через GigaAM MLX успешно завершено!\nФайл: {self.giga_diarize_txt_path}")
        else:
            self.gd_progress.setValue(0)
            QMessageBox.critical(self, "Ошибка", "Произошла ошибка при выполнении сценария GigaAM MLX. Проверьте консоль логов.")

    def closeEvent(self, event):
        active_processes = (
            (self.live_thread and self.live_thread.isRunning()) or
            (self.whisper_thread and self.whisper_thread.isRunning()) or
            (self.giga_diarize_thread and self.giga_diarize_thread.isRunning())
        )
        if active_processes:
            reply = QMessageBox.question(
                self, "Выход", "У вас есть активные фоновые процессы. Все равно выйти?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        if self.live_worker:
            self.live_worker.stop()
        if self.live_thread:
            self.live_thread.quit()
            self.live_thread.wait()
        if self.whisper_thread:
            self.whisper_thread.quit()
            self.whisper_thread.wait()
        if self.giga_diarize_thread:
            self.giga_diarize_thread.quit()
            self.giga_diarize_thread.wait()
        event.accept()
