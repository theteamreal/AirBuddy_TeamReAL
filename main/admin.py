from django.contrib import admin
# darsh - Added PolicyComment import for admin registration
from .models import UserHealthProfile, Policy, PolicyVote, AQIData, AQIForecast, PolicyComment

@admin.register(UserHealthProfile)
class UserHealthProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'location', 'risk_level', 'has_respiratory_issues', 'has_heart_disease', 'is_elderly', 'created_at']
    list_filter = ['risk_level', 'has_respiratory_issues', 'has_heart_disease', 'has_allergies', 'is_elderly', 'is_child', 'is_pregnant']
    search_fields = ['user__username', 'location']
    readonly_fields = ['risk_level', 'created_at', 'updated_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'location')
        }),
        ('Health Conditions', {
            'fields': ('has_respiratory_issues', 'has_heart_disease', 'has_allergies')
        }),
        ('Age Group', {
            'fields': ('is_elderly', 'is_child', 'is_pregnant')
        }),
        ('Risk Assessment', {
            'fields': ('risk_level',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ['title', 'policy_type', 'proposed_by', 'status', 'agree_count', 'disagree_count', 'agreement_percentage', 'created_at']
    list_filter = ['policy_type', 'status', 'created_at']
    search_fields = ['title', 'description', 'proposed_by__username']
    readonly_fields = ['created_at', 'updated_at', 'agreement_percentage', 'total_votes']
    
    fieldsets = (
        ('Policy Information', {
            'fields': ('title', 'description', 'policy_type', 'proposed_by')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Voting Statistics', {
            'fields': ('agree_count', 'disagree_count', 'total_votes', 'agreement_percentage')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def agreement_percentage(self, obj):
        return f"{obj.agreement_percentage}%"
    agreement_percentage.short_description = 'Agreement %'

@admin.register(PolicyVote)
class PolicyVoteAdmin(admin.ModelAdmin):
    list_display = ['user', 'policy', 'vote', 'created_at']
    list_filter = ['vote', 'created_at']
    search_fields = ['user__username', 'policy__title']
    readonly_fields = ['created_at']

@admin.register(AQIData)
class AQIDataAdmin(admin.ModelAdmin):
    list_display = ['area', 'aqi_value', 'category', 'pm25', 'pm10', 'primary_source', 'timestamp']
    list_filter = ['area', 'timestamp']
    search_fields = ['area']
    readonly_fields = ['category', 'primary_source']
    
    fieldsets = (
        ('Location & Time', {
            'fields': ('area', 'timestamp')
        }),
        ('Air Quality Metrics', {
            'fields': ('aqi_value', 'category', 'pm25', 'pm10')
        }),
        ('Pollution Sources (%)', {
            'fields': ('traffic_contribution', 'industrial_contribution', 'crop_burning_contribution', 
                      'construction_contribution', 'other_contribution', 'primary_source')
        }),
    )
    
    def category(self, obj):
        return obj.category
    category.short_description = 'AQI Category'
    
    def primary_source(self, obj):
        return obj.primary_source
    primary_source.short_description = 'Main Source'

@admin.register(AQIForecast)
class AQIForecastAdmin(admin.ModelAdmin):
    list_display = ['area', 'forecast_date', 'predicted_aqi', 'confidence', 'created_at']
    list_filter = ['area', 'forecast_date', 'created_at']
    search_fields = ['area']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Forecast Details', {
            'fields': ('area', 'forecast_date', 'predicted_aqi', 'confidence')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )

# darsh - Added PolicyComment admin registration for managing comments
@admin.register(PolicyComment)
class PolicyCommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'policy', 'comment_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'policy__title', 'comment']
    readonly_fields = ['created_at']
    
    def comment_preview(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = 'Comment'

# Customize admin site
admin.site.site_header = "Pollution Platform Administration"
admin.site.site_title = "Pollution Platform Admin"
admin.site.index_title = "Welcome to Pollution Platform Administration"