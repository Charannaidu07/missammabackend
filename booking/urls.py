from django.urls import path
from .views import ServiceListView, AppointmentListCreateView

urlpatterns = [
    path('services/', ServiceListView.as_view()),
    path('appointments/', AppointmentListCreateView.as_view()),
]
