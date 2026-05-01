<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Orbitron&size=36&duration=3000&pause=800&color=00D4FF&center=true&vCenter=true&width=700&lines=SMART+VIRTUAL+ASSISTANT;A.R.I.A+%E2%80%94+AI+Voice+%26+Chat+Engine;Built+with+Python+%F0%9F%90%8D" alt="ARIA Typing SVG" />

<br/>

<img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/AI%20Powered-NLP%20%7C%20Speech-00D4FF?style=for-the-badge&logo=googleassistant&logoColor=white" />
<img src="https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge" />
<img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" />
<img src="https://img.shields.io/badge/Version-2.0.0-purple?style=for-the-badge" />

<br/><br/>

> **ARIA** *(Advanced Responsive Intelligent Assistant)* is a fully voice-driven, AI-powered personal assistant built in Python — designed for productivity, accessibility, and smart automation.

<br/>

```
╔══════════════════════════════════════════════════════════╗
║   🤖  ARIA — SMART VIRTUAL ASSISTANT  v2.0              ║
║   Voice + Text Interface  |  Modular Architecture       ║
║   News • Weather • Email • Alarms • Wikipedia & more    ║
╚══════════════════════════════════════════════════════════╝
```

</div>

---

## 📋 Table of Contents

- [✨ Overview](#-overview)
- [🚀 Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [📸 Screenshots](#-screenshots)
- [⚙️ Setup & Installation](#️-setup--installation)
- [🔑 API Configuration](#-api-configuration)
- [💬 Voice Commands Reference](#-voice-commands-reference)
- [📁 Project Structure](#-project-structure)
- [🧠 How It Works](#-how-it-works)
- [🛠️ Technologies Used](#️-technologies-used)
- [🔮 Future Roadmap](#-future-roadmap)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## ✨ Overview

ARIA is a **Smart Virtual Assistant** built to bridge the gap between humans and technology through natural voice interaction. Originally conceived to empower **visually impaired individuals** and **students**, ARIA has grown into a full-featured AI productivity companion.

Unlike paid alternatives like Alexa or Cortana, ARIA is:
- 🔓 **Open-source** and fully customizable
- 🌐 **Multi-modal** — voice *and* text input
- 🧩 **Modular** — plug in new skills easily
- 🧠 **Smart** — routes commands using NLP intent matching
- ⚡ **Fast** — minimal latency with threaded background tasks

---

## 🚀 Features

<table>
<tr>
<td>

### 🎙️ Voice & NLP
- Natural speech recognition (Google STT)
- Human-like text-to-speech (pyttsx3)
- Intent-based command routing
- Ambient noise auto-calibration

</td>
<td>

### 🌍 Information
- Wikipedia smart search
- Live weather (OpenWeatherMap API)
- Top news headlines (NewsAPI)
- Random facts & jokes engine

</td>
</tr>
<tr>
<td>

### 📅 Productivity
- Threaded reminders (non-blocking)
- Alarm clock with AM/PM parsing
- Current time & date narration
- Google Search launcher

</td>
<td>

### 🌐 Web & Apps
- Open 10+ popular websites by voice
- YouTube video search & play
- Email composer & sender (Gmail SMTP)
- Dynamic URL opening

</td>
</tr>
<tr>
<td>

### 🧘 Wellbeing
- Motivational quote engine (10+ quotes)
- Joke teller with comedic timing
- Inspirational message on demand

</td>
<td>

### 🔧 System
- Modular config via `config.json`
- Structured logging to file + console
- Error handling & graceful recovery
- Voice mode / text mode toggle

</td>
</tr>
</table>

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER (Voice / Text)                       │
└─────────────────────────────────┬───────────────────────────┘
                                  │
                    ┌─────────────▼────────────┐
                    │   Speech Recognizer       │
                    │   (SpeechRecognition)     │
                    └─────────────┬────────────┘
                                  │ query string
                    ┌─────────────▼────────────┐
                    │   Command Router          │
                    │   route_command()         │
                    └──┬──────────────────────┬─┘
                       │                      │
          ┌────────────▼──┐         ┌─────────▼────────────┐
          │  Skill Module  │         │   Web / OS Action     │
          │  (Weather,    │         │   (webbrowser, SMTP,  │
          │   News, Wiki, │         │    OS commands)        │
          │   Jokes, etc.)│         └─────────┬────────────┘
          └────────────┬──┘                   │
                       └──────────┬───────────┘
                                  │
                    ┌─────────────▼────────────┐
                    │   Voice Engine            │
                    │   (pyttsx3 TTS)           │
                    └──────────────────────────┘
```

---

## 📸 Screenshots

| Voice Interaction | Terminal Output |
|:-----------------:|:---------------:|
| ![ss1](Screenshot%202023-04-27%20213238.jpg) | ![ss2](Screenshot%202023-04-27%20213320.jpg) |

| Wikipedia Search | Weather Fetch |
|:---------------:|:-------------:|
| ![ss3](Screenshot%202023-04-27%20213633.jpg) | ![ss4](Screenshot%202023-04-28%20124505.jpg) |

---

## ⚙️ Setup & Installation

### Prerequisites

- Python 3.10 or higher
- A working microphone (for voice mode)
- Internet connection (for APIs)

### 1. Clone the Repository

```bash
git clone https://github.com/Aranya2801/SMART-VIRTUAL-ASSISTANT.git
cd SMART-VIRTUAL-ASSISTANT
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note for Linux users:** Install PortAudio before PyAudio:
> ```bash
> sudo apt-get install portaudio19-dev python3-dev
> ```

### 4. Configure API Keys

```bash
cp config/config.json config/config.json
# Edit config/config.json with your keys (see below)
```

### 5. Run ARIA

```bash
python src/assistant.py
```

---

## 🔑 API Configuration

Edit `config/config.json`:

```json
{
  "mode": "voice",
  "WEATHER_API_KEY": "get from openweathermap.org",
  "NEWS_API_KEY":    "get from newsapi.org",
  "EMAIL":           "your-email@gmail.com",
  "EMAIL_PASSWORD":  "your-gmail-app-password",
  "default_city":    "Kolkata",
  "language":        "en-in"
}
```

| Key | Source | Required |
|-----|--------|----------|
| `WEATHER_API_KEY` | [openweathermap.org](https://openweathermap.org/api) | For weather |
| `NEWS_API_KEY` | [newsapi.org](https://newsapi.org) | For headlines |
| `EMAIL` + `EMAIL_PASSWORD` | Gmail App Password | For email |

> 🔐 **Security:** Never commit your `config.json` with real keys. It's already in `.gitignore`.

---

## 💬 Voice Commands Reference

| Category | Say... | Action |
|----------|--------|--------|
| **Wikipedia** | `"Wikipedia artificial intelligence"` | Searches and reads summary |
| **Weather** | `"Weather in Mumbai"` | Fetches live weather |
| **News** | `"What's the news today"` | Reads 5 top headlines |
| **Time** | `"What time is it"` | Tells current time |
| **Date** | `"Today's date"` | Tells current date |
| **Joke** | `"Tell me a joke"` | Tells a joke with timing |
| **Motivation** | `"Motivate me"` | Gives an inspirational quote |
| **Fact** | `"Tell me an interesting fact"` | Shares a random fact |
| **Open Site** | `"Open YouTube"` | Opens in browser |
| **YouTube** | `"Play lo-fi music on YouTube"` | Searches YouTube |
| **Google** | `"Search Python tutorials"` | Opens Google search |
| **Reminder** | `"Remind me to drink water"` | Sets threaded reminder |
| **Alarm** | `"Set an alarm"` | Interactive alarm setter |
| **Email** | `"Send email"` | Interactive email composer |
| **Calculate** | `"What is 25 times 4"` | Evaluates math expression |
| **Help** | `"What can you do"` | Lists capabilities |
| **Exit** | `"Stop"` / `"Goodbye"` | Exits gracefully |

---

## 📁 Project Structure

```
SMART-VIRTUAL-ASSISTANT/
│
├── 📂 src/
│   └── assistant.py          # Core engine (all modules)
│
├── 📂 config/
│   └── config.json           # API keys & settings (gitignored)
│
├── 📂 docs/
│   └── MINOR PROJECT REPORT 2.0.pdf
│
├── 📂 assets/
│   └── screenshots/          # UI screenshots
│
├── requirements.txt          # Python dependencies
├── .gitignore                # Excludes secrets & caches
├── LICENSE                   # MIT License
└── README.md                 # This file
```

---

## 🧠 How It Works

ARIA operates through a clean 4-stage pipeline:

```
1. LISTEN    →  Microphone input captured via SpeechRecognition
2. RECOGNIZE →  Google STT converts audio to text string
3. ROUTE     →  Intent matched via keyword patterns in route_command()
4. RESPOND   →  Skill module executes → pyttsx3 speaks the result
```

**Threaded Tasks** (reminders, alarms) run in background `daemon` threads — so ARIA keeps listening while waiting for a reminder trigger.

**Modular Design** — each capability (Weather, News, Email, etc.) is an independent class. Adding a new skill is as simple as:
1. Creating a new module class
2. Adding an `elif` branch in `route_command()`

---

## 🛠️ Technologies Used

<div align="center">

| Technology | Purpose |
|:----------:|:-------:|
| ![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) | Core language |
| ![SpeechRecognition](https://img.shields.io/badge/SpeechRecognition-Google%20STT-4285F4?style=flat-square&logo=google&logoColor=white) | Voice input |
| ![pyttsx3](https://img.shields.io/badge/pyttsx3-TTS%20Engine-orange?style=flat-square) | Voice output |
| ![Wikipedia](https://img.shields.io/badge/Wikipedia-API-grey?style=flat-square&logo=wikipedia) | Knowledge base |
| ![OpenWeatherMap](https://img.shields.io/badge/OpenWeatherMap-Weather%20API-orange?style=flat-square) | Live weather |
| ![NewsAPI](https://img.shields.io/badge/NewsAPI-Headlines-darkblue?style=flat-square) | News feed |
| ![Gmail SMTP](https://img.shields.io/badge/Gmail-SMTP-EA4335?style=flat-square&logo=gmail) | Email sending |
| ![Threading](https://img.shields.io/badge/Python-Threading-blue?style=flat-square) | Async tasks |

</div>

---

## 🔮 Future Roadmap

- [ ] 🧠 **LLM Integration** — Connect GPT/Gemini for open-ended conversation
- [ ] 🖼️ **GUI Dashboard** — Tkinter or PyQt5 visual interface
- [ ] 📱 **Mobile App** — Flask REST API + Android/iOS frontend
- [ ] 🌐 **Multi-language Support** — Hindi, Bengali, and more
- [ ] 🔌 **Smart Home** — Philips Hue, IFTTT webhook integration
- [ ] 🎵 **Spotify Integration** — Music playback by voice
- [ ] 📊 **Usage Analytics** — Local dashboard of command history
- [ ] 🔒 **Voice Authentication** — Speaker recognition for security

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

```bash
# Fork the repository
# Create your feature branch
git checkout -b feature/amazing-new-skill

# Commit your changes
git commit -m "feat: add amazing new skill"

# Push to your branch
git push origin feature/amazing-new-skill

# Open a Pull Request 🎉
```

Please follow:
- PEP 8 code style
- Add docstrings to new modules
- Update the Voice Commands table in README

---

## 👩‍💻 Author

<div align="center">

**Aranya Ghosh**
Student, KIIT University | Bhubaneswar, India

[![GitHub](https://img.shields.io/badge/GitHub-Aranya2801-181717?style=for-the-badge&logo=github)](https://github.com/Aranya2801)

*"Technology should be a bridge, not a barrier."*

</div>

---

## 📄 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---

<div align="center">

⭐ **Star this repo if ARIA helped you!** ⭐

*Made with ❤️ and Python 🐍*

</div>
