#!/usr/bin/env python3
"""Lenovo Vantage controls for Linux, built with KDE-friendly Qt Widgets."""
import glob
import os
import re
import shutil
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

APP_ID = "io.github.niizam.vantage"
HELPER = "/usr/lib/vantage/vantage-helper"

FAN_MODES = [
    ("Super Silent", "silent"),
    ("Standard", "standard"),
    ("Dust Cleaning", "dust"),
    ("Efficient Thermal Dissipation", "efficient"),
]
FAN_MODE_VALUES = {"0": "silent", "133": "silent", "1": "standard", "2": "dust", "4": "efficient"}


def sh(*args):
    """Run a command, returning (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(args, capture_output=True, text=True)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"{args[0]}: not found"


def which(cmd):
    return shutil.which(cmd) is not None


def vpc_path(name):
    matches = glob.glob(f"/sys/bus/platform/devices/VPC2004:*/{name}")
    return matches[0] if matches else None


def read_file(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def run_helper(*args):
    rc, _, err = sh("pkexec", HELPER, *args)
    return rc == 0, err or "Permission denied"


# --- Hardware controls ---
def get_conservation_mode():
    return read_file(vpc_path("conservation_mode")) == "1"


def set_conservation_mode(active):
    return run_helper("conservation_mode", "on" if active else "off")


def get_usb_charging():
    return read_file(vpc_path("usb_charging")) == "1"


def set_usb_charging(active):
    return run_helper("usb_charging", "on" if active else "off")


def get_fan_mode():
    return FAN_MODE_VALUES.get(read_file(vpc_path("fan_mode")), "standard")


def set_fan_mode(key):
    return run_helper("fan_mode", key)


def get_fn_lock():
    return read_file(vpc_path("fn_lock")) != "1"


def set_fn_lock(active):
    return run_helper("fn_lock", "on" if active else "off")


def get_camera():
    _, out, _ = sh("lsmod")
    return "uvcvideo" in out


def set_camera(active):
    return run_helper("camera", "on" if active else "off")


def get_mic_active():
    _, out, _ = sh("pactl", "get-source-mute", "@DEFAULT_SOURCE@")
    return "yes" not in out.lower()


def set_mic_active(active):
    rc, _, err = sh("pactl", "set-source-mute", "@DEFAULT_SOURCE@", "0" if active else "1")
    return rc == 0, err


def is_wayland_session():
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


def get_touchpad():
    """Return the touchpad and backend usable in this desktop session."""
    if is_wayland_session():
        if os.environ.get("XDG_CURRENT_DESKTOP", "").lower().find("kde") < 0 or not which("busctl"):
            return None
        for name_path in glob.glob("/sys/class/input/event*/device/name"):
            name = read_file(name_path)
            if name and "touchpad" in name.casefold():
                event = name_path.split("/")[-3]
                path = f"/org/kde/KWin/InputDevice/{event}"
                rc, out, _ = sh(
                    "busctl", "--user", "get-property", "org.kde.KWin", path,
                    "org.kde.KWin.InputDevice", "enabled",
                )
                if rc == 0 and out:
                    return {"backend": "kwin", "id": path, "name": name}
        return None

    rc, out, _ = sh("xinput", "list")
    if rc != 0:
        return None
    for line in out.splitlines():
        if "Touchpad" in line:
            match = re.search(r"id=(\d+)", line)
            if match:
                return {"backend": "xinput", "id": match.group(1), "name": line.strip()}
    return None


def get_touchpad_active(touchpad):
    if touchpad["backend"] == "kwin":
        rc, out, _ = sh(
            "busctl", "--user", "get-property", "org.kde.KWin", touchpad["id"],
            "org.kde.KWin.InputDevice", "enabled",
        )
        return rc == 0 and out.endswith(" true")
    _, out, _ = sh("xinput", "--list-props", touchpad["id"])
    for line in out.splitlines():
        if "Device Enabled" in line:
            return line.split(":")[-1].strip() == "1"
    return True


def set_touchpad_active(touchpad, active):
    if touchpad["backend"] == "kwin":
        rc, _, err = sh(
            "busctl", "--user", "set-property", "org.kde.KWin", touchpad["id"],
            "org.kde.KWin.InputDevice", "enabled", "b", "true" if active else "false",
        )
        return rc == 0, err
    rc, _, err = sh("xinput", "enable" if active else "disable", touchpad["id"])
    return rc == 0, err


def get_wifi_active():
    _, out, _ = sh("nmcli", "radio", "wifi")
    return out.strip() == "enabled"


def set_wifi_active(active):
    rc, _, err = sh("nmcli", "radio", "wifi", "on" if active else "off")
    return rc == 0, err


class SettingRow(QFrame):
    """A compact settings row using the active Qt/KDE palette and style."""

    def __init__(self, title, description, parent=None):
        super().__init__(parent)
        self.setObjectName("settingRow")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("settingTitle")
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        description_label = QLabel(description)
        description_label.setObjectName("settingDescription")
        description_label.setWordWrap(True)
        text_box.addWidget(title_label)
        text_box.addWidget(description_label)
        layout.addLayout(text_box, 1)


class VantageWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lenovo Vantage")
        self.setMinimumSize(520, 560)
        self.resize(620, 700)
        self.rows = []

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Lenovo Vantage")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Hardware settings")
        subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        heading.addLayout(title_box, 1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search settings…")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(240)
        self.search.textChanged.connect(self.filter_rows)
        heading.addWidget(self.search, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(heading)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(18)
        self.scroll.setWidget(self.content)
        outer.addWidget(self.scroll, 1)
        self.setCentralWidget(central)

        self.populate()
        self.search.setFocus()

        escape = QAction(self)
        escape.setShortcut(Qt.Key.Key_Escape)
        escape.triggered.connect(self.close)
        self.addAction(escape)

    def add_section(self, title):
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
        self.content_layout.addWidget(section)
        return layout

    def register_row(self, row, searchable):
        row.search_text = searchable.lower()
        self.rows.append(row)

    def add_switch(self, section, title, description, get_fn, set_fn):
        row = SettingRow(title, description)
        switch = QCheckBox()
        switch.setChecked(bool(get_fn()))
        switch.setAccessibleName(title)
        switch.setCursor(Qt.CursorShape.PointingHandCursor)
        row.layout().addWidget(switch, 0, Qt.AlignmentFlag.AlignVCenter)

        def changed(active):
            ok, err = set_fn(active)
            if not ok:
                switch.blockSignals(True)
                switch.setChecked(not active)
                switch.blockSignals(False)
                QMessageBox.warning(self, title, err or "The setting could not be changed.")

        switch.toggled.connect(changed)
        section.addWidget(row)
        self.register_row(row, f"{title} {description}")
        return row

    def add_fan_mode(self, section):
        title, description = "Fan mode", "Choose the thermal and fan profile for this laptop"
        row = SettingRow(title, description)
        combo = QComboBox()
        for label, key in FAN_MODES:
            combo.addItem(label, key)
        combo.setCurrentIndex(max(0, combo.findData(get_fan_mode())))
        combo.setMinimumContentsLength(18)
        row.layout().addWidget(combo, 0, Qt.AlignmentFlag.AlignVCenter)

        def changed(index):
            key = combo.itemData(index)
            ok, err = set_fan_mode(key)
            if not ok:
                QMessageBox.warning(self, "Fan mode", err or "The fan mode could not be changed.")
                combo.blockSignals(True)
                combo.setCurrentIndex(max(0, combo.findData(get_fan_mode())))
                combo.blockSignals(False)

        combo.currentIndexChanged.connect(changed)
        section.addWidget(row)
        self.register_row(row, f"{title} {description} {' '.join(x[0] for x in FAN_MODES)}")

    def populate(self):
        power = self.add_section("Power")
        if vpc_path("conservation_mode"):
            self.add_switch(power, "Conservation mode", "Limit battery charge to help preserve battery lifespan", get_conservation_mode, set_conservation_mode)
        if vpc_path("usb_charging"):
            self.add_switch(power, "Always-on USB", "Charge connected devices while the laptop is off", get_usb_charging, set_usb_charging)

        performance = self.add_section("Performance")
        if vpc_path("fan_mode"):
            self.add_fan_mode(performance)
        if vpc_path("fn_lock"):
            self.add_switch(performance, "Fn Lock", "Use F1–F12 as standard function keys", get_fn_lock, set_fn_lock)

        devices = self.add_section("Devices")
        touchpad = get_touchpad()
        if touchpad:
            self.add_switch(devices, "Touchpad", "Enable or disable the built-in touchpad", lambda: get_touchpad_active(touchpad), lambda active: set_touchpad_active(touchpad, active))
        if sh("modinfo", "-n", "uvcvideo")[0] == 0:
            self.add_switch(devices, "Camera", "Enable or disable the webcam driver", get_camera, set_camera)
        if which("pactl"):
            self.add_switch(devices, "Microphone", "Mute or unmute the default microphone", get_mic_active, set_mic_active)
        if which("nmcli"):
            self.add_switch(devices, "Wi-Fi", "Turn the wireless radio on or off", get_wifi_active, set_wifi_active)

        for section_index in range(self.content_layout.count()):
            section = self.content_layout.itemAt(section_index).widget()
            section.setVisible(section.layout().count() > 1)
        if not self.rows:
            empty = QLabel("This device doesn't expose any supported Lenovo hardware controls.")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_layout.addWidget(empty)
        self.content_layout.addStretch(1)

    def filter_rows(self, text):
        query = text.strip().casefold()
        for row in self.rows:
            row.setVisible(query in row.search_text)
        for section_index in range(self.content_layout.count()):
            item = self.content_layout.itemAt(section_index)
            section = item.widget()
            if section and section.layout():
                children = [section.layout().itemAt(i).widget() for i in range(section.layout().count())]
                section.setVisible(any(child and not child.isHidden() for child in children[1:]))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Lenovo Vantage")
    app.setApplicationDisplayName("Lenovo Vantage")
    app.setDesktopFileName("vantage")
    # Do not set a custom palette or style. Qt's platform theme plugin supplies
    # KDE's active color scheme, Breeze style, and light/dark colors automatically.
    window = VantageWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
