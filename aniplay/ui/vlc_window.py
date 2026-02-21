import os
import vlc
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QFrame, QComboBox
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QWheelEvent
from ..utils.format_utils import format_time
from ..utils.media_matcher import MediaMatcher
from ..config import PREFERRED_AUDIO, PREFERRED_SUBTITLE
from ..utils.logger import get_logger

logger = get_logger(__name__)

class VlcPlayerWindow(QMainWindow):
    # Signals for communication with PlayerWidget
    progress_updated = pyqtSignal(float, float) # current, total
    playback_paused = pyqtSignal(float) # current time
    playback_resumed = pyqtSignal()
    playback_finished = pyqtSignal()
    window_closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AniPlay - VLC Player")
        self.resize(1280, 720)

        # Stability flags for Windows/AMD
        args = [
            "--no-video-title-show",
            "--quiet",
            "--no-stats"
        ]
        
        self.instance = vlc.Instance(*args)
        self.player = self.instance.media_player_new()
        
        # Track fullscreen state
        self.is_fullscreen = False
        
        self.setup_ui()
        self._setup_events()

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Video Surface
        self.video_container = QWidget()
        self.video_container.setStyleSheet("background-color: black;")
        
        # OSD Label (child of video_container)
        self.osd_label = QLabel(self.video_container)
        self.osd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.osd_label.hide()
        self.osd_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 0.6);
                border-radius: 40px;
                font-size: 32px;
                padding: 20px 40px;
                font-weight: bold;
            }
        """)
        
        # Controls Overlay (Bottom)
        self.controls_bar = QFrame()
        self.controls_bar.setFixedHeight(100)
        self.controls_bar.setStyleSheet("background-color: #1a1a1a;")

        self.controls_layout = QVBoxLayout(self.controls_bar)
        self.controls_layout.setContentsMargins(15, 10, 15, 10)
        self.controls_layout.setSpacing(5)
        
        # Seek Bar
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        
        # Buttons and Time
        self.btns_layout = QHBoxLayout()
        self.btns_layout.setSpacing(10)
        
        self.play_pause_btn = QPushButton("⏸️")
        self.play_pause_btn.setMinimumSize(40, 40)
        self.play_pause_btn.clicked.connect(self.toggle_pause)
        
        # Back 10s
        self.skip_back_btn = QPushButton("⏪")
        self.skip_back_btn.setToolTip("Skip Back 10s")
        self.skip_back_btn.setMinimumSize(40, 40)
        self.skip_back_btn.clicked.connect(lambda: self._seek_relative(-10000))

        # Forward 10s
        self.skip_fwd_btn = QPushButton("⏩")
        self.skip_fwd_btn.setToolTip("Skip Forward 10s")
        self.skip_fwd_btn.setMinimumSize(40, 40)
        self.skip_fwd_btn.clicked.connect(lambda: self._seek_relative(10000))
        
        # Next Episode
        self.next_episode_btn = QPushButton("🎬⏭")
        self.next_episode_btn.setToolTip("Next Episode")
        self.next_episode_btn.setMinimumSize(40, 40)
        self.next_episode_btn.clicked.connect(self.playback_finished.emit)
        
        self.volume_btn = QPushButton("🔊")
        self.volume_btn.setMinimumSize(40, 40)
        self.volume_btn.clicked.connect(self.toggle_mute)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        
        # Skip Intro (The specialized one)
        self.skip_intro_btn = QPushButton("⏭️+85")
        self.skip_intro_btn.setToolTip("Skip Intro (85s)")
        self.skip_intro_btn.setMinimumSize(50, 40)
        self.skip_intro_btn.setStyleSheet("font-weight: bold; color: #2196f3;") 
        self.skip_intro_btn.clicked.connect(lambda: self._seek_relative(85000))
        
        # Audio & Subtitle Selectors
        self.audio_selector = QComboBox()
        self.audio_selector.setMinimumWidth(200)
        self.audio_selector.currentIndexChanged.connect(self._on_audio_changed)
        
        self.subtitle_selector = QComboBox()
        self.subtitle_selector.setMinimumWidth(200)
        self.subtitle_selector.currentIndexChanged.connect(self._on_subtitle_changed)
        
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("font-family: 'Consolas';")
        
        self.btns_layout.addWidget(self.play_pause_btn)
        self.btns_layout.addWidget(self.skip_back_btn)
        self.btns_layout.addWidget(self.skip_fwd_btn)
        self.btns_layout.addWidget(self.next_episode_btn)
        self.btns_layout.addWidget(self.skip_intro_btn)
        self.btns_layout.addSpacing(15)
        self.btns_layout.addWidget(self.volume_btn)
        self.btns_layout.addWidget(self.volume_slider)
        self.btns_layout.addStretch()
        self.btns_layout.addWidget(QLabel("🔊"))
        self.btns_layout.addWidget(self.audio_selector)
        self.btns_layout.addSpacing(5)
        self.btns_layout.addWidget(QLabel("💬"))
        self.btns_layout.addWidget(self.subtitle_selector)
        self.btns_layout.addSpacing(10)
        self.btns_layout.addWidget(self.time_label)
        
        self.controls_layout.addWidget(self.seek_slider)
        self.controls_layout.addLayout(self.btns_layout)

        self.layout.addWidget(self.video_container, 1)
        self.layout.addWidget(self.controls_bar)
        
        self._tracks_populated = False
        self._preferences_applied = False
        self.is_muted = False
        self._last_volume = 100
        
        # Enable mouse tracking for fullscreen controls
        self.setMouseTracking(True)
        self.video_container.setMouseTracking(True)
        
        self.audio_selector.installEventFilter(self)
        self.subtitle_selector.installEventFilter(self)
        self.play_pause_btn.installEventFilter(self)
        self.seek_slider.installEventFilter(self)
        self.volume_slider.installEventFilter(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._center_osd()

    def _center_osd(self):
        if hasattr(self, 'osd_label') and self.osd_label:
            self.osd_label.adjustSize()
            x = (self.video_container.width() - self.osd_label.width()) // 2
            y = (self.video_container.height() - self.osd_label.height()) // 2
            self.osd_label.move(x, y)

    def toggle_fullscreen(self):
        """Toggle fullscreen mode with proper controls hiding"""
        if self.is_fullscreen:
            self.showNormal()
            self.controls_bar.show()
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.controls_hide_timer.stop()
            self.is_fullscreen = False
        else:
            self.showFullScreen()
            # IMMEDATELY hide controls to prevent layout flicker
            self.controls_bar.hide()
            self.setCursor(Qt.CursorShape.BlankCursor)
            self.is_fullscreen = True
            self.controls_hide_timer.start(3000) 

    def _setup_events(self):
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_progress)
        self.poll_timer.setInterval(500)
        
        # Timer to auto-hide controls in fullscreen
        self.controls_hide_timer = QTimer(self)
        self.controls_hide_timer.setSingleShot(True)
        self.controls_hide_timer.timeout.connect(self._hide_controls_in_fullscreen)
        
    def _hide_controls_in_fullscreen(self):
        """Hide controls when in fullscreen mode after timeout"""
        if self.is_fullscreen:
            self.controls_bar.hide()
            self.setCursor(Qt.CursorShape.BlankCursor)
    
    def mouseMoveEvent(self, event):
        """Show controls temporarily when mouse moves in fullscreen"""
        if self.is_fullscreen:
            self.controls_bar.show()
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.controls_hide_timer.start(3000)
        super().mouseMoveEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta > 0:
            self._set_volume(min(100, self.player.audio_get_volume() + 5))
        else:
            self._set_volume(max(0, self.player.audio_get_volume() - 5))
        super().wheelEvent(event)

    def _set_volume(self, volume):
        self.player.audio_set_volume(volume)
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(volume)
        self.volume_slider.blockSignals(False)
        self._update_volume_icon(volume)
        self.show_osd(f"Volume: {volume}%")

    def _update_volume_icon(self, volume):
        if volume == 0 or self.is_muted:
            self.volume_btn.setText("🔇")
        elif volume < 33:
            self.volume_btn.setText("🔈")
        elif volume < 66:
            self.volume_btn.setText("🔉")
        else:
            self.volume_btn.setText("🔊")

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.is_muted:
            self._last_volume = self.player.audio_get_volume()
            self.player.audio_set_volume(0)
            self.volume_slider.setEnabled(False)
            self.show_osd("Muted")
        else:
            self.player.audio_set_volume(self._last_volume)
            self.volume_slider.setEnabled(True)
            self.show_osd(f"Volume: {self._last_volume}%")
        self._update_volume_icon(0 if self.is_muted else self.player.audio_get_volume())

    def _on_volume_changed(self, value):
        self.player.audio_set_volume(value)
        self._update_volume_icon(value)
        self.show_osd(f"Volume: {value}%")

    def show_osd(self, text, duration=2000):
        self.osd_label.setText(text)
        self._center_osd()
        self.osd_label.show()
        self.osd_label.raise_()
        QTimer.singleShot(duration, self.osd_label.hide)

    def _seek_relative(self, ms):
        if not self.player.is_seekable():
            return
        new_time = max(0, min(self.player.get_length(), self.player.get_time() + ms))
        self.player.set_time(new_time)
        icon = "⏩" if ms > 0 else "⏪"
        self.show_osd(f"{icon} {abs(ms)//1000}s")

    def play_path(self, path, start_time=0):
        media = self.instance.media_new(path)
        self.player.set_media(media)
        self.player.play()
        
        self._tracks_populated = False
        self._preferences_applied = False
        
        if start_time > 0:
            # Wait a bit longer for media to be ready to seek
            QTimer.singleShot(1000, lambda: self.player.set_time(int(start_time * 1000)))
            
        self.poll_timer.start()

    def _update_tracks_ui(self):
        if self._tracks_populated:
            return
            
        # Check if playback has actually started
        if self.player.get_state() not in [vlc.State.Playing, vlc.State.Paused]:
            return
            
        # Audio Tracks
        self.audio_selector.blockSignals(True)
        self.audio_selector.clear()
        current_audio = self.player.audio_get_track()
        
        audio_tracks = self.player.audio_get_track_description()
        if audio_tracks:
            for track_id, description in audio_tracks:
                desc = description.decode('utf-8') if isinstance(description, bytes) else description
                self.audio_selector.addItem(desc, track_id)
                if track_id == current_audio:
                    self.audio_selector.setCurrentIndex(self.audio_selector.count() - 1)
        self.audio_selector.blockSignals(False)
        
        # Subtitle Tracks
        self.subtitle_selector.blockSignals(True)
        self.subtitle_selector.clear()
        current_sub = self.player.video_get_spu()
        
        sub_tracks = self.player.video_get_spu_description()
        if sub_tracks:
            for track_id, description in sub_tracks:
                desc = description.decode('utf-8') if isinstance(description, bytes) else description
                self.subtitle_selector.addItem(desc, track_id)
                if track_id == current_sub:
                    self.subtitle_selector.setCurrentIndex(self.subtitle_selector.count() - 1)
        self.subtitle_selector.blockSignals(False)
        
        # Only mark as populated if we actually found more than the "Disable" track
        if self.audio_selector.count() > 1 or self.subtitle_selector.count() > 1:
            self._tracks_populated = True
            
        # Apply preferences if not yet done
        if self._tracks_populated and not self._preferences_applied:
            self._apply_preferences(audio_tracks, sub_tracks)
            self._preferences_applied = True

    def _apply_preferences(self, audio_tracks, sub_tracks):
        """Automatically switch to preferred audio and subtitle tracks."""
        if audio_tracks:
            vlc_audio = [{"id": t[0], "name": t[1].decode('utf-8') if isinstance(t[1], bytes) else t[1]} for t in audio_tracks]
            best_audio = MediaMatcher.get_best_track(vlc_audio, PREFERRED_AUDIO, is_subtitle=False)
            if best_audio is not None and best_audio != self.player.audio_get_track():
                logger.info(f"Auto-selecting audio track ID: {best_audio}")
                self.player.audio_set_track(best_audio)
                # Update UI selector
                for i in range(self.audio_selector.count()):
                    if self.audio_selector.itemData(i) == best_audio:
                        self.audio_selector.blockSignals(True)
                        self.audio_selector.setCurrentIndex(i)
                        self.audio_selector.blockSignals(False)
                        break

        if sub_tracks:
            vlc_subs = [{"id": t[0], "name": t[1].decode('utf-8') if isinstance(t[1], bytes) else t[1]} for t in sub_tracks]
            best_sub = MediaMatcher.get_best_track(vlc_subs, PREFERRED_SUBTITLE, is_subtitle=True)
            if best_sub is not None and best_sub != self.player.video_get_spu():
                logger.info(f"Auto-selecting subtitle track ID: {best_sub}")
                self.player.video_set_spu(best_sub)
                # Update UI selector
                for i in range(self.subtitle_selector.count()):
                    if self.subtitle_selector.itemData(i) == best_sub:
                        self.subtitle_selector.blockSignals(True)
                        self.subtitle_selector.setCurrentIndex(i)
                        self.subtitle_selector.blockSignals(False)
                        break

    def _on_audio_changed(self, index):
        track_id = self.audio_selector.itemData(index)
        if track_id is not None:
            self.player.audio_set_track(track_id)

    def _on_subtitle_changed(self, index):
        track_id = self.subtitle_selector.itemData(index)
        if track_id is not None:
            self.player.video_set_spu(track_id)

    def toggle_pause(self):
        # In VLC, is_playing() returns True if it's currently playing
        # We check state BEFORE toggling to determine what to set
        if self.player.is_playing():
            self.player.set_pause(1)
            self.play_pause_btn.setText("▶️")
            self.playback_paused.emit(self.player.get_time() / 1000.0)
        else:
            self.player.set_pause(0)
            self.play_pause_btn.setText("⏸️")
            self.playback_resumed.emit()

    def _on_seek_released(self):
        if not self.player.is_seekable():
            return
            
        value = self.seek_slider.value()
        self.player.set_position(value / 1000.0)

    def _poll_progress(self):
        if not self.player: 
            return
        
        # Periodically refresh tracks until they are found
        if not self._tracks_populated:
            self._update_tracks_ui()
            
        length = self.player.get_length()
        time = self.player.get_time()
        
        if length > 0:
            percentage = int((time / length) * 1000)
            if not self.seek_slider.isSliderDown():
                self.seek_slider.setValue(percentage)
            
            self.progress_updated.emit(time / 1000.0, length / 1000.0)
            
            cur = self._format_time(time / 1000.0)
            tot = self._format_time(length / 1000.0)
            self.time_label.setText(f"{cur} / {tot}")

        state = self.player.get_state()
        if state in [vlc.State.Ended, vlc.State.Error]:
            self.playback_finished.emit()
            self.close()

    def _format_time(self, seconds: float) -> str:
        return format_time(seconds)

    def keyPressEvent(self, event):
        key = event.key()
        handled = True
        
        if key == Qt.Key.Key_Space or key == Qt.Key.Key_K:
            self.toggle_pause()
        elif key == Qt.Key.Key_F or key == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        elif key == Qt.Key.Key_M:
            self.toggle_mute()
        elif key == Qt.Key.Key_Escape:
            if self.is_fullscreen:
                self.toggle_fullscreen()
            else:
                self.close()
        elif key == Qt.Key.Key_Left or key == Qt.Key.Key_J:
            self._seek_relative(-10000)
        elif key == Qt.Key.Key_Right or key == Qt.Key.Key_L:
            self._seek_relative(10000)
        elif key >= Qt.Key.Key_0 and key <= Qt.Key.Key_9:
            percent = (key - Qt.Key.Key_0) / 10.0
            self.player.set_position(percent)
            self.show_osd(f"Seek: {int(percent*100)}%")
        elif key == Qt.Key.Key_BracketLeft:
            rate = max(0.25, self.player.get_rate() - 0.1)
            self.player.set_rate(rate)
            self.show_osd(f"Speed: {rate:.1f}x")
        elif key == Qt.Key.Key_BracketRight:
            rate = min(4.0, self.player.get_rate() + 0.1)
            self.player.set_rate(rate)
            self.show_osd(f"Speed: {rate:.1f}x")
        elif key == Qt.Key.Key_S:
            self._seek_relative(85000)
            self.show_osd("Skipped 85s")
        else:
            handled = False
            super().keyPressEvent(event)
            
        if handled:
            event.accept()
    
    def eventFilter(self, obj, event):
        """Filter keyboard events from combo boxes to handle global shortcuts"""
        if event.type() == event.Type.KeyPress:
            # Handle global shortcuts even when combo boxes have focus
            key = event.key()
            if key in [Qt.Key.Key_Space, Qt.Key.Key_K, Qt.Key.Key_F, Qt.Key.Key_F11, 
                       Qt.Key.Key_M, Qt.Key.Key_Escape, Qt.Key.Key_Left, Qt.Key.Key_J, 
                       Qt.Key.Key_Right, Qt.Key.Key_L, Qt.Key.Key_BracketLeft, Qt.Key.Key_BracketRight, Qt.Key.Key_S] or \
               (key >= Qt.Key.Key_0 and key <= Qt.Key.Key_9):
                self.keyPressEvent(event)
                return True  # Event handled
        
        # Pass other events to the parent class
        return super().eventFilter(obj, event)
    
    def mouseDoubleClickEvent(self, event):
        """Double-click to toggle fullscreen"""
        self.toggle_fullscreen()
        super().mouseDoubleClickEvent(event)

    def showEvent(self, event):
        # Embed VLC in our QWidget after it's shown
        if not self.player.get_hwnd() and not self.player.get_xwindow():
            if os.name == 'nt':
                self.player.set_hwnd(int(self.video_container.winId()))
            else:
                self.player.set_xwindow(int(self.video_container.winId()))
        super().showEvent(event)

    def closeEvent(self, event):
        # Stop polling immediately to prevent further UI updates
        if hasattr(self, 'poll_timer'):
            self.poll_timer.stop()
        
        # Detach VLC from the window handle before it's destroyed.
        # This is critical on Windows to prevent deadlocks when closing
        # via the standard window controls (the "X" button).
        if hasattr(self, 'player') and self.player:
            try:
                if os.name == 'nt':
                    self.player.set_hwnd(0)
                else:
                    self.player.set_xwindow(0)
                
                # Stop synchronously, but detached from the GUI handle
                self.player.stop()
            except Exception:
                pass
        
        # Signal that we are closing
        self.window_closed.emit()
        event.accept()
