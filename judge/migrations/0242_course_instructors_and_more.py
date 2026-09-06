from django.db import migrations, models
import django.db.models.deletion


def migrate_existing_instructors(apps, schema_editor):
    Course = apps.get_model('judge', 'Course')
    for course_id, instructor_id in Course.objects.filter(instructor_id__isnull=False).values_list('id', 'instructor_id'):
        course = Course.objects.get(id=course_id)
        course.instructors.add(instructor_id)


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0241_contest_course_and_is_course_private'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='instructor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='created_courses',
                to='judge.profile',
                verbose_name='Giảng viên tạo',
            ),
        ),
        migrations.AddField(
            model_name='course',
            name='instructors',
            field=models.ManyToManyField(
                blank=True,
                related_name='instructed_courses',
                to='judge.profile',
                verbose_name='Giảng viên',
            ),
        ),
        migrations.RunPython(
            migrate_existing_instructors,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
