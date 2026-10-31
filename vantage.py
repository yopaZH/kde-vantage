#!/usr/bin/env python3
"""Lenovo Vantage controls for Linux, built with KDE-friendly Qt Widgets."""
import glob
import os
import re
import shutil
import subprocess
import sys

from PySide6.QtCore import Qt, QLocale
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

APP_ID = "io.github.niizam.vantage"
HELPER = "/usr/lib/vantage/vantage-helper"

FAN_MODES = [
    ("fan_silent", "silent"),
    ("fan_standard", "standard"),
    ("fan_dust", "dust"),
    ("fan_efficient", "efficient"),
]
FAN_MODE_VALUES = {"0": "silent", "133": "silent", "1": "standard", "2": "dust", "4": "efficient"}

TRANSLATIONS = {
    "en": {
        "subtitle": "Manage your laptop's hardware settings",
        "power": "Power",
        "performance": "Performance",
        "devices": "Devices",
        "conservation_mode": "Conservation mode",
        "conservation_description": "Limit the maximum charge to help extend battery lifespan",
        "usb_charging": "Always-on USB",
        "usb_charging_description": "Keep USB ports powered while the laptop is off",
        "fan_mode": "Fan mode",
        "fan_description": "Choose a cooling profile for the laptop",
        "fan_silent": "Super Silent",
        "fan_standard": "Standard",
        "fan_dust": "Dust Cleaning",
        "fan_efficient": "Efficient Thermal Dissipation",
        "fn_lock": "Fn Lock",
        "fn_lock_description": "Use F1–F12 as standard function keys",
        "touchpad": "Touchpad",
        "touchpad_description": "Enable or disable the built-in touchpad",
        "camera": "Camera",
        "camera_description": "Enable or disable the built-in camera",
        "microphone": "Microphone",
        "microphone_description": "Mute or unmute the default input device",
        "wifi": "Wi-Fi",
        "wifi_description": "Enable or disable the wireless connection",
        "no_controls": "No supported hardware controls found",
        "no_controls_description": "This device doesn't expose any Lenovo Vantage settings.",
        "setting_error": "The setting could not be changed.",
        "enabled": "Enabled",
        "disabled": "Disabled",
    },
    "ru": {
        "subtitle": "Настройка оборудования ноутбука",
        "power": "Питание",
        "performance": "Производительность",
        "devices": "Устройства",
        "conservation_mode": "Режим сохранения заряда",
        "conservation_description": "Ограничивает максимальный уровень заряда батареи и помогает продлить срок её службы.",
        "usb_charging": "USB-зарядка при выключенном ноутбуке",
        "usb_charging_description": "Подаёт питание на USB-порты, даже когда ноутбук выключен.",
        "fan_mode": "Режим вентилятора",
        "fan_description": "Выберите профиль охлаждения ноутбука.",
        "fan_silent": "Тихий",
        "fan_standard": "Стандартный",
        "fan_dust": "Очистка от пыли",
        "fan_efficient": "Эффективное охлаждение",
        "fn_lock": "Fn Lock",
        "fn_lock_description": "Переключает клавиши F1–F12 в режим стандартных функциональных клавиш.",
        "touchpad": "Сенсорная панель",
        "touchpad_description": "Включает или выключает встроенную сенсорную панель.",
        "camera": "Камера",
        "camera_description": "Включает или выключает встроенную камеру.",
        "microphone": "Микрофон",
        "microphone_description": "Отключает или включает микрофон по умолчанию.",
        "wifi": "Wi-Fi",
        "wifi_description": "Включает или выключает беспроводную сеть.",
        "no_controls": "Поддерживаемые настройки оборудования не найдены",
        "no_controls_description": "Это устройство не предоставляет настройки Lenovo Vantage.",
        "setting_error": "Не удалось изменить настройку.",
        "enabled": "Включено",
        "disabled": "Выключено",
    },
}


def active_language():
    language = os.environ.get("LANGUAGE", "").split(":")[0].lower()
    if not language:
        language = QLocale.system().name().lower()
    return "ru" if language.startswith("ru") else "en"


LANGUAGE = active_language()


def tr(key):
    return TRANSLATIONS[LANGUAGE].get(key, TRANSLATIONS["en"].get(key, key))


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


class VantageWindow(QMainWindow):
    CATEGORIES = ("power", "performance", "devices")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lenovo Vantage")
        self.setMinimumSize(900, 560)
        self.resize(1180, 760)
        self.rows = []
        self.form_row = 0
        self.section_headings = set()

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addStretch(1)

        page = QWidget()
        page.setMaximumWidth(2250)
        page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content = QVBoxLayout(page)
        content.setContentsMargins(28, 22, 28, 20)
        content.setSpacing(16)
        root.addWidget(page, 0)
        root.addStretch(1)
        self.setCentralWidget(central)

        header = QVBoxLayout()
        header.setSpacing(3)
        title = QLabel("Lenovo Vantage")
        title_font = title.font()
        title_font.setPointSizeF(title_font.pointSizeF() * 1.4)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        subtitle = QLabel(tr("subtitle"))
        header.addWidget(title)
        header.addWidget(subtitle)
        content.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(14)
        self.scroll.setWidget(body)
        content.addWidget(self.scroll, 1)

        self.form_layout = QGridLayout()
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setHorizontalSpacing(36)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.setColumnMinimumWidth(0, 0)
        self.form_layout.setColumnStretch(0, 1)
        self.form_layout.setColumnStretch(1, 2)
        self.body_layout.addLayout(self.form_layout)

        self.populate()
        self.body_layout.addStretch(1)

        escape = QAction(self)
        escape.setShortcut(Qt.Key.Key_Escape)
        escape.triggered.connect(self.close)
        self.addAction(escape)

    def add_row(self, category, title, description, control):
        if category not in self.section_headings:
            if self.section_headings:
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setFrameShadow(QFrame.Shadow.Sunken)
                self.form_layout.addWidget(separator, self.form_row, 0, 1, 2)
                self.form_row += 1

            section_heading = QLabel(tr(category))
            section_font = section_heading.font()
            section_font.setWeight(QFont.Weight.DemiBold)
            section_heading.setFont(section_font)
            section_heading.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            section_heading.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
            self.form_layout.addWidget(section_heading, self.form_row, 0)
            self.form_layout.setRowMinimumHeight(self.form_row, 32)
            self.section_headings.add(category)
            self.form_row += 1

        label = QLabel(f"{title}:")
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        label.setContentsMargins(0, 4, 0, 0)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        field = QWidget()
        field_layout = QVBoxLayout(field)
        field_layout.setContentsMargins(0, 4, 0, 4)
        field_layout.setSpacing(4)
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        field_layout.addWidget(control, 0, Qt.AlignmentFlag.AlignLeft)
        field_layout.addWidget(description_label)
        self.form_layout.addWidget(label, self.form_row, 0)
        self.form_layout.addWidget(field, self.form_row, 1)
        self.form_row += 1
        self.rows.append(category)
        return label

    def add_checkbox(self, category, title_key, description_key, get_fn, set_fn):
        title = tr(title_key)
        choices = QWidget()
        choices_layout = QVBoxLayout(choices)
        choices_layout.setContentsMargins(0, 0, 0, 0)
        choices_layout.setSpacing(2)
        group = QButtonGroup(choices)
        group.setExclusive(True)
        enabled = QCheckBox(tr("enabled"))
        disabled = QCheckBox(tr("disabled"))
        current = bool(get_fn())
        enabled.setChecked(current)
        disabled.setChecked(not current)
        group.addButton(enabled)
        group.addButton(disabled)
        choices_layout.addWidget(enabled)
        choices_layout.addWidget(disabled)
        row = self.add_row(category, title, tr(description_key), choices)

        def changed(active, desired):
            if not active:
                return
            ok, err = set_fn(desired)
            if not ok:
                current_state = bool(get_fn())
                enabled.blockSignals(True)
                disabled.blockSignals(True)
                enabled.setChecked(current_state)
                disabled.setChecked(not current_state)
                enabled.blockSignals(False)
                disabled.blockSignals(False)
                self.show_error(title, err)

        enabled.toggled.connect(lambda active: changed(active, True))
        disabled.toggled.connect(lambda active: changed(active, False))
        return row

    def add_fan_mode(self):
        title = tr("fan_mode")
        options = QWidget()
        options_layout = QVBoxLayout(options)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(2)
        group = QButtonGroup(options)
        buttons = {}
        current = get_fan_mode()
        for label_key, key in FAN_MODES:
            button = QRadioButton(tr(label_key))
            button.setChecked(key == current)
            group.addButton(button)
            options_layout.addWidget(button)
            buttons[key] = button
        self.add_row("performance", title, tr("fan_description"), options)

        def changed(key):
            def on_toggled(active):
                if not active:
                    return
                ok, err = set_fan_mode(key)
                if not ok:
                    selected_key = get_fan_mode()
                    for radio in buttons.values():
                        radio.blockSignals(True)
                    buttons[selected_key].setChecked(True)
                    for radio in buttons.values():
                        radio.blockSignals(False)
                    self.show_error("Fan mode", err)
            return on_toggled

        for _, key in FAN_MODES:
            buttons[key].toggled.connect(changed(key))

    def show_error(self, title, message):
        self.statusBar().showMessage(f"{title}: {message or tr('setting_error')}", 8000)

    def populate(self):
        if vpc_path("conservation_mode"):
            self.add_checkbox("power", "conservation_mode", "conservation_description", get_conservation_mode, set_conservation_mode)
        if vpc_path("usb_charging"):
            self.add_checkbox("power", "usb_charging", "usb_charging_description", get_usb_charging, set_usb_charging)

        if vpc_path("fan_mode"):
            self.add_fan_mode()
        if vpc_path("fn_lock"):
            self.add_checkbox("performance", "fn_lock", "fn_lock_description", get_fn_lock, set_fn_lock)

        touchpad = get_touchpad()
        if touchpad:
            self.add_checkbox("devices", "touchpad", "touchpad_description", lambda: get_touchpad_active(touchpad), lambda active: set_touchpad_active(touchpad, active))
        if sh("modinfo", "-n", "uvcvideo")[0] == 0:
            self.add_checkbox("devices", "camera", "camera_description", get_camera, set_camera)
        if which("pactl"):
            self.add_checkbox("devices", "microphone", "microphone_description", get_mic_active, set_mic_active)
        if which("nmcli"):
            self.add_checkbox("devices", "wifi", "wifi_description", get_wifi_active, set_wifi_active)

        if not self.rows:
            empty = QWidget()
            empty_layout = QVBoxLayout(empty)
            empty_layout.addStretch(1)
            icon = QLabel()
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QIcon.fromTheme("dialog-information").pixmap(48, 48)
            if not pixmap.isNull():
                icon.setPixmap(pixmap)
                empty_layout.addWidget(icon)
            empty_title = QLabel(tr("no_controls"))
            empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_font = empty_title.font()
            title_font.setWeight(QFont.Weight.DemiBold)
            empty_title.setFont(title_font)
            empty_layout.addWidget(empty_title)
            empty_description = QLabel(tr("no_controls_description"))
            empty_description.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_description.setWordWrap(True)
            empty_layout.addWidget(empty_description)
            empty_layout.addStretch(1)
            self.body_layout.addWidget(empty, 1)


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
