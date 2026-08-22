# Generated manually for province_category field on Contest

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0235_contest_is_province_contest_contest_province_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='province_category',
            field=models.CharField(
                blank=True,
                choices=[
                    ('thpt', 'Đề thi HSG THPT'),
                    ('thcs', 'Đề thi HSG THCS'),
                    ('other', 'Đề thi Khác (Olympic, Trại hè, Chuyên...)')
                ],
                db_index=True,
                default='other',
                help_text='Contest category: THPT, THCS, or Other (for provincial contests).',
                max_length=10,
                verbose_name='Category (Provincial contest)'
            ),
        ),
    ]
