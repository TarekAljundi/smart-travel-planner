# backend/ml/train.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_validate, RandomizedSearchCV
from sklearn.metrics import classification_report
from imblearn.pipeline import Pipeline
from imblearn.over_sampling import SMOTE
import joblib
import os
from app.config import get_settings

settings = get_settings()

# ---------- 1. Load dataset ----------
input_path = "data/destinations.csv"
df = pd.read_csv(input_path)
print(f"Loaded {len(df)} rows from {input_path}")

target = "label"
features = [col for col in df.columns if col not in (target, "destination")]

categorical_cols = ["continent"]
numeric_cols = [col for col in features if col not in categorical_cols]

print(f"Numeric features: {numeric_cols}")
print(f"Categorical features: {categorical_cols}")

# ---------- 2. Remove classes with fewer than 2 samples (SMOTE requirement) ----------
class_counts = df[target].value_counts()
rare_classes = class_counts[class_counts < 2].index.tolist()
if rare_classes:
    print(f"Dropping classes with <2 samples: {rare_classes}")
    df = df[~df[target].isin(rare_classes)]

X = df[features]
y = df[target]
print(f"Training set size after filtering: {len(X)}")
print("Final class distribution:\n", y.value_counts())

# ---------- 3. Preprocessing ----------
numeric_transformer = Pipeline(steps=[
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler()),
])

categorical_transformer = Pipeline(steps=[
    ("imputer", SimpleImputer(strategy="most_frequent")),
    ("onehot", OneHotEncoder(handle_unknown="ignore")),
])

preprocessor = ColumnTransformer(transformers=[
    ("num", numeric_transformer, numeric_cols),
    ("cat", categorical_transformer, categorical_cols),
])

# ---------- 4. Full pipeline with SMOTE (now safe because every class has ≥2 samples) ----------
base_clf = RandomForestClassifier(random_state=42, class_weight="balanced")

pipeline = Pipeline([
    ("prep", preprocessor),
    ("smote", SMOTE(random_state=42, k_neighbors=1)),   # safe for 2‑sample classes
    ("clf", base_clf),
])

# ---------- 5. Cross‑validation ----------
cv_scores = cross_validate(
    pipeline, X, y,
    cv=5,
    scoring=["accuracy", "f1_macro"],
    return_train_score=False,
)
print(f"Baseline (RF + SMOTE): accuracy={cv_scores['test_accuracy'].mean():.3f} ± {cv_scores['test_accuracy'].std():.3f}, "
      f"F1 macro={cv_scores['test_f1_macro'].mean():.3f} ± {cv_scores['test_f1_macro'].std():.3f}")

# ---------- 6. Compare classifiers ----------
models = {
    "LogisticRegression": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
    "RandomForest": RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42),
    "GradientBoosting": GradientBoostingClassifier(n_estimators=100, random_state=42),
}

results = []
for name, clf in models.items():
    pipe = Pipeline([
        ("prep", preprocessor),
        ("smote", SMOTE(random_state=42, k_neighbors=1)),
        ("clf", clf),
    ])
    scores = cross_validate(pipe, X, y, cv=5, scoring=["accuracy", "f1_macro"])
    results.append({
        "model": name,
        "accuracy_mean": scores["test_accuracy"].mean(),
        "accuracy_std": scores["test_accuracy"].std(),
        "f1_macro_mean": scores["test_f1_macro"].mean(),
        "f1_macro_std": scores["test_f1_macro"].std(),
    })
    print(f"{name}: acc={scores['test_accuracy'].mean():.3f} ± {scores['test_accuracy'].std():.3f}, "
          f"F1={scores['test_f1_macro'].mean():.3f} ± {scores['test_f1_macro'].std():.3f}")

os.makedirs("pipeline", exist_ok=True)
pd.DataFrame(results).to_csv("pipeline/results.csv", index=False)
print("Results saved to pipeline/results.csv")

# ---------- 7. Tune Random Forest ----------
print("\nTuning Random Forest...")
param_dist = {
    "clf__n_estimators": [100, 200, 300],
    "clf__max_depth": [None, 10, 20, 30],
    "clf__min_samples_split": [2, 5, 10],
    "clf__min_samples_leaf": [1, 2, 4],
}

tune_pipe = Pipeline([
    ("prep", preprocessor),
    ("smote", SMOTE(random_state=42, k_neighbors=1)),
    ("clf", RandomForestClassifier(random_state=42, class_weight="balanced")),
])

random_search = RandomizedSearchCV(
    tune_pipe,
    param_distributions=param_dist,
    n_iter=20,
    cv=5,
    scoring="f1_macro",
    random_state=42,
    n_jobs=-1,
    verbose=1,
)
random_search.fit(X, y)
print(f"Best parameters: {random_search.best_params_}")
print(f"Best F1 macro: {random_search.best_score_:.3f}")

best_model = random_search.best_estimator_

# ---------- 8. Full evaluation ----------
y_pred = best_model.predict(X)
print("\nClassification report on training data (with SMOTE):")
print(classification_report(y, y_pred, zero_division=0))

# ---------- 9. Save ----------
output_path = settings.ml_model_path
joblib.dump(best_model, output_path)
print(f"Best model saved to {output_path}")