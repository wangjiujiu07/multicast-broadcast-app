import json
import queue
import socket
import struct
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText


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


class BroadcastApp:
    def __init__(self, root):
        self.root = root
        self.root.title("UDP 组播广播 APP")
        self.root.geometry("920x600")

        self.queue = queue.Queue()
        self.stop_event = threading.Event()
        self.receiver = None

        self.sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sender_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self.sender_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

        self._build_ui()
        self._poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        top = tk.Frame(self.root, padx=10, pady=10)
        top.pack(fill=tk.X)

        tk.Label(top, text="昵称").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar(value=socket.gethostname())
        tk.Entry(top, textvariable=self.name_var, width=20).grid(row=0, column=1, padx=6)

        tk.Label(top, text="组播地址").grid(row=0, column=2, sticky="w")
        self.group_var = tk.StringVar(value="239.255.0.1")
        tk.Entry(top, textvariable=self.group_var, width=18).grid(row=0, column=3, padx=6)

        tk.Label(top, text="端口").grid(row=0, column=4, sticky="w")
        self.port_var = tk.StringVar(value="5007")
        tk.Entry(top, textvariable=self.port_var, width=10).grid(row=0, column=5, padx=6)

        tk.Button(top, text="加入监听", command=self.start_receiver, width=12).grid(row=0, column=6, padx=4)
        tk.Button(top, text="退出监听", command=self.stop_receiver, width=12).grid(row=0, column=7, padx=4)

        center = tk.Frame(self.root, padx=10, pady=4)
        center.pack(fill=tk.BOTH, expand=True)

        self.output = ScrolledText(center, state=tk.DISABLED, wrap=tk.WORD, font=("Consolas", 10))
        self.output.pack(fill=tk.BOTH, expand=True)

        bottom = tk.Frame(self.root, padx=10, pady=10)
        bottom.pack(fill=tk.X)

        self.message_var = tk.StringVar()
        entry = tk.Entry(bottom, textvariable=self.message_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        entry.bind("<Return>", lambda _e: self.send_message())

        tk.Button(bottom, text="发送广播", command=self.send_message, width=14).pack(side=tk.LEFT)

    def append_line(self, text, tag="info"):
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text + "\n")
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def parse_endpoint(self):
        group_ip = self.group_var.get().strip()
        port_text = self.port_var.get().strip()
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
            self.append_line("监听已在运行", "system")
            return
        try:
            group_ip, port = self.parse_endpoint()
        except ValueError as exc:
            messagebox.showerror("参数错误", str(exc))
            return

        self.stop_event = threading.Event()
        self.receiver = MulticastReceiver(group_ip, port, self.queue, self.stop_event)
        self.receiver.start()

    def stop_receiver(self):
        if self.receiver and self.receiver.is_alive():
            self.stop_event.set()
            self.receiver.join(timeout=1.0)
        self.receiver = None

    def send_message(self):
        text = self.message_var.get().strip()
        if not text:
            return
        try:
            group_ip, port = self.parse_endpoint()
        except ValueError as exc:
            messagebox.showerror("参数错误", str(exc))
            return

        sender = self.name_var.get().strip() or "anonymous"
        packet = {
            "sender": sender,
            "text": text,
            "ts": time.strftime("%H:%M:%S"),
        }
        data = json.dumps(packet, ensure_ascii=False).encode("utf-8")
        try:
            self.sender_socket.sendto(data, (group_ip, port))
            self.append_line(f"[{packet['ts']}] 我 -> {text}", "self")
            self.message_var.set("")
        except Exception as exc:
            messagebox.showerror("发送失败", str(exc))

    def _poll_queue(self):
        while True:
            try:
                level, text = self.queue.get_nowait()
            except queue.Empty:
                break
            self.append_line(text, level)
        self.root.after(100, self._poll_queue)

    def on_close(self):
        self.stop_receiver()
        try:
            self.sender_socket.close()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    app = BroadcastApp(root)
    app.append_line("欢迎使用 UDP 组播广播 APP")
    app.append_line("提示: 可在多台同网段设备上启动，设置同组播地址+端口即可互通")
    root.mainloop()


if __name__ == "__main__":
    main()
