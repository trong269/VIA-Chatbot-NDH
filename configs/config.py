import yaml
from pathlib import Path

def load_config(path: str = "configs/config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(p, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)