import pandas as pd
import numpy as np
from sklearn.impute import KNNImputer
from typing import Dict, List, Tuple

def impute_missing(df, method="Mean"):
    df_copy = df.copy()
    numeric_cols = df_copy.select_dtypes(include=np.number).columns

    if method == "Mean":
        for col in numeric_cols:
            mean_val = df_copy[col].mean()
            df_copy[col] = df_copy[col].fillna(mean_val)
    elif method == "Median":
        for col in numeric_cols:
            median_val = df_copy[col].median()
            df_copy[col] = df_copy[col].fillna(median_val)
    elif method == "KNN":
        imputer = KNNImputer(n_neighbors=3)
        df_copy[numeric_cols] = imputer.fit_transform(df_copy[numeric_cols])
    return df_copy

def detect_outliers(df, method="IQR"):
    df_num = df.select_dtypes(include=np.number)
    if method == "IQR":
        Q1 = df_num.quantile(0.25)
        Q3 = df_num.quantile(0.75)
        IQR = Q3 - Q1
        outliers = ((df_num < (Q1 - 1.5 * IQR)) | (df_num > (Q3 + 1.5 * IQR)))
        return outliers.any(axis=1)
    elif method == "Z-score":
        from scipy import stats
        z_scores = np.abs(stats.zscore(df_num, nan_policy='omit'))
        return (z_scores > 3).any(axis=1)
    elif method == "Winsorize":
        # Mark rows where any numeric col is beyond 1st/99th percentile
        lower = df_num.quantile(0.01)
        upper = df_num.quantile(0.99)
        mask_lower = (df_num.lt(lower, axis=1)).any(axis=1)
        mask_upper = (df_num.gt(upper, axis=1)).any(axis=1)
        return mask_lower | mask_upper
    else:
        return pd.Series([False]*len(df))

def remove_outliers(df, outliers):
    return df.loc[~outliers]


def winsorize_values(df, limits: Tuple[float, float] = (0.01, 0.99)):
    """Clamp numeric values to given lower/upper quantiles.
    Returns a new DataFrame.
    """
    df_copy = df.copy()
    num_cols = df_copy.select_dtypes(include=np.number).columns
    lowers = df_copy[num_cols].quantile(limits[0])
    uppers = df_copy[num_cols].quantile(limits[1])
    for c in num_cols:
        df_copy[c] = df_copy[c].clip(lower=lowers[c], upper=uppers[c])
    return df_copy


def validate_rules(df, rules: Dict[str, Dict]) -> List[str]:
    """Apply simple rule-based validation.
    rules format example:
    {
      "age": {"min": 0, "max": 120},
      "income": {"min": 0},
      "skip_if": [{"if": {"has_tv": 0}, "then_blank": ["tv_brand"]}]
    }
    Returns list of violation messages.
    """
    logs: List[str] = []
    # range checks
    for col, spec in rules.items():
        if col in df.columns:
            if isinstance(spec, dict):
                if 'min' in spec:
                    bad = df[col].dropna() < spec['min']
                    count = int(bad.sum())
                    if count:
                        logs.append(f"{col}: {count} values below {spec['min']}")
                if 'max' in spec:
                    bad = df[col].dropna() > spec['max']
                    count = int(bad.sum())
                    if count:
                        logs.append(f"{col}: {count} values above {spec['max']}")
    # skip pattern checks
    for spec in rules.get('skip_if', []):
        cond = spec.get('if', {})
        then_blank = spec.get('then_blank', [])
        if cond and then_blank:
            col, val = next(iter(cond.items()))
            if col in df.columns:
                mask = df[col] == val
                for target in then_blank:
                    if target in df.columns:
                        violations = df.loc[mask, target].notna().sum()
                        if violations:
                            logs.append(f"{target}: {violations} should be blank when {col} == {val}")
    return logs
