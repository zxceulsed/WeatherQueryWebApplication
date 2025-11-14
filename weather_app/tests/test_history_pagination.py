import pytest
from django.urls import reverse
from weather_app.models import WeatherQuery
from django.utils import timezone
from django.core.cache import cache

@pytest.mark.django_db
def test_history_filter_and_pagination(client):
    cache.clear()
    for i in range(15):
        WeatherQuery.objects.create(
            city=f"Moscow" if i < 10 else "Paris",
            temperature=10 + i,
            description="clear",
            humidity=60,
            wind_speed=3,
            unit="metric",
            from_cache=False,
            created_at=timezone.now(),
        )

    url = reverse("history") + "?city=Moscow"
    response = client.get(url)
    page_obj = response.context["page_obj"]

    assert response.status_code == 200
    assert all("Moscow" in q.city for q in page_obj)
    assert len(page_obj.object_list) <= 10
