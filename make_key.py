"""Print the hashes of a new passkey, for pasting into the installer and the app.

    python make_key.py my_new_passkey

Two different hashes are needed:

  1. installer.iss  → MyPasskeyHash  (plain SHA-256; Inno Setup's
     GetSHA256OfString hashes the ANSI bytes, which matches exactly for an
     ASCII passkey).
  2. SalesManager.py (and FeedStoreSales.py, which regenerates it)
     → the _ACT_HASHES set  (salted PBKDF2, used by the app's activation
     screen; much slower to guess than plain SHA-256).

Keep the plaintext out of the repository — only the hashes belong in files.
"""
import hashlib
import sys

ACT_SALT = b"hdm-pos-install-v1"          # must match _ACT_SALT in the app

key = sys.argv[1] if len(sys.argv) > 1 else input("Passkey: ")
key = key.strip()

print("installer.iss  MyPasskeyHash:")
print("  " + hashlib.sha256(key.encode("utf-8")).hexdigest())
print()
print("SalesManager.py  _ACT_HASHES entry:")
print("  " + hashlib.pbkdf2_hmac("sha256", key.encode("utf-8"), ACT_SALT, 200_000).hex())
