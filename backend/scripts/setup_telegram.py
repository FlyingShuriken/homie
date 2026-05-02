from __future__ import annotations

import argparse
import asyncio
import os
import sys
from getpass import getpass
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values, set_key
from telethon import TelegramClient
from telethon.errors import RPCError, SessionPasswordNeededError

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = BACKEND_DIR / ".env"
DEFAULT_SESSION_PATH = "./telegram_session.session"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Interactively authenticate the Telegram account used by Homie demo "
            "outreach and create the Telethon session file."
        )
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Path to the backend .env file to read/update.",
    )
    parser.add_argument("--api-id", type=int, help="Telegram app api_id.")
    parser.add_argument("--api-hash", help="Telegram app api_hash.")
    parser.add_argument("--phone", help="Telegram phone number with country code.")
    parser.add_argument(
        "--session-path",
        help=(
            "Telethon session path. Relative paths are resolved from the backend "
            "directory to match PM2/backend runtime behavior."
        ),
    )
    parser.add_argument(
        "--demo-target",
        help="Telegram handle or numeric ID that receives Homie demo messages.",
    )
    parser.add_argument(
        "--no-write-env",
        action="store_true",
        help="Create the session file but do not update the backend .env file.",
    )
    parser.add_argument(
        "--test-message",
        action="store_true",
        help="Send a short test message to the demo target after authentication.",
    )
    return parser.parse_args()


def env_value(
    name: str, env_values: Mapping[str, str | None], default: str = ""
) -> str:
    value = os.environ.get(name)
    if value is None:
        value = env_values.get(name)
    return value or default


def prompt_text(
    label: str, current: str = "", *, required: bool = True, secret: bool = False
) -> str:
    display_default = (
        " [loaded]" if current and secret else f" [{current}]" if current else ""
    )
    while True:
        raw = getpass(f"{label}{display_default}: ") if secret else input(
            f"{label}{display_default}: "
        )
        value = raw.strip()
        if value:
            return value
        if current:
            return current
        if not required:
            return ""
        print(f"{label} is required.")


def prompt_api_id(current: str = "") -> int:
    current = "" if current in {"", "0"} else current
    while True:
        value = prompt_text("Telegram API ID", current)
        try:
            api_id = int(value)
        except ValueError:
            print("Telegram API ID must be a number.")
            continue
        if api_id > 0:
            return api_id
        print("Telegram API ID must be greater than zero.")


def resolve_env_file(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def resolve_session_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = BACKEND_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def write_env_file(
    env_file: Path,
    *,
    api_id: int,
    api_hash: str,
    phone: str,
    session_path: str,
    demo_target: str,
) -> None:
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.touch(exist_ok=True)
    values = {
        "TELEGRAM_API_ID": str(api_id),
        "TELEGRAM_API_HASH": api_hash,
        "TELEGRAM_PHONE": phone,
        "TELEGRAM_SESSION_PATH": session_path,
        "TELEGRAM_DEMO_TARGET": demo_target,
    }
    for key, value in values.items():
        set_key(str(env_file), key, value, quote_mode="never")


async def authenticate(args: argparse.Namespace) -> None:
    env_file = resolve_env_file(args.env_file)
    env_values = dotenv_values(env_file) if env_file.exists() else {}

    api_id = (
        args.api_id
        if args.api_id is not None
        else prompt_api_id(env_value("TELEGRAM_API_ID", env_values))
    )
    if api_id <= 0:
        raise ValueError("Telegram API ID must be greater than zero.")
    api_hash = args.api_hash or prompt_text(
        "Telegram API hash",
        env_value("TELEGRAM_API_HASH", env_values),
        secret=True,
    )
    phone = args.phone or prompt_text(
        "Telegram phone number",
        env_value("TELEGRAM_PHONE", env_values),
    )
    session_path_value = args.session_path or prompt_text(
        "Telegram session path",
        env_value("TELEGRAM_SESSION_PATH", env_values, DEFAULT_SESSION_PATH),
    )
    demo_target = args.demo_target or prompt_text(
        "Telegram demo target",
        env_value("TELEGRAM_DEMO_TARGET", env_values),
    )
    session_path = resolve_session_path(session_path_value)

    print(f"Using session file: {session_path}")
    client = TelegramClient(str(session_path), api_id, api_hash)

    try:
        await client.connect()
        if await client.is_user_authorized():
            print("Telegram session is already authenticated.")
        else:
            sent = await client.send_code_request(phone)
            print(f"Telegram sent a login code to {phone}.")
            code = prompt_text("Login code").replace(" ", "")
            try:
                await client.sign_in(
                    phone=phone,
                    code=code,
                    phone_code_hash=sent.phone_code_hash,
                )
            except SessionPasswordNeededError:
                password = getpass("Two-step verification password: ")
                await client.sign_in(password=password)

        me = await client.get_me()
        label = (
            getattr(me, "username", None)
            or getattr(me, "first_name", None)
            or phone
        )
        print(f"Authenticated Telegram account: {label}")

        if args.test_message:
            await client.send_message(
                demo_target, "Homie Telegram setup test message."
            )
            print(f"Sent test message to {demo_target}.")
    finally:
        await client.disconnect()

    if args.no_write_env:
        print("Skipped .env update because --no-write-env was set.")
        return

    write_env_file(
        env_file,
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        session_path=session_path_value,
        demo_target=demo_target,
    )
    print(f"Updated {env_file}")
    print("Restart the backend process so it picks up the Telegram settings.")


def main() -> int:
    args = parse_args()
    try:
        asyncio.run(authenticate(args))
    except KeyboardInterrupt:
        print("\nTelegram setup cancelled.", file=sys.stderr)
        return 130
    except ValueError as exc:
        print(f"Telegram setup failed: {exc}", file=sys.stderr)
        return 2
    except RPCError as exc:
        print(f"Telegram setup failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
