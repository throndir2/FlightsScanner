"""Dev helper to enqueue a refresh for a single alert from the CLI.

Usage (inside the worker/backend container)::

    python -m app.workers.dev_enqueue <alert_id>
"""

from __future__ import annotations

import sys

from app.workers.tasks import refresh_alert


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m app.workers.dev_enqueue <alert_id>", file=sys.stderr)
        raise SystemExit(2)

    alert_id = sys.argv[1]
    async_result = refresh_alert.delay(alert_id)
    print(f"Enqueued refresh_alert({alert_id}) -> task {async_result.id}")


if __name__ == "__main__":
    main()
