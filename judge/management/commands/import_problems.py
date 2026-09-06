import os
import json
import yaml
from django.conf import settings
from django.core.management.base import BaseCommand
from judge.models import Problem, ProblemGroup, ProblemType, Language, ProblemData

VALID_CHECKERS = {'standard', 'bridged', 'floats', 'floatsabs', 'floatsrel', 'identical', 'linecount'}


class Command(BaseCommand):
    help = 'Import problem entries into database from problem data directory and link zip files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dir',
            default=getattr(settings, 'DMOJ_PROBLEM_DATA_ROOT', '/home/hnueoj/site/problems'),
            help='Directory containing problem folders',
        )

    def handle(self, *args, **options):
        problems_dir = options['dir']
        if not os.path.exists(problems_dir):
            self.stderr.write(self.style.ERROR(f'Directory does not exist: {problems_dir}'))
            return

        default_group = ProblemGroup.objects.first()
        default_type = ProblemType.objects.first()
        all_languages = list(Language.objects.all())

        subdirs = sorted([
            d for d in os.listdir(problems_dir)
            if os.path.isdir(os.path.join(problems_dir, d)) and not d.startswith('.')
        ])

        created_count = 0
        updated_data_count = 0

        for code in subdirs:
            p_dir = os.path.join(problems_dir, code)
            init_path = os.path.join(p_dir, 'init.yml')
            total_points = 0.0
            zip_name = None
            checker_name = 'standard'
            checker_args = ''

            if os.path.exists(init_path):
                try:
                    with open(init_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        if isinstance(data, dict):
                            zip_name = data.get('archive')
                            c_raw = data.get('checker', 'standard')
                            if isinstance(c_raw, dict):
                                checker_name = c_raw.get('name', 'bridged')
                                if 'args' in c_raw:
                                    checker_args = json.dumps(c_raw['args'])
                            elif isinstance(c_raw, str):
                                checker_name = c_raw

                            if 'test_cases' in data and isinstance(data['test_cases'], list):
                                for tc in data['test_cases']:
                                    if isinstance(tc, dict):
                                        total_points += float(tc.get('points', 0))
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'Failed to parse {init_path}: {e}'))

            if not zip_name:
                zips = [f for f in os.listdir(p_dir) if f.endswith('.zip')]
                if zips:
                    zip_name = zips[0]

            if total_points <= 0:
                total_points = 1.0

            if checker_name not in VALID_CHECKERS:
                checker_name = 'standard'

            target_group = default_group
            if code.startswith('hnueolp'):
                g, _ = ProblemGroup.objects.get_or_create(name='hnueolp', defaults={'full_name': 'Olympic Tin học HNUE'})
                target_group = g
            elif code.startswith('dtqg'):
                g, _ = ProblemGroup.objects.get_or_create(name='dtqg', defaults={'full_name': 'Đội tuyển HSG Quốc Gia'})
                target_group = g

            problem, created = Problem.objects.get_or_create(
                code=code,
                defaults={
                    'name': code,
                    'description': code,
                    'group': target_group,
                    'time_limit': 1.0,
                    'memory_limit': 1048576,
                    'points': total_points,
                    'partial': True,
                    'is_public': True,
                }
            )
            if not created and problem.group != target_group and target_group != default_group:
                problem.group = target_group
                problem.save(update_fields=['group'])

            if created:
                created_count += 1
                if default_type:
                    problem.types.add(default_type)
                if all_languages:
                    problem.allowed_languages.set(all_languages)

            # Link ProblemData zipfile and checker
            pd, _ = ProblemData.objects.get_or_create(problem=problem)
            if zip_name and os.path.exists(os.path.join(p_dir, zip_name)):
                pd.zipfile.name = f'{code}/{zip_name}'

            cpp_checkers = [f for f in os.listdir(p_dir) if f.endswith('.cpp')]
            if cpp_checkers:
                pd.custom_checker.name = f'{code}/{cpp_checkers[0]}'
                if checker_name == 'standard':
                    checker_name = 'bridged'

            pd.checker = checker_name
            if checker_args:
                pd.checker_args = checker_args

            pd.update_zipfile_size()
            pd.save()
            updated_data_count += 1

            self.stdout.write(self.style.SUCCESS(f'Processed {code}: zip={zip_name}, size={pd.zipfile_size}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'Done! Created {created_count} problem(s), linked ProblemData for {updated_data_count} problem(s).'
            )
        )
