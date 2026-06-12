from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import unquote, urlparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "unreleased.db"
SESSION_COOKIE = "unreleased_session"
PASSWORD_ITERATIONS = 310_000
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_PROFILE_IMAGE_BYTES = 2 * 1024 * 1024
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def db_connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with db_connect() as database:
        database.executescript(
            """
            PRAGMA journal_mode = WAL;

            CREATE TABLE IF NOT EXISTS invite_codes (
                code TEXT PRIMARY KEY COLLATE NOCASE,
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                max_uses INTEGER CHECK (max_uses IS NULL OR max_uses > 0),
                use_count INTEGER NOT NULL DEFAULT 0 CHECK (use_count >= 0),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash BLOB NOT NULL,
                password_salt BLOB NOT NULL,
                password_iterations INTEGER NOT NULL,
                invite_code TEXT NOT NULL COLLATE NOCASE,
                profile_image BLOB,
                profile_mime TEXT,
                joined_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (invite_code) REFERENCES invite_codes(code)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                thread_title TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
            CREATE INDEX IF NOT EXISTS idx_comments_user_created ON comments(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_posts_user_created ON posts(user_id, created_at DESC);
            """
        )

        default_code = os.environ.get("UNRELEASED_DEFAULT_INVITE", "UNRELEASED2026").strip()
        if default_code:
            database.execute(
                """
                INSERT OR IGNORE INTO invite_codes (code, active, max_uses, use_count, created_at)
                VALUES (?, 1, NULL, 0, ?)
                """,
                (default_code, iso_now()),
            )


def hash_password(password: str, salt: bytes | None = None, iterations: int = PASSWORD_ITERATIONS):
    salt = salt or secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return password_hash, salt, iterations


def verify_password(password: str, expected_hash: bytes, salt: bytes, iterations: int) -> bool:
    actual_hash, _, _ = hash_password(password, salt, iterations)
    return secrets.compare_digest(actual_hash, expected_hash)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def detect_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def parse_profile_image(data_url: str) -> tuple[bytes, str]:
    match = re.fullmatch(r"data:(image/(?:png|jpeg|gif|webp));base64,(.+)", data_url, re.DOTALL)
    if not match:
        raise ValueError("Profile picture must be a PNG, JPEG, GIF, or WebP image.")
    try:
        image_data = base64.b64decode(match.group(2), validate=True)
    except ValueError as error:
        raise ValueError("The profile picture data is invalid.") from error
    if len(image_data) > MAX_PROFILE_IMAGE_BYTES:
        raise ValueError("Profile picture must be 2 MB or smaller.")
    detected_mime = detect_image_mime(image_data)
    if not detected_mime:
        raise ValueError("The uploaded file is not a supported image.")
    return image_data, detected_mime


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "UnreleasedMe/1.0"

    def log_message(self, format_string: str, *args) -> None:
        sys.stdout.write(f"[{self.log_date_time_string()}] {format_string % args}\n")

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'self'")
        super().end_headers()

    def translate_path(self, path: str) -> str:
        parsed_path = unquote(urlparse(path).path)
        relative_path = parsed_path.lstrip("/") or "index.html"
        candidate = (ROOT / relative_path).resolve()
        if ROOT not in candidate.parents and candidate != ROOT:
            return str(ROOT / "__not_found__")
        return str(candidate)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed.path)
            return
        super().do_GET()

    def do_POST(self) -> None:
        self.handle_api_write("POST")

    def do_PUT(self) -> None:
        self.handle_api_write("PUT")

    def send_json(self, status: int, payload: dict | list, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: int, message: str) -> None:
        self.send_json(status, {"error": message})

    def read_json(self) -> dict:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid request size.") from error
        if content_length <= 0 or content_length > MAX_JSON_BYTES:
            raise ValueError("Request body is empty or too large.")
        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("Request body must be valid JSON.") from error
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def request_cookie(self, name: str) -> str | None:
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get(name)
        return morsel.value if morsel else None

    def current_user(self, database: sqlite3.Connection) -> sqlite3.Row | None:
        session_token = self.request_cookie(SESSION_COOKIE)
        if not session_token:
            return None
        now = iso_now()
        database.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        return database.execute(
            """
            SELECT users.*
            FROM users
            JOIN sessions ON sessions.user_id = users.id
            WHERE sessions.token_hash = ? AND sessions.expires_at > ?
            """,
            (token_hash(session_token), now),
        ).fetchone()

    def require_user(self, database: sqlite3.Connection) -> sqlite3.Row | None:
        user = self.current_user(database)
        if not user:
            self.send_error_json(HTTPStatus.UNAUTHORIZED, "Please sign in to continue.")
        return user

    def session_headers(self, user_id: int, remember: bool, database: sqlite3.Connection) -> dict[str, str]:
        raw_token = secrets.token_urlsafe(32)
        duration = timedelta(days=30 if remember else 1)
        expires_at = utc_now() + duration
        database.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash(raw_token), user_id, iso_now(), expires_at.isoformat()),
        )
        cookie = f"{SESSION_COOKIE}={raw_token}; Path=/; HttpOnly; SameSite=Lax"
        if remember:
            cookie += f"; Max-Age={int(duration.total_seconds())}"
        return {"Set-Cookie": cookie}

    def user_payload(self, user: sqlite3.Row) -> dict:
        return {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "inviteCode": user["invite_code"],
            "joinedAt": user["joined_at"],
            "hasProfileImage": bool(user["profile_image"]),
            "profileImageUrl": f"/api/profile-image?v={user['updated_at']}" if user["profile_image"] else "/assets/default-profile.png",
        }

    def handle_api_get(self, path: str) -> None:
        with db_connect() as database:
            if path == "/api/health":
                self.send_json(HTTPStatus.OK, {"ok": True})
                return
            if path == "/api/me":
                user = self.require_user(database)
                if user:
                    self.send_json(HTTPStatus.OK, {"user": self.user_payload(user)})
                return
            if path == "/api/profile-image":
                user = self.current_user(database)
                if not user or not user["profile_image"]:
                    self.send_response(HTTPStatus.FOUND)
                    self.send_header("Location", "/assets/default-profile.png")
                    self.end_headers()
                    return
                image_data = user["profile_image"]
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", user["profile_mime"])
                self.send_header("Content-Length", str(len(image_data)))
                self.send_header("Cache-Control", "private, no-cache")
                self.end_headers()
                self.wfile.write(image_data)
                return
            if path == "/api/activity":
                user = self.require_user(database)
                if not user:
                    return
                comments = database.execute(
                    "SELECT id, thread_title AS title, body, created_at AS date FROM comments WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
                    (user["id"],),
                ).fetchall()
                posts = database.execute(
                    "SELECT id, title, body, created_at AS date FROM posts WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
                    (user["id"],),
                ).fetchall()
                self.send_json(
                    HTTPStatus.OK,
                    {"comments": [dict(row) for row in comments], "posts": [dict(row) for row in posts]},
                )
                return
        self.send_error_json(HTTPStatus.NOT_FOUND, "API endpoint not found.")

    def handle_api_write(self, method: str) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            self.send_error_json(HTTPStatus.NOT_FOUND, "Endpoint not found.")
            return
        try:
            payload = self.read_json()
        except ValueError as error:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
            return

        try:
            if method == "POST" and path == "/api/register":
                self.api_register(payload)
            elif method == "POST" and path == "/api/login":
                self.api_login(payload)
            elif method == "POST" and path == "/api/logout":
                self.api_logout()
            elif method == "PUT" and path == "/api/profile":
                self.api_update_profile(payload)
            elif method == "POST" and path == "/api/comments":
                self.api_create_comment(payload)
            elif method == "POST" and path == "/api/posts":
                self.api_create_post(payload)
            else:
                self.send_error_json(HTTPStatus.NOT_FOUND, "API endpoint not found.")
        except sqlite3.IntegrityError:
            self.send_error_json(HTTPStatus.CONFLICT, "That username or email is already in use.")

    def api_register(self, payload: dict) -> None:
        username = str(payload.get("username", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        invite_code = str(payload.get("inviteCode", "")).strip()
        if not USERNAME_PATTERN.fullmatch(username):
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Username must be 3-30 letters, numbers, dots, dashes, or underscores.")
            return
        if not EMAIL_PATTERN.fullmatch(email):
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Enter a valid email address.")
            return
        if len(password) < 8 or len(password) > 128:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Password must be 8-128 characters.")
            return
        if not invite_code:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Enter an invite code.")
            return

        password_hash, password_salt, iterations = hash_password(password)
        with db_connect() as database:
            database.execute("BEGIN IMMEDIATE")
            invite = database.execute(
                "SELECT * FROM invite_codes WHERE code = ? COLLATE NOCASE",
                (invite_code,),
            ).fetchone()
            if not invite or not invite["active"] or (invite["max_uses"] is not None and invite["use_count"] >= invite["max_uses"]):
                database.rollback()
                self.send_error_json(HTTPStatus.FORBIDDEN, "That invite code is invalid or no longer available.")
                return
            now = iso_now()
            cursor = database.execute(
                """
                INSERT INTO users (
                    username, email, password_hash, password_salt, password_iterations,
                    invite_code, joined_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (username, email, password_hash, password_salt, iterations, invite["code"], now, now),
            )
            database.execute("UPDATE invite_codes SET use_count = use_count + 1 WHERE code = ?", (invite["code"],))
            headers = self.session_headers(cursor.lastrowid, True, database)
            database.commit()
            user = database.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            self.send_json(HTTPStatus.CREATED, {"user": self.user_payload(user)}, headers)

    def api_login(self, payload: dict) -> None:
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        remember = bool(payload.get("remember", False))
        with db_connect() as database:
            user = database.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
            valid = user and verify_password(password, user["password_hash"], user["password_salt"], user["password_iterations"])
            if not valid:
                self.send_error_json(HTTPStatus.UNAUTHORIZED, "Email or password is incorrect.")
                return
            headers = self.session_headers(user["id"], remember, database)
            database.commit()
            self.send_json(HTTPStatus.OK, {"user": self.user_payload(user)}, headers)

    def api_logout(self) -> None:
        session_token = self.request_cookie(SESSION_COOKIE)
        with db_connect() as database:
            if session_token:
                database.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(session_token),))
        self.send_json(
            HTTPStatus.OK,
            {"ok": True},
            {"Set-Cookie": f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"},
        )

    def api_update_profile(self, payload: dict) -> None:
        username = str(payload.get("username", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        if not USERNAME_PATTERN.fullmatch(username):
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Username must be 3-30 letters, numbers, dots, dashes, or underscores.")
            return
        if not EMAIL_PATTERN.fullmatch(email):
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Enter a valid email address.")
            return
        with db_connect() as database:
            user = self.require_user(database)
            if not user:
                return
            image_sql = ""
            values: list = [username, email, iso_now()]
            if payload.get("removeProfileImage"):
                image_sql = ", profile_image = NULL, profile_mime = NULL"
            elif payload.get("profileImage"):
                try:
                    image_data, image_mime = parse_profile_image(str(payload["profileImage"]))
                except ValueError as error:
                    self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
                    return
                image_sql = ", profile_image = ?, profile_mime = ?"
                values.extend([image_data, image_mime])
            values.append(user["id"])
            database.execute(
                f"UPDATE users SET username = ?, email = ?, updated_at = ?{image_sql} WHERE id = ?",
                values,
            )
            updated_user = database.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
            self.send_json(HTTPStatus.OK, {"user": self.user_payload(updated_user)})

    def api_create_comment(self, payload: dict) -> None:
        title = str(payload.get("threadTitle", "")).strip()
        body = str(payload.get("body", "")).strip()
        if not title or not body or len(title) > 120 or len(body) > 5000:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Comment title or body is invalid.")
            return
        with db_connect() as database:
            user = self.require_user(database)
            if not user:
                return
            cursor = database.execute(
                "INSERT INTO comments (user_id, thread_title, body, created_at) VALUES (?, ?, ?, ?)",
                (user["id"], title, body, iso_now()),
            )
            self.send_json(HTTPStatus.CREATED, {"id": cursor.lastrowid})

    def api_create_post(self, payload: dict) -> None:
        title = str(payload.get("title", "")).strip()
        body = str(payload.get("body", "")).strip()
        if not title or not body or len(title) > 160 or len(body) > 20_000:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Post title or body is invalid.")
            return
        with db_connect() as database:
            user = self.require_user(database)
            if not user:
                return
            cursor = database.execute(
                "INSERT INTO posts (user_id, title, body, created_at) VALUES (?, ?, ?, ?)",
                (user["id"], title, body, iso_now()),
            )
            self.send_json(HTTPStatus.CREATED, {"id": cursor.lastrowid})


def main() -> None:
    initialize_database()
    host = os.environ.get("UNRELEASED_HOST", "127.0.0.1")
    port = int(os.environ.get("UNRELEASED_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Unreleased.me running at http://{host}:{port}")
    print(f"Default invite code: {os.environ.get('UNRELEASED_DEFAULT_INVITE', 'UNRELEASED2026')}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
