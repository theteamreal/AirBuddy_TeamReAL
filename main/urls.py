from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Home and Auth
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='main/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Policies
    path('policies/', views.policies, name='policies'),
    path('policies/create/', views.create_policy, name='create_policy'),
    path('policies/<int:policy_id>/vote/', views.vote_policy, name='vote_policy'),
    
    # AQI Features
    path('aqi-map/', views.aqi_map, name='aqi_map'),
    
    
    # Policy Simulation
    path('policy-simulation/', views.policy_simulation, name='policy_simulation'),
      # Multi-city forecast URLs
    path('forecasts/', views.forecasts, name='forecasts'),
    path('forecasts/<str:city>/', views.forecasts, name='forecasts_city'),
    
    # Admin model training
    path('retrain-model/', views.retrain_model, name='retrain_model'),
    
    # API endpoints (optional)
    path('api/aqi/', views.get_city_aqi_api, name='api_city_aqi'),
    path('api/forecast/', views.get_city_forecast_api, name='api_city_forecast'),
]