import pytest
from unittest.mock import patch
from django.urls import reverse
from weather_app.models import WeatherQuery
from django.core.cache import cache

@pytest.mark.django_db
@patch("weather_app.services.requests.get")
def test_cache_reuse_vs_fresh_fetch(mock_get, client):
    cache.clear()
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "name": "Moscow",
        "sys": {"country": "RU"},
        "main": {"temp": 5, "feels_like": 4, "humidity": 70},
        "weather": [{"description": "cloudy", "icon": "04d"}],
        "wind": {"speed": 3},
    }

    url = reverse("weather")

    response1 = client.post(url, {"city": "Moscow", "unit": "metric"})
    assert response1.status_code == 200
    assert WeatherQuery.objects.count() == 1
    assert not response1.context["weather"]["from_cache"]

    mock_get.reset_mock()
    response2 = client.post(url, {"city": "Moscow", "unit": "metric"})
    assert response2.status_code == 200
    assert WeatherQuery.objects.count() == 2  # создаётся копия из кэша
    assert response2.context["weather"]["from_cache"]
    mock_get.assert_not_called()
