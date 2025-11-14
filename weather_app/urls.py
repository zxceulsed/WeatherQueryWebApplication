from django.urls import path
from .views import WeatherView, HistoryView

urlpatterns = [
    path("", WeatherView.as_view(), name="weather"),
    path("history/", HistoryView.as_view(), name="history"),

]
