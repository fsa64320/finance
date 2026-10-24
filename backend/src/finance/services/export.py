"""Export complet et restauration des données (FR-030, SC-009, contracts/export-format.md).

L'export est un fichier JSON versionné, non chiffré. La restauration n'est acceptée que sur une
instance vide ; le fichier est validé en entier avant la moindre écriture, puis écrit en une seule
transaction. Les identifiants sont conservés, donc les relations (virements, imports, versions)
restent intactes.
"""

import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from finance.db import models
from finance.db.types import canonical_decimal_text
from finance.domain.enums import (
    AccountType,
    InstrumentKind,
    PriceKind,
    PriceMode,
    PriceSource,
    RateKind,
    RateSource,
    TransactionType,
)
from finance.services import settings as settings_service
from finance.services.errors import ConflictError, FieldError, ValidationFailed

FORMAT_VERSION = 1
MAX_PROBLEMS = 50
_CURRENCY = re.compile(r"[A-Z]{3}")

SECTIONS = (
    "accounts",
    "instruments",
    "transactions",
    "prices",
    "declared_balances",
    "rates",
    "imports",
    "import_mappings",
)


# ---------------------------------------------------------------------------------- export


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _dec(value: Decimal | None) -> str | None:
    return None if value is None else canonical_decimal_text(value)


def _day(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def export_data(session: Session) -> dict[str, Any]:
    """Toutes les données, versions de chaque opération comprises ; aucun secret."""
    now = datetime.now(UTC)
    current = settings_service.get_settings(session)

    accounts = [
        {
            "id": a.id,
            "type": a.type.value,
            "name": a.name,
            "institution": a.institution,
            "currency": a.currency,
            "opened_on": _day(a.opened_on),
            "closed_on": _day(a.closed_on),
            "settings": a.settings,
        }
        for a in session.scalars(sa.select(models.Account).order_by(models.Account.id))
    ]
    instruments = [
        {
            "id": i.id,
            "kind": i.kind.value,
            "name": i.name,
            "isin": i.isin,
            "currency": i.currency,
            "price_ticker": i.price_ticker,
            "price_mode": i.price_mode.value,
        }
        for i in session.scalars(sa.select(models.Instrument).order_by(models.Instrument.id))
    ]

    versions: dict[str, list[models.TransactionVersion]] = defaultdict(list)
    for row in session.scalars(
        sa.select(models.TransactionVersion).order_by(
            models.TransactionVersion.transaction_id, models.TransactionVersion.version
        )
    ).unique():
        versions[row.transaction_id].append(row)
    transactions = [
        {
            "id": t.id,
            "account_id": t.account_id,
            "created_at": _stamp(t.created_at),
            "versions": [
                {
                    "version": v.version,
                    "voided": v.voided,
                    "type": v.type.value,
                    "trade_date": _day(v.trade_date),
                    "instrument_id": v.instrument_id,
                    "quantity": _dec(v.quantity),
                    "unit_price": _dec(v.unit_price),
                    "fees": _dec(v.fees),
                    "cash_amount": _dec(v.cash_amount),
                    "currency": v.currency,
                    "unlock_date": _day(v.unlock_date),
                    "transfer_group_id": v.transfer_group_id,
                    "label": v.label,
                    "external_id": v.external_id,
                    "line_fingerprint": v.line_fingerprint,
                    "import_id": v.import_id,
                    "created_at": _stamp(v.created_at),
                }
                for v in versions.get(t.id, [])
            ],
        }
        for t in session.scalars(sa.select(models.Transaction).order_by(models.Transaction.id))
    ]

    prices = [
        {
            "instrument_id": p.instrument_id,
            "price_date": _day(p.price_date),
            "kind": p.kind.value,
            "value": _dec(p.value),
            "currency": p.currency,
            "source": p.source.value,
            "recorded_at": _stamp(p.recorded_at),
        }
        for p in session.scalars(
            sa.select(models.Price).order_by(
                models.Price.instrument_id,
                models.Price.price_date,
                models.Price.kind,
                models.Price.recorded_at,
            )
        )
    ]
    declared = [
        {
            "account_id": b.account_id,
            "instrument_id": b.instrument_id,
            "balance_date": _day(b.balance_date),
            "amount": _dec(b.amount),
            "currency": b.currency,
            "recorded_at": _stamp(b.recorded_at),
        }
        for b in session.scalars(
            sa.select(models.DeclaredBalance).order_by(
                models.DeclaredBalance.account_id,
                models.DeclaredBalance.instrument_id,
                models.DeclaredBalance.balance_date,
                models.DeclaredBalance.recorded_at,
            )
        )
    ]
    # Un taux par date d'effet : la saisie la plus récente. Les corrections remplacées n'ont plus
    # d'effet sur aucune valeur.
    winners: dict[tuple[Any, ...], models.Rate] = {}
    for r in session.scalars(sa.select(models.Rate).order_by(models.Rate.recorded_at)):
        winners[(r.kind, r.base, r.quote, r.effective_from)] = r
    rates = [
        {
            "kind": r.kind.value,
            "base": r.base,
            "quote": r.quote,
            "effective_from": _day(r.effective_from),
            "value": _dec(r.value),
            "source": r.source.value,
        }
        for r in sorted(
            winners.values(),
            key=lambda r: (r.kind.value, r.base or "", r.quote or "", r.effective_from),
        )
    ]
    imports = [
        {
            "id": b.id,
            "account_id": b.account_id,
            "file_name": b.file_name,
            "file_hash": b.file_hash,
            "mapping_id": b.mapping_id,
            "rows_added": b.rows_added,
            "rows_skipped": b.rows_skipped,
            "rows_rejected": b.rows_rejected,
            "imported_at": _stamp(b.imported_at),
        }
        for b in session.scalars(sa.select(models.ImportBatch).order_by(models.ImportBatch.id))
    ]
    mappings = [
        {
            "id": m.id,
            "name": m.name,
            "delimiter": m.delimiter,
            "encoding": m.encoding,
            "date_format": m.date_format,
            "decimal_separator": m.decimal_separator,
            "columns": m.columns,
        }
        for m in session.scalars(sa.select(models.ImportMapping).order_by(models.ImportMapping.id))
    ]

    settings_service.record_export(session, now)
    return {
        "format_version": FORMAT_VERSION,
        "exported_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reference_currency": current.reference_currency,
        "settings": {
            "auto_fetch_prices": current.auto_fetch_prices,
            "export_reminder_days": current.export_reminder_days,
        },
        "accounts": accounts,
        "instruments": instruments,
        "transactions": transactions,
        "prices": prices,
        "declared_balances": declared,
        "rates": rates,
        "imports": imports,
        "import_mappings": mappings,
    }


# ------------------------------------------------------------------------------ validation


@dataclass
class _Checker:
    problems: list[FieldError] = field(default_factory=list)

    def fail(self, path: str, message: str) -> None:
        if len(self.problems) < MAX_PROBLEMS:
            self.problems.append(FieldError(path, message))

    def text(
        self, row: dict[str, Any], key: str, path: str, *, optional: bool = False, limit: int = 500
    ) -> str | None:
        value = row.get(key)
        if value is None and optional:
            return None
        if not isinstance(value, str) or (not value.strip() and not optional and key != "label"):
            self.fail(f"{path}.{key}", "Texte attendu.")
            return None
        if len(value) > limit:
            self.fail(f"{path}.{key}", f"Texte trop long ({limit} caractères au plus).")
            return None
        return value

    def identifier(
        self, row: dict[str, Any], key: str, path: str, *, optional: bool = False
    ) -> str | None:
        value = row.get(key)
        if value is None and optional:
            return None
        if not isinstance(value, str) or not value or len(value) > 36:
            self.fail(f"{path}.{key}", "Identifiant attendu (36 caractères au plus).")
            return None
        return value

    def currency(self, row: dict[str, Any], key: str, path: str) -> str | None:
        value = row.get(key)
        if not isinstance(value, str) or not _CURRENCY.fullmatch(value):
            self.fail(f"{path}.{key}", "Devise attendue : trois lettres majuscules.")
            return None
        return value

    def decimal(
        self, row: dict[str, Any], key: str, path: str, *, optional: bool = False
    ) -> Decimal | None:
        value = row.get(key)
        if value is None:
            if not optional:
                self.fail(f"{path}.{key}", "Nombre décimal attendu, sous forme de texte.")
            return None
        if not isinstance(value, str):
            self.fail(f"{path}.{key}", 'Un montant est un texte décimal, par exemple "90.2".')
            return None
        try:
            number = Decimal(value)
        except InvalidOperation:
            number = None
        if number is None or not number.is_finite() or "e" in value.lower():
            self.fail(f"{path}.{key}", f"Nombre décimal invalide : « {value[:40]} ».")
            return None
        return number

    def day(
        self, row: dict[str, Any], key: str, path: str, *, optional: bool = False
    ) -> date | None:
        value = row.get(key)
        if value is None and optional:
            return None
        try:
            if not isinstance(value, str):
                raise ValueError
            return date.fromisoformat(value)
        except ValueError:
            self.fail(f"{path}.{key}", "Date attendue au format AAAA-MM-JJ.")
            return None

    def stamp(self, row: dict[str, Any], key: str, path: str) -> datetime | None:
        value = row.get(key)
        try:
            if not isinstance(value, str):
                raise ValueError
            parsed = datetime.fromisoformat(value)
        except ValueError:
            self.fail(f"{path}.{key}", "Horodatage attendu, par exemple 2026-01-05T10:00:00Z.")
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    def enum[E](
        self, row: dict[str, Any], key: str, path: str, kind: Callable[[str], E]
    ) -> E | None:
        try:
            return kind(row.get(key))  # type: ignore[arg-type]
        except ValueError:
            self.fail(f"{path}.{key}", f"Valeur inconnue : « {str(row.get(key))[:40]} ».")
            return None

    def integer(self, row: dict[str, Any], key: str, path: str, minimum: int = 0) -> int | None:
        value = row.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            self.fail(f"{path}.{key}", f"Entier attendu, {minimum} au minimum.")
            return None
        return value


def _rows(payload: dict[str, Any], section: str, checker: _Checker) -> list[dict[str, Any]]:
    value = payload.get(section)
    if not isinstance(value, list):
        checker.fail(section, "Liste attendue.")
        return []
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(value):
        if isinstance(row, dict):
            rows.append(row)
        else:
            checker.fail(f"{section}[{index}]", "Objet attendu.")
            rows.append({})
    return rows


@dataclass
class _Parsed:
    objects: list[Any] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    reference_currency: str = "EUR"
    rates: list[dict[str, Any]] = field(default_factory=list)


def _check_version(payload: dict[str, Any], checker: _Checker) -> bool:
    version = payload.get("format_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        checker.fail(
            "format_version", "Version du format absente ou illisible : ce n'est pas un export."
        )
        return False
    if version > FORMAT_VERSION:
        checker.fail(
            "format_version",
            f"Version {version} du format inconnue : cet export est plus récent que cette "
            f"application (version {FORMAT_VERSION}). Mettez l'application à jour avant de "
            "restaurer.",
        )
        return False
    return True


def _parse(payload: dict[str, Any], checker: _Checker) -> _Parsed:
    out = _Parsed()
    reference = payload.get("reference_currency", "EUR")
    if isinstance(reference, str) and _CURRENCY.fullmatch(reference):
        out.reference_currency = reference
    else:
        checker.fail("reference_currency", "Devise attendue : trois lettres majuscules.")
    given = payload.get("settings", {})
    if not isinstance(given, dict):
        checker.fail("settings", "Objet attendu.")
        given = {}
    if "auto_fetch_prices" in given and not isinstance(given["auto_fetch_prices"], bool):
        checker.fail("settings.auto_fetch_prices", "Vrai ou faux attendu.")
    elif "auto_fetch_prices" in given:
        out.settings["auto_fetch_prices"] = given["auto_fetch_prices"]
    if "export_reminder_days" in given:
        days = checker.integer(given, "export_reminder_days", "settings")
        if days is not None:
            out.settings["export_reminder_days"] = days

    account_ids: set[str] = set()
    open_names: set[str] = set()
    for i, row in enumerate(_rows(payload, "accounts", checker)):
        path = f"accounts[{i}]"
        ident = checker.identifier(row, "id", path)
        if ident in account_ids:
            checker.fail(f"{path}.id", "Identifiant en double.")
        if ident:
            account_ids.add(ident)
        kind = checker.enum(row, "type", path, AccountType)
        name = checker.text(row, "name", path, limit=200)
        currency = checker.currency(row, "currency", path)
        opened = checker.day(row, "opened_on", path)
        closed = checker.day(row, "closed_on", path, optional=True)
        institution = checker.text(row, "institution", path, optional=True, limit=200)
        settings = row.get("settings", {})
        if not isinstance(settings, dict):
            checker.fail(f"{path}.settings", "Objet attendu.")
            settings = {}
        if opened and closed and closed < opened:
            checker.fail(f"{path}.closed_on", "La clôture précède l'ouverture.")
        if name and closed is None:
            if name in open_names:
                checker.fail(f"{path}.name", "Deux comptes ouverts portent le même nom.")
            open_names.add(name)
        if ident and kind and name and currency and opened:
            out.objects.append(
                models.Account(
                    id=ident,
                    type=kind,
                    name=name,
                    institution=institution,
                    currency=currency,
                    opened_on=opened,
                    closed_on=closed,
                    settings=settings,
                )
            )

    instrument_ids: set[str] = set()
    isins: set[str] = set()
    for i, row in enumerate(_rows(payload, "instruments", checker)):
        path = f"instruments[{i}]"
        ident = checker.identifier(row, "id", path)
        if ident in instrument_ids:
            checker.fail(f"{path}.id", "Identifiant en double.")
        if ident:
            instrument_ids.add(ident)
        kind_i = checker.enum(row, "kind", path, InstrumentKind)
        name = checker.text(row, "name", path, limit=200)
        isin = checker.text(row, "isin", path, optional=True, limit=12)
        if isin is not None:
            if isin in isins:
                checker.fail(f"{path}.isin", "Deux actifs portent le même ISIN.")
            isins.add(isin)
        currency = checker.currency(row, "currency", path)
        ticker = checker.text(row, "price_ticker", path, optional=True, limit=50)
        mode = checker.enum(row, "price_mode", path, PriceMode)
        if ident and kind_i and name and currency and mode:
            out.objects.append(
                models.Instrument(
                    id=ident,
                    kind=kind_i,
                    name=name,
                    isin=isin,
                    currency=currency,
                    price_ticker=ticker,
                    price_mode=mode,
                )
            )

    mapping_ids: set[str] = set()
    for i, row in enumerate(_rows(payload, "import_mappings", checker)):
        path = f"import_mappings[{i}]"
        ident = checker.identifier(row, "id", path)
        if ident in mapping_ids:
            checker.fail(f"{path}.id", "Identifiant en double.")
        if ident:
            mapping_ids.add(ident)
        name = checker.text(row, "name", path, limit=200)
        delimiter = checker.text(row, "delimiter", path, limit=1)
        encoding = checker.text(row, "encoding", path, limit=50)
        date_format = checker.text(row, "date_format", path, limit=50)
        decimal_separator = checker.text(row, "decimal_separator", path, limit=1)
        columns = row.get("columns")
        if not isinstance(columns, dict):
            checker.fail(f"{path}.columns", "Objet attendu.")
        if (
            ident
            and name
            and delimiter
            and encoding
            and date_format
            and decimal_separator
            and isinstance(columns, dict)
        ):
            out.objects.append(
                models.ImportMapping(
                    id=ident,
                    name=name,
                    delimiter=delimiter,
                    encoding=encoding,
                    date_format=date_format,
                    decimal_separator=decimal_separator,
                    columns=columns,
                )
            )

    import_ids: set[str] = set()
    for i, row in enumerate(_rows(payload, "imports", checker)):
        path = f"imports[{i}]"
        ident = checker.identifier(row, "id", path)
        if ident in import_ids:
            checker.fail(f"{path}.id", "Identifiant en double.")
        if ident:
            import_ids.add(ident)
        account_id = checker.identifier(row, "account_id", path)
        if account_id and account_id not in account_ids:
            checker.fail(f"{path}.account_id", "Compte inconnu.")
        mapping_id = checker.identifier(row, "mapping_id", path, optional=True)
        if mapping_id and mapping_id not in mapping_ids:
            checker.fail(f"{path}.mapping_id", "Paramétrage d'import inconnu.")
        file_name = checker.text(row, "file_name", path, limit=500)
        file_hash = checker.text(row, "file_hash", path, limit=128)
        added = checker.integer(row, "rows_added", path)
        skipped = checker.integer(row, "rows_skipped", path)
        rejected = checker.integer(row, "rows_rejected", path)
        at = checker.stamp(row, "imported_at", path)
        if None not in (ident, account_id, file_name, file_hash, added, skipped, rejected, at):
            out.objects.append(
                models.ImportBatch(
                    id=ident,
                    account_id=account_id,
                    file_name=file_name,
                    file_hash=file_hash,
                    mapping_id=mapping_id,
                    rows_added=added,
                    rows_skipped=skipped,
                    rows_rejected=rejected,
                    imported_at=at,
                )
            )

    transaction_ids: set[str] = set()
    groups: dict[str, datetime] = {}
    transactions: list[Any] = []
    versions: list[Any] = []
    for i, row in enumerate(_rows(payload, "transactions", checker)):
        path = f"transactions[{i}]"
        ident = checker.identifier(row, "id", path)
        if ident in transaction_ids:
            checker.fail(f"{path}.id", "Identifiant en double.")
        if ident:
            transaction_ids.add(ident)
        account_id = checker.identifier(row, "account_id", path)
        if account_id and account_id not in account_ids:
            checker.fail(f"{path}.account_id", "Compte inconnu.")
        created = checker.stamp(row, "created_at", path)
        raw_versions = row.get("versions")
        if not isinstance(raw_versions, list) or not raw_versions:
            checker.fail(f"{path}.versions", "Au moins une version attendue.")
            continue
        if ident and account_id and created:
            transactions.append(
                models.Transaction(id=ident, account_id=account_id, created_at=created)
            )
        for j, version in enumerate(raw_versions):
            vpath = f"{path}.versions[{j}]"
            if not isinstance(version, dict):
                checker.fail(vpath, "Objet attendu.")
                continue
            number = checker.integer(version, "version", vpath, minimum=1)
            if number is not None and number != j + 1:
                checker.fail(f"{vpath}.version", "Les versions se suivent : 1, 2, 3…")
            voided = version.get("voided")
            if not isinstance(voided, bool):
                checker.fail(f"{vpath}.voided", "Vrai ou faux attendu.")
            kind_t = checker.enum(version, "type", vpath, TransactionType)
            trade_date = checker.day(version, "trade_date", vpath)
            instrument_id = checker.identifier(version, "instrument_id", vpath, optional=True)
            if instrument_id and instrument_id not in instrument_ids:
                checker.fail(f"{vpath}.instrument_id", "Actif inconnu.")
            quantity = checker.decimal(version, "quantity", vpath, optional=True)
            unit_price = checker.decimal(version, "unit_price", vpath, optional=True)
            fees = checker.decimal(version, "fees", vpath)
            cash = checker.decimal(version, "cash_amount", vpath)
            currency = checker.currency(version, "currency", vpath)
            unlock = checker.day(version, "unlock_date", vpath, optional=True)
            group = checker.identifier(version, "transfer_group_id", vpath, optional=True)
            label = version.get("label")
            if label is not None and not isinstance(label, str):
                checker.fail(f"{vpath}.label", "Texte attendu.")
                label = None
            external_id = checker.text(version, "external_id", vpath, optional=True, limit=200)
            fingerprint = checker.text(version, "line_fingerprint", vpath, optional=True, limit=128)
            import_id = checker.identifier(version, "import_id", vpath, optional=True)
            if import_id and import_id not in import_ids:
                checker.fail(f"{vpath}.import_id", "Import inconnu.")
            vcreated = checker.stamp(version, "created_at", vpath)
            if group and vcreated:
                groups[group] = min(groups.get(group, vcreated), vcreated)
            if (
                ident
                and number
                and isinstance(voided, bool)
                and kind_t
                and trade_date
                and fees is not None
                and cash is not None
                and currency
                and vcreated
            ):
                versions.append(
                    models.TransactionVersion(
                        transaction_id=ident,
                        version=number,
                        voided=voided,
                        type=kind_t,
                        trade_date=trade_date,
                        instrument_id=instrument_id,
                        quantity=quantity,
                        unit_price=unit_price,
                        fees=fees,
                        cash_amount=cash,
                        currency=currency,
                        unlock_date=unlock,
                        transfer_group_id=group,
                        label=label or None,
                        external_id=external_id,
                        line_fingerprint=fingerprint,
                        import_id=import_id,
                        created_at=vcreated,
                    )
                )

    for i, row in enumerate(_rows(payload, "prices", checker)):
        path = f"prices[{i}]"
        instrument_id = checker.identifier(row, "instrument_id", path)
        if instrument_id and instrument_id not in instrument_ids:
            checker.fail(f"{path}.instrument_id", "Actif inconnu.")
        on = checker.day(row, "price_date", path)
        kind_p = checker.enum(row, "kind", path, PriceKind)
        value = checker.decimal(row, "value", path)
        if value is not None and value <= 0:
            checker.fail(f"{path}.value", "Le prix doit être strictement positif.")
            value = None
        currency = checker.currency(row, "currency", path)
        source = checker.enum(row, "source", path, PriceSource)
        recorded = checker.stamp(row, "recorded_at", path)
        if (
            instrument_id
            and on
            and kind_p
            and value is not None
            and currency
            and source
            and recorded
        ):
            out.objects.append(
                models.Price(
                    instrument_id=instrument_id,
                    price_date=on,
                    kind=kind_p,
                    value=value,
                    currency=currency,
                    source=source,
                    recorded_at=recorded,
                )
            )

    for i, row in enumerate(_rows(payload, "declared_balances", checker)):
        path = f"declared_balances[{i}]"
        account_id = checker.identifier(row, "account_id", path)
        if account_id and account_id not in account_ids:
            checker.fail(f"{path}.account_id", "Compte inconnu.")
        instrument_id = checker.identifier(row, "instrument_id", path)
        if instrument_id and instrument_id not in instrument_ids:
            checker.fail(f"{path}.instrument_id", "Actif inconnu.")
        on = checker.day(row, "balance_date", path)
        amount = checker.decimal(row, "amount", path)
        currency = checker.currency(row, "currency", path)
        recorded = checker.stamp(row, "recorded_at", path)
        if account_id and instrument_id and on and amount is not None and currency and recorded:
            out.objects.append(
                models.DeclaredBalance(
                    account_id=account_id,
                    instrument_id=instrument_id,
                    balance_date=on,
                    amount=amount,
                    currency=currency,
                    recorded_at=recorded,
                )
            )

    for i, row in enumerate(_rows(payload, "rates", checker)):
        path = f"rates[{i}]"
        kind_r = checker.enum(row, "kind", path, RateKind)
        base = checker.text(row, "base", path, optional=True, limit=3)
        quote = checker.text(row, "quote", path, optional=True, limit=3)
        on = checker.day(row, "effective_from", path)
        value = checker.decimal(row, "value", path)
        source_r = checker.enum(row, "source", path, RateSource)
        if kind_r is RateKind.FX and not (base and quote):
            checker.fail(
                f"{path}.quote", "Un taux de change a une devise de base et une devise cotée."
            )
        if kind_r and on and value is not None and source_r:
            out.rates.append(
                {
                    "kind": kind_r,
                    "base": base,
                    "quote": quote,
                    "effective_from": on,
                    "value": value,
                    "source": source_r,
                }
            )

    out.objects.extend(models.TransferGroup(id=g, created_at=c) for g, c in groups.items())
    out.objects.extend(transactions)
    out.objects.extend(versions)
    return out


# ------------------------------------------------------------------------------- restore

# Ordre d'insertion qui respecte les clés étrangères.
_ORDER = (
    models.Account,
    models.Instrument,
    models.ImportMapping,
    models.ImportBatch,
    models.TransferGroup,
    models.Transaction,
    models.TransactionVersion,
    models.Price,
    models.DeclaredBalance,
)


def restore_data(session: Session, payload: dict[str, Any]) -> None:
    """Restaure `payload` dans une instance vide ; tout ou rien."""
    empty = (
        session.scalar(sa.select(sa.func.count()).select_from(models.Account)) == 0
        and session.scalar(sa.select(sa.func.count()).select_from(models.Instrument)) == 0
    )
    if not empty:
        raise ConflictError(
            "La restauration n'est possible que sur une instance vide : cette instance contient "
            "déjà des comptes ou des actifs."
        )
    checker = _Checker()
    if _check_version(payload, checker):
        for section in SECTIONS:
            if section not in payload:
                checker.fail(section, "Section absente : ce n'est pas un export complet.")
    if checker.problems:
        raise ValidationFailed(checker.problems)
    parsed = _parse(payload, checker)
    if checker.problems:
        raise ValidationFailed(checker.problems)

    for model in _ORDER:
        session.add_all([item for item in parsed.objects if type(item) is model])
        session.flush()

    # Les taux livrés avec l'application existent déjà : seuls ceux qui diffèrent sont ajoutés,
    # chacun après les précédents pour que la saisie la plus récente reste celle qui fait foi.
    now = datetime.now(UTC)
    for offset, rate in enumerate(parsed.rates):
        latest = session.scalars(
            sa.select(models.Rate)
            .where(
                models.Rate.kind == rate["kind"],
                models.Rate.base.is_(None)
                if rate["base"] is None
                else models.Rate.base == rate["base"],
                models.Rate.quote.is_(None)
                if rate["quote"] is None
                else models.Rate.quote == rate["quote"],
                models.Rate.effective_from == rate["effective_from"],
            )
            .order_by(models.Rate.recorded_at.desc())
            .limit(1)
        ).first()
        if latest is not None and latest.value == rate["value"]:
            continue
        session.add(models.Rate(recorded_at=now + timedelta(microseconds=offset), **rate))
        session.flush()

    settings_service.update_settings(
        session,
        reference_currency=parsed.reference_currency,
        auto_fetch_prices=parsed.settings.get("auto_fetch_prices"),
        export_reminder_days=parsed.settings.get("export_reminder_days"),
    )
