# RAG Evaluation (M3)

Methodology
-----------
- **Corpus**: 12 controlled synthetic listings (Casablanca/Marrakech/Rabat, French + English wording), insertion order = stable ids 1-12.
- **Embeddings**: `fastembed` default model (bge-small-en-v1.5, 384 dims) on CPU via ONNX Runtime.
- **Vector store**: SQLite table `rag_chunks` (chunk text + float32 embedding BLOB); cosine similarity computed in Python over all chunks.
- **Index**: rebuilt per chunk size; each listing is `title + description` chunked on whitespace.
- **Retrieval**: top-5 chunks; a listing is "retrieved" if it appears in the top-5.
- **Answer/refusal**: a question is refused when the top chunk's cosine similarity is below `DARPILOT_RAG_THRESHOLD` (default 0.60).
- **Hit**:
  - mapping question (expected id): hit if expected id in top-5 results;
  - refusal question (no expected id): hit if the answer is refused.

Evaluation set
--------------
34 questions (>= 30 required): 24 mapping (10 English, 10 mapping + French variants) and 10 refusal/nonsense questions. Stored in `data/eval_questions.json`.
Script: `scripts/eval_rag.py`.

Results
-------
| Chunk size | Hits | Questions | Hit rate |
|------------|------|-----------|----------|
| 60 words   | 32   | 34        | 94.1%    |
| 120 words  | 32   | 34        | 94.1%    |

Both chunk sizes give the same hit rate because every listing description is
short (< 60 words), so each listing is a single chunk regardless of chunk
size. With longer descriptions the chunk size would matter more.

Misses (2, both borderline refusal cases):
- "university enrollment Morocco" -> top score 0.600 (not refused, threshold 0.60)
- "hotel booking Agadir" -> top score 0.623 (not refused)

These sit right at the refusal threshold, showing the threshold is a real
tuning knob: raising it reduces false positives on unrelated queries but
risks refusing legitimate low-score matches. The 0.60 default keeps the demo
usable while refusing clearly unrelated queries.

Notes
-----
- fastembed downloads the embedding model (~100 MB) into a cache on first use; no PyTorch/GPU required, fits the 8 GB RAM / no-GPU constraint.
- All data is synthetic; no real names, phone numbers, or listings are used.
