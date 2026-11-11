import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_root():
    """Test health check / UI endpoint."""
    res = client.get("/")
    assert res.status_code == 200


def test_api_info():
    """Test API metadata endpoint."""
    res = client.get("/api")
    assert res.status_code == 200
    data = res.json()
    assert "utilities_count" in data
    assert data["version"] == "1.0.0"


def test_list_utilities():
    """Test listing all utilities and check for core Indian utilities."""
    res = client.get("/api/utilities")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 4

    utility_ids = [u["utility_id"] for u in data]
    assert "bses_delhi" in utility_ids
    assert "bescom_karnataka" in utility_ids
    assert "msedcl_maharashtra" in utility_ids
    assert "tangedco_tamil_nadu" in utility_ids


def test_get_tariff_success():
    """Test retrieving tariff rules for BSES Delhi."""
    res = client.get("/api/tariffs/bses_delhi")
    assert res.status_code == 200
    data = res.json()
    assert data["utility_id"] == "bses_delhi"
    assert len(data["slabs"]) > 0
    assert "fixed_charges" in data


def test_get_tariff_not_found():
    """Test 404 on nonexistent utility."""
    res = client.get("/api/tariffs/nonexistent_discom")
    assert res.status_code == 404


def test_calculate_endpoint():
    """Test POST /api/calculate with 250 units."""
    payload = {
        "utility_id": "bses_delhi",
        "units": 250,
        "sanctioned_load_kw": 1.0,
        "apply_subsidy": True,
    }
    res = client.post("/api/calculate", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["utility_id"] == "bses_delhi"
    assert data["units"] == 250.0
    assert data["net_payable"] > 0
    assert data["energy_charges"] > 0
    assert len(data["slab_breakdown"]) > 0


def test_simulate_endpoint():
    """Test POST /api/simulate for ranges 0 to 200 in steps of 50."""
    payload = {
        "utility_ids": ["bses_delhi", "bescom_karnataka"],
        "start_units": 0,
        "end_units": 200,
        "step": 50,
        "sanctioned_load_kw": 1.0,
        "apply_subsidy": True,
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "points" in data
    assert len(data["points"]) == 5  # 0, 50, 100, 150, 200
    first_pt = data["points"][0]
    assert first_pt["units"] == 0.0
    assert "bses_delhi" in first_pt["bills"]
    assert "bescom_karnataka" in first_pt["bills"]


def test_compare_endpoint():
    """Test GET /api/compare across utilities."""
    res = client.get("/api/compare?units=200&sanctioned_load_kw=1.0&apply_subsidy=true")
    assert res.status_code == 200
    data = res.json()

    assert "bses_delhi" in data
    assert "bescom_karnataka" in data
    assert "msedcl_maharashtra" in data
    assert "tangedco_tamil_nadu" in data


def test_register_tariff_endpoint():
    """Test POST /api/tariffs to dynamically add a new tariff."""
    new_tariff = {
        "utility_id": "kseb_kerala",
        "utility_name": "Kerala State Electricity Board (KSEB)",
        "state": "Kerala",
        "year": 2024,
        "category": "Domestic LT-1A",
        "fixed_charges": {
            "charge_type": "flat_monthly",
            "rate": 70.0,
            "min_charge": 70.0
        },
        "slabs": [
            {
                "from_units": 0,
                "to_units": 50,
                "rate_per_unit": 3.50
            },
            {
                "from_units": 51,
                "to_units": 100,
                "rate_per_unit": 4.20
            }
        ],
        "taxes_and_surcharges": {
            "electricity_duty_pct": 10.0,
            "fpppa_rate_per_unit": 0.0,
            "regulatory_surcharge_pct": 0.0,
            "pension_surcharge_pct": 0.0
        },
        "subsidy": None
    }

    res = client.post("/api/tariffs?persist=false", json=new_tariff)
    assert res.status_code == 201
    data = res.json()
    assert data["utility_id"] == "kseb_kerala"

    # Verify calculation works on newly registered utility
    calc_res = client.post("/api/calculate", json={"utility_id": "kseb_kerala", "units": 75})
    assert calc_res.status_code == 200
    assert calc_res.json()["utility_id"] == "kseb_kerala"
