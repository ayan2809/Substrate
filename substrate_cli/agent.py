"""Substrate Agent — LLM integration with session memory (Google Gemini)."""

from __future__ import annotations

from google import genai
from google.genai import types

from prompt import SYSTEM_PROMPT


class SubstrateAgent:
    """Manages conversation history and LLM calls for a single session."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        """
        Initialise the agent.

        Args:
            api_key: Google Gemini API key.
            model: Model identifier (default: gemini-2.0-flash).
        """
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.history: list[types.Content] = []

    def run(self, user_input: str) -> str:
        """
        Send a user message and return the assistant's response.

        Context is automatically maintained across calls via the history list.

        Args:
            user_input: The user's idea, constraint, or follow-up.

        Returns:
            The model's Markdown-formatted response.

        Raises:
            Exception: Propagated from the Gemini API on failure.
        """
        self.history.append(
            types.Content(role="user", parts=[types.Part(text=user_input)])
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=self.history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
        )

        assistant_text = response.text or ""
        self.history.append(
            types.Content(role="model", parts=[types.Part(text=assistant_text)])
        )
        return assistant_text
