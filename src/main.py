import sys
from dotenv import load_dotenv
from PyQt6.QtWidgets import QApplication

# Load environment variables (like HF_TOKEN) right at the top
load_dotenv()

# Import the decoupled app class from our frontend module
from frontend.app import VoiceScribeMultiToolApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VoiceScribeMultiToolApp()
    window.show()
    sys.exit(app.exec())
