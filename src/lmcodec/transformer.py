"""Tiny deterministic Transformer-style carrier model."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path

from lmcodec.lm import default_vocab


@dataclass
class TransformerState:
    context: tuple[int, ...]
    position: int = 0


class TransformerLM:
    """Small causal Transformer feature model with a trained output head.

    This is the first Transformer experiment backend. It keeps the attention
    stack deterministic and trains only the output projection, which is enough
    to exercise model-shaped probabilities through LMCodec without adding a
    heavy dependency or a large autograd system.
    """

    model_type = "transformer-rf-v1"

    def __init__(
        self,
        *,
        vocab: str | None = None,
        block_size: int = 16,
        d_model: int = 16,
        ff_dim: int = 32,
        seed: int = 42,
        params: dict[str, object] | None = None,
    ) -> None:
        self.vocab = vocab or default_vocab()
        if "\n" in self.vocab or "\r" in self.vocab:
            raise ValueError("vocab must exclude newline characters")
        if len(set(self.vocab)) != len(self.vocab):
            raise ValueError("vocab must not contain duplicate characters")
        if block_size <= 0:
            raise ValueError("block_size must be positive")
        if d_model <= 0:
            raise ValueError("d_model must be positive")
        if ff_dim <= 0:
            raise ValueError("ff_dim must be positive")

        self.block_size = block_size
        self.d_model = d_model
        self.ff_dim = ff_dim
        self.seed = seed
        self._bos_id = len(self.vocab)
        self._token_to_id = {char: idx for idx, char in enumerate(self.vocab)}

        if params is None:
            self.params = self._init_params()
        else:
            self.params = params
        self._feature_cache: dict[tuple[int, ...], tuple[float, ...]] = {}
        self._prob_cache: dict[tuple[int, ...], tuple[float, ...]] = {}
        self._build_projection_cache()
        self._build_output_cache()

    @classmethod
    def train(
        cls,
        text: str,
        *,
        vocab: str | None = None,
        block_size: int = 16,
        d_model: int = 16,
        ff_dim: int = 32,
        seed: int = 42,
        epochs: int = 1,
        learning_rate: float = 0.05,
        smoothing: float = 0.25,
    ) -> TransformerLM:
        if epochs <= 0:
            raise ValueError("epochs must be positive")
        if learning_rate <= 0.0:
            raise ValueError("learning_rate must be positive")
        if smoothing <= 0.0:
            raise ValueError("smoothing must be positive")

        model = cls(vocab=vocab, block_size=block_size, d_model=d_model, ff_dim=ff_dim, seed=seed)
        token_ids = [model._token_to_id[char] for char in text if char in model._token_to_id]
        if not token_ids:
            raise ValueError("training text has no characters in vocab")

        model._set_unigram_bias(token_ids, smoothing)
        for _ in range(epochs):
            context: tuple[int, ...] = ()
            for token_id in token_ids:
                features = model._features(context)
                logits = model._logits(features)
                probs = _softmax(logits)
                model._train_output_head(features, probs, token_id, learning_rate)
                context = model._next_context(context, token_id)

        model.params = _round_tree(model.params)
        model._build_projection_cache()
        model._build_output_cache()
        model._feature_cache.clear()
        model._prob_cache.clear()
        return model

    @property
    def size(self) -> int:
        return len(self.vocab)

    @property
    def fingerprint(self) -> str:
        return sha256(self.to_canonical_json().encode("utf-8")).hexdigest()

    def init_state(self) -> TransformerState:
        return TransformerState(context=())

    def step_probs(self, state: TransformerState) -> tuple[float, ...]:
        context = state.context[-self.block_size :]
        cached = self._prob_cache.get(context)
        if cached is not None:
            return cached
        probs = tuple(_softmax(self._logits(self._features(context))))
        self._prob_cache[context] = probs
        return probs

    def advance(self, state: TransformerState, token_id: int) -> None:
        if token_id < 0 or token_id >= self.size:
            raise ValueError("token_id out of range")
        state.context = self._next_context(state.context, token_id)
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
    def load(cls, path: str | Path) -> TransformerLM:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("model_type") != cls.model_type:
            raise ValueError("unsupported model type")
        return cls(
            vocab=data["vocab"],
            block_size=int(data["block_size"]),
            d_model=int(data["d_model"]),
            ff_dim=int(data["ff_dim"]),
            seed=int(data["seed"]),
            params=data["params"],
        )

    def to_canonical_json(self) -> str:
        data = {
            "model_type": self.model_type,
            "vocab": self.vocab,
            "block_size": self.block_size,
            "d_model": self.d_model,
            "ff_dim": self.ff_dim,
            "seed": self.seed,
            "params": _round_tree(self.params),
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    def _init_params(self) -> dict[str, object]:
        scale = 1.0 / math.sqrt(self.d_model)
        return {
            "token_embedding": _matrix(self.size + 1, self.d_model, self.seed, "tok", scale),
            "position_embedding": _matrix(self.block_size, self.d_model, self.seed, "pos", scale),
            "wq": _matrix(self.d_model, self.d_model, self.seed, "wq", scale),
            "wk": _matrix(self.d_model, self.d_model, self.seed, "wk", scale),
            "wv": _matrix(self.d_model, self.d_model, self.seed, "wv", scale),
            "wo": _matrix(self.d_model, self.d_model, self.seed, "wo", scale),
            "w1": _matrix(self.d_model, self.ff_dim, self.seed, "w1", scale),
            "b1": [0.0] * self.ff_dim,
            "w2": _matrix(self.ff_dim, self.d_model, self.seed, "w2", 1.0 / math.sqrt(self.ff_dim)),
            "b2": [0.0] * self.d_model,
            "wout": _matrix(self.d_model, self.size, self.seed, "wout", 0.01),
            "bout": [0.0] * self.size,
        }

    def _set_unigram_bias(self, token_ids: list[int], smoothing: float) -> None:
        counts = [smoothing] * self.size
        for token_id in token_ids:
            counts[token_id] += 1.0
        total = sum(counts)
        self.params["bout"] = [math.log(count / total) for count in counts]
        self._build_output_cache()

    def _train_output_head(
        self,
        features: tuple[float, ...],
        probs: list[float],
        target_id: int,
        learning_rate: float,
    ) -> None:
        wout = self.params["wout"]
        bout = self.params["bout"]
        assert isinstance(wout, list)
        assert isinstance(bout, list)
        for token_id, prob in enumerate(probs):
            grad = prob - (1.0 if token_id == target_id else 0.0)
            bout[token_id] -= learning_rate * grad
            for idx, value in enumerate(features):
                wout[idx][token_id] -= learning_rate * grad * value

    def _features(self, context: tuple[int, ...]) -> tuple[float, ...]:
        context = context[-self.block_size :]
        cached = self._feature_cache.get(context)
        if cached is not None:
            return cached

        ids = [self._bos_id] * (self.block_size - len(context)) + list(context)
        last_id = ids[-1]
        h_last = self._h_by_pos_token[-1][last_id]
        q = self._q_last_by_token[last_id]
        scores = [
            _dot(q, self._k_by_pos_token[pos][token_id]) * self._attention_scale
            for pos, token_id in enumerate(ids)
        ]
        weights = _softmax(scores)
        attended = [0.0] * self.d_model
        for pos, (weight, token_id) in enumerate(zip(weights, ids, strict=True)):
            value = self._v_by_pos_token[pos][token_id]
            for idx in range(self.d_model):
                attended[idx] += weight * value[idx]
        residual = _add(h_last, _matvec(attended, self._wo))
        hidden = [math.tanh(value) for value in _add(_matvec(residual, self._w1), self._b1)]
        features = tuple(_add(residual, _add(_matvec(hidden, self._w2), self._b2)))
        self._feature_cache[context] = features
        return features

    def _logits(self, features: tuple[float, ...]) -> list[float]:
        wout = self._wout
        logits = list(self._bout)
        token_ids = self._token_ids
        for idx, feature in enumerate(features):
            row = wout[idx]
            for token_id in token_ids:
                logits[token_id] += feature * row[token_id]
        return logits

    def _next_context(self, context: tuple[int, ...], token_id: int) -> tuple[int, ...]:
        return (context + (token_id,))[-self.block_size :]

    def _build_projection_cache(self) -> None:
        token_embedding = self.params["token_embedding"]
        position_embedding = self.params["position_embedding"]
        wq = self.params["wq"]
        wk = self.params["wk"]
        wv = self.params["wv"]
        wo = self.params["wo"]
        w1 = self.params["w1"]
        b1 = self.params["b1"]
        w2 = self.params["w2"]
        b2 = self.params["b2"]
        assert isinstance(token_embedding, list)
        assert isinstance(position_embedding, list)
        assert isinstance(wq, list)
        assert isinstance(wk, list)
        assert isinstance(wv, list)
        assert isinstance(wo, list)
        assert isinstance(w1, list)
        assert isinstance(b1, list)
        assert isinstance(w2, list)
        assert isinstance(b2, list)

        self._attention_scale = 1.0 / math.sqrt(self.d_model)
        self._wo = wo
        self._w1 = w1
        self._b1 = b1
        self._w2 = w2
        self._b2 = b2
        self._h_by_pos_token = []
        self._k_by_pos_token = []
        self._v_by_pos_token = []
        for pos in range(self.block_size):
            h_rows: list[tuple[float, ...]] = []
            k_rows: list[tuple[float, ...]] = []
            v_rows: list[tuple[float, ...]] = []
            pos_embedding = position_embedding[pos]
            for token_id in range(self.size + 1):
                h = tuple(a + b for a, b in zip(token_embedding[token_id], pos_embedding, strict=True))
                h_rows.append(h)
                k_rows.append(tuple(_matvec(h, wk)))
                v_rows.append(tuple(_matvec(h, wv)))
            self._h_by_pos_token.append(h_rows)
            self._k_by_pos_token.append(k_rows)
            self._v_by_pos_token.append(v_rows)
        self._q_last_by_token = [
            tuple(_matvec(self._h_by_pos_token[-1][token_id], wq))
            for token_id in range(self.size + 1)
        ]

    def _build_output_cache(self) -> None:
        wout = self.params["wout"]
        bout = self.params["bout"]
        assert isinstance(wout, list)
        assert isinstance(bout, list)
        self._wout = wout
        self._bout = bout
        self._token_ids = range(self.size)


def _matrix(rows: int, cols: int, seed: int, name: str, scale: float) -> list[list[float]]:
    return [[_hash_gauss(seed, f"{name}:{row}:{col}") * scale for col in range(cols)] for row in range(rows)]


def _hash_gauss(seed: int, key: str) -> float:
    u1 = max(_hash_uniform(seed, key + ":a"), 1e-12)
    u2 = _hash_uniform(seed, key + ":b")
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def _hash_uniform(seed: int, key: str) -> float:
    digest = sha256(f"{seed}:{key}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    return (value + 0.5) / 2**64


def _matvec(vec: list[float] | tuple[float, ...], matrix: list[list[float]]) -> list[float]:
    cols = len(matrix[0])
    out = [0.0] * cols
    for row_idx, value in enumerate(vec):
        row = matrix[row_idx]
        for col in range(cols):
            out[col] += value * row[col]
    return out


def _dot(left: list[float], right: list[float]) -> float:
    total = 0.0
    for idx in range(len(left)):
        total += left[idx] * right[idx]
    return total


def _add(left: list[float] | tuple[float, ...], right: list[float] | tuple[float, ...]) -> list[float]:
    return [a + b for a, b in zip(left, right, strict=True)]


def _softmax(logits: list[float]) -> list[float]:
    high = max(logits)
    exps = [math.exp(value - high) for value in logits]
    total = sum(exps)
    return [value / total for value in exps]


def _round_tree(value: object) -> object:
    if isinstance(value, float):
        return float(f"{value:.12g}")
    if isinstance(value, list):
        return [_round_tree(item) for item in value]
    if isinstance(value, dict):
        return {key: _round_tree(value[key]) for key in sorted(value)}
    return value
