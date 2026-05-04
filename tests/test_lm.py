import tempfile
import unittest
from pathlib import Path

from lmcodec.codec import CodecSettings, decode, encode
from lmcodec.lm import NGramLM, default_vocab
from lmcodec.probability import ProbabilityShapeSettings
from lmcodec.transformer import TransformerLM


class NGramLMTests(unittest.TestCase):
    def test_save_load_preserves_fingerprint_and_probs(self) -> None:
        model = NGramLM.train("hello hello carrier text", order=2, alpha=0.5, uniform_mix=0.25)
        state = model.init_state()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.json"
            model.save(path)
            loaded = NGramLM.load(path)

        self.assertEqual(loaded.fingerprint, model.fingerprint)
        self.assertEqual(loaded.vocab, model.vocab)
        self.assertEqual(loaded.order, model.order)
        self.assertEqual(loaded.uniform_mix, model.uniform_mix)
        self.assertEqual(loaded.step_probs(loaded.init_state()), model.step_probs(state))

    def test_ngram_order_zero_codec_roundtrip(self) -> None:
        model = NGramLM.train(default_vocab() * 3, order=0, alpha=1.0)
        payload = b"ngram model roundtrip"

        message = encode(payload, model=model, wrap=80)

        self.assertEqual(decode(message, model=model), payload)

    def test_ngram_context_changes_distribution(self) -> None:
        model = NGramLM.train("aaaaab", order=1, alpha=1.0, uniform_mix=0.25)
        state = model.init_state()
        initial_probs = model.step_probs(state)
        model.advance(state, model.token_to_id("a"))
        after_a_probs = model.step_probs(state)

        self.assertNotEqual(initial_probs, after_a_probs)

    def test_ngram_order_one_codec_roundtrip_with_flattening(self) -> None:
        corpus = "the carrier text likes letters and spaces " * 20 + default_vocab()
        model = NGramLM.train(corpus, order=1, alpha=1.0, uniform_mix=0.75)
        payload = b"order one"

        message = encode(payload, model=model, wrap=80)

        self.assertEqual(decode(message, model=model), payload)


class TransformerLMTests(unittest.TestCase):
    def test_save_load_preserves_fingerprint_and_probs(self) -> None:
        model = TransformerLM.train(
            "transformer carrier text " * 3 + default_vocab(),
            block_size=8,
            d_model=8,
            ff_dim=12,
            epochs=1,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.json"
            model.save(path)
            loaded = TransformerLM.load(path)

        self.assertEqual(loaded.fingerprint, model.fingerprint)
        self.assertEqual(loaded.vocab, model.vocab)
        self.assertEqual(loaded.step_probs(loaded.init_state()), model.step_probs(model.init_state()))

    def test_transformer_context_changes_distribution(self) -> None:
        model = TransformerLM.train(
            "the carrier text likes letters and spaces " * 2 + default_vocab(),
            block_size=8,
            d_model=8,
            ff_dim=12,
        )
        state = model.init_state()
        initial_probs = model.step_probs(state)
        model.advance(state, model.token_to_id("a"))
        after_a_probs = model.step_probs(state)

        self.assertNotEqual(initial_probs, after_a_probs)

    def test_transformer_cached_probs_are_deterministic(self) -> None:
        model = TransformerLM.train(
            "the carrier text likes letters and spaces " * 2 + default_vocab(),
            block_size=8,
            d_model=8,
            ff_dim=12,
        )
        state = model.init_state()
        model.advance(state, model.token_to_id("t"))
        model.advance(state, model.token_to_id("h"))

        first = model.step_probs(state)
        model._feature_cache.clear()
        model._prob_cache.clear()
        second = model.step_probs(state)

        self.assertEqual(second, first)
        self.assertEqual(model.fingerprint, model.fingerprint)

    def test_transformer_codec_roundtrip_with_shaping(self) -> None:
        model = TransformerLM.train(
            "the carrier text likes letters and spaces " * 3 + default_vocab(),
            block_size=8,
            d_model=8,
            ff_dim=12,
        )
        settings = CodecSettings(shape=ProbabilityShapeSettings(uniform_mix=0.75, temperature=1.5))
        payload = b"tx"

        message = encode(payload, model=model, settings=settings, wrap=80)

        self.assertEqual(decode(message, model=model), payload)


if __name__ == "__main__":
    unittest.main()
