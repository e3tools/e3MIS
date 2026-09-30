import time

from django.core.management.base import BaseCommand

from fieldmonitoring.core.jobs import run_due_jobs


class Command(BaseCommand):
    help = "Run scheduled jobs that are due. Use --loop to keep running (scheduler container)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=int, default=60)

    def handle(self, *args, loop=False, interval=60, **options):
        while True:
            result = run_due_jobs()
            ran = {k: v for k, v in result.items() if v is not None}
            if ran:
                self.stdout.write(f"ran: {ran}")
            if not loop:
                return
            time.sleep(interval)
