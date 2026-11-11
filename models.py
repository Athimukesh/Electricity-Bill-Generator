from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class TariffSlab(BaseModel):
    """Represents a single tiered consumption slab."""
    from_units: float = Field(ge=0, description="Starting units (inclusive)")
    to_units: Optional[float] = Field(default=None, description="Ending units (inclusive), None if open-ended")
    rate_per_unit: float = Field(ge=0, description="Cost in currency per unit (kWh)")


class FixedChargeConfig(BaseModel):
    """Configuration for fixed monthly charges."""
    charge_type: str = Field(
        default="per_kw_monthly",
        description="'per_kw_monthly' (rate * load_kw), 'flat_monthly', or 'tiered_by_load'"
    )
    rate: float = Field(ge=0, description="Base rate in rupees")
    min_charge: Optional[float] = Field(default=0.0, description="Minimum fixed charge applicable")


class TaxAndDutyConfig(BaseModel):
    """Configuration for government taxes, electricity duty, and surcharges."""
    electricity_duty_pct: float = Field(default=0.0, description="Electricity Duty % applied to energy charges")
    fpppa_rate_per_unit: float = Field(default=0.0, description="Fuel / Power Purchase Adjustment per unit (₹/kWh)")
    regulatory_surcharge_pct: float = Field(default=0.0, description="Regulatory Surcharge % (on energy + fixed charges)")
    pension_surcharge_pct: float = Field(default=0.0, description="Pension Trust Surcharge % (e.g. in Delhi)")


class SubsidyConfig(BaseModel):
    """Configuration for state/utility specific electricity subsidies."""
    scheme_name: str = Field(description="Name of the government subsidy scheme")
    subsidy_type: str = Field(
        description="Type: 'delhi_lifeline', 'gruha_jyothi', 'tamil_nadu_universal', 'flat_percentage', 'none'"
    )
    free_units_limit: Optional[float] = Field(default=None, description="Max units for free entitlement")
    discount_pct: Optional[float] = Field(default=None, description="Discount percentage if applicable")
    description: str = Field(default="", description="Human-readable description of subsidy rules")


class TariffPlan(BaseModel):
    """Common tariff structure representing an electricity board's tariff rules for a specific year."""
    utility_id: str = Field(description="Unique identifier, e.g., 'bescom_karnataka'")
    utility_name: str = Field(description="Official name of electricity board")
    state: str = Field(description="Indian State / UT")
    year: int = Field(description="Effective tariff year, e.g., 2024")
    category: str = Field(default="Domestic / Residential (LT)", description="Consumer tariff category")
    description: Optional[str] = Field(default="", description="Tariff details and context")
    currency: str = Field(default="₹", description="Currency symbol")
    fixed_charges: FixedChargeConfig
    slabs: List[TariffSlab]
    taxes_and_surcharges: TaxAndDutyConfig = Field(default_factory=TaxAndDutyConfig)
    subsidy: Optional[SubsidyConfig] = None


# --- Request and Response Schemas for Calculation Engine & REST API ---

class BillCalculationRequest(BaseModel):
    utility_id: str = Field(description="Utility identifier (e.g. 'bses_delhi', 'bescom_karnataka')")
    year: Optional[int] = Field(default=None, description="Tariff year (defaults to latest available year)")
    units: float = Field(ge=0, description="Electricity consumption in units (kWh)")
    sanctioned_load_kw: float = Field(default=1.0, gt=0, description="Sanctioned load in kW (used for fixed charges)")
    apply_subsidy: bool = Field(default=True, description="Whether to apply state government subsidy if eligible")


class SlabBreakdownItem(BaseModel):
    slab_index: int
    range_description: str
    units_in_slab: float
    rate_per_unit: float
    amount: float


class TaxBreakdownItem(BaseModel):
    name: str
    rate_info: str
    amount: float


class BillCalculationResponse(BaseModel):
    utility_id: str
    utility_name: str
    state: str
    year: int
    category: str
    units: float
    sanctioned_load_kw: float

    # Energy slab charges
    energy_charges: float
    slab_breakdown: List[SlabBreakdownItem]

    # Fixed charges
    fixed_charges: float
    fixed_charge_details: str

    # Taxes & Surcharges
    taxes_and_surcharges: List[TaxBreakdownItem]
    total_taxes_and_surcharges: float

    # Totals before & after subsidy
    gross_amount: float
    subsidy_applied: bool
    subsidy_name: Optional[str] = None
    subsidy_amount: float = 0.0
    subsidy_details: Optional[str] = None

    net_payable: float
    effective_rate_per_unit: float
    currency: str = "₹"

    # Human-friendly charge explanations
    bill_explanation: Optional[str] = None
    energy_explanation: Optional[str] = None
    fixed_explanation: Optional[str] = None
    taxes_explanation: Optional[str] = None

    # Energy savings impact (for saving 30 or 50 units)
    savings_30_units: Optional[float] = None
    bill_at_minus_30: Optional[float] = None
    savings_50_units: Optional[float] = None
    bill_at_minus_50: Optional[float] = None


class SimulationRequest(BaseModel):
    utility_ids: Optional[List[str]] = Field(
        default=None,
        description="List of utility IDs to simulate. If None/empty, simulates for all registered utilities."
    )
    year: Optional[int] = Field(default=None, description="Tariff year (defaults to latest)")
    start_units: float = Field(default=0.0, ge=0, description="Starting consumption units")
    end_units: float = Field(default=500.0, ge=0, description="Ending consumption units")
    step: float = Field(default=50.0, gt=0, description="Step increment for units")
    exact_units: Optional[float] = Field(
        default=None,
        description="Optional exact consumption units to explicitly include in the simulated curve points"
    )
    sanctioned_load_kw: float = Field(default=1.0, gt=0, description="Sanctioned load in kW")
    apply_subsidy: bool = Field(default=True, description="Whether to include subsidies in simulation")


class UtilitySummary(BaseModel):
    utility_id: str
    utility_name: str
    state: str
    available_years: List[int]
    category: str
    has_subsidy: bool
    subsidy_name: Optional[str] = None


class SimulationPoint(BaseModel):
    units: float
    bills: Dict[str, BillCalculationResponse]


class SimulationResponse(BaseModel):
    points: List[SimulationPoint]
    utilities_simulated: List[str]

