import logging
import webbrowser
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging_config import setup_logging
from app.core.models import (
    Action, ActionStatus, ActionType, Message, MessageStatus,
)
from app.pipeline.execution.handlers import email_handler


logger = logging.getLogger(__name__)


SEPARATOR = "─" * 72
PLACEHOLDER_MARKER = "[INSERT"
DRAFT_URL_TEMPLATE = "https://mail.google.com/mail/u/0/#drafts"


def _render_action(action: Action, message: Optional[Message]) -> None:
    payload = action.payload or {}
    body = payload["message"]["reply_body"]
    has_placeholder = PLACEHOLDER_MARKER in body

    print(SEPARATOR)
    print(f"Action #{action.id}     "
          f"Created: {action.created_at:%Y-%m-%d %H:%M}     "
          f"Status: {action.status.value}")
    print()
    if message:
        print(f"---- Original email ----")
        print(f"From: {message.from_address}\n"
              f"Subject: {message.subject}\n"
              f"Date: {message.received_date}")
    print(SEPARATOR)
    print(f"To: {payload["message"]["to_address"]}")
    print(f"Subject: {payload["message"]["subject"]}")
    attachments = payload["message"]["attachments_to_include"] or []
    if attachments:
        print(f"Attachments: {', '.join(attachments)}")
    print()
    print(body)
    print()
    if has_placeholder:
        print(">>> WARNING: draft contains unfilled placeholders. "
              "Edit in Gmail before approving. <<<")
    print(SEPARATOR)
    print(f"Gmail draft: {DRAFT_URL_TEMPLATE}")
    print("[a]pprove  [r]eject  [s]kip  [e]dit in Gmail  [q]uit")


def _prompt() -> str:
    while True:
        choice = input("> ").strip().lower()
        if choice in {"a", "r", "s", "e", "q"}:
            return choice
        print("Pick one of: a / r / s / e / q")


def _approve(action: Action, db: Session) -> None:
    action.status = ActionStatus.APPROVED
    print(f"Approved action #{action.id}. Will be sent on next executor run.\n")


def _reject(action: Action, db: Session) -> None:
    reason = input("Reason (optional): ").strip()
    action.status = ActionStatus.REJECTED
    action.error = f"Rejected: {reason}" if reason else "Rejected"

    # Mark the underlying message as actioned — the user explicitly closed this out
    message = db.get(Message, action.message_id)
    if message is not None:
        message.status = MessageStatus.ACTIONED

    # Clean up the orphan Gmail draft
    draft_id = (action.payload or {}).get("draft_id")
    if draft_id:
        email_handler.delete_draft(draft_id)

    print(f"Rejected action #{action.id}. Draft deleted.\n")


def run() -> int | None:
    approved = 0
    skipped = 0
    rejected = 0
    with SessionLocal() as db:
        awaiting_actions = db.scalars(
            select(Action)
            .where(Action.action_type == ActionType.SEND_REPLY)
            .where(Action.status == ActionStatus.AWAITING_APPROVAL)
            .order_by(Action.created_at)
        ).all()

        if not awaiting_actions:
            print("Nothing awaiting approval.")
            return

        print(f"{len(awaiting_actions)} action(s) awaiting approval.\n")

        for action in awaiting_actions:
            message = db.get(Message, action.message_id)
            _render_action(action, message)

            while True:
                choice = _prompt()
                if choice == "a":
                    _approve(action, db)
                    approved += 1
                    break
                if choice == "r":
                    _reject(action, db)
                    rejected += 1
                    break
                if choice == "s":
                    print(f"Skipped action #{action.id}.\n")
                    skipped += 1
                    break
                if choice == "e":
                    webbrowser.open(DRAFT_URL_TEMPLATE)
                    print("Opened Gmail drafts. Edit, then return here.\n")
                    # Loop again — don't break, let user re-decide
                    continue
                if choice == "q":
                    db.commit()
                    print("Quitting. Remaining items stay in queue.")
                    return

            db.commit()  # commit after each decision

        print(
            "Review complete. Summary: approved=%d rejected=%d skipped=%d", 
            approved, rejected, skipped
        )

    return approved


def main() -> None:
    setup_logging()
    load_dotenv()
    approved_count = run()
    if approved_count and approved_count > 0:
        print(f"\nSending {approved_count} approved email(s)...")
        from app.pipeline.execution import approve
        approve.run()


if __name__ == "__main__":
    main()