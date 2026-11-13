import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('courses', '0006_course_year_courseaiconversation'),
    ]

    operations = [
        migrations.AddField(
            model_name='enrollment',
            name='result_submitted_to_department',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='enrollment',
            name='result_submitted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='enrollment',
            name='result_submitted_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='department_submitted_results',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
