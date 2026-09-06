# AirBuddy 🌍

> AI-powered air-quality monitoring, prediction, pollution-source
> detection, and personalized health insights.

AirBuddy is a Django-based air-pollution intelligence platform designed
to help users understand current and future air quality, identify
possible pollution sources from images, and receive personalized health
guidance.

The project combines real-time AQI data, city-specific machine-learning
models, computer vision/YOLO object detection, weather information, user
health profiles, and policy simulation into a single web platform.

## ✨ Key Features

-   **Real-time AQI monitoring** using the World Air Quality Index
    (WAQI) API.
-   **Multi-city AQI forecasting** using city-specific machine-learning
    models.
-   **AQI prediction** through a Python ML prediction module.
-   **Pollution-source detection from images** using YOLOv8.
-   Detects pollution-related objects such as cars, trucks, buses,
    motorcycles, bicycles, and trains.
-   Estimates the potential AQI impact of detected traffic/heavy
    vehicles.
-   **Weather forecast integration** using OpenWeather.
-   **Personalized health recommendations** based on AQI, location, risk
    level, and the user's health profile.
-   **AQI categories and risk levels** for easier interpretation.
-   **Policy simulation** for evaluating pollution-control measures such
    as traffic control, industrial control, construction regulation,
    firecracker bans, and crop-burning control.
-   **User registration and health profiles** for personalized
    recommendations.
-   Django templates and database-backed application architecture.

## 🧠 How AirBuddy Works

The overall flow is:

``` text
User
  │
  ▼
Django Web Application
  │
  ├── Current AQI ───────────────► WAQI API
  │
  ├── Weather Information ───────► OpenWeather API
  │
  ├── AQI Forecast ──────────────► City-specific ML Model
  │
  ├── Image Analysis ────────────► YOLOv8
  │                                  │
  │                                  ▼
  │                          Pollution-source analysis
  │
  ├── User Health Profile
  │          │
  │          ▼
  │   Personalized Health Advice
  │
  └── Policy Simulation
             │
             ▼
       Estimated AQI impact
```

## 🤖 Machine Learning

AirBuddy contains a dedicated AQI prediction module in
`main/aqi_predictor.py`.

The predictor:

1.  Gets current AQI information for a selected city.
2.  Loads a city-specific trained model when available.
3.  Uses stored model/scaler files for prediction.
4.  Produces future AQI predictions.
5.  Can train and save models for supported cities.

The repository also contains multiple pre-trained `.pkl` models under
`ml_models/`, including models for locations such as:

-   Ahmedabad
-   Chennai
-   Chhindwara Nagar Tahsil
-   Delhi
-   Ghaziabad
-   Gurgoan
-   Mohkhed
-   Mumbai
-   Nagpur
-   Noida
-   Patna
-   Poonam Sagar
-   Pune
-   Rohini
-   Shanti Park

A TensorFlow/Keras model (`model.h5`) is also included in the ML-model
directory.

## 👁️ Computer Vision & Pollution Detection

AirBuddy includes a YOLOv8-based pollution-source detector in:

``` text
main/yolo_detector.py
```

The detector uses the Ultralytics YOLO implementation and identifies
objects that may be associated with pollution, particularly road traffic
and heavy vehicles.

Supported pollution-related classes include:

-   Car
-   Truck
-   Bus
-   Motorcycle
-   Bicycle
-   Train

The detector calculates:

-   Number of detected vehicles
-   Number of heavy vehicles
-   Estimated pollution impact
-   Estimated AQI rise
-   Potential pollution source

Example flow:

``` text
Input Image
     │
     ▼
YOLOv8 Object Detection
     │
     ▼
Vehicle / Heavy Vehicle Count
     │
     ▼
Pollution Impact Estimation
     │
     ▼
Estimated AQI Rise
```

> **Note:** The AQI impact values produced by the detector are
> project-level estimates used for analysis; they should not be
> interpreted as official environmental measurements.

## 📊 AQI & Health Insights

The application uses AQI ranges to classify air-quality conditions and
generate appropriate recommendations.

The forecasting/health workflow considers information such as:

-   Current AQI
-   Forecasted AQI
-   Peak AQI
-   Lowest AQI
-   Average AQI
-   User location
-   User risk level
-   Relevant health conditions

This allows the application to provide context-aware guidance, such as
recommending safer times for outdoor activity when air quality is
expected to be better.

## 🏛️ Pollution Policy Simulation

AirBuddy also provides a policy-simulation component.

The application can simulate pollution-control measures such as:

-   Traffic Control / Odd-Even
-   Industrial Control
-   Construction Regulation
-   Firecracker Ban
-   Crop Burning Control

The simulation estimates:

-   AQI before intervention
-   AQI after intervention
-   Percentage reduction
-   Estimated health benefit
-   Estimated implementation cost
-   Number of policies applied
-   Number of affected areas

This component is intended as a decision-support simulation rather than
an official environmental policy model.

## 🏗️ Project Structure

``` text
AirBuddy_TeamReAL/
│
├── main/
│   ├── migrations/
│   ├── management/
│   ├── templates/
│   ├── templatetags/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   ├── aqi_predictor.py
│   ├── cv_aqi_detector.py
│   ├── enhanced_aqi_detector.py
│   ├── yolo_detector.py
│   └── aqi_model.pkl
│
├── ml_models/
│   ├── aqi_model_ahmedabad.pkl
│   ├── aqi_model_chennai.pkl
│   ├── aqi_model_delhi.pkl
│   ├── aqi_model_mumbai.pkl
│   ├── aqi_model_nagpur.pkl
│   ├── aqi_model_noida.pkl
│   ├── aqi_model_pune.pkl
│   ├── ...
│   └── model.h5
│
├── pollution_platform/
│   └── Django project configuration
│
├── aqi_images/
│   └── uploaded/generated AQI-related images
│
├── db.sqlite3
├── manage.py
└── requirements.txt
```

## 🛠️ Technology Stack

### Backend

-   Python
-   Django 3.2
-   Django REST Framework

### Machine Learning

-   scikit-learn
-   NumPy
-   Pandas
-   Joblib
-   TensorFlow / Keras

### Computer Vision

-   OpenCV
-   Ultralytics YOLOv8
-   Pillow

### Data & APIs

-   WAQI API for air-quality information
-   OpenWeather API for weather forecasts

### Frontend

-   Django Templates
-   HTML/CSS
-   Bootstrap/Crispy Forms
-   JavaScript

### Database

-   SQLite for the included development database
-   PostgreSQL support is available through the project's
    dependencies/configuration

The repository's `requirements.txt` contains the project's pinned Python
dependencies, including Django, Django REST Framework, scikit-learn,
OpenCV, TensorFlow, PyTorch, Ultralytics, Streamlit, and related
packages.

## ⚙️ Installation

### 1. Clone the repository

``` bash
git clone https://github.com/theteamreal/AirBuddy_TeamReAL.git
cd AirBuddy_TeamReAL
```

### 2. Create a virtual environment

Windows:

``` bash
python -m venv venv
venv\Scripts\activate
```

Linux/macOS:

``` bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

``` bash
pip install -r requirements.txt
```

> The repository contains older pinned ML packages, so using a
> compatible Python environment may be necessary. If dependency
> installation fails, check the versions in `requirements.txt` before
> upgrading packages individually.

### 4. Configure environment variables

The application uses external services for AQI and weather data.
Configure the required API credentials in the project's
environment/settings configuration.

Typical variables include:

``` env
AQI_API_TOKEN=your_waqi_token
WEATHER_API_KEY=your_openweather_key
```

Do not commit real API keys or secrets to GitHub.

### 5. Run database migrations

``` bash
python manage.py migrate
```

### 6. Start the development server

``` bash
python manage.py runserver
```

Then open:

``` text
http://127.0.0.1:8000/
```

## 🔐 User & Health Profile

AirBuddy supports user registration and health-profile information.

The profile can be used to personalize air-quality recommendations
according to factors such as the user's risk level and relevant health
conditions.

Because health information can be sensitive, production deployments
should use appropriate authentication, access controls, secure storage,
and privacy practices.

## 📁 Important Files

  -----------------------------------------------------------------------
  File                                Purpose
  ----------------------------------- -----------------------------------
  `manage.py`                         Django command-line entry point

  `pollution_platform/`               Main Django project configuration

  `main/views.py`                     Application views and platform
                                      logic

  `main/models.py`                    Database models

  `main/forms.py`                     User/application forms

  `main/aqi_predictor.py`             AQI data retrieval and ML
                                      prediction

  `main/yolo_detector.py`             YOLOv8 pollution-source detection

  `main/cv_aqi_detector.py`           Computer-vision AQI detection
                                      functionality

  `main/enhanced_aqi_detector.py`     Enhanced AQI detection
                                      functionality

  `ml_models/`                        City-specific trained ML models

  `db.sqlite3`                        Included SQLite development
                                      database

  `requirements.txt`                  Python dependency list
  -----------------------------------------------------------------------

## 🚀 Future Improvements

Possible improvements include:

-   Real-time sensor/IoT integration
-   More robust time-series forecasting models
-   Automated model retraining with fresh AQI data
-   Better calibration of image-based pollution estimates
-   Integration with official government air-quality datasets
-   Interactive maps and geospatial pollution analysis
-   Mobile application
-   Push notifications for AQI alerts
-   More cities and regional models
-   Production-grade authentication and secret management
-   Automated testing and CI/CD
-   Deployment using Docker/cloud infrastructure

## ⚠️ Disclaimer

AirBuddy is an educational/software project for air-quality analysis and
decision support.

Predicted AQI values, image-based pollution estimates, health
recommendations, and policy-simulation results should not be treated as
official environmental measurements, medical advice, or government
policy recommendations.

For health or safety decisions, consult authoritative environmental and
medical sources.

## 👥 Team

**Team ReAL**
**Team Memebers:**
    Jemit Malnika
    Tanish Belel
    Darsh Jilka

Project: **AirBuddy**

Repository: https://github.com/theteamreal/AirBuddy_TeamReAL
