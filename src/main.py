import sys
from dotenv import load_dotenv
from PyQt6.QtWidgets import QApplication

# Load environment variables (like HF_TOKEN) right at the top
load_dotenv()

# Import our MVC components
from backend.model import VoiceScribeModel
from frontend.view import VoiceScribeView
from frontend.controller import VoiceScribeController

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Instantiate the MVC architecture components
    model = VoiceScribeModel()
    view = VoiceScribeView()
    controller = VoiceScribeController(model, view)
    
    view.show()
    sys.exit(app.exec())
