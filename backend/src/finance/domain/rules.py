"""Règles de validation d'une opération (data-model.md).

Les erreurs bloquent la saisie ; les avertissements ne la bloquent jamais (un historique peut être
incomplet). La fonction est pure : l'appelant fournit le contexte (compte, quantité détenue).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from finance.domain.enums import AccountType
from finance.domain.enums import TransactionType as T

_TRADES = frozenset({T.BUY, T.SELL})
_INSTRUMENT_REQUIRED = frozenset({T.BUY, T.SELL, T.DIVIDEND, T.DISTRIBUTION})
_INSTRUMENT_FORBIDDEN = frozenset(
    {T.DEPOSIT, T.WITHDRAWAL, T.FEE, T.EMPLOYER_MATCH, T.TRANSFER_OUT, T.TRANSFER_IN}
)
_TRANSFERS = frozenset({T.TRANSFER_OUT, T.TRANSFER_IN})
_CONTRIBUTIONS = frozenset({T.DEPOSIT, T.EMPLOYER_MATCH})


@dataclass(frozen=True)
class Violation:
    code: str
    field: str
    message: str


@dataclass(frozen=True)
class RuleResult:
    errors: tuple[Violation, ...] = ()
    warnings: tuple[Violation, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def check_transaction(
    *,
    account_type: AccountType,
    account_opened_on: date,
    type: T,
    trade_date: date,
    amount: Decimal | None = None,
    has_instrument: bool = False,
    quantity: Decimal | None = None,
    unit_price: Decimal | None = None,
    fees: Decimal = Decimal(0),
    transfer_group_id: str | None = None,
    unlock_date: date | None = None,
    held_quantity: Decimal | None = None,
) -> RuleResult:
    errors: list[Violation] = []
    warnings: list[Violation] = []

    def error(code: str, field: str, message: str) -> None:
        errors.append(Violation(code, field, message))

    if type is T.EMPLOYER_MATCH and account_type is not AccountType.PEE:
        error("employer_match_pee_only", "type", "L'abondement n'existe que sur un PEE.")
    if type in _TRADES and account_type is AccountType.LIVRET_A:
        error(
            "livret_a_cash_only",
            "type",
            "Un Livret A ne contient que de la trésorerie : pas d'achat ni de vente.",
        )
    if trade_date < account_opened_on:
        error(
            "before_opening",
            "trade_date",
            "La date de l'opération précède l'ouverture du compte.",
        )
    if fees < 0:
        error("fees_not_negative", "fees", "Les frais ne peuvent pas être négatifs.")

    if type in _TRADES:
        if amount is not None:
            error("amount_forbidden", "amount", "Un achat ou une vente n'a pas de montant libre.")
        if quantity is None or quantity <= 0:
            error("quantity_positive", "quantity", "La quantité doit être strictement positive.")
        if unit_price is None or unit_price <= 0:
            error(
                "unit_price_positive",
                "unit_price",
                "Le prix unitaire doit être strictement positif.",
            )
    else:
        if amount is None or amount <= 0:
            error("amount_positive", "amount", "Le montant doit être strictement positif.")
        if quantity is not None or unit_price is not None:
            error(
                "trade_fields_forbidden",
                "quantity",
                "La quantité et le prix unitaire ne concernent que les achats et les ventes.",
            )

    if type in _INSTRUMENT_REQUIRED and not has_instrument:
        error("instrument_required", "instrument", "Cette opération porte sur un actif.")
    if type in _INSTRUMENT_FORBIDDEN and has_instrument:
        error(
            "instrument_forbidden",
            "instrument",
            "Cette opération est un flux de trésorerie : elle ne porte sur aucun actif.",
        )

    if type in _TRANSFERS and transfer_group_id is None:
        error("transfer_group_required", "transfer_group_id", "Un virement a un groupe de jambes.")
    if type not in _TRANSFERS and transfer_group_id is not None:
        error(
            "transfer_group_forbidden",
            "transfer_group_id",
            "Seul un virement appartient à un groupe de jambes.",
        )

    if unlock_date is not None:
        if account_type is not AccountType.PEE:
            error("unlock_date_pee_only", "unlock_date", "La date de déblocage concerne le PEE.")
        if type not in _CONTRIBUTIONS:
            error(
                "unlock_date_contribution_only",
                "unlock_date",
                "Seul un versement ou un abondement a une date de déblocage.",
            )

    if (
        type is T.SELL
        and held_quantity is not None
        and quantity is not None
        and quantity > held_quantity
    ):
        warnings.append(
            Violation(
                "oversell",
                "quantity",
                "La vente dépasse la quantité détenue : l'historique est peut-être incomplet.",
            )
        )
    return RuleResult(errors=tuple(errors), warnings=tuple(warnings))
