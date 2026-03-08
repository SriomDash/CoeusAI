import hashlib

def generate_file_hash(file_bytes: bytes) -> str:
    """
    Generates a SHA-256 hash from file bytes.
    Used for deduplication to prevent uploading the exact same file twice.
    """
    
    sha256 = hashlib.sha256()
    
   
    sha256.update(file_bytes)
    
    
    return sha256.hexdigest()