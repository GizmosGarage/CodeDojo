import json
from pathlib import Path


def load_skill_tree(data_dir: Path) -> dict:
    path = data_dir / "skill_tree.json"
    with open(path) as f:
        return json.load(f)
