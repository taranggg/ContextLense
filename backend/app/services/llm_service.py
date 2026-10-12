"""
Local LLM inference behind a small adapter interface.

`MLXBackend` runs an MLX-LM checkpoint on Apple Silicon. Another local runtime
can be added by implementing `LLMBackend` and registering it in
`create_llm_backend`. There is deliberately no fallback that fabricates an
answer: if inference is unavailable, callers receive `LLMUnavailableError`.
"""
from __future__ import annotations

import importlib.util
import logging
import platform
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol

from ..config import Settings
from ..schemas import LLMStatus

logger = logging.getLogger("contextlens.llm")

Message = dict[str, str]


@dataclass(frozen=True)
class GenerationParams:
    max_tokens: int
    temperature: float
    top_p: float


@dataclass
class GenerationResult:
    text: str
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    finish_reason: Optional[str]
    generation_ms: float
    cancelled: bool = False


class LLMUnavailableError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class GenerationError(RuntimeError):
    pass


class LLMBackend(Protocol):
    runtime: str
    model_id: str

    def status(self) -> LLMStatus: ...

    def start_loading(self) -> None:
        """Begin loading in the background (no-op if loaded or unavailable)."""

    def count_tokens(self, messages: list[Message]) -> int:
        """Prompt length in tokens after applying the chat template. Loads the model if needed."""

    def generate(
        self,
        messages: list[Message],
        params: GenerationParams,
        on_token: Optional[Callable[[str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> GenerationResult:
        """Blocking generation. Raises LLMUnavailableError or GenerationError."""


class DisabledBackend:
    """Used when LLM_RUNTIME=none or an unknown runtime is configured."""

    def __init__(self, runtime: str, model_id: str, reason: str):
        self.runtime = runtime
        self.model_id = model_id
        self._reason = reason

    def status(self) -> LLMStatus:
        return LLMStatus(status="not_configured", detail=self._reason, runtime=self.runtime, model=self.model_id)

    def start_loading(self) -> None:
        return None

    def count_tokens(self, messages: list[Message]) -> int:
        raise LLMUnavailableError("llm_not_configured", self._reason)

    def generate(self, messages, params, on_token=None, should_stop=None) -> GenerationResult:
        raise LLMUnavailableError("llm_not_configured", self._reason)


class MLXBackend:
    runtime = "mlx"

    def __init__(self, model_id: str, allow_download: bool = False):
        self.model_id = model_id
        self.allow_download = allow_download
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mlx")  # all MLX work on one thread
        self._lock = threading.Lock()
        self._load_future: Optional[Future] = None
        self._model = None
        self._tokenizer = None
        self._state = "not_loaded"
        self._detail: Optional[str] = None
        self.load_time_s: Optional[float] = None
        self._check_environment()

    # ------------------------------------------------------------------ status / loading

    def _check_environment(self) -> None:
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            self._state = "unavailable"
            self._detail = (
                f"MLX requires macOS on Apple Silicon; this machine is {platform.system()} {platform.machine()}. "
                "Run the backend on an Apple Silicon Mac, or add another local runtime adapter."
            )
        elif importlib.util.find_spec("mlx_lm") is None:
            self._state = "unavailable"
            self._detail = "The mlx-lm package is not installed. Run: pip install mlx-lm"

    def _resolve_model_path(self) -> str:
        local = Path(self.model_id).expanduser()
        if local.exists():
            return str(local)
        from huggingface_hub import snapshot_download

        try:
            return snapshot_download(self.model_id, local_files_only=not self.allow_download)
        except Exception as exc:
            if not self.allow_download:
                raise LLMUnavailableError(
                    "llm_not_downloaded",
                    f"The model '{self.model_id}' is not downloaded. Run: hf download {self.model_id}",
                ) from exc
            raise LLMUnavailableError("llm_download_failed", f"Could not download '{self.model_id}': {exc}") from exc

    def _load(self) -> None:
        try:
            path = self._resolve_model_path()
            from mlx_lm import load

            start = time.perf_counter()
            model, tokenizer = load(path)
            self.load_time_s = round(time.perf_counter() - start, 2)
            self._model, self._tokenizer = model, tokenizer
            self._state, self._detail = "ready", None
            logger.info("Loaded %s in %.2fs", self.model_id, self.load_time_s)
        except LLMUnavailableError as exc:
            self._state = "not_downloaded" if exc.code == "llm_not_downloaded" else "error"
            self._detail = exc.message
            logger.warning(exc.message)
        except Exception as exc:
            self._state = "error"
            self._detail = f"Failed to load '{self.model_id}': {exc}"
            logger.exception("Model load failed")

    def start_loading(self) -> Optional[Future]:
        with self._lock:
            if self._state in ("unavailable", "ready"):
                return self._load_future
            if self._load_future is None or (self._load_future.done() and self._state != "ready"):
                self._state, self._detail = "loading", None
                self._load_future = self._executor.submit(self._load)
            return self._load_future

    def _ensure_loaded(self) -> None:
        if self._state == "ready":
            return
        if self._state == "unavailable":
            raise LLMUnavailableError("llm_unavailable", self._detail or "Local inference is unavailable.")
        future = self.start_loading()
        if future is not None:
            future.result()
        if self._state != "ready":
            code = "llm_not_downloaded" if self._state == "not_downloaded" else "llm_load_failed"
            raise LLMUnavailableError(code, self._detail or "The local model could not be loaded.")

    def status(self) -> LLMStatus:
        detail = self._detail
        if self._state == "not_loaded":
            detail = "The model loads on first use."
        return LLMStatus(
            status=self._state,  # type: ignore[arg-type]
            detail=detail,
            runtime=self.runtime,
            model=self.model_id,
            load_time_s=self.load_time_s,
        )

    # ------------------------------------------------------------------ inference

    def _prompt(self, messages: list[Message]) -> str:
        return self._tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)

    def count_tokens(self, messages: list[Message]) -> int:
        self._ensure_loaded()
        return self._executor.submit(lambda: len(self._tokenizer.encode(self._prompt(messages), add_special_tokens=False))).result()

    def generate(
        self,
        messages: list[Message],
        params: GenerationParams,
        on_token: Optional[Callable[[str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> GenerationResult:
        self._ensure_loaded()
        return self._executor.submit(self._generate, messages, params, on_token, should_stop).result()

    def _generate(self, messages, params: GenerationParams, on_token, should_stop) -> GenerationResult:
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler

        start = time.perf_counter()
        sampler = make_sampler(temp=params.temperature, top_p=params.top_p if params.top_p < 1.0 else 0.0)
        parts: list[str] = []
        last = None
        cancelled = False
        try:
            for response in stream_generate(
                self._model, self._tokenizer, self._prompt(messages), max_tokens=params.max_tokens, sampler=sampler
            ):
                last = response
                if response.text:
                    parts.append(response.text)
                    if on_token:
                        on_token(response.text)
                if should_stop and should_stop():
                    cancelled = True
                    break
        except Exception as exc:
            logger.exception("Generation failed")
            raise GenerationError(f"Local generation failed: {exc}") from exc
        return GenerationResult(
            text="".join(parts).strip(),
            prompt_tokens=getattr(last, "prompt_tokens", None),
            completion_tokens=getattr(last, "generation_tokens", None),
            finish_reason="cancelled" if cancelled else getattr(last, "finish_reason", None),
            generation_ms=(time.perf_counter() - start) * 1000,
            cancelled=cancelled,
        )


def create_llm_backend(settings: Settings) -> LLMBackend:
    if settings.llm_runtime == "mlx":
        return MLXBackend(settings.llm_model, allow_download=settings.llm_allow_download)
    if settings.llm_runtime in ("none", "disabled", ""):
        return DisabledBackend("none", settings.llm_model, "Local inference is disabled (LLM_RUNTIME=none).")
    return DisabledBackend(
        settings.llm_runtime,
        settings.llm_model,
        f"Unknown LLM_RUNTIME '{settings.llm_runtime}'. Supported: mlx, none.",
    )
