from __future__ import annotations

import numpy as np
import pandas as pd

from recession_risk.models.logistic import SimpleLogisticRegression


class PlattCalibrator:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.model: SimpleLogisticRegression | None = None
        self.status = "disabled" if not enabled else "unfit"

    def fit(self, raw_scores, y_true) -> "PlattCalibrator":
        raw = np.asarray(raw_scores, dtype=float)
        y = np.asarray(y_true, dtype=float)
        if not self.enabled:
            self.status = "disabled"
            return self
        if len(raw) == 0 or len(np.unique(y)) < 2:
            self.status = "identity_insufficient_classes"
            return self
        self.model = SimpleLogisticRegression(l2_penalty=1e-6, maxiter=500).fit(raw.reshape(-1, 1), y)
        self.status = "platt"
        return self

    def predict(self, raw_scores) -> np.ndarray:
        raw = np.asarray(raw_scores, dtype=float)
        if self.model is None:
            return np.clip(raw, 0.0, 1.0)
        return self.model.predict_proba(raw.reshape(-1, 1))[:, 1]

    def get_summary(self) -> pd.DataFrame:
        rows: list[dict[str, object]] = [{"feature": "calibration_status", "coefficient": self.status}]
        if self.model is not None and self.model.coef_ is not None:
            rows.extend(
                [
                    {"feature": "calibration_intercept", "coefficient": float(self.model.coef_[0])},
                    {"feature": "calibration_slope", "coefficient": float(self.model.coef_[1])},
                ]
            )
        return pd.DataFrame(rows)
