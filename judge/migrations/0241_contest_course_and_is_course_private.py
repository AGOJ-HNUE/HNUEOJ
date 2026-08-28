from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0240_course_contest_and_contest_is_course_only'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='is_course_private',
            field=models.BooleanField(db_index=True, default=False, help_text='If private, only members of the specified course may see the contest', verbose_name='private to course'),
        ),
        migrations.AddField(
            model_name='contest',
            name='course',
            field=models.ForeignKey(blank=True, help_text='If private, only this course may see the contest', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contests', to='judge.course', verbose_name='course'),
        ),
        migrations.AlterField(
            model_name='contest',
            name='is_organization_private',
            field=models.BooleanField(db_index=True, default=False, verbose_name='private to organizations'),
        ),
    ]
