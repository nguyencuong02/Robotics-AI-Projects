import serial
import time
import numpy as np
import math

class Scara:
    def __init__(self, port='COM9', baudrate=9600, timeout=1):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)
        self.link1 = 80
        self.link2 = 70

    def close(self):
        self.ser.close()

    def flush_serial(self):
        time.sleep(0.05)
        while self.ser.in_waiting:
            _ = self.ser.readline()

    def send_setpoints(self, sp1, sp2, sp3, sp4, sp5):
        sp1 = max(-90, min(90, sp1)) + 150
        sp2 = 100 - max(-90, min(90, sp2))
        sp3 = max(-90, min(90, sp3)) + 90
        sp4 = max(-90, min(90, sp4)) + 90
        sp5 = max(-90, min(90, sp5)) + 90
        cmd = f"{int(sp1)},{int(sp2)},{int(sp3)},{int(sp4)},{int(sp5)}\n"
        self.ser.write(cmd.encode())
        print(f"Sent setpoints: {cmd.strip()}")
        time.sleep(0.1)
        self.flush_serial()

    def get_angles(self):
        self.ser.reset_input_buffer()
        self.ser.write(b"GET\n")
        timeout = time.time() + 2
        while time.time() < timeout:
            if self.ser.in_waiting:
                line = self.ser.readline().decode().strip()
                if line.startswith('<') and line.endswith('>'):
                    parts = line[1:-1].split(',')
                    if len(parts) >= 2:
                        try:
                            a1 = float(parts[0])
                            a2 = float(parts[1])
                            a3 = float(parts[2])
                            a4 = float(parts[3])
                            a5 = float(parts[4])
                            return a1, a2, a3, a4, a5
                        except:
                            pass
        return None, None

    def forward_kinematics(self, theta1, theta2):
        t1 = np.radians(theta1)
        t2 = np.radians(theta2)
        x1 = self.link1 * np.cos(t1)
        y1 = self.link1 * np.sin(t1)
        x2 = x1 + self.link2 * np.cos(t1 + t2)
        y2 = y1 + self.link2 * np.sin(t1 + t2)
        return (0, 0), (x1, y1), (x2, y2)

    def inverse_kinematics(self, x, y):
        a1 = self.link1
        a2 = self.link2
        r2 = x**2 + y**2
        r = np.sqrt(r2)
        if r > a1 + a2 or r < abs(a1 - a2):
            return None
        cos_theta2 = (r2 - a1**2 - a2**2) / (2 * a1 * a2)
        sin_theta2 = np.sqrt(1 - cos_theta2**2)
        theta2_pos = np.arctan2(sin_theta2, cos_theta2)
        theta2_neg = np.arctan2(-sin_theta2, cos_theta2)
        k1 = a1 + a2 * cos_theta2
        k2 = a2 * sin_theta2
        theta1_pos = np.arctan2(y, x) - np.arctan2(k2, k1)
        theta1_neg = np.arctan2(y, x) - np.arctan2(-k2, k1)
        return (np.degrees(theta1_pos), np.degrees(theta2_pos)), (np.degrees(theta1_neg), np.degrees(theta2_neg))

    def to_pos(self, x, y, z, a, b):
        results = self.inverse_kinematics(x, y)
        if results is None:
            print("Tọa độ ngoài vùng làm việc.")
            return
        result1, result2 = results

        def in_range(t1, t2): return -90 <= t1 <= 90 and -90 <= t2 <= 90

        if in_range(*result1):
            sp1, sp2 = result1
        elif in_range(*result2):
            sp1, sp2 = result2
        else:
            print("Không có cặp góc hợp lệ.")
            return
        

        sp3 = a-(sp2+sp1)
        if sp3 < 90:
            sp3 = -sp3
        elif sp3 > 90:
            sp3 = 180-sp3

        sp4 = z
        sp4_mm = max(0, min(20, sp4))
        sp4_angle = sp4_mm * 4


        sp5 = b
        sp5_mm = max(0, min(20, sp5))
        sp5_angle = sp5_mm * 3


        self.send_setpoints(sp1, sp2, sp3, sp4_angle, sp5_angle)\
        

    def send_command(self, cmd):
        self.myserial.write((cmd + '\n').encode())
        print(f"Sent command: {cmd}")
        time.sleep(0.1)

    def toPos(self, x, y):
        result = self.inverse_kinematics(x, y)
        if result is None:
            print("Điểm ngoài vùng làm việc.")
            return
        sp1, sp2 = result
        cmd = f"{int(sp1)},{int(sp2)},90,90,90"
        self.send_command(cmd)

    def linearMove(self, startPos, endPos, step):
        print('Chạy robot theo quỹ đạo tuyến tính')
        for i in range(1, step + 1):
            t = i / step
            Px = endPos[0] * t + startPos[0] * (1 - t)
            Py = endPos[1] * t + startPos[1] * (1 - t)
            self.toPos(Px, Py)

    def smoothMove(self, startPos, endPos, step):
        print('Chạy robot theo quỹ đạo mượt')
        for i in range(1, step + 1):
            t = i / step
            t = (1 - math.cos(t * math.pi)) / 2
            Px = endPos[0] * t + startPos[0] * (1 - t)
            Py = endPos[1] * t + startPos[1] * (1 - t)
            self.toPos(Px, Py)

    def pick_and_place(self, pick_pos, pick_angle, grip_open, place_pos, place_angle):
        px, py, pz = pick_pos
        tx, ty, tz = place_pos
        delay = 0.5

        self.to_pos(px, py, 20, pick_angle, 20)  # mở kẹp
        time.sleep(delay)

        self.to_pos(px, py, pz, pick_angle, 20)
        time.sleep(delay)

        self.to_pos(px, py, pz, pick_angle, grip_open)  # đóng kẹp
        time.sleep(delay)

        self.to_pos(px, py, 20, pick_angle, grip_open)
        time.sleep(delay)

        self.to_pos(tx, ty, 20, place_angle, grip_open)
        time.sleep(delay)

        self.to_pos(tx, ty, tz, place_angle, grip_open)
        time.sleep(delay)

        self.to_pos(tx, ty, tz, place_angle, 20)  # mở kẹp
        time.sleep(delay)

        self.to_pos(tx, ty, 20, place_angle, 20)
        time.sleep(delay)

        self.send_setpoints(0, 0, -90, 80, 0)
