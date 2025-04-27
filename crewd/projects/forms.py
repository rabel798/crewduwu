from django import forms
from .models import Project, Application, Message, TECH_CHOICES

class ProjectForm(forms.ModelForm):
    """Form for creating/editing a project"""
    required_skills = forms.MultipleChoiceField(
        choices=[(tech, tech) for tech in TECH_CHOICES],
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    
    class Meta:
        model = Project
        fields = ['title', 'description', 'team_size', 'duration']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
        # Checkbox select doesn't need form-control
        self.fields['required_skills'].widget.attrs.update({'class': ''})
        
        # If instance has required_skills, pre-select them
        if self.instance.pk and self.instance.required_skills:
            self.initial['required_skills'] = self.instance.get_required_skills_list()
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Convert required_skills list to comma-separated string
        required_skills = self.cleaned_data.get('required_skills', [])
        instance.required_skills = ','.join(required_skills)
        
        if commit:
            instance.save()
        return instance


class ApplicationForm(forms.ModelForm):
    """Form for applying to a project"""
    class Meta:
        model = Application
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5})
        }


class InvitationResponseForm(forms.Form):
    """Form for responding to an invitation"""
    RESPONSE_CHOICES = [
        ('accept', 'Accept Invitation'),
        ('reject', 'Decline Invitation')
    ]
    
    response = forms.ChoiceField(
        choices=RESPONSE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )


class MessageForm(forms.ModelForm):
    """Form for sending a message in a group"""
    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Type your message here...'})
        }


class TechStackAnalysisForm(forms.Form):
    """Form for analyzing tech stack using AI"""
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Enter your project description here...'}),
        label='Project Description'
    )