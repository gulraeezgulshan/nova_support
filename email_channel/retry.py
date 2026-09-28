"""Send again the e-mails that gave up, e.g. after fixing a blocked or misconfigured sender.

Usage (repo root, or a Railway shell on the worker):
    python -m email_channel.retry

The worker's outbox flush (every 30 s) then sends them with the configured sender.
"""

from email_channel.tasks import retry_failed

if __name__ == "__main__":
    print(f"{retry_failed()} failed e-mail(s) queued again.")
