from __future__ import annotations

import numpy as np
import pandas as pd

from recession_risk.models.logistic import SimpleLogisticRegression


class MultivariateLogitModel:
    def __init__(self, feature_names: list[str]) -> None:
        self.feature_names = feature_names
        self.model = SimpleLogisticRegression()
        self.feature_means_: np.ndarray | None = None
        self.feature_scales_: np.ndarray | None = None

    def fit(self, X, y) -> "MultivariateLogitModel":
        X_arr = np.asarray(X, dtype=float)
        self.feature_means_ = X_arr.mean(axis=0)
        self.feature_scales_ = X_arr.std(axis=0)
        self.feature_scales_[self.feature_scales_ == 0.0] = 1.0
        standardized = (X_arr - self.feature_means_) / self.feature_scales_
        self.model.fit(standardized, np.asarray(y, dtype=float))
        return self

    def predict_proba(self, X) -> np.ndarray:
        if self.feature_means_ is None or self.feature_scales_ is None:
            raise RuntimeError("Model must be fit before prediction.")
        X_arr = np.asarray(X, dtype=float)
        standardized = (X_arr - self.feature_means_) / self.feature_scales_
        return self.model.predict_proba(standardized)

    def get_model_summary(self) -> pd.DataFrame:
        coefficients = np.asarray(self.model.coef_, dtype=float)
        return pd.DataFrame(
            {
                "feature": ["intercept", *self.feature_names],
                "coefficient": coefficients,
            }
        )
