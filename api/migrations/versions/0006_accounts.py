"""Accounts: Better Auth's tables plus our per-user tables with row-level security (spec 018).

Better Auth (web app, 1.7.x with the jwt plugin) uses these tables as-is; its own migration
tool is not used, so one Alembic history owns the whole schema. Column names are Better
Auth's camelCase.

Per-user tables FORCE row-level security. The API's /me routes `SET LOCAL ROLE ofs_app` (no
BYPASSRLS) and `set_config('app.user_id', ...)`, so even a superuser connection is held to the
policies (ACC-14).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)
USER_TABLES = ("user_preferences", "scan_history", "favorites")


def _user_fk(ondelete: str = "CASCADE") -> sa.ForeignKey:
    return sa.ForeignKey("user.id", ondelete=ondelete)


def upgrade() -> None:
    # --- Better Auth (ACC-1, ACC-2) ---
    op.create_table(
        "user",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("emailVerified", sa.Boolean, nullable=False),
        sa.Column("image", sa.Text),
        sa.Column("createdAt", TS, nullable=False),
        sa.Column("updatedAt", TS, nullable=False),
    )
    op.create_table(
        "session",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("expiresAt", TS, nullable=False),
        sa.Column("token", sa.Text, nullable=False, unique=True),
        sa.Column("createdAt", TS, nullable=False),
        sa.Column("updatedAt", TS, nullable=False),
        sa.Column("ipAddress", sa.Text),
        sa.Column("userAgent", sa.Text),
        sa.Column("userId", sa.Text, _user_fk(), nullable=False, index=True),
    )
    op.create_table(
        "account",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("accountId", sa.Text, nullable=False),
        sa.Column("providerId", sa.Text, nullable=False),
        sa.Column("userId", sa.Text, _user_fk(), nullable=False, index=True),
        sa.Column("accessToken", sa.Text),
        sa.Column("refreshToken", sa.Text),
        sa.Column("idToken", sa.Text),
        sa.Column("accessTokenExpiresAt", TS),
        sa.Column("refreshTokenExpiresAt", TS),
        sa.Column("scope", sa.Text),
        sa.Column("password", sa.Text),
        sa.Column("createdAt", TS, nullable=False),
        sa.Column("updatedAt", TS, nullable=False),
    )
    op.create_table(
        "verification",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("identifier", sa.Text, nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("expiresAt", TS, nullable=False),
        sa.Column("createdAt", TS, nullable=False),
        sa.Column("updatedAt", TS, nullable=False),
    )
    op.create_table(
        "jwks",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("publicKey", sa.Text, nullable=False),
        sa.Column("privateKey", sa.Text, nullable=False),
        sa.Column("createdAt", TS, nullable=False),
        sa.Column("expiresAt", TS),
        sa.Column("alg", sa.Text),
        sa.Column("crv", sa.Text),
    )

    # --- Our per-user tables (ACC-5, ACC-9, ACC-12) ---
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Text, _user_fk(), primary_key=True),
        sa.Column("allergens", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("diets", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("save_history", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "scan_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text, _user_fk(), nullable=False),
        sa.Column(
            "gtin", sa.Text, sa.ForeignKey("products.gtin", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("scanned_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("total", sa.SmallInteger),  # the score when scanned
        sa.Column("band", sa.Text),
    )
    op.create_index("scan_history_user_time", "scan_history", ["user_id", sa.text("id DESC")])
    op.create_table(
        "favorites",
        sa.Column("user_id", sa.Text, _user_fk(), primary_key=True),
        sa.Column(
            "gtin", sa.Text, sa.ForeignKey("products.gtin", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_foreign_key(  # ACC-13, ACC-18: contributions outlive the account, unlinked
        "contributions_user_fk", "contributions", "user", ["user_id"], ["id"], ondelete="SET NULL"
    )

    # --- Row-level security (ACC-14) ---
    op.execute("""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ofs_app') THEN
            CREATE ROLE ofs_app NOLOGIN NOBYPASSRLS;
          END IF;
        END $$
    """)
    op.execute("GRANT ofs_app TO CURRENT_USER")
    op.execute("GRANT USAGE ON SCHEMA public TO ofs_app")
    op.execute("GRANT SELECT ON products, scores TO ofs_app")
    op.execute("GRANT USAGE ON SEQUENCE scan_history_id_seq TO ofs_app")
    for table in USER_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO ofs_app")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY own_rows ON {table} "
            "USING (user_id = current_setting('app.user_id', true)) "
            "WITH CHECK (user_id = current_setting('app.user_id', true))"
        )


def downgrade() -> None:
    for table in USER_TABLES:
        op.execute(f"DROP POLICY IF EXISTS own_rows ON {table}")
    op.drop_constraint("contributions_user_fk", "contributions", type_="foreignkey")
    for table in ("favorites", "scan_history", "user_preferences", "jwks", "verification",
                  "account", "session", "user"):  # fmt: skip
        op.drop_table(table)
    op.execute("REVOKE ALL ON SCHEMA public FROM ofs_app")
    op.execute("REVOKE ALL ON products, scores FROM ofs_app")
