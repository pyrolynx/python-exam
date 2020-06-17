# Generated by Django 3.0.7 on 2020-06-17 14:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('exam_web', '0003_auto_20200613_1722'),
    ]

    operations = [
        migrations.AlterField(
            model_name='examticket',
            name='session',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='exam_tickets', to='exam_web.UserSession'),
        ),
        migrations.AlterField(
            model_name='usersession',
            name='student',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='user_sessions', to='exam_web.Student'),
        ),
    ]