from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_is_email_verified_passwordresettoken_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="is_trainer",
        ),
    ]
