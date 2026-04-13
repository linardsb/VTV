# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Lightweight JSON-based model registry for ML artifact versioning (ML-2.2).

Tracks model versions, metrics, and production pointers. Artifacts stored
as joblib files; metadata stored in a committed JSON registry file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import joblib

from app.core.logging import get_logger
from app.ml.models.schemas import ModelMetadata, TrainingMetrics

logger = get_logger(__name__)

_DEFAULT_REGISTRY_PATH = Path("models/registry.json")


class ModelRegistry:
    """JSON-backed model version registry with atomic writes.

    Args:
        registry_path: Path to the registry JSON file.
    """

    def __init__(self, registry_path: Path = _DEFAULT_REGISTRY_PATH) -> None:
        self._path = registry_path
        self._data = self._load()
        self._cache: dict[str, tuple[Any, ModelMetadata]] = {}

    def _load(self) -> dict[str, Any]:
        """Load registry JSON from disk."""
        if not self._path.exists():
            return {"models": {}}
        with self._path.open() as f:
            result: dict[str, Any] = json.load(f)
            return result

    def _save(self) -> None:
        """Write registry JSON atomically (write to tmp, rename)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path_str = tempfile.mkstemp(
            dir=str(self._path.parent),
            suffix=".json.tmp",
        )
        tmp = Path(tmp_path_str)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self._data, f, indent=2)
                f.write("\n")
            tmp.replace(self._path)
        except BaseException:
            if tmp.exists():
                tmp.unlink()
            raise

    def register(
        self,
        name: str,
        version: int,
        metadata: ModelMetadata,
        artifact_path: Path,
    ) -> None:
        """Register a trained model version in the registry.

        Args:
            name: Model name (e.g., "eta_gbm").
            version: Integer version number.
            metadata: Training metadata and metrics.
            artifact_path: Path to the serialized model artifact.
        """
        models: dict[str, Any] = self._data.setdefault("models", {})
        model_entry: dict[str, Any] = models.setdefault(name, {"versions": {}})
        versions: dict[str, Any] = model_entry.setdefault("versions", {})

        versions[str(version)] = {
            "trained_at": metadata.trained_at,
            "training_window_days": metadata.training_window_days,
            "training_rows": metadata.training_rows,
            "feature_version": metadata.feature_version,
            "metrics": {
                "mae": metadata.metrics.mae,
                "rmse": metadata.metrics.rmse,
                "p90_error": metadata.metrics.p90_error,
                "per_route_mae": metadata.metrics.per_route_mae,
            },
            "artifact": str(artifact_path),
        }
        self._save()

        logger.info(
            "ml.registry.model_registered",
            model_name=name,
            version=version,
            mae=metadata.metrics.mae,
            artifact=str(artifact_path),
        )

    def load_latest(self, name: str) -> tuple[Any, ModelMetadata]:
        """Load the most recent version of a model.

        Args:
            name: Model name.

        Returns:
            Tuple of (loaded model object, metadata).

        Raises:
            KeyError: If no versions exist for the model name.
        """
        models: dict[str, Any] = self._data.get("models", {})
        if name not in models:
            msg = f"No model registered with name '{name}'"
            raise KeyError(msg)

        versions: dict[str, Any] = models[name].get("versions", {})
        if not versions:
            msg = f"No versions found for model '{name}'"
            raise KeyError(msg)

        latest_ver = str(max(int(v) for v in versions))
        return self._load_version(name, latest_ver)

    def promote(self, name: str, version: int) -> None:
        """Set the production pointer for a model.

        Args:
            name: Model name.
            version: Version number to promote.

        Raises:
            KeyError: If the model or version doesn't exist.
        """
        models: dict[str, Any] = self._data.get("models", {})
        if name not in models:
            msg = f"No model registered with name '{name}'"
            raise KeyError(msg)

        versions: dict[str, Any] = models[name].get("versions", {})
        if str(version) not in versions:
            msg = f"Version {version} not found for model '{name}'"
            raise KeyError(msg)

        models[name]["production"] = version
        self._save()

        logger.info(
            "ml.registry.model_promoted",
            model_name=name,
            version=version,
        )

    def get_production(self, name: str) -> tuple[Any, ModelMetadata] | None:
        """Load the production version of a model.

        Args:
            name: Model name.

        Returns:
            Tuple of (loaded model, metadata), or None if no production version set.
        """
        models: dict[str, Any] = self._data.get("models", {})
        if name not in models:
            return None

        prod_version = models[name].get("production")
        if prod_version is None:
            return None

        return self._load_version(name, str(prod_version))

    def rollback(self, name: str) -> None:
        """Remove the production pointer for a model.

        Args:
            name: Model name.

        Raises:
            KeyError: If the model doesn't exist.
        """
        models: dict[str, Any] = self._data.get("models", {})
        if name not in models:
            msg = f"No model registered with name '{name}'"
            raise KeyError(msg)

        models[name].pop("production", None)
        self._save()

        logger.info(
            "ml.registry.model_rolled_back",
            model_name=name,
        )

    def _load_version(self, name: str, version_str: str) -> tuple[Any, ModelMetadata]:
        """Load a specific model version from disk.

        Args:
            name: Model name.
            version_str: Version number as string.

        Returns:
            Tuple of (loaded model object, metadata).
        """
        cache_key = f"{name}:{version_str}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        version_data: dict[str, Any] = self._data["models"][name]["versions"][version_str]
        artifact_path = Path(version_data["artifact"])
        model = joblib.load(artifact_path)

        metrics_data: dict[str, Any] = version_data["metrics"]
        metrics = TrainingMetrics(
            mae=float(metrics_data["mae"]),
            rmse=float(metrics_data["rmse"]),
            p90_error=float(metrics_data["p90_error"]),
            per_route_mae={str(k): float(v) for k, v in metrics_data["per_route_mae"].items()},
        )
        metadata = ModelMetadata(
            version=int(version_str),
            model_name=name,
            trained_at=str(version_data["trained_at"]),
            training_window_days=int(version_data["training_window_days"]),
            training_rows=int(version_data["training_rows"]),
            feature_version=str(version_data["feature_version"]),
            metrics=metrics,
        )

        # Check feature version mismatch
        if metadata.feature_version != "ml-2.1-v1":
            logger.warning(
                "ml.registry.feature_version_mismatch",
                model_name=name,
                version=int(version_str),
                expected="ml-2.1-v1",
                actual=metadata.feature_version,
            )

        self._cache[cache_key] = (model, metadata)

        logger.info(
            "ml.registry.model_loaded",
            model_name=name,
            version=int(version_str),
        )
        return model, metadata

    def next_version(self, name: str) -> int:
        """Get the next version number for a model.

        Args:
            name: Model name.

        Returns:
            Next integer version (1 if no versions exist).
        """
        models: dict[str, Any] = self._data.get("models", {})
        if name not in models:
            return 1
        versions: dict[str, Any] = models[name].get("versions", {})
        if not versions:
            return 1
        return max(int(v) for v in versions) + 1
