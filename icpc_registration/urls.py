from django.urls import path
from . import views

app_name = 'icpc_registration'

urlpatterns = [
    path('', views.icpc_index, name='index'),
    path('thong-ke/', views.icpc_admin_stats, name='stats'),
    path('export-excel/', views.icpc_export_excel, name='export_excel'),
    path('update-status/<int:pk>/', views.icpc_update_status, name='update_status'),
]
