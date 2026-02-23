import yaml
import os
from jinja2 import Template
from pathlib import Path

def load_prompt(file_path: str, prompt_key: str, **kwargs) -> str:
    """
    Loads a YAML file using Pathlib for cross-platform path compatibility.
    """
    # 1. Convert the string path to a Path object to fix slashes automatically
    # This turns 'backend/prompts/...' into 'backend\\prompts\\...' on Windows
    relative_path = Path(file_path)
    
    # 2. Get the absolute path starting from your project root
    # This uses your current working directory (E:\CoeusAI)
    full_path = Path.cwd() / relative_path

    if not full_path.exists():
        raise FileNotFoundError(f"Prompt file not found at: {full_path}")

    with open(full_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    raw_template = data.get(prompt_key)
    if not raw_template:
        raise ValueError(f"Key '{prompt_key}' not found in {full_path}")
    
    template = Template(raw_template)
    return template.render(**kwargs)