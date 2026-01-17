from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import snap_to_aqi_enhanced, snap_result_enhanced #darsh

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
     path('policies/', views.policies, name='policies'),
    path('policies/create/', views.create_policy, name='create_policy'),
    path('policies/<int:policy_id>/vote/', views.vote_policy, name='vote_policy'),
    # darsh - Added URL for adding comments to policies
    path('policies/<int:policy_id>/comment/', views.comment_policy, name='comment_policy'),
    # darsh - Added URLs for deleting policies and comments
    path('policies/<int:policy_id>/delete/', views.delete_policy, name='delete_policy'),
    path('comments/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
      # Multi-city forecast URLs
    path('forecasts/', views.forecasts, name='forecasts'),
    path('forecasts/<str:city>/', views.forecasts, name='forecasts_city'),
    
    # Admin model training
    path('retrain-model/', views.retrain_model, name='retrain_model'),
    path('live-aqi/', views.live_aqi, name='live_aqi'),
    
    # API endpoints (optional)
    path('api/aqi/', views.get_city_aqi_api, name='api_city_aqi'),
    path('api/forecast/', views.get_city_forecast_api, name='api_city_forecast'),
    path('policy-simulation/', views.policy_simulation, name='policy_simulation'),
     path('api/ai-health-alerts/', views.generate_ai_health_alerts, name='generate_ai_health_alerts'),
    path('api/test-ai-health-alerts/', views.test_ai_health_alerts, name='test_ai_health_alerts'),
     # AQI Features
    path('aqi-map/', views.aqi_map, name='aqi_map'),
    path('heatmap/', views.aqi_heatmap, name='aqi_heatmap'),
    # Snap-to-AQI Feature -darsh 
    path('snap-to-aqi/', views.snap_to_aqi, name='snap_to_aqi'),
    path('snap-to-aqi/result/<int:prediction_id>/', views.snap_result, name='snap_result'),
    path('snap-to-aqi/history/', views.snap_history, name='snap_history'),

     # Live Camera URLs (NEW - ADD THESE)
    path('live-camera/', views.live_camera, name='live_camera'),
    path('api/analyze-frame/', views.analyze_camera_frame, name='analyze_camera_frame'),
    path('api/capture-snapshot/', views.capture_live_snapshot, name='capture_live_snapshot'),

    # Enhanced YOLO detection URLs
    path('snap-enhanced/', snap_to_aqi_enhanced, name='snap_to_aqi_enhanced'),
    path('snap-result-enhanced/<int:prediction_id>/', snap_result_enhanced, name='snap_result_enhanced'),
    #path('api/detect-vehicles/', detect_vehicles_api, name='detect_vehicles_api'),
    
]