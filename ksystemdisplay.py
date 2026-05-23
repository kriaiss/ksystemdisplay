import psutil
import platform
import AppKit
import traceback
import objc
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QFrame, QApplication, QProgressBar)
from PyQt6.QtCore import (Qt, QPoint, QPropertyAnimation, QEasingCurve, 
                             QParallelAnimationGroup, QTimer)
from PyQt6.QtGui import QAction
from AppKit import (NSUserDefaults, NSEvent, NSKeyDownMask, 
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorStationary,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindow)

def get_ksys_theme(is_dark):
    bg = "rgba(25, 25, 25, 180)" if is_dark else "rgba(240, 240, 240, 180)"
    text = "#ffffff" if is_dark else "#000000"
    subtext = "rgba(255, 255, 255, 140)" if is_dark else "rgba(0, 0, 0, 140)"
    border = "rgba(255, 255, 255, 25)" if is_dark else "rgba(0, 0, 0, 25)"
    
    return f"""
    QFrame#MainContainer {{
        background: {bg};
        border-radius: 20px;
        border: 1px solid {border};
    }}
    QLabel {{ font-family: 'Menlo'; }}
    QLabel#Title {{ color: {subtext}; font-size: 10px; font-weight: bold; text-transform: uppercase; }}
    QLabel#Value {{ color: {text}; font-size: 12px; font-weight: bold; }}
    QLabel#Info {{ color: {subtext}; font-size: 9px; }}
    QProgressBar {{
        border: none;
        background-color: rgba(128, 128, 128, 30);
        height: 4px;
        border-radius: 2px;
    }}
    QProgressBar::chunk {{ background-color: #007AFF; border-radius: 2px; }}
    """

class StatRow(QWidget):
    def __init__(self, title):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        header = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("Title")
        self.val_label = QLabel("0%")
        self.val_label.setObjectName("Value")
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.val_label)
        
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.info_label = QLabel("")
        self.info_label.setObjectName("Info")
        
        layout.addLayout(header)
        layout.addWidget(self.bar)
        layout.addWidget(self.info_label)

class KSysWindow(QWidget):
    def __init__(self, ktools):
        super().__init__()
        self.ktools = ktools

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.setFixedSize(220, 180)
        self.end_pos = QPoint(20, 50)
        self.start_pos = QPoint(-250, 50)
        
        self.move(self.start_pos)
        self.setWindowOpacity(0.0)

        self.root = QFrame(self)
        self.root.setObjectName("MainContainer")
        self.root.setFixedSize(220, 180)
        
        layout = QVBoxLayout(self.root)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        try:
            sys_ver = platform.mac_ver()[0]
            cpu_name = platform.processor() or "Apple Silicon"
            info_text = f"macOS {sys_ver}\n{cpu_name}"
        except:
            info_text = "System Monitor"

        self.sys_label = QLabel(info_text)
        self.sys_label.setObjectName("Info")
        self.sys_label.setStyleSheet("font-weight: bold; font-size: 10px;")
        layout.addWidget(self.sys_label)

        self.cpu_stat = StatRow("CPU")
        self.ram_stat = StatRow("RAM")
        
        layout.addWidget(self.cpu_stat)
        layout.addWidget(self.ram_stat)

        self.anim_group = QParallelAnimationGroup()
        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        
        for a in [self.pos_anim, self.opacity_anim]:
            a.setDuration(400)
            a.setEasingCurve(QEasingCurve.Type.OutQuint)
            self.anim_group.addAnimation(a)
            
        self.is_hiding = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_stats)
        self.timer.start(2000)
        self.update_theme()

    def showEvent(self, event):
        try:
            from AppKit import NSApp, NSStatusWindowLevel, NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorStationary, NSWindowCollectionBehaviorIgnoresCycle
            
            QTimer.singleShot(100, self._apply_native_flags)
            
            print("ksystemdisplay: showEvent triggered")
        except Exception as e:
            print(f"ksystemdisplay error in showEvent: {e}")
        super().showEvent(event)

    def _apply_native_flags(self):
        try:
            from AppKit import NSApp, NSStatusWindowLevel
            for window in NSApp.windows():
                if window.isVisible() and window.frame().size.width == self.width():
                    window.setLevel_(NSStatusWindowLevel + 1)
                    
                    window.setHidesOnDeactivate_(False)
                    
                    window.setIgnoresMouseEvents_(True)
                    
                    behavior = (NSWindowCollectionBehaviorCanJoinAllSpaces | 
                                NSWindowCollectionBehaviorStationary | 
                                NSWindowCollectionBehaviorIgnoresCycle)
                    window.setCollectionBehavior_(behavior)
                    
                    print(f"ksystemdisplay: native flags n level applied to window: {window}")
                    break
        except Exception as e:
            print(f"ksystemdisplay: failed to apply native flags: {e}")

    def refresh_stats(self):
        if not self.isVisible() or self.windowOpacity() < 0.05:
            return

        try:
            cpu_p = psutil.cpu_percent()
            self.cpu_stat.val_label.setText(f"{int(cpu_p)}%")
            self.cpu_stat.bar.setValue(int(cpu_p))

            try:
                import time
                boot_time = psutil.boot_time()
                uptime_seconds = time.time() - boot_time
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                if hours > 24:
                    days = hours // 24
                    self.cpu_stat.info_label.setText(f"Uptime: {days}d {hours%24}h {minutes}m")
                else:
                    self.cpu_stat.info_label.setText(f"Uptime: {hours}h {minutes}m")
            except:
                self.cpu_stat.info_label.setText("Uptime: N/A")

            ram = psutil.virtual_memory()
            used_gb = ram.used / (1024**3)
            total_gb = ram.total / (1024**3)

            display_percent = (used_gb / total_gb) * 100
            
            self.ram_stat.val_label.setText(f"{display_percent:.1f}%")
            self.ram_stat.bar.setValue(int(display_percent))
            self.ram_stat.info_label.setText(f"Used: {used_gb:.1f}GB / {total_gb:.0f}GB")
            
        except Exception as e:
            print(f"ksystemdisplay: stats error: {e}")

    def toggle(self):
        if self.anim_group.state() == QParallelAnimationGroup.State.Running: return
        if not self.isVisible() or self.windowOpacity() < 0.1:
            self.is_hiding = False
            self.update_theme()
            self.show()
            self.raise_()
            self.pos_anim.setStartValue(self.start_pos)
            self.pos_anim.setEndValue(self.end_pos)
            self.opacity_anim.setStartValue(self.windowOpacity())
            self.opacity_anim.setEndValue(1.0)
            self.anim_group.start()
        else:
            self.hide_anim()

    def hide_anim(self):
        self.is_hiding = True
        self.pos_anim.setEndValue(self.start_pos)
        self.opacity_anim.setEndValue(0.0)
        self.anim_group.start()
        QTimer.singleShot(400, self.hide)

    def update_theme(self):
        is_dark = NSUserDefaults.standardUserDefaults().stringForKey_("AppleInterfaceStyle") == "Dark"
        self.setStyleSheet(get_ksys_theme(is_dark))

class Plugin:
    def __init__(self, ktools):
        self.layer = "fixed"
        self.ktools = ktools
        self.name = "ksystemdisplay"
        self.monitor = KSysWindow(self.ktools)
        print(f"ksystemdisplay: created with layer: {self.layer}")
        
        def hotkey_handler(event):
            mask = (1 << 20) | (1 << 19)
            if event.keyCode() == 42 and (event.modifierFlags() & mask) == mask:
                QTimer.singleShot(0, self.monitor.toggle)
                return None
            return event
            
        self.global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSKeyDownMask, hotkey_handler)
        self.local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(NSKeyDownMask, hotkey_handler)
        
        self.action = QAction("open ksystemdisplay (⌥⌘\\)", self.ktools.menu)
        self.action.triggered.connect(self.monitor.toggle)
        
        QTimer.singleShot(1000, self.monitor.toggle)

    def unload(self):
        if self.monitor and hasattr(self.monitor, 'timer'):
            self.monitor.timer.stop()

        try:
            if hasattr(self, 'global_monitor') and self.global_monitor:
                AppKit.NSEvent.removeMonitor_(self.global_monitor)
                self.global_monitor = None
            if hasattr(self, 'local_monitor') and self.local_monitor:
                AppKit.NSEvent.removeMonitor_(self.local_monitor)
                self.local_monitor = None
        except: pass

        try:
            self.action.triggered.disconnect()
        except: pass

        if self.monitor:
            if hasattr(self.monitor, 'anim_group'):
                self.monitor.anim_group.stop()
            self.monitor.close()
            self.monitor.deleteLater()
            self.monitor = None

        import gc
        gc.collect()

        print("ksys: monitors and timers stopped")

    def update_theme(self):
        self.monitor.update_theme()

    def get_actions(self):
        return [self.action]