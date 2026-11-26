from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0011_auto_20261110_2237'),
    ]

    operations = [
        migrations.AddField(
            model_name='sebsession',
            name='login_used',
            field=models.BooleanField(default=False),
        ),
    ]
