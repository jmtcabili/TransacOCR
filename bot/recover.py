import asyncio

from app import recover_stuck

# Run from cron. Note: importing app runs its module-level code (init_db, env vars).
asyncio.run(recover_stuck())
