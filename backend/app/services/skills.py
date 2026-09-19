"""
Semantic skill matching.

Pipeline (per spec):
  task requirement text -> normalize -> embedding -> cosine similarity
  -> skill graph lookup (transferable skills) -> combined compatibility score

Embedding backend:
  We try to use `sentence-transformers` (BGE/E5-class model) if it is
  installed and a model can be loaded offline. In hackathon / restricted
  network environments this is frequently unavailable, so we fall back to a
  deterministic hashed character-n-gram embedding (a lightweight, dependency
  free stand-in for a real sentence embedding). Both paths produce
  fixed-length vectors that support cosine similarity, so the rest of the
  system (candidate generation, storage, scoring) is completely agnostic to
  which backend produced the vector. This satisfies the "local deterministic
  fallback" requirement without faking accuracy claims.
"""
import hashlib
import math
import re
from functools import lru_cache
from typing import Iterable, List, Optional

import networkx as nx

EMBED_DIM = 128

_USE_ST = False
_st_model = None
try:  # pragma: no cover - optional heavy dependency
    from sentence_transformers import SentenceTransformer  # type: ignore
    _st_model = SentenceTransformer("all-MiniLM-L6-v2")
    _USE_ST = True
except Exception:
    _USE_ST = False


def normalize_skill(name: str) -> str:
    return re.sub(r"[^a-z0-9+#. ]", "", name.strip().lower())


def _hash_embedding(text: str, dim: int = EMBED_DIM) -> List[float]:
    """Deterministic character-trigram hashed embedding (fallback backend)."""
    text = normalize_skill(text)
    vec = [0.0] * dim
    tokens = text.split() or [text]
    grams = set()
    for tok in tokens:
        padded = f"^{tok}$"
        for i in range(len(padded) - 2):
            grams.add(padded[i:i + 3])
        grams.add(tok)
    if not grams:
        grams = {text or "unknown"}
    for gram in grams:
        h = int(hashlib.sha256(gram.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_text(text: str) -> List[float]:
    if _USE_ST and _st_model is not None:  # pragma: no cover
        vec = _st_model.encode(text, normalize_embeddings=True)
        return vec.tolist()
    return _hash_embedding(text)


def cosine_similarity(a: Optional[List[float]], b: Optional[List[float]]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a[:n])) or 1e-9
    nb = math.sqrt(sum(x * x for x in b[:n])) or 1e-9
    sim = dot / (na * nb)
    return max(0.0, min(1.0, (sim + 1) / 2 if not _USE_ST else max(0.0, sim)))


# ---------------------------------------------------------------------------
# Skill knowledge graph (transferable-skill relationships).
# Using NetworkX as the lightweight substitute for Neo4j in the MVP, per the
# explicit "NetworkX if Neo4j is excessive for the MVP" guidance. The graph
# API surface (add relationship, shortest transferability path) mirrors what
# a Neo4j Cypher query would return, so swapping backends later only touches
# this module.
# ---------------------------------------------------------------------------
SKILL_GRAPH = nx.Graph()

DEFAULT_SKILL_RELATIONSHIPS = [
    ("react", "vue", 0.65), ("react", "javascript", 0.8), ("react", "typescript", 0.75),
    ("vue", "javascript", 0.8), ("vue", "typescript", 0.7),
    ("javascript", "typescript", 0.85), ("javascript", "node.js", 0.75),
    ("python", "fastapi", 0.8), ("python", "django", 0.75), ("python", "flask", 0.75),
    ("python", "data analysis", 0.6), ("python", "machine learning", 0.6),
    ("fastapi", "django", 0.55), ("fastapi", "flask", 0.6),
    ("machine learning", "data analysis", 0.7), ("machine learning", "deep learning", 0.85),
    ("deep learning", "pytorch", 0.8), ("deep learning", "tensorflow", 0.8),
    ("sql", "postgresql", 0.85), ("sql", "data analysis", 0.6), ("postgresql", "mysql", 0.75),
    ("aws", "azure", 0.6), ("aws", "devops", 0.7), ("devops", "docker", 0.75),
    ("docker", "kubernetes", 0.8), ("kubernetes", "devops", 0.75),
    ("project management", "agile", 0.7), ("agile", "scrum", 0.85),
    ("ui design", "ux design", 0.85), ("ux design", "figma", 0.7),
    ("java", "spring boot", 0.75), ("java", "kotlin", 0.6),
    ("c#", ".net", 0.8), (".net", "azure", 0.55),
    ("networking", "security", 0.5), ("security", "devops", 0.4),
]


def build_skill_graph(skill_names: Iterable[str]):
    SKILL_GRAPH.clear()
    for name in skill_names:
        SKILL_GRAPH.add_node(normalize_skill(name))
    for a, b, w in DEFAULT_SKILL_RELATIONSHIPS:
        na, nb = normalize_skill(a), normalize_skill(b)
        if na in SKILL_GRAPH.nodes and nb in SKILL_GRAPH.nodes:
            SKILL_GRAPH.add_edge(na, nb, weight=w)


def graph_transferability(skill_have: str, skill_need: str) -> float:
    """Return a 0..1 transferability score via shortest weighted path in the skill graph."""
    a, b = normalize_skill(skill_have), normalize_skill(skill_need)
    if a == b:
        return 1.0
    if a not in SKILL_GRAPH.nodes or b not in SKILL_GRAPH.nodes:
        return 0.0
    try:
        path = nx.shortest_path(SKILL_GRAPH, a, b, weight=lambda u, v, d: 1 - d.get("weight", 0.3))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return 0.0
    if len(path) > 3:  # too many hops -> weak transfer signal
        return 0.0
    strength = 1.0
    for u, v in zip(path[:-1], path[1:]):
        strength *= SKILL_GRAPH[u][v]["weight"]
    return strength


def skill_compatibility(
    employee_skills: List[str],
    required_skill: str,
    embeddings_cache: Optional[dict] = None,
) -> float:
    """
    Final compatibility score for one required skill against an employee's
    skill set: max over (exact match, graph transferability, embedding
    cosine similarity).
    """
    req_norm = normalize_skill(required_skill)
    best = 0.0
    req_vec = (embeddings_cache or {}).get(req_norm) if embeddings_cache else None
    if req_vec is None:
        req_vec = embed_text(required_skill)

    for have in employee_skills:
        have_norm = normalize_skill(have)
        if have_norm == req_norm:
            return 1.0
        graph_score = graph_transferability(have_norm, req_norm)
        have_vec = (embeddings_cache or {}).get(have_norm) if embeddings_cache else None
        if have_vec is None:
            have_vec = embed_text(have)
        embed_score = cosine_similarity(have_vec, req_vec)
        combined = max(graph_score, 0.55 * embed_score + 0.45 * graph_score)
        best = max(best, combined)
    return round(best, 4)


def skill_compatibility_detailed(employee_skills: List[str], required_skill: str) -> dict:
    """
    Same scoring as skill_compatibility(), but also reports HOW the best
    match was found -- "exact" (employee literally has the skill),
    "transferable" (no exact match, but the skill graph / embedding found a
    related skill -- e.g. Vue/JS/TypeScript covering a React requirement),
    or "none" (no usable signal at all). This is what lets a hard
    requirement degrade gracefully instead of failing outright the moment
    the one person with the exact skill is unavailable, and lets the UI
    prove the transferability claim with a real number instead of asserting
    it.
    """
    req_norm = normalize_skill(required_skill)
    req_vec = embed_text(required_skill)
    best_score = 0.0
    best_via = "none"
    best_source_skill = None

    for have in employee_skills:
        have_norm = normalize_skill(have)
        if have_norm == req_norm:
            return {"skill": required_skill, "score": 1.0, "matched_via": "exact", "matched_from": have}
        graph_score = graph_transferability(have_norm, req_norm)
        embed_score = cosine_similarity(embed_text(have), req_vec)
        combined = max(graph_score, 0.55 * embed_score + 0.45 * graph_score)
        if combined > best_score:
            best_score = combined
            best_via = "transferable" if combined > 0.15 else "none"
            best_source_skill = have

    return {
        "skill": required_skill, "score": round(best_score, 4),
        "matched_via": best_via if best_score > 0 else "none",
        "matched_from": best_source_skill if best_via == "transferable" else None,
    }


def embedding_backend_name() -> str:
    return "sentence-transformers/all-MiniLM-L6-v2" if _USE_ST else "hashed-ngram-fallback-v1"
