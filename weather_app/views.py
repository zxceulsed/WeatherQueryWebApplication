import csv
import logging
from datetime import datetime, timedelta

import requests
from decouple import config
from django.core.paginator import Paginator
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_GET

from .forms import CityForm
from .models import WeatherQuery
from .services import WeatherService

logger = logging.getLogger(__name__)

class WeatherView(View):
    template_name = "weather_app/index.html"

    def get(self, request):
        form = CityForm()
        return render(request, self.template_name, {"form": form, "unit": "metric"})

    def post(self, request):
        form = CityForm(request.POST)
        weather_data = None
        error = None
        unit = request.POST.get("unit", "metric")

        if form.is_valid():
            city_input = form.cleaned_data["city"].strip()
            city_key = city_input.lower()
            now = timezone.now()

            recent_query = WeatherQuery.objects.filter(
                city__iexact=city_key,
                unit=unit,
                created_at__gte=now - timedelta(minutes=5)
            ).order_by("-created_at").first()

            if recent_query:
                weather_data = {
                    "city": recent_query.city.title(),
                    "temperature": recent_query.temperature,
                    "description": recent_query.description,
                    "humidity": recent_query.humidity,
                    "wind_speed": recent_query.wind_speed,
                    "unit": recent_query.unit,
                    "from_cache": True,
                }
                WeatherQuery.objects.create(
                    city=recent_query.city,
                    temperature=recent_query.temperature,
                    description=recent_query.description,
                    humidity=recent_query.humidity,
                    wind_speed=recent_query.wind_speed,
                    unit=recent_query.unit,
                    from_cache=True
                )
            else:
                service = WeatherService()
                weather_data = service.get_weather(city_input, units=unit)

                if weather_data:
                    if unit == "imperial":
                        weather_data["wind_speed"] = round(weather_data["wind_speed"] * 0.44704, 2)

                    weather_data["from_cache"] = False

                    WeatherQuery.objects.create(
                        city=city_key,
                        temperature=weather_data["temperature"],
                        description=weather_data["description"],
                        humidity=weather_data["humidity"],
                        wind_speed=weather_data["wind_speed"],
                        unit=unit,
                        from_cache=False
                    )
                else:
                    error = "Город не найден или ошибка получения данных."

        return render(request, self.template_name, {
            "form": form,
            "weather": weather_data,
            "error": error,
            "unit": unit,
        })

class HistoryView(View):
    template_name = "weather_app/history.html"

    def get(self, request):
        queries = WeatherQuery.objects.all().order_by("-created_at")

        city = request.GET.get("city", "").strip()
        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")

        if city:
            queries = queries.filter(city__icontains=city)

        if date_from:
            queries = queries.filter(created_at__date__gte=date_from)

        if date_to:
            queries = queries.filter(created_at__date__lte=date_to)

        paginator = Paginator(queries, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context = {
            "page_obj": page_obj,
            "city": city,
            "date_from": date_from,
            "date_to": date_to,
        }
        return render(request, self.template_name, context)


def export_csv(request):
    queries = WeatherQuery.objects.all()

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="weather_history.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Дата и время запроса",
        "Город",
        "Температура",
        "Описание",
        "Влажность (%)",
        "Скорость ветра (м/с)",
        "Единицы",
        "Из кэша",
    ])

    for q in queries:
        writer.writerow([
            q.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            q.city,
            q.temperature,
            q.description,
            q.humidity,
            q.wind_speed,
            "°C" if q.unit == "metric" else "°F",
            "Да" if q.from_cache else "Нет",
        ])

    return response

@require_GET
def health_check(request):
    start_time = datetime.utcnow()
    logger.info(
        f"event=health_check_start method=GET path={request.path} timestamp={start_time.isoformat()}Z"
    )

    health = {
        "database": "unknown",
        "external_api": "unknown",
        "status": "unknown",
        "latency_ms": None,
        "timestamp": start_time.isoformat() + "Z",
    }


    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        health["database"] = "ok"
    except Exception as e:
        health["database"] = "error"
        logger.error(
            f"event=db_error timestamp={datetime.utcnow().isoformat()}Z error={e}"
        )

    # --- 2️⃣ Проверка внешнего API (OpenWeather) ---
    WEATHER_API_KEY = config("WEATHER_API_KEY", default=None)
    if WEATHER_API_KEY:
        try:
            api_start = datetime.utcnow()
            resp = requests.get(
                f"https://api.openweathermap.org/data/2.5/weather?q=Vienna&appid={WEATHER_API_KEY}",
                timeout=1.5,
            )
            api_end = datetime.utcnow()
            api_latency = (api_end - api_start).total_seconds() * 1000
            if resp.status_code == 200:
                health["external_api"] = f"ok ({api_latency:.2f} ms)"
            else:
                health["external_api"] = f"error (status {resp.status_code})"

            logger.info(
                f"event=external_api_check status_code={resp.status_code} latency_ms={api_latency:.2f} timestamp={api_end.isoformat()}Z"
            )
        except requests.RequestException as e:
            health["external_api"] = "timeout"
            logger.error(
                f"event=external_api_error timestamp={datetime.utcnow().isoformat()}Z error={e}"
            )
    else:
        health["external_api"] = "skipped (no API key)"

    end_time = datetime.utcnow()
    latency_ms = (end_time - start_time).total_seconds() * 1000
    health["latency_ms"] = round(latency_ms, 2)
    health["status"] = (
        "ok"
        if health["database"] == "ok" and "ok" in health["external_api"]
        else "degraded"
    )

    logger.info(
        f"event=health_check_end status={health['status']} total_latency_ms={health['latency_ms']} timestamp={end_time.isoformat()}Z"
    )

    return JsonResponse(health, status=200 if health["status"] == "ok" else 503)