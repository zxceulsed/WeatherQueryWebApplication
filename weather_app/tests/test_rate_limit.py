import pytest
from django.urls import reverse
from weather_app.models import WeatherQuery
from django.core.cache import cache

@pytest.mark.django_db
def test_rate_limit_returns_429(client):
    cache.clear()
    url = reverse("weather")
    limit = 30

    for i in range(limit):
        response = client.post(url, {"city": "Paris"})
        assert response.status_code == 200


    response = client.post(url, {"city": "Paris"})
    assert response.status_code == 429


    assert WeatherQuery.objects.count() == limit
