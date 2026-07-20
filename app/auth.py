"""Bearer token auth helpers."""

from __future__ import annotations

from functools import wraps

from flask import g, jsonify, request

from app.store import find_user_by_token


def get_bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[len("Bearer ") :].strip()
    return token or None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        token = get_bearer_token()
        if not token:
            return jsonify({"error": "unauthorized", "message": "Missing or invalid token"}), 401
        user = find_user_by_token(token)
        if not user:
            return jsonify({"error": "unauthorized", "message": "Invalid token"}), 401
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped
