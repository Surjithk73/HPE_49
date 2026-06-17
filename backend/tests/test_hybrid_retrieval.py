#!/usr/bin/env python3
"""
Diagnostic script for the hybrid retrieval pipeline.

Verifies that BM25 (lexical), BGE-large (vector), and RRF (fusion)
are all working correctly. Shows side-by-side rankings with scores
for a set of test queries.

Usage:
    cd backend
    python tests/test_hybrid_retrieval.py
"""
import sys
import os
import time

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from pipeline.schema_loader import load_schema
from pipeline.normalizer import QueryNormalizer
from pipeline import embeddings
from pipeline.schema_linker import SchemaLinker, reciprocal_rank_fusion, _tokenize

import numpy as np


# ── Formatting helpers ────────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def header(title: str):
    print(f"\n{BOLD}{'═' * 70}")
    print(f"  {title}")
    print(f"{'═' * 70}{RESET}")

def subheader(title: str):
    print(f"\n{CYAN}── {title} ──{RESET}")


# ── Load components ───────────────────────────────────────────────────────────

header("QueryCraft Hybrid Retrieval Diagnostics")

print(f"\n{DIM}Loading schema...{RESET}")
schema_path = os.path.join(BACKEND_DIR, "schema_store", "enriched_schema.yaml")
loader = load_schema(schema_path)
schema = loader.get_schema()
table_names = [k for k, v in schema.items() if isinstance(v, dict) and "columns" in v]
print(f"  Schema: {len(table_names)} tables — {', '.join(table_names)}")

normalizer = QueryNormalizer()
linker = SchemaLinker(schema)


# ── Test 1: BM25 ─────────────────────────────────────────────────────────────

header("Test 1: BM25 Lexical Search")

bm25_ok = linker._ensure_bm25_index()
if not bm25_ok:
    print(f"\n  {YELLOW}[FAIL] BM25 index failed to build!{RESET}")
    print("    Make sure `rank-bm25` is installed: pip install rank-bm25")
    sys.exit(1)

print(f"  {GREEN}[OK] BM25 index ready — {len(linker._bm25_table_names)} tables indexed{RESET}")
print(f"  Model: BM25Okapi (rank-bm25)")

# Show tokenization example
sample = "show average cpu busy time per cpu"
tokens = _tokenize(sample)
print(f"\n  Tokenization example:")
print(f"    Input:  \"{sample}\"")
print(f"    Tokens: {tokens}")

# BM25 scores for test queries
bm25_queries = [
    "show cpu busy time per cpu",
    "disk read write operations",
    "process memory usage",
    "transaction management facility",
    "file io per opener",
]

print(f"\n  {BOLD}BM25 Rankings:{RESET}")
for q in bm25_queries:
    query_tokens = _tokenize(q)
    scores = linker._bm25.get_scores(query_tokens)
    order = np.argsort(scores)[::-1]

    print(f"\n  Query: \"{q}\"")
    print(f"  {'Rank':<6} {'Table':<10} {'BM25 Score':<12}")
    print(f"  {'─'*6} {'─'*10} {'─'*12}")
    for rank, idx in enumerate(order, 1):
        name = linker._bm25_table_names[idx]
        score = scores[idx]
        marker = f" {GREEN}◄{RESET}" if rank <= 3 and score > 0 else ""
        print(f"  {rank:<6} {name:<10} {score:<12.4f}{marker}")


# ── Test 2: BGE-large Vector Search ───────────────────────────────────────────

header("Test 2: BGE-large Vector Search (BAAI/bge-large-en-v1.5)")

print(f"\n{DIM}Waiting for embedding model to load...{RESET}")
t0 = time.time()
ready = embeddings.wait(timeout=180)
elapsed = time.time() - t0

if not ready:
    print(f"\n  {YELLOW}[FAIL] Embedding model failed to load within 180s!{RESET}")
    print("    Check your internet connection — the model downloads on first run (~1.3GB).")
    sys.exit(1)

model = embeddings.get()
print(f"  {GREEN}[OK] BGE-large model ready{RESET} (loaded in {elapsed:.1f}s)")
print(f"  Model: {embeddings.MODEL_NAME}")
print(f"  Embedding dim: {model.get_sentence_embedding_dimension()}")

# Ensure table embeddings are built
emb_ok = linker._ensure_table_embeddings()
assert emb_ok, "Table embeddings failed to build"
print(f"  Table embeddings: {linker._table_embeddings.shape}")

vector_queries = [
    "show cpu busy time per cpu",
    "disk read write operations",
    "process memory usage",
    "transaction management facility",
    "file io per opener",
]

print(f"\n  {BOLD}Vector Similarity Rankings:{RESET}")
for q in vector_queries:
    query_vec = np.asarray(model.encode([q], normalize_embeddings=True))[0]
    sims = linker._table_embeddings @ query_vec
    order = np.argsort(sims)[::-1]

    print(f"\n  Query: \"{q}\"")
    print(f"  {'Rank':<6} {'Table':<10} {'Cosine Sim':<12}")
    print(f"  {'─'*6} {'─'*10} {'─'*12}")
    for rank, idx in enumerate(order, 1):
        name = linker._table_embedding_names[idx]
        sim = sims[idx]
        marker = f" {GREEN}◄{RESET}" if rank <= 3 else ""
        print(f"  {rank:<6} {name:<10} {sim:<12.4f}{marker}")


# ── Test 3: RRF Fusion ───────────────────────────────────────────────────────

header("Test 3: Reciprocal Rank Fusion (RRF)")

rrf_queries = [
    "show cpu busy time per cpu",
    "disk read write operations",
    "process memory usage",
    "compare cpu and disk performance",
    "transaction management facility",
]

print(f"\n  {BOLD}Side-by-Side: BM25 vs BGE vs RRF{RESET}")
for q in rrf_queries:
    bm25_ranked = linker._bm25_rank(q)
    vector_ranked = linker._vector_rank(q)
    fused = reciprocal_rank_fusion([bm25_ranked, vector_ranked], k=60)

    print(f"\n  Query: \"{q}\"")
    print(f"  {'Rank':<6} {'BM25':<12} {'BGE-large':<12} {'RRF Winner':<12} {'RRF Score':<10}")
    print(f"  {'─'*6} {'─'*12} {'─'*12} {'─'*12} {'─'*10}")

    for rank in range(min(len(table_names), 5)):
        bm25_name = bm25_ranked[rank] if rank < len(bm25_ranked) else "—"
        vec_name = vector_ranked[rank] if rank < len(vector_ranked) else "—"
        rrf_name = fused[rank][0] if rank < len(fused) else "—"
        rrf_score = fused[rank][1] if rank < len(fused) else 0.0
        marker = f" {GREEN}◄{RESET}" if rank < 3 else ""
        print(f"  {rank+1:<6} {bm25_name:<12} {vec_name:<12} {rrf_name:<12} {rrf_score:<10.6f}{marker}")


# ── Test 4: Full pipeline integration ─────────────────────────────────────────

header("Test 4: Full Pipeline Integration (link_schema)")

integration_queries = [
    ("show average cpu busy time per cpu", None),
    ("list disk device reads and writes", None),
    ("compare cpu and process utilization", None),
    ("transaction commit rate", None),
    ("file io statistics", None),
]

print(f"\n  {BOLD}End-to-end: NL query -> normalized -> domain -> selected tables -> DDL{RESET}")
for raw_query, _ in integration_queries:
    norm = normalizer.normalize(raw_query)
    norm_text = norm["normalized_text"]
    domain = norm["domain_category"]

    # For multi-domain, show what the hybrid retrieval picks
    if domain == "multi":
        selected = linker._score_and_select_tables(norm_text)
    else:
        selected = [domain]

    context = linker.link_schema(norm_text, domain)

    print(f"\n  Query:      \"{raw_query}\"")
    print(f"  Normalized: \"{norm_text}\"")
    print(f"  Domain:     {domain}")
    print(f"  Selected:   {selected}")
    print(f"  DDL length: {len(context)} chars")

    # Show which tables appear in the DDL
    import re
    ddl_tables = re.findall(r'CREATE TABLE macht413\.(\w+)', context)
    print(f"  DDL tables: {ddl_tables}")


# ── Test 5: Sanity checks ────────────────────────────────────────────────────

header("Test 5: Sanity Checks")

all_passed = True

# 5a: BM25 should rank "cpu" table first for CPU queries
bm25_cpu = linker._bm25_rank("cpu busy time utilization")
if bm25_cpu[0] == "cpu":
    print(f"  {GREEN}[OK]{RESET} BM25 ranks 'cpu' first for CPU queries")
else:
    print(f"  {YELLOW}[FAIL]{RESET} BM25 ranked '{bm25_cpu[0]}' first for CPU query (expected 'cpu')")
    all_passed = False

# 5b: BGE should rank a disk-related table first for disk queries
vec_disk = linker._vector_rank("disk read write io operations")
disk_tables = {"disc", "dfile", "dopen"}
if vec_disk[0] in disk_tables:
    print(f"  {GREEN}[OK]{RESET} BGE ranks '{vec_disk[0]}' first for disk queries (disk-related [OK])")
else:
    print(f"  {YELLOW}[FAIL]{RESET} BGE ranked '{vec_disk[0]}' first for disk query (expected one of {disk_tables})")
    all_passed = False

# 5c: RRF should rank 'proc' in top 3 for process queries
bm25_r = linker._bm25_rank("process memory busy time")
vec_r = linker._vector_rank("process memory busy time")
fused_r = reciprocal_rank_fusion([bm25_r, vec_r], k=60)
top3_rrf = [name for name, _ in fused_r[:3]]
if "proc" in top3_rrf:
    pos = top3_rrf.index("proc") + 1
    print(f"  {GREEN}[OK]{RESET} RRF ranks 'proc' #{pos} for process queries (top 3 [OK])")
else:
    print(f"  {YELLOW}[FAIL]{RESET} RRF top-3 is {top3_rrf} for process query ('proc' missing)")
    all_passed = False

# 5d: Embedding dimension check
dim = model.get_sentence_embedding_dimension()
if dim == 1024:
    print(f"  {GREEN}[OK]{RESET} Embedding dimension is 1024 (BGE-large confirmed)")
else:
    print(f"  {YELLOW}[FAIL]{RESET} Embedding dimension is {dim} (expected 1024 for BGE-large)")
    all_passed = False

# 5e: Model name check
if "bge-large" in embeddings.MODEL_NAME.lower():
    print(f"  {GREEN}[OK]{RESET} Model name contains 'bge-large': {embeddings.MODEL_NAME}")
else:
    print(f"  {YELLOW}[FAIL]{RESET} Unexpected model name: {embeddings.MODEL_NAME}")
    all_passed = False

# 5f: BM25 produces non-zero scores
scores = linker._bm25.get_scores(_tokenize("cpu busy time"))
if np.any(scores > 0):
    print(f"  {GREEN}[OK]{RESET} BM25 produces non-zero scores (max={scores.max():.4f})")
else:
    print(f"  {YELLOW}[FAIL]{RESET} BM25 scores are all zero!")
    all_passed = False


# ── Summary ──────────────────────────────────────────────────────────────────

header("Summary")
print(f"""
  Embedding Model:  {embeddings.MODEL_NAME}
  Embedding Dim:    {model.get_sentence_embedding_dimension()}
  BM25 Index:       {len(linker._bm25_table_names)} tables
  Table Embeddings: {linker._table_embeddings.shape}
  Tables:           {', '.join(table_names)}
""")

if all_passed:
    print(f"  {GREEN}{BOLD}[OK] All sanity checks passed!{RESET}")
    print(f"  {GREEN}  BM25 lexical search — working{RESET}")
    print(f"  {GREEN}  BGE-large vector search — working{RESET}")
    print(f"  {GREEN}  Reciprocal Rank Fusion — working{RESET}")
else:
    print(f"  {YELLOW}{BOLD}⚠ Some checks failed — review output above{RESET}")

print()
