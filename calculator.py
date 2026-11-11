from typing import List, Tuple
from app.engine.models import (
    TariffPlan,
    BillCalculationRequest,
    BillCalculationResponse,
    SlabBreakdownItem,
    TaxBreakdownItem,
)


class TariffCalculator:
    """Core calculation engine for Indian electricity tariffs, slabs, fixed charges, taxes, and subsidies."""

    @classmethod
    def calculate_bill(
        cls,
        tariff: TariffPlan,
        units: float,
        sanctioned_load_kw: float = 1.0,
        apply_subsidy: bool = True,
        _compute_savings: bool = True,
    ) -> BillCalculationResponse:
        """
        Calculates a complete electricity bill based on the tariff rules.
        """
        units = max(0.0, round(units, 2))
        sanctioned_load_kw = max(0.1, round(sanctioned_load_kw, 2))

        # 1. Slab-based Energy Charges Calculation
        slab_breakdown, energy_charges = cls._calculate_energy_slabs(tariff, units)

        # 2. Fixed Monthly Charges Calculation
        fixed_charges, fixed_charge_details = cls._calculate_fixed_charges(
            tariff, sanctioned_load_kw
        )

        # 3. Government Duties & Surcharges Calculation
        taxes_and_surcharges, total_taxes = cls._calculate_taxes_and_surcharges(
            tariff, units, energy_charges, fixed_charges
        )

        # 4. Gross Bill
        gross_amount = round(energy_charges + fixed_charges + total_taxes, 2)

        # 5. Subsidy Calculation
        subsidy_applied, subsidy_name, subsidy_amount, subsidy_details = cls._calculate_subsidy(
            tariff, units, energy_charges, fixed_charges, total_taxes, gross_amount, apply_subsidy
        )

        # 6. Final Net Payable
        net_payable = max(0.0, round(gross_amount - subsidy_amount, 2))
        effective_rate = round(net_payable / units, 2) if units > 0 else 0.0

        # Helper to format currency values cleanly (e.g. ₹2,800 vs ₹3,349.20)
        def _fmt(val: float) -> str:
            r = round(val, 2)
            if r == int(r):
                return f"{int(r):,}"
            return f"{r:,.2f}"

        # 7. Detailed charge explanations
        active_slabs = [s for s in slab_breakdown if s.units_in_slab > 0]
        if active_slabs:
            slab_parts = [
                f"{s.units_in_slab:.1f} u × {tariff.currency}{s.rate_per_unit:.2f} ({s.range_description})"
                for s in active_slabs
            ]
            energy_explanation = (
                f"Calculated using progressive telescopic slab tiers: "
                f"{' + '.join(slab_parts)} = {tariff.currency}{_fmt(energy_charges)}"
            )
        else:
            energy_explanation = f"0 units consumed, resulting in {tariff.currency}0.00 energy charges."

        fixed_explanation = (
            f"Monthly base charge based on sanctioned demand: {fixed_charge_details} = {tariff.currency}{_fmt(fixed_charges)}"
        )

        if taxes_and_surcharges:
            tax_parts = [f"{t.name}: {tariff.currency}{_fmt(t.amount)}" for t in taxes_and_surcharges]
            taxes_explanation = f"Statutory taxes and surcharges: {', '.join(tax_parts)} = {tariff.currency}{_fmt(total_taxes)}"
        else:
            taxes_explanation = "No government duties, fuel adjustments, or surcharges applicable."

        units_display = f"{int(units)}" if units == int(units) else f"{units:.1f}"
        bill_explanation = (
            f"You used {units_display} electricity units this month. "
            f"Your estimated bill is {tariff.currency}{_fmt(net_payable)}. "
            f"Your energy charges are {tariff.currency}{_fmt(energy_charges)}, "
            f"fixed charges are {tariff.currency}{_fmt(fixed_charges)}, "
            f"and other charges are {tariff.currency}{_fmt(total_taxes)}."
        )

        # 8. Energy savings impact for saving 30 or 50 units
        savings_30 = None
        bill_minus_30 = None
        savings_50 = None
        bill_minus_50 = None

        if _compute_savings:
            if units > 0:
                units_30 = max(0.0, round(units - 30.0, 2))
                res_30 = cls.calculate_bill(
                    tariff, units_30, sanctioned_load_kw, apply_subsidy, _compute_savings=False
                )
                bill_minus_30 = res_30.net_payable
                savings_30 = max(0.0, round(net_payable - res_30.net_payable, 2))

                units_50 = max(0.0, round(units - 50.0, 2))
                res_50 = cls.calculate_bill(
                    tariff, units_50, sanctioned_load_kw, apply_subsidy, _compute_savings=False
                )
                bill_minus_50 = res_50.net_payable
                savings_50 = max(0.0, round(net_payable - res_50.net_payable, 2))
            else:
                savings_30 = 0.0
                bill_minus_30 = net_payable
                savings_50 = 0.0
                bill_minus_50 = net_payable

        return BillCalculationResponse(
            utility_id=tariff.utility_id,
            utility_name=tariff.utility_name,
            state=tariff.state,
            year=tariff.year,
            category=tariff.category,
            units=units,
            sanctioned_load_kw=sanctioned_load_kw,
            energy_charges=round(energy_charges, 2),
            slab_breakdown=slab_breakdown,
            fixed_charges=round(fixed_charges, 2),
            fixed_charge_details=fixed_charge_details,
            taxes_and_surcharges=taxes_and_surcharges,
            total_taxes_and_surcharges=round(total_taxes, 2),
            gross_amount=gross_amount,
            subsidy_applied=subsidy_applied,
            subsidy_name=subsidy_name,
            subsidy_amount=round(subsidy_amount, 2),
            subsidy_details=subsidy_details,
            net_payable=net_payable,
            effective_rate_per_unit=effective_rate,
            currency=tariff.currency,
            bill_explanation=bill_explanation,
            energy_explanation=energy_explanation,
            fixed_explanation=fixed_explanation,
            taxes_explanation=taxes_explanation,
            savings_30_units=savings_30,
            bill_at_minus_30=bill_minus_30,
            savings_50_units=savings_50,
            bill_at_minus_50=bill_minus_50,
        )

    @classmethod
    def _calculate_energy_slabs(
        cls, tariff: TariffPlan, units: float
    ) -> Tuple[List[SlabBreakdownItem], float]:
        """Calculates telescopic tiered slab costs."""
        slab_items: List[SlabBreakdownItem] = []
        total_energy_cost = 0.0

        if not tariff.slabs:
            return slab_items, total_energy_cost

        # Sort slabs by from_units
        sorted_slabs = sorted(tariff.slabs, key=lambda s: s.from_units)

        prev_upper = 0.0

        for idx, slab in enumerate(sorted_slabs, start=1):
            # Normalize boundary in case slabs are written as 0-100, 101-200
            effective_lower = prev_upper if (slab.from_units == prev_upper + 1) else slab.from_units

            if slab.to_units is not None:
                range_str = f"{int(slab.from_units)} - {int(slab.to_units)} units"
                upper_bound = slab.to_units
                prev_upper = upper_bound
            else:
                range_str = f"Above {int(slab.from_units)} units"
                upper_bound = float("inf")

            if units > effective_lower:
                units_in_this_slab = min(units, upper_bound) - effective_lower
                units_in_this_slab = max(0.0, round(units_in_this_slab, 2))
            else:
                units_in_this_slab = 0.0

            amount = round(units_in_this_slab * slab.rate_per_unit, 2)
            total_energy_cost += amount

            slab_items.append(
                SlabBreakdownItem(
                    slab_index=idx,
                    range_description=range_str,
                    units_in_slab=units_in_this_slab,
                    rate_per_unit=slab.rate_per_unit,
                    amount=amount,
                )
            )

        return slab_items, round(total_energy_cost, 2)

    @classmethod
    def _calculate_fixed_charges(
        cls, tariff: TariffPlan, sanctioned_load_kw: float
    ) -> Tuple[float, str]:
        """Computes fixed monthly demand charges."""
        fc_cfg = tariff.fixed_charges
        charge_type = fc_cfg.charge_type

        if charge_type == "per_kw_monthly":
            amount = sanctioned_load_kw * fc_cfg.rate
            if fc_cfg.min_charge and amount < fc_cfg.min_charge:
                amount = fc_cfg.min_charge
            details = f"{tariff.currency}{fc_cfg.rate:.2f}/kW/month × {sanctioned_load_kw:.1f} kW"
        elif charge_type == "flat_monthly":
            amount = fc_cfg.rate
            details = f"Flat charge of {tariff.currency}{fc_cfg.rate:.2f}/month"
        elif charge_type == "tiered_by_load":
            # For domestic <= 2kW vs > 2kW (typical in Delhi DERC)
            if sanctioned_load_kw <= 2.0:
                amount = sanctioned_load_kw * fc_cfg.rate
                details = f"{tariff.currency}{fc_cfg.rate:.2f}/kW/month (≤2 kW tier) × {sanctioned_load_kw:.1f} kW"
            else:
                higher_rate = fc_cfg.rate * 2.5
                amount = sanctioned_load_kw * higher_rate
                details = f"{tariff.currency}{higher_rate:.2f}/kW/month (>2 kW tier) × {sanctioned_load_kw:.1f} kW"
        else:
            amount = sanctioned_load_kw * fc_cfg.rate
            details = f"{tariff.currency}{fc_cfg.rate:.2f} × {sanctioned_load_kw:.1f} kW"

        return round(amount, 2), details

    @classmethod
    def _calculate_taxes_and_surcharges(
        cls,
        tariff: TariffPlan,
        units: float,
        energy_charges: float,
        fixed_charges: float,
    ) -> Tuple[List[TaxBreakdownItem], float]:
        """Calculates state electricity duties, fuel adjustment surcharges, and regulatory fees."""
        taxes: List[TaxBreakdownItem] = []
        taxes_cfg = tariff.taxes_and_surcharges
        total = 0.0

        # 1. Electricity Duty (applied on Energy Charges in most Indian states)
        if taxes_cfg.electricity_duty_pct > 0:
            duty_amt = round(energy_charges * (taxes_cfg.electricity_duty_pct / 100.0), 2)
            taxes.append(
                TaxBreakdownItem(
                    name="Electricity Duty",
                    rate_info=f"{taxes_cfg.electricity_duty_pct:.1f}% on Energy Charges",
                    amount=duty_amt,
                )
            )
            total += duty_amt

        # 2. FPPPA / FAC (Fuel and Power Purchase Price Adjustment, charged per unit)
        if taxes_cfg.fpppa_rate_per_unit > 0 and units > 0:
            fpppa_amt = round(units * taxes_cfg.fpppa_rate_per_unit, 2)
            taxes.append(
                TaxBreakdownItem(
                    name="Fuel Adjustment (FPPPA/FAC)",
                    rate_info=f"{tariff.currency}{taxes_cfg.fpppa_rate_per_unit:.2f}/unit",
                    amount=fpppa_amt,
                )
            )
            total += fpppa_amt

        # 3. Regulatory Surcharge (applied on Energy + Fixed charges, e.g. Delhi DERC)
        if taxes_cfg.regulatory_surcharge_pct > 0:
            base_sum = energy_charges + fixed_charges
            reg_amt = round(base_sum * (taxes_cfg.regulatory_surcharge_pct / 100.0), 2)
            taxes.append(
                TaxBreakdownItem(
                    name="Regulatory Surcharge",
                    rate_info=f"{taxes_cfg.regulatory_surcharge_pct:.1f}% on (Energy + Fixed)",
                    amount=reg_amt,
                )
            )
            total += reg_amt

        # 4. Pension Trust Surcharge (e.g. Delhi)
        if taxes_cfg.pension_surcharge_pct > 0:
            base_sum = energy_charges + fixed_charges
            pension_amt = round(base_sum * (taxes_cfg.pension_surcharge_pct / 100.0), 2)
            taxes.append(
                TaxBreakdownItem(
                    name="Pension Trust Surcharge",
                    rate_info=f"{taxes_cfg.pension_surcharge_pct:.1f}% on (Energy + Fixed)",
                    amount=pension_amt,
                )
            )
            total += pension_amt

        return taxes, round(total, 2)

    @classmethod
    def _calculate_subsidy(
        cls,
        tariff: TariffPlan,
        units: float,
        energy_charges: float,
        fixed_charges: float,
        taxes: float,
        gross_amount: float,
        apply_subsidy: bool,
    ) -> Tuple[bool, str, float, str]:
        """Calculates state-specific electricity subsidies (Delhi, Karnataka Gruha Jyothi, Tamil Nadu, etc.)."""
        if not apply_subsidy or not tariff.subsidy:
            return False, "", 0.0, "Subsidy not requested or not configured for this utility."

        subsidy = tariff.subsidy
        stype = subsidy.subsidy_type.lower()
        currency = tariff.currency

        if stype == "delhi_lifeline":
            # Delhi Lifeline scheme:
            # 0 - 200 units: 100% subsidy (net payable is ₹0, all energy + fixed + surcharges waived)
            # 201 - 400 units: 50% discount on energy charges (capped at ₹800)
            # > 400 units: 0 subsidy
            if units <= 200.0:
                subsidy_amt = gross_amount
                return (
                    True,
                    subsidy.scheme_name,
                    subsidy_amt,
                    f"100% Lifeline Subsidy: Consumption ≤ 200 units. Full waiver of {currency}{gross_amount:.2f}.",
                )
            elif units <= 400.0:
                subsidy_amt = min(800.0, round(energy_charges * 0.50, 2))
                return (
                    True,
                    subsidy.scheme_name,
                    subsidy_amt,
                    f"50% Subsidy on Energy Charges for consumption between 201-400 units (Saved {currency}{subsidy_amt:.2f}).",
                )
            else:
                return (
                    False,
                    subsidy.scheme_name,
                    0.0,
                    "Consumption exceeded 400 units limit. No subsidy applicable under Delhi Lifeline policy.",
                )

        elif stype == "gruha_jyothi":
            # Karnataka Gruha Jyothi:
            # Entitlement up to 200 units per month for domestic consumers.
            # If consumption <= 200 units: 100% subsidy (net payable = 0).
            # If consumption > 200 units: Full bill payable (0 subsidy).
            if units <= 200.0:
                subsidy_amt = gross_amount
                return (
                    True,
                    subsidy.scheme_name,
                    subsidy_amt,
                    f"Gruha Jyothi: 100% subsidy for consumption ≤ 200 units. Full waiver of {currency}{gross_amount:.2f}.",
                )
            else:
                return (
                    False,
                    subsidy.scheme_name,
                    0.0,
                    f"Consumption ({units:.0f} units) exceeded 200 unit Gruha Jyothi threshold. Full bill payable.",
                )

        elif stype == "tamil_nadu_universal":
            # Tamil Nadu: First 100 units 100% free for all domestic consumers.
            # If first slab is ₹0, the energy is already free in slab calculation.
            # Fixed charge or duty waiver for low-income can also be covered.
            return (
                True,
                subsidy.scheme_name,
                0.0,
                "TANGEDCO Scheme: First 100 units already priced at ₹0.00/unit in slab calculations.",
            )

        elif stype == "flat_percentage":
            discount_pct = subsidy.discount_pct or 0.0
            subsidy_amt = round(energy_charges * (discount_pct / 100.0), 2)
            return (
                True,
                subsidy.scheme_name,
                subsidy_amt,
                f"{discount_pct}% Government Subsidy on Energy Charges (Saved {currency}{subsidy_amt:.2f}).",
            )

        return False, "", 0.0, "Standard tariff applied with no active subsidy."
