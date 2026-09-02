"""Маршруты раздела «Сроки оплаты». Только пути."""

from django.urls import path

from api.deadlines import views

urlpatterns = [
    path("", views.deadlines, name="deadlines"),
    path("xlsx/", views.deadlines_xlsx, name="deadlines-xlsx"),
    path("<int:agent_id>/", views.deadline_detail, name="deadline-detail"),
]
