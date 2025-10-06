import pyautogui
import pytesseract
from PIL import Image
import requests
import time
import datetime
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import os
import json


CONFIG_PATH = "config.json"


def load_config():
    if not os.path.exists(CONFIG_PATH):
        config_defaut = {
            "teams_webhook_url": "",
            "wait_interval": 30,
            "keyword": "Error",
            "ocr_language": "eng",
            "instrument": "Thermo Fusion",
            "tesseract": "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_defaut, f, indent=4)
        print("Fill config file before continuing")
        return config_defaut
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
    
config = load_config()
TEAMS_WEBHOOK_URL = config.get("teams_webhook_url", "")
WAIT_INTERVAL = config.get("wait_interval", 30)
KEYWORDS = config.get("keywords", "Error")
OCR_LANGUAGE = config.get("ocr_language", "eng")
INSTRUMENT = config.get("instrument", "UNKNOW")
TESSERACT = config.get("tesseract", None)

if TESSERACT is None:
    print("Install Tesseract and fill config")
    exit()
pytesseract.pytesseract.tesseract_cmd = TESSERACT


def perform_ocr(zone=None):
    """Perform a screenshot and OCR"""
    screenshot_path = "capture.png"
    if zone:
        x, y, w, h = zone
        image = pyautogui.screenshot(region=(x, y, w, h))
    else:
        image = pyautogui.screenshot()
    image.save(screenshot_path)
    texte = pytesseract.image_to_string(image, lang=OCR_LANGUAGE)
    return texte.strip()

def analyze_text(text, log_callback):
    """Look for LC and MS status in the text."""
    print(text)
    print(f"Instrument: {INSTRUMENT}")
    if INSTRUMENT=="Fusion" or INSTRUMENT=="Exploris":
        #It's a Thermo Scientific instrument. We are watching Xcalibur left pannel.
        split_text = text.split("\n")
        LC_status_header_index = [i for i, j in enumerate(split_text) if "Thermo Scientific" in j]
        #print(f"LC STATUS HEADER INDEX: {LC_status_header_index}")
        if len(LC_status_header_index) == 0:
            log_callback("ERROR: Cannot read LC status")
            notify_teams(INSTRUMENT, {"ERROR": "Cannot read LC status"}, log_callback)
            return
        LC_status_index = LC_status_header_index[0] + 1
        MS_status_header_index = [i for i, j in enumerate(split_text) if "Orbitrap" in j]
        if len(MS_status_header_index) == 0:
            log_callback("ERROR: Cannot read MS status")
            notify_teams(INSTRUMENT, {"ERROR": "Cannot read MS status"}, log_callback)
            return
        MS_status_index = MS_status_header_index[0] + 1
        messages = {"LC status": split_text[LC_status_index], "MS status": split_text[MS_status_index]}
        log_callback(f"LC Status: {split_text[LC_status_index]}")
        log_callback(f"MS Status: {split_text[MS_status_index]}")
        notify_teams(INSTRUMENT, messages, log_callback)
    

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
    for title in messages:
        payload["attachments"][0]["content"]["body"][1]["facts"].append({"title": title, "value": messages[title]})

    try:
        r = requests.post(TEAMS_WEBHOOK_URL, json=payload)
        if r.status_code == 200 or r.status_code == 202:
            log_callback("Notification sent!")
        else:
            log_callback(f"🚨 Teams notification error : {r.status_code} - {r.text}")
    except Exception as e:
        log_callback("🚨Teams notification error :", e)

def auto_loop(stop_event, log_callback, zone):
    log_callback(f"=== 🦕 Watcher started every ~{WAIT_INTERVAL} min) 🦕 ===")
    while not stop_event.is_set():
        texte = perform_ocr(zone)
        log_callback("\n--- OCR ---")
        log_callback(texte[:400] + "...\n")
        analyze_text(texte, log_callback)
        if stop_event.wait(WAIT_INTERVAL * 60):
            break
    log_callback("🛑 Watcher stopped.")

class MS_Watcher:
    # --- Fonctions UI ---
    def __init__(self, root):
        self.root = root
        self.root.title("MS Watcher")
        self.root.geometry("720x520")
        self.root.resizable(False, False)

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