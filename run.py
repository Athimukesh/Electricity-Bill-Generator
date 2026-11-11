"""
Convenient runner script for the Open Tariff Engine.
Usage: python run.py
"""
import sys
import uvicorn

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print("=" * 65)
    print("[*] Starting Open Tariff Engine for Indian Electricity Bills")
    print("[*] Dashboard UI : http://localhost:8000")
    print("[*] API Docs (Swagger): http://localhost:8000/docs")
    print("=" * 65)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

