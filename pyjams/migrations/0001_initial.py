from typing import ClassVar

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies: ClassVar[list] = []

    operations: ClassVar[list] = [
        migrations.CreateModel(
            name="Greeting",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "when",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="date created"
                    ),
                ),
            ],
        ),
    ]
