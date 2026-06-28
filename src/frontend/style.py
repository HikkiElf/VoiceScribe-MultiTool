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
