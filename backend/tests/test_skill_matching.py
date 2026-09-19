from app.services.skills import skill_compatibility, normalize_skill, build_skill_graph, cosine_similarity, embed_text


def test_exact_skill_match_is_perfect():
    assert skill_compatibility(["Python", "SQL"], "Python") == 1.0


def test_normalize_skill_lowercases_and_strips_punctuation():
    assert normalize_skill("  React.JS! ") == "react.js"


def test_no_related_skill_gives_low_score():
    build_skill_graph(["Python", "React", "Vue", "JavaScript", "Welding"])
    score = skill_compatibility(["Welding"], "React")
    assert score < 0.5


def test_transferable_skill_scores_above_zero():
    build_skill_graph(["React", "Vue", "JavaScript", "TypeScript"])
    # Employee knows Vue/JavaScript/TypeScript but task requires React --
    # the skill graph should recognize these as transferable (per spec
    # example), giving a materially higher score than an unrelated skill.
    score_transferable = skill_compatibility(["Vue", "JavaScript", "TypeScript"], "React")
    score_unrelated = skill_compatibility(["Welding"], "React")
    assert score_transferable > score_unrelated
    assert score_transferable > 0.3


def test_cosine_similarity_of_identical_vectors_is_high():
    v = embed_text("Python")
    assert cosine_similarity(v, v) > 0.99


def test_cosine_similarity_handles_missing_vectors():
    assert cosine_similarity(None, [1.0, 2.0]) == 0.0
    assert cosine_similarity([], []) == 0.0
