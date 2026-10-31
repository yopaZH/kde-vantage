#!/usr/bin/env python3
"""Lenovo Vantage controls for Linux, built with KDE-friendly Qt Widgets."""
import glob
import os
import re
import shutil
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
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


class SettingRow(QWidget):
    """A flat settings-page row styled entirely by the active Qt theme."""

    def __init__(self, title, description, control, parent=None):
        super().__init__(parent)
        self.search_text = f"{title} {description}".casefold()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(24)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(4)
        title_label = QLabel(title)
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        text_box.addWidget(title_label)
        text_box.addWidget(description_label)
        layout.addLayout(text_box, 1)
        layout.addWidget(control, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


class VantageWindow(QMainWindow):
    CATEGORIES = [
        ("Power", "Battery and charging settings", "preferences-system-power-management"),
        ("Performance", "Thermal and keyboard settings", "preferences-system-performance"),
        ("Devices", "Connected hardware and radios", "preferences-desktop-peripherals"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lenovo Vantage")
        self.setMinimumSize(760, 560)
        self.resize(980, 680)
        self.rows = []
        self.pages = {}
        self.page_layouts = {}
        self.category_items = {}

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("navigationSidebar")
        sidebar.setMinimumWidth(210)
        sidebar.setMaximumWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(12)
        app_name = QLabel("Lenovo Vantage")
        app_name.setContentsMargins(8, 4, 8, 8)
        sidebar_layout.addWidget(app_name)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search settings…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_rows)
        sidebar_layout.addWidget(self.search)
        self.navigation = QListWidget()
        self.navigation.setFrameShape(QFrame.Shape.NoFrame)
        self.navigation.currentItemChanged.connect(self.open_category)
        sidebar_layout.addWidget(self.navigation, 1)
        root.addWidget(sidebar)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(divider)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.create_pages()
        self.populate()
        self.search.setFocus()

        escape = QAction(self)
        escape.setShortcut(Qt.Key.Key_Escape)
        escape.triggered.connect(self.close)
        self.addAction(escape)

    def create_pages(self):
        for name, description, icon_name in self.CATEGORIES:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(32, 26, 32, 24)
            page_layout.setSpacing(18)

            heading = QVBoxLayout()
            heading.setSpacing(4)
            title = QLabel(name)
            title_font = title.font()
            title_font.setPointSizeF(title_font.pointSizeF() * 1.4)
            title_font.setWeight(QFont.Weight.DemiBold)
            title.setFont(title_font)
            subtitle = QLabel(description)
            heading.addWidget(title)
            heading.addWidget(subtitle)
            page_layout.addLayout(heading)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            body = QWidget()
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(0, 0, 0, 0)
            body_layout.setSpacing(0)
            scroll.setWidget(body)
            page_layout.addWidget(scroll, 1)

            no_results = QLabel("No matching settings")
            no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_results.hide()
            page_layout.addWidget(no_results)

            self.pages[name] = page
            self.page_layouts[name] = (body_layout, no_results)
            self.stack.addWidget(page)
            item = QListWidgetItem(name)
            item.setIcon(QIcon.fromTheme(icon_name))
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.navigation.addItem(item)
            self.category_items[name] = item

    def add_row(self, category, title, description, searchable, control):
        row = SettingRow(title, description, control)
        row.search_text = f"{searchable} {title} {description}".casefold()
        layout, _ = self.page_layouts[category]
        if layout.count():
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Sunken)
            layout.addWidget(separator)
            row.separator = separator
        else:
            row.separator = None
        layout.addWidget(row)
        self.rows.append((category, row))
        return row

    def add_switch(self, category, title, description, get_fn, set_fn):
        switch = QCheckBox()
        switch.setChecked(bool(get_fn()))
        switch.setAccessibleName(title)
        switch.setCursor(Qt.CursorShape.PointingHandCursor)
        row = self.add_row(category, title, description, "", switch)

        def changed(active):
            ok, err = set_fn(active)
            if not ok:
                switch.blockSignals(True)
                switch.setChecked(not active)
                switch.blockSignals(False)
                QMessageBox.warning(self, title, err or "The setting could not be changed.")

        switch.toggled.connect(changed)
        return row

    def add_fan_mode(self):
        title, description = "Fan mode", "Choose the thermal and fan profile for this laptop"
        combo = QComboBox()
        for label, key in FAN_MODES:
            combo.addItem(label, key)
        combo.setCurrentIndex(max(0, combo.findData(get_fan_mode())))
        combo.setMinimumContentsLength(18)
        self.add_row("Performance", title, description, " ".join(x[0] for x in FAN_MODES), combo)

        def changed(index):
            ok, err = set_fan_mode(combo.itemData(index))
            if not ok:
                QMessageBox.warning(self, "Fan mode", err or "The fan mode could not be changed.")
                combo.blockSignals(True)
                combo.setCurrentIndex(max(0, combo.findData(get_fan_mode())))
                combo.blockSignals(False)

        combo.currentIndexChanged.connect(changed)

    def populate(self):
        if vpc_path("conservation_mode"):
            self.add_switch("Power", "Conservation mode", "Limit battery charge to help preserve battery lifespan", get_conservation_mode, set_conservation_mode)
        if vpc_path("usb_charging"):
            self.add_switch("Power", "Always-on USB", "Charge connected devices while the laptop is off", get_usb_charging, set_usb_charging)

        if vpc_path("fan_mode"):
            self.add_fan_mode()
        if vpc_path("fn_lock"):
            self.add_switch("Performance", "Fn Lock", "Use F1–F12 as standard function keys", get_fn_lock, set_fn_lock)

        touchpad = get_touchpad()
        if touchpad:
            self.add_switch("Devices", "Touchpad", "Enable or disable the built-in touchpad", lambda: get_touchpad_active(touchpad), lambda active: set_touchpad_active(touchpad, active))
        if sh("modinfo", "-n", "uvcvideo")[0] == 0:
            self.add_switch("Devices", "Camera", "Enable or disable the webcam driver", get_camera, set_camera)
        if which("pactl"):
            self.add_switch("Devices", "Microphone", "Mute or unmute the default microphone", get_mic_active, set_mic_active)
        if which("nmcli"):
            self.add_switch("Devices", "Wi-Fi", "Turn the wireless radio on or off", get_wifi_active, set_wifi_active)

        for name, _, _ in self.CATEGORIES:
            if not self.page_layouts[name][0].count():
                self.category_items[name].setHidden(True)

        if self.rows:
            first = next(name for name, _, _ in self.CATEGORIES if not self.category_items[name].isHidden())
            self.navigation.setCurrentItem(self.category_items[first])
        else:
            empty = QLabel("This device doesn't expose any supported Lenovo hardware controls.")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stack.addWidget(empty)
            self.stack.setCurrentWidget(empty)

    def open_category(self, current, _previous):
        if not current:
            return
        category = current.data(Qt.ItemDataRole.UserRole)
        self.stack.setCurrentWidget(self.pages[category])
        self.filter_rows(self.search.text())

    def filter_rows(self, text):
        query = text.strip().casefold()
        available_categories = set()
        for category, row in self.rows:
            matches = query in row.search_text
            row.setVisible(matches)
            if row.separator:
                row.separator.setVisible(matches)
            if matches:
                available_categories.add(category)
        for name, _, _ in self.CATEGORIES:
            has_matches = name in available_categories
            self.category_items[name].setHidden(not has_matches)
            self.page_layouts[name][1].setVisible(bool(query) and not has_matches)
        current = self.navigation.currentItem()
        if current and current.isHidden():
            for name, _, _ in self.CATEGORIES:
                if not self.category_items[name].isHidden():
                    self.navigation.setCurrentItem(self.category_items[name])
                    break


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
