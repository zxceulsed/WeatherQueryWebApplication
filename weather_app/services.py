import requests
from decouple import config

class WeatherService:
    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

    def get_weather(self, city, units="metric"):
        params = {
            "q": city,
            "appid": config('WEATHER_API_KEY'),
            "units": units,
            "lang": "ru",
        }

        try:
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            return {
                "city": data["name"],
                "country": data["sys"]["country"],
                "temperature": round(data["main"]["temp"], 1),
                "feels_like": round(data["main"]["feels_like"], 1),
                "humidity": data["main"]["humidity"],
                "wind_speed": data["wind"]["speed"],
                "description": data["weather"][0]["description"].capitalize(),
                "icon": data["weather"][0]["icon"],
            }
        except Exception as e:
            print(f"Ошибка при запросе погоды: {e}")
            return None
