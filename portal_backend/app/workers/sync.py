"""
Deprecated: The Redis-based sync worker has been replaced by the cron job
at app.cron.onboard_students.

Run the cron job directly:
    python -m app.cron.onboard_students
"""

from app.cron.onboard_students import main, run_onboard_cron

__all__ = ["main", "run_onboard_cron"]

if __name__ == "__main__":
    main()
