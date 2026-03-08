"""Management command to trigger daily challenge generation."""
from django.core.management.base import BaseCommand

from ai.tasks import generate_daily_challenges_task


class Command(BaseCommand):
    help = "Generate daily challenges for students"

    def handle(self, *args, **options):
        result = generate_daily_challenges_task()
        self.stdout.write(self.style.SUCCESS(f"Generated: {result}"))
