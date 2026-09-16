import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.models import ConversationSession
from app.db.session import SessionLocal


def test_database_rejects_conversation_for_missing_elder(client):
    with SessionLocal() as db:
        if db.bind.dialect.name == "sqlite":
            assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
        db.add(ConversationSession(elder_id="nonexistent-elder", save_messages=True, allow_analysis=True))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        if db.bind.dialect.name == "sqlite":
            assert db.execute(text("PRAGMA foreign_key_check")).all() == []
