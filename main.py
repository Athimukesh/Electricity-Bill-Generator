from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List, Optional, Dict

from app.engine.models import (
    TariffPlan,
    BillCalculationRequest,
    BillCalculationResponse,
    SimulationRequest,
    SimulationResponse,
    SimulationPoint,
    UtilitySummary,
)
from app.engine.calculator import TariffCalculator
from app.engine.registry import registry

app = FastAPI(
    title="Open Tariff Engine for Indian Electricity Bills",
    description="A modular, standardized tariff calculation and simulation engine for Indian electricity utility boards.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for external client applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for the frontend dashboard
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serves the interactive web simulator dashboard."""
    index_file = static_path / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Open Tariff Engine API is running. Visit /docs for Swagger documentation."}


@app.get("/api", tags=["General"])
def api_info():
    """Returns general metadata about the Open Tariff Engine."""
    return {
        "engine": "Open Tariff Engine for Indian Electricity Bills",
        "version": "1.0.0",
        "description": "Standardized calculation and simulation engine supporting slab tiers, fixed charges, and state subsidies.",
        "utilities_count": len(registry.list_utilities()),
        "endpoints": {
            "utilities": "/api/utilities",
            "tariffs": "/api/tariffs/{utility_id}",
            "calculate": "/api/calculate",
            "simulate": "/api/simulate",
            "compare": "/api/compare",
            "docs": "/docs",
        },
    }


@app.get("/api/utilities", response_model=List[UtilitySummary], tags=["Utilities"])
def list_utilities():
    """Lists all registered electricity utilities, states, and available tariff years."""
    return registry.list_utilities()


@app.get("/api/tariffs/{utility_id}", response_model=TariffPlan, tags=["Tariffs"])
def get_tariff(utility_id: str, year: Optional[int] = Query(None, description="Tariff year (defaults to latest)")):
    """Retrieves the complete tariff structure and slab rules for a specific utility."""
    tariff = registry.get_tariff(utility_id, year)
    if not tariff:
        raise HTTPException(
            status_code=404,
            detail=f"Tariff not found for utility '{utility_id}'" + (f" and year {year}" if year else ""),
        )
    return tariff


@app.post("/api/tariffs", response_model=TariffPlan, status_code=201, tags=["Tariffs"])
def register_tariff(tariff: TariffPlan, persist: bool = Query(True, description="Whether to persist to disk")):
    """Registers a new electricity utility or tariff year into the system."""
    try:
        registered = registry.register_tariff(tariff, persist_to_disk=persist)
        return registered
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to register tariff: {str(e)}")


@app.post("/api/calculate", response_model=BillCalculationResponse, tags=["Calculation"])
def calculate_bill(request: BillCalculationRequest):
    """
    Calculates the electricity bill for given consumption units, utility, load, and subsidy preference.
    Computes slab breakdown, fixed charges, government taxes/duties, and subsidies.
    """
    tariff = registry.get_tariff(request.utility_id, request.year)
    if not tariff:
        raise HTTPException(
            status_code=404,
            detail=f"Utility '{request.utility_id}' with year {request.year or 'latest'} not found.",
        )

    response = TariffCalculator.calculate_bill(
        tariff=tariff,
        units=request.units,
        sanctioned_load_kw=request.sanctioned_load_kw,
        apply_subsidy=request.apply_subsidy,
    )
    return response


@app.post("/api/simulate", response_model=SimulationResponse, tags=["Simulation"])
def simulate_tariffs(sim_req: SimulationRequest):
    """
    Simulates electricity bills across a range of consumption units (e.g., 0 to 500 units).
    Can simulate for a specific utility or compare across multiple utilities simultaneously.
    """
    # Determine which utilities to include
    if sim_req.utility_ids and len(sim_req.utility_ids) > 0:
        target_uids = [u.strip().lower() for u in sim_req.utility_ids]
    else:
        target_uids = registry.get_all_utility_ids()

    # Pre-fetch tariffs
    utility_tariffs: Dict[str, TariffPlan] = {}
    for uid in target_uids:
        t = registry.get_tariff(uid, sim_req.year)
        if t:
            utility_tariffs[uid] = t

    if not utility_tariffs:
        raise HTTPException(
            status_code=404,
            detail="No matching tariffs found for the requested utilities.",
        )

    # Generate consumption points with optional exact_units inclusion
    step = max(1.0, sim_req.step)
    end_units = max(sim_req.start_units, sim_req.end_units)

    unit_values_set = set()
    val = sim_req.start_units
    while val <= end_units:
        unit_values_set.add(round(val, 2))
        val += step

    if sim_req.exact_units is not None:
        exact = max(0.0, round(sim_req.exact_units, 2))
        if sim_req.start_units <= exact <= end_units:
            unit_values_set.add(exact)

    sorted_units = sorted(unit_values_set)
    points: List[SimulationPoint] = []

    for u in sorted_units:
        point_bills: Dict[str, BillCalculationResponse] = {}
        for uid, tariff in utility_tariffs.items():
            calc = TariffCalculator.calculate_bill(
                tariff=tariff,
                units=u,
                sanctioned_load_kw=sim_req.sanctioned_load_kw,
                apply_subsidy=sim_req.apply_subsidy,
                _compute_savings=False,
            )
            point_bills[uid] = calc

        points.append(SimulationPoint(units=u, bills=point_bills))

    return SimulationResponse(
        points=points,
        utilities_simulated=list(utility_tariffs.keys()),
    )


@app.get("/api/compare", response_model=Dict[str, BillCalculationResponse], tags=["Simulation"])
def compare_utilities(
    units: float = Query(..., ge=0, description="Electricity consumption in units (kWh)"),
    sanctioned_load_kw: float = Query(1.0, gt=0, description="Sanctioned load in kW"),
    apply_subsidy: bool = Query(True, description="Whether to apply state subsidies"),
    year: Optional[int] = Query(None, description="Tariff year"),
):
    """
    Convenient comparison endpoint: Returns the bill calculation for all registered utilities
    for a specific consumption unit and load.
    """
    results: Dict[str, BillCalculationResponse] = {}
    all_uids = registry.get_all_utility_ids()

    for uid in all_uids:
        tariff = registry.get_tariff(uid, year)
        if tariff:
            calc = TariffCalculator.calculate_bill(
                tariff=tariff,
                units=units,
                sanctioned_load_kw=sanctioned_load_kw,
                apply_subsidy=apply_subsidy,
            )
            results[uid] = calc

    return results
