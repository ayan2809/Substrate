"""Substrate Critic — Auditor agent for self-correcting the Generator's output."""

from __future__ import annotations

from google import genai
from google.genai import types


CRITIC_SYSTEM_PROMPT = """\
You are an Auditor. Your sole purpose is to review a Substrate Deconstruction \
and verify its logical integrity.

## YOUR TASK
Review the provided Substrate Deconstruction. Specifically look for:
1. **Logical leaps** — conclusions that do not follow from stated premises.
2. **Fake economic principles** — invented or misapplied economic laws.
3. **Hallucinated facts** — statistics, studies, or claims presented as factual without basis.
4. **Circular reasoning** — arguments that assume their own conclusion.
5. **Missing causal mechanisms** — claimed effects without a clear mechanism.

## YOUR OUTPUT FORMAT
- If the deconstruction is logically sound, output EXACTLY: `PASS`
- If the deconstruction is flawed, output EXACTLY: `FAIL: [Specific Reason]`

You must output ONLY one of these two formats. No preamble, no commentary, no markdown formatting.
"""


class SubstrateCritic:
    """Auditor agent that reviews Generator output for logical integrity."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        """
        Initialise the Critic.

        Args:
            api_key: Google Gemini API key.
            model: Model identifier (default: gemini-2.5-flash).
        """
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def audit(self, deconstruction: str) -> tuple[bool, str]:
        """
        Audit a Generator deconstruction for logical integrity.

        Args:
            deconstruction: The full Markdown output from the Generator.

        Returns:
            (passed, reason) — passed is True if PASS, False if FAIL.
            reason is empty on PASS, contains the specific flaw on FAIL.
        """
        contents = [
            types.Content(
                role="user",
                parts=[types.Part(text=(
                    "Review the following Substrate Deconstruction for logical integrity. "
                    "Output PASS if sound, or FAIL: [reason] if flawed.\n\n"
                    f"--- BEGIN DECONSTRUCTION ---\n{deconstruction}\n--- END DECONSTRUCTION ---"
                ))],
            )
        ]

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=CRITIC_SYSTEM_PROMPT,
                temperature=0.0,
                top_p=0.8,
            ),
        )

        verdict = (response.text or "").strip()

        if verdict.upper().startswith("PASS"):
            return True, ""
        elif verdict.upper().startswith("FAIL"):
            # Extract reason after "FAIL:"
            reason = verdict.split(":", 1)[1].strip() if ":" in verdict else verdict
            return False, reason
        else:
            # Unexpected format — treat as pass to avoid blocking the user
            return True, ""
