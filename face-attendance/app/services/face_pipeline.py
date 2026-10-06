import os
import cv2
import numpy as np
import insightface
import onnxruntime as ort
import logging

logger = logging.getLogger(__name__)

class FacePipeline:
    _instance = None

    def __new__(cls, config=None):
        if cls._instance is None:
            cls._instance = super(FacePipeline, cls).__new__(cls)
            cls._instance._initialize(config)
        return cls._instance

    def _initialize(self, config):
        if not config:
            # Fallback for simple scripts
            pack_name = os.environ.get('FACE_MODEL_PACK', 'buffalo_l')
            det_size = int(os.environ.get('DET_SIZE', 640))
        else:
            pack_name = config.get('FACE_MODEL_PACK', 'buffalo_l')
            det_size = int(config.get('DET_SIZE', 640))

        self.det_size = (det_size, det_size)
        
        # Check providers
        providers = ort.get_available_providers()
        if 'CUDAExecutionProvider' in providers:
            self.providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            logger.info("FacePipeline initialized with CUDA Execution Provider (GPU).")
            print("FacePipeline initialized with CUDA Execution Provider (GPU).")
        else:
            self.providers = ['CPUExecutionProvider']
            logger.info("FacePipeline initialized with CPU Execution Provider.")
            print("FacePipeline initialized with CPU Execution Provider.")
            # If fallback to CPU is forced, you might want to switch to buffalo_s
            # but we'll stick to config unless it's too slow.
            
        self.app = insightface.app.FaceAnalysis(name=pack_name, providers=self.providers)
        self.app.prepare(ctx_id=0, det_size=self.det_size, det_thresh=0.6)

    def process_frame(self, img_bgr):
        """
        Process a BGR image and return a list of faces.
        Each face is an insightface Face object with:
        .bbox, .kps, .embedding, .det_score
        """
        if img_bgr is None:
            return []
        faces = self.app.get(img_bgr)
        return faces

    def get_largest_face(self, faces):
        if not faces:
            return None
        return max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))

# Helper to get the singleton instance
def get_pipeline(config=None):
    return FacePipeline(config)
