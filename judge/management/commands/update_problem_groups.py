from django.core.management.base import BaseCommand
from judge.models import Problem, ProblemGroup


class Command(BaseCommand):
    help = 'Update problem group based on problem code prefix'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prefix',
            default='hnueolp',
            help='Problem code prefix to match (default: hnueolp)',
        )
        parser.add_argument(
            '--group-name',
            default='hnueolp',
            help='Problem group unique name/slug (default: hnueolp)',
        )
        parser.add_argument(
            '--group-full-name',
            default='Olympic Tin học HNUE',
            help='Problem group display name (default: Olympic Tin học HNUE)',
        )

    def handle(self, *args, **options):
        prefix = options['prefix']
        group_name = options['group_name']
        group_full_name = options['group_full_name']

        group, created = ProblemGroup.objects.get_or_create(
            name=group_name,
            defaults={'full_name': group_full_name},
        )
        if not created and group.full_name != group_full_name:
            group.full_name = group_full_name
            group.save(update_fields=['full_name'])

        matching_problems = Problem.objects.filter(code__startswith=prefix)
        count = matching_problems.count()
        matching_problems.update(group=group)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated {count} problem(s) matching prefix "{prefix}" to group "{group.full_name}" (code: {group.name}).'
            )
        )
