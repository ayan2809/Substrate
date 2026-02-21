<p align="center">
  <img src="https://img.shields.io/badge/version-1.0-cyan?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/LLM-Gemini%202.0%20Flash-orange?style=for-the-badge&logo=google&logoColor=white" alt="Gemini">
  <img src="https://img.shields.io/badge/platform-macOS-lightgrey?style=for-the-badge&logo=apple&logoColor=white" alt="macOS">
</p>

<h1 align="center">⚛️ Substrate</h1>

<p align="center">
  <strong>A First-Principles Reasoning Agent for Your Terminal</strong><br>
  <em>Recursive Deconstruction · Highest Leverage · Zero Jargon</em>
</p>

---

## What is Substrate?

Substrate is a **Mac-native CLI tool** that takes any idea — a product concept, a business strategy, a technical architecture — and ruthlessly deconstructs it using **First Principles thinking**.

It doesn't brainstorm. It doesn't validate. It **stress-tests**.

> *"Strip every idea of marketing jargon. What is the actual movement of data, value, or energy?"*

---

## ✨ Features

### 🔬 Atomic Deconstruction
Every idea is broken into its **non-reducible components** — data flows, value chains, and energy movements. No hand-waving. No buzzwords.

### 🎯 Assumption Auditing
Substrate identifies the top assumptions your idea relies on and flags the **fragile** ones — especially those based on analogy ("Uber for X") rather than foundational truth.

### ⚡ High-Leverage Tweaks
Instead of a laundry list of features, Substrate finds the **single smallest change** that produces disproportionate impact. The 10% input → 50% output variable.

### 🔴 Built-In Red Teaming
Every analysis includes a **Contrarian View** — a rigorous argument for why the proposed tweak might fail, grounded in fundamental laws of human behavior or economics.

### 💬 Session Memory
Substrate maintains full **conversational context** within a session. Refine your idea iteratively:
```
You:       "A food delivery app for pets"
Substrate: [Full 5-section deconstruction]
You:       "Actually, change assumption #2 — pet owners DO want a dedicated app"
Substrate: [Refined analysis with updated assumptions]
```

### 🎨 Rich Terminal UI
- ASCII art banner on startup
- Colorized, formatted Markdown output via [Rich](https://github.com/Textualize/rich)
- Live spinner animation during LLM processing
- Clean prompt styling

### 🔌 Modular Architecture
```
substrate_cli/
├── main.py        # CLI interface (Typer + Rich)
├── agent.py       # LLM client & session memory
├── prompt.py      # System prompt (swap to customise reasoning style)
└── .env           # API key (gitignored)
```
Swap models by passing `--model`:
```bash
python main.py start --model gemini-2.0-flash
python main.py start --model gemini-2.5-pro-preview-05-06
```

---

## 🚀 Quick Start

```bash
# Clone
git clone git@github.com:ayan2809/Substrate.git
cd Substrate/substrate_cli

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
echo "GEMINI_API_KEY=your-key-here" > .env

# Run
python main.py start
```

---

## 🧠 The Substrate Thinking Protocol

For every idea you submit, Substrate internally executes:

| Step | What It Does |
|------|-------------|
| **Core Axiom** | Identifies the one fundamental truth the idea depends on |
| **Assumption Audit** | Lists the top 3 assumptions; flags analogous vs. foundational |
| **Leverage Point** | Finds the single variable with disproportionate impact |
| **Red Team** | Argues why the tweak might fail using first principles |

The output is always structured into **5 clear sections**:

1. **The Atomic Deconstruction** — Non-reducible components
2. **Weak Assumptions** — Where the idea is fragile
3. **The High-Leverage Tweak** — One specific, small adjustment
4. **Logical Derivation** — Why the tweak works (first principles only)
5. **The Contrarian View** — Why it might still be waste

---

## 🛠 Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| CLI Framework | [Typer](https://typer.tiangolo.com/) |
| Terminal UI | [Rich](https://rich.readthedocs.io/) |
| LLM | [Google Gemini 2.0 Flash](https://ai.google.dev/) |
| Env Management | [python-dotenv](https://github.com/theskumar/python-dotenv) |

---

## 📄 License

MIT

---

<p align="center">
  <strong>Think clearly. Build less. Leverage more.</strong>
</p>
