"""Substrate Agent — Phase 4: Generator-Critic pipeline with dual-memory context."""

from __future__ import annotations

from typing import Callable

from google import genai
from google.genai import types

from critic import SubstrateCritic
from memory import SubstrateMemory
from prompt import SYSTEM_PROMPT


class SubstrateAgent:
    """Orchestrates dual-memory context assembly, LLM generation, and Critic audit."""

    def __init__(
        self,
        api_key: str,
        memory: SubstrateMemory,
        model: str = "gemini-2.5-flash",
    ) -> None:
        """
        Initialise the agent and its Critic.

        Args:
            api_key: Google Gemini API key.
            memory: A SubstrateMemory instance for dual read/write.
            model: Model identifier (default: gemini-2.5-flash).
        """
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.memory = memory
        self.critic = SubstrateCritic(api_key=api_key, model=model)

    def _assemble_context(self, user_input: str) -> list[types.Content]:
        """
        Build the context window from both memory sources + new prompt.

        Source A (Semantic):  Top 2 similar past interactions from ChromaDB.
        Source B (Chronological): Last 10 messages from the current session via SQLite.
        """
        contents: list[types.Content] = []

        # ── Source A: Semantic recall (cross-session) ─────────────────
        similar = self.memory.get_similar(user_input, n=2)
        if similar:
            past_context = "\n---\n".join(similar)
            injection = (
                "The following are semantically relevant interactions from previous sessions.\n"
                "STRICT RULE: If this past context is not fundamentally related to the "
                "current axiom, IGNORE IT ENTIRELY.\n\n"
                f"<Past_Context>\n{past_context}\n</Past_Context>"
            )
            contents.append(
                types.Content(role="user", parts=[types.Part(text=injection)])
            )
            contents.append(
                types.Content(
                    role="model",
                    parts=[types.Part(text=(
                        "Acknowledged. I have reviewed the past context. "
                        "I will only reference it if it is fundamentally related "
                        "to the current analysis."
                    ))],
                )
            )

        # ── Source B: Chronological recall (current session) ──────────
        recent = self.memory.get_recent(n=10)
        for msg in recent:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part(text=msg["content"])])
            )

        # ── New user prompt ───────────────────────────────────────────
        contents.append(
            types.Content(role="user", parts=[types.Part(text=user_input)])
        )

        return contents

    def _generate(self, contents: list[types.Content]) -> str:
        """Call the Generator LLM and return the raw text."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.1,
                top_p=0.8,
            ),
        )
        return response.text or ""

    # ── Required output sections ──────────────────────────────────────
    REQUIRED_SECTIONS = [
        "THE ATOMIC DECONSTRUCTION",
        "WEAK ASSUMPTIONS",
        "THE HIGH-LEVERAGE TWEAK",
        "LOGICAL DERIVATION",
        "THE CONTRARIAN VIEW",
    ]

    def _validate_structure(self, text: str) -> tuple[bool, list[str]]:
        """Verify the response contains all 5 required Substrate sections."""
        missing = [
            section for section in self.REQUIRED_SECTIONS
            if section not in text.upper()
        ]
        return len(missing) == 0, missing

    def run(
        self,
        user_input: str,
        on_audit_start: Callable[[], object] | None = None,
        on_audit_end: Callable[[], None] | None = None,
    ) -> tuple[str, dict]:
        """
        Full Generator → Critic pipeline.

        1. Assemble context from dual memory.
        2. Generate a response (Generator).
        3. Audit the response (Critic).
        4. If FAIL: re-generate once with the Critic's reason appended.
        5. Validate structure and dual-save.

        Args:
            user_input: The user's idea, constraint, or follow-up.
            on_audit_start: Optional callback invoked when the audit phase begins.
            on_audit_end: Optional callback invoked when the audit phase ends.

        Returns:
            (response_text, audit_info) where audit_info contains:
                - "passed": bool (first audit result)
                - "reason": str (critic's reason if failed)
                - "regenerated": bool (whether a re-generation occurred)
        """
        contents = self._assemble_context(user_input)

        # ── Generation (attempt 1) ────────────────────────────────────
        assistant_text = self._generate(contents)

        # ── Critic audit ──────────────────────────────────────────────
        ctx = None
        if on_audit_start:
            ctx = on_audit_start()

        passed, reason = self.critic.audit(assistant_text)
        audit_info = {"passed": passed, "reason": reason, "regenerated": False}

        if not passed:
            # Re-generate with the Critic's feedback appended
            contents.append(
                types.Content(role="model", parts=[types.Part(text=assistant_text)])
            )
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text=(
                        f"Your previous response was audited and FAILED for this reason: "
                        f"{reason}\n\n"
                        "Please re-generate your deconstruction, fixing the identified flaw. "
                        "Maintain the strict 5-section output structure."
                    ))],
                )
            )
            assistant_text = self._generate(contents)
            audit_info["regenerated"] = True

        if on_audit_end and ctx is not None:
            on_audit_end()

        # ── Structure validation ──────────────────────────────────────
        is_valid, missing = self._validate_structure(assistant_text)
        if not is_valid:
            missing_list = ", ".join(missing)
            assistant_text += (
                f"\n\n---\n> ⚠️ **Structure Warning:** The following required sections "
                f"were missing from this response: {missing_list}. "
                f"Consider re-prompting for a complete deconstruction."
            )

        # ── Dual-write to SQLite + ChromaDB ───────────────────────────
        self.memory.save(user_input, assistant_text)

        return assistant_text, audit_info
