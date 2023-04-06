import sys
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QSlider, QLineEdit
from PySide6.QtGui import QIntValidator
from PySide6.QtCore import Qt

def on_slider_value_changed(value):
    print("Slider value:", value)
    line_edit.setText(str(value))

def on_line_edit_enter_pressed():
    user_input = line_edit.text()
    if user_input.isdigit():
        slider.setValue(int(user_input))

app = QApplication(sys.argv)

window = QWidget()
layout = QVBoxLayout(window)

slider = QSlider(Qt.Horizontal)
slider.setMinimum(0)
slider.setMaximum(100)
slider.setTickPosition(QSlider.TicksBelow)
slider.setTickInterval(10)
slider.valueChanged.connect(on_slider_value_changed)

line_edit = QLineEdit()
line_edit.setPlaceholderText("Enter a value between 0 and 100")
line_edit.setValidator(QIntValidator(0, 100))
line_edit.returnPressed.connect(on_line_edit_enter_pressed)

layout.addWidget(slider)
layout.addWidget(line_edit)

window.show()
sys.exit(app.exec_())
