"""LMCodec command-line interface."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import TypeVar

from lmcodec.codec import CodecSettings, decode, encode
from lmcodec.errors import LMCodecError
from lmcodec.lm import FixedLM, NGramLM
from lmcodec.probability import ProbabilityShapeSettings
from lmcodec.transformer import TransformerLM

T = TypeVar("T")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lmcodec")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="train a deterministic carrier model")
    train_parser.add_argument("--data", required=True)
    train_parser.add_argument("--out", required=True)
    train_parser.add_argument("--model-type", choices=("ngram", "transformer"), default="ngram")
    train_parser.add_argument("--order", type=int, default=2)
    train_parser.add_argument("--alpha", type=float, default=1.0)
    train_parser.add_argument("--uniform-mix", type=float, default=0.5)
    train_parser.add_argument("--block-size", type=int, default=16)
    train_parser.add_argument("--d-model", type=int, default=16)
    train_parser.add_argument("--ff-dim", type=int, default=32)
    train_parser.add_argument("--seed", type=int, default=42)
    train_parser.add_argument("--epochs", type=int, default=1)
    train_parser.add_argument("--learning-rate", type=float, default=0.05)

    encode_parser = subparsers.add_parser("encode", help="encode bytes to armoured text")
    encode_parser.add_argument("--model", help="model JSON file from train")
    encode_parser.add_argument("--in", dest="infile", required=True)
    encode_parser.add_argument("--out", dest="outfile", required=True)
    encode_parser.add_argument("--wrap", type=int, default=0)
    encode_parser.add_argument("--topk", type=int, default=0)
    _add_shape_args(encode_parser)
    encode_parser.add_argument("--max-steps", type=int)

    decode_parser = subparsers.add_parser("decode", help="decode armoured text to bytes")
    decode_parser.add_argument("--model", help="model JSON file from train")
    decode_parser.add_argument("--in", dest="infile", required=True)
    decode_parser.add_argument("--out", dest="outfile", required=True)
    decode_parser.add_argument("--topk", type=int)
    _add_shape_args(decode_parser, default=None)

    args = parser.parse_args(argv)

    try:
        if args.command == "train":
            text = Path(args.data).read_text(encoding="utf-8")
            if args.model_type == "ngram":
                model = NGramLM.train(text, order=args.order, alpha=args.alpha, uniform_mix=args.uniform_mix)
            else:
                model = TransformerLM.train(
                    text,
                    block_size=args.block_size,
                    d_model=args.d_model,
                    ff_dim=args.ff_dim,
                    seed=args.seed,
                    epochs=args.epochs,
                    learning_rate=args.learning_rate,
                )
            model.save(args.out)
            print(f"model path: {args.out}")
            print(f"model type: {model.model_type}")
            if isinstance(model, NGramLM):
                print(f"order: {model.order}")
                print(f"uniform mix: {model.uniform_mix}")
            if isinstance(model, TransformerLM):
                print(f"block size: {model.block_size}")
                print(f"d model: {model.d_model}")
                print(f"ff dim: {model.ff_dim}")
                print(f"seed: {model.seed}")
            print(f"vocab size: {model.size}")
            print(f"model fingerprint: {model.fingerprint}")
            return 0

        model = _load_model(args.model)
        if args.command == "encode":
            settings = _settings_from_args(args)
            payload = Path(args.infile).read_bytes()
            message = encode(payload, model=model, settings=settings, wrap=args.wrap, max_steps=args.max_steps)
            Path(args.outfile).write_text(message, encoding="utf-8", newline="\n")
            carrier_chars = _carrier_char_count(message)
            payload_bits = (12 + len(payload)) * 8
            print(f"payload bytes: {len(payload)}")
            print(f"carrier chars: {carrier_chars}")
            print(f"full armour chars: {len(message)}")
            print(f"bits/char: {payload_bits / max(carrier_chars, 1):.3f}")
            print(f"base64 chars baseline: {len(base64.b64encode(payload))}")
            print(f"model fingerprint: {model.fingerprint}")
            return 0
        if args.command == "decode":
            message = Path(args.infile).read_text(encoding="utf-8")
            settings = _settings_from_args(args) if _has_explicit_decode_settings(args) else None
            payload = decode(message, model=model, settings=settings)
            Path(args.outfile).write_bytes(payload)
            print(f"payload bytes: {len(payload)}")
            print("CRC status: ok")
            print(f"model fingerprint: {model.fingerprint}")
            return 0
    except (LMCodecError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    parser.error("unreachable command")
    return 2


def _load_model(model_path: str | None) -> FixedLM | NGramLM | TransformerLM:
    if model_path:
        model_type = json.loads(Path(model_path).read_text(encoding="utf-8")).get("model_type")
        if model_type == NGramLM.model_type:
            return NGramLM.load(model_path)
        if model_type == TransformerLM.model_type:
            return TransformerLM.load(model_path)
        raise LMCodecError("unsupported model type")
    return FixedLM()


def _add_shape_args(parser: argparse.ArgumentParser, *, default: float | None = 0.0) -> None:
    parser.add_argument("--shape-uniform-mix", type=float, default=default)
    parser.add_argument("--temperature", type=float, default=1.0 if default is not None else None)
    parser.add_argument("--min-prob", type=float, default=default)
    parser.add_argument("--min-entropy-bits", type=float, default=default)


def _settings_from_args(args: argparse.Namespace) -> CodecSettings:
    return CodecSettings(
        topk=_default(args.topk, 0),
        shape=ProbabilityShapeSettings(
            uniform_mix=_default(args.shape_uniform_mix, 0.0),
            temperature=_default(args.temperature, 1.0),
            min_probability=_default(args.min_prob, 0.0),
            min_entropy_bits=_default(args.min_entropy_bits, 0.0),
        ),
    )


def _has_explicit_decode_settings(args: argparse.Namespace) -> bool:
    return any(
        value is not None
        for value in (
            args.topk,
            args.shape_uniform_mix,
            args.temperature,
            args.min_prob,
            args.min_entropy_bits,
        )
    )


def _default(value: T | None, default: T) -> T:
    return default if value is None else value


def _carrier_char_count(message: str) -> int:
    lines = message.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    try:
        blank = lines.index("")
    except ValueError:
        return 0
    end = next((idx for idx, line in enumerate(lines) if line.strip() == "-----END LMCODEC-----"), len(lines))
    return sum(len(line) for line in lines[blank + 1 : end])


if __name__ == "__main__":
    raise SystemExit(main())
