from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    token_version: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    address_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    default_ward_id: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey("wards.id", ondelete="RESTRICT", name="fk_users_default_ward"),
        nullable=True,
        index=True,
    )
