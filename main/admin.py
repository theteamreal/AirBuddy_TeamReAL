from django.contrib import admin
from .models import ImageAQIPrediction, UserHealthProfile, Policy, PolicyVote

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



# Customize admin site
admin.site.site_header = "Pollution Platform Administration"
admin.site.site_title = "Pollution Platform Admin"
admin.site.index_title = "Welcome to Pollution Platform Administration"

#darsh

@admin.register(ImageAQIPrediction)
class ImageAQIPredictionAdmin(admin.ModelAdmin):
    list_display = ['user', 'predicted_aqi', 'pollution_source', 'created_at']
    list_filter = ['pollution_source', 'health_alert_level']
    search_fields = ['user__username', 'location']