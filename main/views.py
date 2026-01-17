# Django core imports
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Max

# Python standard library
from datetime import datetime, timedelta
import random
import json
import traceback
import base64
import os
from io import BytesIO

# Third-party libraries
import requests
import numpy as np
import cv2
from PIL import Image as PILImage

# Local app imports - models
from .models import (
    UserHealthProfile,
    Policy,
    PolicyVote,
    PolicyComment,
    AQIData,
    AQIForecast,
    ImageAQIPrediction
)

# Local app imports - forms
from .forms import HealthProfileForm, PolicyForm

# Local app imports - utilities
from .aqi_predictor import predict_aqi, get_current_aqi, train_model
from .cv_aqi_detector import get_detector
from .enhanced_aqi_detector import get_enhanced_detector
def home(request):
    """Landing page - Capture The Flag theme"""
    return render(request, 'home.html')


def register(request):
    """User registration with health questionnaire"""
    if request.method == 'POST':
        user_form = UserCreationForm(request.POST)
        health_form = HealthProfileForm(request.POST)
        
        if user_form.is_valid() and health_form.is_valid():
            user = user_form.save()
            health_profile = health_form.save(commit=False)
            health_profile.user = user
            health_profile.save()
            
            login(request, user)
            messages.success(request, 'Registration successful! Welcome to the platform.')
            return redirect('dashboard')
    else:
        user_form = UserCreationForm()
        health_form = HealthProfileForm()
    
    return render(request, 'register.html', {
        'user_form': user_form,
        'health_form': health_form
    })


@login_required
def dashboard(request):
    """Personalized dashboard based on health profile"""
    health_profile = request.user.health_profile
    
    # Get AQI data for user's location
    location_aqi = None
    if health_profile.location:
        location_aqi = AQIData.objects.filter(
            area__icontains=health_profile.location
        ).first()
    
    # Get general Delhi NCR AQI data
    recent_aqi = AQIData.objects.all()[:10]
    
    # Get forecasts
    forecasts = AQIForecast.objects.filter(
        forecast_date__gte=datetime.now()
    )[:5]
    
    # Get personalized health alerts
    alerts = get_health_alerts(health_profile, location_aqi)
    
    # Get trending policies
    trending_policies = Policy.objects.filter(status='PROPOSED')[:5]
    
    context = {
        'health_profile': health_profile,
        'location_aqi': location_aqi,
        'recent_aqi': recent_aqi,
        'forecasts': forecasts,
        'alerts': alerts,
        'trending_policies': trending_policies,
    }
    
    return render(request, 'dashboard.html', context)


def get_health_alerts(health_profile, aqi_data):
    """Generate personalized health alerts"""
    alerts = []
    
    if not aqi_data:
        return alerts
    
    aqi_value = aqi_data.aqi_value
    
    if health_profile.risk_level == 'SEVERE':
        if aqi_value > 150:
            alerts.append({
                'level': 'danger',
                'message': '⚠️ SEVERE RISK: Stay indoors. Avoid all outdoor activities. Use air purifier.'
            })
        elif aqi_value > 100:
            alerts.append({
                'level': 'warning',
                'message': '⚠️ HIGH RISK: Limit outdoor exposure. Wear N95 mask if going out.'
            })
    
    elif health_profile.risk_level == 'HIGH':
        if aqi_value > 200:
            alerts.append({
                'level': 'danger',
                'message': '⚠️ Stay indoors. Avoid physical activities outdoors.'
            })
        elif aqi_value > 150:
            alerts.append({
                'level': 'warning',
                'message': '⚠️ Reduce outdoor activities. Use mask when going out.'
            })
    
    elif health_profile.risk_level == 'MODERATE':
        if aqi_value > 200:
            alerts.append({
                'level': 'warning',
                'message': '⚠️ Consider staying indoors during peak pollution hours.'
            })
    
    # Add source-specific alerts
    if aqi_data.traffic_contribution > 40:
        alerts.append({
            'level': 'info',
            'message': f'🚗 Traffic is the main pollution source ({aqi_data.traffic_contribution:.1f}%). Avoid main roads.'
        })
    
    if aqi_data.crop_burning_contribution > 30:
        alerts.append({
            'level': 'info',
            'message': f'🔥 Crop burning contributing {aqi_data.crop_burning_contribution:.1f}% to pollution.'
        })
    
    return alerts


@login_required
def policies(request):
    """Policy listing and creation"""
    policy_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    
    # darsh - Added prefetch_related for comments to load comments with policies
    policies_list = Policy.objects.prefetch_related('comments', 'comments__user').all()
    
    if policy_type:
        policies_list = policies_list.filter(policy_type=policy_type)
    if status:
        policies_list = policies_list.filter(status=status)
    
    # Get user's votes
    user_votes = {}
    if request.user.is_authenticated:
        votes = PolicyVote.objects.filter(user=request.user)
        user_votes = {vote.policy_id: vote.vote for vote in votes}
    
    context = {
        'policies': policies_list,
        'user_votes': user_votes,
        'policy_types': Policy.POLICY_TYPES,
        'selected_type': policy_type,
        'selected_status': status,
    }
    
    return render(request, 'policies.html', context)


@login_required
def create_policy(request):
    """Create new policy proposal"""
    if request.method == 'POST':
        form = PolicyForm(request.POST)
        if form.is_valid():
            policy = form.save(commit=False)
            policy.proposed_by = request.user
            policy.save()
            messages.success(request, 'Policy proposed successfully!')
            return redirect('policies')
    else:
        form = PolicyForm()
    
    return render(request, 'create_policy.html', {'form': form})


@login_required
def vote_policy(request, policy_id):
    """Vote on a policy (AJAX)"""
    if request.method == 'POST':
        policy = get_object_or_404(Policy, id=policy_id)
        vote_type = request.POST.get('vote')
        
        if vote_type not in ['AGREE', 'DISAGREE']:
            return JsonResponse({'error': 'Invalid vote'}, status=400)
        
        # Remove existing vote if any
        existing_vote = PolicyVote.objects.filter(user=request.user, policy=policy).first()
        
        if existing_vote:
            # Remove old vote count
            if existing_vote.vote == 'AGREE':
                policy.agree_count -= 1
            else:
                policy.disagree_count -= 1
            
            # Update vote
            existing_vote.vote = vote_type
            existing_vote.save()
        else:
            # Create new vote
            existing_vote = PolicyVote.objects.create(
                user=request.user,
                policy=policy,
                vote=vote_type
            )
        
        # Update new vote count
        if vote_type == 'AGREE':
            policy.agree_count += 1
        else:
            policy.disagree_count += 1
        
        policy.save()
        
        return JsonResponse({
            'success': True,
            'agree_count': policy.agree_count,
            'disagree_count': policy.disagree_count,
            'agreement_percentage': policy.agreement_percentage,
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


# darsh - Added comment_policy view for adding comments to policies
@login_required
def comment_policy(request, policy_id):
    """Add comment to a policy (AJAX)"""
    if request.method == 'POST':
        policy = get_object_or_404(Policy, id=policy_id)
        comment_text = request.POST.get('comment', '').strip()
        
        if not comment_text:
            return JsonResponse({'error': 'Comment cannot be empty'}, status=400)
        
        # Create comment
        comment = PolicyComment.objects.create(
            user=request.user,
            policy=policy,
            comment=comment_text
        )
        
        return JsonResponse({
            'success': True,
            'comment_id': comment.id,
            'username': request.user.username,
            'comment': comment_text,
            'created_at': comment.created_at.strftime('%d %b %Y, %H:%M'),
            'comment_count': policy.comments.count()
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


# darsh - Added delete_policy view for policy owners to delete their policies
@login_required
def delete_policy(request, policy_id):
    """Delete a policy (only by owner)"""
    if request.method == 'POST':
        policy = get_object_or_404(Policy, id=policy_id)
        
        # Check if user is the owner
        if policy.proposed_by != request.user:
            return JsonResponse({'error': 'You can only delete your own policies'}, status=403)
        
        policy.delete()
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


# darsh - Added delete_comment view for comment owners to delete their comments
@login_required
def delete_comment(request, comment_id):
    """Delete a comment (only by owner)"""
    if request.method == 'POST':
        comment = get_object_or_404(PolicyComment, id=comment_id)
        
        # Check if user is the owner
        if comment.user != request.user:
            return JsonResponse({'error': 'You can only delete your own comments'}, status=403)
        
        policy_id = comment.policy.id
        comment.delete()
        
        # Get updated comment count
        comment_count = PolicyComment.objects.filter(policy_id=policy_id).count()
        
        return JsonResponse({'success': True, 'comment_count': comment_count})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def aqi_map(request):
    """AQI heatmap and visualization"""
    areas = AQIData.objects.values('area').distinct()
    
    selected_area = request.GET.get('area', '')
    
    if selected_area:
        aqi_data = AQIData.objects.filter(area=selected_area)[:24]
    else:
        aqi_data = AQIData.objects.all()[:20]
    
    context = {
        'areas': areas,
        'aqi_data': aqi_data,
        'selected_area': selected_area,
    }
    
    return render(request, 'aqi_map.html', context)


@login_required
def forecasts(request):
    """AQI forecasts for next 24-72 hours"""
    forecasts = AQIForecast.objects.filter(
        forecast_date__gte=datetime.now(),
        forecast_date__lte=datetime.now() + timedelta(hours=72)
    )
    
    context = {
        'forecasts': forecasts,
    }
    
    return render(request, 'forecasts.html', context)


# darsh - Enhanced Policy Impact Simulator with real-time data and scientific calculations
@login_required
def policy_simulation(request):
    """Simulate policy impact using real AQI data and scientific impact models"""
    
    # Get all unique areas with their latest AQI data
    areas_data = {}
    for area in AQIData.objects.values('area').distinct():
        latest = AQIData.objects.filter(area=area['area']).order_by('-timestamp').first()
        if latest:
            areas_data[area['area']] = {
                'aqi': latest.aqi_value,
                'pm25': latest.pm25,
                'pm10': latest.pm10,
                'traffic': latest.traffic_contribution,
                'industrial': latest.industrial_contribution,
                'crop_burning': latest.crop_burning_contribution,
                'construction': latest.construction_contribution,
                'other': latest.other_contribution,
            }
    
    # Scientific impact percentages based on research (source contribution reduction effectiveness)
    # darsh - These are based on Delhi NCR pollution studies
    POLICY_IMPACT = {
        'TRAFFIC': {
            'name': 'Traffic Control (Odd-Even)',
            'source': 'traffic',
            'min_reduction': 0.10,  # 10% of traffic contribution
            'max_reduction': 0.25,  # 25% of traffic contribution
            'health_factor': 1.2,   # Health improvement multiplier
            'cost_per_day': 50000000,  # ₹5 Cr/day implementation cost
        },
        'INDUSTRY': {
            'name': 'Industrial Control',
            'source': 'industrial',
            'min_reduction': 0.15,
            'max_reduction': 0.35,
            'health_factor': 1.5,
            'cost_per_day': 100000000,
        },
        'CONSTRUCTION': {
            'name': 'Construction Regulation',
            'source': 'construction',
            'min_reduction': 0.20,
            'max_reduction': 0.40,
            'health_factor': 1.1,
            'cost_per_day': 30000000,
        },
        'FIRECRACKER': {
            'name': 'Firecracker Ban',
            'source': 'other',
            'min_reduction': 0.30,
            'max_reduction': 0.50,
            'health_factor': 1.8,
            'cost_per_day': 10000000,
        },
        'CROP_BURNING': {
            'name': 'Crop Burning Control',
            'source': 'crop_burning',
            'min_reduction': 0.25,
            'max_reduction': 0.45,
            'health_factor': 2.0,
            'cost_per_day': 200000000,
        },
    }
    
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        
        selected_policies = data.get('policies', [])
        implementation_level = float(data.get('implementation_level', 75)) / 100
        duration_days = int(data.get('duration', 30))
        selected_area = data.get('area', 'all')
        
        # Get areas to simulate
        if selected_area == 'all':
            simulation_areas = areas_data
        else:
            simulation_areas = {selected_area: areas_data.get(selected_area, {})}
        
        results = []
        total_before_aqi = 0
        total_after_aqi = 0
        total_reduction = 0
        total_health_benefit = 0
        total_cost = 0
        
        for area_name, area_info in simulation_areas.items():
            if not area_info:
                continue
                
            before_aqi = area_info['aqi']
            aqi_reduction = 0
            
            # Calculate cumulative impact from all selected policies
            for policy_type in selected_policies:
                if policy_type in POLICY_IMPACT:
                    impact = POLICY_IMPACT[policy_type]
                    source = impact['source']
                    source_contribution = area_info.get(source, 0)
                    
                    # Calculate reduction based on implementation level
                    reduction_rate = impact['min_reduction'] + (impact['max_reduction'] - impact['min_reduction']) * implementation_level
                    
                    # AQI reduction = source contribution * reduction rate
                    policy_aqi_reduction = (source_contribution / 100) * before_aqi * reduction_rate
                    aqi_reduction += policy_aqi_reduction
                    
                    # Add to total cost
                    total_cost += impact['cost_per_day'] * duration_days * implementation_level
            
            after_aqi = max(50, before_aqi - aqi_reduction)  # Minimum AQI of 50 (good air)
            reduction_percent = ((before_aqi - after_aqi) / before_aqi) * 100 if before_aqi > 0 else 0
            
            # Health benefit calculation (lives saved per year per 10 AQI reduction)
            # Based on WHO data: ~1.5% mortality reduction per 10 μg/m³ PM2.5 reduction
            health_benefit = (before_aqi - after_aqi) * 0.15 * (duration_days / 365) * 1000  # Per million population
            
            results.append({
                'area': area_name,
                'before_aqi': round(before_aqi),
                'after_aqi': round(after_aqi),
                'reduction': round(reduction_percent, 1),
                'health_benefit': round(health_benefit),
            })
            
            total_before_aqi += before_aqi
            total_after_aqi += after_aqi
            total_health_benefit += health_benefit
        
        num_areas = len(results) if results else 1
        avg_before = round(total_before_aqi / num_areas)
        avg_after = round(total_after_aqi / num_areas)
        avg_reduction = round(((avg_before - avg_after) / avg_before) * 100, 1) if avg_before > 0 else 0
        
        # Calculate AQI categories
        def get_category(aqi):
            if aqi <= 50: return 'Good'
            elif aqi <= 100: return 'Satisfactory'
            elif aqi <= 200: return 'Moderate'
            elif aqi <= 300: return 'Poor'
            elif aqi <= 400: return 'Very Poor'
            else: return 'Severe'
        
        return JsonResponse({
            'success': True,
            'summary': {
                'avg_before_aqi': avg_before,
                'avg_after_aqi': avg_after,
                'avg_reduction': avg_reduction,
                'before_category': get_category(avg_before),
                'after_category': get_category(avg_after),
                'total_health_benefit': round(total_health_benefit),
                'total_cost_crores': round(total_cost / 10000000, 2),
                'duration_days': duration_days,
                'implementation_level': int(implementation_level * 100),
                'policies_applied': len(selected_policies),
                'areas_affected': num_areas,
            },
            'area_results': sorted(results, key=lambda x: x['reduction'], reverse=True)[:10],
        })
    
    # GET request - render the simulation page
    policies = Policy.objects.filter(status='PROPOSED')
    
    # Calculate current average AQI
    avg_aqi = sum([a['aqi'] for a in areas_data.values()]) / len(areas_data) if areas_data else 0
    
    context = {
        'policies': policies,
        'areas': list(areas_data.keys()),
        'areas_data': areas_data,
        'current_avg_aqi': round(avg_aqi),
        'policy_types': [
            {'code': 'TRAFFIC', 'name': 'Traffic Control (Odd-Even)', 'icon': '🚗'},
            {'code': 'INDUSTRY', 'name': 'Industrial Control', 'icon': '🏭'},
            {'code': 'CONSTRUCTION', 'name': 'Construction Regulation', 'icon': '🏗️'},
            {'code': 'FIRECRACKER', 'name': 'Firecracker Ban', 'icon': '🎆'},
            {'code': 'CROP_BURNING', 'name': 'Crop Burning Control', 'icon': '🌾'},
        ],
    }
    
    return render(request, 'policy_simulation.html', context)

def fetch_live_aqi(city):
    try:
        url = f"https://api.waqi.info/feed/{city}/?token={settings.AQI_API_TOKEN}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get("status") != "ok":
            return None

        iaqi = data["data"].get("iaqi", {})

        return {
            "aqi": data["data"]["aqi"],
            "pm25": iaqi.get("pm25", {}).get("v"),
            "pm10": iaqi.get("pm10", {}).get("v"),
            "no2": iaqi.get("no2", {}).get("v"),
            "co": iaqi.get("co", {}).get("v"),
            "time": data["data"]["time"]["s"],
            "city": data["data"]["city"]["name"]
        }
    except Exception:
        return None

def live_aqi(request):
    user = request.user

    city = "delhi"  # default fallback

    if hasattr(user, "health_profile") and user.health_profile:
        city = user.health_profile.location or city

    data = fetch_live_aqi(city)

    if not data:
        return JsonResponse({"error": "AQI data unavailable"}, status=503)

    return JsonResponse(data)

def home(request):
    """Landing page - Capture The Flag theme"""
    return render(request, 'home.html')


def register(request):
    """User registration with health questionnaire"""
    if request.method == 'POST':
        user_form = UserCreationForm(request.POST)
        health_form = HealthProfileForm(request.POST)
        
        if user_form.is_valid() and health_form.is_valid():
            user = user_form.save()
            health_profile = health_form.save(commit=False)
            health_profile.user = user
            health_profile.save()
            
            login(request, user)
            messages.success(request, 'Registration successful! Welcome to the platform.')
            return redirect('dashboard')
    else:
        user_form = UserCreationForm()
        health_form = HealthProfileForm()
    
    return render(request, 'register.html', {
        'user_form': user_form,
        'health_form': health_form
    })


@login_required
def forecasts(request):
    """Show AQI forecasts using ML model - supports any city"""
    
    # Default city from user profile
    default_city = "Delhi"
    try:
        health_profile = request.user.health_profile
        if health_profile.location:
            default_city = health_profile.location
    except:
        pass
    
    # Get city from query parameter or use default
    city = request.GET.get('city', default_city).strip()
    
    # If no city provided, use default
    if not city:
        city = default_city
    
    try:
        # Get current AQI - THIS IS THE EXACT VALUE
        current_aqi_data = get_current_aqi(city)
        current_aqi = current_aqi_data.get('aqi', 0)
        
        # Ensure current_aqi is an integer for exact display
        current_aqi = int(current_aqi)
        current_aqi_data['aqi'] = current_aqi
        
        # Get ML predictions (anchored to current AQI)
        predictions = predict_aqi(city=city)
        
        # Popular cities for quick selection
        major_cities = [
            'Delhi', 'Mumbai', 'Bangalore', 'Kolkata', 'Chennai',
            'Hyderabad', 'Pune', 'Ahmedabad', 'Noida', 'Gurgaon',
            'Chandigarh', 'Jaipur', 'Lucknow', 'Kanpur', 'Nagpur',
            'Indore', 'Bhopal', 'Patna', 'Rohini', 'Ghaziabad'
        ]
        
        context = {
            'forecasts': predictions,
            'current_aqi': current_aqi,
            'current_aqi_data': current_aqi_data,
            'city': city,
            'available_cities': major_cities,
            'model_type': 'Random Forest ML Model'
        }
        
        return render(request, 'forecasts.html', context)
        
    except Exception as e:
        print(f"Error in forecasts view for {city}: {str(e)}")
        messages.error(request, f'Unable to get forecast for {city}. Please try another city.')
        
        context = {
            'forecasts': [],
            'current_aqi': 0,
            'current_aqi_data': {'city': city, 'time': 'N/A'},
            'city': city,
            'available_cities': ['Delhi', 'Mumbai', 'Bangalore'],
            'model_type': 'Random Forest ML Model'
        }
        
        return render(request, 'forecasts.html', context)


@login_required
def retrain_model(request):
    """Admin view to retrain the model for specific city"""
    
    if not request.user.is_staff:
        messages.error(request, 'Only administrators can retrain models.')
        return redirect('forecasts')
    
    if request.method == 'POST':
        city = request.POST.get('city', 'Delhi').strip()
        
        try:
            score = train_model(city)
            messages.success(
                request, 
                f'✓ Model retrained successfully for {city}. R² Score: {score:.4f}'
            )
        except Exception as e:
            messages.error(request, f'Failed to retrain model for {city}: {str(e)}')
        
        return redirect('forecasts')
    
    # GET request - show retrain form
    major_cities = [
        'Delhi', 'Mumbai', 'Bangalore', 'Kolkata', 'Chennai',
        'Hyderabad', 'Pune', 'Ahmedabad', 'Noida', 'Gurgaon'
    ]
    
    context = {
        'available_cities': major_cities
    }
    
    return render(request, 'retrain_model.html', context)



from django.http import JsonResponse

@login_required
def get_city_aqi_api(request):
    """API endpoint to get AQI for any city"""
    city = request.GET.get('city', 'Delhi')
    
    try:
        aqi_data = get_current_aqi(city)
        return JsonResponse({
            'status': 'success',
            'data': aqi_data
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


@login_required
def get_city_forecast_api(request):
    """API endpoint to get forecast for any city"""
    city = request.GET.get('city', 'Delhi')
    
    try:
        predictions = predict_aqi(city=city)
        return JsonResponse({
            'status': 'success',
            'city': city,
            'forecasts': predictions
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
    



@csrf_exempt  # Add this if you're testing from frontend
@login_required
def generate_ai_health_alerts(request):
    """Generate AI-powered health alerts using Groq API"""
    
    # Add logging to debug
    print("🔵 generate_ai_health_alerts called")
    print(f"🔵 Request method: {request.method}")
    print(f"🔵 Request body: {request.body}")
    
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Only POST requests allowed'
        }, status=405)
    
    try:
        # Get request data
        data = json.loads(request.body) if request.body else {}
        print(f"🔵 Parsed data: {data}")
        
        city = data.get('city', 'Delhi')
        current_aqi = float(data.get('currentAQI', 0))
        peak_aqi = float(data.get('peakAQI', 0))
        min_aqi = float(data.get('minAQI', 0))
        avg_aqi = float(data.get('avgAQI', 0))
        peak_time = data.get('peakTime', 'Unknown')
        best_time = data.get('bestTime', 'Unknown')
        has_sudden_spike = data.get('hasSuddenSpike', False)
        max_spike = float(data.get('maxSpike', 0))
        
        # Get user's health profile
        health_profile = request.user.health_profile
        
        # Build health conditions list
        conditions = []
        if health_profile.has_respiratory_issues:
            conditions.append('Respiratory issues (Asthma/COPD)')
        if health_profile.has_heart_disease:
            conditions.append('Heart disease')
        if health_profile.has_allergies:
            conditions.append('Allergies')
        if health_profile.is_elderly:
            conditions.append('Elderly (60+)')
        if health_profile.is_child:
            conditions.append('Child (under 12)')
        if health_profile.is_pregnant:
            conditions.append('Pregnant')
        
        conditions_text = ', '.join(conditions) if conditions else 'No pre-existing conditions'
        
        # Get AQI category
        def get_aqi_category(aqi):
            if aqi <= 50:
                return 'Good'
            elif aqi <= 100:
                return 'Moderate'
            elif aqi <= 200:
                return 'Unhealthy for Sensitive Groups'
            elif aqi <= 300:
                return 'Unhealthy'
            elif aqi <= 400:
                return 'Very Unhealthy'
            return 'Hazardous'
        
        # Build the prompt
        spike_warning = f"\n- Warning: Sudden AQI spike expected (+{max_spike:.0f} points)" if has_sudden_spike else ""
        
        prompt = f"""You are an expert air quality health advisor AI specializing in personalized health recommendations for air pollution exposure.

CRITICAL: Respond ONLY with valid JSON. No markdown, no backticks, no explanations.

User Health Profile:
- Location: {city}
- Current AQI: {current_aqi:.0f} ({get_aqi_category(current_aqi)})
- Peak AQI (next 24h): {peak_aqi:.0f} at {peak_time}
- Lowest AQI (next 24h): {min_aqi:.0f} at {best_time}
- Average AQI (next 24h): {avg_aqi:.0f}
- Risk Level: {health_profile.risk_level}
- Health Conditions: {conditions_text}{spike_warning}

Generate 4-7 personalized health alerts with varying severity levels:
- level: "danger" (critical), "warning" (significant risk), "info" (awareness), "success" (favorable)
- icon: relevant emoji (🚨, ⚠️, 🫁, ❤️, 👶, 🤰, 💊, ✅, 🌟)
- title: concise alert title (max 60 characters)
- message: detailed 2-3 sentence explanation of health risk/benefit
- actions: array of 3-4 specific, actionable recommendations

Guidelines:
- For SEVERE risk + high AQI (>200): Include critical "stay indoors" alert
- For specific conditions: Include condition-specific alerts
- Include timing recommendations (best/worst times for outdoor activity)
- Add medication reminders for high-risk individuals when AQI > 150
- Balance warnings with positive guidance

Return ONLY this JSON structure (no other text):
{{"alerts": [{{"level": "danger", "icon": "🚨", "title": "Critical Alert", "message": "Detailed explanation here.", "actions": ["Action 1", "Action 2", "Action 3"]}}]}}"""

        # Check API key
        api_key = getattr(settings, 'GROQ_API_KEY', None)
        print(f"🔵 API Key exists: {api_key is not None}")
        print(f"🔵 API Key starts with: {api_key[:10] if api_key else 'None'}...")
        
        if not api_key:
            return JsonResponse({
                'success': False,
                'error': 'GROQ_API_KEY not configured. Add it to settings.py'
            }, status=500)
        
        # Call Groq API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        payload = {
            'model': 'llama-3.3-70b-versatile',
            'messages': [
                {
                    'role': 'system',
                    'content': 'You are a health advisor AI. Always respond with valid JSON format, no markdown formatting.'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.7,
            'max_tokens': 2000,
            'response_format': {'type': 'json_object'}
        }
        
        print("🔵 Sending request to Groq API...")
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"🔵 Groq API response status: {response.status_code}")
        print(f"🔵 Groq API response: {response.text[:500]}")
        
        if response.status_code != 200:
            error_msg = response.text
            return JsonResponse({
                'success': False,
                'error': f'Groq API error ({response.status_code}): {error_msg}'
            }, status=500)
        
        response_data = response.json()
        alerts_text = response_data['choices'][0]['message']['content'].strip()
        
        print(f"🔵 AI Response: {alerts_text[:200]}")
        
        # Clean response (remove markdown if present)
        alerts_text = alerts_text.replace('```json', '').replace('```', '').strip()
        
        # Remove any leading/trailing text before/after JSON
        start_idx = alerts_text.find('{')
        end_idx = alerts_text.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            alerts_text = alerts_text[start_idx:end_idx]
        
        # Parse JSON
        alerts_data = json.loads(alerts_text)
        
        if 'alerts' not in alerts_data or not isinstance(alerts_data['alerts'], list):
            raise ValueError('Invalid AI response format')
        
        print(f"🟢 Success! Generated {len(alerts_data['alerts'])} alerts")
        
        return JsonResponse({
            'success': True,
            'alerts': alerts_data['alerts']
        })
        
    except json.JSONDecodeError as e:
        print(f"🔴 JSON Decode Error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Failed to parse AI response: {str(e)}',
            'raw_response': alerts_text if 'alerts_text' in locals() else 'No response'
        }, status=500)
        
    except Exception as e:
        print(f"🔴 Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'Error generating health alerts: {str(e)}'
        }, status=500)


@csrf_exempt
@login_required  
def test_ai_health_alerts(request):
    """Test if Groq API is working"""
    
    print("🔵 test_ai_health_alerts called")
    
    # Check API key
    api_key = getattr(settings, 'GROQ_API_KEY', None)
    
    if not api_key:
        return JsonResponse({
            'success': False,
            'error': 'GROQ_API_KEY not found in settings.py',
            'fix': 'Add GROQ_API_KEY = "gsk_..." to your settings.py',
            'get_key': 'Get your key from https://console.groq.com/'
        })
    
    if not api_key.startswith('gsk_'):
        return JsonResponse({
            'success': False,
            'error': 'Invalid API key format',
            'fix': 'Groq API key should start with "gsk_"',
            'your_key_starts_with': api_key[:10] + '...' if len(api_key) > 10 else api_key
        })
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        payload = {
            'model': 'llama-3.3-70b-versatile',
            'messages': [
                {
                    'role': 'user',
                    'content': 'Respond with exactly this JSON: {"status": "working"}'
                }
            ],
            'max_tokens': 50,
            'temperature': 0,
            'response_format': {'type': 'json_object'}
        }
        
        print("🔵 Sending test request to Groq API...")
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=10
        )
        
        print(f"🔵 Test response status: {response.status_code}")
        print(f"🔵 Test response: {response.text}")
        
        if response.status_code == 200:
            return JsonResponse({
                'success': True,
                'message': '✅ Groq AI is working correctly!',
                'status': 'All systems operational',
                'model': 'llama-3.3-70b-versatile',
                'provider': 'Groq'
            })
        elif response.status_code == 401:
            return JsonResponse({
                'success': False,
                'error': 'Invalid API key',
                'fix': 'Get a new API key from https://console.groq.com/'
            })
        elif response.status_code == 429:
            return JsonResponse({
                'success': False,
                'error': 'Rate limit exceeded',
                'fix': 'Wait a moment and try again, or upgrade your plan'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'API returned {response.status_code}',
                'response': response.text[:300]
            })
            
    except requests.exceptions.Timeout:
        return JsonResponse({
            'success': False,
            'error': 'Request timed out',
            'fix': 'Check your internet connection'
        })
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            'success': False,
            'error': 'Connection error',
            'fix': 'Check your internet connection'
        })
    except Exception as e:
        print(f"🔴 Test Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    

@login_required
def aqi_heatmap(request):
    """
    Render the enhanced AQI heat map page
    """
    return render(request, 'aqi_heatmap.html')


@require_http_methods(["GET"])
def get_all_aqi_api(request):
    """API endpoint to get latest AQI data for all areas"""
    
    cached_data = cache.get('aqi_heatmap_data')
    if cached_data:
        print("✅ Returning cached AQI data")
        return JsonResponse(cached_data, safe=False)
    
    try:
        print("🔵 Fetching AQI data from database...")
        
        latest_timestamps = AQIData.objects.values('area').annotate(
            latest_time=Max('timestamp')
        )
        
        if not latest_timestamps.exists():
            print("⚠️ No data in database, returning sample data")
            return JsonResponse(get_sample_aqi_data(), safe=False)
        
        aqi_data = []
        for item in latest_timestamps:
            latest_reading = AQIData.objects.filter(
                area=item['area'],
                timestamp=item['latest_time']
            ).first()
            
            if latest_reading:
                # Use getattr with defaults for safe attribute access
                aqi_data.append({
                    'area': latest_reading.area or 'Unknown',
                    'aqi_value': float(getattr(latest_reading, 'aqi_value', 0) or 0),
                    'category': getattr(latest_reading, 'category', 'Unknown'),
                    'pm25': float(getattr(latest_reading, 'pm25', 0) or 0),
                    'pm10': float(getattr(latest_reading, 'pm10', 0) or 0),
                    'no2': float(getattr(latest_reading, 'no2', 0) or 0),
                    'co': float(getattr(latest_reading, 'co', 0) or 0),
                    'primary_source': getattr(latest_reading, 'primary_source', 'Unknown'),
                    'traffic_contribution': float(getattr(latest_reading, 'traffic_contribution', 0) or 0),
                    'industrial_contribution': float(getattr(latest_reading, 'industrial_contribution', 0) or 0),
                    'crop_burning_contribution': float(getattr(latest_reading, 'crop_burning_contribution', 0) or 0),
                    'construction_contribution': float(getattr(latest_reading, 'construction_contribution', 0) or 0),
                    'other_contribution': float(getattr(latest_reading, 'other_contribution', 0) or 0),
                    'timestamp': latest_reading.timestamp.isoformat() if latest_reading.timestamp else ''
                })
        
        if not aqi_data:
            print("⚠️ No valid data found, returning sample data")
            return JsonResponse(get_sample_aqi_data(), safe=False)
        
        cache.set('aqi_heatmap_data', aqi_data, 300)
        
        print(f"✅ Returning {len(aqi_data)} AQI records")
        return JsonResponse(aqi_data, safe=False)
        
    except Exception as e:
        print(f"🔴 Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse(get_sample_aqi_data(), safe=False)

def get_sample_aqi_data():
    """
    Sample AQI data for when database is empty or for testing
    This provides realistic Delhi NCR air quality data
    """
    from datetime import datetime
    
    return [
        {
            'area': 'Connaught Place',
            'aqi_value': 185.0,
            'category': 'Unhealthy for Sensitive Groups',
            'pm25': 85.0,
            'pm10': 145.0,
            'no2': 45.0,
            'co': 1.2,
            'primary_source': 'Traffic',
            'traffic_contribution': 35.0,
            'industrial_contribution': 25.0,
            'crop_burning_contribution': 20.0,
            'construction_contribution': 20.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Rohini',
            'aqi_value': 245.0,
            'category': 'Very Unhealthy',
            'pm25': 125.0,
            'pm10': 195.0,
            'no2': 55.0,
            'co': 1.8,
            'primary_source': 'Traffic',
            'traffic_contribution': 40.0,
            'industrial_contribution': 30.0,
            'crop_burning_contribution': 15.0,
            'construction_contribution': 15.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Dwarka',
            'aqi_value': 165.0,
            'category': 'Unhealthy for Sensitive Groups',
            'pm25': 75.0,
            'pm10': 135.0,
            'no2': 40.0,
            'co': 1.0,
            'primary_source': 'Traffic',
            'traffic_contribution': 35.0,
            'industrial_contribution': 25.0,
            'crop_burning_contribution': 20.0,
            'construction_contribution': 20.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Noida',
            'aqi_value': 275.0,
            'category': 'Very Unhealthy',
            'pm25': 145.0,
            'pm10': 225.0,
            'no2': 60.0,
            'co': 2.0,
            'primary_source': 'Industry',
            'traffic_contribution': 30.0,
            'industrial_contribution': 40.0,
            'crop_burning_contribution': 15.0,
            'construction_contribution': 15.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Gurgaon',
            'aqi_value': 195.0,
            'category': 'Unhealthy',
            'pm25': 95.0,
            'pm10': 165.0,
            'no2': 50.0,
            'co': 1.5,
            'primary_source': 'Traffic',
            'traffic_contribution': 45.0,
            'industrial_contribution': 25.0,
            'crop_burning_contribution': 15.0,
            'construction_contribution': 15.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Anand Vihar',
            'aqi_value': 265.0,
            'category': 'Very Unhealthy',
            'pm25': 140.0,
            'pm10': 215.0,
            'no2': 65.0,
            'co': 1.9,
            'primary_source': 'Traffic',
            'traffic_contribution': 50.0,
            'industrial_contribution': 25.0,
            'crop_burning_contribution': 15.0,
            'construction_contribution': 10.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Punjabi Bagh',
            'aqi_value': 215.0,
            'category': 'Very Unhealthy',
            'pm25': 105.0,
            'pm10': 175.0,
            'no2': 52.0,
            'co': 1.6,
            'primary_source': 'Traffic',
            'traffic_contribution': 40.0,
            'industrial_contribution': 25.0,
            'crop_burning_contribution': 20.0,
            'construction_contribution': 15.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Faridabad',
            'aqi_value': 225.0,
            'category': 'Very Unhealthy',
            'pm25': 110.0,
            'pm10': 180.0,
            'no2': 53.0,
            'co': 1.7,
            'primary_source': 'Industry',
            'traffic_contribution': 30.0,
            'industrial_contribution': 40.0,
            'crop_burning_contribution': 15.0,
            'construction_contribution': 15.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Ghaziabad',
            'aqi_value': 255.0,
            'category': 'Very Unhealthy',
            'pm25': 130.0,
            'pm10': 205.0,
            'no2': 58.0,
            'co': 1.85,
            'primary_source': 'Industry',
            'traffic_contribution': 35.0,
            'industrial_contribution': 35.0,
            'crop_burning_contribution': 15.0,
            'construction_contribution': 15.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Greater Noida',
            'aqi_value': 235.0,
            'category': 'Very Unhealthy',
            'pm25': 115.0,
            'pm10': 190.0,
            'no2': 54.0,
            'co': 1.75,
            'primary_source': 'Construction',
            'traffic_contribution': 30.0,
            'industrial_contribution': 25.0,
            'crop_burning_contribution': 15.0,
            'construction_contribution': 30.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Nehru Place',
            'aqi_value': 205.0,
            'category': 'Very Unhealthy',
            'pm25': 100.0,
            'pm10': 170.0,
            'no2': 48.0,
            'co': 1.55,
            'primary_source': 'Traffic',
            'traffic_contribution': 42.0,
            'industrial_contribution': 28.0,
            'crop_burning_contribution': 15.0,
            'construction_contribution': 15.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Karol Bagh',
            'aqi_value': 195.0,
            'category': 'Unhealthy',
            'pm25': 92.0,
            'pm10': 162.0,
            'no2': 47.0,
            'co': 1.45,
            'primary_source': 'Traffic',
            'traffic_contribution': 38.0,
            'industrial_contribution': 27.0,
            'crop_burning_contribution': 18.0,
            'construction_contribution': 17.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Lajpat Nagar',
            'aqi_value': 185.0,
            'category': 'Unhealthy',
            'pm25': 88.0,
            'pm10': 155.0,
            'no2': 44.0,
            'co': 1.35,
            'primary_source': 'Traffic',
            'traffic_contribution': 36.0,
            'industrial_contribution': 26.0,
            'crop_burning_contribution': 19.0,
            'construction_contribution': 19.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Janakpuri',
            'aqi_value': 175.0,
            'category': 'Unhealthy',
            'pm25': 82.0,
            'pm10': 148.0,
            'no2': 42.0,
            'co': 1.25,
            'primary_source': 'Traffic',
            'traffic_contribution': 34.0,
            'industrial_contribution': 24.0,
            'crop_burning_contribution': 21.0,
            'construction_contribution': 21.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Mayur Vihar',
            'aqi_value': 220.0,
            'category': 'Very Unhealthy',
            'pm25': 108.0,
            'pm10': 182.0,
            'no2': 56.0,
            'co': 1.65,
            'primary_source': 'Traffic',
            'traffic_contribution': 41.0,
            'industrial_contribution': 29.0,
            'crop_burning_contribution': 15.0,
            'construction_contribution': 15.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Vasant Kunj',
            'aqi_value': 155.0,
            'category': 'Unhealthy for Sensitive Groups',
            'pm25': 70.0,
            'pm10': 128.0,
            'no2': 38.0,
            'co': 1.15,
            'primary_source': 'Traffic',
            'traffic_contribution': 32.0,
            'industrial_contribution': 22.0,
            'crop_burning_contribution': 23.0,
            'construction_contribution': 23.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Saket',
            'aqi_value': 165.0,
            'category': 'Unhealthy for Sensitive Groups',
            'pm25': 76.0,
            'pm10': 138.0,
            'no2': 40.0,
            'co': 1.2,
            'primary_source': 'Traffic',
            'traffic_contribution': 33.0,
            'industrial_contribution': 23.0,
            'crop_burning_contribution': 22.0,
            'construction_contribution': 22.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Pitampura',
            'aqi_value': 210.0,
            'category': 'Very Unhealthy',
            'pm25': 103.0,
            'pm10': 172.0,
            'no2': 51.0,
            'co': 1.6,
            'primary_source': 'Traffic',
            'traffic_contribution': 39.0,
            'industrial_contribution': 28.0,
            'crop_burning_contribution': 17.0,
            'construction_contribution': 16.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Shahdara',
            'aqi_value': 240.0,
            'category': 'Very Unhealthy',
            'pm25': 120.0,
            'pm10': 192.0,
            'no2': 59.0,
            'co': 1.75,
            'primary_source': 'Industry',
            'traffic_contribution': 35.0,
            'industrial_contribution': 35.0,
            'crop_burning_contribution': 15.0,
            'construction_contribution': 15.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        },
        {
            'area': 'Okhla',
            'aqi_value': 250.0,
            'category': 'Very Unhealthy',
            'pm25': 128.0,
            'pm10': 200.0,
            'no2': 62.0,
            'co': 1.82,
            'primary_source': 'Industry',
            'traffic_contribution': 32.0,
            'industrial_contribution': 38.0,
            'crop_burning_contribution': 15.0,
            'construction_contribution': 15.0,
            'other_contribution': 0.0,
            'timestamp': datetime.now().isoformat()
        }
    ]
#darsh - CV Views

@login_required
def snap_to_aqi(request):
    """Snap-to-AQI: Upload image and get instant AQI prediction"""
    
    if request.method == 'POST':
        try:
            # Get uploaded image
            image_file = request.FILES.get('image')
            location = request.POST.get('location', '')
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            
            if not image_file:
                messages.error(request, 'Please upload an image.')
                return redirect('snap_to_aqi')
            
            # Validate image format
            allowed_formats = ['jpg', 'jpeg', 'png']
            file_ext = image_file.name.split('.')[-1].lower()
            if file_ext not in allowed_formats:
                messages.error(request, 'Please upload a valid image (JPG, JPEG, or PNG).')
                return redirect('snap_to_aqi')
            
            # Get user's location for base AQI
            user_city = location if location else "Delhi"
            try:
                if hasattr(request.user, 'health_profile') and request.user.health_profile.location:
                    user_city = request.user.health_profile.location
            except:
                pass
            
            # Get current AQI for user's location
            current_aqi_data = get_current_aqi(user_city)
            base_aqi = current_aqi_data.get('aqi', 150)
            
            # Save image to temporary location first
            temp_path = default_storage.save(f'temp/{image_file.name}', ContentFile(image_file.read()))
            full_temp_path = os.path.join(default_storage.location, temp_path)
            
            # Run CV detection FIRST to get all required fields
            detector = get_detector()
            result = detector.predict_aqi_from_image(full_temp_path, base_aqi=base_aqi)
            
            # Reset file pointer for saving to model
            image_file.seek(0)
            
            # Now create prediction record with ALL required fields populated
            prediction_record = ImageAQIPrediction(
                user=request.user,
                image=image_file,
                location=location or user_city,
                base_aqi=base_aqi,
                predicted_aqi=result['predicted_aqi'],
                aqi_rise=result['aqi_rise'],
                haziness_score=result['haziness_score'],
                pollution_source=result['pollution_source'],
                health_alert_level=result['health_alert_level']
            )
            
            # Add coordinates if available
            if latitude and longitude:
                try:
                    prediction_record.latitude = float(latitude)
                    prediction_record.longitude = float(longitude)
                except:
                    pass
            
            # Save the complete record
            prediction_record.save()
            
            # Clean up temporary file
            try:
                default_storage.delete(temp_path)
            except:
                pass
            
            # Success message
            messages.success(
                request,
                f'✓ Analysis complete! Detected AQI: {result["predicted_aqi"]} '
                f'(+{result["aqi_rise"]} from pollution source)'
            )
            
            return redirect('snap_result', prediction_id=prediction_record.id)
            
        except Exception as e:
            print(f"Error in snap_to_aqi: {e}")
            print(traceback.format_exc())
            messages.error(request, f'Error processing image: {str(e)}')
            return redirect('snap_to_aqi')
    
    # GET request - show upload form
    user_city = "Delhi"
    try:
        if hasattr(request.user, 'health_profile') and request.user.health_profile.location:
            user_city = request.user.health_profile.location
    except:
        pass
    
    # Get recent predictions
    recent_predictions = ImageAQIPrediction.objects.filter(
        user=request.user
    )[:5]
    
    # Get current AQI
    current_aqi_data = get_current_aqi(user_city)
    
    context = {
        'recent_predictions': recent_predictions,
        'current_aqi': current_aqi_data.get('aqi', 0),
        'user_city': user_city,
    }
    
    return render(request, 'snap_to_aqi.html', context)


@login_required
def snap_result(request, prediction_id):
    """Display detailed results of Snap-to-AQI prediction"""
    
    prediction = get_object_or_404(ImageAQIPrediction, id=prediction_id, user=request.user)
    
    # Get health recommendations based on AQI
    recommendations = get_snap_recommendations(prediction, request.user)
    
    # Get nearby area AQI for comparison
    nearby_aqi = None
    if prediction.location:
        nearby_aqi = AQIData.objects.filter(
            area__icontains=prediction.location
        ).first()
    
    context = {
        'prediction': prediction,
        'recommendations': recommendations,
        'nearby_aqi': nearby_aqi,
    }
    
    return render(request, 'snap_result.html', context)


@login_required
def snap_history(request):
    """View history of all Snap-to-AQI predictions"""
    
    predictions = ImageAQIPrediction.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    # Get statistics
    total_predictions = predictions.count()
    avg_aqi = predictions.aggregate(django_models.Avg('predicted_aqi'))['predicted_aqi__avg'] or 0
    highest_aqi = predictions.aggregate(django_models.Max('predicted_aqi'))['predicted_aqi__max'] or 0
    
    # Get source distribution
    source_stats = predictions.values('pollution_source').annotate(
        count=django_models.Count('id')
    ).order_by('-count')
    
    context = {
        'predictions': predictions,
        'total_predictions': total_predictions,
        'avg_aqi': round(avg_aqi),
        'highest_aqi': highest_aqi,
        'source_stats': source_stats,
    }
    
    return render(request, 'snap_history.html', context)


# ============================================================================
# Helper function for recommendations
# ============================================================================

def get_snap_recommendations(prediction, user):
    """Generate personalized recommendations based on image prediction"""
    recommendations = []
    aqi = prediction.predicted_aqi
    source = prediction.pollution_source
    
    # General AQI-based recommendations
    if aqi > 300:
        recommendations.append({
            'icon': '🚨',
            'title': 'SEVERE ALERT',
            'message': 'Stay indoors immediately. Close all windows. Use air purifier.',
            'priority': 'danger'
        })
    elif aqi > 200:
        recommendations.append({
            'icon': '⚠️',
            'title': 'HIGH POLLUTION',
            'message': 'Avoid outdoor activities. Wear N95 mask if you must go out.',
            'priority': 'warning'
        })
    elif aqi > 150:
        recommendations.append({
            'icon': '⚠️',
            'title': 'UNHEALTHY AIR',
            'message': 'Limit outdoor exposure. Sensitive groups should stay indoors.',
            'priority': 'warning'
        })
    elif aqi > 100:
        recommendations.append({
            'icon': '😷',
            'title': 'MODERATE POLLUTION',
            'message': 'Sensitive groups should limit prolonged outdoor activities.',
            'priority': 'info'
        })
    
    # Source-specific recommendations
    if source == 'SMOKE':
        recommendations.append({
            'icon': '🚭',
            'title': 'Smoke Detected',
            'message': 'Avoid the area. Smoke contains harmful particulates and gases.',
            'priority': 'danger'
        })
    elif source == 'DUST':
        recommendations.append({
            'icon': '💨',
            'title': 'Dust Pollution',
            'message': 'Close windows. Wear mask. Dust can aggravate respiratory issues.',
            'priority': 'warning'
        })
    elif source == 'VEHICLE':
        recommendations.append({
            'icon': '🚗',
            'title': 'Vehicle Emissions',
            'message': 'Avoid main roads. Use less congested routes if possible.',
            'priority': 'warning'
        })
    elif source == 'FIRE':
        recommendations.append({
            'icon': '🔥',
            'title': 'Fire/Burning Detected',
            'message': 'Evacuate area immediately. Report to authorities if needed.',
            'priority': 'danger'
        })
    elif source == 'CONSTRUCTION':
        recommendations.append({
            'icon': '🏗️',
            'title': 'Construction Dust',
            'message': 'Avoid construction sites. Dust contains PM10 particles.',
            'priority': 'warning'
        })
    elif source == 'INDUSTRIAL':
        recommendations.append({
            'icon': '🏭',
            'title': 'Industrial Emissions',
            'message': 'Stay away from industrial areas. Air contains toxic pollutants.',
            'priority': 'warning'
        })
    
    # Health-specific recommendations
    try:
        if hasattr(user, 'health_profile') and user.health_profile:
            profile = user.health_profile
            
            if profile.has_respiratory_issues and aqi > 150:
                recommendations.append({
                    'icon': '💊',
                    'title': 'Respiratory Alert',
                    'message': 'Keep your inhaler ready. Avoid any outdoor activity.',
                    'priority': 'danger'
                })
            
            if profile.has_heart_disease and aqi > 150:
                recommendations.append({
                    'icon': '❤️',
                    'title': 'Heart Health Alert',
                    'message': 'Avoid physical exertion. Monitor your condition closely.',
                    'priority': 'danger'
                })
            
            if profile.is_child or profile.is_elderly:
                recommendations.append({
                    'icon': '👶' if profile.is_child else '👴',
                    'title': 'Vulnerable Group Alert',
                    'message': 'Extra caution advised. Stay in well-ventilated indoor spaces.',
                    'priority': 'warning'
                })
            
            if profile.is_pregnant and aqi > 100:
                recommendations.append({
                    'icon': '🤰',
                    'title': 'Pregnancy Alert',
                    'message': 'Minimize outdoor exposure. Poor air quality can affect fetal development.',
                    'priority': 'warning'
                })
    except Exception as e:
        print(f"Error getting health profile recommendations: {e}")
    
    # Add general protective measures
    if aqi > 100:
        recommendations.append({
            'icon': '😷',
            'title': 'Protective Measures',
            'message': 'Wear N95 mask outdoors. Use air purifier indoors. Stay hydrated.',
            'priority': 'info'
        })
    
    return recommendations

# ============================================================================
# LIVE CAMERA CAPTURE FEATURE
# ADD these new views to your existing views.py (don't replace anything)
# ============================================================================

@login_required
def live_camera(request):
    """Live camera capture page with real-time smoke detection"""
    
    # Get user's location for base AQI
    user_city = "Delhi"
    try:
        if hasattr(request.user, 'health_profile') and request.user.health_profile.location:
            user_city = request.user.health_profile.location
    except:
        pass
    
    # Get current AQI
    current_aqi_data = get_current_aqi(user_city)
    
    context = {
        'current_aqi': current_aqi_data.get('aqi', 0),
        'user_city': user_city,
    }
    
    return render(request, 'live_camera.html', context)


@login_required
def analyze_camera_frame(request):
    """
    AJAX endpoint to analyze camera frame in real-time
    Detects smoke and returns detection results
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    try:
        # Get base64 image from request
        image_data = request.POST.get('image')
        
        if not image_data:
            return JsonResponse({'error': 'No image data'}, status=400)
        
        # Remove data URL prefix if present
        if 'base64,' in image_data:
            image_data = image_data.split('base64,')[1]
        
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        image = PILImage.open(BytesIO(image_bytes))
        
        # Convert to numpy array for OpenCV
        img_array = np.array(image)
        
        # Perform smoke detection
        detection_result = detect_smoke_realtime(img_array)
        
        # Get user's city for base AQI
        user_city = "Delhi"
        try:
            if hasattr(request.user, 'health_profile') and request.user.health_profile.location:
                user_city = request.user.health_profile.location
        except:
            pass
        
        # Get current AQI
        current_aqi_data = get_current_aqi(user_city)
        base_aqi = current_aqi_data.get('aqi', 150)
        
        # Calculate AQI rise based on smoke intensity
        smoke_intensity = detection_result['smoke_intensity']
        aqi_rise = int(smoke_intensity * 150)  # Max 150 AQI rise
        predicted_aqi = min(500, base_aqi + aqi_rise)
        
        # Determine pollution level
        if smoke_intensity > 0.7:
            pollution_level = "SEVERE"
            alert_color = "#dc3545"
        elif smoke_intensity > 0.5:
            pollution_level = "HIGH"
            alert_color = "#ff7e00"
        elif smoke_intensity > 0.3:
            pollution_level = "MODERATE"
            alert_color = "#ffc107"
        elif smoke_intensity > 0.1:
            pollution_level = "LOW"
            alert_color = "#28a745"
        else:
            pollution_level = "CLEAN"
            alert_color = "#00e400"
        
        return JsonResponse({
            'success': True,
            'smoke_detected': detection_result['smoke_detected'],
            'smoke_intensity': round(smoke_intensity, 3),
            'smoke_percentage': round(detection_result['smoke_percentage'], 1),
            'smoke_regions': detection_result['smoke_regions'],
            'base_aqi': base_aqi,
            'aqi_rise': aqi_rise,
            'predicted_aqi': predicted_aqi,
            'pollution_level': pollution_level,
            'alert_color': alert_color,
            'haziness_score': detection_result['haziness_score'],
        })
        
    except Exception as e:
        print(f"Error analyzing camera frame: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)


@login_required
def capture_live_snapshot(request):
    """
    Save a snapshot from live camera as a prediction record
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    try:
        # Get base64 image from request
        image_data = request.POST.get('image')
        location = request.POST.get('location', '')
        
        if not image_data:
            return JsonResponse({'error': 'No image data'}, status=400)
        
        # Remove data URL prefix
        if 'base64,' in image_data:
            image_data = image_data.split('base64,')[1]
        
        # Decode and save image
        image_bytes = base64.b64decode(image_data)
        image = PILImage.open(BytesIO(image_bytes))
        
        # Save to temporary file
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        image.save(temp_file.name, 'JPEG')
        temp_file.close()
        
        # Get user's city for base AQI
        user_city = location if location else "Delhi"
        try:
            if hasattr(request.user, 'health_profile') and request.user.health_profile.location:
                user_city = request.user.health_profile.location
        except:
            pass
        
        # Get current AQI
        current_aqi_data = get_current_aqi(user_city)
        base_aqi = current_aqi_data.get('aqi', 150)
        
        # Run CV detection
        detector = get_detector()
        result = detector.predict_aqi_from_image(temp_file.name, base_aqi=base_aqi)
        
        # Create Django file from temp file
        from django.core.files import File
        django_file = File(open(temp_file.name, 'rb'))
        
        # Create prediction record
        prediction_record = ImageAQIPrediction(
            user=request.user,
            location=location or user_city,
            base_aqi=base_aqi,
            predicted_aqi=result['predicted_aqi'],
            aqi_rise=result['aqi_rise'],
            haziness_score=result['haziness_score'],
            pollution_source=result['pollution_source'],
            health_alert_level=result['health_alert_level']
        )
        
        # Save image to model
        prediction_record.image.save(
            f'live_capture_{request.user.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg',
            django_file,
            save=False
        )
        
        prediction_record.save()
        
        # Clean up temp file
        django_file.close()
        os.unlink(temp_file.name)
        
        return JsonResponse({
            'success': True,
            'prediction_id': prediction_record.id,
            'predicted_aqi': result['predicted_aqi'],
            'aqi_rise': result['aqi_rise'],
            'message': 'Snapshot saved successfully!'
        })
        
    except Exception as e:
        print(f"Error capturing live snapshot: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)


# ============================================================================
# HELPER FUNCTION - Real-time Smoke Detection
# ============================================================================

def detect_smoke_realtime(img_array):
    """
    Detect smoke in real-time from camera frame
    Returns smoke regions and intensity
    """
    try:
        # Convert RGB to BGR for OpenCV
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = img_array
        
        # Convert to HSV for better smoke detection
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        
        # Convert to grayscale for haziness
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        
        # Detect smoke (grayish-white areas with low saturation)
        # Smoke characteristics: High value, low saturation
        lower_smoke = np.array([0, 0, 180])  # Low saturation, high brightness
        upper_smoke = np.array([180, 50, 255])
        smoke_mask = cv2.inRange(hsv, lower_smoke, upper_smoke)
        
        # Detect dust/haze (brownish-yellow areas)
        lower_dust = np.array([15, 30, 100])
        upper_dust = np.array([35, 150, 255])
        dust_mask = cv2.inRange(hsv, lower_dust, upper_dust)
        
        # Combine masks
        combined_mask = cv2.bitwise_or(smoke_mask, dust_mask)
        
        # Calculate smoke percentage
        total_pixels = combined_mask.size
        smoke_pixels = np.count_nonzero(combined_mask)
        smoke_percentage = (smoke_pixels / total_pixels) * 100
        
        # Find contours (smoke regions)
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Get bounding boxes for significant regions
        smoke_regions = []
        min_area = 1000  # Minimum area to consider as smoke
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > min_area:
                x, y, w, h = cv2.boundingRect(contour)
                smoke_regions.append({
                    'x': int(x),
                    'y': int(y),
                    'width': int(w),
                    'height': int(h),
                    'area': int(area)
                })
        
        # Calculate haziness (blur detection)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        haziness_score = 1.0 - min(1.0, laplacian_var / 500.0)
        
        # Calculate smoke intensity (0-1)
        # Combine percentage and haziness
        smoke_intensity = (smoke_percentage / 100) * 0.7 + haziness_score * 0.3
        smoke_intensity = min(1.0, smoke_intensity)
        
        return {
            'smoke_detected': smoke_percentage > 5,  # 5% threshold
            'smoke_percentage': smoke_percentage,
            'smoke_intensity': smoke_intensity,
            'smoke_regions': smoke_regions[:10],  # Return max 10 regions
            'haziness_score': round(haziness_score, 3),
            'num_regions': len(smoke_regions)
        }
        
    except Exception as e:
        print(f"Error in smoke detection: {e}")
        return {
            'smoke_detected': False,
            'smoke_percentage': 0,
            'smoke_intensity': 0,
            'smoke_regions': [],
            'haziness_score': 0,
            'num_regions': 0
        }

#darsh - ENHANCED YOLO Views
@login_required
def snap_to_aqi_enhanced(request):
    """
    Enhanced Snap-to-AQI with YOLO object detection
    Detects: smoke/haze + vehicles/construction
    """
    
    if request.method == 'POST':
        try:
            # Get uploaded image
            image_file = request.FILES.get('image')
            location = request.POST.get('location', '')
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            
            if not image_file:
                messages.error(request, 'Please upload an image.')
                return redirect('snap_to_aqi_enhanced')
            
            # Validate image format
            allowed_formats = ['jpg', 'jpeg', 'png']
            file_ext = image_file.name.split('.')[-1].lower()
            if file_ext not in allowed_formats:
                messages.error(request, 'Please upload a valid image (JPG, JPEG, or PNG).')
                return redirect('snap_to_aqi_enhanced')
            
            # Get user's location for base AQI
            user_city = location if location else "Delhi"
            try:
                if hasattr(request.user, 'health_profile') and request.user.health_profile.location:
                    user_city = request.user.health_profile.location
            except:
                pass
            
            # Get current AQI for user's location
            current_aqi_data = get_current_aqi(user_city)
            base_aqi = current_aqi_data.get('aqi', 150)
            
            # Save image to temporary location
            temp_path = default_storage.save(f'temp/{image_file.name}', ContentFile(image_file.read()))
            full_temp_path = os.path.join(default_storage.location, temp_path)
            
            # Run ENHANCED detection (CV + YOLO) using the NEW detector
            enhanced_detector = get_enhanced_detector()
            result = enhanced_detector.predict_aqi_from_image(full_temp_path, base_aqi=base_aqi)
            
            # Reset file pointer for saving to model
            image_file.seek(0)
            
            # Create prediction record with ENHANCED data
            prediction_record = ImageAQIPrediction(
                user=request.user,
                image=image_file,
                location=location or user_city,
                base_aqi=base_aqi,
                predicted_aqi=result['predicted_aqi'],
                aqi_rise=result['aqi_rise'],
                haziness_score=result['haziness_score'],
                pollution_source=result['pollution_source'],
                health_alert_level=result['health_alert_level']
            )
            
            # Add coordinates if available
            if latitude and longitude:
                try:
                    prediction_record.latitude = float(latitude)
                    prediction_record.longitude = float(longitude)
                except:
                    pass
            
            # Save the record
            prediction_record.save()
            
            # Clean up temporary file
            try:
                default_storage.delete(temp_path)
            except:
                pass
            
            # BUILD DETAILED SUCCESS MESSAGE
            # Get pollution source name
            source_names = {
                'SMOKE': '🔥 Smoke/Fire',
                'DUST': '💨 Dust',
                'VEHICLE': '🚗 Vehicle Emissions',
                'CONSTRUCTION': '🏗️ Construction',
                'INDUSTRIAL': '🏭 Industrial',
                'FIRE': '🔥 Fire/Burning',
                'UNKNOWN': '❓ Unknown Source',
            }
            source_display = source_names.get(result['pollution_source'], result['pollution_source'])
            
            # Build detection details list
            detection_details = []
            
            # Add pollution source
            detection_details.append(f"Source: {source_display}")
            
            # Add vehicle info if detected
            if result.get('vehicle_count', 0) > 0:
                vehicle_info = f"{result['vehicle_count']} vehicle(s)"
                if result.get('heavy_vehicle_count', 0) > 0:
                    vehicle_info += f" ({result['heavy_vehicle_count']} heavy)"
                detection_details.append(f"🚗 {vehicle_info}")
            
            # Add smoke/haze info
            haziness = result.get('haziness_score', 0)
            if haziness > 0.5:
                detection_details.append(f"🌫️ Haze: {haziness*100:.0f}%")
            elif haziness > 0.3:
                detection_details.append(f"🌫️ Slight haze detected")
            
            # Add CV detection if different from main source
            cv_source = result.get('cv_pollution_source')
            if cv_source and cv_source != result['pollution_source']:
                detection_details.append(f"Also detected: {source_names.get(cv_source, cv_source)}")
            
            # Add detection method info
            detection_method = result.get('detection_method', 'Unknown')
            if 'YOLO' in detection_method:
                detection_details.append("🤖 AI-powered detection")
            
            # Create formatted message
            detail_lines = " | ".join(detection_details)
            
            # Main success message with all details
            success_message = (
                f"✅ Enhanced Analysis Complete!\n\n"
                f"📊 Predicted AQI: {result['predicted_aqi']} (Base: {base_aqi}, Rise: +{result['aqi_rise']})\n"
                f"🎯 {detail_lines}\n"
                f"⚠️ Health Alert: {result['health_alert_level']}"
            )
            
            messages.success(request, success_message)
            
            return redirect('snap_result_enhanced', prediction_id=prediction_record.id)
            
        except Exception as e:
            print(f"Error in enhanced snap_to_aqi: {e}")
            print(traceback.format_exc())
            messages.error(request, f'Error processing image: {str(e)}')
            return redirect('snap_to_aqi_enhanced')
    
    # GET request - show upload form
    user_city = "Delhi"
    try:
        if hasattr(request.user, 'health_profile') and request.user.health_profile.location:
            user_city = request.user.health_profile.location
    except:
        pass
    
    # Get recent predictions
    recent_predictions = ImageAQIPrediction.objects.filter(
        user=request.user
    )[:5]
    
    # Get current AQI
    current_aqi_data = get_current_aqi(user_city)
    
    context = {
        'recent_predictions': recent_predictions,
        'current_aqi': current_aqi_data.get('aqi', 0),
        'user_city': user_city,
        'enhanced_mode': True,
    }
    
    return render(request, 'snap_to_aqi.html', context)


@login_required
def snap_result_enhanced(request, prediction_id):
    """
    Display ENHANCED results with YOLO detections
    """
    
    prediction = get_object_or_404(ImageAQIPrediction, id=prediction_id, user=request.user)
    
    # Re-run detection to get detailed breakdown
    try:
        enhanced_detector = get_enhanced_detector()
        full_image_path = prediction.image.path
        result = enhanced_detector.predict_aqi_from_image(full_image_path, base_aqi=prediction.base_aqi)
    except:
        result = {
            'vehicle_count': 0,
            'heavy_vehicle_count': 0,
            'yolo_detections': [],
            'cv_pollution_source': prediction.pollution_source,
            'yolo_pollution_source': None,
        }
    
    # Get health recommendations
    recommendations = get_snap_recommendations(prediction, request.user)
    
    # Add vehicle-specific recommendations
    if result.get('vehicle_count', 0) > 10:
        recommendations.insert(0, {
            'icon': '🚗',
            'title': f'{result["vehicle_count"]} Vehicles Detected',
            'message': 'Heavy traffic pollution. Avoid this area during peak hours.',
            'priority': 'warning'
        })
    
    # Get nearby area AQI for comparison
    nearby_aqi = None
    if prediction.location:
        nearby_aqi = AQIData.objects.filter(
            area__icontains=prediction.location
        ).first()
    
    context = {
        'prediction': prediction,
        'recommendations': recommendations,
        'nearby_aqi': nearby_aqi,
        'enhanced_result': result,  # Extra YOLO data
        'vehicle_count': result.get('vehicle_count', 0),
        'heavy_vehicle_count': result.get('heavy_vehicle_count', 0),
        'yolo_detections': result.get('yolo_detections', []),
    }
    
    return render(request, 'snap_result.html', context)