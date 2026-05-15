#!/usr/bin/env python3
"""Train a tiny Transformer carrier with PyTorch and export LMCodec JSON."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lmcodec.lm import default_vocab  # noqa: E402
from lmcodec.transformer import TransformerLM  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--valid-data")
    parser.add_argument("--out", required=True)
    parser.add_argument("--block-size", type=int, default=16)
    parser.add_argument("--d-model", type=int, default=16)
    parser.add_argument("--ff-dim", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--max-train-tokens", type=int, default=4096)
    parser.add_argument("--vocab", default=default_vocab())
    args = parser.parse_args(argv)

    try:
        import torch
        import torch.nn.functional as functional
    except ImportError:
        print("PyTorch is not installed. Install torch to use this training exporter.", file=sys.stderr)
        return 2

    torch.manual_seed(args.seed)
    torch.set_num_threads(1)

    text = Path(args.data).read_text(encoding="utf-8")
    token_to_id = {char: idx for idx, char in enumerate(args.vocab)}
    token_ids = [token_to_id[char] for char in text if char in token_to_id]
    if args.max_train_tokens > 0:
        token_ids = token_ids[: args.max_train_tokens]
    if not token_ids:
        print("training text has no characters in vocab", file=sys.stderr)
        return 2

    contexts, targets = _build_training_rows(token_ids, args.block_size, len(args.vocab))
    x = torch.tensor(contexts, dtype=torch.long)
    y = torch.tensor(targets, dtype=torch.long)
    valid_x = None
    valid_y = None
    if args.valid_data:
        valid_text = Path(args.valid_data).read_text(encoding="utf-8")
        valid_ids = [token_to_id[char] for char in valid_text if char in token_to_id]
        if not valid_ids:
            print("validation text has no characters in vocab", file=sys.stderr)
            return 2
        valid_contexts, valid_targets = _build_training_rows(valid_ids, args.block_size, len(args.vocab))
        valid_x = torch.tensor(valid_contexts, dtype=torch.long)
        valid_y = torch.tensor(valid_targets, dtype=torch.long)

    model = TorchCarrierModel(
        vocab=args.vocab,
        block_size=args.block_size,
        d_model=args.d_model,
        ff_dim=args.ff_dim,
        seed=args.seed,
        torch=torch,
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    best_valid = float("inf")
    best_params: list[object] | None = None

    for epoch in range(args.epochs):
        optimizer.zero_grad(set_to_none=True)
        logits = model(x)
        loss = functional.cross_entropy(logits, y)
        loss.backward()
        optimizer.step()
        train_bits = loss.item() / math.log(2)
        if valid_x is not None and valid_y is not None:
            with torch.no_grad():
                valid_loss = functional.cross_entropy(model(valid_x), valid_y)
            valid_bits = valid_loss.item() / math.log(2)
            if valid_bits < best_valid:
                best_valid = valid_bits
                best_params = model.clone_parameters()
            print(f"epoch {epoch + 1}: train_nll_bits={train_bits:.3f} valid_nll_bits={valid_bits:.3f}")
        else:
            print(f"epoch {epoch + 1}: nll_bits={train_bits:.3f}")

    if best_params is not None:
        model.restore_parameters(best_params)
        print(f"selected valid_nll_bits={best_valid:.3f}")

    exported = TransformerLM(
        vocab=args.vocab,
        block_size=args.block_size,
        d_model=args.d_model,
        ff_dim=args.ff_dim,
        seed=args.seed,
        params=model.export_params(),
    )
    exported.save(args.out)
    print(f"model path: {args.out}")
    print(f"model type: {exported.model_type}")
    print(f"vocab size: {exported.size}")
    print(f"model fingerprint: {exported.fingerprint}")
    return 0


class TorchCarrierModel:
    def __init__(
        self,
        *,
        vocab: str,
        block_size: int,
        d_model: int,
        ff_dim: int,
        seed: int,
        torch: object,
    ) -> None:
        self.torch = torch
        self.vocab = vocab
        self.block_size = block_size
        self.d_model = d_model
        self.ff_dim = ff_dim
        init = TransformerLM(vocab=vocab, block_size=block_size, d_model=d_model, ff_dim=ff_dim, seed=seed)
        params = init.params
        self.token_embedding = self._parameter(params["token_embedding"])
        self.position_embedding = self._parameter(params["position_embedding"])
        self.wq = self._parameter(params["wq"])
        self.wk = self._parameter(params["wk"])
        self.wv = self._parameter(params["wv"])
        self.wo = self._parameter(params["wo"])
        self.w1 = self._parameter(params["w1"])
        self.b1 = self._parameter(params["b1"])
        self.w2 = self._parameter(params["w2"])
        self.b2 = self._parameter(params["b2"])
        self.wout = self._parameter(params["wout"])
        self.bout = self._parameter(params["bout"])

    def __call__(self, contexts: object) -> object:
        torch = self.torch
        positions = torch.arange(self.block_size, dtype=torch.long, device=contexts.device)
        h = self.token_embedding[contexts] + self.position_embedding[positions].unsqueeze(0)
        q = h[:, -1, :] @ self.wq
        keys = h @ self.wk
        values = h @ self.wv
        scores = torch.einsum("bd,btd->bt", q, keys) / math.sqrt(self.d_model)
        weights = torch.softmax(scores, dim=-1)
        attended = torch.einsum("bt,btd->bd", weights, values)
        residual = h[:, -1, :] + attended @ self.wo
        hidden = torch.tanh(residual @ self.w1 + self.b1)
        features = residual + hidden @ self.w2 + self.b2
        return features @ self.wout + self.bout

    def parameters(self) -> list[object]:
        return [
            self.token_embedding,
            self.position_embedding,
            self.wq,
            self.wk,
            self.wv,
            self.wo,
            self.w1,
            self.b1,
            self.w2,
            self.b2,
            self.wout,
            self.bout,
        ]

    def clone_parameters(self) -> list[object]:
        return [value.detach().clone() for value in self.parameters()]

    def restore_parameters(self, values: list[object]) -> None:
        for current, saved in zip(self.parameters(), values, strict=True):
            current.data.copy_(saved)

    def export_params(self) -> dict[str, object]:
        return {
            "token_embedding": self._export(self.token_embedding),
            "position_embedding": self._export(self.position_embedding),
            "wq": self._export(self.wq),
            "wk": self._export(self.wk),
            "wv": self._export(self.wv),
            "wo": self._export(self.wo),
            "w1": self._export(self.w1),
            "b1": self._export(self.b1),
            "w2": self._export(self.w2),
            "b2": self._export(self.b2),
            "wout": self._export(self.wout),
            "bout": self._export(self.bout),
        }

    def _parameter(self, value: object) -> object:
        torch = self.torch
        return torch.nn.Parameter(torch.tensor(value, dtype=torch.float32))

    def _export(self, value: object) -> object:
        return value.detach().cpu().tolist()


def _build_training_rows(token_ids: list[int], block_size: int, bos_id: int) -> tuple[list[list[int]], list[int]]:
    rows: list[list[int]] = []
    targets: list[int] = []
    context: tuple[int, ...] = ()
    for token_id in token_ids:
        rows.append([bos_id] * (block_size - len(context)) + list(context))
        targets.append(token_id)
        context = (context + (token_id,))[-block_size:]
    return rows, targets


if __name__ == "__main__":
    raise SystemExit(main())
