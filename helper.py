import numpy as np

def get_dwell_times(df, tc_column, threshold=0.1, min_minutes=10):
    # 1. Calculate rate of change (Degrees per Minute)
    # We use .diff() and divide by the time step
    temp_diff = df[tc_column].diff()
    time_diff = df["Minutes"].diff()
    slope = (temp_diff / time_diff).abs()

    # 2. Identify stable points
    is_flat = slope < threshold
    
    # 3. Group consecutive stable points into unique IDs
    # This increments the ID every time the 'is_flat' status changes
    df['group'] = (is_flat != is_flat.shift()).cumsum()
    
    # 4. Filter only for groups that are 'flat'
    dwells = df[is_flat].groupby('group').agg(
        start_time=('Minutes', 'min'),
        end_time=('Minutes', 'max'),
        avg_temp=(tc_column, 'mean'),
        duration=('Minutes', lambda x: x.max() - x.min())
    )
    
    # 5. Remove short-lived noise
    return dwells[dwells['duration'] >= min_minutes]