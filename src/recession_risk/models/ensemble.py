from __future__ import annotations

import pandas as pd


class SimpleAverageEnsemble:
    def __init__(self, member_names: list[str], threshold: float = 0.5) -> None:
        self.member_names = member_names
        self.threshold = threshold

    def fit(self, member_frames: list[pd.DataFrame]) -> "SimpleAverageEnsemble":
        if not member_frames:
            raise ValueError("Ensemble requires at least one member frame.")
        return self

    def predict_proba(self, member_frames: list[pd.DataFrame]) -> pd.DataFrame:
        merged = None
        for index, frame in enumerate(member_frames):
            member = frame.loc[:, ["date", "score", "actual", "target_name", "horizon", "split_name", "train_end", "test_start"]].copy()
            member = member.rename(columns={"score": f"score_{index}"})
            if merged is None:
                merged = member
            else:
                merged = merged.merge(
                    member,
                    on=["date", "actual", "target_name", "horizon", "split_name", "train_end", "test_start"],
                    how="inner",
                )
        if merged is None or merged.empty:
            return pd.DataFrame()
        score_columns = [column for column in merged.columns if column.startswith("score_")]
        merged["score"] = merged[score_columns].mean(axis=1)
        merged["signal"] = merged["score"] >= self.threshold
        return merged

    def get_model_summary(self) -> pd.DataFrame:
        weight = 1 / len(self.member_names) if self.member_names else 0.0
        return pd.DataFrame({"member_name": self.member_names, "weight": [weight] * len(self.member_names)})
