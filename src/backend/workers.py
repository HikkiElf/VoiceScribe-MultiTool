import os
import sys
import time
import queue
import subprocess
import numpy as np
import torch
import sounddevice as sd
import scipy.io.wavfile as wavf
import gigaam
from PyQt6.QtCore import QObject, pyqtSignal
from .config import MODEL_NAME, SAMPLE_RATE, CHUNK_DURATION, SILENCE_THRESHOLD, SILENCE_DURATION

try:
    from pyannote.audio import Pipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False
    Pipeline = None

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
        silence_samples = 0
        has_speech = False

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

                            # Track continuous silence
                            if np.max(np.abs(data)) < SILENCE_THRESHOLD:
                                silence_samples += len(data)
                            else:
                                silence_samples = 0
                                has_speech = True

                            current_audio = np.concatenate(audio_buffer, axis=0)

                            # Calculate current silence duration in seconds
                            silence_duration = silence_samples / SAMPLE_RATE

                            # Condition 1: Max chunk duration reached
                            max_duration_reached = len(current_audio) >= samples_per_chunk

                            # Condition 2: Silence duration reached after some speech was detected
                            silence_reached = has_speech and (silence_duration >= SILENCE_DURATION)

                            if max_duration_reached or silence_reached:
                                # Prevent transcribing if the entire buffer is just background noise/silence
                                if np.max(np.abs(current_audio)) < SILENCE_THRESHOLD:
                                    audio_buffer = []
                                    silence_samples = 0
                                    has_speech = False
                                    continue

                                # Reset states for the next chunk
                                audio_buffer = []
                                silence_samples = 0
                                has_speech = False

                                temp_wav = f"ui_temp_{int(time.time())}.wav"
                                wavf.write(temp_wav, SAMPLE_RATE, current_audio)

                                try:
                                    # Try standard transcribe first
                                    try:
                                        result = self.model.transcribe(temp_wav)
                                    except Exception as transcribe_e:
                                        # Fallback to longform if the file exceeds standard limits
                                        if "Too long wav file" in str(transcribe_e) and hasattr(self.model, "transcribe_longform"):
                                            self.log_signal.emit("⚠️ Аудио слишком длинное, переключаюсь на transcribe_longform...")
                                            result = self.model.transcribe_longform(temp_wav)
                                        else:
                                            raise transcribe_e

                                    # Extract text safely
                                    if hasattr(result, 'text'):
                                        text = result.text.strip()
                                    elif isinstance(result, dict):
                                        text = result.get("text", "").strip()
                                    else:
                                        text = str(result).strip()

                                    if text:
                                        self.log_signal.emit(f"Распознано: {text}")
                                        txt_file.write(text + "\n")
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

            if not PYANNOTE_AVAILABLE:
                self.log_signal.emit("💥 Ошибка: Модуль pyannote.audio не установлен.")
                self.finished_signal.emit(False)
                return

            self.log_signal.emit("--> [GigaAM-Diarize] Загрузка модели GigaAM...")
            model = gigaam.load_model(MODEL_NAME)
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

            diarize_kwargs = {}
            if self.num_speakers is not None:
                diarize_kwargs["num_speakers"] = self.num_speakers
            else:
                if self.min_speakers is not None:
                    diarize_kwargs["min_speakers"] = self.min_speakers
                if self.max_speakers is not None:
                    diarize_kwargs["max_speakers"] = self.max_speakers

            self.log_signal.emit("--> [GigaAM-Diarize] Анализ структуры спикеров (PyAnnote VAD/Embedding)...")
            diarization_output = diarize_pipeline(self.audio_path, **diarize_kwargs)
            self.progress_signal.emit(65)

            self.log_signal.emit("--> [GigaAM-Diarize] Нарезка сегментов и транскрибация через GigaAM...")

            turns = list(diarization_output.exclusive_speaker_diarization)
            total_turns = len(turns)

            with open(self.output_txt, "w", encoding="utf-8") as f:
                for idx, (turn, speaker) in enumerate(turns):
                    start_time = turn.start
                    end_time = turn.end
                    duration = end_time - start_time

                    if duration < 0.4:
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
                        result = model.transcribe(temp_chunk)
                        text = result.text.strip() if hasattr(result, 'text') else str(result).strip()

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

                    current_pct = int(65 + ((idx + 1) / total_turns) * 35)
                    self.progress_signal.emit(current_pct)

            self.progress_signal.emit(100)
            self.finished_signal.emit(True)
        except Exception as e:
            self.log_signal.emit(f"💥 Критическая ошибка разделения ролей GigaAM: {e}")
            self.finished_signal.emit(False)
