"""initial schema

Schéma initial (data-model.md) : comptes, actifs, journal des opérations en ajout seul avec ses
versions, prix, soldes déclarés, taux, imports et réglages. Les tables du journal reçoivent des
déclencheurs qui refusent tout UPDATE et DELETE (principe II).

Revision ID: 0001
Revises:
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from finance.db.types import DecimalText, UtcDateTime

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Copie figée de la liste du journal : une migration ne doit pas dépendre du code qui évolue.
APPEND_ONLY_TABLES = (
    "transaction",
    "transaction_version",
    "transfer_group",
    "price",
    "declared_balance",
    "rate",
    "import_batch",
)


def create_append_only_triggers() -> None:
    for table in APPEND_ONLY_TABLES:
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f'CREATE TRIGGER "{table}_no_{action.lower()}" BEFORE {action} ON "{table}" '
                f"BEGIN SELECT RAISE(ABORT, 'append-only: {table} refuse {action}'); END"
            )


def drop_append_only_triggers() -> None:
    for table in APPEND_ONLY_TABLES:
        for action in ("update", "delete"):
            op.execute(f'DROP TRIGGER IF EXISTS "{table}_no_{action}"')


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "account",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "PEE",
                "PEA",
                "CTO",
                "ASSURANCE_VIE",
                "LIVRET_A",
                name="account_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("institution", sa.String(length=200), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("opened_on", sa.Date(), nullable=False),
        sa.Column("closed_on", sa.Date(), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.CheckConstraint(
            "closed_on IS NULL OR closed_on >= opened_on",
            name=op.f("ck_account_closed_after_opened"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account")),
    )
    with op.batch_alter_table("account", schema=None) as batch_op:
        batch_op.create_index(
            "uq_account_open_name", ["name"], unique=True, sqlite_where=sa.text("closed_on IS NULL")
        )

    op.create_table(
        "import_mapping",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("delimiter", sa.String(length=1), nullable=False),
        sa.Column("encoding", sa.String(length=50), nullable=False),
        sa.Column("date_format", sa.String(length=50), nullable=False),
        sa.Column("decimal_separator", sa.String(length=1), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_mapping")),
        sa.UniqueConstraint("name", name=op.f("uq_import_mapping_name")),
    )
    op.create_table(
        "instrument",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "EQUITY",
                "ETF",
                "FUND",
                "FCPE",
                "SCPI",
                "EURO_FUND",
                "CASH",
                name="instrument_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("isin", sa.String(length=12), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("price_ticker", sa.String(length=50), nullable=True),
        sa.Column(
            "price_mode",
            sa.Enum(
                "AUTO",
                "MANUAL",
                name="price_mode",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "isin IS NULL OR length(isin) = 12", name=op.f("ck_instrument_isin_length")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_instrument")),
        sa.UniqueConstraint("isin", name=op.f("uq_instrument_isin")),
    )
    op.create_table(
        "rate",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "LIVRET_A",
                "FX",
                name="rate_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("base", sa.String(length=3), nullable=True),
        sa.Column("quote", sa.String(length=3), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("value", DecimalText(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "ECB",
                "MANUAL",
                name="rate_source",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("recorded_at", UtcDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate")),
    )
    with op.batch_alter_table("rate", schema=None) as batch_op:
        batch_op.create_index(
            "ix_rate_kind_pair_from", ["kind", "base", "quote", "effective_from"], unique=False
        )

    op.create_table(
        "setting",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_setting")),
    )
    op.create_table(
        "transfer_group",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transfer_group")),
    )
    op.create_table(
        "declared_balance",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("instrument_id", sa.String(length=36), nullable=False),
        sa.Column("balance_date", sa.Date(), nullable=False),
        sa.Column("amount", DecimalText(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("recorded_at", UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_declared_balance_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instrument.id"],
            name=op.f("fk_declared_balance_instrument_id_instrument"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_declared_balance")),
    )
    with op.batch_alter_table("declared_balance", schema=None) as batch_op:
        batch_op.create_index(
            "ix_declared_balance_account_date",
            ["account_id", "instrument_id", "balance_date"],
            unique=False,
        )

    op.create_table(
        "import_batch",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column("mapping_id", sa.String(length=36), nullable=True),
        sa.Column("rows_added", sa.Integer(), nullable=False),
        sa.Column("rows_skipped", sa.Integer(), nullable=False),
        sa.Column("rows_rejected", sa.Integer(), nullable=False),
        sa.Column("imported_at", UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_import_batch_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["mapping_id"],
            ["import_mapping.id"],
            name=op.f("fk_import_batch_mapping_id_import_mapping"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batch")),
    )
    with op.batch_alter_table("import_batch", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_import_batch_account_id"), ["account_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_import_batch_file_hash"), ["file_hash"], unique=False)

    op.create_table(
        "price",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("instrument_id", sa.String(length=36), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "MARKET",
                "NAV",
                "SUBSCRIPTION",
                "REDEMPTION",
                name="price_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("value", DecimalText(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "PROVIDER",
                "MANUAL",
                name="price_source",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("recorded_at", UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instrument.id"], name=op.f("fk_price_instrument_id_instrument")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price")),
    )
    with op.batch_alter_table("price", schema=None) as batch_op:
        batch_op.create_index(
            "ix_price_instrument_date", ["instrument_id", "price_date"], unique=False
        )

    op.create_table(
        "transaction",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_transaction_account_id_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transaction")),
    )
    with op.batch_alter_table("transaction", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_transaction_account_id"), ["account_id"], unique=False)

    op.create_table(
        "transaction_version",
        sa.Column("transaction_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("voided", sa.Boolean(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "DEPOSIT",
                "WITHDRAWAL",
                "BUY",
                "SELL",
                "DIVIDEND",
                "DISTRIBUTION",
                "INTEREST",
                "FEE",
                "EMPLOYER_MATCH",
                "TRANSFER_OUT",
                "TRANSFER_IN",
                name="transaction_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("instrument_id", sa.String(length=36), nullable=True),
        sa.Column("quantity", DecimalText(), nullable=True),
        sa.Column("unit_price", DecimalText(), nullable=True),
        sa.Column("fees", DecimalText(), nullable=False),
        sa.Column("cash_amount", DecimalText(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("unlock_date", sa.Date(), nullable=True),
        sa.Column("transfer_group_id", sa.String(length=36), nullable=True),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("line_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("import_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_transaction_version_version_positive")),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["import_batch.id"],
            name=op.f("fk_transaction_version_import_id_import_batch"),
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instrument.id"],
            name=op.f("fk_transaction_version_instrument_id_instrument"),
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transaction.id"],
            name=op.f("fk_transaction_version_transaction_id_transaction"),
        ),
        sa.ForeignKeyConstraint(
            ["transfer_group_id"],
            ["transfer_group.id"],
            name=op.f("fk_transaction_version_transfer_group_id_transfer_group"),
        ),
        sa.PrimaryKeyConstraint("transaction_id", "version", name=op.f("pk_transaction_version")),
    )
    with op.batch_alter_table("transaction_version", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_transaction_version_external_id"), ["external_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_transaction_version_instrument_id"), ["instrument_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_transaction_version_line_fingerprint"),
            ["line_fingerprint"],
            unique=False,
        )
        batch_op.create_index("ix_transaction_version_trade_date", ["trade_date"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_transaction_version_transfer_group_id"),
            ["transfer_group_id"],
            unique=False,
        )

    create_append_only_triggers()


def downgrade() -> None:
    """Downgrade schema."""
    drop_append_only_triggers()
    with op.batch_alter_table("transaction_version", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_transaction_version_transfer_group_id"))
        batch_op.drop_index("ix_transaction_version_trade_date")
        batch_op.drop_index(batch_op.f("ix_transaction_version_line_fingerprint"))
        batch_op.drop_index(batch_op.f("ix_transaction_version_instrument_id"))
        batch_op.drop_index(batch_op.f("ix_transaction_version_external_id"))

    op.drop_table("transaction_version")
    with op.batch_alter_table("transaction", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_transaction_account_id"))

    op.drop_table("transaction")
    with op.batch_alter_table("price", schema=None) as batch_op:
        batch_op.drop_index("ix_price_instrument_date")

    op.drop_table("price")
    with op.batch_alter_table("import_batch", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_import_batch_file_hash"))
        batch_op.drop_index(batch_op.f("ix_import_batch_account_id"))

    op.drop_table("import_batch")
    with op.batch_alter_table("declared_balance", schema=None) as batch_op:
        batch_op.drop_index("ix_declared_balance_account_date")

    op.drop_table("declared_balance")
    op.drop_table("transfer_group")
    op.drop_table("setting")
    with op.batch_alter_table("rate", schema=None) as batch_op:
        batch_op.drop_index("ix_rate_kind_pair_from")

    op.drop_table("rate")
    op.drop_table("instrument")
    op.drop_table("import_mapping")
    with op.batch_alter_table("account", schema=None) as batch_op:
        batch_op.drop_index("uq_account_open_name", sqlite_where=sa.text("closed_on IS NULL"))

    op.drop_table("account")
