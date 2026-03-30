from __future__ import annotations

import numpy as np
import pandas as pd

from recession_risk.models.logistic import SimpleLogisticRegression


class MultivariateLogitModel:
    def __init__(self, feature_names: list[str]) -> None:
        self.feature_names = feature_names
        self.model = SimpleLogisticRegression()

    def fit(self, X, y) -> "MultivariateLogitModel":
        self.model.fit(np.asarray(X, dtype=float), np.asarray(y, dtype=float))
        return self

    def predict_proba(self, X) -> np.ndarray:
        return self.model.predict_proba(np.asarray(X, dtype=float))

    def get_model_summary(self) -> pd.DataFrame:
        coefficients = np.asarray(self.model.coef_, dtype=float)
        return pd.DataFrame(
            {
                "feature": ["intercept", *self.feature_names],
                "coefficient": coefficients,
            }
        )
