from django.urls import path
from . import views

app_name = 'student_profile'

urlpatterns = [
    path('', views.profile_dashboard, name='dashboard'),
    path('api/full-profile/', views.api_get_full_profile, name='api_get_full_profile'),
    path('api/grades/update-value/', views.api_update_grade_value, name='api_update_grade_value'),
    path('api/subjects/save/', views.api_save_subject, name='api_save_subject'),
    path('api/subjects/search/', views.api_search_curriculum_subjects, name='api_search_curriculum_subjects'),
    path('api/grades/<int:grade_id>/delete/', views.api_delete_grade, name='api_delete_grade'),
    path('api/semesters/add/', views.api_add_semester, name='api_add_semester'),
    path('api/semesters/<str:semester_id>/edit/', views.api_edit_semester, name='api_edit_semester'),
    path('api/semesters/<str:semester_id>/delete/', views.api_delete_semester, name='api_delete_semester'),
    path('api/profile/reset/', views.api_reset_profile, name='api_reset_profile'),
]
