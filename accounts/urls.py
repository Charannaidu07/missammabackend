from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterView, MeView

urlpatterns = [
    path('register/', RegisterView.as_view()),
    path('login/', TokenObtainPairView.as_view()),   # <– SimpleJWT login
    path('refresh/', TokenRefreshView.as_view()),    # <– refresh endpoint
    path('me/', MeView.as_view()),
]
