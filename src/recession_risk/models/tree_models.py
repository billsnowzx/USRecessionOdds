from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import GradientBoostingClassifier
except ImportError:  # pragma: no cover - optional dependency path
    GradientBoostingClassifier = None


class GradientBoostingRecessionModel:
    def __init__(
        self,
        feature_names: list[str],
        n_estimators: int = 100,
        learning_rate: float = 0.05,
        max_depth: int = 2,
        random_state: int = 42,
    ) -> None:
        self.feature_names = feature_names
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.random_state = random_state
        self.model: GradientBoostingClassifier | None = None

    def fit(self, X, y) -> "GradientBoostingRecessionModel":
        if GradientBoostingClassifier is None:
            raise RuntimeError("Tree models require scikit-learn. Install with `pip install -e .[ml]`.")
        self.model = GradientBoostingClassifier(
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            max_depth=self.max_depth,
            random_state=self.random_state,
        )
        self.model.fit(np.asarray(X, dtype=float), np.asarray(y, dtype=float))
        return self

    def predict_proba(self, X) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model must be fit before prediction.")
        return self.model.predict_proba(np.asarray(X, dtype=float))

    def get_model_summary(self) -> pd.DataFrame:
        if self.model is None:
            raise RuntimeError("Model must be fit before summary.")
        return pd.DataFrame(
            {
                "feature": self.feature_names,
                "importance": self.model.feature_importances_,
            }
        )
