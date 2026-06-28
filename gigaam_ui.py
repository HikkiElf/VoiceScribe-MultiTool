import os
import queue
import subprocess
import sys
import time
from dotenv import load_dotenv
import gigaam
import numpy as np
import scipy.io.wavfile as wavf
import sounddevice as sd
import torch

# Безопасный кроссплатформенный импорт MLX-компонентов и PyAnnote
try:
    from gigaam_mlx import load_model as load_mlx_model, transcribe as transcribe_mlx
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False
    load_mlx_model, transcribe_mlx = None, None

try:
    from pyannote.audio import Pipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False
    Pipeline = None

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QComboBox, QPushButton, QCheckBox, QTextEdit,
    QFileDialog, QMessageBox, QFrame, QStyle, QProgressBar, QSpinBox, QGroupBox,
    QLineEdit
)

# Загрузка конфигурации из .env
load_dotenv()

MODEL_NAME = "v3_e2e_rnnt"
SAMPLE_RATE = 16000
CHUNK_DURATION = 5
SILENCE_THRESHOLD = 0.02

# Модернизированный QSS CSS шаблон стилей
MODERN_STYLE = """
QMainWindow {
    background-color: #121214;
}
QWidget {
    color: #e1e1e6;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QFrame#Card {
    background-color: #1a1a1e;
    border: 1px solid #29292e;
    border-radius: 8px;
}
QTabWidget::pane {
    border: 1px solid #29292e;
    background-color: #1a1a1e;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background-color: #121214;
    border: 1px solid #29292e;
    padding: 10px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background-color: #1a1a1e;
    border-bottom-color: #1a1a1e;
    color: #9871ff;
    font-weight: bold;
}
QPushButton {
    background-color: #29292e;
    border: 1px solid #3e3e42;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #3e3e42;
}
QPushButton:pressed {
    background-color: #4e4e54;
}
QPushButton#PrimaryAction {
    background-color: #7c4dff;
    color: #ffffff;
    border: none;
}
QPushButton#PrimaryAction:hover {
    background-color: #9166ff;
}
QPushButton#PrimaryAction:disabled {
    background-color: #2a1b4e;
    color: #757575;
}
QComboBox, QSpinBox, QLineEdit {
    background-color: #202024;
    border: 1px solid #29292e;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e1e1e6;
}
QComboBox::drop-down {
    border: none;
}
QTextEdit {
    background-color: #0c0c0d;
    border: 1px solid #29292e;
    border-radius: 6px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    color: #a9a9b3;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QProgressBar {
    border: 1px solid #29292e;
    border-radius: 6px;
    background-color: #0c0c0d;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
    height: 22px;
}
QProgressBar::chunk {
    background-color: #7c4dff;
    border-radius: 5px;
}
"""


class ModelLoader(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def run(self):
        try:
            model = gigaam.load_model(MODEL_NAME)
            self.finished.emit(model)
        except Exception as e:
            self.error.emit(str(e))


class LiveTranscriptionWorker(QObject):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, model, device_id, channels, output_txt, save_audio, output_wav):
        super().__init__()
        self.model = model
        self.device_id = device_id
        self.channels = channels
        self.output_txt = output_txt
        self.save_audio = save_audio
        self.output_wav = output_wav
        self.is_recording = True
        self.audio_queue = queue.Queue()
        self.full_audio_data = []

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        if self.is_recording:
            if indata.shape[1] > 1:
                mono_data = np.mean(indata, axis=1, keepdims=True)
            else:
                mono_data = indata.copy()
            self.audio_queue.put(mono_data)

    def run(self):
        samples_per_chunk = SAMPLE_RATE * CHUNK_DURATION
        audio_buffer = []

        try:
            stream = sd.InputStream(
                device=self.device_id, samplerate=SAMPLE_RATE,
                channels=self.channels, callback=self.audio_callback,
                blocksize=int(SAMPLE_RATE * 0.5)
            )

            with stream:
                with open(self.output_txt, "a", encoding="utf-8") as txt_file:
                    while self.is_recording:
                        try:
                            data = self.audio_queue.get(timeout=0.5)
                            audio_buffer.append(data)
                            if self.save_audio:
                                self.full_audio_data.append(data)

                            current_audio = np.concatenate(audio_buffer, axis=0)

                            if len(current_audio) >= samples_per_chunk:
                                audio_buffer = []
                                if np.max(np.abs(current_audio)) < SILENCE_THRESHOLD:
                                    continue

                                temp_wav = f"ui_temp_{int(time.time())}.wav"
                                wavf.write(temp_wav, SAMPLE_RATE, current_audio)

                                try:
                                    result = self.model.transcribe(temp_wav)
                                    text = result.text.strip()
                                    if text:
                                        self.log_signal.emit(f"Распознано: {text}")
                                        txt_file.write(text + " ")
                                        txt_file.flush()
                                except Exception as e:
                                    self.log_signal.emit(f"Ошибка инференса: {e}")
                                finally:
                                    if os.path.exists(temp_wav):
                                        os.remove(temp_wav)
                        except queue.Empty:
                            continue

            if self.save_audio and self.full_audio_data:
                self.log_signal.emit("Экспорт мастер-аудио на диск...")
                full_audio = np.concatenate(self.full_audio_data, axis=0)
                wavf.write(self.output_wav, SAMPLE_RATE, full_audio)
                self.log_signal.emit(f"🎉 Аудио успешно сохранено: {os.path.basename(self.output_wav)}")

        except Exception as e:
            self.log_signal.emit(f"Критическая ошибка аудиопотока: {e}")

        self.finished_signal.emit()

    def stop(self):
        self.is_recording = False


class WhisperXWorker(QObject):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, audio_path, hf_token, selected_formats):
        super().__init__()
        self.audio_path = audio_path
        self.hf_token = hf_token
        self.selected_formats = selected_formats

    def run(self):
        output_dir = os.path.dirname(self.audio_path)
        cmd = ["whisperx", self.audio_path, "--model", "large-v3", "--diarize", "--hf_token", self.hf_token, "--output_dir", output_dir]

        if len(self.selected_formats) == 1:
            cmd.extend(["--output_format", self.selected_formats[0]])
        else:
            cmd.extend(["--output_format", "all"])

        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                cleaned_line = line.strip()
                if cleaned_line:
                    self.log_signal.emit(f"[WhisperX] {cleaned_line}")

            process.wait()

            if process.returncode == 0:
                if len(self.selected_formats) > 1 and len(self.selected_formats) < 5:
                    all_formats = {"txt", "srt", "tsv", "json", "vtt"}
                    unwanted_formats = all_formats - set(self.selected_formats)
                    base_path, _ = os.path.splitext(self.audio_path)
                    for fmt in unwanted_formats:
                        unwanted_file = f"{base_path}.{fmt}"
                        if os.path.exists(unwanted_file):
                            os.remove(unwanted_file)
                self.finished_signal.emit(True)
            else:
                self.finished_signal.emit(False)
        except Exception as e:
            self.log_signal.emit(f"💥 Ошибка выполнения: {e}")
            self.finished_signal.emit(False)


class GigaAMDiarizeWorker(QObject):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)

    def __init__(self, audio_path, output_txt, hf_token, min_speakers, max_speakers, num_speakers):
        super().__init__()
        self.audio_path = audio_path
        self.output_txt = output_txt
        self.hf_token = hf_token
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.num_speakers = num_speakers

    def run(self):
        try:
            self.progress_signal.emit(5)
            if not MLX_AVAILABLE:
                self.log_signal.emit("💥 Ошибка: Модуль gigaam_mlx недоступен на текущей системе (требуется Apple Silicon).")
                self.finished_signal.emit(False)
                return

            if not PYANNOTE_AVAILABLE:
                self.log_signal.emit("💥 Ошибка: Модуль pyannote.audio не установлен.")
                self.finished_signal.emit(False)
                return

            self.log_signal.emit("--> [GigaAM-Diarize] Загрузка модели GigaAM-v3 RNNT (MLX)...")
            model, tokenizer = load_mlx_model(model_type="rnnt")
            self.progress_signal.emit(20)

            self.log_signal.emit("--> [GigaAM-Diarize] Загрузка конвейера диаризации PyAnnote...")
            diarize_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-community-1",
                token=self.hf_token
            )
            self.progress_signal.emit(40)

            if torch.backends.mps.is_available():
                diarize_pipeline.to(torch.device("mps"))
            elif torch.cuda.is_available():
                diarize_pipeline.to(torch.device("cuda"))

            # Настройка ограничений
            diarize_kwargs = {}
            if self.num_speakers is not None:
                diarize_kwargs["num_speakers"] = self.num_speakers
            else:
                if self.min_speakers is not None:
                    diarize_kwargs["min_speakers"] = self.min_speakers
                if self.max_speakers is not None:
                    diarize_kwargs["max_speakers"] = self.max_speakers

            self.log_signal.emit(f"--> [GigaAM-Diarize] Анализ структуры спикеров (PyAnnote VAD/Embedding)...")
            diarization_output = diarize_pipeline(self.audio_path, **diarize_kwargs)
            self.progress_signal.emit(65)

            self.log_signal.emit("--> [GigaAM-Diarize] Нарезка сегментов и транскрибация через MLX...")

            turns = list(diarization_output.exclusive_speaker_diarization)
            total_turns = len(turns)

            with open(self.output_txt, "w", encoding="utf-8") as f:
                for idx, (turn, speaker) in enumerate(turns):
                    start_time = turn.start
                    end_time = turn.end
                    duration = end_time - start_time

                    if duration < 0.4:
                        # Расчет прогресса даже при пропуске слишком короткого сегмента
                        current_pct = int(65 + ((idx + 1) / total_turns) * 35)
                        self.progress_signal.emit(current_pct)
                        continue

                    temp_chunk = f"ui_diarize_chunk_{speaker}_{start_time:.2f}.wav"

                    ffmpeg_cmd = [
                        "ffmpeg", "-y",
                        "-ss", str(start_time),
                        "-to", str(end_time),
                        "-i", self.audio_path,
                        "-c", "copy",
                        temp_chunk
                    ]
                    subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    try:
                        res = transcribe_mlx(model, tokenizer, temp_chunk)
                        text = res.get("text", "") if isinstance(res, dict) else str(res)
                        text = text.strip()

                        if text:
                            line = f"[{start_time:.2f}s - {end_time:.2f}s] {speaker}: {text}\n"
                            f.write(line)
                            f.flush()
                            self.log_signal.emit(line.strip())

                    except Exception as e:
                        self.log_signal.emit(f"Ошибка сегмента [{start_time:.2f}s]: {e}")
                    finally:
                        if os.path.exists(temp_chunk):
                            os.remove(temp_chunk)

                    # Динамическое обновление полосы прогресса
                    current_pct = int(65 + ((idx + 1) / total_turns) * 35)
                    self.progress_signal.emit(current_pct)

            self.progress_signal.emit(100)
            self.finished_signal.emit(True)
        except Exception as e:
            self.log_signal.emit(f"💥 Критическая ошибка разделения ролей GigaAM: {e}")
            self.finished_signal.emit(False)


class ModernTranscriptionApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GigaAM & WhisperX Studio")
        self.resize(750, 900)
        self.setMinimumSize(650, 800)

        self.model = None
        self.device_mapping = {}

        # Paths
        self.output_txt_path = ""
        self.output_wav_path = ""
        self.whisper_audio_path = ""
        self.giga_diarize_audio_path = ""
        self.giga_diarize_txt_path = ""

        # Threads
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

        # Проверка доступности MLX на уровне UI
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

        # Конфигурационная плашка токена Hugging Face на самом верху
        token_frame = QFrame()
        token_frame.setObjectName("Card")
        token_layout = QHBoxLayout(token_frame)
        token_layout.setContentsMargins(12, 10, 12, 10)
        token_layout.addWidget(QLabel("<b>Hugging Face Token (HF_TOKEN):</b>"))

        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Вставьте ваш hf_... токен для работы диаризации")

        # Чтение сохраненного токена (с поддержкой старого и нового ключа)
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

        # Tabs Setup
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_giga = QWidget()
        self.tab_giga_diarize = QWidget()
        self.tab_whisper = QWidget()

        self.tabs.addTab(self.tab_giga, " 🎙️  Живая запись (GigaAM) ")
        self.tabs.addTab(self.tab_giga_diarize, " 👥  Разделение ролей (GigaAM MLX) ")
        self.tabs.addTab(self.tab_whisper, " 👥  Разделение ролей (WhisperX) ")

        self.setup_giga_tab()
        self.setup_giga_diarize_tab()
        self.setup_whisper_tab()

        # Monitoring / Console Log Panel
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

        main_layout.addWidget(log_frame, 1)

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
                    # Убираем старый или текущий ключ, чтобы не дублировать
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

    def setup_giga_tab(self):
        layout = QVBoxLayout(self.tab_giga)
        layout.setSpacing(12)
        layout.setContentsMargins(14, 14, 14, 14)

        # Card 1: Input Device Selection
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

        # Card 2: Save Text Target
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

        # Card 3: Parallel Master Audio Recording
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

        # Main Streaming Activation Trigger
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

        # Card 1: Input Audio
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

        # Card 2: Output Text Target
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

        # Card 3: Speaker Boundaries & Tuning Constraints
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

        # Панель нового прогресс-бара
        self.gd_progress = QProgressBar()
        self.gd_progress.setRange(0, 100)
        self.gd_progress.setValue(0)
        self.gd_progress.setTextVisible(True)
        layout.addWidget(self.gd_progress)

        # Execution Control Button
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

        # Checkbox Settings Matrix
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

        # Execution Call to Action Button
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

        # Сброс и активация прогресс-бара
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernTranscriptionApp()
    window.show()
    sys.exit(app.exec())
