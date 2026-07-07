import tkinter as tk
from tkinter import ttk
from scara import Scara
import math
import threading
import time

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D

robot = Scara()

class RobotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SCARA Robot GUI")

        left_frame = ttk.Frame(root)
        left_frame.grid(row=0, column=0, sticky="n", padx=10, pady=10)

        # btn_frame = ttk.Frame(root)
        # btn_frame.grid(row=0, column=1, sticky="n", padx=10, pady=30)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.grid(row=2, column=0, sticky="n", padx=10, pady=10)

        right_frame = ttk.Frame(root)
        right_frame.grid(row=0, column=2, sticky="n", padx=10, pady=10)

        self.canvas = tk.Canvas(left_frame, width=400, height=400, bg='white')
        self.canvas.grid(row=0, column=0)


        self.label = ttk.Label(left_frame, text="Đang lấy dữ liệu...", font=("Arial", 12, "bold"))
        self.label.grid(row=1, column=0,pady=20)

        ttk.Button(btn_frame, text="Nhập 1 điểm", command=self.input_single_point, width=20).grid(row=1, column=0, pady=5)
        ttk.Button(btn_frame, text="Nhập nhiều điểm", command=self.input_multiple_points, width=20).grid(row=2, column=0, pady=5)
        ttk.Button(btn_frame, text="Gắp vật", command=self.pick_place, width=20).grid(row=3, column=0, pady=5)

        # Vẽ robot 3D
        self.figure = Figure(figsize=(6, 6), dpi=100)
        self.ax3d = self.figure.add_subplot(111, projection='3d')
        self.canvas3d = FigureCanvasTkAgg(self.figure, master=right_frame)
        self.canvas3d.get_tk_widget().grid(row=0, column=0, padx=10)

        self.update_view()

    def input_single_point(self):
        win = tk.Toplevel(self.root)
        win.title("Nhập tọa độ")

        labels = ['X:', 'Y:', 'Z:', 'Góckẹp:', 'Kẹp:']
        entries = []

        for i, label in enumerate(labels):
            ttk.Label(win, text=label).grid(row=i, column=0)
            entry = ttk.Entry(win)
            entry.grid(row=i, column=1)
            entries.append(entry)

        def submit():
            try:
                x, y, z, a, b = map(float, [e.get() for e in entries])
                robot.to_pos(x, y, int(z), int(a), int(b))
                win.destroy()
            except:
                print("Lỗi nhập.")

        ttk.Button(win, text="Gửi", command=submit).grid(row=5, columnspan=2, pady=5)

    def input_multiple_points(self):
        win = tk.Toplevel(self.root)
        win.title("Nhập nhiều điểm")

        ttk.Label(win, text="Mỗi dòng 1 điểm: X Y Z Góckẹp Kẹp").pack()
        text_box = tk.Text(win, width=40, height=10)
        text_box.pack()

        def submit_multiple():
            def run_sequence():
                lines = text_box.get("1.0", "end").strip().split('\n')
                for line in lines:
                    try:
                        parts = list(map(float, line.strip().split()))
                        if len(parts) != 5:
                            print("Sai định dạng:", line)
                            continue
                        x, y, z, a, b = parts
                        robot.to_pos(x, y, int(z), int(a), int(b))

                        # Cập nhật view sau mỗi điểm
                        self.update_view()

                        # Delay giữa các điểm
                        time.sleep(0.3)

                    except Exception as e:
                        print(f"Lỗi dòng '{line}': {e}")

                win.destroy()

            # Chạy trong luồng riêng
            threading.Thread(target=run_sequence, daemon=True).start()

        ttk.Button(win, text="Gửi tất cả", command=submit_multiple).pack(pady=5)

    def pick_place(self):
        win = tk.Toplevel(self.root)
        win.title("Gắp và thả")

        ttk.Label(win, text="Điểm gắp (x y z góc mở_kẹp):").pack()
        pick_entry = ttk.Entry(win)
        pick_entry.pack()

        ttk.Label(win, text="Điểm thả (x y z góc):").pack()
        place_entry = ttk.Entry(win)
        place_entry.pack()

        def run_pick_and_place():
            try:
                px, py, pz, pick_angle, grip_open = map(float, pick_entry.get().split())
                tx, ty, tz, place_angle = map(float, place_entry.get().split())

                # Gọi pick_and_place trong luồng riêng
                robot.pick_and_place(
                    pick_pos=(px, py, pz),
                    pick_angle=pick_angle,
                    grip_open=grip_open,
                    place_pos=(tx, ty, tz),
                    place_angle=place_angle
                )
            except Exception as e:
                print("Lỗi gắp/thả:", e)
            finally:
                win.destroy()

        def submit():
            threading.Thread(target=run_pick_and_place, daemon=True).start()

        ttk.Button(win, text="Thực hiện", command=submit).pack(pady=5)

    def update_view(self):
        result = robot.get_angles()
        if result and len(result) >= 5:
            angle1, angle2, grip_angle, z, grip = result
            theta1 = angle1 - 150
            theta2 = 100 - angle2
            z = (z-90)/4

            _, _, (x, y) = robot.forward_kinematics(theta1, theta2)

            self.label.config(
                text=(
                    f"Góc: θ1={theta1:.2f}, θ2={theta2:.2f}, Kẹp={grip:.1f}\n"
                    f"Vị trí: x={x:.1f}, y={y:.1f}, Z={z:.1f}"
                )
            )


            self.draw_robot(theta1, theta2)
            self.draw_robot_3d(theta1, theta2, z, grip_angle, grip)
        else:
            self.label.config(text="Không đọc được góc.")

        self.root.after(500, self.update_view)

    def draw_workspace(self):
        a1 = 80
        a2 = 70
        min_radius = abs(a1 - a2)
        max_radius = a1 + a2
        mid_radius = math.sqrt(a1**2 + a2**2)

        def to_canvas(x, y):
            return 200 + x, 200 - y

        def draw_arc(radius, cx, cy, color, start=270, extent=180):
            x1, y1 = to_canvas(cx - radius, cy - radius)
            x2, y2 = to_canvas(cx + radius, cy + radius)
            self.canvas.create_arc(x1, y1, x2, y2,
                                   start=start, extent=extent,
                                   style=tk.ARC, outline=color, width=2)

        draw_arc(max_radius, 0, 0, "lightgray", start=270, extent=180)
        draw_arc(mid_radius, 0, 0, "lightgray", start=230, extent=260)
        draw_arc(a2, 0, a1, "lightgray", start=180, extent=-90)
        draw_arc(a2, 0, -a1, "lightgray", start=180, extent=90)

    def draw_robot(self, theta1, theta2):
        self.canvas.delete("all")
        origin, joint, end = robot.forward_kinematics(theta1, theta2)

        def to_canvas(x, y):
            return 200 + x, 200 - y

        x0, y0 = to_canvas(*origin)
        x1, y1 = to_canvas(*joint)
        x2, y2 = to_canvas(*end)

        for i in range(-160, 161, 20):
            cx1, cy1 = to_canvas(i, -160)
            cx2, cy2 = to_canvas(i, 160)
            self.canvas.create_line(cx1, cy1, cx2, cy2, fill="#eee")
            self.canvas.create_text(cx1, 200 + 5, text=str(i), anchor="n", fill="gray")

        for j in range(-160, 161, 20):
            cx1, cy1 = to_canvas(-160, j)
            cx2, cy2 = to_canvas(160, j)
            self.canvas.create_line(cx1, cy1, cx2, cy2, fill="#eee")
            self.canvas.create_text(200 + 5, cy1, text=str(j), anchor="w", fill="gray")

        self.canvas.create_line(0, 200, 400, 200, fill="black")
        self.canvas.create_line(200, 0, 200, 400, fill="black")
        self.canvas.create_text(390, 190, text="X", font=("Arial", 10, "bold"))
        self.canvas.create_text(210, 10, text="Y", font=("Arial", 10, "bold"))

        self.draw_workspace()

        self.canvas.create_line(x0, y0, x1, y1, width=5, fill='red')
        self.canvas.create_line(x1, y1, x2, y2, width=5, fill='grey')
        self.canvas.create_oval(x0-5, y0-5, x0+5, y0+5, fill="black")
        self.canvas.create_oval(x1-5, y1-5, x1+5, y1+5, fill="black")
        self.canvas.create_oval(x2-5, y2-5, x2+5, y2+5, fill="blue")

    def draw_robot_3d(self, theta1, theta2, z, grip_angle, grip):
        self.ax3d.clear()

        # Kích thước cánh tay
        a1, a2 = 80, 70

        # Chuyển góc về radian
        theta1_rad = math.radians(theta1)
        theta2_rad = math.radians(theta2)
        grip_rad = math.radians(grip_angle)

        # Base đến shoulder cố định theo trục Z
        base = (0, 0, 0)
        shoulder = (0, 0, 100)

        # Tính tọa độ elbow trên mặt phẳng XY, Z vẫn là 100
        x1 = a1 * math.cos(theta1_rad)
        y1 = a1 * math.sin(theta1_rad)
        elbow = (x1, y1, shoulder[2])

        # Tọa độ end effector cố định tại Z=100
        x2 = x1 + a2 * math.cos(theta1_rad + theta2_rad)
        y2 = y1 + a2 * math.sin(theta1_rad + theta2_rad)
        end_eff = (x2, y2, 100)

        # Điểm gắn gripper tịnh tiến theo z
        grip_base = (x2, y2, z)

        # Vẽ các đoạn tay robot
        self.ax3d.plot([base[0], shoulder[0]], [base[1], shoulder[1]], [base[2], shoulder[2]], 'blue', linewidth=6, label='Base')
        self.ax3d.plot([shoulder[0], elbow[0]], [shoulder[1], elbow[1]], [shoulder[2], elbow[2]], 'red', linewidth=4, label='Shoulder')
        self.ax3d.plot([elbow[0], end_eff[0]], [elbow[1], end_eff[1]], [elbow[2], end_eff[2]], 'gray', linewidth=4, label='Elbow')

        # Vẽ đoạn khớp từ end_eff đến gripper (theo Z)
        self.ax3d.plot(
            [end_eff[0], grip_base[0]],
            [end_eff[1], grip_base[1]],
            [end_eff[2], grip_base[2]],
            'black', linewidth=3, label='Vertical Link'
        )

        # Tính toán vị trí 2 ngón gripper
        dx = (grip / 2) * math.cos(grip_rad)
        dy = (grip / 2) * math.sin(grip_rad)

        g1 = (grip_base[0] + dx, grip_base[1] + dy, grip_base[2])
        g2 = (grip_base[0] - dx, grip_base[1] - dy, grip_base[2])

        self.ax3d.plot([grip_base[0], g1[0]], [grip_base[1], g1[1]], [grip_base[2], g1[2]], 'green', linewidth=1)
        self.ax3d.plot([grip_base[0], g2[0]], [grip_base[1], g2[1]], [grip_base[2], g2[2]], 'green', linewidth=1)

        # Các điểm đánh dấu
        for point, color, size in [(base, 'k', 30), (shoulder, 'k', 20), (elbow, 'k', 20), (end_eff, 'gray', 20), (grip_base, 'b', 40)]:
            self.ax3d.scatter(*point, c=color, s=size)

        # Cài đặt trục và tiêu đề
        self.ax3d.set_xlim(-200, 200)
        self.ax3d.set_ylim(-200, 200)
        self.ax3d.set_zlim(0, 250)
        self.ax3d.set_xlabel('X')
        self.ax3d.set_ylabel('Y')
        self.ax3d.set_zlabel('Z')
        self.ax3d.set_title("Robot 3D View")
        self.ax3d.legend()
        self.canvas3d.draw()

