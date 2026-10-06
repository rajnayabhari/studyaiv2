import cv2
import sys

def check_camera(url):
    print(f"Connecting to camera: {url}")
    cap = cv2.VideoCapture(url)
    
    if not cap.isOpened():
        print(f"Failed to open camera: {url}")
        sys.exit(1)
        
    ret, frame = cap.read()
    if not ret:
        print("Failed to grab a frame from the camera.")
        sys.exit(1)
        
    h, w = frame.shape[:2]
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Success! Resolution: {w}x{h}, FPS: {fps}")
    print("Press 'q' to exit the preview window (if running with GUI).")
    
    # Just grab 5 frames and exit to avoid GUI dependencies holding it open in testing
    for _ in range(5):
        ret, frame = cap.read()
        if not ret:
            break
            
    cap.release()
    print("Camera check passed.")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        check_camera(sys.argv[1])
    else:
        print("Usage: python check_camera.py <camera_url_or_index>")
        # Default test fallback
        check_camera(0)
