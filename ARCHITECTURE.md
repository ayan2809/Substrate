# Substrate Context Engine — Deep Architecture

> A technical deep-dive into how Substrate assembles, validates, and persists context across every reasoning cycle.

---

## 1. System Overview

The context engine is the core of Substrate. It is responsible for answering one question before every LLM call: **"What information does the model need to produce a first-principles analysis right now?"**

The engine is distributed across four files:

| File | Role in the Context Engine |
|------|---------------------------|
| `memory.py` | **Storage layer** — dual-write and dual-read across SQLite + ChromaDB |
| `agent.py` | **Orchestrator** — assembles context, calls the LLM, invokes the Critic, triggers saves |
| `critic.py` | **Auditor** — a second LLM pass that validates logical integrity before output reaches the user |
| `prompt.py` | **Identity** — the system instruction that shapes all LLM behavior |

### Execution Flow (Single Prompt)

```
User types a prompt
       │
       ▼
┌─────────────────────────────────────────────┐
│  CONTEXT ASSEMBLY  (agent._assemble_context) │
│                                             │
│  1. ChromaDB.get_similar(prompt, n=2)       │──→ Source A: Semantic recall
│  2. SQLite.get_recent(n=10)                 │──→ Source B: Chronological recall
│  3. Append the new user prompt              │──→ Source C: Current input
│                                             │
│  Output: list[Content]                      │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  GENERATION  (agent._generate)              │
│                                             │
│  Gemini API call with:                      │
│  • system_instruction = SYSTEM_PROMPT       │
│  • temperature = 0.1                        │
│  • top_p = 0.8                              │
│  • contents = assembled context             │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  CRITIC AUDIT  (critic.audit)               │
│                                             │
│  Separate Gemini API call with:             │
│  • system_instruction = CRITIC_PROMPT       │
│  • temperature = 0.0                        │
│  • top_p = 0.8                              │
│                                             │
│  Output: PASS  or  FAIL: [reason]           │
├─────────────────────────────────────────────┤
│  If FAIL:                                   │
│    Append failed response + reason           │
│    Re-generate (1 retry max)                │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  STRUCTURE VALIDATION                       │
│  (_validate_structure)                      │
│                                             │
│  Check for 5 required sections:             │
│  ☐ THE ATOMIC DECONSTRUCTION               │
│  ☐ WEAK ASSUMPTIONS                        │
│  ☐ THE HIGH-LEVERAGE TWEAK                 │
│  ☐ LOGICAL DERIVATION                      │
│  ☐ THE CONTRARIAN VIEW                     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  DUAL-WRITE  (memory.save)                  │
│                                             │
│  SQLite:  2 rows  (user + model)            │
│  ChromaDB: 1 doc  (combined interaction)    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
           Response reaches terminal
```

---

## 2. Memory Layer (`memory.py`)

### 2.1 Storage Topology

```
~/.substrate/                        ← Created on first run
├── substrate.db                     ← SQLite database (single file)
└── chroma_db/                       ← ChromaDB persistent store
    ├── chroma.sqlite3               ← ChromaDB's internal metadata
    └── <collection-uuid>/           ← Embedding data files
```

Both stores live under `~/.substrate/` (user's home directory), completely decoupled from the project source. This means:
- Data survives across project directory moves
- Multiple terminals can share the same memory
- `git` never touches the data (it's outside the repo)

### 2.2 Initialization Sequence

```python
SubstrateMemory.__init__()
│
├─ mkdir ~/.substrate/                      # Ensure dir exists
├─ self.session_uuid = uuid4().hex          # 32-char hex string
│
├─ SQLite:
│   ├─ sqlite3.connect(~/.substrate/substrate.db)
│   ├─ row_factory = sqlite3.Row            # Dict-like access
│   └─ CREATE TABLE IF NOT EXISTS sessions  # Idempotent schema
│
└─ ChromaDB:
    ├─ PersistentClient(path=~/.substrate/chroma_db/)
    └─ get_or_create_collection("substrate_insights")
```

**Key design decision:** The session UUID is generated fresh on every `SubstrateMemory()` instantiation — i.e., every time you run `python main.py start`. There is no session resume. Each CLI invocation is a new session with a new UUID.

### 2.3 SQLite Schema

```sql
CREATE TABLE sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,   -- monotonic ordering
    session_uuid TEXT    NOT NULL,                      -- groups messages by session
    timestamp    TEXT    NOT NULL,                      -- ISO 8601 UTC
    role         TEXT    NOT NULL,                      -- "user" or "model"
    content      TEXT    NOT NULL                       -- raw text
);
```

**Design notes:**
- `id` is `AUTOINCREMENT` — this guarantees strictly monotonic ordering, which is critical for `ORDER BY id DESC LIMIT n` to produce correct chronological recall
- `session_uuid` is a filter, not a foreign key — there is no separate sessions table. This is intentional: the schema is flat for simplicity and query speed
- `role` uses `"user"` and `"model"` to match Gemini's API vocabulary directly — no mapping needed at read time
- `timestamp` is stored as ISO 8601 text, not a datetime column, because SQLite has no native datetime type and text sorting on ISO 8601 is lexicographically correct

### 2.4 ChromaDB Collection

| Property | Value |
|----------|-------|
| **Collection name** | `substrate_insights` |
| **Client type** | `PersistentClient` (writes to disk) |
| **Embedding model** | ChromaDB's built-in default (all-MiniLM-L6-v2) |
| **Document format** | `"User: {input}\nSubstrate: {response}"` |
| **Metadata** | `session_uuid`, `timestamp` |
| **ID** | Fresh `uuid4().hex` per interaction |

**Why one combined document instead of two?**
Embedding the user input and model response together captures the full semantic meaning of the *interaction*. A query like "pet food delivery" would match a document containing both the user's pet-related question AND Substrate's analysis of it — giving richer recall than matching just the question alone.

### 2.5 Dual-Write Protocol

```python
def save(user_input, model_response):
    now = utc_timestamp()
    interaction_id = uuid4().hex

    # Write 1: SQLite (two rows)
    INSERT (session_uuid, now, "user",  user_input)
    INSERT (session_uuid, now, "model", model_response)
    COMMIT

    # Write 2: ChromaDB (one document)
    collection.upsert(
        ids    = [interaction_id],
        docs   = ["User: {input}\nSubstrate: {response}"],
        meta   = {session_uuid, timestamp}
    )
```

**Atomicity:** The two writes are NOT transactional across stores. If SQLite succeeds but ChromaDB fails (extremely unlikely with local disk), you lose semantic recall for that interaction but retain chronological history. This is an acceptable trade-off — chromaDB failures don't corrupt the session.

**`upsert` vs `add`:** Using `upsert` with a unique UUID means idempotent writes. If the same save is somehow called twice, it overwrites rather than duplicating.

### 2.6 Read: Chronological (`get_recent`)

```sql
SELECT role, content FROM sessions
WHERE session_uuid = ?
ORDER BY id DESC
LIMIT ?
```

Then `reversed()` in Python to restore chronological order.

**Why `DESC` + `reversed()` instead of `ASC` + `LIMIT`?**
SQLite's `LIMIT` with `ORDER BY ASC` would give you the *first* N messages, not the *last* N. To get the most recent N, you must order descending, take N, then reverse in application code.

**Window size:** Fixed at 10 messages (5 user/model pairs). This is a deliberate constraint:
- 10 messages is enough to maintain conversational flow without blowing up the context window
- At ~500 tokens per message, this is ~5,000 tokens — roughly 5% of a 100K context window
- Prevents token budget starvation when combined with Source A and the system prompt

### 2.7 Read: Semantic (`get_similar`)

```python
def get_similar(query, n=2):
    total = collection.count()
    if total == 0:          # Cold-start safety
        return []

    actual_n = min(n, total)
    results = collection.query(
        query_texts=[query],
        n_results=actual_n,
    )
    return results["documents"][0]
```

**Cold-start handling:** On first-ever use, the collection is empty. `collection.query()` with `n_results > count` would throw an error. The `min(n, total)` guard and the `count == 0` early return prevent this.

**Why top 2, not top 5?**
- Semantic matches are approximate — the further you go beyond top-2, the more noise you inject
- Each match is a full interaction (user + model response) — easily 1,000+ tokens. Top 2 = ~2,000 tokens
- Combined with Source B (10 messages, ~5,000 tokens) and the system prompt (~600 tokens), this keeps total context under ~8,000 tokens — plenty of headroom for the model's response

---

## 3. Context Assembly (`agent._assemble_context`)

This is the function that runs before every LLM call. It builds a `list[Content]` that becomes the `contents` argument to Gemini's `generate_content`.

### 3.1 Assembly Order

```
Position in contents[]:

[0-1]  Source A: Semantic recall (if available)
       ├─ [0] user:  "<Past_Context>...</Past_Context>" + strict ignore rule
       └─ [1] model: "Acknowledged. I will only reference if related."

[2..N] Source B: Chronological recall (last 10 from SQLite)
       ├─ user: "..." 
       ├─ model: "..."
       └─ ... (up to 10 messages)

[N+1]  New user prompt
       └─ user: "the actual thing the user just typed"
```

**The order matters.** By placing semantic recall *before* chronological recall, the model sees long-term context first, then the recent conversation, then the new prompt. This mimics how humans contextualize: background knowledge → recent discussion → current question.

### 3.2 Source A: Semantic Injection

When ChromaDB returns matches, they're wrapped in a carefully structured injection:

```
The following are semantically relevant interactions from previous sessions.
STRICT RULE: If this past context is not fundamentally related to the
current axiom, IGNORE IT ENTIRELY.

<Past_Context>
User: [past user input]
Substrate: [past model response]
---
User: [another past input]
Substrate: [another past response]
</Past_Context>
```

Followed by a synthetic model acknowledgment:

```
Acknowledged. I have reviewed the past context.
I will only reference it if it is fundamentally related
to the current analysis.
```

**Why the synthetic user/model pair?**
Gemini's API expects alternating `user` → `model` turns. You can't just inject context as a system message mid-conversation. By wrapping it as a user message with a model acknowledgment, we:
1. Maintain valid turn structure
2. Prime the model to selectively use the context rather than blindly incorporating it
3. The "IGNORE IT ENTIRELY" instruction acts as a hard guard against irrelevant context pollution

### 3.3 Source B: Chronological Replay

```python
recent = memory.get_recent(n=10)
for msg in recent:
    role = "user" if msg["role"] == "user" else "model"
    contents.append(Content(role=role, parts=[Part(text=msg["content"])]))
```

These are replayed verbatim from SQLite. The model sees its own prior responses as if it had just generated them, which is what enables follow-ups like "change assumption #2."

### 3.4 Context Budget

| Component | Typical size | Source |
|-----------|-------------|--------|
| System prompt | ~600 tokens | `prompt.py` (fixed) |
| Source A (semantic, 2 matches) | ~2,000 tokens | ChromaDB |
| Synthetic acknowledgment | ~40 tokens | Hardcoded |
| Source B (last 10 messages) | ~5,000 tokens | SQLite |
| New user prompt | ~50-200 tokens | User input |
| **Total context** | **~8,000 tokens** | |
| Model response headroom | ~92,000 tokens | Gemini 2.5 Flash (1M window) |

With Gemini's 1M token context window, the engine uses less than 1% of available capacity. This is by design — headroom ensures the model never truncates its reasoning.

---

## 4. Generation Pipeline (`agent.run`)

### 4.1 Generator Configuration

```python
GenerateContentConfig(
    system_instruction = SYSTEM_PROMPT,     # 600-token identity prompt
    temperature = 0.1,                      # Near-deterministic
    top_p = 0.8,                            # Constrained sampling
)
```

**`temperature=0.1`:** On a scale of 0.0 (fully deterministic) to 2.0 (maximum randomness), 0.1 is almost deterministic. The same prompt will produce nearly identical responses across runs. This eliminates creative drift — Substrate produces precise causal chains, not brainstorms.

**`top_p=0.8`:** Only the top 80% of the probability distribution is sampled. This cuts the long tail of unlikely tokens — the ones responsible for hallucinated facts and invented terminology.

**Why not `temperature=0.0`?**
At exactly 0.0, the model is fully greedy (always picks the highest-probability token). This can cause repetition loops in long outputs. 0.1 adds just enough entropy to avoid degenerate behavior while staying highly deterministic.

### 4.2 Critic Audit (`critic.audit`)

The Critic is a **separate LLM call** with its own system prompt:

```python
GenerateContentConfig(
    system_instruction = CRITIC_SYSTEM_PROMPT,
    temperature = 0.0,      # Fully deterministic (short binary output)
    top_p = 0.8,
)
```

**Why `temperature=0.0` for the Critic but 0.1 for the Generator?**
The Critic produces a binary output (`PASS` or `FAIL: reason`). There's no need for entropy in a yes/no decision. Full determinism ensures consistent audit behavior.

**What the Critic checks:**

| Check | What It Catches |
|-------|----------------|
| Logical leaps | "X therefore Y" where Y doesn't follow from X |
| Fake economic principles | Invented laws presented as established economics |
| Hallucinated facts | Statistics or studies cited without basis |
| Circular reasoning | Arguments that assume their own conclusion |
| Missing causal mechanisms | "This will increase engagement" without explaining *how* |

**Graceful degradation:** If the Critic returns something that isn't `PASS` or `FAIL:...` (unexpected API behavior), the engine treats it as `PASS` to avoid blocking the user.

### 4.3 Re-Generation on Failure

When the Critic returns `FAIL`:

```python
# Append the failed response as context
contents.append(Content(role="model", parts=[Part(text=failed_response)]))

# Append the critic's feedback as a user instruction
contents.append(Content(role="user", parts=[Part(text=
    f"Your previous response was audited and FAILED for this reason: {reason}\n\n"
    "Please re-generate your deconstruction, fixing the identified flaw. "
    "Maintain the strict 5-section output structure."
)]))

# Re-generate (same parameters, enriched context)
assistant_text = self._generate(contents)
```

**Key design decisions:**
- **One retry maximum** — prevents infinite loops between Generator and Critic
- **Full context preserved** — the re-generation sees everything: both memory sources, the original prompt, the failed response, AND the critic's reason
- **The model corrects itself** — it sees what it wrote, sees why it was wrong, and can specifically fix that flaw
- **Only the corrected response is saved** — the failed attempt is never persisted to SQLite or ChromaDB

### 4.4 Structure Validation

After the Critic passes (or after re-generation), the response is checked for structural completeness:

```python
REQUIRED_SECTIONS = [
    "THE ATOMIC DECONSTRUCTION",
    "WEAK ASSUMPTIONS",
    "THE HIGH-LEVERAGE TWEAK",
    "LOGICAL DERIVATION",
    "THE CONTRARIAN VIEW",
]

# Case-insensitive substring check
missing = [s for s in REQUIRED_SECTIONS if s not in text.upper()]
```

This catches cases where the model produces logically sound content (passes Critic) but skips a section. A warning is appended to the output with the specific missing section names.

---

## 5. Dual-Write Persistence

After all validation, `memory.save(user_input, final_response)` executes the dual-write:

```
Save Event
│
├─ SQLite:
│   INSERT user  (session_uuid, timestamp, "user",  user_input)
│   INSERT model (session_uuid, timestamp, "model", final_response)
│   COMMIT
│
└─ ChromaDB:
    UPSERT document = "User: {input}\nSubstrate: {response}"
    WITH id = new uuid4
    WITH metadata = {session_uuid, timestamp}
```

**The write happens AFTER validation, not before.** This means:
- Failed generations are never persisted
- Only audited, structurally validated responses enter the memory stores
- This keeps the semantic index clean — no flawed reasoning pollutes future recalls

---

## 6. Edge Cases & Safety

| Scenario | Behavior |
|----------|----------|
| **First-ever run** | `~/.substrate/` created, empty SQLite table created, empty ChromaDB collection created. Sources A and B return empty. Only the new prompt + system prompt go to the LLM. |
| **ChromaDB has fewer docs than `n`** | `min(n, total)` prevents the query from requesting more results than exist. |
| **ChromaDB is empty** | `count() == 0` check returns `[]` immediately — no query is attempted. |
| **Critic returns unexpected output** | Treated as `PASS` — the user is never blocked by Critic misbehavior. |
| **API error during generation** | Exception propagates to `main.py`, which catches it and prints the error without crashing the REPL. |
| **API error during audit** | Same — exception propagates and is caught. |
| **User presses Ctrl+C** | `KeyboardInterrupt` caught in `main.py`, `memory.close()` called, SQLite connection closed cleanly. |
| **Multiple terminals** | Both use the same `substrate.db` file. SQLite handles concurrent reads. Concurrent writes are serialized by SQLite's file-level lock. |

---

## 7. Data Flow Summary

```
                    ┌──────────────────────────────────────┐
                    │         ~/.substrate/                 │
                    │                                      │
                    │  substrate.db     chroma_db/         │
                    │  ┌──────────┐    ┌──────────────┐   │
                    │  │ sessions │    │ substrate_    │   │
                    │  │          │    │ insights      │   │
     WRITE ─────────│──│ 2 rows   │    │ 1 document   │───│── WRITE
     (after audit)  │  │ per call │    │ per call     │   │  (after audit)
                    │  └─────┬────┘    └──────┬───────┘   │
                    │        │                │            │
                    │   READ │           READ │            │
                    │   (last 10,        (top 2,           │
                    │    current          all sessions,    │
                    │    session)         by meaning)      │
                    │        │                │            │
                    └────────┼────────────────┼────────────┘
                             │                │
                             ▼                ▼
                    ┌────────────────────────────────────┐
                    │   _assemble_context()               │
                    │                                    │
                    │   Source B (chrono) + Source A (sem) │
                    │   + new user prompt                 │
                    │   = list[Content]                   │
                    └────────────────┬───────────────────┘
                                    │
                                    ▼
                    ┌────────────────────────────────────┐
                    │   Gemini API                        │
                    │   system_instruction + contents     │
                    └────────────────────────────────────┘
```

---

## 8. Architectural Evaluation (Pros & Cons)

Any architecture is a set of trade-offs. Here is an honest evaluation of the Substrate context engine:

### ✅ Pros (Why this works well)

1. **Zero Infrastructure Overhead:** By using embedded SQLite and local ChromaDB, the agent runs entirely self-contained. There are no databases to spin up, no Docker containers, and no cloud dependencies other than the LLM API itself.
2. **True "Long-Term" Feel:** Separating chronological from semantic memory solves the classic LLM window problem. The model remembers what you said 30 seconds ago *and* applies related insights from 3 months ago without manual prompting.
3. **High Signal-to-Noise Ratio:** The Critic pipeline and `top_p=0.8` constraints brutally filter out the typical AI "fluff." Users only see audited, structurally sound logic, which builds trust.
4. **Self-Healing Output:** The single re-generation attempt allows the model to catch its own hallucinations and correct them before the user ever sees them.
5. **Data Privacy / Ownership:** All interaction history lives strictly on the user's local disk in `~/.substrate/`. 

### ⚠️ Cons (The Trade-offs)

1. **High Latency (No Streaming):** Because the Critic must evaluate the *full* generated response to determine logical integrity, we cannot stream tokens to the terminal. The user waits for the entire Generator call *plus* the Critic call to finish before seeing a single byte of output. If a re-generation is triggered, latency essentially triples.
2. **Token Cost Inflation:** Every prompt sends the system instructions (~600 tokens), the past 10 messages (~5k tokens), and 2 long-term insights (~2k tokens). This makes every prompt computationally "heavy."
3. **Semantic Blind Spots:** ChromaDB retrieves by vector similarity. If a user asks about "supply chain logistics," it will retrieve past queries about "shipping routes" (high similarity). But it might miss a past query about "data pipeline bottlenecks" (low textual similarity, but high structural/first-principles similarity).
4. **Monotonic Storage Growth:** The `~/.substrate/` directory strictly grows over time. There is currently no pruning, TTL (Time To Live), or session archiving mechanism. Over thousands of interactions, ChromaDB embeddings will consume significant disk space.
5. **Coupled Semantic Context:** Because user inputs and model responses are embedded together as single documents in ChromaDB, the embedding represents the *average* meaning of the interaction. Highly nuanced user prompts might get "watered down" by the larger volume of the model's response text during vector search.
