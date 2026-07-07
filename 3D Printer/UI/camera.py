import cv2
import numpy as np
from PIL import Image, ImageTk

class CameraManager:
    def __init__(self, camera_index=0):
        self.cap = cv2.VideoCapture(camera_index)
        
        # ==========================================
        # CẤU HÌNH AI YOLOv4-TINY
        # ==========================================
        self.NAMES = "obj.names"
        self.CFG = "custom-yolov4-tiny-detector.cfg"
        self.WEIGHTS = "custom-yolov4-tiny-detector_best.weights"
        self.CONF_THRES = 0.4
        self.NMS_THRES = 0.5
        
        try:
            with open(self.NAMES, "r") as f:
                self.class_names = [c.strip() for c in f.readlines() if c.strip()]
            
            self.net = cv2.dnn.readNetFromDarknet(self.CFG, self.WEIGHTS)
            
            # Bật CUDA nếu máy bạn có GPU NVIDIA hỗ trợ
            # self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            # self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
            
            self.output_names = self.net.getUnconnectedOutLayersNames()
            self.ai_enabled = True
        except Exception as e:
            print(f"Lỗi tải AI Model: {e}")
            self.ai_enabled = False

    def get_frame(self, width=420, height=240):
        if not (self.cap and self.cap.isOpened()):
            return None, []

        ret, frame = self.cap.read()
        if not ret:
            return None, []

        detected_labels = []

        # ==========================================
        # XỬ LÝ NHẬN DIỆN AI
        # ==========================================
        if self.ai_enabled:
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (320, 320), swapRB=True, crop=False)
            self.net.setInput(blob)
            outputs = self.net.forward(self.output_names)

            boxes, confidences, class_ids = [], [], []

            for output in outputs:
                for det in output:
                    scores = det[5:]
                    class_id = int(np.argmax(scores))
                    conf = float(scores[class_id])

                    if conf > self.CONF_THRES:
                        cx, cy, bw, bh = det[:4] * np.array([w, h, w, h])
                        x = int(cx - bw / 2)
                        y = int(cy - bh / 2)

                        boxes.append([x, y, int(bw), int(bh)])
                        confidences.append(conf)
                        class_ids.append(class_id)

            indices = cv2.dnn.NMSBoxes(boxes, confidences, self.CONF_THRES, self.NMS_THRES)

            if len(indices) > 0:
                for i in np.array(indices).flatten():
                    x, y, bw, bh = boxes[i]
                    label = self.class_names[class_ids[i]]
                    conf = confidences[i]
                    
                    # Thêm nhãn vào danh sách trả về
                    detected_labels.append(label)

                    # Vẽ khung AI lên hình
                    cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
                    cv2.putText(frame, f"{label} {conf:.2f}", (x, max(30, y - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # Chuyển đổi định dạng cho Tkinter
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (width, height))
        img_tk = ImageTk.PhotoImage(image=Image.fromarray(frame))
        
        return img_tk, detected_labels

    def release(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()