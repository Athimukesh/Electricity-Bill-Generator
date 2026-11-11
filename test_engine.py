import pytest
from app.engine.models import (
    TariffPlan,
    TariffSlab,
    FixedChargeConfig,
    TaxAndDutyConfig,
    SubsidyConfig,
)
from app.engine.calculator import TariffCalculator
from app.engine.registry import TariffRegistry, registry


def test_zero_units_consumption():
    """Testing that 0 units consumption still applies fixed charges unless fully subsidized."""
    tariff = registry.get_tariff("msedcl_maharashtra", 2024)
    assert tariff is not None

    bill = TariffCalculator.calculate_bill(tariff, units=0, sanctioned_load_kw=1.0, apply_subsidy=True)
    assert bill.units == 0.0
    assert bill.energy_charges == 0.0
    assert bill.fixed_charges == 128.0  # Flat monthly charge for MSEDCL
    assert bill.net_payable == 128.0


def test_slab_boundary_calculations():
    """Testing accurate tiered slab distribution for BESCOM Karnataka."""
    tariff = registry.get_tariff("bescom_karnataka", 2024)
    assert tariff is not None

    # Slabs for BESCOM 2024:
    # 0 to 100 @ 4.75
    # 101+ @ 7.00
    # Test 50 units (all in slab 1)
    bill_50 = TariffCalculator.calculate_bill(tariff, units=50, sanctioned_load_kw=1.0, apply_subsidy=False)
    assert bill_50.slab_breakdown[0].units_in_slab == 50.0
    assert bill_50.slab_breakdown[0].amount == 50 * 4.75
    assert bill_50.energy_charges == 50 * 4.75

    # Test 150 units (100 in slab 1, 50 in slab 2)
    bill_150 = TariffCalculator.calculate_bill(tariff, units=150, sanctioned_load_kw=1.0, apply_subsidy=False)
    assert bill_150.slab_breakdown[0].units_in_slab == 100.0
    assert bill_150.slab_breakdown[0].amount == 475.0
    assert bill_150.slab_breakdown[1].units_in_slab == 50.0
    assert bill_150.slab_breakdown[1].amount == 50 * 7.00
    assert bill_150.energy_charges == 475.0 + 350.0  # 825.0


def test_delhi_lifeline_subsidy():
    """Testing Delhi DERC Lifeline subsidy thresholds."""
    tariff = registry.get_tariff("bses_delhi", 2024)
    assert tariff is not None

    # Case 1: <= 200 units -> 100% bill waiver
    bill_180 = TariffCalculator.calculate_bill(tariff, units=180, sanctioned_load_kw=1.0, apply_subsidy=True)
    assert bill_180.subsidy_applied is True
    assert bill_180.net_payable == 0.0
    assert bill_180.subsidy_amount == bill_180.gross_amount

    # Case 2: 250 units (in 201-400 range) -> 50% energy charges discount
    bill_250 = TariffCalculator.calculate_bill(tariff, units=250, sanctioned_load_kw=1.0, apply_subsidy=True)
    assert bill_250.subsidy_applied is True
    expected_subsidy = round(bill_250.energy_charges * 0.50, 2)
    assert bill_250.subsidy_amount == expected_subsidy
    assert bill_250.net_payable == round(bill_250.gross_amount - expected_subsidy, 2)

    # Case 3: 450 units (> 400 range) -> 0 subsidy
    bill_450 = TariffCalculator.calculate_bill(tariff, units=450, sanctioned_load_kw=1.0, apply_subsidy=True)
    assert bill_450.subsidy_amount == 0.0
    assert bill_450.net_payable == bill_450.gross_amount


def test_karnataka_gruha_jyothi_subsidy():
    """Testing Gruha Jyothi subsidy cliff edge at 200 units."""
    tariff = registry.get_tariff("bescom_karnataka", 2024)
    assert tariff is not None

    # 190 units <= 200 -> 100% subsidy (net payable 0)
    bill_subsidized = TariffCalculator.calculate_bill(tariff, units=190, sanctioned_load_kw=1.0, apply_subsidy=True)
    assert bill_subsidized.subsidy_applied is True
    assert bill_subsidized.net_payable == 0.0

    # 210 units > 200 -> Full bill payable (0 subsidy)
    bill_full = TariffCalculator.calculate_bill(tariff, units=210, sanctioned_load_kw=1.0, apply_subsidy=True)
    assert bill_full.subsidy_amount == 0.0
    assert bill_full.net_payable == bill_full.gross_amount
    assert bill_full.net_payable > 0


def test_tamil_nadu_100_free_units():
    """Testing Tamil Nadu TANGEDCO 100 units universal free tier."""
    tariff = registry.get_tariff("tangedco_tamil_nadu", 2024)
    assert tariff is not None

    # First 100 units have rate 0.0
    bill_90 = TariffCalculator.calculate_bill(tariff, units=90, sanctioned_load_kw=1.0, apply_subsidy=True)
    assert bill_90.energy_charges == 0.0


def test_multi_year_tariff_retrieval():
    """Testing retrieval of specific years and default to latest year."""
    # BSES Delhi has 2023 and 2024
    t_2023 = registry.get_tariff("bses_delhi", 2023)
    t_2024 = registry.get_tariff("bses_delhi", 2024)
    t_latest = registry.get_tariff("bses_delhi", None)

    assert t_2023 is not None
    assert t_2024 is not None
    assert t_latest is not None
    assert t_2023.year == 2023
    assert t_2024.year == 2024
    assert t_latest.year == 2024  # Latest should be 2024


def test_custom_tariff_registration():
    """Testing dynamic modular registration of a new utility."""
    custom_plan = TariffPlan(
        utility_id="pvvnl_up",
        utility_name="Paschimanchal Vidyut Vitran Nigam Ltd (PVVNL)",
        state="Uttar Pradesh",
        year=2024,
        category="Domestic LMV-1",
        fixed_charges=FixedChargeConfig(charge_type="per_kw_monthly", rate=120.0),
        slabs=[
            TariffSlab(from_units=0, to_units=150, rate_per_unit=5.50),
            TariffSlab(from_units=151, to_units=300, rate_per_unit=6.00),
            TariffSlab(from_units=301, to_units=None, rate_per_unit=7.00),
        ],
        taxes_and_surcharges=TaxAndDutyConfig(electricity_duty_pct=5.0),
        subsidy=None,
    )

    reg = TariffRegistry()
    reg.register_tariff(custom_plan, persist_to_disk=False)

    fetched = reg.get_tariff("pvvnl_up", 2024)
    assert fetched is not None
    assert fetched.utility_name == "Paschimanchal Vidyut Vitran Nigam Ltd (PVVNL)"

    bill = TariffCalculator.calculate_bill(fetched, units=200, sanctioned_load_kw=2.0)
    # Energy: 150 * 5.50 (825) + 50 * 6.00 (300) = 1125.0
    assert bill.energy_charges == 1125.0
    # Fixed: 2 * 120 = 240.0
    assert bill.fixed_charges == 240.0
    # Taxes: 5% on 1125 = 56.25
    assert bill.total_taxes_and_surcharges == 56.25
    assert bill.net_payable == 1125.0 + 240.0 + 56.25
