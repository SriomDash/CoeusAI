import uuid

def generate_job_id() -> str:
    return str(uuid.uuid4())