import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from app.engine.models import TariffPlan, UtilitySummary


class TariffRegistry:
    """
    Manages loading, storing, and retrieving electricity tariffs by utility and year.
    Modular design allows adding new utilities dynamically or via JSON files.
    """

    def __init__(self, tariffs_dir: Optional[Path] = None):
        if tariffs_dir is None:
            # Default to app/tariffs directory
            self.tariffs_dir = Path(__file__).resolve().parent.parent / "tariffs"
        else:
            self.tariffs_dir = tariffs_dir

        # In-memory storage: (utility_id, year) -> TariffPlan
        self._tariffs: Dict[Tuple[str, int], TariffPlan] = {}
        self.reload_tariffs()

    def reload_tariffs(self) -> int:
        """Loads all tariff JSON definitions from the tariffs directory."""
        self._tariffs.clear()
        if not self.tariffs_dir.exists():
            return 0

        loaded_count = 0
        for file_path in self.tariffs_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    tariff = TariffPlan(**data)
                    self._tariffs[(tariff.utility_id, tariff.year)] = tariff
                    loaded_count += 1
            except Exception as e:
                print(f"Error loading tariff from {file_path}: {e}")

        return loaded_count

    def get_tariff(self, utility_id: str, year: Optional[int] = None) -> Optional[TariffPlan]:
        """
        Retrieves a tariff by utility_id and year.
        If year is not specified, returns the tariff for the latest available year.
        """
        utility_id = utility_id.strip().lower()

        if year is not None:
            return self._tariffs.get((utility_id, year))

        # Find latest year for this utility
        matching = [
            (y, tariff)
            for (uid, y), tariff in self._tariffs.items()
            if uid == utility_id
        ]
        if not matching:
            return None

        # Sort by year descending and return latest
        matching.sort(key=lambda x: x[0], reverse=True)
        return matching[0][1]

    def register_tariff(self, tariff: TariffPlan, persist_to_disk: bool = True) -> TariffPlan:
        """
        Registers a new tariff rule in memory and optionally writes to the tariffs directory.
        """
        key = (tariff.utility_id.strip().lower(), tariff.year)
        self._tariffs[key] = tariff

        if persist_to_disk:
            self.tariffs_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{tariff.utility_id}_{tariff.year}.json"
            target_path = self.tariffs_dir / filename
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(tariff.model_dump(), f, indent=2, ensure_ascii=False)

        return tariff

    def list_utilities(self) -> List[UtilitySummary]:
        """Returns a summarized list of all registered utilities with available years."""
        utilities_map: Dict[str, Dict] = {}

        for (uid, yr), tariff in self._tariffs.items():
            if uid not in utilities_map:
                utilities_map[uid] = {
                    "utility_id": uid,
                    "utility_name": tariff.utility_name,
                    "state": tariff.state,
                    "years": set(),
                    "category": tariff.category,
                    "has_subsidy": tariff.subsidy is not None,
                    "subsidy_name": tariff.subsidy.scheme_name if tariff.subsidy else None,
                }
            utilities_map[uid]["years"].add(yr)

        summaries: List[UtilitySummary] = []
        for uid, info in sorted(utilities_map.items()):
            summaries.append(
                UtilitySummary(
                    utility_id=info["utility_id"],
                    utility_name=info["utility_name"],
                    state=info["state"],
                    available_years=sorted(list(info["years"]), reverse=True),
                    category=info["category"],
                    has_subsidy=info["has_subsidy"],
                    subsidy_name=info["subsidy_name"],
                )
            )

        return summaries

    def get_all_utility_ids(self) -> List[str]:
        """Returns unique list of all utility IDs."""
        return sorted(list(set(uid for (uid, _) in self._tariffs.keys())))


# Global singleton instance for application use
registry = TariffRegistry()
