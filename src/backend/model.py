import os
from dotenv import load_dotenv

class VoiceScribeModel:
    """
    Model class representing the data and state of the VoiceScribe application.
    """
    def __init__(self):
        load_dotenv()
        
        # Core loaded components
        self.giga_model = None
        self.device_mapping = {}
        
        # Settings and file paths
        self.output_txt_path = ""
        self.output_wav_path = ""
        self.whisper_audio_path = ""
        self.giga_diarize_audio_path = ""
        self.giga_diarize_txt_path = ""
        
        # HF Token config
        self.hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_READ_TOKEN") or ""
        
        # Audio / Diarization properties
        self.save_audio = False
        self.min_speakers = 1
        self.max_speakers = 6
        self.exact_speakers = 2
        self.use_exact_speakers = False
        self.whisperx_formats = ["txt", "srt", "tsv", "json", "vtt"]
        
    def update_hf_token(self, token: str) -> bool:
        """
        Saves token to environment and updates the local .env configuration file.
        """
        self.hf_token = token
        os.environ["HF_TOKEN"] = token
        env_lines = []
        has_token = False

        try:
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

            with open(".env", "w", encoding="utf-8") as f:
                f.writelines(env_lines)
            return True
        except Exception:
            return False
