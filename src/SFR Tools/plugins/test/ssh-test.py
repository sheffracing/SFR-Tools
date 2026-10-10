from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from utils.git import Git, find_github_repo
from utils import settings, build
from pathlib import Path
import plugin
import requests

email = "your_email@example.com"
passphrase = b"your-passphrase"

private_path = Path(__file__).parents[0] / "keys" / "sign"
public_path = Path(__file__).parents[0] / "keys" / "sign.public"

def verify():
    try:
        if not private_path.exists() or not public_path.exists():
            return False
        
        private_key = serialization.load_ssh_private_key(
            private_path.read_bytes(),
            password=None,
        )
        public_key = serialization.load_ssh_public_key(
            public_path.read_bytes()
        )

    except (ValueError, TypeError, ValueError):
        return False

    private_public = private_key.public_key()
    return (
        private_public.public_bytes(
            serialization.Encoding.OpenSSH,
            serialization.PublicFormat.OpenSSH,
        )
        == public_key.public_bytes(
            serialization.Encoding.OpenSSH,
            serialization.PublicFormat.OpenSSH,
        )
    )
def is_key_uploaded():
    public_key = serialization.load_ssh_public_key(
        public_path.read_bytes()
    )
    
def generate_key(email):
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    ) + b" " + email.encode() + b"\n"
    return private_key_bytes, public_key_bytes

git = Git()
user = git.user.get_user()
email = user.email or f"{user.id}+{user.login}@users.noreply.github.com"

#priv, pub = generate_key(email)
#print(priv, pub)
#private_path.write_bytes(priv)
#public_path.write_bytes(pub)

git.upload_ssh_key()
print(verify())
git.get_uploaded_ssh_keys()

import os
if os.name != "nt":
    private_path.chmod(0o600)