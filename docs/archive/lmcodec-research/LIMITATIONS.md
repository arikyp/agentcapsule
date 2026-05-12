# LMCodec Limitations

LMCodec V1 is a research prototype, not a production privacy, compression, or
steganography tool.

## Transport

- V1 is lossless for payloads covered by the tests and demos, but it is not yet
  stress-tested as a large-file archival format.
- The frame uses CRC32 for corruption detection. It does not embed a SHA256
  digest in the payload frame.
- The copy/paste armour is plain text and does not provide secrecy.

## Carrier Text

- The fixed carrier is stable and efficient, but it does not look natural.
- The n-gram and Transformer carriers shape the symbol distribution, but V1
  does not produce semantically meaningful prose.
- Greedy Transformer previews are not representative of real encoded output.
  Actual carrier text is selected by payload bits through the range coder.

## Models

- The fixed carrier is the default V1 path.
- The Transformer carrier is experimental but pinned and reproducible.
- PyTorch is optional and only used for training/export experiments. Runtime
  inference is dependency-free pure Python.

## Performance

- Pure-Python Transformer inference is usable for demos and small experiments,
  but slower than the fixed carrier.
- Larger Transformer models quickly become expensive in pure Python.

## V2 Work

- Better carrier corpora.
- Better trained Transformer models.
- Faster pure-Python inference.
- Stronger frame integrity if a new frame version is introduced.
- Autoresearch-style experiment loops.
