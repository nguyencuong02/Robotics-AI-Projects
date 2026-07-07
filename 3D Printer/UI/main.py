import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import cv2
from PIL import Image, ImageTk
from datetime import datetime
import numpy as np
from collections import deque
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import time

# Import cấu hình và module kết nối
from config import *
from network import PrinterNetwork
from camera import CameraManager

class MainsailTkinterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MÁY IN 3D - UI")
        
        apply_theme() # Áp dụng theme từ file config
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"{screen_width}x{screen_height}+0+0")
        try:
            self.root.after(0, lambda: self.root.state('zoomed'))
        except tk.TclError:
            pass 
            
        self.root.configure(fg_color=BG_COLOR)
        
        self.ip_var = ctk.StringVar(value="192.168.100.195")
        self.is_connected = False
        
        # Khởi tạo Network Manager (Tách biệt logic mạng)
        self.network = PrinterNetwork(
            gui_callback=self.parse_incoming_data,
            connection_callback=self.update_connection_status,
            log_callback=lambda msg: self.append_log(msg, is_cmd=False)
        )
        
        self.distance_var = ctk.StringVar(value="10")
        self.extrude_len_var = ctk.StringVar(value="10")
        self.extrude_speed_var = ctk.StringVar(value="5")

        self.move_x_var = ctk.StringVar()
        self.move_y_var = ctk.StringVar()
        self.move_z_var = ctk.StringVar()
        
        self.extruder_history = deque([25.0]*40, maxlen=40)
        self.bed_history = deque([25.0]*40, maxlen=40)
        
        self.camera = CameraManager(camera_index=0)

        self.last_ai_alert = 0
        self.last_ai_pause = 0
        
        self.create_layout()
        self.update_webcam_stream()

    def create_layout(self):
        # ==========================================
        # THANH TIÊU ĐỀ & KẾT NỐI (TOP BAR)
        # ==========================================
        top_bar = ctk.CTkFrame(self.root, fg_color=PANEL_COLOR, corner_radius=8, height=60)
        top_bar.pack(side='top', fill='x', padx=15, pady=(15, 5))
        top_bar.pack_propagate(False)
        
        ctk.CTkLabel(top_bar, text="MÁY IN 3D", font=('Segoe UI', 18, 'bold'), text_color=TEXT_GREEN).pack(side='left', padx=20, pady=15)
        ctk.CTkLabel(top_bar, text="Địa chỉ IP Moonraker:", font=('Segoe UI', 12, 'bold'), text_color=TEXT_WHITE).pack(side='left', padx=(20, 5))
        
        self.ent_ip = ctk.CTkEntry(top_bar, textvariable=self.ip_var, width=140, height=30, fg_color=BG_COLOR, border_color="#434c56", corner_radius=6, text_color=TEXT_WHITE)
        self.ent_ip.pack(side='left', padx=5)
        
        self.btn_connect = ctk.CTkButton(top_bar, text="KẾT NỐI", width=90, height=30, fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER,text_color="#212121",  corner_radius=6, command=self.action_connect_printer)
        self.btn_connect.pack(side='left', padx=10)
        
        self.btn_estop = ctk.CTkButton(top_bar, text="DỪNG KHẨN CẤP", width=120, height=34, fg_color=RED_BTN, hover_color=RED_BTN_HOVER, font=('Segoe UI', 12, 'bold'), corner_radius=6, command=self.emergency_stop)
        self.btn_estop.pack(side='right', padx=20)
        
        self.lbl_net_status = ctk.CTkLabel(top_bar, text="Chưa kết nối mạng", text_color=TEXT_GRAY, font=('Segoe UI', 11, 'italic'))
        self.lbl_net_status.pack(side='right', padx=15)

        # ==========================================
        # KHU VỰC CHÍNH (3 CỘT)
        # ==========================================
        main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        main_container.pack(side='bottom', fill='both', expand=True, padx=10, pady=5)

        self.col1 = ctk.CTkFrame(main_container, fg_color="transparent")
        self.col1.pack(side='left', fill='both', expand=True, padx=5)
        self.col2 = ctk.CTkFrame(main_container, fg_color="transparent")
        self.col2.pack(side='left', fill='both', expand=True, padx=5)
        self.col3 = ctk.CTkFrame(main_container, fg_color="transparent")
        self.col3.pack(side='left', fill='both', expand=True, padx=5)

        self.build_camera_panel(self.col1)
        self.build_bed_mesh_panel(self.col1)
        self.build_printing_panel(self.col2)
        self.build_tool_panel(self.col2)
        self.build_thermals_panel(self.col3)
        self.build_console_panel(self.col3)

    # ==========================================
    # CỘT 1: WEBCAM & LƯỚI BÀN NHIỆT
    # ==========================================
    # ==================================================
    # XỬ LÝ ẢNH TỪ WEBCAM VÀ PHẢN HỒI AI
    # ==================================================
    def update_webcam_stream(self):
        canvas_width = self.cam_canvas.winfo_width()
        if canvas_width <= 1:
            canvas_width = 420
            
        # Lấy ảnh và danh sách lỗi từ file camera.py
        img_tk, detected_labels = self.camera.get_frame(width=canvas_width, height=240)
        
        if img_tk:
            self.img_tk = img_tk
            self.cam_canvas.create_image(0, 0, anchor='nw', image=self.img_tk)
            
            # XỬ LÝ KHI CÓ LỖI TỪ AI
            if detected_labels:
                current_time = time.time()
                
                # 1. CẢNH BÁO CHUNG (Cooldown 5 giây)
                if current_time - self.last_ai_alert > 5.0:
                    unique_labels = list(set(detected_labels)) # Xóa các nhãn trùng nhau
                    self.append_log(f"⚠️ AI Cảnh báo: Phát hiện {', '.join(unique_labels)}")
                    self.last_ai_alert = current_time
                
                # 2. XỬ LÝ LỖI NGHIÊM TRỌNG (Spaghetti) -> TẠM DỪNG (Cooldown 15 giây)
                # Đổi các nhãn thành chữ thường để so sánh cho chắc chắn
                lower_labels = [lbl.lower() for lbl in detected_labels] 
                if "spaghetti" in lower_labels:
                    # Chỉ dừng nếu máy đang in và đã qua thời gian cooldown
                    if self.current_print_state == "printing" and (current_time - self.last_ai_pause > 15.0):
                        self.append_log("🚨 AI PHÁT HIỆN SPAGHETTI! TẠM DỪNG MÁY IN...", is_cmd=True)
                        self.send_gcode("PAUSE")
                        self.last_ai_pause = current_time
            
        self.root.after(30, self.update_webcam_stream)

    def build_camera_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=PANEL_COLOR, corner_radius=10)
        panel.pack(fill='x', pady=5)
        
        header = ctk.CTkFrame(panel, fg_color=PANEL_HEADER_COLOR, corner_radius=8)
        header.pack(fill='x', padx=10, pady=(10, 0))
        ctk.CTkLabel(header, text="📷 Camera", font=('Segoe UI', 14, 'bold'), text_color=TEXT_GREEN).pack(side='left', padx=15, pady=8)
        
        self.cam_canvas = tk.Canvas(panel, height=240, bg=BG_COLOR, highlightthickness=0)
        self.cam_canvas.pack(fill='x', padx=15, pady=15)

    def build_bed_mesh_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=PANEL_COLOR, corner_radius=10)
        panel.pack(fill='both', expand=True, pady=5)
        
        header = ctk.CTkFrame(panel, fg_color=PANEL_HEADER_COLOR, corner_radius=8)
        header.pack(fill='x', padx=10, pady=(10,0))
        ctk.CTkLabel(header, text="📐 Lưới bàn nhiệt", font=('Segoe UI', 14, 'bold'), text_color=TEXT_GREEN).pack(side='left', padx=15, pady=8)
        
        self.mesh_fig = Figure(figsize=(4, 3), dpi=100, facecolor=PANEL_COLOR)
        self.mesh_fig.subplots_adjust(left=0, right=1, bottom=0.1, top=0.9)
        self.mesh_ax = self.mesh_fig.add_subplot(111, projection='3d')
        self._apply_3d_theme()

        self.mesh_canvas = FigureCanvasTkAgg(self.mesh_fig, master=panel)
        self.mesh_canvas.get_tk_widget().pack(fill='both', expand=True, padx=15, pady=(5, 10))
        
        controls = ctk.CTkFrame(panel, fg_color="transparent")
        controls.pack(fill='x', padx=15, pady=(0, 15))
        
        ctk.CTkButton(controls, text="ĐO LƯỚI (CALIBRATE)", fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, corner_radius=6, command=lambda: self.send_gcode("BED_MESH_CALIBRATE")).pack(fill='x', pady=3)
        ctk.CTkButton(controls, text="XÓA LƯỚI (CLEAR)", fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, corner_radius=6, command=lambda: self.send_gcode("BED_MESH_CLEAR")).pack(fill='x', pady=3)
        ctk.CTkButton(controls, text="CÂN TRỤC Z", fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, corner_radius=6, command=lambda: self.send_gcode("Z_TILT_ADJUST")).pack(fill='x', pady=3)

    def _apply_3d_theme(self):
        self.mesh_ax.set_facecolor(PANEL_COLOR)
        self.mesh_ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
        self.mesh_ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
        self.mesh_ax.zaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
        for axis in (self.mesh_ax.xaxis, self.mesh_ax.yaxis, self.mesh_ax.zaxis):
            axis._axinfo["grid"]['color'] = (1, 1, 1, 0.1)
            axis.line.set_color((1, 1, 1, 0))
        self.mesh_ax.tick_params(axis='x', colors=TEXT_GRAY, labelsize=7)
        self.mesh_ax.tick_params(axis='y', colors=TEXT_GRAY, labelsize=7)
        self.mesh_ax.tick_params(axis='z', colors=TEXT_GRAY, labelsize=7)

    def draw_bed_mesh(self, matrix):
        self.mesh_ax.clear()
        self._apply_3d_theme()
        if not matrix or len(matrix) == 0 or len(matrix[0]) == 0:
            self.mesh_canvas.draw()
            return
            
        Z = np.array(matrix)
        rows, cols = Z.shape
        X, Y = np.meshgrid(np.linspace(0, 220, cols), np.linspace(0, 220, rows))
        self.mesh_ax.plot_surface(X, Y, Z, cmap='coolwarm', edgecolor='none', alpha=0.9)
        self.mesh_ax.set_xlim([0, 220])
        self.mesh_ax.set_ylim([0, 220])
        self.mesh_ax.view_init(elev=25, azim=-45)
        self.mesh_canvas.draw()

    # ==========================================
    # CỘT 2: TRẠNG THÁI IN & ĐIỀU KHIỂN
    # ==========================================
    def build_printing_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=PANEL_COLOR, corner_radius=10)
        panel.pack(fill='x', pady=5)
        
        header = ctk.CTkFrame(panel, fg_color=PANEL_HEADER_COLOR, corner_radius=8)
        header.pack(fill='x', padx=10, pady=(10, 0))
        ctk.CTkLabel(header, text="🖨️ Trạng thái In", font=('Segoe UI', 14, 'bold'), text_color=TEXT_GREEN).pack(side='left', padx=15, pady=8)
        
        self.print_content = ctk.CTkFrame(panel, fg_color="transparent")
        self.print_content.pack(fill='both', expand=True, padx=15, pady=15)

        self.frame_idle = ctk.CTkFrame(self.print_content, fg_color="transparent")
        ctk.CTkLabel(self.frame_idle, text="Máy in đang rảnh (Standby)", text_color=TEXT_GRAY).pack(pady=10)
        ctk.CTkButton(self.frame_idle, text="TẢI LÊN G-CODE VÀ IN", fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, corner_radius=6, command=self.upload_gcode).pack(pady=5)

        self.frame_active = ctk.CTkFrame(self.print_content, fg_color="transparent")
        btn_frame = ctk.CTkFrame(self.frame_active, fg_color="transparent")
        btn_frame.pack(fill='x', pady=(0, 10))
        ctk.CTkButton(btn_frame, text="TẠM DỪNG", width=90, fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, command=lambda: self.send_gcode("PAUSE")).pack(side='left', padx=(0, 5))
        ctk.CTkButton(btn_frame, text="TIẾP TỤC", width=90, fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, command=lambda: self.send_gcode("RESUME")).pack(side='left', padx=5)
        ctk.CTkButton(btn_frame, text="HỦY IN", width=90, fg_color=RED_BTN, hover_color=RED_BTN_HOVER, command=lambda: self.send_gcode("CANCEL_PRINT")).pack(side='left', padx=5)

        data_frame = ctk.CTkFrame(self.frame_active, fg_color="transparent")
        data_frame.pack(fill='both', expand=True)

        self.prog_canvas = tk.Canvas(data_frame, width=90, height=90, bg=PANEL_COLOR, highlightthickness=0)
        self.prog_canvas.pack(side='left', padx=(0, 15))
        self.prog_canvas.create_oval(5, 5, 85, 85, outline="#2d343c", width=6)
        self.prog_arc = self.prog_canvas.create_arc(5, 5, 85, 85, start=90, extent=0, outline=TEXT_GREEN, width=6, style=tk.ARC)
        self.prog_text = self.prog_canvas.create_text(45, 45, text="0%", fill=TEXT_GREEN, font=('Segoe UI', 13, 'bold'))

        info_frame = ctk.CTkFrame(data_frame, fg_color="transparent")
        info_frame.pack(side='left', fill='both', expand=True)
        self.lbl_print_file = ctk.CTkLabel(info_frame, text="File: ---", font=('Segoe UI', 12, 'bold'), text_color=TEXT_WHITE, anchor="w", justify="left")
        self.lbl_print_file.pack(fill='x')
        self.lbl_print_time = ctk.CTkLabel(info_frame, text="Thời gian: 00:00:00 / 00:00:00", text_color=TEXT_GRAY, anchor="w")
        self.lbl_print_time.pack(fill='x')
        self.lbl_print_filament = ctk.CTkLabel(info_frame, text="Nhựa dùng: 0.0 m", text_color=TEXT_GRAY, anchor="w")
        self.lbl_print_filament.pack(fill='x')

        self.current_print_state = ""
        self.frame_idle.pack(fill='both', expand=True)

    def build_tool_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=PANEL_COLOR, corner_radius=10)
        panel.pack(fill='both', expand=True, pady=5)
        
        header = ctk.CTkFrame(panel, fg_color=PANEL_HEADER_COLOR, corner_radius=8)
        header.pack(fill='x', padx=10, pady=(10, 0))
        ctk.CTkLabel(header, text="🔧 Điều khiển", font=('Segoe UI', 14, 'bold'), text_color=TEXT_GREEN).pack(side='left', padx=15, pady=8)
        ctk.CTkButton(header, text="MOTORS OFF", width=80, height=26, fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, command=lambda: self.send_gcode("M84")).pack(side='right', padx=15)
        
        ctk.CTkLabel(panel, text="1. Di chuyển trục (XYZ)", font=('Segoe UI', 12, 'bold'), text_color=TEXT_GRAY).pack(anchor='w', padx=15, pady=(15, 5))
        
        axis_container = ctk.CTkFrame(panel, fg_color="transparent")
        axis_container.pack(anchor='center', pady=(10, 5))
        btn_w, btn_h, cr, pad = 48, 42, 8, 4
        
        xy_frame = ctk.CTkFrame(axis_container, fg_color="transparent")
        xy_frame.pack(side='left', padx=15)
        ctk.CTkButton(xy_frame, text="↑", width=btn_w, height=btn_h, font=('Arial', 20), corner_radius=cr, fg_color=GREEN_BTN, hover_color=GREEN_BTN_HOVER, command=lambda: self.move_axis('Y', 1)).grid(row=0, column=1, padx=pad, pady=pad)
        ctk.CTkButton(xy_frame, text="←", width=btn_w, height=btn_h, font=('Arial', 20), corner_radius=cr, fg_color=GREEN_BTN, hover_color=GREEN_BTN_HOVER, command=lambda: self.move_axis('X', -1)).grid(row=1, column=0, padx=pad, pady=pad)
        ctk.CTkButton(xy_frame, text="⌂", width=btn_w, height=btn_h, font=('Arial', 20), corner_radius=cr, fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, command=lambda: self.send_gcode("G28 X Y")).grid(row=1, column=1, padx=pad, pady=pad)
        ctk.CTkButton(xy_frame, text="→", width=btn_w, height=btn_h, font=('Arial', 20), corner_radius=cr, fg_color=GREEN_BTN, hover_color=GREEN_BTN_HOVER, command=lambda: self.move_axis('X', 1)).grid(row=1, column=2, padx=pad, pady=pad)
        ctk.CTkButton(xy_frame, text="↓", width=btn_w, height=btn_h, font=('Arial', 20), corner_radius=cr, fg_color=GREEN_BTN, hover_color=GREEN_BTN_HOVER, command=lambda: self.move_axis('Y', -1)).grid(row=2, column=1, padx=pad, pady=pad)
        
        z_frame = ctk.CTkFrame(axis_container, fg_color="transparent")
        z_frame.pack(side='left', padx=15)
        ctk.CTkButton(z_frame, text="↑", width=btn_w, height=btn_h, font=('Arial', 20), corner_radius=cr, fg_color=GREEN_BTN, hover_color=GREEN_BTN_HOVER, command=lambda: self.move_axis('Z', 1)).grid(row=0, column=0, padx=pad, pady=pad)
        ctk.CTkButton(z_frame, text="⌂", width=btn_w, height=btn_h, font=('Arial', 20), corner_radius=cr, fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, command=lambda: self.send_gcode("G28 Z")).grid(row=1, column=0, padx=pad, pady=pad)
        ctk.CTkButton(z_frame, text="↓", width=btn_w, height=btn_h, font=('Arial', 20), corner_radius=cr, fg_color=GREEN_BTN, hover_color=GREEN_BTN_HOVER, command=lambda: self.move_axis('Z', -1)).grid(row=2, column=0, padx=pad, pady=pad)

        home_frame = ctk.CTkFrame(axis_container, fg_color="transparent")
        home_frame.pack(side='left', padx=15)
        ctk.CTkButton(home_frame, text="⌂ ALL", width=90, height=btn_h, font=('Segoe UI', 13, 'bold'), corner_radius=cr, fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, command=lambda: self.send_gcode("G28")).grid(row=0, column=0, padx=pad, pady=pad)
        ctk.CTkButton(home_frame, text="⌂ X", width=90, height=btn_h, font=('Segoe UI', 13, 'bold'), corner_radius=cr, fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, command=lambda: self.send_gcode("G28 X")).grid(row=1, column=0, padx=pad, pady=pad)
        ctk.CTkButton(home_frame, text="⌂ Y", width=90, height=btn_h, font=('Segoe UI', 13, 'bold'), corner_radius=cr, fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, command=lambda: self.send_gcode("G28 Y")).grid(row=2, column=0, padx=pad, pady=pad)

        dist_frame = ctk.CTkFrame(panel, fg_color="transparent")
        dist_frame.pack(fill='x', padx=25, pady=(5, 15))
        self.seg_dist = ctk.CTkSegmentedButton(dist_frame, values=["0.1", "1", "10", "25", "50", "100"], variable=self.distance_var, font=('Segoe UI', 13, 'bold'), fg_color=BG_COLOR, selected_color=GRAY_BTN, selected_hover_color=GRAY_BTN_HOVER, unselected_color=BG_COLOR, unselected_hover_color=PANEL_COLOR, text_color=TEXT_WHITE)
        self.seg_dist.pack(fill='x')

        ctk.CTkLabel(panel, text="2. Tọa độ (Vị trí thực / Đi tới)", font=('Segoe UI', 12, 'bold'), text_color=TEXT_GRAY).pack(anchor='w', padx=15, pady=(5, 5))
        
        pos_frame = ctk.CTkFrame(panel, fg_color="transparent")
        pos_frame.pack(fill='x', padx=15, pady=5)
        
        def create_pos_box(parent, axis_name):
            box = ctk.CTkFrame(parent, fg_color="transparent", border_width=1, border_color="#434c56", corner_radius=6)
            lbl = ctk.CTkLabel(box, text=f"{axis_name} [0.00]", font=('Segoe UI', 10), text_color=TEXT_GRAY)
            lbl.pack(anchor='w', padx=5, pady=(2, 0))
            ent = ctk.CTkEntry(box, width=65, height=26, border_width=0, fg_color="transparent", font=('Consolas', 15), text_color=TEXT_WHITE)
            ent.pack(fill='x', padx=2, pady=(0, 2))
            return box, lbl, ent

        self.box_x, self.lbl_pos_x, self.ent_move_x = create_pos_box(pos_frame, "X")
        self.box_x.pack(side='left', padx=(0, 10))
        self.box_y, self.lbl_pos_y, self.ent_move_y = create_pos_box(pos_frame, "Y")
        self.box_y.pack(side='left', padx=10)
        self.box_z, self.lbl_pos_z, self.ent_move_z = create_pos_box(pos_frame, "Z")
        self.box_z.pack(side='left', padx=10)

        ctk.CTkButton(pos_frame, text="DI CHUYỂN", width=90, height=44, font=('Segoe UI', 12, 'bold'), fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, command=self.action_move_to).pack(side='left', padx=(10, 0))

        ctk.CTkLabel(panel, text="3. Đầu đùn (Extruder)", font=('Segoe UI', 12, 'bold'), text_color=TEXT_GRAY).pack(anchor='w', padx=15, pady=(15, 5))
        ext_frame = ctk.CTkFrame(panel, fg_color="transparent")
        ext_frame.pack(fill='x', padx=15, pady=(5, 15))
        
        input_ext = ctk.CTkFrame(ext_frame, fg_color="transparent")
        input_ext.pack(side='left')
        len_box = ctk.CTkFrame(input_ext, fg_color="transparent", border_width=1, border_color="#434c56", corner_radius=6)
        len_box.pack(fill='x', pady=4)
        ctk.CTkLabel(len_box, text="C.Dài (mm)", width=75, anchor='w', font=('Segoe UI', 11), text_color=TEXT_GRAY).pack(side='left', padx=5)
        ctk.CTkEntry(len_box, textvariable=self.extrude_len_var, width=50, height=26, border_width=0, fg_color="transparent", font=('Consolas', 13)).pack(side='left')

        spd_box = ctk.CTkFrame(input_ext, fg_color="transparent", border_width=1, border_color="#434c56", corner_radius=6)
        spd_box.pack(fill='x', pady=4)
        ctk.CTkLabel(spd_box, text="T.Độ (mm/s)", width=75, anchor='w', font=('Segoe UI', 11), text_color=TEXT_GRAY).pack(side='left', padx=5)
        ctk.CTkEntry(spd_box, textvariable=self.extrude_speed_var, width=50, height=26, border_width=0, fg_color="transparent", font=('Consolas', 13)).pack(side='left')
        
        ctk.CTkButton(ext_frame, text="RETRACT ︿", width=100, height=60, corner_radius=8, fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, font=('Segoe UI', 11, 'bold'), command=self.action_retract).pack(side='left', padx=(20, 10))
        ctk.CTkButton(ext_frame, text="EXTRUDE ﹀", width=100, height=60, corner_radius=8, fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, font=('Segoe UI', 11, 'bold'), command=self.action_extrude).pack(side='left')

    # ==========================================
    # CỘT 3: THERMALS & CONSOLE
    # ==========================================
    def build_thermals_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=PANEL_COLOR, corner_radius=10)
        panel.pack(fill='x', pady=5)
        
        header = ctk.CTkFrame(panel, fg_color=PANEL_HEADER_COLOR, corner_radius=8)
        header.pack(fill='x', padx=10, pady=(10, 0))
        ctk.CTkLabel(header, text="🔥 Nhiệt độ", font=('Segoe UI', 14, 'bold'), text_color=TEXT_GREEN).pack(side='left', padx=15, pady=8)
        
        table_frame = ctk.CTkFrame(panel, fg_color="transparent")
        table_frame.pack(fill='x', padx=15, pady=10)
        ctk.CTkLabel(table_frame, text="Linh kiện", font=('Segoe UI', 12, 'bold'), text_color=TEXT_GRAY).grid(row=0, column=0, sticky='w', padx=5)
        ctk.CTkLabel(table_frame, text="Thực tế", font=('Segoe UI', 12, 'bold'), text_color=TEXT_GRAY).grid(row=0, column=1, sticky='w', padx=25)
        ctk.CTkLabel(table_frame, text="Mục tiêu", font=('Segoe UI', 12, 'bold'), text_color=TEXT_GRAY).grid(row=0, column=2, sticky='w', padx=5)
        
        ctk.CTkLabel(table_frame, text="Đầu đùn", text_color="#f44336", font=('Segoe UI', 13, 'bold')).grid(row=1, column=0, sticky='w', padx=5, pady=6)
        self.lbl_act_ext = ctk.CTkLabel(table_frame, text="0.0 °C", font=('Segoe UI', 13, 'bold'), text_color=TEXT_WHITE)
        self.lbl_act_ext.grid(row=1, column=1, sticky='w', padx=25)
        self.ent_tgt_ext = ctk.CTkEntry(table_frame, width=60, height=28, fg_color=BG_COLOR, border_width=1, border_color="#434c56", corner_radius=6)
        self.ent_tgt_ext.insert(0, "0")
        self.ent_tgt_ext.grid(row=1, column=2, sticky='w', padx=5)
        self.ent_tgt_ext.bind("<Return>", lambda e: self.set_temperature('extruder'))

        ctk.CTkLabel(table_frame, text="Bàn nhiệt", text_color=TEXT_GREEN, font=('Segoe UI', 13, 'bold')).grid(row=2, column=0, sticky='w', padx=5, pady=6)
        self.lbl_act_bed = ctk.CTkLabel(table_frame, text="0.0 °C", font=('Segoe UI', 13, 'bold'), text_color=TEXT_WHITE)
        self.lbl_act_bed.grid(row=2, column=1, sticky='w', padx=25)
        self.ent_tgt_bed = ctk.CTkEntry(table_frame, width=60, height=28, fg_color=BG_COLOR, border_width=1, border_color="#434c56", corner_radius=6)
        self.ent_tgt_bed.insert(0, "0")
        self.ent_tgt_bed.grid(row=2, column=2, sticky='w', padx=5)
        self.ent_tgt_bed.bind("<Return>", lambda e: self.set_temperature('bed'))

        self.chart_canvas = tk.Canvas(panel, height=140, bg=BG_COLOR, highlightthickness=0)
        self.chart_canvas.pack(fill='x', padx=15, pady=(5, 15))
        self.draw_chart_grid(500)

    def draw_chart_grid(self, c_width):
        self.chart_canvas.delete("grid")
        for temp_val in [50, 150, 250]:
            y = 140 - (temp_val * 120 / 250) - 10
            self.chart_canvas.create_line(30, y, c_width, y, fill="#2d343c", tags="grid")
            self.chart_canvas.create_text(15, y, text=str(temp_val), fill=TEXT_GRAY, font=('Segoe UI', 8), tags="grid")

    def update_chart_lines(self):
        c_width = self.chart_canvas.winfo_width()
        if c_width < 100: c_width = 400 
        
        self.draw_chart_grid(c_width)
        self.chart_canvas.delete("lines")
        
        w, h = c_width - 30, 120
        points_count = len(self.extruder_history)
        if points_count < 2: return
        dx = w / (points_count - 1)
        
        ext_coords = [ (30 + (i * dx), 140 - (temp * h / 250) - 10) for i, temp in enumerate(self.extruder_history) ]
        flat_ext = [item for sublist in ext_coords for item in sublist]
        self.chart_canvas.create_line(flat_ext, fill="#f44336", width=2, tags="lines")

        bed_coords = [ (30 + (i * dx), 140 - (temp * h / 250) - 10) for i, temp in enumerate(self.bed_history) ]
        flat_bed = [item for sublist in bed_coords for item in sublist]
        self.chart_canvas.create_line(flat_bed, fill=TEXT_GREEN, width=2, tags="lines")

    def build_console_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=PANEL_COLOR, corner_radius=10)
        panel.pack(fill='both', expand=True, pady=5)
        
        header = ctk.CTkFrame(panel, fg_color=PANEL_HEADER_COLOR, corner_radius=8)
        header.pack(fill='x', padx=10, pady=(10, 5))
        ctk.CTkLabel(header, text=">_ Console", font=('Segoe UI', 14, 'bold'), text_color=TEXT_GREEN).pack(side='left', padx=15, pady=8)
        
        input_frame = ctk.CTkFrame(panel, fg_color="transparent")
        input_frame.pack(side='bottom', fill='x', padx=15, pady=15)
        
        self.ent_console_cmd = ctk.CTkEntry(input_frame, fg_color=BG_COLOR, border_color="#434c56", border_width=1, height=36, font=('Consolas', 12))
        self.ent_console_cmd.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.ent_console_cmd.bind("<Return>", lambda e: self.action_send_console_command())
        
        ctk.CTkButton(input_frame, text="GỬI", width=90, height=36, corner_radius=6, fg_color=GRAY_BTN, hover_color=GRAY_BTN_HOVER, font=('Segoe UI', 12, 'bold'), command=self.action_send_console_command).pack(side='right')

        text_bg = ctk.CTkFrame(panel, fg_color=BG_COLOR, corner_radius=8)
        text_bg.pack(side='top', fill='both', expand=True, padx=15, pady=(5, 5))
        self.txt_console = tk.Text(text_bg, bg=BG_COLOR, fg="#b0bec5", insertbackground="white", bd=0, highlightthickness=0, font=('Consolas', 11))
        self.txt_console.pack(fill='both', expand=True, padx=10, pady=10)
        self.txt_console.configure(state='disabled')
        
        self.txt_console.tag_config('cmd', foreground=TEXT_GREEN)
        self.txt_console.tag_config('time', foreground=TEXT_GRAY)
        self.txt_console.tag_config('resp', foreground='#a4ef9a')

    # ==========================================
    # XỬ LÝ SỰ KIỆN & GIAO TIẾP
    # ==========================================
    def format_time(self, seconds):
        if not seconds: return "00:00:00"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def append_log(self, text, is_cmd=False):
        now = datetime.now().strftime("%H:%M:%S")
        def run():
            self.txt_console.configure(state='normal')
            self.txt_console.insert('end', f"{now}   ", 'time')
            if is_cmd:
                self.txt_console.insert('end', f"$ {text}\n", 'cmd')
            else:
                self.txt_console.insert('end', f"// {text}\n", 'resp')
            self.txt_console.see('end')
            self.txt_console.configure(state='disabled')
        self.root.after(0, run)

    def action_connect_printer(self):
        target_ip = self.ip_var.get().strip()
        if not target_ip: return
        self.append_log(f"Đang chuẩn bị kết nối tới {target_ip}...", is_cmd=False)
        self.lbl_net_status.configure(text="Đang kết nối...", text_color="yellow")
        # Sử dụng Network Manager
        self.network.connect(target_ip)

    def update_connection_status(self, is_connected, error_msg=""):
        self.is_connected = is_connected
        if is_connected:
            self.root.after(0, lambda: self.lbl_net_status.configure(text="Đã kết nối", text_color="#a4ef9a"))
        else:
            self.root.after(0, lambda: self.lbl_net_status.configure(text="Lỗi kết nối", text_color="#f44336"))

    def parse_incoming_data(self, data):
        if "method" in data and data["method"] == "notify_gcode_response":
            for line in data.get("params", []):
                self.append_log(line, is_cmd=False)

        status = {}
        if data.get("method") == "notify_status_update":
            params = data.get("params", [])
            if params and isinstance(params[0], dict):
                status = params[0]
        else:
            result = data.get("result")
            if isinstance(result, dict):
                status = result.get("status", {})
                
        if not status: return
        
        if "extruder" in status:
            if "temperature" in status["extruder"]:
                t = status["extruder"]["temperature"]
                self.extruder_history.append(t)
                self.root.after(0, lambda: self.lbl_act_ext.configure(text=f"{round(t,1)} °C"))
            if "target" in status["extruder"]:
                self.root.after(0, lambda: self.update_target_entry('ext', status["extruder"]["target"]))
                
        if "heater_bed" in status:
            if "temperature" in status["heater_bed"]:
                b = status["heater_bed"]["temperature"]
                self.bed_history.append(b)
                self.root.after(0, lambda: self.lbl_act_bed.configure(text=f"{round(b,1)} °C"))
            if "target" in status["heater_bed"]:
                self.root.after(0, lambda: self.update_target_entry('bed', status["heater_bed"]["target"]))

        self.root.after(0, self.update_chart_lines)

        if "toolhead" in status and "position" in status["toolhead"]:
            pos = status["toolhead"]["position"]
            self.root.after(0, lambda: self.lbl_pos_x.configure(text=f"X [{pos[0]:.2f}]"))
            self.root.after(0, lambda: self.lbl_pos_y.configure(text=f"Y [{pos[1]:.2f}]"))
            self.root.after(0, lambda: self.lbl_pos_z.configure(text=f"Z [{pos[2]:.2f}]"))

        if "display_status" in status and "progress" in status["display_status"]:
            prog = status["display_status"]["progress"]
            self.root.after(0, lambda: self.prog_canvas.itemconfig(self.prog_arc, extent=-int(prog*360)))
            self.root.after(0, lambda: self.prog_canvas.itemconfig(self.prog_text, text=f"{int(prog*100)}%"))
            
        if "print_stats" in status:
            st = status["print_stats"]
            if "state" in st:
                new_state = st["state"].lower()
                if new_state in ["printing", "paused"]:
                    if self.current_print_state not in ["printing", "paused"]:
                        self.frame_idle.pack_forget()
                        self.frame_active.pack(fill='both', expand=True)
                        self.current_print_state = new_state
                else:
                    if self.current_print_state in ["printing", "paused", ""]:
                        self.frame_active.pack_forget()
                        self.frame_idle.pack(fill='both', expand=True)
                        self.current_print_state = new_state

            if "filename" in st:
                fname = st["filename"] if st["filename"] else "Chưa tải file"
                self.root.after(0, lambda: self.lbl_print_file.configure(text=f"File: {fname}"))
            if "print_duration" in st and "total_duration" in st:
                pd = self.format_time(st["print_duration"])
                td = self.format_time(st["total_duration"])
                self.root.after(0, lambda: self.lbl_print_time.configure(text=f"Thời gian: {pd} / {td}"))
            if "filament_used" in st:
                used = st["filament_used"] / 1000
                self.root.after(0, lambda: self.lbl_print_filament.configure(text=f"Nhựa dùng: {used:.2f} m"))

        if "bed_mesh" in status and "mesh_matrix" in status["bed_mesh"]:
            matrix = status["bed_mesh"]["mesh_matrix"]
            if matrix:
                self.root.after(0, lambda: self.draw_bed_mesh(matrix))

    def update_target_entry(self, mode, val):
        if mode == 'ext' and self.root.focus_get() != self.ent_tgt_ext:
            self.ent_tgt_ext.delete(0, tk.END)
            self.ent_tgt_ext.insert(0, str(int(val)))
        elif mode == 'bed' and self.root.focus_get() != self.ent_tgt_bed:
            self.ent_tgt_bed.delete(0, tk.END)
            self.ent_tgt_bed.insert(0, str(int(val)))

    def action_send_console_command(self):
        cmd = self.ent_console_cmd.get().strip()
        if cmd:
            self.send_gcode(cmd)
            self.ent_console_cmd.delete(0, tk.END)

    def action_move_to(self):
        cmd = "G90\nG1"
        has_move = False
        if self.ent_move_x.get().strip(): 
            cmd += f" X{self.ent_move_x.get().strip()}"
            has_move = True
        if self.ent_move_y.get().strip(): 
            cmd += f" Y{self.ent_move_y.get().strip()}"
            has_move = True
        if self.ent_move_z.get().strip(): 
            cmd += f" Z{self.ent_move_z.get().strip()}"
            has_move = True
            
        if has_move:
            self.send_gcode(cmd)
        else:
            messagebox.showinfo("Thông báo", "Vui lòng nhập ít nhất một tọa độ để di chuyển.")

    def upload_gcode(self):
        if not self.is_connected:
            messagebox.showwarning("Cảnh báo", "Bạn phải kết nối mạng với máy in trước khi tải lên.")
            return
        file_path = filedialog.askopenfilename(filetypes=[("G-Code Files", "*.gcode")])
        if file_path:
            self.network.upload_and_print(self.ip_var.get().strip(), file_path)

    def send_gcode(self, script):
        if not self.is_connected: return
        payload = {"jsonrpc": "2.0", "method": "printer.gcode.script", "params": {"script": script}, "id": "tk_cmd"}
        self.network.send_command(payload)
        self.append_log(script, is_cmd=True)

    def move_axis(self, axis, direction):
        dist = float(self.distance_var.get())
        self.send_gcode(f"G91\nG1 {axis}{dist * direction} F3000\nG90")

    def action_extrude(self):
        length, speed = self.extrude_len_var.get(), int(self.extrude_speed_var.get()) * 60
        self.send_gcode(f"M83\nG1 E{length} F{speed}")

    def action_retract(self):
        length, speed = self.extrude_len_var.get(), int(self.extrude_speed_var.get()) * 60
        self.send_gcode(f"M83\nG1 E-{length} F{speed}")

    def set_temperature(self, heater):
        if heater == 'extruder':
            self.send_gcode(f"SET_HEATER_TEMPERATURE HEATER=extruder TARGET={self.ent_tgt_ext.get()}")
        else:
            self.send_gcode(f"SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET={self.ent_tgt_bed.get()}")
        self.root.focus_set()

    def emergency_stop(self):
        if not self.is_connected: return
        payload = {"jsonrpc": "2.0", "method": "printer.emergency_stop", "params": {}, "id": "estop"}
        self.network.send_command(payload)
        self.append_log("ĐÃ KÍCH HOẠT DỪNG KHẨN CẤP TOÀN HỆ THỐNG (M112)!", is_cmd=True)

    def __del__(self):
        if hasattr(self, 'camera'):
            self.camera.release()

if __name__ == "__main__":
    root = ctk.CTk()
    app = MainsailTkinterGUI(root)
    root.mainloop()