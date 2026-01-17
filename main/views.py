from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
# darsh - Added PolicyComment import for comment feature
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