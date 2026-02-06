import os
import vlc
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QFrame, QComboBox
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

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
        
        # Controls Overlay (Bottom)
        self.controls_bar = QFrame()
        self.controls_bar.setFixedHeight(80)

        
        self.controls_layout = QVBoxLayout(self.controls_bar)
        
        # Seek Bar
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        
        # Buttons and Time
        self.btns_layout = QHBoxLayout()
        self.play_pause_btn = QPushButton("⏸")
        self.play_pause_btn.clicked.connect(self.toggle_pause)
        
        # Audio & Subtitle Selectors
        self.audio_selector = QComboBox()
        self.audio_selector.setMinimumWidth(150)
        self.audio_selector.currentIndexChanged.connect(self._on_audio_changed)
        
        self.subtitle_selector = QComboBox()
        self.subtitle_selector.setMinimumWidth(150)
        self.subtitle_selector.currentIndexChanged.connect(self._on_subtitle_changed)
        
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("font-family: 'Consolas';")
        
        self.btns_layout.addWidget(self.play_pause_btn)
        self.btns_layout.addStretch()
        self.btns_layout.addWidget(QLabel("🔊"))
        self.btns_layout.addWidget(self.audio_selector)
        self.btns_layout.addWidget(QLabel("💬"))
        self.btns_layout.addWidget(self.subtitle_selector)
        self.btns_layout.addWidget(self.time_label)
        
        self.controls_layout.addWidget(self.seek_slider)
        self.controls_layout.addLayout(self.btns_layout)

        self.layout.addWidget(self.video_container, 1)
        self.layout.addWidget(self.controls_bar)
        
        self._tracks_populated = False
        
        # Enable mouse tracking for fullscreen controls
        self.setMouseTracking(True)
        self.video_container.setMouseTracking(True)
        
        self.audio_selector.installEventFilter(self)
        self.subtitle_selector.installEventFilter(self)
        self.play_pause_btn.installEventFilter(self)
        self.seek_slider.installEventFilter(self)
        
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
            self.controls_bar.hide()
            self.controls_hide_timer.start(3000)  # Start auto-hide timer
            self.is_fullscreen = True

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
            # Restart the hide timer
            self.controls_hide_timer.start(3000)  # Hide after 3 seconds
        super().mouseMoveEvent(event)

    def play_path(self, path, start_time=0):
        media = self.instance.media_new(path)
        self.player.set_media(media)
        self.player.play()
        
        self._tracks_populated = False
        
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
            self.play_pause_btn.setText("▶")
            self.playback_paused.emit(self.player.get_time() / 1000.0)
        else:
            self.player.set_pause(0)
            self.play_pause_btn.setText("⏸")
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
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0: 
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.toggle_pause()
        elif event.key() == Qt.Key.Key_F or event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Escape:
            if self.is_fullscreen:
                self.toggle_fullscreen()
            else:
                self.close()
        elif event.key() == Qt.Key.Key_Left:
            self.player.set_time(max(0, self.player.get_time() - 10000))
        elif event.key() == Qt.Key.Key_Right:
            self.player.set_time(min(self.player.get_length(), self.player.get_time() + 10000))
        super().keyPressEvent(event)
    
    def eventFilter(self, obj, event):
        """Filter keyboard events from combo boxes to handle global shortcuts"""
        if event.type() == event.Type.KeyPress:
            # Handle global shortcuts even when combo boxes have focus
            if event.key() == Qt.Key.Key_Space:
                self.toggle_pause()
                return True  # Event handled
            elif event.key() == Qt.Key.Key_F or event.key() == Qt.Key.Key_F11:
                self.toggle_fullscreen()
                return True
            elif event.key() == Qt.Key.Key_Escape:
                if self.is_fullscreen:
                    self.toggle_fullscreen()
                else:
                    self.close()
                return True
            elif event.key() == Qt.Key.Key_Left:
                self.player.set_time(max(0, self.player.get_time() - 10000))
                return True
            elif event.key() == Qt.Key.Key_Right:
                self.player.set_time(min(self.player.get_length(), self.player.get_time() + 10000))
                return True
        
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
        self.poll_timer.stop()
        self.player.stop()
        self.window_closed.emit()
        event.accept()
