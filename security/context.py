# security/context.py
import contextvars
from dataclasses import dataclass

_current_token = contextvars.ContextVar("current_token", default=None)
_current_user = contextvars.ContextVar("current_user", default=None)


@dataclass
class UserContext:
    username: str
    roles: list[str]
    token: str


def set_current_token(token: str):
    _current_token.set(token)


def get_current_token() -> str | None:
    return _current_token.get()


def set_current_user(user: UserContext):
    _current_user.set(user)


def current_user() -> UserContext | None:
    return _current_user.get()
