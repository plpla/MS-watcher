import socket
import threading
import json
import pyautogui
from ollama import Client
from PIL import Image
import requests
import time
import datetime
import os
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

def perform_vision(client_socket, zone=None):
    """Takes a screenshot from a zone and send it to Ollama for interpretation"""
    screenshot_path = "capture.png"
    if zone:
        x, y, w, h = zone
        image = pyautogui.screenshot(region=(x, y, w, h))
    else:
        image = pyautogui.screenshot()
    image.save(screenshot_path)
    result = analyze_image_ollama(screenshot_path, client_socket, url=URL)
    print(result)
    notify_teams(INSTRUMENT, result, client_socket)

def notify_teams(sender, messages, client_socket):
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
            send_log(client_socket, "Notification sent!")
        else:
            send_log(client_socket, f"Teams notification error : {r.status_code} - {r.text}")
    except Exception as e:
        send_log(client_socket, f"Teams notification error : {e}")

def analyze_image_ollama(screenshot_path, client_socket, url=URL):
    
    with open(screenshot_path, "rb") as screenshot:
        images_to_bytes = base64.b64encode(screenshot.read())

    prompt = ""
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        prompt = f.read()

    if prompt == "":
        print("Error: prompt is empty")
        return {"state": "error", "summary": "LLM prompt is empty"}
    
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "images": [images_to_bytes.decode('utf-8')],
        "stream": False
    }
    try:
        send_log(client_socket, "Sending screenshot to Ollama...")
        r = requests.post(url, json=payload, timeout=300)
        r.raise_for_status()
        result = r.json()
        response_text = str(result.get("response", "").strip())
        #print(response_text)
        send_log(client_socket, "Got an answer!")
        return response_text
    except Exception as e:
        print(f"Error Ollama: {e}")
        return {"state": "error", "summary": str(e)}

def send_log(client_socket, message):
    try:
        data = json.dumps({"log": message})
        client_socket.sendall(data.encode('utf-8') + b'\n')
    except:
        pass  # Client disconnected

def auto_loop(stop_event, client_socket, zone):
    send_log(client_socket, f"=== Watcher started every ~{WAIT_INTERVAL} min) ===")
    while not stop_event.is_set():
        perform_vision(client_socket, zone)
        if stop_event.wait(WAIT_INTERVAL * 60):
            break
    send_log(client_socket, "Watcher stopped.")

def handle_client(client_socket):
    stop_event = threading.Event()
    thread = None
    zone = None
    buffer = ""
    while True:
        try:
            data = client_socket.recv(1024)
            if not data:
                break
            buffer += data.decode('utf-8')
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if line.strip():
                    message = json.loads(line)
                    command = message.get("command")
                    if command == "start":
                        if thread and thread.is_alive():
                            send_log(client_socket, "Already running")
                        else:
                            zone = tuple(message.get("zone"))
                            stop_event.clear()
                            thread = threading.Thread(target=auto_loop, args=(stop_event, client_socket, zone))
                            thread.start()
                            send_log(client_socket, "Watching!")
                    elif command == "stop":
                        stop_event.set()
                        if thread:
                            thread.join()
                        send_log(client_socket, "Stop requested")
        except:
            break
    if thread and thread.is_alive():
        stop_event.set()
        thread.join()
    client_socket.close()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', 12345))
    server_socket.listen(1)
    print("Server listening on port 12345")
    while True:
        client_socket, addr = server_socket.accept()
        print(f"Connection from {addr}")
        threading.Thread(target=handle_client, args=(client_socket,)).start()

if __name__ == "__main__":
    main()