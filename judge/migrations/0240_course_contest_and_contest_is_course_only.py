from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone
import datetime


def migrate_exams_to_contests(apps, schema_editor):
    Exam = apps.get_model('judge', 'Exam')
    Contest = apps.get_model('judge', 'Contest')
    ContestProblem = apps.get_model('judge', 'ContestProblem')
    CourseContest = apps.get_model('judge', 'CourseContest')
    Submission = apps.get_model('judge', 'Submission')

    for exam in Exam.objects.all():
        contest = exam.contest
        if not contest:
            slug_key = f"exam-c{exam.course_id}-e{exam.id}"[:30]
            start = exam.start_time or exam.created_at
            end = exam.end_time or (start + datetime.timedelta(days=365))
            contest = Contest.objects.create(
                key=slug_key,
                name=exam.title,
                description=exam.description or '',
                start_time=start,
                end_time=end,
                time_limit=exam.time_limit,
                is_visible=False,
                is_course_only=True,
                format_name='atcoder',
            )
            for order, ep in enumerate(exam.exam_problems.all()):
                ContestProblem.objects.create(
                    contest=contest,
                    problem=ep.problem,
                    order=order,
                    points=ep.custom_score if ep.custom_score is not None else ep.problem.points,
                )

        CourseContest.objects.get_or_create(
            course=exam.course,
            contest=contest,
            defaults={
                'chapter': exam.chapter,
                'scope_type': 'CHAPTER' if exam.chapter_id else 'COURSE',
                'order_index': exam.order_index,
                'passing_grade': exam.pass_percentage if hasattr(exam, 'pass_percentage') else 50.0,
            }
        )

        Submission.objects.filter(exam_id=exam.id).update(contest_object=contest)


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0239_alter_contest_end_time_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='is_course_only',
            field=models.BooleanField(default=False, help_text='If set, this contest is embedded in a course.', verbose_name='is course only'),
        ),
        migrations.CreateModel(
            name='CourseContest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope_type', models.CharField(choices=[('CHAPTER', 'Contest cấp Chương'), ('COURSE', 'Contest cấp Khóa học (Giữa kỳ / Cuối kỳ)')], db_index=True, default='CHAPTER', max_length=16, verbose_name='Phân cấp Contest')),
                ('weight', models.FloatField(default=1.0, help_text='Trọng số dùng để tính tổng điểm trung bình khóa học.', verbose_name='Trọng số điểm (%)')),
                ('passing_grade', models.FloatField(default=50.0, help_text='Tỷ lệ % điểm Contest cần đạt để coi là Phủ điểm/Pass.', verbose_name='Điểm đạt tối thiểu (%)')),
                ('is_required', models.BooleanField(default=True, help_text='Học viên phải tham gia/đạt chuẩn mới được tính hoàn thành Khóa học.', verbose_name='Bắt buộc hoàn thành')),
                ('order_index', models.PositiveIntegerField(db_index=True, default=0, verbose_name='Thứ tự hiển thị')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('chapter', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chapter_contests', to='judge.chapter', verbose_name='Chương')),
                ('contest', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_mappings', to='judge.contest', verbose_name='Contest liên kết')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_contests', to='judge.course', verbose_name='Khóa học')),
            ],
            options={
                'verbose_name': 'Contest trong Khóa học',
                'verbose_name_plural': 'Các Contest trong Khóa học',
                'ordering': ('order_index', 'id'),
                'unique_together': {('course', 'contest')},
            },
        ),
        migrations.RunPython(migrate_exams_to_contests, reverse_code=migrations.RunPython.noop),
    ]
