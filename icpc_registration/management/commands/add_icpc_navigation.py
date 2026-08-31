from django.core.management.base import BaseCommand
from django.db import models
from judge.models import NavigationBar


class Command(BaseCommand):
    help = 'Thêm menu CLB NVSP & Tiểu ban ICPC vào NavigationBar'

    def handle(self, *args, **options):
        # 1. Tạo hoặc lấy parent item CLB NVSP
        clb_nav = NavigationBar.objects.filter(key='clb_nvsp').first()
        if not clb_nav:
            max_order = NavigationBar.objects.filter(parent=None).aggregate(models.Max('order'))['order__max'] or 0
            clb_nav = NavigationBar.objects.create(
                key='clb_nvsp',
                label='CLB NVSP',
                path='/clb-nvsp/icpc/',
                regex='^/clb-nvsp/',
                order=max_order + 1,
            )
            self.stdout.write(self.style.SUCCESS('Đã tạo menu cha "CLB NVSP"'))

        # 2. Tạo sub-item "Tiểu ban ICPC"
        if not NavigationBar.objects.filter(key='icpc_sub').exists():
            sub_order = NavigationBar.objects.filter(parent=clb_nav).aggregate(models.Max('order'))['order__max'] or 0
            NavigationBar.objects.create(
                key='icpc_sub',
                label='Tiểu ban ICPC',
                path='/clb-nvsp/icpc/',
                regex='^/clb-nvsp/icpc/$',
                order=sub_order + 1,
                parent=clb_nav,
            )
            self.stdout.write(self.style.SUCCESS('Đã tạo menu con "Tiểu ban ICPC"'))

        # 3. Tạo sub-item "Đăng ký thành viên"
        if not NavigationBar.objects.filter(key='icpc_reg').exists():
            sub_order = NavigationBar.objects.filter(parent=clb_nav).aggregate(models.Max('order'))['order__max'] or 0
            NavigationBar.objects.create(
                key='icpc_reg',
                label='Đăng ký thành viên',
                path='/clb-nvsp/icpc/dang-ky/',
                regex='^/clb-nvsp/icpc/dang-ky/',
                order=sub_order + 1,
                parent=clb_nav,
            )
            self.stdout.write(self.style.SUCCESS('Đã tạo menu con "Đăng ký thành viên"'))

        # Rebuild MPTT tree
        NavigationBar.objects.rebuild()
        self.stdout.write(self.style.SUCCESS('Hoàn tất cập nhật NavigationBar.'))
