from django.core.management.base import BaseCommand
from judge.models import Problem


class Command(BaseCommand):
    help = 'Batch update memory limit and points for all problems in system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--memory-limit',
            type=int,
            default=1048576,
            help='Memory limit in KB (default: 1048576 for 1GB)',
        )
        parser.add_argument(
            '--points',
            type=float,
            default=1.0,
            help='Problem points (default: 1.0)',
        )
        parser.add_argument(
            '--prefix',
            type=str,
            default=None,
            help='Filter problem codes by prefix (optional)',
        )

    def handle(self, *args, **options):
        memory_limit = options['memory_limit']
        points = options['points']
        prefix = options['prefix']

        queryset = Problem.objects.all()
        if prefix:
            queryset = queryset.filter(code__startswith=prefix)

        count = queryset.count()
        updated = queryset.update(memory_limit=memory_limit, points=points)

        prefix_str = f' matching prefix "{prefix}"' if prefix else ''
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated {updated}/{count} problem(s){prefix_str} with memory_limit={memory_limit} KB and points={points}.'
            )
        )
