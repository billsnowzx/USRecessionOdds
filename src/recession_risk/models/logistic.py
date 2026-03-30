from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit


class SimpleLogisticRegression:
    def __init__(self, l2_penalty: float = 1e-6, maxiter: int = 500) -> None:
        self.l2_penalty = l2_penalty
        self.maxiter = maxiter
        self.coef_: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "SimpleLogisticRegression":
        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(-1, 1)

        design = np.column_stack([np.ones(len(X_arr)), X_arr])

        def objective(beta: np.ndarray) -> float:
            logits = design @ beta
            probs = np.clip(expit(logits), 1e-8, 1 - 1e-8)
            neg_log_likelihood = -(y_arr * np.log(probs) + (1 - y_arr) * np.log(1 - probs)).mean()
            penalty = 0.5 * self.l2_penalty * np.square(beta[1:]).sum()
            return float(neg_log_likelihood + penalty)

        result = minimize(
            objective,
            x0=np.zeros(design.shape[1], dtype=float),
            method="BFGS",
            options={"maxiter": self.maxiter},
        )
        if not result.success:
            raise RuntimeError(f"Logistic regression failed to converge: {result.message}")

        self.coef_ = result.x
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("Model must be fit before prediction.")
        X_arr = np.asarray(X, dtype=float)
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(-1, 1)
        design = np.column_stack([np.ones(len(X_arr)), X_arr])
        probs = expit(design @ self.coef_)
        return np.column_stack([1 - probs, probs])
