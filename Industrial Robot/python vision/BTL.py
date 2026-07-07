import socket
import threading
import time

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

# ================== CẤU HÌNH ==================
USE_TEST_IMAGE = True
IMG_PATH = "pic.png"
CAM_INDEX = 1

BELT_WIDTH_MM     = 300.0       # bề rộng băng tải thật (mm)
IGNORE_MIDDLE_MM  = 200.0       # bỏ vùng giữa để tránh cạnh box
IGNORE_LEFT_RATIO = 0.10        # bỏ ~10% bên trái (tường đen)
XLEFT_OFFSET_PX   = 0           # nếu muốn bù thêm mép trái thì set khác 0

HOST = "127.0.0.1"              # IP ABB Socket
PORT = 11000                    # Port ABB Socket

DRAW_COLOR = (0, 255, 255)      # vàng tươi


# ================== VISION FUNCTION ==================

def find_horizontal_belt_edges(edges):
    """Tìm y_top, y_bot của băng tải bằng histogram theo Y (trên ROI)."""
    h, w = edges.shape
    hist_y = edges.sum(axis=1).astype(np.float32)

    if hist_y.max() <= 0:
        return None, None

    peaks = np.where(hist_y > 0.3 * hist_y.max())[0]
    if len(peaks) == 0:
        return None, None

    clusters = []
    cur = [peaks[0]]
    for p in peaks[1:]:
        if p - cur[-1] <= 8:
            cur.append(p)
        else:
            clusters.append(cur)
            cur = [p]
    clusters.append(cur)

    centers = sorted(int(np.mean(c)) for c in clusters)

    best_pair = None
    best_gap = -1
    for i in range(len(centers)):
        for j in range(i + 1, len(centers)):
            gap = abs(centers[j] - centers[i])
            if gap > best_gap:
                best_gap = gap
                best_pair = (centers[i], centers[j])

    if best_pair is None:
        return None, None

    y_top, y_bot = sorted(best_pair)
    return y_top, y_bot


def find_left_edge(edges, y_top, y_bot, mm_per_px,
                   ignore_left_ratio=IGNORE_LEFT_RATIO,
                   ignore_middle_mm=IGNORE_MIDDLE_MM):
    """
    Tìm mép TRÁI băng bằng Sobel X + histogram theo X.
    Có fallback nếu mask xoá hết biên.
    """
    h, w = edges.shape

    yc = int((y_top + y_bot) / 2)
    band_half = int(0.15 * (y_bot - y_top))
    y1 = max(0, yc - band_half)
    y2 = min(h - 1, yc + band_half)
    band = edges[y1:y2, :]

    sobelx = cv2.Sobel(band, cv2.CV_32F, 1, 0, ksize=3)
    abs_sobelx = np.abs(sobelx)
    hist_x = abs_sobelx.sum(axis=0)

    ignore_left_px = int(ignore_left_ratio * w)
    hist_x[:ignore_left_px] = 0

    if ignore_middle_mm > 0:
        half_win_px = int((ignore_middle_mm / 2.0) / mm_per_px)
        cx = w // 2
        x1m = max(cx - half_win_px, 0)
        x2m = min(cx + half_win_px, w - 1)
        hist_x[x1m:x2m + 1] = 0

    # fallback: nếu bị xoá sạch
    if hist_x.max() <= 0:
        hist_x = abs_sobelx.sum(axis=0)
        hist_x[: int(0.05 * w)] = 0

    if hist_x.max() <= 0:
        return None

    peaks = np.where(hist_x > 0.3 * hist_x.max())[0]
    if len(peaks) == 0:
        return None

    clusters = []
    cur = [peaks[0]]
    for p in peaks[1:]:
        if p - cur[-1] <= 4:
            cur.append(p)
        else:
            clusters.append(cur)
            cur = [p]
    clusters.append(cur)

    left_cluster = min(clusters, key=lambda c: min(c))
    return int(min(left_cluster))


def find_box_on_belt(edges_half, y_top, y_bot):
    """
    Tìm hộp nằm trên băng:
      - quét contour toàn nửa trái
      - bỏ đường dài, contour nhỏ, contour ngoài dải băng
      - chọn contour có area_box/ratio lớn nhất.
    """
    h, w = edges_half.shape
    contours, _ = cv2.findContours(edges_half, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_score = 0.0

    for c in contours:
        if len(c) < 5:
            continue

        (bx, by), (rw, rh), raw_angle = cv2.minAreaRect(c)
        if rw < 1 or rh < 1:
            continue

        area_box = rw * rh
        ratio = max(rw, rh) / (min(rw, rh) + 1e-6)

        if by <= y_top + 5 or by >= y_bot - 5:
            continue
        if ratio > 6.0:
            continue
        if area_box < 300:
            continue

        score = area_box / ratio
        if score > best_score:
            best_score = score
            best = (bx, by, rw, rh, raw_angle, c)

    return best


def analyze_image(frame):
    """
    Xử lý 1 frame:
      - CẮT ROI nửa trái
      - tìm băng tải (y_top, y_bot) -> mm/px
      - tìm mép trái bằng Sobel X
      - đoạn đỏ = giao đường đỏ với 2 đường xanh (y_top, y_bot)
      - trả về (ảnh ROI vẽ, DX_mm, DY_mm, angle_robot_deg)
    """
    h, w = frame.shape[:2]
    w2 = w // 2

    roi = frame[:, :w2].copy()

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    roi_edges = cv2.Canny(blur, 50, 150)

    # 1) băng tải
    y_top, y_bot = find_horizontal_belt_edges(roi_edges)
    print("[DEBUG] y_top, y_bot =", y_top, y_bot)
    if y_top is None:
        print("[VISION] Không tìm được băng tải (ROI).")
        return roi, None, None, None

    belt_height_px = float(abs(y_bot - y_top))
    if belt_height_px <= 1:
        print("[VISION] belt_height_px quá nhỏ.")
        return roi, None, None, None

    mm_per_px = BELT_WIDTH_MM / belt_height_px
    print(f"[DEBUG] belt_height_px={belt_height_px:.1f}, mm_per_px={mm_per_px:.3f}")

    # 2 đường xanh (cùng màu DRAW_COLOR)
    cv2.line(roi, (0, y_top), (w2, y_top), DRAW_COLOR, 2)
    cv2.line(roi, (0, y_bot), (w2, y_bot), DRAW_COLOR, 2)

    y_mid = int(0.5 * (y_top + y_bot))

    # 2) mép trái
    x_left = find_left_edge(roi_edges, y_top, y_bot, mm_per_px)
    if x_left is None:
        print("[VISION] Không tìm được mép trái.")
        return roi, None, None, None

    x_left = int(x_left + XLEFT_OFFSET_PX)

    top_red = (x_left, y_top)
    bot_red = (x_left, y_bot)
    mid_red = (x_left, y_mid)

    # ĐOẠN ĐỎ nhưng cũng dùng DRAW_COLOR
    cv2.line(roi, top_red, bot_red, DRAW_COLOR, 3)
    cv2.circle(roi, top_red, 5, DRAW_COLOR, -1)
    cv2.circle(roi, bot_red, 5, DRAW_COLOR, -1)
    cv2.circle(roi, mid_red, 5, DRAW_COLOR, -1)

    # 3) hộp trên băng
    box = find_box_on_belt(roi_edges, y_top, y_bot)
    print("[DEBUG] box =", box[:5] if box is not None else None)
    if box is None:
        print("[VISION] Không tìm được hộp.")
        return roi, None, None, None

    bx, by, bw, bh, raw_angle, contour = box

    rect = cv2.boxPoints(((bx, by), (bw, bh), raw_angle))
    rect = np.intp(rect)
    cv2.drawContours(roi, [rect], 0, DRAW_COLOR, 2)
    cv2.circle(roi, (int(bx), int(by)), 4, DRAW_COLOR, -1)

    # 4) góc hộp
    angle = raw_angle
    if bw < bh:
        angle += 90
    while angle > 90:
        angle -= 180
    while angle < -90:
        angle += 180
    angle_robot = angle

    # 5) DX / DY
    dx_px = bx - x_left
    dy_px = by - y_mid

    X_mm = dx_px * mm_per_px - 40
    Y_mm = dy_px * mm_per_px

    print(f"[RESULT] X={X_mm:.1f} mm, Y={Y_mm:.1f} mm,"
          f" angle_img={angle:.1f} deg, angle_robot={angle_robot:.1f} deg")

    # vẽ DX/DY – cũng cùng màu
    proj = (x_left, int(by))                # chân vuông góc từ tâm hộp xuống đoạn đỏ
    cv2.line(roi, proj, (int(bx), int(by)), DRAW_COLOR, 3)   # DX
    cv2.circle(roi, proj, 4, DRAW_COLOR, -1)
    cv2.line(roi, mid_red, proj, DRAW_COLOR, 3)              # DY

    cv2.putText(roi, "DX", ((proj[0] + int(bx)) // 2, proj[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, DRAW_COLOR, 2)
    cv2.putText(roi, "DY", (mid_red[0] + 5, (mid_red[1] + proj[1]) // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, DRAW_COLOR, 2)

    text = f"X={X_mm:.1f}mm  Y={Y_mm:.1f}mm  th={angle_robot:.1f}deg"
    cv2.putText(roi, text, (20, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, DRAW_COLOR, 2)

    # Trả về CHỈ nửa trái (roi đã vẽ)
    return roi, X_mm, Y_mm, angle_robot


def capture_frame():
    """Lấy 1 frame: từ ảnh test hoặc camera."""
    if USE_TEST_IMAGE:
        img = cv2.imread(IMG_PATH)
        if img is None:
            print("[ERR] Không đọc được ảnh", IMG_PATH)
        else:
            print("[VISION] Đọc ảnh OK:", IMG_PATH, "shape =", img.shape)
        return img
    else:
        cap = cv2.VideoCapture(CAM_INDEX)
        if not cap.isOpened():
            print("[ERR] Không mở được camera", CAM_INDEX)
            return None
        ret, frame = cap.read()
        cap.release()
        if not ret:
            print("[ERR] Không capture được frame từ camera")
            return None
        print("[VISION] Capture frame từ camera OK, shape =", frame.shape)
        return frame


# ================== UI + SOCKET CLIENT ==================

class VisionClientUI:
    def __init__(self, master):
        self.master = master
        self.master.title("ABB Vision Client")

        self.sock = None
        self.running = False

        self.last_frame = None   # chỉ giữ ảnh ROI
        self.photo = None

        self.var_status = tk.StringVar(value="Chưa kết nối ABB")
        self.var_x = tk.StringVar(value="X: --- mm")
        self.var_y = tk.StringVar(value="Y: --- mm")
        self.var_ang = tk.StringVar(value="Góc: --- deg")

        self.build_ui()
        self.update_image_loop()

    def build_ui(self):
        top = ttk.Frame(self.master)
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        ttk.Label(top, textvariable=self.var_status).pack(side=tk.LEFT, padx=5)

        btn_connect = ttk.Button(top, text="Kết nối ABB", command=self.start_client_thread)
        btn_connect.pack(side=tk.RIGHT, padx=5)

        info = ttk.Frame(self.master)
        info.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        ttk.Label(info, textvariable=self.var_x).grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Label(info, textvariable=self.var_y).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(info, textvariable=self.var_ang).grid(row=0, column=2, padx=5, pady=2, sticky="w")

        log_frame = ttk.LabelFrame(self.master, text="Log từ ABB")
        log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=10, pady=5)

        self.txt_log = tk.Text(log_frame, height=8, wrap="word")
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.txt_log.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.configure(yscrollcommand=scroll.set)

        frame_img = ttk.Frame(self.master, borderwidth=1, relief=tk.SUNKEN)
        frame_img.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)

        # CHỈ MỘT ẢNH: ROI nửa trái
        self.lbl_img = ttk.Label(frame_img, text="Result (half-left)")
        self.lbl_img.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def log(self, text):
        print(text)
        self.txt_log.insert(tk.END, text + "\n")
        self.txt_log.see(tk.END)

    def start_client_thread(self):
        if self.running:
            messagebox.showinfo("Thông báo", "Client đã chạy rồi.")
            return
        t = threading.Thread(target=self.client_loop, daemon=True)
        t.start()
        self.running = True

    def client_loop(self):
        self.var_status.set(f"Đang kết nối {HOST}:{PORT} ...")
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((HOST, PORT))
            self.var_status.set(f"Đã kết nối ABB {HOST}:{PORT}")
            self.log(f"[INFO] Connected to ABB {HOST}:{PORT}")
        except OSError as e:
            self.var_status.set("Kết nối ABB thất bại")
            messagebox.showerror("Lỗi kết nối", str(e))
            self.running = False
            return

        buffer = ""

        try:
            while True:
                data = self.sock.recv(1024)
                if not data:
                    self.var_status.set("ABB đã đóng kết nối")
                    self.log("[INFO] ABB closed connection.")
                    break

                text = data.decode("utf-8", errors="ignore")
                buffer += text

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    msg = line.strip()
                    if not msg:
                        continue
                    self.handle_message(msg)

        except OSError as e:
            self.var_status.set("Mất kết nối ABB")
            self.log(f"[ERR] Socket error: {e}")
        finally:
            if self.sock is not None:
                try:
                    self.sock.close()
                except:
                    pass
            self.sock = None
            self.running = False
            self.log("[INFO] Client loop ended")

    def handle_message(self, msg: str):
        self.log(f"[ABB] >> {repr(msg)}")

        if msg.startswith("LOG:"):
            log_text = msg[4:]
            self.var_status.set(log_text)

        elif msg == "CAPTURE":
            self.var_status.set("Nhận CAPTURE – đang xử lý ảnh...")
            self.log("[VISION] Bắt đầu xử lý CAPTURE")

            frame = capture_frame()
            if frame is None:
                self.log("[VISION] frame = None (không đọc được ảnh/camera)")
                dx = dy = ang = 0.0
            else:
                self.log(f"[VISION] frame shape = {frame.shape}")
                res, X_mm, Y_mm, angle = analyze_image(frame)
                # res đã là ROI nửa trái
                self.last_frame = cv2.cvtColor(res, cv2.COLOR_BGR2RGB)
                self.log("[VISION] Đã gán last_frame")

                if X_mm is None:
                    dx = dy = ang = 0.0
                    self.log("[VISION] Không tìm được hộp, gửi 0,0,0")
                else:
                    dx = X_mm
                    dy = Y_mm
                    ang = angle
                    self.var_x.set(f"X: {dx:.1f} mm")
                    self.var_y.set(f"Y: {dy:.1f} mm")
                    self.var_ang.set(f"Góc: {ang:.1f} deg")
                    self.log(f"[VISION] Kết quả: X={dx:.1f}, Y={dy:.1f}, ang={ang:.1f}")

            for line in (f"DX:{dx}", f"DY:{dy}", f"ANG:{ang}"):
                out = (line + "\n").encode("utf-8")
                self.log(f"[PC] << {line}")
                self.sock.sendall(out)
                time.sleep(0.02)

            self.var_status.set("Đã gửi DX/DY/ANG cho ABB")

        elif msg == "QUIT":
            self.var_status.set("Nhận QUIT từ ABB")
            self.log("[INFO] Received QUIT from ABB.")

        else:
            self.log(f"[INFO] Lệnh khác từ ABB: {msg}")

    def update_image_loop(self):
        try:
            if self.last_frame is not None:
                # Giữ đúng tỉ lệ ảnh ROI khi resize
                h, w, _ = self.last_frame.shape
                max_w, max_h = 640, 480   # kích thước tối đa muốn hiển thị

                scale = min(max_w / w, max_h / h)  # tỉ lệ thu phóng
                new_w = int(w * scale)
                new_h = int(h * scale)

                img = Image.fromarray(self.last_frame)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                self.photo = ImageTk.PhotoImage(img)
                self.lbl_img.configure(image=self.photo)
                self.lbl_img.image = self.photo
        except Exception as e:
            print("[UI] Lỗi khi cập nhật ảnh:", e)

        self.master.after(50, self.update_image_loop)



def main():
    root = tk.Tk()
    app = VisionClientUI(root)
    root.geometry("350x650")
    root.mainloop()


if __name__ == "__main__":
    main()
