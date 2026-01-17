from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from .models import UserHealthProfile, Policy, PolicyVote, AQIData
from .forms import HealthProfileForm, PolicyForm
from datetime import datetime, timedelta
import random
from .aqi_predictor import predict_aqi, get_current_aqi
from .models import AQIData, UserHealthProfile
from .aqi_predictor import predict_aqi, get_current_aqi, train_model


from .aqi_predictor import predict_aqi 
import os
from .models import UserHealthProfile, Policy, PolicyVote, AQIData, AQIForecast, PolicyComment
from .forms import HealthProfileForm, PolicyForm
from datetime import datetime, timedelta
import random

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
    
    
    
    # Get personalized health alerts
    alerts = get_health_alerts(health_profile, location_aqi)
    
    # Get trending policies
    trending_policies = Policy.objects.filter(status='PROPOSED')[:5]
    
    context = {
        'health_profile': health_profile,
        'location_aqi': location_aqi,
        'recent_aqi': recent_aqi,
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


@login_required
def policy_simulation(request):
    """Simulate policy impact"""
    if request.method == 'POST':
        policy_id = request.POST.get('policy_id')
        # Here you would implement actual simulation logic
        # For now, return simulated data
        
        return JsonResponse({
            'success': True,
            'before_aqi': random.randint(200, 350),
            'after_aqi': random.randint(100, 200),
            'reduction': random.randint(20, 50),
        })
    
    policies = Policy.objects.filter(status='PROPOSED')
    
    return render(request, 'policy_simulation.html', {
        'policies': policies
    })




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