"""Deterministic lightweight language-model interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path


@dataclass
class FixedLMState:
    position: int = 0


class FixedLM:
    """A deterministic fixed-distribution character model.

    This is intentionally simple. It proves the transport layer before a real
    trained LM is introduced.
    """

    def __init__(self, vocab: str | None = None) -> None:
        self.vocab = vocab or default_vocab()
        if "\n" in self.vocab or "\r" in self.vocab:
            raise ValueError("vocab must exclude newline characters")
        if len(set(self.vocab)) != len(self.vocab):
            raise ValueError("vocab must not contain duplicate characters")
        self._token_to_id = {char: idx for idx, char in enumerate(self.vocab)}
        self._probs = self._build_probs()

    @property
    def size(self) -> int:
        return len(self.vocab)

    @property
    def fingerprint(self) -> str:
        h = sha256()
        h.update(b"lmcodec-fixed-v1\n")
        h.update(self.vocab.encode("utf-8"))
        h.update(b"\n")
        for prob in self._probs:
            h.update(f"{prob:.17g}\n".encode("ascii"))
        return h.hexdigest()

    def init_state(self) -> FixedLMState:
        return FixedLMState()

    def step_probs(self, state: FixedLMState) -> tuple[float, ...]:
        return self._probs

    def advance(self, state: FixedLMState, token_id: int) -> None:
        if token_id < 0 or token_id >= self.size:
            raise ValueError("token_id out of range")
        state.position += 1

    def token_to_id(self, token: str) -> int:
        try:
            return self._token_to_id[token]
        except KeyError as exc:
            raise ValueError(f"invalid carrier token: {token!r}") from exc

    def id_to_token(self, token_id: int) -> str:
        return self.vocab[token_id]

    def _build_probs(self) -> tuple[float, ...]:
        # The transport kernel starts with a 64-symbol uniform alphabet. Because
        # 65536 / 64 is exact, every token carries exactly six bits and avoids
        # arithmetic-coder underflow pathologies while the codec is being built.
        return tuple(1.0 / len(self.vocab) for _ in self.vocab)


def default_vocab() -> str:
    """Return a 64-character copy/paste-safe alphabet."""

    return "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ."


@dataclass
class NGramState:
    context: str
    position: int = 0


class NGramLM:
    """Deterministic character n-gram model with additive smoothing."""

    model_type = "ngram-v1"

    def __init__(
        self,
        *,
        vocab: str | None = None,
        order: int = 2,
        alpha: float = 1.0,
        uniform_mix: float = 0.5,
        counts: dict[str, list[int]] | None = None,
    ) -> None:
        if order < 0:
            raise ValueError("order must be non-negative")
        if alpha <= 0.0:
            raise ValueError("alpha must be positive")
        if uniform_mix < 0.0 or uniform_mix > 1.0:
            raise ValueError("uniform_mix must be between 0 and 1")
        self.vocab = vocab or default_vocab()
        if "\n" in self.vocab or "\r" in self.vocab:
            raise ValueError("vocab must exclude newline characters")
        if len(set(self.vocab)) != len(self.vocab):
            raise ValueError("vocab must not contain duplicate characters")
        self.order = order
        self.alpha = alpha
        self.uniform_mix = uniform_mix
        self._token_to_id = {char: idx for idx, char in enumerate(self.vocab)}
        self._counts = counts or {}
        self._prob_cache: dict[str, tuple[float, ...]] = {}

    @classmethod
    def train(
        cls,
        text: str,
        *,
        vocab: str | None = None,
        order: int = 2,
        alpha: float = 1.0,
        uniform_mix: float = 0.5,
    ) -> NGramLM:
        model = cls(vocab=vocab, order=order, alpha=alpha, uniform_mix=uniform_mix)
        context = model._initial_context()
        for char in text:
            if char not in model._token_to_id:
                continue
            bucket = model._counts.setdefault(context, [0] * len(model.vocab))
            bucket[model._token_to_id[char]] += 1
            context = model._next_context(context, char)
        return model

    @property
    def size(self) -> int:
        return len(self.vocab)

    @property
    def fingerprint(self) -> str:
        return sha256(self.to_canonical_json().encode("utf-8")).hexdigest()

    def init_state(self) -> NGramState:
        return NGramState(context=self._initial_context())

    def step_probs(self, state: NGramState) -> tuple[float, ...]:
        context = self._backoff_context(state.context)
        cached = self._prob_cache.get(context)
        if cached is not None:
            return cached

        counts = self._counts.get(context, [0] * self.size)
        denom = sum(counts) + self.alpha * self.size
        uniform = 1.0 / self.size
        probs = tuple(
            (1.0 - self.uniform_mix) * ((count + self.alpha) / denom) + self.uniform_mix * uniform
            for count in counts
        )
        self._prob_cache[context] = probs
        return probs

    def advance(self, state: NGramState, token_id: int) -> None:
        if token_id < 0 or token_id >= self.size:
            raise ValueError("token_id out of range")
        state.context = self._next_context(state.context, self.vocab[token_id])
        state.position += 1

    def token_to_id(self, token: str) -> int:
        try:
            return self._token_to_id[token]
        except KeyError as exc:
            raise ValueError(f"invalid carrier token: {token!r}") from exc

    def id_to_token(self, token_id: int) -> str:
        return self.vocab[token_id]

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_canonical_json() + "\n", encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, path: str | Path) -> NGramLM:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("model_type") != cls.model_type:
            raise ValueError("unsupported model type")
        counts = {key: list(value) for key, value in data["counts"].items()}
        return cls(
            vocab=data["vocab"],
            order=int(data["order"]),
            alpha=float(data["alpha"]),
            uniform_mix=float(data["uniform_mix"]),
            counts=counts,
        )

    def to_canonical_json(self) -> str:
        data = {
            "model_type": self.model_type,
            "vocab": self.vocab,
            "order": self.order,
            "alpha": self.alpha,
            "uniform_mix": self.uniform_mix,
            "counts": {key: self._counts[key] for key in sorted(self._counts)},
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    def _initial_context(self) -> str:
        return "^" * self.order

    def _next_context(self, context: str, char: str) -> str:
        if self.order == 0:
            return ""
        return (context + char)[-self.order :]

    def _backoff_context(self, context: str) -> str:
        current = context
        while current and current not in self._counts:
            current = current[1:]
        return current if current in self._counts else ""
