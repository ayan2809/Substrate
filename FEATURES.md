# Substrate — Feature Documentation

> **Version 2.0** · Mac-native CLI · First-Principles Reasoning Agent

---

## Table of Contents
- [Core Reasoning Engine](#core-reasoning-engine)
- [Interactive REPL](#interactive-repl)
- [Model Browser](#model-browser)
- [Dual-Memory Architecture](#dual-memory-architecture)
- [Anti-Hallucination Guardrails](#anti-hallucination-guardrails)
- [Generator-Critic Audit Loop](#generator-critic-audit-loop)
- [Terminal UI](#terminal-ui)
- [Configuration & Extensibility](#configuration--extensibility)

---

## Core Reasoning Engine

Substrate is not a brainstorming tool. It performs **Recursive Deconstruction** on any idea to find the *Smallest Viable Tweak* with the *Highest Leverage*.

Every idea submitted is internally processed through a strict **Thinking Protocol**:

| Step | What It Does |
|------|-------------|
| **Core Axiom** | Identifies the one fundamental truth the idea depends on |
| **Assumption Audit** | Lists the top 3 assumptions; flags analogous vs. foundational |
| **Leverage Point** | Finds the single variable where a 10% improvement yields 50% impact |
| **Red Team** | Argues why the tweak might fail using first principles |

Every response is structured into **5 mandatory sections**:

1. **The Atomic Deconstruction** — Non-reducible components (data flows, value chains, energy movements)
2. **Weak Assumptions** — Where the idea is fragile, especially analogy-based thinking
3. **The High-Leverage Tweak** — One specific, small adjustment with disproportionate impact
4. **Logical Derivation (Reasoning)** — Why the tweak works, using first principles only
5. **The Contrarian View** — A rigorous argument for why the tweak might still be waste

---

## Interactive REPL

Start a session with:
```bash
python main.py start
```

### Session Features
- **Persistent prompt loop** — Submit ideas, receive analyses, refine iteratively
- **Session UUID** — Each session gets a unique identifier (displayed on startup as an 8-character prefix)
- **Conversational context** — Follow-up prompts retain full session history. Say *"change assumption #2"* and Substrate knows what you're referring to
- **Clean exit** — Type `exit`, `quit`, or press `Ctrl+C` for a graceful shutdown
- **Error resilience** — API errors are caught and displayed without crashing the REPL

### Example Session
```
[Substrate] Enter your idea or constraint (or type 'exit'):
> A subscription service for artisanal dog treats
⠸ Deconstructing to atoms...
⠼ Substrate is auditing its own logic...
✓ Audit passed.

### 1. THE ATOMIC DECONSTRUCTION
[... full 5-section analysis ...]

[Substrate] Enter your idea or constraint (or type 'exit'):
> Actually, change assumption #2 — pet owners DO want a dedicated app
⠸ Deconstructing to atoms...
⠼ Substrate is auditing its own logic...
✓ Audit passed.

### 1. THE ATOMIC DECONSTRUCTION
[... refined analysis with updated assumption ...]
```

---

## Model Browser

List all available Gemini models with:
```bash
python main.py models
```

Displays a formatted table with:
- **Model Name** — the identifier to use with `--model`
- **Display Name** — human-readable name
- **Description** — what the model does

Use any listed model:
```bash
python main.py start --model gemini-2.5-pro
python main.py start -m gemini-2.5-flash
```

**Default model:** `gemini-2.5-flash` (best balance of reasoning depth and speed)

---

## Dual-Memory Architecture

Substrate maintains two persistent memory stores at `~/.substrate/`:

### Short-Term Memory (SQLite)
- **File:** `~/.substrate/substrate.db`
- **Table:** `sessions(id, session_uuid, timestamp, role, content)`
- **Scope:** Current session only
- **Retrieval:** Last **10 messages** are loaded into the LLM context on every prompt
- **Purpose:** Maintains immediate conversational flow — follow-ups, refinements, rule-setting

### Long-Term Memory (ChromaDB)
- **Directory:** `~/.substrate/chroma_db/`
- **Collection:** `substrate_insights`
- **Scope:** All sessions, all time
- **Retrieval:** Top **2 semantically similar** past interactions are injected on every prompt
- **Purpose:** Cross-session recall — Substrate references relevant insights from previous sessions without you providing any IDs

### Dual-Write Pipeline
Every time you submit an idea and Substrate responds:
1. **SQLite** receives two rows (user + model) tagged with the current `session_uuid`
2. **ChromaDB** receives one combined document (`"User: {input}\nSubstrate: {response}"`) with automatic embedding

### Context Assembly
On each new prompt, the agent builds its LLM context from:

| Source | Store | What | Count |
|--------|-------|------|-------|
| **Source A** (Semantic) | ChromaDB | Most similar past interactions across all sessions | Top 2 |
| **Source B** (Chronological) | SQLite | Recent messages in current session | Last 10 |

Source A is injected as `<Past_Context>` with a strict guard rule:
> *"If this past context is not fundamentally related to the current axiom, IGNORE IT ENTIRELY."*

### Cold-Start Handling
When ChromaDB is empty (first use), retrieval returns an empty list gracefully — no crash, no error.

### Startup Display
```
Session efd662e7 started  ·  Model: gemini-2.5-flash  ·  3 insight(s) in long-term memory
```

---

## Anti-Hallucination Guardrails

### Parameter Tuning
The Generator LLM is mechanically restricted:

| Parameter | Value | Effect |
|-----------|-------|--------|
| `temperature` | `0.1` | Near-deterministic output; minimizes creative drift |
| `top_p` | `0.8` | Constrains token sampling to the 80th percentile of probability mass |

These are hardcoded in the `GenerateContentConfig` — the model produces tight, focused reasoning with precise causal chains instead of speculative filler.

### Structural Validation
After every response, the agent checks that all **5 required sections** are present:

1. THE ATOMIC DECONSTRUCTION
2. WEAK ASSUMPTIONS
3. THE HIGH-LEVERAGE TWEAK
4. LOGICAL DERIVATION
5. THE CONTRARIAN VIEW

If any section is missing, a warning is appended:
```
⚠️ Structure Warning: The following required sections were missing:
LOGICAL DERIVATION, THE CONTRARIAN VIEW.
Consider re-prompting for a complete deconstruction.
```

---

## Generator-Critic Audit Loop

Every response goes through a **two-agent pipeline** before reaching your terminal.

### How It Works
```
User Prompt
    ↓
┌─────────────────────┐
│  GENERATOR (Agent)  │  ← System prompt + dual memory context
│  temp=0.1, top_p=0.8│
└─────────┬───────────┘
          ↓
┌─────────────────────┐
│  CRITIC (Auditor)   │  ← Separate system prompt, temp=0.0
│  Checks for:        │
│  • Logical leaps    │
│  • Fake economics   │
│  • Hallucinated facts│
│  • Circular reasoning│
│  • Missing causality │
└─────────┬───────────┘
          ↓
    PASS? ──→ Output to terminal
    FAIL? ──→ Re-generate once with critic's reason appended
              ──→ Output to terminal
```

### Critic Verdicts
The Critic agent operates at `temperature=0.0` (fully deterministic) and outputs exactly one of:
- `PASS` — the deconstruction is logically sound
- `FAIL: [Specific Reason]` — a specific flaw was identified

### Re-Generation
On FAIL, the critic's reason is appended to the Generator's context and **one re-generation** occurs. This self-correcting loop ensures only audited logic reaches you.

### Terminal Display
```
✓ Audit passed.                           ← clean pass

⚠ Critic flagged: Missing causal mechanism ← flagged + re-generated
  in Section 4 connecting X to Y.
✓ Re-generated with fix applied.
```

### Spinners
The REPL shows distinct spinner phases:
1. `⠸ Deconstructing to atoms...` — Generator is working
2. `⠼ Substrate is auditing its own logic...` — Critic is reviewing

---

## Terminal UI

Built with [Rich](https://rich.readthedocs.io/) for a premium terminal experience:

- **ASCII art banner** on startup
- **Styled info panel** with version and tagline
- **Colorized Markdown rendering** — headers, bullet points, bold, emphasis all rendered natively in the terminal
- **Live spinners** with contextual messages (generation → audit)
- **Formatted tables** for the model browser
- **Color-coded messages** — green for success, yellow for warnings, red for errors, cyan for info

---

## Configuration & Extensibility

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |

Loaded from `substrate_cli/.env` or system environment.

### CLI Options
| Command | Option | Description |
|---------|--------|-------------|
| `start` | `--model` / `-m` | Override the default Gemini model |
| `models` | — | List all available models |

### Modular Architecture
```
substrate_cli/
├── main.py       # CLI entry point & REPL
├── agent.py      # Generator-Critic pipeline + context assembly
├── critic.py     # Auditor agent (swappable)
├── memory.py     # Dual storage layer (swappable)
├── prompt.py     # System prompt constant (swappable)
├── .env          # API key (gitignored)
└── .gitignore    # Protects secrets
```

Each module is independently replaceable:
- **Swap the model** → change `--model` flag or default in `agent.py`
- **Swap the reasoning style** → edit `prompt.py`
- **Swap the audit criteria** → edit `critic.py`
- **Swap the storage backend** → replace `memory.py`

---

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.11+ |
| CLI Framework | Typer | 0.9+ |
| Terminal UI | Rich | 13.0+ |
| LLM | Google Gemini | 2.5 Flash (default) |
| Short-Term Memory | SQLite | stdlib |
| Long-Term Memory | ChromaDB | 0.5+ |
| Env Management | python-dotenv | 1.0+ |
