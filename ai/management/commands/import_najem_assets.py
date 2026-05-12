"""Import external Najem Aslan AI assets into backend paths."""
from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ai.models import AIModelWeight


class Command(BaseCommand):
    help = "Copy Najem Aslan Feature assets into backend data/weights and register active model."

    def handle(self, *args, **options):
        source_root = Path(settings.AI_EXTERNAL_FEATURE_DIR)
        if not source_root.exists():
            self.stdout.write(self.style.WARNING(f"Source not found: {source_root}"))
            return

        weights_dir = Path(settings.AI_WEIGHTS_DIR)
        data_dir = Path(settings.BASE_DIR) / "ai" / "data"
        weights_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)

        estimator_src = source_root / "Time Estimation Feature" / "Estimator.pkl"
        estimator_dst = weights_dir / "Estimator.pkl"
        if estimator_src.exists():
            shutil.copy2(estimator_src, estimator_dst)
            AIModelWeight.objects.filter(capability=AIModelWeight.CAPABILITY_TIME).update(is_active=False)
            AIModelWeight.objects.update_or_create(
                name="NajemEstimator",
                capability=AIModelWeight.CAPABILITY_TIME,
                defaults={
                    "provider": AIModelWeight.PROVIDER_LOCAL,
                    "weight_path": str(estimator_dst),
                    "is_active": True,
                    "metadata": {"source": str(estimator_src)},
                },
            )

        dataset_src = source_root / "Time Estimation Feature" / "Informatics_task_times_synthetic.csv"
        if dataset_src.exists():
            shutil.copy2(dataset_src, data_dir / "Informatics_task_times_synthetic.csv")

        challenge_src = source_root / "Chat Bot feature" / "challenge_bank_informatics.json"
        if challenge_src.exists():
            shutil.copy2(challenge_src, data_dir / "challenge_bank_informatics.json")

        svg_src = source_root / "my_final_mindmap.svg"
        if svg_src.exists():
            shutil.copy2(svg_src, Path(settings.AI_MINDMAP_SVG_PATH))

        self.stdout.write(self.style.SUCCESS("Najem Aslan assets imported successfully."))
