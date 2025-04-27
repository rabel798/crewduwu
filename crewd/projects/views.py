from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.views import View
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Project, Application
from accounts.models import TECH_CHOICES, UserProfile
from .forms import ProjectForm
from .services import ProjectTaggingService

class ProjectListView(ListView):
    """View for listing all projects"""
    model = Project
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'
    paginate_by = 9
    
    def get_queryset(self):
        return Project.objects.filter(status='active').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tech_choices'] = TECH_CHOICES
        return context


class ProjectDetailView(DetailView):
    """View for viewing a project's details"""
    model = Project
    template_name = 'projects/project_detail.html'
    context_object_name = 'project'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()
        
        # Check if the user has already applied
        if self.request.user.is_authenticated:
            context['has_applied'] = Application.objects.filter(
                project=project, 
                applicant=self.request.user
            ).exists()
            
            # Check if the user is the project leader
            context['is_creator'] = (project.team_leader == self.request.user)
            
            # Check if the user is a member
            context['is_member'] = project.members.filter(id=self.request.user.id).exists()
        
        # Get team members (excluding the leader if one exists)
        if project.team_leader:
            context['team_members'] = project.members.exclude(id=project.team_leader.id)
        else:
            context['team_members'] = project.members.all()
        
        return context


@login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.team_leader = request.user
            
            # Generate tags using Groq API
            tagging_service = ProjectTaggingService()
            tags = tagging_service.generate_tags(project.description)
            project.set_tags_list(tags)
            project.save()

            # Get profile recommendations
            applicant_profiles = UserProfile.objects.filter(role='applicant')
            profile_data = [{
                'user': profile.user,
                'skills': profile.skills,  # Now using the text field directly
                'experience': profile.experience
            } for profile in applicant_profiles]
            
            recommendations = tagging_service.get_profile_recommendations(
                tags,
                profile_data
            )

            return render(request, 'projects/project_created.html', {
                'project': project,
                'recommendations': recommendations[:5]  # Top 5 recommendations
            })
    else:
        form = ProjectForm()
    
    return render(request, 'projects/create_project.html', {'form': form})


class ApplyToProjectView(LoginRequiredMixin, View):
    """View for applying to a project"""
    
    def get(self, request, pk):
        project = Project.objects.get(pk=pk)
        
        # Check if the user is the leader
        if project.team_leader == request.user:
            messages.error(request, "You cannot apply to your own project.")
            return redirect('projects:project_detail', pk=pk)
        
        # Check if the user has already applied
        if Application.objects.filter(project=project, applicant=request.user).exists():
            messages.warning(request, "You have already applied to this project.")
            return redirect('projects:project_detail', pk=pk)
        
        # Check if the user is already a member
        if project.members.filter(id=request.user.id).exists():
            messages.warning(request, "You are already a member of this project.")
            return redirect('projects:project_detail', pk=pk)
        
        return render(request, 'projects/apply_project.html', {'project': project})
    
    def post(self, request, pk):
        project = Project.objects.get(pk=pk)
        message = request.POST.get('message', '')
        
        # Create application
        Application.objects.create(
            project=project,
            applicant=request.user,
            message=message
        )
        
        messages.success(request, f"Your application for {project.title} has been submitted!")
        return redirect('projects:project_detail', pk=pk)


class DashboardView(LoginRequiredMixin, View):
    """View for the user's dashboard"""
    
    def get(self, request):
        user = request.user
        
        if user.role == 'applicant':
            return redirect('projects:dashboard_applicant')
        elif user.role == 'leader':
            return redirect('projects:dashboard_leader')
        elif user.role == 'company':
            # Show talent pool for company users
            talent_pool_view = TalentPoolView.as_view()
            return talent_pool_view(request)
        else:
            # Default to role selection
            return redirect('accounts:role_selection')


class TalentPoolView(LoginRequiredMixin, ListView):
    template_name = 'dashboard/talent_pool.html'
    context_object_name = 'profiles'
    paginate_by = 9

    def get_queryset(self):
        User = get_user_model()
        queryset = User.objects.filter(role='applicant').select_related('profile')

        # Apply search filters
        search = self.request.GET.get('search')
        role = self.request.GET.get('role')
        experience = self.request.GET.get('experience')

        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(profile__skills__name__icontains=search)
            ).distinct()

        if role:
            queryset = queryset.filter(profile__role=role)

        if experience:
            queryset = queryset.filter(profile__experience_level=experience)

        return queryset


class CompanyDashboardView(LoginRequiredMixin, TemplateView):
    """View for company dashboard"""
    template_name = 'dashboard/company_dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        # Ensure user has company role
        if request.user.role != 'company':
            messages.warning(request, "You need to be a company to access this page.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Add company-specific context data
        context['total_projects'] = Project.objects.filter(team_leader=user).count()
        context['active_projects'] = Project.objects.filter(team_leader=user, status='active').count()
        context['total_applications'] = Application.objects.filter(project__team_leader=user).count()
        context['pending_applications'] = Application.objects.filter(project__team_leader=user, status='pending').count()

        return context