import cv2
import threading
import time
import logging

logger = logging.getLogger(__name__)

class CameraService:
    def __init__(self, url):
        self.url = url
        if str(url).isdigit():
            self.url = int(url)
        self.cap = None
        self.latest_frame = None
        self.running = False
        self.lock = threading.Lock()
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def _update(self):
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                logger.info(f"Connecting to camera: {self.url}")
                self.cap = cv2.VideoCapture(self.url)
                if not self.cap.isOpened():
                    logger.warning(f"Failed to open camera: {self.url}. Retrying in 5s.")
                    time.sleep(5)
                    continue
            
            ret, frame = self.cap.read()
            if not ret:
                logger.warning(f"Failed to read frame from {self.url}. Reconnecting...")
                self.cap.release()
                continue
                
            with self.lock:
                self.latest_frame = frame
                
    def get_frame(self):
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            return None

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()

# Global registry of cameras by classroom_id
_cameras = {}

def get_camera_service(classroom_id, url):
    if classroom_id not in _cameras:
        cam = CameraService(url)
        cam.start()
        _cameras[classroom_id] = cam
    return _cameras[classroom_id]
