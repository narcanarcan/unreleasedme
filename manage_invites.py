from __future__ import annotations

import argparse

from server import db_connect, initialize_database, iso_now


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Unreleased.me invite codes.")
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="Add or reactivate an invite code.")
    add.add_argument("code")
    add.add_argument("--max-uses", type=int)

    commands.add_parser("list", help="List invite codes.")

    toggle = commands.add_parser("set-active", help="Enable or disable an invite code.")
    toggle.add_argument("code")
    toggle.add_argument("active", choices=("yes", "no"))

    args = parser.parse_args()
    initialize_database()
    with db_connect() as database:
        if args.command == "add":
            database.execute(
                """
                INSERT INTO invite_codes (code, active, max_uses, use_count, created_at)
                VALUES (?, 1, ?, 0, ?)
                ON CONFLICT(code) DO UPDATE SET active = 1, max_uses = excluded.max_uses
                """,
                (args.code.strip(), args.max_uses, iso_now()),
            )
            print(f"Invite code ready: {args.code.strip()}")
        elif args.command == "set-active":
            cursor = database.execute(
                "UPDATE invite_codes SET active = ? WHERE code = ? COLLATE NOCASE",
                (1 if args.active == "yes" else 0, args.code.strip()),
            )
            print("Invite code updated." if cursor.rowcount else "Invite code not found.")
        else:
            rows = database.execute(
                "SELECT code, active, use_count, max_uses, created_at FROM invite_codes ORDER BY created_at DESC"
            ).fetchall()
            for row in rows:
                limit = row["max_uses"] if row["max_uses"] is not None else "unlimited"
                print(f"{row['code']}: active={bool(row['active'])}, uses={row['use_count']}/{limit}")


if __name__ == "__main__":
    main()
