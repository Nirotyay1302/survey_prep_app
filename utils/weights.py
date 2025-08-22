import pandas as pd
import numpy as np

def apply_weights(df, weight_col):
    if weight_col not in df.columns:
        raise ValueError(f"Weight column '{weight_col}' not found in data.")
    df_copy = df.copy()
    df_copy['weight'] = df_copy[weight_col]
    return df_copy

def compute_weighted_summary(df, value_col, weight_col='weight'):
    if value_col not in df.columns or weight_col not in df.columns:
        raise ValueError("Value or weight column missing.")
    
    d = df.dropna(subset=[value_col, weight_col])
    weights = d[weight_col]
    values = d[value_col]

    weighted_mean = np.average(values, weights=weights)
    weighted_var = np.average((values - weighted_mean)**2, weights=weights)
    weighted_se = np.sqrt(weighted_var) / np.sqrt(len(values))

    margin_of_error = 1.96 * weighted_se

    return {
        'weighted_mean': weighted_mean,
        'margin_of_error': margin_of_error
    }
