"""
    This handles closing of APR_MONITOR. 
    With cleanup code: cancel batch jobs, remove old logs (older than 14 days), and close database connections (no corruption).
"""