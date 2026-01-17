from django import forms
from .models import UserHealthProfile, Policy

class HealthProfileForm(forms.ModelForm):
    """Form for health questionnaire during registration"""
    
    class Meta:
        model = UserHealthProfile
        fields = [
            'has_respiratory_issues',
            'has_heart_disease',
            'has_allergies',
            'is_elderly',
            'is_child',
            'is_pregnant',
            'location',
        ]
        
        widgets = {
            'has_respiratory_issues': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'has_heart_disease': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'has_allergies': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_elderly': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_child': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_pregnant': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Connaught Place, Gurgaon, Noida'
            }),
        }
        
        labels = {
            'has_respiratory_issues': 'Do you have respiratory issues? (Asthma, COPD, etc.)',
            'has_heart_disease': 'Do you have heart disease?',
            'has_allergies': 'Do you have allergies?',
            'is_elderly': 'Are you 60 years or older?',
            'is_child': 'Are you under 12 years old?',
            'is_pregnant': 'Are you pregnant?',
            'location': 'Your location in Delhi NCR',
        }


class PolicyForm(forms.ModelForm):
    """Form for creating new policy proposals"""
    
    class Meta:
        model = Policy
        fields = ['title', 'description', 'policy_type']
        
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter policy title',
                'maxlength': '200'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe your policy proposal in detail...',
                'rows': 6
            }),
            'policy_type': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        
        labels = {
            'title': 'Policy Title',
            'description': 'Policy Description',
            'policy_type': 'Policy Type',
        }