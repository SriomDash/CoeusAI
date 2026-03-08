import hashlib
import re
import uuid

def generate_stable_user_id(user_name: str) -> str:
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', user_name.lower())
    digest = hashlib.sha256(clean_name.encode()).hexdigest()[:12]
    return f"{clean_name}_{digest}"

def generate_file_id() -> str:
    return str(uuid.uuid4())