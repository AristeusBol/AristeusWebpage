import pathlib


def resolve_root(sample_id, candidates=("train", "test", ".")):
    sample_path = pathlib.Path(sample_id)
    for candidate in candidates:
        if pathlib.Path(candidate, sample_path).exists():
            return pathlib.Path(candidate)
    raise FileNotFoundError(
        f"Could not locate image '{sample_id}' (tried {', '.join(repr(c) for c in candidates)})"
    )
