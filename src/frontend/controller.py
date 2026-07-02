import os
import time
import sounddevice as sd
from PyQt6.QtCore import QObject, QThread, pyqtSlot, Qt
from PyQt6.QtWidgets import QFileDialog, QApplication, QMessageBox

# Import backend workers
from backend.workers import (
    ModelLoader, LiveTranscriptionWorker, WhisperXWorker, GigaAMDiarizeWorker
)

class VoiceScribeController(QObject):
    """
    Controller class coordinating actions between Model and View.
    It manages background worker threads and responds to View inputs.
    """
    def __init__(self, model, view):
        super().__init__()
        self.model = model
        self.view = view

        # Thread states
        self.loader_thread = None
        self.loader_worker = None
        
        self.live_thread = None
        self.live_worker = None
        
        self.whisper_thread = None
        self.whisper_worker = None
        
        self.giga_diarize_thread = None
        self.giga_diarize_worker = None

        # Set up connections
        self.connect_signals()

        # Initialize View state from Model
        self.init_view_from_model()

        # Start GigaAM Model Loader
        self.view.log("Инициализация базовой модели GigaAM... Пожалуйста, подождите.")
        self.load_model_async()

    def init_view_from_model(self):
        """Sets initial values in the UI widgets based on the Model state."""
        self.view.token_input.setText(self.model.hf_token)
        self.populate_devices()

    def connect_signals(self):
        # Token control triggers
        self.view.btn_toggle_token.clicked.connect(self.toggle_token_visibility)
        self.view.btn_save_token.clicked.connect(self.save_token_to_env)

        # Device selection triggers
        self.view.btn_refresh_devices.clicked.connect(self.populate_devices)

        # Folder/File browsing triggers
        self.view.btn_browse_txt.clicked.connect(self.browse_txt_file)
        self.view.btn_browse_wav.clicked.connect(self.browse_wav_file)
        self.view.btn_gd_browse_audio.clicked.connect(self.browse_giga_diarize_audio)
        self.view.btn_gd_browse_txt.clicked.connect(self.browse_giga_diarize_txt)
        self.view.btn_wx_browse_audio.clicked.connect(self.browse_whisper_file)

        # Config change triggers
        self.view.save_audio_chk.stateChanged.connect(self.toggle_audio_fields)
        self.view.chk_exact_spk.stateChanged.connect(self.toggle_exact_speaker_lock)

        # Copy Logs
        self.view.btn_copy_log.clicked.connect(self.copy_log_to_clipboard)

        # Operation launch triggers
        self.view.btn_start_transcription.clicked.connect(self.toggle_transcription)
        self.view.btn_gd_start.clicked.connect(self.start_giga_diarization)
        self.view.btn_wx_start.clicked.connect(self.start_whisperx)

        # Intercept app exit
        self.view.close_requested.connect(self.on_close_requested)

    # Token visibility & persistence
    def toggle_token_visibility(self):
        if self.view.token_input.echoMode() == self.view.token_input.EchoMode.Password:
            self.view.token_input.setEchoMode(self.view.token_input.EchoMode.Normal)
            self.view.btn_toggle_token.setText("Скрыть")
        else:
            self.view.token_input.setEchoMode(self.view.token_input.EchoMode.Password)
            self.view.btn_toggle_token.setText("Показать")

    def save_token_to_env(self):
        token = self.view.token_input.text().strip()
        if not token:
            self.view.show_warning("Внимание", "Поле токена пустое.")
            return

        success = self.model.update_hf_token(token)
        if success:
            self.view.show_info("Успех", "Токен успешно сохранен в .env и обновлен в памяти!")
            self.view.log("HF_TOKEN успешно перезаписан.")
        else:
            self.view.show_critical("Ошибка", "Не удалось сохранить .env файл.")

    # Device enumeration
    def populate_devices(self):
        try:
            self.view.device_dropdown.clear()
            self.model.device_mapping.clear()
            devices = sd.query_devices()
            default_input = sd.query_devices(kind="input")
            default_index = default_input.get("index", -1)

            select_idx = 0
            for i, dev in enumerate(devices):
                if dev["max_input_channels"] > 0:
                    display_name = f"{dev['name']} (ID: {i})"
                    self.view.device_dropdown.addItem(display_name)
                    self.model.device_mapping[display_name] = i
                    if i == default_index:
                        select_idx = self.view.device_dropdown.count() - 1

            if self.view.device_dropdown.count() > 0:
                self.view.device_dropdown.setCurrentIndex(select_idx)
        except Exception as e:
            self.view.log(f"Ошибка сканирования устройств: {e}")

    # Configuration switches
    def toggle_audio_fields(self, state):
        is_checked = (state == 2)
        self.model.save_audio = is_checked
        self.view.btn_browse_wav.setEnabled(is_checked)
        self.view.wav_file_lbl.setStyleSheet(f"color: {'#e1e1e6' if is_checked else '#5c5c62'};")
        if not is_checked:
            self.view.wav_file_lbl.setText("Запись звука отключена...")
            self.model.output_wav_path = ""
        else:
            self.view.wav_file_lbl.setText(
                os.path.basename(self.model.output_wav_path) if self.model.output_wav_path else "Файл аудио не выбран..."
            )

    def toggle_exact_speaker_lock(self, state):
        is_checked = (state == 2)
        self.model.use_exact_speakers = is_checked
        self.view.spin_exact_spk.setEnabled(is_checked)
        self.view.spin_min_spk.setEnabled(not is_checked)
        self.view.spin_max_spk.setEnabled(not is_checked)

    # File browsing operations
    def browse_txt_file(self):
        file_path, _ = QFileDialog.getSaveFileName(self.view, "Сохранить текст", "", "Text Files (*.txt)")
        if file_path:
            self.model.output_txt_path = file_path
            self.view.txt_file_lbl.setText(os.path.basename(file_path))

    def browse_wav_file(self):
        file_path, _ = QFileDialog.getSaveFileName(self.view, "Сохранить аудиозапись", "", "WAV Audio (*.wav)")
        if file_path:
            self.model.output_wav_path = file_path
            self.view.wav_file_lbl.setText(os.path.basename(file_path))

    def browse_whisper_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self.view, "Выбрать аудиофайл", "", "Audio Files (*.wav *.mp3 *.m4a)")
        if file_path:
            self.model.whisper_audio_path = file_path
            self.view.wx_file_lbl.setText(os.path.basename(file_path))

    def browse_giga_diarize_audio(self):
        file_path, _ = QFileDialog.getOpenFileName(self.view, "Выбрать аудио для диаризации", "", "Audio Files (*.wav *.mp3 *.m4a)")
        if file_path:
            self.model.giga_diarize_audio_path = file_path
            self.view.gd_audio_lbl.setText(os.path.basename(file_path))

    def browse_giga_diarize_txt(self):
        file_path, _ = QFileDialog.getSaveFileName(self.view, "Сохранить результат диаризации", "", "Text Files (*.txt)")
        if file_path:
            self.model.giga_diarize_txt_path = file_path
            self.view.gd_txt_lbl.setText(os.path.basename(file_path))

    def copy_log_to_clipboard(self):
        content = self.view.log_text.toPlainText().strip()
        if content:
            QApplication.clipboard().setText(content)
            self.view.show_info("Успех", "Лог успешно скопирован в буфер обмена!")

    # Model Loading (Async)
    def load_model_async(self):
        self.loader_thread = QThread()
        self.loader_worker = ModelLoader()
        self.loader_worker.moveToThread(self.loader_thread)

        self.loader_thread.started.connect(self.loader_worker.run)
        self.loader_worker.finished.connect(self.on_model_loaded)
        self.loader_worker.error.connect(self.on_model_error)

        self.loader_thread.start()

    @pyqtSlot(object)
    def on_model_loaded(self, model_instance):
        self.model.giga_model = model_instance
        self.view.log("Базовая модель GigaAM загружена в память.")
        self.view.btn_start_transcription.setEnabled(True)
        self.loader_thread.quit()
        self.loader_thread.wait()

    @pyqtSlot(str)
    def on_model_error(self, error_msg):
        self.view.log(f"Ошибка загрузки модели GigaAM: {error_msg}")
        self.view.show_critical("Критическая ошибка", f"Не удалось загрузить модель GigaAM:\n{error_msg}")
        self.loader_thread.quit()
        self.loader_thread.wait()

    # Live Transcription
    def toggle_transcription(self):
        if self.live_thread and self.live_thread.isRunning():
            self.view.btn_start_transcription.setEnabled(False)
            self.live_worker.stop()
            return

        if not self.model.output_txt_path or self.view.device_dropdown.count() == 0:
            self.view.show_warning("Внимание", "Заполните настройки: укажите выходной текстовый файл и выберите устройство.")
            return
        if self.model.save_audio and not self.model.output_wav_path:
            self.view.show_warning("Внимание", "Укажите путь для сохранения мастер-файла .wav.")
            return

        device_name = self.view.device_dropdown.currentText()
        device_id = self.model.device_mapping[device_name]

        try:
            device_info = sd.query_devices(device_id, 'input')
            channels = int(device_info['max_input_channels'])
        except Exception:
            channels = 1

        self.live_thread = QThread()
        self.live_worker = LiveTranscriptionWorker(
            model=self.model.giga_model,
            device_id=device_id,
            channels=channels,
            output_txt=self.model.output_txt_path,
            save_audio=self.model.save_audio,
            output_wav=self.model.output_wav_path
        )
        self.live_worker.moveToThread(self.live_thread)

        self.live_thread.started.connect(self.live_worker.run)
        self.live_worker.log_signal.connect(self.view.log)
        self.live_worker.finished_signal.connect(self.on_transcription_stopped)

        self.live_thread.start()

        self.view.btn_start_transcription.setText("⏹️ Остановить и сохранить всё")
        self.view.btn_start_transcription.setStyleSheet("background-color: #e02424; color: white;")
        self.view.device_dropdown.setEnabled(False)
        self.view.save_audio_chk.setEnabled(False)
        self.view.btn_browse_wav.setEnabled(False)
        self.view.log("🏁 Потоковая транскрибация запущена...")

    def on_transcription_stopped(self):
        self.live_thread.quit()
        self.live_thread.wait()

        self.view.btn_start_transcription.setText("Запустить транскрибацию")
        self.view.btn_start_transcription.setStyleSheet("")
        self.view.btn_start_transcription.setEnabled(True)
        self.view.device_dropdown.setEnabled(True)
        self.view.save_audio_chk.setEnabled(True)
        if self.model.save_audio:
            self.view.btn_browse_wav.setEnabled(True)

        self.view.log("🏁 Процесс записи и сохранения полностью завершен.")

    # WhisperX Worker Execution
    def start_whisperx(self):
        if not self.model.whisper_audio_path:
            self.view.show_warning("Внимание", "Выберите аудиофайл для постобработки.")
            return

        selected_formats = []
        if self.view.wx_txt_var.isChecked(): selected_formats.append("txt")
        if self.view.wx_srt_var.isChecked(): selected_formats.append("srt")
        if self.view.wx_tsv_var.isChecked(): selected_formats.append("tsv")
        if self.view.wx_json_var.isChecked(): selected_formats.append("json")
        if self.view.wx_vtt_var.isChecked(): selected_formats.append("vtt")

        if not selected_formats:
            self.view.show_warning("Внимание", "Выберите хотя бы один формат на выходе!")
            return

        hf_token = self.view.token_input.text().strip()
        if not hf_token or hf_token.startswith("hf_какой_то_ваш"):
            self.view.show_critical("Ошибка токена", "Проверьте валидность HF_TOKEN в верхней строке интерфейса.")
            return

        self.view.btn_wx_start.setEnabled(False)
        self.view.btn_wx_start.setText("⏳ Выполняется обработка WhisperX...")

        self.whisper_thread = QThread()
        self.whisper_worker = WhisperXWorker(self.model.whisper_audio_path, hf_token, selected_formats)
        self.whisper_worker.moveToThread(self.whisper_thread)

        self.whisper_thread.started.connect(self.whisper_worker.run)
        self.whisper_worker.log_signal.connect(self.view.log)
        self.whisper_worker.finished_signal.connect(self.on_whisper_finished)

        self.whisper_thread.start()

    @pyqtSlot(bool)
    def on_whisper_finished(self, success):
        self.whisper_thread.quit()
        self.whisper_thread.wait()

        self.view.btn_wx_start.setEnabled(True)
        self.view.btn_wx_start.setText("🚀 Запустить разделение спикеров (WhisperX)")

        if success:
            output_dir = os.path.dirname(self.model.whisper_audio_path)
            self.view.log(f"🎉 Успех! Файлы сохранены в папку: {output_dir}")
            self.view.show_info("Готово", f"WhisperX успешно завершил обработку файла!\nПапка: {output_dir}")
        else:
            self.view.log("💥 Обработка WhisperX завершилась с ошибкой.")
            self.view.show_critical("Ошибка", "Произошла ошибка при выполнении сценария WhisperX. Проверьте консоль логов.")

    # GigaAM Diarization Worker Execution
    def start_giga_diarization(self):
        if not self.model.giga_diarize_audio_path or not self.model.giga_diarize_txt_path:
            self.view.show_warning("Внимание", "Заполните пути: выберите входной аудиофайл и целевой файл сохранения .txt")
            return

        hf_token = self.view.token_input.text().strip()
        if not hf_token or hf_token.startswith("hf_какой_то_ваш"):
            self.view.show_critical("Ошибка токена", "Проверьте валидность HF_TOKEN в верхней строке интерфейса.")
            return

        if self.model.use_exact_speakers:
            num_spk = self.view.spin_exact_spk.value()
            min_spk, max_spk = None, None
        else:
            num_spk = None
            min_spk = self.view.spin_min_spk.value()
            max_spk = self.view.spin_max_spk.value()

        self.view.gd_progress.setValue(0)
        self.view.btn_gd_start.setEnabled(False)
        self.view.btn_gd_start.setText("⏳ Выполняется обработка GigaAM...")

        self.giga_diarize_thread = QThread()
        self.giga_diarize_worker = GigaAMDiarizeWorker(
            audio_path=self.model.giga_diarize_audio_path,
            output_txt=self.model.giga_diarize_txt_path,
            hf_token=hf_token,
            min_speakers=min_spk,
            max_speakers=max_spk,
            num_speakers=num_spk
        )
        self.giga_diarize_worker.moveToThread(self.giga_diarize_thread)

        self.giga_diarize_thread.started.connect(self.giga_diarize_worker.run)
        self.giga_diarize_worker.log_signal.connect(self.view.log)
        self.giga_diarize_worker.progress_signal.connect(self.view.gd_progress.setValue)
        self.giga_diarize_worker.finished_signal.connect(self.on_giga_diarize_finished)

        self.giga_diarize_thread.start()

    @pyqtSlot(bool)
    def on_giga_diarize_finished(self, success):
        self.giga_diarize_thread.quit()
        self.giga_diarize_thread.wait()

        self.view.btn_gd_start.setEnabled(True)
        self.view.btn_gd_start.setText("🚀 Запустить разделение спикеров (GigaAM)")

        if success:
            self.view.gd_progress.setValue(100)
            self.view.log(f"🎉 Успех! Результат сохранен: {self.model.giga_diarize_txt_path}")
            self.view.show_info("Готово", f"Разделение ролей через GigaAM успешно завершено!\nФайл: {self.model.giga_diarize_txt_path}")
        else:
            self.view.gd_progress.setValue(0)
            self.view.show_critical("Ошибка", "Произошла ошибка при выполнении сценария GigaAM. Проверьте консоль логов.")

    # Intercept view destruction to safely stop workers
    def on_close_requested(self, event):
        active_processes = (
            (self.live_thread and self.live_thread.isRunning()) or
            (self.whisper_thread and self.whisper_thread.isRunning()) or
            (self.giga_diarize_thread and self.giga_diarize_thread.isRunning())
        )
        if active_processes:
            confirmed = self.view.show_question(
                "Выход", 
                "У вас есть активные фоновые процессы. Все равно выйти?"
            )
            if not confirmed:
                event.ignore()
                return

        # Force stopping live worker safely
        if self.live_worker:
            self.live_worker.stop()
        
        # Shutdown threads cleanly
        for thread in [self.live_thread, self.whisper_thread, self.giga_diarize_thread]:
            if thread:
                thread.quit()
                thread.wait()
                
        event.accept()
