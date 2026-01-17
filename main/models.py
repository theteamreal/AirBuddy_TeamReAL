from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UserHealthProfile(models.Model):
    """Health profile for personalized dashboard"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='health_profile')
    
    # Health conditions
    has_respiratory_issues = models.BooleanField(default=False, verbose_name="Respiratory Issues (Asthma, COPD)")
    has_heart_disease = models.BooleanField(default=False, verbose_name="Heart Disease")
    has_allergies = models.BooleanField(default=False, verbose_name="Allergies")
    is_elderly = models.BooleanField(default=False, verbose_name="Age 60+")
    is_child = models.BooleanField(default=False, verbose_name="Age below 12")
    is_pregnant = models.BooleanField(default=False, verbose_name="Pregnant")
    
    # Location
    location = models.CharField(max_length=100, blank=True, help_text="Area in Delhi NCR")
    
    # Risk level (calculated)
    RISK_LEVELS = [
        ('LOW', 'Low Risk'),
        ('MODERATE', 'Moderate Risk'),
        ('HIGH', 'High Risk'),
        ('SEVERE', 'Severe Risk'),
    ]
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS, default='LOW')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def calculate_risk_level(self):
        """Calculate risk level based on health conditions"""
        risk_score = 0
        if self.has_respiratory_issues:
            risk_score += 3
        if self.has_heart_disease:
            risk_score += 2
        if self.has_allergies:
            risk_score += 1
        if self.is_elderly or self.is_child:
            risk_score += 2
        if self.is_pregnant:
            risk_score += 2
        
        if risk_score >= 6:
            return 'SEVERE'
        elif risk_score >= 4:
            return 'HIGH'
        elif risk_score >= 2:
            return 'MODERATE'
        return 'LOW'
    
    def save(self, *args, **kwargs):
        self.risk_level = self.calculate_risk_level()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user.username} - {self.risk_level}"


class Policy(models.Model):
    """Policy proposals for pollution control"""
    POLICY_TYPES = [
        ('TRAFFIC', 'Traffic Management'),
        ('INDUSTRY', 'Industrial Control'),
        ('CONSTRUCTION', 'Construction Regulation'),
        ('FIRECRACKER', 'Firecracker Ban'),
        ('CROP_BURNING', 'Crop Burning Control'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('PROPOSED', 'Proposed'),
        ('UNDER_REVIEW', 'Under Review'),
        ('IMPLEMENTED', 'Implemented'),
        ('REJECTED', 'Rejected'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPES)
    proposed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proposed_policies')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROPOSED')
    
    # Voting
    agree_count = models.IntegerField(default=0)
    disagree_count = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def total_votes(self):
        return self.agree_count + self.disagree_count
    
    @property
    def agreement_percentage(self):
        if self.total_votes == 0:
            return 0
        return round((self.agree_count / self.total_votes) * 100, 1)


class PolicyVote(models.Model):
    """Track user votes on policies"""
    VOTE_CHOICES = [
        ('AGREE', 'Agree'),
        ('DISAGREE', 'Disagree'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='policy_votes')
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='votes')
    vote = models.CharField(max_length=10, choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'policy']
    
    def __str__(self):
        return f"{self.user.username} - {self.vote} on {self.policy.title}"


class AQIData(models.Model):
    """Air Quality Index data for different areas"""
    area = models.CharField(max_length=100)
    aqi_value = models.IntegerField()
    pm25 = models.FloatField(verbose_name="PM2.5")
    pm10 = models.FloatField(verbose_name="PM10")
    
    # Pollution sources (percentage contribution)
    traffic_contribution = models.FloatField(default=0)
    industrial_contribution = models.FloatField(default=0)
    crop_burning_contribution = models.FloatField(default=0)
    construction_contribution = models.FloatField(default=0)
    other_contribution = models.FloatField(default=0)
    
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "AQI Data"
        verbose_name_plural = "AQI Data"
    
    def __str__(self):
        return f"{self.area} - AQI {self.aqi_value} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"
    
    @property
    def category(self):
        if self.aqi_value <= 50:
            return "Good"
        elif self.aqi_value <= 100:
            return "Moderate"
        elif self.aqi_value <= 200:
            return "Unhealthy for Sensitive Groups"
        elif self.aqi_value <= 300:
            return "Unhealthy"
        elif self.aqi_value <= 400:
            return "Very Unhealthy"
        return "Hazardous"
    
    @property
    def primary_source(self):
        """Identify the primary pollution source"""
        sources = {
            'Traffic': self.traffic_contribution,
            'Industry': self.industrial_contribution,
            'Crop Burning': self.crop_burning_contribution,
            'Construction': self.construction_contribution,
            'Other': self.other_contribution,
        }
        return max(sources, key=sources.get)


class AQIForecast(models.Model):
    """Forecasted AQI for next 24-72 hours"""
    area = models.CharField(max_length=100)
    forecast_date = models.DateTimeField()
    predicted_aqi = models.IntegerField()
    confidence = models.FloatField(help_text="Prediction confidence (0-1)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['forecast_date']
    
    def __str__(self):
        return f"{self.area} - {self.forecast_date.strftime('%Y-%m-%d')} - AQI {self.predicted_aqi}"