import pyautogui
from ollama import Client
from PIL import Image
import requests
import time
import datetime
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import os
import json
import base64

CONFIG_PATH = "config.json"
pyautogui.FAILSAFE = False

def load_config():
    if not os.path.exists(CONFIG_PATH):
        config_defaut = {
            "teams_webhook_url": "",
            "wait_interval": 30,
            "keyword": "Error",
            "model": "qwen2.5vl:7b",
            "ollama_url": "http://127.0.0.1:11434/api/generate",
            "instrument": "UNKNOWN INSTRUMENT",
            "prompt_file": "PROMPT_FILE.txt"
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_defaut, f, indent=4)
        print("Fill config file before continuing")
        return config_defaut
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
    
config = load_config()
TEAMS_WEBHOOK_URL = config.get("teams_webhook_url")
WAIT_INTERVAL = config.get("wait_interval")
INSTRUMENT = config.get("instrument")
URL = config.get("ollama_url")
PROMPT_FILE = config.get("prompt_file")
MODEL = config.get("model")

def perform_vision(log_callback, zone=None):
    """Takes a screenshot from a zone and send it to Ollama for interpretation"""
    screenshot_path = "capture.png"
    if zone:
        x, y, w, h = zone
        image = pyautogui.screenshot(region=(x, y, w, h))
    else:
        image = pyautogui.screenshot()
    image.save(screenshot_path)
    result = analyze_image_ollama(screenshot_path, log_callback, url = URL)
    print(result)
    notify_teams(INSTRUMENT, result, log_callback)

def notify_teams(sender, messages, log_callback):
    payload = {
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Container",
                            "style": "attention",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": sender,
                                    "weight": "bolder",
                                    "size": "large",
                                    "color": "attention"
                                }
                            ]
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {
                                    "title": "Horodatage:",
                                    "value": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                },
                            ]
                        }
                    ]
                }
            }
        ]
    }
    #Add message content
    payload["attachments"][0]["content"]["body"][1]["facts"].append({"title": "Status", "value": messages})

    try:
        r = requests.post(TEAMS_WEBHOOK_URL, json=payload)
        if r.status_code == 200 or r.status_code == 202:
            log_callback("Notification sent!")
        else:
            log_callback(f"Teams notification error : {r.status_code} - {r.text}")
    except Exception as e:
        log_callback("Teams notification error :", e)


def analyze_image_ollama(screenshot_path, log_callback, url=URL):
    
    with open(screenshot_path, "rb") as screenshot:
        images_to_bytes = base64.b64encode(screenshot.read())

    prompt = ""
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        prompt = f.read()

    if prompt == "":
        print(f"Error: prompt is empty")
        return {"state": "error", "summary": "LLM prompt is empty"}
    
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "images": [images_to_bytes.decode('utf-8')],
        "stream": False
    }
    try:
        log_callback("Sending screenshot to Ollama...")
        r = requests.post(url, json=payload, timeout=300)
        r.raise_for_status()
        result = r.json()
        response_text = str(result.get("response", "").strip())
        #print(response_text)
        log_callback("Got an answer!")
        return response_text
    except Exception as e:
        print(f"Error Ollama: {e}")
        return {"state": "error", "summary": str(e)}


def auto_loop(stop_event, log_callback, zone):
    log_callback(f"=== Watcher started every ~{WAIT_INTERVAL} min) ===")
    while not stop_event.is_set():
        perform_vision(log_callback, zone)
        if stop_event.wait(WAIT_INTERVAL * 60):
            break
    log_callback("Watcher stopped.")


class MS_Watcher:
    # --- Fonctions UI ---
    def __init__(self, root):
        self.root = root
        self.root.title("MS Watcher")
        self.root.geometry("720x520")
        self.root.resizable(True, True)

        self.zone = None
        self.stop_event = threading.Event()
        self.thread = None

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
        self.stop_event.clear()
        self.thread = threading.Thread(target=auto_loop, args=(self.stop_event, self.log, self.zone))
        self.thread.start()
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.log("Watching!")

    def stop(self):
        self.stop_event.set()
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.log("Stop requested")


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
