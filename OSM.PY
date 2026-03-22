# ==========================================================
# 🗺️ OpenStreetMap Emergency Services Locator
# ==========================================================

import requests
import math
from typing import List, Dict, Optional

try:
    from config import DEFAULT_LATITUDE, DEFAULT_LONGITUDE, WEATHER_API_KEY
except ImportError:
    DEFAULT_LATITUDE = 9.9312    # Kochi, Kerala (fallback)
    DEFAULT_LONGITUDE = 76.2673  # Kochi, Kerala (fallback)
    WEATHER_API_KEY = ""


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class EmergencyServicesLocator:

    EXCLUDE_KEYWORDS = [
        'dental', 'dentist', 'teeth', 'tooth', 'orthodont',
        'eye', 'vision', 'ophthalm', 'opthal', 'retina',
        'veterinar', 'animal', 'pet care',
        'skin', 'dermatol', 'cosmetic', 'plastic surg',
        'ayurved', 'homeopath', 'homoeopath', 'homoeo',
        'siddha', 'naturopath', 'unani',
        'cancer', 'oncolog',
        'maternity', 'gynae', 'gynaecol', 'obstetric',
        'paediatric', 'pediatric',
        'psychiatr', 'mental health', 'de-addiction',
        'dialysis', 'kidney', 'nephrol',
        'clini',
        'polyclinic',
        'nursing home',
        'dispensar',
        'physiother',
        'rehabilit',
        'blood bank',
        'dr.',
        'dr ',
    ]

    PREFER_KEYWORDS = [
        'general hospital', 'govt', 'government', 'district hospital',
        'medical college', 'apollo', 'fortis', 'manipal', 'columbia',
        'miot', 'kauvery', 'primary health', 'community health',
        'taluk hospital', 'civil hospital', 'emergency', 'trauma',
        'multi speciality', 'super speciality', 'rajiv gandhi',
        'stanley', 'kilpauk', 'esi', 'esic', 'victoria', 'bowring',
        'st john', 'saint john', 'corporation hospital',
        # Kerala-specific hospitals
        'medical college hospital', 'district hospital', 'taluk',
        'general hospital', 'lakeshore', 'amrita', 'aster', 'kims',
        'baby memorial', 'malabar', 'kozhikode medical',
        'thiruvananthapuram medical', 'ernakulam general',
        'thrissur district', 'kollam district',
    ]

    def __init__(self):
        self.overpass_url  = "https://overpass-api.de/api/interpreter"
        self.nominatim_url = "https://nominatim.openstreetmap.org"
        self.weather_api_key = WEATHER_API_KEY

    def _query_overpass(self, query: str) -> Optional[Dict]:
        try:
            response = requests.post(
                self.overpass_url,
                data={'data': query},
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Overpass API error: {e}")
        return None

    def _is_general_hospital(self, name: str, tags: dict) -> bool:
        name_lower = name.lower()

        for kw in self.EXCLUDE_KEYWORDS:
            if kw in name_lower:
                print(f"   Skipping [{kw}]: {name}")
                return False

        speciality = (
            tags.get('speciality', '') or
            tags.get('healthcare:speciality', '') or
            tags.get('healthcare', '') or
            tags.get('medical_system', '')
        ).lower()

        for kw in ['dental', 'eye', 'veterinary', 'ayurveda',
                   'homoeopathy', 'homeopathy', 'physiotherapy']:
            if kw in speciality:
                print(f"   Skipping tag [{kw}]: {name}")
                return False

        if tags.get('healthcare', '') == 'clinic':
            print(f"   Skipping healthcare=clinic: {name}")
            return False

        return True

    def _prefer_score(self, name: str) -> int:
        name_lower = name.lower()
        return sum(1 for kw in self.PREFER_KEYWORDS if kw in name_lower)

    def get_address_from_coords(self, lat: float, lon: float) -> str:
        try:
            response = requests.get(
                f"{self.nominatim_url}/reverse",
                params={
                    'lat': lat,
                    'lon': lon,
                    'format': 'json',
                    'zoom': 16,
                    'addressdetails': 1,
                },
                headers={'User-Agent': 'AISeeYou-AccidentDetection/1.0'},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('display_name', f"{lat:.4f}, {lon:.4f}")
        except Exception as e:
            print(f"Geocoding error: {e}")
        return f"{lat:.4f}, {lon:.4f}"

    def find_nearest_hospitals(self, lat: float, lon: float,
                               radius: int = 5000, limit: int = 5) -> List[Dict]:
        fetch_count = limit * 8
        query = f"""
        [out:json][timeout:25];
        (
          node["amenity"="hospital"](around:{radius},{lat},{lon});
          way["amenity"="hospital"](around:{radius},{lat},{lon});
          relation["amenity"="hospital"](around:{radius},{lat},{lon});
        );
        out center {fetch_count};
        """
        result = self._query_overpass(query)
        hospitals = []

        if result and 'elements' in result:
            for element in result['elements']:
                h_lat = element.get('lat') or element.get('center', {}).get('lat')
                h_lon = element.get('lon') or element.get('center', {}).get('lon')
                if not h_lat or not h_lon:
                    continue

                tags = element.get('tags', {})
                name = (tags.get('name') or tags.get('name:en') or 'Unknown Hospital')

                if not self._is_general_hospital(name, tags):
                    continue

                distance = haversine_distance(lat, lon, h_lat, h_lon)
                hospitals.append({
                    'name':        name,
                    'latitude':    h_lat,
                    'longitude':   h_lon,
                    'distance_km': round(distance, 2),
                    'phone':       tags.get('phone', 'N/A'),
                    'emergency':   tags.get('emergency', 'unknown'),
                    'address':     tags.get('addr:full', 'N/A'),
                    '_score':      self._prefer_score(name),
                })

        hospitals.sort(key=lambda x: (x['distance_km'] - x['_score'] * 0.5))
        for h in hospitals:
            h.pop('_score', None)
        return hospitals[:limit]

    def find_nearest_police_stations(self, lat: float, lon: float,
                                     radius: int = 5000, limit: int = 5) -> List[Dict]:
        query = f"""
        [out:json][timeout:25];
        (
          node["amenity"="police"](around:{radius},{lat},{lon});
          way["amenity"="police"](around:{radius},{lat},{lon});
          relation["amenity"="police"](around:{radius},{lat},{lon});
        );
        out center {limit};
        """
        result = self._query_overpass(query)
        stations = []

        if result and 'elements' in result:
            for element in result['elements']:
                s_lat = element.get('lat') or element.get('center', {}).get('lat')
                s_lon = element.get('lon') or element.get('center', {}).get('lon')
                if not s_lat or not s_lon:
                    continue

                tags = element.get('tags', {})
                name = (tags.get('name') or tags.get('name:en') or 'Unknown Police Station')
                distance = haversine_distance(lat, lon, s_lat, s_lon)

                stations.append({
                    'name':        name,
                    'latitude':    s_lat,
                    'longitude':   s_lon,
                    'distance_km': round(distance, 2),
                    'phone':       tags.get('phone', 'N/A'),
                    'address':     tags.get('addr:full', 'N/A'),
                })

        stations.sort(key=lambda x: x['distance_km'])
        return stations[:limit]

    def find_nearest_fire_stations(self, lat: float, lon: float,
                                   radius: int = 5000, limit: int = 3) -> List[Dict]:
        query = f"""
        [out:json][timeout:25];
        (
          node["amenity"="fire_station"](around:{radius},{lat},{lon});
          way["amenity"="fire_station"](around:{radius},{lat},{lon});
        );
        out center {limit};
        """
        result = self._query_overpass(query)
        stations = []

        if result and 'elements' in result:
            for element in result['elements']:
                f_lat = element.get('lat') or element.get('center', {}).get('lat')
                f_lon = element.get('lon') or element.get('center', {}).get('lon')
                if not f_lat or not f_lon:
                    continue

                tags = element.get('tags', {})
                name = (tags.get('name') or tags.get('name:en') or 'Unknown Fire Station')
                distance = haversine_distance(lat, lon, f_lat, f_lon)

                stations.append({
                    'name':        name,
                    'latitude':    f_lat,
                    'longitude':   f_lon,
                    'distance_km': round(distance, 2),
                    'phone':       tags.get('phone', 'N/A'),
                })

        stations.sort(key=lambda x: x['distance_km'])
        return stations[:limit]

    def get_all_emergency_services(self, lat: float, lon: float) -> Dict:
        print(f"Querying emergency services at ({lat:.4f}, {lon:.4f})")
        hospitals = self.find_nearest_hospitals(lat, lon, limit=3)
        police    = self.find_nearest_police_stations(lat, lon, limit=3)
        fire      = self.find_nearest_fire_stations(lat, lon, limit=2)
        address   = self.get_address_from_coords(lat, lon)

        return {
            'location': {
                'latitude':  lat,
                'longitude': lon,
                'address':   address,
            },
            'nearest_hospital':     hospitals[0] if hospitals else None,
            'all_hospitals':        hospitals,
            'nearest_police':       police[0] if police else None,
            'all_police_stations':  police,
            'nearest_fire_station': fire[0] if fire else None,
            'all_fire_stations':    fire,
        }


# ==========================================================
# Weather Service
# ==========================================================

class WeatherService:

    def __init__(self, api_key: str = None):
        self.api_key  = api_key or WEATHER_API_KEY
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    def get_weather(self, lat: float, lon: float) -> Dict:
        if not self.api_key:
            return self._get_simulated_weather()
        try:
            response = requests.get(
                self.base_url,
                params={
                    'lat': lat, 'lon': lon,
                    'appid': self.api_key,
                    'units': 'metric',
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'weather':     data['weather'][0]['main'],
                    'description': data['weather'][0]['description'],
                    'temperature': round(data['main']['temp'], 1),
                    'humidity':    data['main']['humidity'],
                    'wind_speed':  data['wind']['speed'],
                    'visibility':  data.get('visibility', 10000) / 1000,
                    'clouds':      data['clouds']['all'],
                    'rain':        data.get('rain', {}).get('1h', 0),
                    'risk_factor': self._calculate_risk_factor(data),
                    'city':        data.get('name', ''),
                }
        except Exception as e:
            print(f"Weather API error: {e}")
        return self._get_simulated_weather()

    def _get_simulated_weather(self) -> Dict:
        return {
            'weather':     'Clear',
            'description': 'clear sky (simulated)',
            'temperature': 28,
            'humidity':    65,
            'wind_speed':  3.5,
            'visibility':  10,
            'clouds':      20,
            'rain':        0,
            'risk_factor': 'Low',
            'city':        'N/A',
        }

    def _calculate_risk_factor(self, weather_data: Dict) -> str:
        risk_score   = 0
        weather_main = weather_data['weather'][0]['main'].lower()
        visibility   = weather_data.get('visibility', 10000)
        rain         = weather_data.get('rain', {}).get('1h', 0)
        wind         = weather_data['wind']['speed']

        if weather_main in ['rain', 'drizzle']:       risk_score += 30
        elif weather_main == 'thunderstorm':           risk_score += 50
        elif weather_main in ['snow', 'sleet']:        risk_score += 60
        elif weather_main in ['fog', 'mist', 'haze']: risk_score += 40

        if visibility < 1000:   risk_score += 40
        elif visibility < 5000: risk_score += 20

        if rain > 10:  risk_score += 30
        elif rain > 5: risk_score += 15

        if wind > 20:   risk_score += 20
        elif wind > 10: risk_score += 10

        if risk_score >= 60:   return 'High'
        elif risk_score >= 30: return 'Medium'
        else:                  return 'Low'


# ==========================================================
# Module-level singletons
# ==========================================================
emergency_locator = EmergencyServicesLocator()
weather_service   = WeatherService()


def get_emergency_info(lat: float = None, lon: float = None) -> Dict:
    """
    Get complete emergency services + weather for a location.
    Always pass lat/lon explicitly from the GUI or accident data.
    Only falls back to Kochi default if nothing is provided at all.
    """
    lat = lat if lat is not None else DEFAULT_LATITUDE
    lon = lon if lon is not None else DEFAULT_LONGITUDE
    services = emergency_locator.get_all_emergency_services(lat, lon)
    weather  = weather_service.get_weather(lat, lon)
    return {**services, 'weather': weather}


# ==========================================================
# Self-test — Kerala locations
# ==========================================================
if __name__ == "__main__":
    print("Testing Emergency Services Locator — Kerala")
    print("=" * 55)
    for city, lat, lon in [
        ("Kochi",          9.9312,  76.2673),
        ("Trivandrum",     8.5241,  76.9366),
        ("Kozhikode",     11.2588,  75.7804),
        ("Thrissur",      10.5276,  76.2144),
        ("Kollam",         8.8932,  76.6141),
    ]:
        print(f"\n{city} ({lat}, {lon})")
        info = get_emergency_info(lat, lon)
        print(f"  Address : {info['location']['address'][:65]}...")
        if info['nearest_hospital']:
            h = info['nearest_hospital']
            print(f"  Hospital: {h['name']} — {h['distance_km']} km")
        else:
            print("  Hospital: None found within 5 km")
        if info['nearest_police']:
            p = info['nearest_police']
            print(f"  Police  : {p['name']} — {p['distance_km']} km")
        w = info['weather']
        print(f"  Weather : {w['weather']}, {w['temperature']}C, Risk: {w['risk_factor']}")
    print("\nTest complete!")