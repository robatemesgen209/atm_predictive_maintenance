import hashlib, hmac, os, secrets
import streamlit as st
from db import get_conn, now_iso

ITERATIONS = 310_000

def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"{salt.hex()}:{digest.hex()}"

def _verify(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), ITERATIONS).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except Exception:
        return False

def user_count():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

def create_user(username, password, role, district="", full_name=""):
    username = username.strip().lower()
    if len(username) < 3 or len(password) < 10:
        raise ValueError("Username must be at least 3 characters and password at least 10 characters.")
    with get_conn() as conn:
        conn.execute("""INSERT INTO users(username,password_hash,role,district,full_name,is_active,created_at)
                        VALUES(?,?,?,?,?,1,?)""",
                     (username, _hash_password(password), role, district.strip(), full_name.strip(), now_iso()))

def authenticate(username, password):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username.strip().lower(),)).fetchone()
    if not row or not row["is_active"] or not _verify(password, row["password_hash"]):
        return None
    return {k: row[k] for k in ("id","username","role","district","full_name")}

def require_login():
    if "user" not in st.session_state:
        st.warning("Please sign in to continue.")
        st.stop()
    return st.session_state.user

def logout():
    st.session_state.pop("user", None)
    st.rerun()


def reset_password(username, new_password):
    if len(new_password) < 10:
        raise ValueError("Password must be at least 10 characters.")
    with get_conn() as conn:
        cur = conn.execute("UPDATE users SET password_hash=? WHERE username=?",
                           (_hash_password(new_password), username.strip().lower()))
        if cur.rowcount == 0:
            raise ValueError("User account not found.")
