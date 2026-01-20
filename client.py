import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import socket
import json

class MS_Watcher:
    # --- Fonctions UI ---
    def __init__(self, root):
        self.root = root
        self.root.title("MS Watcher")
        self.root.geometry("720x520")
        self.root.resizable(True, True)

        self.zone = None

        # Connect to server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect(('localhost', 12345))
        except Exception as e:
            messagebox.showerror("Connection Error", f"Cannot connect to server: {e}")
            root.destroy()
            return

        # Start thread to receive logs
        threading.Thread(target=self.receive_logs, daemon=True).start()

        self.log_box = scrolledtext.ScrolledText(root, width=85, height=25, state='disabled', bg="#f9f9f9")
        self.log_box.pack(padx=10, pady=10)

        frame = tk.Frame(root)
        frame.pack()

        self.select_button = tk.Button(frame, text="Select Zone", width=18, command=self.select_zone)
        self.select_button.pack(side=tk.LEFT, padx=5)

        self.start_button = tk.Button(frame, text="▶️ Start", width=15, command=self.start, state='disabled')
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(frame, text="⏹️ Stop", width=15, command=self.stop, state='disabled')
        self.stop_button.pack(side=tk.LEFT, padx=5)

    def log(self, message):
        self.log_box.config(state='normal')
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.see(tk.END)
        self.log_box.config(state='disabled')

    def receive_logs(self):
        buffer = ""
        while True:
            try:
                data = self.sock.recv(1024)
                if not data:
                    break
                buffer += data.decode('utf-8')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        message = json.loads(line)
                        log_msg = message.get("log")
                        if log_msg:
                            self.log(log_msg)
            except:
                break

    def select_zone(self):
        self.log("Select zone to watch on screen.")
        self.root.withdraw()
        selector = ZoneSelector(self.root)
        self.root.wait_window(selector)
        self.root.deiconify()

        if selector.zone:
            self.zone = selector.zone
            self.start_button.config(state='normal')
            self.log(f"Selected zone : {self.zone}")
        else:
            self.log("No zone selected")

    def start(self):
        if not self.zone:
            messagebox.showwarning("Screen zone is missing", "Please select zone to watch.")
            return
        data = json.dumps({"command": "start", "zone": self.zone})
        self.sock.sendall(data.encode('utf-8') + b'\n')
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')

    def stop(self):
        data = json.dumps({"command": "stop"})
        self.sock.sendall(data.encode('utf-8') + b'\n')
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')


class ZoneSelector(tk.Toplevel):
    """Screen zone selector with transparency. Does not handle multi-monitor setting if main screen is not used."""
    def __init__(self, master):
        super().__init__(master)
        self.attributes("-fullscreen", True)
        self.attributes("-alpha", 0.3)
        self.configure(bg="gray")
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.canvas = tk.Canvas(self, cursor="cross", bg="gray", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.zone = None

    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y,
                                                 outline="red", width=2)

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        end_x, end_y = event.x, event.y
        x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
        x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
        self.zone = (x1, y1, x2 - x1, y2 - y1)
        self.destroy()

# -----------------------------
# Main!
# -----------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = MS_Watcher(root)
    root.mainloop()