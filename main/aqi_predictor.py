import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import pickle
import os

class AQIMLPredictor:
    def __init__(self):
        self.models = {}  # Store models per city
        self.scalers = {}  # Store scalers per city
        self.waqi_token = "5e0214c5c216996d172b81aada3023f232491cb9"
        self.weather_api_key = "cd923425db3a0c14da21f71823ff56c9"
        self.models_dir = "ml_models"
        
        # Create models directory if it doesn't exist
        if not os.path.exists(self.models_dir):
            os.makedirs(self.models_dir)
        
    def get_model_path(self, city):
        """Get model path for specific city"""
        safe_city = city.replace(" ", "_").lower()
        return os.path.join(self.models_dir, f"aqi_model_{safe_city}.pkl")
    
    def get_current_aqi(self, city="Delhi"):
        """Get real-time AQI data"""
        try:
            url = f"https://api.waqi.info/feed/{city}/?token={self.waqi_token}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'ok':
                    aqi = data['data']['aqi']
                    iaqi = data['data'].get('iaqi', {})
                    
                    return {
                        'aqi': aqi,
                        'pm25': iaqi.get('pm25', {}).get('v', 0),
                        'pm10': iaqi.get('pm10', {}).get('v', 0),
                        'no2': iaqi.get('no2', {}).get('v', 0),
                        'o3': iaqi.get('o3', {}).get('v', 0),
                        'city': data['data']['city']['name'],
                        'time': data['data']['time']['s']
                    }
        except:
            pass
        
        # Fallback to OpenWeather
        try:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={self.weather_api_key}"
            geo_response = requests.get(geo_url, timeout=10)
            
            if geo_response.status_code == 200:
                geo_data = geo_response.json()
                if geo_data:
                    lat = geo_data[0]['lat']
                    lon = geo_data[0]['lon']
                    
                    aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={self.weather_api_key}"
                    aqi_response = requests.get(aqi_url, timeout=10)
                    
                    if aqi_response.status_code == 200:
                        aqi_data = aqi_response.json()
                        components = aqi_data['list'][0]['components']
                        pm25 = components.get('pm2_5', 0)
                        
                        return {
                            'aqi': self.calculate_aqi_from_pm25(pm25),
                            'pm25': pm25,
                            'pm10': components.get('pm10', 0),
                            'no2': components.get('no2', 0),
                            'o3': components.get('o3', 0),
                            'city': city,
                            'time': datetime.now().strftime('%Y-%m-%d %H:%M')
                        }
        except:
            pass
        
        return {
            'aqi': 150, 'pm25': 0, 'pm10': 0, 'no2': 0, 'o3': 0,
            'city': city, 'time': datetime.now().strftime('%Y-%m-%d %H:%M')
        }
    
    def calculate_aqi_from_pm25(self, pm25):
        """Calculate AQI from PM2.5"""
        if pm25 <= 12.0:
            return int((50 - 0) / (12.0 - 0) * (pm25 - 0) + 0)
        elif pm25 <= 35.4:
            return int((100 - 51) / (35.4 - 12.1) * (pm25 - 12.1) + 51)
        elif pm25 <= 55.4:
            return int((150 - 101) / (55.4 - 35.5) * (pm25 - 35.5) + 101)
        elif pm25 <= 150.4:
            return int((200 - 151) / (150.4 - 55.5) * (pm25 - 55.5) + 151)
        elif pm25 <= 250.4:
            return int((300 - 201) / (250.4 - 150.5) * (pm25 - 150.5) + 201)
        elif pm25 <= 350.4:
            return int((400 - 301) / (350.4 - 250.5) * (pm25 - 250.5) + 301)
        else:
            return int((500 - 401) / (500.4 - 350.5) * (pm25 - 350.5) + 401)
    
    def get_weather_forecast(self, city):
        """Get weather forecast"""
        try:
            url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={self.weather_api_key}&units=metric"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def create_training_data(self, city="Delhi", days=30):
        """Create synthetic training data based on real patterns"""
        print(f"Creating training data for {city}...")
        
        # Get current real data
        current = self.get_current_aqi(city)
        base_aqi = current['aqi']
        
        # City-specific AQI patterns
        city_profiles = {
            'delhi': {'base_multiplier': 1.2, 'winter_increase': 50, 'traffic_hours': [7,8,9,18,19,20]},
            'mumbai': {'base_multiplier': 0.9, 'winter_increase': 20, 'traffic_hours': [8,9,10,19,20,21]},
            'bangalore': {'base_multiplier': 0.7, 'winter_increase': 15, 'traffic_hours': [8,9,18,19]},
            'kolkata': {'base_multiplier': 1.0, 'winter_increase': 35, 'traffic_hours': [7,8,9,18,19]},
            'chennai': {'base_multiplier': 0.8, 'winter_increase': 10, 'traffic_hours': [8,9,18,19]},
            'noida': {'base_multiplier': 1.15, 'winter_increase': 45, 'traffic_hours': [7,8,9,18,19,20]},
            'gurgaon': {'base_multiplier': 1.1, 'winter_increase': 40, 'traffic_hours': [7,8,9,18,19,20]},
        }
        
        city_key = city.lower()
        profile = city_profiles.get(city_key, {'base_multiplier': 1.0, 'winter_increase': 30, 'traffic_hours': [8,9,18,19]})
        
        data = []
        
        for day in range(days):
            for hour in range(0, 24, 3):
                timestamp = datetime.now() - timedelta(days=day, hours=hour)
                
                hour_of_day = timestamp.hour
                day_of_week = timestamp.weekday()
                month = timestamp.month
                
                # Base AQI with city profile
                aqi = base_aqi * profile['base_multiplier'] + np.random.randint(-30, 30)
                
                # Seasonal pattern
                if month in [11, 12, 1]:
                    aqi += profile['winter_increase']
                elif month in [6, 7, 8]:
                    aqi -= 20
                
                # Traffic pattern
                if hour_of_day in profile['traffic_hours']:
                    aqi += 25
                elif hour_of_day in [0, 1, 2, 3, 4, 5]:
                    aqi -= 15
                
                # Weekend effect
                if day_of_week == 6:
                    aqi -= 10
                
                # Weather simulation
                temp = 25 + np.random.randn() * 5
                humidity = 60 + np.random.randn() * 15
                wind = 3 + abs(np.random.randn() * 2)
                
                # Weather effects on AQI
                if humidity > 70:
                    aqi += 15
                if wind > 5:
                    aqi -= 20
                if temp < 15:
                    aqi += 15
                
                aqi = max(0, min(500, aqi))
                
                data.append({
                    'hour': hour_of_day,
                    'day_of_week': day_of_week,
                    'month': month,
                    'temp': temp,
                    'humidity': humidity,
                    'wind': wind,
                    'aqi_lag_1': aqi + np.random.randint(-5, 5),
                    'aqi_lag_3': aqi + np.random.randint(-10, 10),
                    'aqi': aqi
                })
        
        return pd.DataFrame(data)
    
    def train_model(self, city="Delhi"):
        """Train Random Forest model for specific city"""
        print(f"Training ML model for {city}...")
        
        # Create training data
        df = self.create_training_data(city, days=60)
        
        # Features
        features = ['hour', 'day_of_week', 'month', 'temp', 'humidity', 'wind', 'aqi_lag_1', 'aqi_lag_3']
        X = df[features]
        y = df['aqi']
        
        # Create new scaler for this city
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Train Random Forest
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_scaled, y)
        
        # Store model and scaler
        self.models[city] = model
        self.scalers[city] = scaler
        
        # Calculate accuracy
        score = model.score(X_scaled, y)
        print(f"Model R² Score for {city}: {score:.4f}")
        
        # Save model
        self.save_model(city)
        
        return score
    
    def predict_aqi(self, city="Delhi"):
        """Predict AQI for next 72 hours using ML model - anchored to current AQI"""
        
        # Load or train model for this city
        model_path = self.get_model_path(city)
        
        if city not in self.models:
            if os.path.exists(model_path):
                self.load_model(city)
            else:
                print(f"No model found for {city}. Training new model...")
                self.train_model(city)
        
        # Get current AQI - THIS IS THE EXACT ANCHOR POINT
        current = self.get_current_aqi(city)
        current_aqi = current['aqi']
        print(f"Current AQI for {city}: {current_aqi} (EXACT)")
        
        # Get weather forecast
        weather_data = self.get_weather_forecast(city)
        
        if not weather_data or 'list' not in weather_data:
            print(f"No weather data available for {city}")
            return []
        
        predictions = []
        aqi_history = [current_aqi, current_aqi]
        
        model = self.models[city]
        scaler = self.scalers[city]
        
        # Track cumulative drift to prevent predictions from diverging too far
        cumulative_adjustment = 0
        max_drift_per_hour = 15  # Maximum AQI change per hour
        max_total_drift = 50     # Maximum total drift from current AQI
        
        for idx, item in enumerate(weather_data['list'][:24]):
            timestamp = datetime.fromtimestamp(item['dt'])
            
            # Prepare features
            features = {
                'hour': timestamp.hour,
                'day_of_week': timestamp.weekday(),
                'month': timestamp.month,
                'temp': item['main']['temp'],
                'humidity': item['main']['humidity'],
                'wind': item['wind']['speed'],
                'aqi_lag_1': aqi_history[-1],
                'aqi_lag_3': aqi_history[-2] if len(aqi_history) > 1 else aqi_history[-1]
            }
            
            # Create feature array
            X = np.array([[
                features['hour'],
                features['day_of_week'],
                features['month'],
                features['temp'],
                features['humidity'],
                features['wind'],
                features['aqi_lag_1'],
                features['aqi_lag_3']
            ]])
            
            # Scale and predict
            X_scaled = scaler.transform(X)
            raw_prediction = model.predict(X_scaled)[0]
            
            # Apply constraints to keep predictions realistic and anchored
            if idx == 0:
                # First prediction: very close to current AQI (±5)
                predicted_aqi = current_aqi + np.clip(raw_prediction - current_aqi, -5, 5)
            else:
                # Subsequent predictions: gradual change from previous
                change_from_previous = raw_prediction - aqi_history[-1]
                
                # Limit change per hour
                constrained_change = np.clip(change_from_previous, -max_drift_per_hour, max_drift_per_hour)
                
                # Apply change
                predicted_aqi = aqi_history[-1] + constrained_change
                
                # Track total drift from original current AQI
                drift_from_current = predicted_aqi - current_aqi
                
                # If drifting too far, pull back towards current AQI
                if abs(drift_from_current) > max_total_drift:
                    # Apply rubber band effect - pull back 30% towards current
                    predicted_aqi = predicted_aqi - 0.3 * (drift_from_current - np.sign(drift_from_current) * max_total_drift)
            
            # Keep in valid range
            predicted_aqi = max(0, min(500, predicted_aqi))
            
            # Get category
            if predicted_aqi <= 50:
                category = "Good"
            elif predicted_aqi <= 100:
                category = "Satisfactory"
            elif predicted_aqi <= 200:
                category = "Moderate"
            elif predicted_aqi <= 300:
                category = "Poor"
            elif predicted_aqi <= 400:
                category = "Very Poor"
            else:
                category = "Severe"
            
            predictions.append({
                'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                'aqi': round(predicted_aqi, 1),
                'category': category,
                'temp': round(item['main']['temp'], 1),
                'humidity': item['main']['humidity'],
                'wind': round(item['wind']['speed'], 1)
            })
            
            # Update history
            aqi_history.append(predicted_aqi)
            if len(aqi_history) > 3:
                aqi_history.pop(0)
        
        return predictions
    
    def save_model(self, city):
        """Save trained model for specific city"""
        model_path = self.get_model_path(city)
        with open(model_path, 'wb') as f:
            pickle.dump({
                'model': self.models[city],
                'scaler': self.scalers[city]
            }, f)
        print(f"Model saved for {city} to {model_path}")
    
    def load_model(self, city):
        """Load trained model for specific city"""
        model_path = self.get_model_path(city)
        if os.path.exists(model_path):
            with open(model_path, 'rb') as f:
                data = pickle.load(f)
                self.models[city] = data['model']
                self.scalers[city] = data['scaler']
            print(f"Model loaded for {city} from {model_path}")
            return True
        return False


# Main functions for Django
def get_current_aqi(city="Delhi"):
    """Get current AQI"""
    predictor = AQIMLPredictor()
    return predictor.get_current_aqi(city)


def predict_aqi(city="Delhi"):
    """Predict AQI using ML model"""
    predictor = AQIMLPredictor()
    return predictor.predict_aqi(city)


def train_model(city="Delhi"):
    """Train the model"""
    predictor = AQIMLPredictor()
    return predictor.train_model(city)


# Test
if __name__ == "__main__":
    print("="*60)
    print("AQI ML Predictor - Multi-City Random Forest Model")
    print("="*60)
    
    cities = ["Delhi", "Mumbai", "Bangalore", "Noida"]
    
    for city in cities:
        print(f"\n{'='*50}")
        print(f"Testing {city}")
        print('='*50)
        
        # Get predictions
        results = predict_aqi(city=city)
        
        if results:
            print(f"\nNext 5 hours forecast (ML-based):")
            for r in results[:5]:
                print(f"{r['time']} - AQI: {r['aqi']} ({r['category']}) | Temp: {r['temp']}°C | Wind: {r['wind']}m/s")
        else:
            print(f"No forecast data available for {city}")