# MS-Watcher

## Overview  
**MS-Watcher** is a simple application that monitors analytical chemistry instruments (such as LC-MS systems) by analyzing screenshots with a local multimodal LLM.  
The tool automatically:

- Captures a selectable region of the instrument control software  
- Sends the screenshot to a local LLM (e.g., via Ollama) for interpretation  
- Extracts instrument status (running, idle, error, etc.)  
- Sends the interpreted status to a Microsoft Teams channel using an Adaptive Card  
- Repeats automatically at a user-defined interval

We use it for automated monitoring of analytical chemistry instruments.

---

## Features  
- **Region-based screenshot monitoring** using PyAutoGUI to reduce LLM prompt size and increased focus on system parameters
- **Local LLM vision inference** Ollama compatible
- **Adaptive-Card notifications to Microsoft Teams**  
- **Fully configurable via `config.json`**  
- **Prompt stored in external text file** Editable without code!
- **Graphical interface (Tkinter)** for ease of use

---

## Installation

### Requirements
- Python **3.8+**
- A local LLM endpoint (e.g., **Ollama** with a vision model such as Qwen2.5-VL)
- Microsoft Teams webhook access. Configured throught Power Automate