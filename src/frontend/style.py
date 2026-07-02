MODERN_STYLE = """
QMainWindow {
    background-color: #0e0e11;
}

QWidget {
    color: #e4e4e7;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
}

/* Card design for container frames */
QFrame#Card {
    background-color: #18181c;
    border: 1px solid #27272a;
    border-radius: 10px;
}

/* Sidebar navigation widget styling */
QListWidget#Sidebar {
    background-color: #121216;
    border: 1px solid #27272a;
    border-radius: 10px;
    padding: 8px 0px;
    outline: none;
}

QListWidget#Sidebar::item {
    padding: 12px 16px;
    border-radius: 8px;
    color: #a1a1aa;
    margin: 6px 10px;
    border: none;
    font-size: 13px;
    font-weight: 500;
}

QListWidget#Sidebar::item:selected {
    background-color: #7c4dff;
    color: #ffffff;
    font-weight: 600;
}

QListWidget#Sidebar::item:hover:!selected {
    background-color: #242429;
    color: #f4f4f5;
}

/* Main Tab layout configurations */
QTabWidget::pane {
    border: 1px solid #27272a;
    background-color: #18181c;
    border-radius: 10px;
    top: -1px;
}

QTabBar::tab {
    background-color: #0e0e11;
    border: 1px solid #27272a;
    padding: 10px 20px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
    color: #a1a1aa;
}

QTabBar::tab:selected {
    background-color: #18181c;
    border-bottom-color: #18181c;
    color: #9871ff;
    font-weight: 600;
}

/* Button design presets */
QPushButton {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    color: #f4f4f5;
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #3f3f46;
    border-color: #52525b;
}

QPushButton:pressed {
    background-color: #1e1e21;
}

QPushButton:disabled {
    background-color: #1f1f23;
    border-color: #27272a;
    color: #52525b;
}

QPushButton#PrimaryAction {
    background-color: #7c4dff;
    color: #ffffff;
    border: 1px solid #6d3aee;
}

QPushButton#PrimaryAction:hover {
    background-color: #8c60ff;
    border-color: #7c4dff;
}

QPushButton#PrimaryAction:pressed {
    background-color: #6536df;
}

QPushButton#PrimaryAction:disabled {
    background-color: #241d3d;
    border-color: #1a152d;
    color: #5d5483;
}

/* Form Controls (Inputs, Combo boxes, Spin boxes) */
QComboBox, QSpinBox, QLineEdit {
    background-color: #121215;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 7px 12px;
    color: #f4f4f5;
    selection-background-color: #7c4dff;
}

QComboBox:focus, QSpinBox:focus, QLineEdit:focus {
    border: 1px solid #9871ff;
}

QComboBox::drop-down {
    border: none;
    padding-right: 10px;
}

/* Labels and Texts styling */
QLabel {
    font-size: 13px;
}

/* Checkboxes styling */
QCheckBox {
    spacing: 10px;
    color: #e4e4e7;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    background-color: #121215;
}

QCheckBox::indicator:checked {
    background-color: #7c4dff;
    border-color: #7c4dff;
    image: url(data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>);
}

QCheckBox::indicator:hover {
    border-color: #52525b;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background-color: #121215;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #27272a;
    min-height: 30px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background-color: #3f3f46;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}

/* Console terminal outputs */
QTextEdit {
    background-color: #09090b;
    border: 1px solid #1f1f23;
    border-radius: 8px;
    font-family: 'SF Mono', 'Fira Code', 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    color: #a1a1aa;
    line-height: 1.6;
    padding: 8px;
}

/* Progress indicator bars */
QProgressBar {
    border: 1px solid #27272a;
    border-radius: 8px;
    background-color: #09090b;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
    height: 24px;
}

QProgressBar::chunk {
    background-color: #7c4dff;
    border-radius: 7px;
}
"""
