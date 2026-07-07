import asyncio
import json
import threading
import websockets
import requests
import os

class PrinterNetwork:
    def __init__(self, gui_callback, connection_callback, log_callback):
        """
        Khởi tạo trình quản lý mạng máy in.
        - gui_callback: Hàm xử lý dữ liệu nhận được từ WebSocket.
        - connection_callback: Hàm cập nhật trạng thái kết nối lên UI.
        - log_callback: Hàm in log ra màn hình Console.
        """
        self.gui_callback = gui_callback
        self.connection_callback = connection_callback
        self.log_callback = log_callback
        self.websocket = None
        self.loop = None
        self.send_queue = None
        self.is_connected = False

    def connect(self, ip_addr):
        # Chạy vòng lặp asyncio trên một thread riêng biệt
        threading.Thread(target=self._start_loop, args=(ip_addr,), daemon=True).start()

    def _start_loop(self, ip_addr):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.send_queue = asyncio.Queue()
        self.loop.run_until_complete(self._ws_handler(ip_addr))

    async def _ws_handler(self, ip_addr):
        uri = f"ws://{ip_addr}/websocket"
        try:
            async with websockets.connect(uri) as websocket:
                self.websocket = websocket
                self.is_connected = True
                self.connection_callback(True)
                self.log_callback("Đã thiết lập đồng bộ với Klipper!")
                
                # Gửi yêu cầu định danh và đăng ký theo dõi trạng thái
                await websocket.send(json.dumps({"jsonrpc": "2.0", "method": "server.connection.identify", "params": {"client_name": "mainsail_tk", "version": "1.0.0", "type": "web"}, "id": 1}))
                await websocket.send(json.dumps({"jsonrpc": "2.0", "method": "printer.objects.subscribe", "params": {"objects": {"extruder": None, "heater_bed": None, "toolhead": None, "print_stats": None, "display_status": None, "bed_mesh": None}}, "id": 2}))

                while True:
                    listener_task = asyncio.create_task(websocket.recv())
                    sender_task = asyncio.create_task(self.send_queue.get())
                    
                    done, pending = await asyncio.wait([listener_task, sender_task], return_when=asyncio.FIRST_COMPLETED)

                    for task in done:
                        if task == listener_task:
                            self.gui_callback(json.loads(task.result()))
                        elif task == sender_task:
                            await websocket.send(json.dumps(task.result()))
                            self.send_queue.task_done()
                            
                    for task in pending: task.cancel()
        except Exception as e:
            self.is_connected = False
            self.connection_callback(False, str(e))
            self.log_callback(f"Lỗi mạng: {e}")

    def send_command(self, payload):
        if self.is_connected and self.send_queue and self.loop:
            self.loop.call_soon_threadsafe(self.send_queue.put_nowait, payload)

    def upload_and_print(self, ip, file_path):
        def _upload():
            try:
                filename = os.path.basename(file_path)
                url = f"http://{ip}/server/files/upload"
                files = {'file': (filename, open(file_path, 'rb'))}
                data = {'print': 'true'}
                self.log_callback(f"Đang tải {filename} lên máy in...")
                
                response = requests.post(url, files=files, data=data)
                if response.status_code in [200, 201]:
                    self.log_callback("Tải lên thành công! Đang khởi động in...")
                else:
                    self.log_callback(f"Lỗi tải lên: {response.text}")
            except Exception as e:
                self.log_callback(f"Lỗi hệ thống khi tải file: {e}")
                
        threading.Thread(target=_upload, daemon=True).start()