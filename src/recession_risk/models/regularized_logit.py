from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.special import expit


class RegularizedLogitModel:
    def __init__(
        self,
        feature_names: list[str],
        penalty: str = "elasticnet",
        alpha: float = 0.1,
        l1_ratio: float = 0.5,
        learning_rate: float = 0.1,
        max_iter: int = 2000,
        tolerance: float = 1e-6,
    ) -> None:
        self.feature_names = feature_names
        self.penalty = penalty
        self.alpha = alpha
        self.l1_ratio = l1_ratio if penalty == "elasticnet" else 1.0
        self.learning_rate = learning_rate
        self.max_iter = max_iter
        self.tolerance = tolerance
        self.intercept_: float = 0.0
        self.coef_: np.ndarray | None = None
        self.feature_means_: np.ndarray | None = None
        self.feature_scales_: np.ndarray | None = None

    def fit(self, X, y) -> "RegularizedLogitModel":
        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        self.feature_means_ = X_arr.mean(axis=0)
        self.feature_scales_ = X_arr.std(axis=0)
        self.feature_scales_[self.feature_scales_ == 0.0] = 1.0
        standardized = (X_arr - self.feature_means_) / self.feature_scales_

        coefficients = np.zeros(standardized.shape[1], dtype=float)
        intercept = 0.0
        previous_loss = float("inf")

        for _ in range(self.max_iter):
            logits = intercept + standardized @ coefficients
            probabilities = expit(logits)
            errors = probabilities - y_arr

            intercept -= self.learning_rate * errors.mean()
            gradient = standardized.T @ errors / len(standardized)
            gradient += self.alpha * (1 - self.l1_ratio) * coefficients
            candidate = coefficients - self.learning_rate * gradient
            threshold = self.learning_rate * self.alpha * self.l1_ratio
            coefficients = np.sign(candidate) * np.maximum(np.abs(candidate) - threshold, 0.0)

            loss = self._objective(standardized, y_arr, intercept, coefficients)
            if abs(previous_loss - loss) <= self.tolerance:
                break
            previous_loss = loss

        self.intercept_ = float(intercept)
        self.coef_ = coefficients
        return self

    def predict_proba(self, X) -> np.ndarray:
        if self.coef_ is None or self.feature_means_ is None or self.feature_scales_ is None:
            raise RuntimeError("Model must be fit before prediction.")
        X_arr = np.asarray(X, dtype=float)
        standardized = (X_arr - self.feature_means_) / self.feature_scales_
        probabilities = expit(self.intercept_ + standardized @ self.coef_)
        return np.column_stack([1 - probabilities, probabilities])

    def get_model_summary(self) -> pd.DataFrame:
        if self.coef_ is None:
            raise RuntimeError("Model must be fit before summary.")
        return pd.DataFrame(
            {
                "feature": ["intercept", *self.feature_names],
                "coefficient": [self.intercept_, *self.coef_.tolist()],
                "selected": [True, *[bool(abs(value) > 1e-8) for value in self.coef_]],
            }
        )

    def _objective(self, X, y, intercept: float, coefficients: np.ndarray) -> float:
        probabilities = np.clip(expit(intercept + X @ coefficients), 1e-8, 1 - 1e-8)
        loss = -(y * np.log(probabilities) + (1 - y) * np.log(1 - probabilities)).mean()
        l1 = self.alpha * self.l1_ratio * np.abs(coefficients).sum()
        l2 = 0.5 * self.alpha * (1 - self.l1_ratio) * np.square(coefficients).sum()
        return float(loss + l1 + l2)
