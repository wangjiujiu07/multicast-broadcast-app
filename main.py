import json
import queue
import socket
import struct
import threading
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout


KV = """
<RootWidget>:
    orientation: "vertical"
    padding: dp(10)
    spacing: dp(8)

    BoxLayout:
        size_hint_y: None
        height: dp(42)
        spacing: dp(6)
        TextInput:
            id: name_input
            text: root.default_name
            hint_text: "昵称"
            multiline: False
        TextInput:
            id: group_input
            text: "239.255.0.1"
            hint_text: "组播地址"
            multiline: False
        TextInput:
            id: port_input
            text: "5007"
            hint_text: "端口"
            multiline: False
            input_filter: "int"

    BoxLayout:
        size_hint_y: None
        height: dp(42)
        spacing: dp(6)
        Button:
            text: "加入监听"
            on_release: root.start_receiver()
        Button:
            text: "退出监听"
            on_release: root.stop_receiver()

    TextInput:
        id: output
        text: root.log_text
        readonly: True
        font_size: "14sp"

    BoxLayout:
        size_hint_y: None
        height: dp(42)
        spacing: dp(6)
        TextInput:
            id: message_input
            hint_text: "输入广播消息"
            multiline: False
            on_text_validate: root.send_message()
        Button:
            size_hint_x: None
            width: dp(120)
            text: "发送广播"
            on_release: root.send_message()
"""


class MulticastReceiver(threading.Thread):
    def __init__(self, group_ip, port, output_queue, stop_event):
        super().__init__(daemon=True)
        self.group_ip = group_ip
        self.port = port
        self.output_queue = output_queue
        self.stop_event = stop_event
        self.sock = None

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("", self.port))
            mreq = struct.pack("4s4s", socket.inet_aton(self.group_ip), socket.inet_aton("0.0.0.0"))
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            self.sock.settimeout(0.5)
            self.output_queue.put(("system", f"已加入组播组 {self.group_ip}:{self.port}"))
        except Exception as exc:
            self.output_queue.put(("error", f"接收端启动失败: {exc}"))
            return

        while not self.stop_event.is_set():
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except Exception as exc:
                if not self.stop_event.is_set():
                    self.output_queue.put(("error", f"接收错误: {exc}"))
                break

            try:
                payload = json.loads(data.decode("utf-8", errors="ignore"))
                name = payload.get("sender", "unknown")
                text = payload.get("text", "")
                ts = payload.get("ts", "")
                self.output_queue.put(("message", f"[{ts}] {name}@{addr[0]}:{addr[1]} -> {text}"))
            except Exception:
                raw = data.decode("utf-8", errors="ignore")
                self.output_queue.put(("message", f"{addr}: {raw}"))

        try:
            if self.sock is not None:
                self.sock.close()
        except Exception:
            pass
        self.output_queue.put(("system", "已退出组播监听"))


class RootWidget(BoxLayout):
    log_text = StringProperty("")
    default_name = StringProperty(socket.gethostname())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.receiver = None
        self.sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sender_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self.sender_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        Clock.schedule_interval(self.poll_queue, 0.1)
        self.append_line("欢迎使用 UDP 组播广播 APP")
        self.append_line("提示: 多设备设同组播地址+端口即可互通")

    def append_line(self, text):
        self.log_text = (self.log_text + text + "\n")[-20000:]

    def parse_endpoint(self):
        group_ip = self.ids.group_input.text.strip()
        port_text = self.ids.port_input.text.strip()
        if not group_ip:
            raise ValueError("组播地址不能为空")
        try:
            socket.inet_aton(group_ip)
        except OSError as exc:
            raise ValueError("组播地址格式不正确") from exc

        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError("端口必须是数字") from exc
        if port < 1 or port > 65535:
            raise ValueError("端口范围必须是 1-65535")
        return group_ip, port

    def start_receiver(self):
        if self.receiver and self.receiver.is_alive():
            self.append_line("监听已在运行")
            return
        try:
            group_ip, port = self.parse_endpoint()
        except ValueError as exc:
            self.append_line(f"参数错误: {exc}")
            return
        self.stop_event = threading.Event()
        self.receiver = MulticastReceiver(group_ip, port, self.event_queue, self.stop_event)
        self.receiver.start()

    def stop_receiver(self):
        if self.receiver and self.receiver.is_alive():
            self.stop_event.set()
            self.receiver.join(timeout=1.0)
        self.receiver = None

    def send_message(self):
        text = self.ids.message_input.text.strip()
        if not text:
            return
        try:
            group_ip, port = self.parse_endpoint()
        except ValueError as exc:
            self.append_line(f"参数错误: {exc}")
            return

        sender = self.ids.name_input.text.strip() or "anonymous"
        packet = {
            "sender": sender,
            "text": text,
            "ts": time.strftime("%H:%M:%S"),
        }
        data = json.dumps(packet, ensure_ascii=False).encode("utf-8")
        try:
            self.sender_socket.sendto(data, (group_ip, port))
            self.append_line(f"[{packet['ts']}] 我 -> {text}")
            self.ids.message_input.text = ""
        except Exception as exc:
            self.append_line(f"发送失败: {exc}")

    def poll_queue(self, _dt):
        while True:
            try:
                _level, text = self.event_queue.get_nowait()
            except queue.Empty:
                break
            self.append_line(text)

    def on_stop(self):
        self.stop_receiver()
        try:
            self.sender_socket.close()
        except Exception:
            pass


class MulticastApp(App):
    def build(self):
        Builder.load_string(KV)
        return RootWidget()

    def on_stop(self):
        root = self.root
        if root is not None:
            root.on_stop()


if __name__ == "__main__":
    MulticastApp().run()
