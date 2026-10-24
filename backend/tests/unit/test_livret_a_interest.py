"""FR-009 : intérêts estimés du Livret A par quinzaine, crédités au 31 décembre.

Règle testée (research.md §8) : intérêt d'une quinzaine = solde minimum de la quinzaine x taux
annuel / 24. Un dépôt compte à partir de la quinzaine qui suit, un retrait dès la quinzaine en
cours. Les intérêts de l'année sont arrondis au centime (demi supérieur) au crédit du 31
décembre ; les intérêts réels saisis prévalent. Montants attendus calculés à la main.
"""

from datetime import UTC, datetime
from decimal import Decimal

from finance.domain.livret_a import Flow, InterestEstimate, LivretASchedule, RateRow

from finance.domain.caps import DEFAULT_LIVRET_A_CAP
from finance.domain.enums import TransactionType as T
from finance.domain.networth import AccountRef, compute_net_worth
from finance.domain.valuation import value_account
from tests.domain_helpers import d, day, deposit, make

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def rate(on: str, value: str) -> RateRow:
    return RateRow(effective_from=day(on), value=d(value), recorded_at=NOW)


R3 = [rate("2025-01-01", "3")]


def flow(on: str, amount: str, real: bool = False) -> Flow:
    return Flow(on=day(on), amount=d(amount), real_interest=real)


def at(flows, rates, on, until="2030-12-31") -> InterestEstimate:  # type: ignore[no-untyped-def]
    return LivretASchedule.build(flows, rates, until=day(until)).estimate_at(day(on))


def test_the_default_cap_is_22950() -> None:
    assert Decimal("22950") == DEFAULT_LIVRET_A_CAP


class TestQuinzaines:
    def test_a_balance_held_all_period_earns_a_twenty_fourth_of_the_rate_per_quinzaine(
        self,
    ) -> None:
        got = at([flow("2025-12-31", "1000")], R3, "2026-01-31")
        # 2 quinzaines x 1000 x 3 % / 24
        assert (got.credited, got.accrued, got.missing_rate_from) == (d("0"), d("2.5"), None)

    def test_a_deposit_counts_from_the_next_quinzaine(self) -> None:
        got = at([flow("2026-01-10", "1000")], R3, "2026-01-31")
        assert got.accrued == d("1.25")  # seule la quinzaine du 16 au 31 janvier

    def test_a_deposit_on_the_15th_counts_from_the_16th(self) -> None:
        assert at([flow("2026-01-15", "1000")], R3, "2026-01-31").accrued == d("1.25")

    def test_a_deposit_on_the_16th_counts_from_the_1st_of_the_next_month(self) -> None:
        flows = [flow("2026-01-16", "1000")]
        assert at(flows, R3, "2026-01-31").accrued == d("0")
        assert at(flows, R3, "2026-02-15").accrued == d("1.25")

    def test_a_withdrawal_takes_effect_in_the_current_quinzaine(self) -> None:
        flows = [flow("2025-12-20", "2000"), flow("2026-01-10", "-500")]
        # 1500 sur les deux quinzaines : 2 x 1500 x 3 % / 24
        assert at(flows, R3, "2026-01-31").accrued == d("3.75")

    def test_a_withdrawal_on_the_16th_counts_for_that_quinzaine(self) -> None:
        flows = [flow("2025-12-20", "1000"), flow("2026-01-16", "-400")]
        assert at(flows, R3, "2026-01-31").accrued == d("2")  # (1000 + 600) x 3 % / 24

    def test_only_completed_quinzaines_count(self) -> None:
        flows = [flow("2025-12-31", "1000")]
        assert at(flows, R3, "2026-01-30").accrued == d("1.25")
        assert at(flows, R3, "2026-01-31").accrued == d("2.5")

    def test_no_flow_means_no_interest(self) -> None:
        assert at([], R3, "2026-06-30") == InterestEstimate(d("0"), d("0"), None)

    def test_a_balance_that_returns_to_zero_earns_nothing_afterwards(self) -> None:
        flows = [flow("2025-12-20", "1000"), flow("2026-01-16", "-1000")]
        assert at(flows, R3, "2026-03-31").accrued == d("1.25")  # première quinzaine seulement


class TestRates:
    def test_the_rate_in_force_at_the_start_of_each_quinzaine_applies(self) -> None:
        rates = [rate("2025-01-01", "3"), rate("2026-02-01", "2.4")]
        got = at([flow("2025-12-31", "1200")], rates, "2026-02-15")
        # (1200 x 3 + 1200 x 3 + 1200 x 2,4) / 2400
        assert got.accrued == d("4.2")

    def test_a_correction_on_the_same_date_uses_the_latest_entry(self) -> None:
        rates = [
            RateRow(day("2025-01-01"), d("3"), NOW),
            RateRow(day("2025-01-01"), d("2.4"), datetime(2026, 1, 2, tzinfo=UTC)),
        ]
        assert at([flow("2025-12-31", "1200")], rates, "2026-01-15").accrued == d("1.2")

    def test_a_missing_rate_is_reported_and_the_period_left_out(self) -> None:
        rates = [rate("2026-02-01", "2.4")]
        got = at([flow("2025-12-31", "1200")], rates, "2026-02-15")
        assert got.missing_rate_from == day("2026-01-01")
        assert got.accrued == d("1.2")  # seule la quinzaine de février a un taux

    def test_no_rate_at_all(self) -> None:
        got = at([flow("2025-12-31", "1200")], [], "2026-02-15")
        assert got.accrued == d("0") and got.missing_rate_from == day("2026-01-01")


class TestCrediting:
    def test_the_year_is_credited_on_the_31st_of_december(self) -> None:
        flows = [flow("2025-12-31", "1000")]
        before = at(flows, R3, "2026-12-30")
        after = at(flows, R3, "2026-12-31")
        assert before.credited == d("0") and before.accrued == d("28.75")  # 23 quinzaines terminées
        assert (after.credited, after.accrued) == (d("30"), d("0"))

    def test_credited_interest_earns_interest_the_next_year(self) -> None:
        flows = [flow("2025-12-31", "1000")]
        first = at(flows, R3, "2027-01-15")
        assert first.credited == d("30")
        assert first.accrued == d("1.2875")  # 1030 x 3 % / 24
        second = at(flows, R3, "2027-12-31")
        assert second.credited == d("60.9")  # 30 + 24 x 1030 x 3 % / 24 = 30 + 30,90

    def test_the_yearly_amount_is_rounded_half_up_to_the_cent(self) -> None:
        got = at([flow("2025-12-31", "1")], [rate("2025-01-01", "0.5")], "2026-12-31")
        assert got.credited == d("0.01")  # 0,005

    def test_a_real_interest_operation_replaces_the_estimate_of_its_year(self) -> None:
        flows = [flow("2025-12-31", "1000"), flow("2026-12-31", "28.5", real=True)]
        assert at(flows, R3, "2026-12-31") == InterestEstimate(d("0"), d("0"), None)

    def test_before_the_real_operation_the_estimate_still_shows(self) -> None:
        flows = [flow("2025-12-31", "1000"), flow("2026-12-31", "28.5", real=True)]
        assert at(flows, R3, "2026-06-30").accrued == d("15")  # 12 quinzaines x 1000 x 3 % / 24

    def test_real_interest_is_part_of_the_balance_that_earns_the_next_year(self) -> None:
        flows = [flow("2025-12-31", "1000"), flow("2026-12-31", "28.5", real=True)]
        got = at(flows, R3, "2027-01-15")
        assert got.credited == d("0") and got.accrued == d("1.285625")  # 1028,5 x 3 % / 24


def test_a_schedule_built_further_ahead_gives_the_same_estimates() -> None:
    flows = [
        flow("2025-03-10", "3000"),
        flow("2025-08-20", "-400"),
        flow("2026-01-16", "250"),
        flow("2026-12-31", "55.1", real=True),
        flow("2027-05-05", "-1000"),
    ]
    rates = [rate("2025-01-01", "3"), rate("2025-08-01", "2.4"), rate("2027-02-01", "1.7")]
    for on in ("2025-06-15", "2025-12-31", "2026-01-31", "2026-12-31", "2027-03-01", "2027-12-31"):
        near = LivretASchedule.build(flows, rates, until=day(on)).estimate_at(day(on))
        far = LivretASchedule.build(flows, rates, until=day("2029-12-31")).estimate_at(day(on))
        assert near == far, on


def test_flows_come_from_the_account_entries() -> None:
    entries = [
        deposit("1000", "2025-12-31"),
        make(T.INTEREST, "2026-12-31", cash="28.5"),
        make(T.DEPOSIT, "2026-01-02", cash="5", voided=True),
        deposit("999", "2026-01-02", account="other"),
    ]
    schedule = LivretASchedule.from_entries(entries, "a1", R3, until=day("2027-01-15"))
    assert schedule.estimate_at(day("2027-01-15")).accrued == d("1.285625")


class TestInAccountValue:
    ENTRIES = (deposit("1000", "2025-12-31"),)

    def test_the_estimated_interest_is_added_to_the_value_and_flagged(self) -> None:
        schedule = LivretASchedule.from_entries(self.ENTRIES, "a1", R3, until=day("2026-01-31"))
        result = value_account(
            account_id="a1",
            entries=list(self.ENTRIES),
            instruments={},
            prices=[],
            balances=[],
            as_of=day("2026-01-31"),
            currency="EUR",
            livret=schedule,
        )
        assert result.cash == d("1000") and result.interest_estimate == d("2.5")
        assert result.total == d("1002.5") and result.estimated

    def test_a_missing_rate_is_a_warning(self) -> None:
        schedule = LivretASchedule.from_entries(self.ENTRIES, "a1", [], until=day("2026-01-31"))
        result = value_account(
            account_id="a1",
            entries=list(self.ENTRIES),
            instruments={},
            prices=[],
            balances=[],
            as_of=day("2026-01-31"),
            currency="EUR",
            livret=schedule,
        )
        assert [w.code for w in result.warnings] == ["rate_missing"]
        assert result.estimated and result.total == d("1000")

    def test_an_ordinary_account_has_no_interest(self) -> None:
        result = value_account(
            account_id="a1",
            entries=list(self.ENTRIES),
            instruments={},
            prices=[],
            balances=[],
            as_of=day("2026-01-31"),
            currency="EUR",
        )
        assert result.interest_estimate == d("0") and not result.estimated

    def test_net_worth_adds_the_interest_of_livret_accounts_only(self) -> None:
        refs = [
            AccountRef("a1", day("2025-01-01"), None, "EUR", is_livret_a=True),
            AccountRef("a2", day("2025-01-01"), None, "EUR"),
        ]
        entries = [*self.ENTRIES, deposit("1000", "2025-12-31", account="a2")]
        result = compute_net_worth(
            refs=refs,
            entries=entries,
            instruments={},
            prices=[],
            balances=[],
            as_of=day("2026-01-31"),
            currency="EUR",
            livret_rates=R3,
        )
        assert result.total == d("2002.5") and result.estimated
