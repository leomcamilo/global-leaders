"""Real-SLM backends (GAME_RULES.md §7). Same 4-method contract as FakeLLM, so the
engine is unchanged. A base class owns prompt -> request -> extract JSON -> validate ->
retry -> optional FakeLLM fallback; subclasses only implement the HTTP call.

Backends:
  • OllamaCloudLLM  — https://ollama.com/api/chat, Bearer OLLAMA_API_KEY (default)
  • OpenRouterLLM   — https://openrouter.ai/api/v1/chat/completions, Bearer OPENROUTER_API_KEY

Stdlib-only (urllib); nothing to install.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

from engine.countries import CountryDef
from engine import prompts
from engine.llm import Action, FakeLLM
from engine.schemas import (
    JudgeOutput,
    NarratorOutput,
    Option,
    SchemaError,
    parse_cast,
    parse_chat_reply,
    parse_objectives,
    parse_options,
)
from engine.state import WorldState
from engine.events import Event

OLLAMA_DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "nemotron-3-nano:30b")
OPENROUTER_DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-nano-9b-v2")


class RemoteError(RuntimeError):
    pass


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json(raw: str) -> dict:
    """Pull a JSON object out of a model reply, tolerating reasoning traces / fences."""
    text = _THINK_RE.sub("", raw)
    text = _FENCE_RE.sub("", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("no JSON object found", text, 0)
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise json.JSONDecodeError("unbalanced JSON braces", text, start)


# ---------------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------------

class RemoteChatLLM:
    name = "remote"

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        max_retries: int = 3,
        timeout: int = 120,
        fallback: FakeLLM | None = None,
        verbose: bool = False,
    ):
        self.model = model
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout
        self.fallback = fallback
        self.verbose = verbose
        self.total_tokens = 0  # cumulative prompt+completion tokens (the "small model" story)
        self.calls = 0

    # -- HTTP (shared) -----------------------------------------------------------

    def _post(self, url: str, headers: dict, payload: dict) -> dict:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            raise RemoteError(f"HTTP {e.code}: {body[:400]}") from e
        except urllib.error.URLError as e:
            raise RemoteError(f"network error: {e.reason}") from e

    def _complete(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        raise NotImplementedError

    # -- generic validated call --------------------------------------------------

    def _ask(self, role, system, user, validate, temperature, max_tokens):
        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            t0 = time.time()
            try:
                raw = self._complete(system, user, temperature, max_tokens)
                data = extract_json(raw)
                validate(data)
                if self.verbose:
                    print(f"      [{self.name}:{role} ok {time.time() - t0:.1f}s try {attempt}]")
                return data
            except (json.JSONDecodeError, SchemaError, KeyError, RemoteError) as e:
                last_err = e
                if self.verbose:
                    print(f"      [{self.name}:{role} retry {attempt}/{self.max_retries}: "
                          f"{type(e).__name__}: {str(e)[:120]}]")
                user += (f"\n\nYour previous reply was invalid ({type(e).__name__}). "
                         "Return ONLY the JSON object, exactly as specified.")
        if self.fallback is not None:
            if self.verbose:
                print(f"      [{self.name}:{role} FELL BACK to FakeLLM]")
            return None
        raise RemoteError(f"{role}: failed after {self.max_retries} tries: {last_err}")

    # -- 4-method contract -------------------------------------------------------

    def setup_objectives(self, country: CountryDef, state: WorldState) -> dict:
        d = self._ask("objectives", prompts.OBJECTIVES_SYSTEM,
                      prompts.objectives_user(country, state),
                      parse_objectives, 0.5, 2048)
        return d if d is not None else self.fallback.setup_objectives(country, state)

    def cast_design(self, country: CountryDef, state: WorldState) -> dict:
        d = self._ask("cast", prompts.CAST_SYSTEM, prompts.cast_user(country, state),
                      parse_cast, 0.9, 2048)
        return d if d is not None else self.fallback.cast_design(country, state)

    def narrate(self, event: Event, state: WorldState, prev_mode: str | None = None) -> dict:
        d = self._ask("narrate", prompts.NARRATOR_SYSTEM,
                      prompts.narrator_user(event, state, prev_mode),
                      lambda x: NarratorOutput.parse(x), 0.85, 1024)
        return d if d is not None else self.fallback.narrate(event, state, prev_mode)

    def options(self, event: Event, state: WorldState) -> dict:
        d = self._ask("options", prompts.OPTIONS_SYSTEM,
                      prompts.options_user(event, state),
                      lambda x: parse_options(x), 0.7, 1024)
        return d if d is not None else self.fallback.options(event, state)

    def judge(self, event: Event, action: Action, state: WorldState) -> dict:
        action_text = f"{action.label} — {action.summary}" if isinstance(action, Option) else str(action)
        d = self._ask("judge", prompts.JUDGE_SYSTEM,
                      prompts.judge_user(event, action_text, state),
                      lambda x: JudgeOutput.parse(x), 0.4, 1024)
        return d if d is not None else self.fallback.judge(event, action, state)

    def converse(self, figure, persona, question, state, history) -> dict:
        d = self._ask("converse", prompts.CONVERSE_SYSTEM,
                      prompts.converse_user(figure, persona, question, state, history),
                      parse_chat_reply, 0.85, 512)
        return d if d is not None else self.fallback.converse(figure, persona, question, state, history)


# ---------------------------------------------------------------------------------
# Ollama Cloud — native /api/chat
# ---------------------------------------------------------------------------------

class OllamaCloudLLM(RemoteChatLLM):
    name = "ollama"
    URL = os.environ.get("OLLAMA_HOST", "https://ollama.com").rstrip("/") + "/api/chat"

    def __init__(self, model: str = OLLAMA_DEFAULT_MODEL, api_key: str | None = None,
                 think: bool = False, **kw):
        api_key = api_key or os.environ.get("OLLAMA_API_KEY")
        if not api_key:
            raise RemoteError("Set OLLAMA_API_KEY (create one at https://ollama.com/settings/keys).")
        super().__init__(model=model, api_key=api_key, **kw)
        self.think = think  # Nemotron is a reasoning model; off by default for clean, cheap JSON

    def _complete(self, system, user, temperature, max_tokens):
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "format": "json",
            "think": self.think,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        resp = self._post(self.URL, headers, payload)
        self.total_tokens += int(resp.get("prompt_eval_count", 0)) + int(resp.get("eval_count", 0))
        self.calls += 1
        return resp["message"]["content"]


# ---------------------------------------------------------------------------------
# OpenRouter — OpenAI-compatible /v1/chat/completions
# ---------------------------------------------------------------------------------

class OpenRouterLLM(RemoteChatLLM):
    name = "openrouter"
    URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, model: str = OPENROUTER_DEFAULT_MODEL, api_key: str | None = None, **kw):
        api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RemoteError("Set OPENROUTER_API_KEY (get one at https://openrouter.ai/keys).")
        super().__init__(model=model, api_key=api_key, **kw)
        self._json_mode = True

    def _complete(self, system, user, temperature, max_tokens):
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self._json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/leomcamilo/global-leaders",
            "X-Title": "Global Leaders",
        }
        try:
            resp = self._post(self.URL, headers, payload)
        except RemoteError as e:
            if self._json_mode and "response_format" in str(e).lower():
                self._json_mode = False
                payload.pop("response_format", None)
                resp = self._post(self.URL, headers, payload)
            else:
                raise
        usage = resp.get("usage", {})
        self.total_tokens += int(usage.get("total_tokens", 0))
        self.calls += 1
        return resp["choices"][0]["message"]["content"]


# Convenience aliases (NVIDIA is a hackathon partner).
def NemotronLLM(fallback=None, verbose=False, **kw) -> OllamaCloudLLM:
    return OllamaCloudLLM(fallback=fallback, verbose=verbose, **kw)


BACKENDS = {"ollama": OllamaCloudLLM, "openrouter": OpenRouterLLM}
