# ⚡ Open Tariff Engine for Indian Electricity Bills

A modular, standardized tariff calculation and simulation engine for Indian electricity distribution companies (**Discoms**). Built with **Python** and **FastAPI**.

Designed for hackathons, power sector transparency, smart metering, fintech billing platforms, and consumer awareness tools.

---

## 🌟 Key Features

1. **Unit-based Calculation**: Accepts electricity consumption in units (kWh) and sanctioned load (kW).
2. **Standardized Tariff Structure**: Normalizes disparate state tariff orders into a common schema.
3. **Telescopic Slab Rates**: Calculates progressive tiered pricing (e.g., 0–100, 101–200, 201+ units).
4. **Fixed & Demand Charges**: Supports monthly fixed charges (`per_kw_monthly`, `flat_monthly`, or tiered by load).
5. **State Subsidy Modeling**:
   - **Delhi Lifeline Scheme**: 100% waiver for $\le 200$ units, 50% discount for 201–400 units.
   - **Karnataka Gruha Jyothi**: 100% bill waiver for households consuming up to 200 units.
   - **Tamil Nadu TANGEDCO**: Universal 100 free units for all domestic consumers.
6. **Multi-Year Support**: Stores and queries tariff orders categorized by utility and year (e.g., 2023 vs 2024).
7. **Interactive Simulator & What-If Insights**: Real-time slider simulation and threshold warnings (e.g., warning user when saving 10 units drops bill to ₹0).
8. **Cross-Discom Comparison**: Compare bills for the same electricity usage across Delhi, Karnataka, Maharashtra, and Tamil Nadu.
9. **Extensible & Modular**: Add new utilities simply by dropping a JSON file into `app/tariffs/` or via REST API.
10. **Modern Interactive Dashboard**: Dark-mode glassmorphic web dashboard included at `http://localhost:8000`.
11. **RESTful API**: Ready for integration into mobile apps, web portals, or IoT meters.

---

## 📂 Project Structure

```
hack/
├── app/
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── models.py              # Pydantic schemas (TariffPlan, BillCalculation, etc.)
│   │   ├── calculator.py          # Pure calculation engine (slabs, fixed, taxes, subsidies)
│   │   └── registry.py            # Tariff loader & registry (multi-utility & multi-year)
│   ├── tariffs/                   # Sample tariff JSON data stored by utility and year
│   │   ├── bescom_karnataka_2024.json
│   │   ├── bses_delhi_2023.json
│   │   ├── bses_delhi_2024.json
│   │   ├── msedcl_maharashtra_2024.json
│   │   └── tangedco_tamil_nadu_2024.json
│   ├── static/                    # Frontend simulator dashboard
│   │   ├── index.html             # Glassmorphic UI layout
│   │   ├── style.css              # Modern dark-mode styling
│   │   └── app.js                 # Reactive simulation & comparison logic
│   ├── main.py                    # FastAPI application setup & routes
│   └── __init__.py
├── tests/
│   ├── test_engine.py             # Engine unit tests (slabs, fixed, subsidies)
│   └── test_api.py                # FastAPI REST endpoint integration tests
├── requirements.txt               # Dependencies
├── run.py                         # One-click launcher script
└── README.md                      # Documentation
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.9+ (Python 3.10, 3.11, 3.12, 3.13, 3.14 supported).

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Application
```bash
python run.py
```
Or with uvicorn directly:
```bash
uvicorn app.main:app --reload --port 8000
```

Open your browser:
- **Interactive Simulator Dashboard**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🧪 Running Tests

The test suite validates slab calculations, edge cases, fixed charges, government subsidies, and API endpoints:

```bash
python -m pytest -v
```

All 16 tests should pass:
```
tests/test_api.py::test_api_root PASSED
tests/test_api.py::test_api_info PASSED
tests/test_api.py::test_list_utilities PASSED
tests/test_api.py::test_calculate_endpoint PASSED
tests/test_api.py::test_simulate_endpoint PASSED
tests/test_api.py::test_compare_endpoint PASSED
tests/test_engine.py::test_zero_units_consumption PASSED
tests/test_engine.py::test_slab_boundary_calculations PASSED
tests/test_engine.py::test_delhi_lifeline_subsidy PASSED
tests/test_engine.py::test_karnataka_gruha_jyothi_subsidy PASSED
tests/test_engine.py::test_tamil_nadu_100_free_units PASSED
...
```

---

## 📡 REST API Reference

### 1. Calculate Electricity Bill
**Endpoint**: `POST /api/calculate`

**Request Body**:
```json
{
  "utility_id": "bses_delhi",
  "year": 2024,
  "units": 250,
  "sanctioned_load_kw": 1.0,
  "apply_subsidy": true
}
```

**Response**:
```json
{
  "utility_id": "bses_delhi",
  "utility_name": "BSES Rajdhani Power Limited (BRPL)",
  "state": "Delhi",
  "year": 2024,
  "category": "Domestic / Residential (LT-1)",
  "units": 250.0,
  "sanctioned_load_kw": 1.0,
  "energy_charges": 825.0,
  "slab_breakdown": [
    {
      "slab_index": 1,
      "range_description": "0 - 200 units",
      "units_in_slab": 200.0,
      "rate_per_unit": 3.0,
      "amount": 600.0
    },
    {
      "slab_index": 2,
      "range_description": "201 - 400 units",
      "units_in_slab": 50.0,
      "rate_per_unit": 4.5,
      "amount": 225.0
    }
  ],
  "fixed_charges": 40.0,
  "fixed_charge_details": "₹40.00/kW/month (≤2 kW tier) × 1.0 kW",
  "taxes_and_surcharges": [
    { "name": "Electricity Duty", "rate_info": "5.0% on Energy Charges", "amount": 41.25 },
    { "name": "Regulatory Surcharge", "rate_info": "8.0% on (Energy + Fixed)", "amount": 69.2 },
    { "name": "Pension Trust Surcharge", "rate_info": "5.0% on (Energy + Fixed)", "amount": 43.25 }
  ],
  "total_taxes_and_surcharges": 153.7,
  "gross_amount": 1018.7,
  "subsidy_applied": true,
  "subsidy_name": "Delhi DERC Lifeline Subsidy Scheme",
  "subsidy_amount": 412.5,
  "subsidy_details": "50% Subsidy on Energy Charges for consumption between 201-400 units (Saved ₹412.50).",
  "net_payable": 606.2,
  "effective_rate_per_unit": 2.42,
  "currency": "₹"
}
```

---

### 2. Simulate Consumption Range
**Endpoint**: `POST /api/simulate`

**Request Body**:
```json
{
  "utility_ids": ["bses_delhi", "bescom_karnataka"],
  "start_units": 0,
  "end_units": 300,
  "step": 100,
  "sanctioned_load_kw": 1.0,
  "apply_subsidy": true
}
```

---

### 3. Cross-Discom Instant Comparison
**Endpoint**: `GET /api/compare?units=250&sanctioned_load_kw=1.0&apply_subsidy=true`

Returns the bill breakdown for all registered Discoms simultaneously for side-by-side comparison.

---

### 4. List All Utilities
**Endpoint**: `GET /api/utilities`

Returns list of all available electricity boards, their states, categories, and available tariff years.

---

### 5. Register a New Utility Tariff
**Endpoint**: `POST /api/tariffs`

Add any electricity utility dynamically via REST API.

---

## ➕ Adding a New Electricity Utility

Adding a new utility is completely modular:

### Option A: Create a JSON file in `app/tariffs/`
Create a file named `<utility_id>_<year>.json` (e.g., `pvvnl_up_2024.json`):

```json
{
  "utility_id": "pvvnl_up",
  "utility_name": "Paschimanchal Vidyut Vitran Nigam Ltd",
  "state": "Uttar Pradesh",
  "year": 2024,
  "category": "Domestic (LMV-1)",
  "fixed_charges": {
    "charge_type": "per_kw_monthly",
    "rate": 110.0
  },
  "slabs": [
    { "from_units": 0, "to_units": 150, "rate_per_unit": 5.50 },
    { "from_units": 151, "to_units": 300, "rate_per_unit": 6.00 },
    { "from_units": 301, "to_units": null, "rate_per_unit": 7.00 }
  ],
  "taxes_and_surcharges": {
    "electricity_duty_pct": 5.0,
    "fpppa_rate_per_unit": 0.0,
    "regulatory_surcharge_pct": 0.0,
    "pension_surcharge_pct": 0.0
  },
  "subsidy": null
}
```
Restart the server or call `registry.reload_tariffs()`. The engine picks it up automatically!

### Option B: Use the REST API
Send a `POST` request to `/api/tariffs` with the JSON payload.

---

## 💡 Demonstration Utilities Included

| Utility ID | Utility Name | State | Key Features / Subsidies |
| :--- | :--- | :--- | :--- |
| `bses_delhi` | BSES Rajdhani (BRPL) | Delhi | Multi-tier slabs, 100% free under 200 units, 50% discount under 400 units, DERC regulatory & pension surcharges |
| `bescom_karnataka` | BESCOM | Karnataka | Simplified 2-tier slabs, Gruha Jyothi scheme (100% bill waiver up to 200 units), FPPPA surcharge |
| `msedcl_maharashtra` | Mahavitaran (MSEDCL) | Maharashtra | 4-tier progressive slabs, flat fixed charge, 16% electricity duty, FAC surcharge |
| `tangedco_tamil_nadu` | TANGEDCO | Tamil Nadu | 100 units universal free tier (₹0/unit), progressive slabs up to 500+ units |

---

## 📜 License
MIT License. Open for hackathons and research.
