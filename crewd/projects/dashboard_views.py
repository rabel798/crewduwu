from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q, Count, F
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth import get_user_model
import json
import os
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_POST
import cohere
from django.conf import settings

from .models import (
    Project, Application, Invitation, Group, GroupMembership, 
    ProjectMembership, Message, TECH_CHOICES, TechStackAnalysis
)
from .forms import ProjectForm, ApplicationForm, InvitationResponseForm, MessageForm
from accounts.models import User
from .grok_api import analyze_tech_stack

User = get_user_model()

class TalentPoolView(LoginRequiredMixin, ListView):
    """View for displaying the talent pool"""
    model = User
    template_name = 'dashboard/company_dashboard.html'
    context_object_name = 'profiles'
    paginate_by = 9

    def get_experience_range(self, experience_level):
        """Map experience level categories to numeric ranges"""
        ranges = {
            'entry': (0, 2),      # 0-2 years
            'junior': (2, 4),     # 2-4 years
            'mid': (4, 7),        # 4-7 years
            'senior': (7, 100),   # 7+ years
        }
        return ranges.get(experience_level, (0, 100))

    def get_queryset(self):
        queryset = User.objects.filter(role='applicant')
        
        # Apply search filters
        search = self.request.GET.get('search')
        role = self.request.GET.get('role')
        experience = self.request.GET.get('experience')
        skills = self.request.GET.getlist('skills')

        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(tech_stack__icontains=search)
            ).distinct()

        if role:
            queryset = queryset.filter(role=role)

        if experience:
            min_exp, max_exp = self.get_experience_range(experience)
            queryset = queryset.filter(
                profile__experience__gte=min_exp,
                profile__experience__lt=max_exp
            )

        if skills:
            for skill in skills:
                queryset = queryset.filter(tech_stack__icontains=skill)

        return queryset.order_by('-date_joined')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tech_choices'] = TECH_CHOICES
        context['search_query'] = self.request.GET.get('search', '')
        context['role_filter'] = self.request.GET.get('role', '')
        context['experience_filter'] = self.request.GET.get('experience', '')
        context['skills_filter'] = self.request.GET.getlist('skills')
        context['experience_levels'] = [
            ('entry', 'Entry Level (0-2 years)'),
            ('junior', 'Junior (2-4 years)'),
            ('mid', 'Mid Level (4-7 years)'),
            ('senior', 'Senior (7+ years)')
        ]
        return context

# Base dashboard view
class DashboardView(LoginRequiredMixin, View):
    """Main dashboard view that redirects to appropriate role-based dashboard"""
    def get(self, request):
        user = request.user
        
        if not user.role:
            return redirect('accounts:role_selection')
        
        if user.role == 'applicant':
            return redirect('projects:dashboard_applicant')
        elif user.role == 'team_leader':
            return redirect('projects:dashboard_leader')
        elif user.role == 'company':
            # Show talent pool for company users
            talent_pool_view = TalentPoolView.as_view()
            return talent_pool_view(request)
        else:
            return redirect('accounts:role_selection')


class SwitchRoleView(LoginRequiredMixin, View):
    """View for switching between roles"""
    def get(self, request):
        user = request.user
        
        if user.role == 'applicant':
            user.role = 'leader'
            user.save()
            messages.success(request, "You've switched to Team Leader view.")
            return redirect('projects:dashboard_leader')
        elif user.role == 'leader':
            user.role = 'applicant'
            user.save()
            messages.success(request, "You've switched to Applicant view.")
            return redirect('projects:dashboard_applicant')
        elif user.role == 'company':
            # Currently "coming soon" - no switching
            messages.info(request, "Company view is coming soon.")
            return redirect('projects:dashboard')
        else:
            return redirect('accounts:role_selection')


class ViewProfileView(LoginRequiredMixin, DetailView):
    """View for viewing a user's profile"""
    model = User
    template_name = 'dashboard/view_profile.html'
    context_object_name = 'profile_user'
    pk_url_kwarg = 'user_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_user = self.get_object()
        
        # Get user's projects
        if profile_user.role == 'leader':
            context['projects'] = Project.objects.filter(creator=profile_user)
        else:
            context['memberships'] = ProjectMembership.objects.filter(
                user=profile_user, 
                status='active'
            ).select_related('project')
        
        # Get tech stack list
        if profile_user.tech_stack:
            context['tech_stack'] = profile_user.get_tech_stack_list()
        
        return context


# Applicant Dashboard Views
class ApplicantDashboardView(LoginRequiredMixin, TemplateView):
    """Applicant's main dashboard view"""
    template_name = 'dashboard/applicant_dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has applicant role
        if request.user.role != 'applicant':
            messages.warning(request, "You need to be an applicant to access this page.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Active applications count (pending applications)
        context['active_applications_count'] = Application.objects.filter(
            applicant=user,
            status='pending'
        ).count()
        
        # Teams joined count (active project memberships)
        context['teams_joined_count'] = ProjectMembership.objects.filter(
            user=user,
            status='active'
        ).count()
        
        # Pending invitations count
        context['pending_invitations_count'] = Invitation.objects.filter(
            recipient=user, 
            status='pending'
        ).count()
        
        # Active projects count (where user is a member)
        context['active_projects_count'] = ProjectMembership.objects.filter(
            user=user, 
            status='active'
        ).count()
        
        # Recent projects (limit to 5)
        context['recent_projects'] = Project.objects.filter(
            status='open'
        ).order_by('-created_at')[:5]
        
        # Get user's applications
        context['applications'] = Application.objects.filter(
            applicant=user
        ).select_related('project', 'project__team_leader').order_by('-created_at')[:5]
        
        return context


class ContributorsListView(LoginRequiredMixin, ListView):
    """View for listing all contributors/users"""
    model = User
    template_name = 'dashboard/applicant/contributors.html'
    context_object_name = 'contributors'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has applicant role
        if request.user.role != 'applicant':
            messages.warning(request, "You need to be an applicant to access this page.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = User.objects.exclude(id=self.request.user.id)
        
        # Apply search filters if provided
        search_query = self.request.GET.get('search', '')
        tech_filter = self.request.GET.get('tech', '')
        
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) | 
                Q(email__icontains=search_query)
            )
        
        if tech_filter:
            queryset = queryset.filter(tech_stack__icontains=tech_filter)
        
        return queryset.order_by('-date_joined')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tech_choices'] = TECH_CHOICES
        context['search_query'] = self.request.GET.get('search', '')
        context['tech_filter'] = self.request.GET.get('tech', '')
        return context


class ProjectsListView(LoginRequiredMixin, ListView):
    """View for listing all projects for applicants"""
    model = Project
    template_name = 'dashboard/projects_list.html'
    context_object_name = 'projects'
    paginate_by = 9
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has applicant role
        if request.user.role != 'applicant':
            messages.warning(request, "You need to be an applicant to access this page.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = Project.objects.all()
        
        # Apply search filters if provided
        search_query = self.request.GET.get('search', '')
        tech_filter = self.request.GET.get('tech', '')
        
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        if tech_filter:
            queryset = queryset.filter(tags__icontains=tech_filter)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tech_choices'] = TECH_CHOICES
        context['search_query'] = self.request.GET.get('search', '')
        context['tech_filter'] = self.request.GET.get('tech', '')
        
        # Check which projects user has already applied to
        user_applications = Application.objects.filter(applicant=self.request.user)
        applied_project_ids = [app.project_id for app in user_applications]
        context['applied_project_ids'] = applied_project_ids
        
        return context


class InvitationsListView(LoginRequiredMixin, ListView):
    """View for listing all invitations for an applicant"""
    model = Invitation
    template_name = 'dashboard/invitations_list.html'
    context_object_name = 'invitations'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has applicant role
        if request.user.role != 'applicant':
            messages.warning(request, "You need to be an applicant to access this page.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return Invitation.objects.filter(
            recipient=self.request.user
        ).select_related('project', 'sender').order_by('-created_at')


class UpdateInvitationView(LoginRequiredMixin, View):
    """View for updating invitation status (accept/reject)"""
    def post(self, request, invitation_id):
        invitation = get_object_or_404(Invitation, id=invitation_id, recipient=request.user)
        action = request.POST.get('action')
        
        if action == 'accept':
            invitation.status = 'accepted'
            invitation.save()
            
            # Add user to project
            project = invitation.project
            ProjectMembership.objects.create(
                project=project,
                user=request.user,
                role='contributor'
            )
            
            # Add user to group
            try:
                group = project.group
                GroupMembership.objects.create(
                    group=group,
                    user=request.user,
                    role='member'
                )
            except Group.DoesNotExist:
                # Create group if it doesn't exist
                group = Group.objects.create(
                    name=f"{project.title} Team",
                    description=f"Group for {project.title} project",
                    project=project
                )
                
                # Add project creator as admin
                GroupMembership.objects.create(
                    group=group,
                    user=project.creator,
                    role='admin'
                )
                
                # Add current user as member
                GroupMembership.objects.create(
                    group=group,
                    user=request.user,
                    role='member'
                )
            
            messages.success(request, f"You have joined {project.title}!")
        
        elif action == 'reject':
            invitation.status = 'rejected'
            invitation.save()
            messages.info(request, f"You declined the invitation to {invitation.project.title}.")
        
        return redirect('projects:invitations_list')


class MyContributionsView(LoginRequiredMixin, ListView):
    """View for listing all projects a user is contributing to"""
    model = ProjectMembership
    template_name = 'dashboard/my_contributions.html'
    context_object_name = 'memberships'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has applicant role
        if request.user.role != 'applicant':
            messages.warning(request, "You need to be an applicant to access this page.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return ProjectMembership.objects.filter(
            user=self.request.user
        ).select_related('project').order_by('-joined_at')


class MyApplicationsView(LoginRequiredMixin, ListView):
    """View for listing all applications submitted by an applicant"""
    model = Application
    template_name = 'dashboard/applicant/my_applications.html'
    context_object_name = 'applications'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has applicant role
        if request.user.role != 'applicant':
            messages.warning(request, "You need to be an applicant to access this page.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        status_filter = self.request.GET.get('status', '')
        
        queryset = Application.objects.filter(
            applicant=self.request.user
        ).select_related('project', 'project__team_leader')
        
        if status_filter and status_filter in ['pending', 'accepted', 'rejected']:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        return context


class GroupsListView(LoginRequiredMixin, ListView):
    """View for listing all groups a user is part of"""
    model = GroupMembership
    template_name = 'dashboard/applicant/groups.html'
    context_object_name = 'memberships'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has a role
        if not request.user.role:
            messages.warning(request, "You need to select a role first.")
            return redirect('accounts:role_selection')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Get all groups where the user is a member, including project and message info
        return GroupMembership.objects.filter(
            user=self.request.user
        ).select_related(
            'group',
            'group__project',
            'group__project__team_leader'
        ).prefetch_related(
            'group__messages',
            'group__members'
        ).order_by('-group__created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any additional context needed for the template
        return context


class ViewGroupView(LoginRequiredMixin, DetailView):
    """View for viewing a group and its chat"""
    model = Group
    template_name = 'dashboard/group_chat.html'
    context_object_name = 'group'
    pk_url_kwarg = 'group_id'
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user is a member of the group
        group = self.get_object()
        if not group.members.filter(id=request.user.id).exists():
            return redirect('projects:groups_list')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = self.get_object()
        
        # Get group messages
        context['messages'] = Message.objects.filter(group=group).order_by('created_at')
        
        # Get group members
        context['members'] = GroupMembership.objects.filter(
            group=group
        ).select_related('user')
        
        # Get project
        context['project'] = group.project
        
        return context
    
    def post(self, request, group_id):
        group = self.get_object()
        message_content = request.POST.get('message', '').strip()
        
        if message_content:
            message = Message.objects.create(
                group=group,
                sender=request.user,
                content=message_content
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': {
                        'content': message.content,
                        'sender': message.sender.username,
                        'created_at': message.created_at.strftime('%b %d, %Y %I:%M %p')
                    }
                })
        
        return redirect('projects:view_group', group_id=group_id)


# Team Leader Dashboard Views
class TeamLeaderDashboardView(LoginRequiredMixin, TemplateView):
    """Team Leader's main dashboard view"""
    template_name = 'dashboard/team_leader_dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has team leader role
        if request.user.role != 'leader':
            messages.warning(request, "You need to be a team leader to access this page.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get projects led by the user
        user_projects = Project.objects.filter(team_leader=user)
        
        # Active projects count (projects with status='open')
        context['active_projects_count'] = user_projects.filter(status='open').count()
        
        # Pending applications count
        context['pending_applications_count'] = Application.objects.filter(
            project__team_leader=user,
            status='pending'
        ).count()
        
        # Team members count (across all projects)
        context['team_members_count'] = ProjectMembership.objects.filter(
            project__team_leader=user,
            status='active'
        ).exclude(user=user).count()  # Exclude the leader themselves
        
        # Completed projects count
        context['completed_projects_count'] = user_projects.filter(status='completed').count()
        
        # Get recent projects for display
        context['recent_projects'] = user_projects.order_by('-created_at')[:5]
        
        # Get recent applications
        context['recent_applications'] = Application.objects.filter(
            project__team_leader=user
        ).select_related('applicant', 'project').order_by('-created_at')[:5]
        
        return context


class MyProjectsView(LoginRequiredMixin, ListView):
    """View for listing all projects created by a team leader"""
    model = Project
    template_name = 'dashboard/my_projects.html'
    context_object_name = 'projects'
    paginate_by = 9
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has team leader role
        if request.user.role != 'leader':
            messages.warning(request, "You need to be a team leader to access this page.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return Project.objects.filter(
            team_leader=self.request.user
        ).order_by('-created_at')


class CreateProjectView(LoginRequiredMixin, CreateView):
    """View for creating a new project"""
    model = Project
    form_class = ProjectForm
    template_name = 'dashboard/leader/create_project.html'
    success_url = reverse_lazy('projects:my_projects')
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has team leader role
        if request.user.role != 'leader':
            messages.warning(request, "You need to be a team leader to create projects.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tech_choices'] = TECH_CHOICES
        return context
    
    def form_valid(self, form):
        # Set both creator and team_leader to the current user
        form.instance.creator = self.request.user
        form.instance.team_leader = self.request.user
        response = super().form_valid(form)
        
        # Create a group for the project
        group = Group.objects.create(
            name=f"{form.instance.title} Team",
            description=f"Group for {form.instance.title} project",
            project=form.instance
        )
        
        # Add project creator as admin
        GroupMembership.objects.create(
            group=group,
            user=self.request.user,
            role='admin'
        )
        
        # Add project creator as member too
        ProjectMembership.objects.create(
            project=form.instance,
            user=self.request.user,
            role='leader'
        )
        
        messages.success(self.request, f"{form.instance.title} created successfully!")
        return response


class ManageProjectView(LoginRequiredMixin, DetailView):
    """View for managing a project"""
    model = Project
    template_name = 'dashboard/manage_project.html'
    context_object_name = 'project'
    pk_url_kwarg = 'project_id'
    
    def dispatch(self, request, *args, **kwargs):
        project = self.get_object()
        # Ensure user is the team leader
        if project.team_leader != request.user:
            messages.error(request, "You don't have permission to manage this project.")
            return redirect('projects:my_projects')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()
        
        # Project applications
        context['applications'] = Application.objects.filter(
            project=project
        ).select_related('applicant').order_by('-created_at')
        
        # Project members
        context['memberships'] = ProjectMembership.objects.filter(
            project=project
        ).select_related('user').order_by('-joined_at')
        
        # Get tech stack analyses
        context['analyses'] = TechStackAnalysis.objects.filter(
            project=project
        ).order_by('-created_at')
        
        return context
    
    def post(self, request, project_id):
        project = self.get_object()
        action = request.POST.get('action')
        
        if action == 'update_status':
            status = request.POST.get('status')
            if status in ['active', 'completed', 'cancelled']:
                project.status = status
                project.save()
                messages.success(request, f"Project status updated to {status}.")
        elif action == 'update_project':
            # Update project details
            team_size = request.POST.get('team_size')
            duration = request.POST.get('duration')
            required_skills = request.POST.getlist('required_skills')
            
            project.team_size = int(team_size)
            project.duration = duration
            project.required_skills = ','.join(required_skills)
            project.save()
            
            messages.success(request, "Project details updated successfully!")
        
        return redirect('projects:manage_project', project_id=project_id)


class FindContributorsView(LoginRequiredMixin, ListView):
    """View for finding potential contributors based on tech stack"""
    model = User
    template_name = 'dashboard/find_contributors.html'
    context_object_name = 'contributors'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has team leader role
        if request.user.role != 'leader':
            messages.warning(request, "You need to be a team leader to access this page.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(Project, id=project_id)
        
        # Ensure user is the project creator
        if project.creator != self.request.user:
            return User.objects.none()
        
        # Get users with matching tech stack
        required_skills = project.get_required_skills_list()
        queryset = User.objects.filter(role='applicant').exclude(id=self.request.user.id)
        
        # Calculate match score for each user
        for user in queryset:
            if user.tech_stack:
                user_skills = user.get_tech_stack_list()
                match_score = sum(1 for skill in required_skills if skill in user_skills)
                match_percent = int(match_score / len(required_skills) * 100) if required_skills else 0
                user.match_score = match_score
                user.match_percent = match_percent
            else:
                user.match_score = 0
                user.match_percent = 0
        
        # Sort by match score (higher first)
        queryset = sorted(queryset, key=lambda u: u.match_score, reverse=True)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(Project, id=project_id)
        context['project'] = project
        
        # Get already invited users
        invited_user_ids = Invitation.objects.filter(
            project=project
        ).values_list('recipient_id', flat=True)
        context['invited_user_ids'] = invited_user_ids
        
        # Get already accepted users
        accepted_user_ids = ProjectMembership.objects.filter(
            project=project
        ).values_list('user_id', flat=True)
        context['accepted_user_ids'] = accepted_user_ids
        
        return context


class InviteContributorView(LoginRequiredMixin, View):
    """View for inviting a contributor to a project"""
    def post(self, request, project_id, user_id):
        project = get_object_or_404(Project, id=project_id)
        user = get_object_or_404(User, id=user_id)
        
        # Ensure user is the project creator
        if project.creator != request.user:
            messages.error(request, "You don't have permission to invite users to this project.")
            return redirect('projects:my_projects')
        
        # Check if user is already invited
        if Invitation.objects.filter(project=project, recipient=user).exists():
            messages.warning(request, f"{user.username} is already invited to this project.")
            return redirect('projects:find_contributors', project_id=project_id)
        
        # Check if user is already a member
        if ProjectMembership.objects.filter(project=project, user=user).exists():
            messages.warning(request, f"{user.username} is already a member of this project.")
            return redirect('projects:find_contributors', project_id=project_id)
        
        # Create invitation
        message = request.POST.get('message', '')
        Invitation.objects.create(
            project=project,
            sender=request.user,
            recipient=user,
            message=message
        )
        
        messages.success(request, f"Invitation sent to {user.username}!")
        return redirect('projects:find_contributors', project_id=project_id)


class SentInvitationsView(LoginRequiredMixin, ListView):
    """View for listing all invitations sent by a team leader"""
    model = Invitation
    template_name = 'dashboard/leader/sent_invitations.html'
    context_object_name = 'invitations'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has team leader role
        if request.user.role != 'leader':
            messages.warning(request, "You need to be a team leader to access this page.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return Invitation.objects.filter(
            sender=self.request.user
        ).select_related('project', 'recipient').order_by('-created_at')


class CancelInvitationView(LoginRequiredMixin, View):
    """View for canceling a sent invitation"""
    def post(self, request, invitation_id):
        invitation = get_object_or_404(Invitation, id=invitation_id, sender=request.user)
        
        # Only cancel if still pending
        if invitation.status == 'pending':
            invitation.delete()
            messages.success(request, "Invitation cancelled successfully.")
        else:
            messages.warning(request, "Cannot cancel an invitation that has already been accepted or rejected.")
        
        return redirect('projects:sent_invitations')


class ApplicationsListView(LoginRequiredMixin, ListView):
    """View for listing all applications to a team leader's projects"""
    model = Application
    template_name = 'dashboard/leader/applications.html'
    context_object_name = 'applications'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        # Ensure user has team leader role
        if request.user.role != 'leader':
            messages.warning(request, "You need to be a team leader to access this page.")
            return redirect('projects:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        status_filter = self.request.GET.get('status', '')
        
        queryset = Application.objects.filter(
            project__team_leader=self.request.user
        ).select_related('project', 'applicant')
        
        if status_filter and status_filter in ['pending', 'accepted', 'rejected']:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        return context


class ViewApplicationView(LoginRequiredMixin, DetailView):
    """View for viewing a specific application"""
    model = Application
    template_name = 'dashboard/view_application.html'
    context_object_name = 'application'
    pk_url_kwarg = 'application_id'
    
    def dispatch(self, request, *args, **kwargs):
        application = self.get_object()
        # Ensure user is the team leader
        if application.project.team_leader != request.user:
            messages.error(request, "You don't have permission to view this application.")
            return redirect('projects:applications_list')
        return super().dispatch(request, *args, **kwargs)


class UpdateApplicationView(LoginRequiredMixin, View):
    """View for updating application status (accept/reject)"""
    def post(self, request, application_id):
        application = get_object_or_404(Application, id=application_id)
        
        # Ensure user is the team leader
        if application.project.team_leader != request.user:
            messages.error(request, "You don't have permission to update this application.")
            return redirect('projects:applications_list')
        
        action = request.POST.get('action')
        
        if action == 'accept' and application.status == 'pending':
            try:
                # Start transaction to ensure all operations succeed or none do
                with transaction.atomic():
                    # Update application status
                    application.status = 'accepted'
                    application.save()
                    
                    # Add user to project
                    project_membership = ProjectMembership.objects.create(
                        project=application.project,
                        user=application.applicant,
                        role='contributor'
                    )
                    
                    # Get or create project group
                    group, created = Group.objects.get_or_create(
                        project=application.project,
                        defaults={
                            'name': f"{application.project.title} Team",
                            'description': f"Group for {application.project.title} project"
                        }
                    )
                    
                    # Add applicant to group if not already a member
                    if not GroupMembership.objects.filter(group=group, user=application.applicant).exists():
                        GroupMembership.objects.create(
                            group=group,
                            user=application.applicant,
                            role='member'
                        )
                    
                    # Ensure team leader is admin of the group
                    GroupMembership.objects.get_or_create(
                        group=group,
                        user=application.project.team_leader,
                        defaults={'role': 'admin'}
                    )
                    
                    # Create welcome message in the group
                    Message.objects.create(
                        group=group,
                        sender=application.project.team_leader,
                        content=f"Welcome {application.applicant.username} to the team!"
                    )
                    
                    messages.success(
                        request, 
                        f"{application.applicant.username} has been added to the project and team group!"
                    )
            
            except Exception as e:
                messages.error(request, f"Error accepting application: {str(e)}")
                return redirect('projects:applications_list')
                    
        elif action == 'reject' and application.status == 'pending':
            application.status = 'rejected'
            application.save()
            messages.info(request, f"Application from {application.applicant.username} rejected.")
        
        return redirect('projects:applications_list')


def analyze_tech_stack_simple(description):
    """Simple tech stack analysis using text matching"""
    description_lower = description.lower()
    tech_list = []
    
    # Map of common terms to technologies
    tech_mapping = {
        'web': ['HTML/CSS', 'JavaScript', 'React', 'Django'],
        'frontend': ['HTML/CSS', 'JavaScript', 'React', 'Vue', 'Angular'],
        'backend': ['Python', 'Django', 'Node.js', 'Java', 'PostgreSQL'],
        'database': ['PostgreSQL', 'MySQL', 'MongoDB', 'Redis'],
        'mobile': ['React', 'Mobile Development', 'Swift', 'Kotlin'],
        'cloud': ['AWS', 'Azure', 'Google Cloud', 'Docker'],
        'ai': ['Python', 'Machine Learning', 'Data Science'],
        'api': ['REST API', 'GraphQL', 'Node.js', 'Django'],
        'microservices': ['Docker', 'Kubernetes', 'Microservices'],
    }
    
    # First, check for exact matches
    for tech in TECH_CHOICES:
        if tech.lower() in description_lower:
            tech_list.append(tech)
    
    # Then, check for keyword matches
    for keyword, techs in tech_mapping.items():
        if keyword in description_lower:
            for tech in techs:
                if tech not in tech_list and tech in TECH_CHOICES:
                    tech_list.append(tech)
    
    # If no matches found, add some default full-stack technologies
    if not tech_list:
        tech_list = ['Python', 'JavaScript', 'HTML/CSS', 'PostgreSQL']
    
    # Limit to top 7 most relevant
    return tech_list[:7]

class AnalyzeTechStackView(LoginRequiredMixin, View):
    """View to analyze project description and suggest tech stack from predefined choices."""
    
    def post(self, request, project_id=None):
        # If project_id is provided, verify ownership
        if project_id:
            project = get_object_or_404(Project, id=project_id)
            if project.team_leader != request.user:
                return JsonResponse({'error': 'Unauthorized'}, status=403)
            description = project.description
        else:
            # For new projects, get description from POST data
            description = request.POST.get('description', '').strip()
            if not description:
                return JsonResponse({
                    'error': 'Project description is required',
                    'message': 'Please provide a project description.'
                }, status=400)
        
        try:
            # Get tech stack suggestions using simple text matching
            suggested_tech_stack = analyze_tech_stack_simple(description)
            
            if not suggested_tech_stack:
                return JsonResponse({
                    'message': 'No relevant tech stack suggestions found for your project description.',
                    'tech_stack': [],
                    'recommendations': []
                }, status=200)
            
            # If we have a project, save the analysis
            if project_id:
                analysis = TechStackAnalysis.objects.create(
                    project=project,
                    description=description,
                    analysis_result={
                        'suggested_tech_stack': suggested_tech_stack,
                        'analyzed_at': str(timezone.now())
                    }
                )
                
                # Update project's required skills
                project.required_skills = ', '.join(suggested_tech_stack)
                project.save()
            
            # Find matching profiles
            matching_profiles = []
            for user in User.objects.filter(role='applicant').exclude(id=request.user.id):
                if user.tech_stack:
                    user_skills = user.get_tech_stack_list()
                    matches = set(suggested_tech_stack) & set(user_skills)
                    match_score = len(matches) / len(suggested_tech_stack) * 100
                    
                    if match_score > 0:
                        matching_profiles.append({
                            'id': user.id,
                            'username': user.username,
                            'tech_stack': user.tech_stack,
                            'match_score': int(match_score),
                            'matching_skills': list(matches)
                        })
            
            # Sort by match score and get top 5
            matching_profiles.sort(key=lambda x: x['match_score'], reverse=True)
            top_matches = matching_profiles[:5]
            
            return JsonResponse({
                'tech_stack': suggested_tech_stack,
                'message': 'Tech stack analysis completed successfully',
                'recommendations': top_matches
            })
            
        except Exception as e:
            print(f"Error in tech stack analysis: {str(e)}")  # Add logging
            return JsonResponse({
                'error': str(e),
                'message': 'Error analyzing tech stack. Please try again.'
            }, status=500)

class RecommendedContributorsView(LoginRequiredMixin, View):
    """API view for getting recommended contributors based on tech stack"""
    def get(self, request):
        skills = request.GET.get('skills', '').split(',')
        skills = [s.strip() for s in skills if s.strip()]
        
        # Get users with matching tech stack
        users = User.objects.filter(role='applicant').exclude(id=request.user.id)
        
        # Calculate match scores
        recommended = []
        for user in users:
            if user.tech_stack:
                user_skills = user.get_tech_stack_list()
                match_score = sum(1 for skill in skills if skill in user_skills)
                match_percent = int((match_score / len(skills)) * 100) if skills else 0
                
                if match_percent > 0:  # Only include users with some match
                    recommended.append({
                        'id': user.id,
                        'username': user.username,
                        'tech_stack': user.tech_stack,
                        'match_score': match_percent
                    })
        
        # Sort by match score
        recommended.sort(key=lambda x: x['match_score'], reverse=True)
        
        return JsonResponse(recommended[:5], safe=False)  # Return top 5 matches

class InviteContributorAPIView(LoginRequiredMixin, View):
    """API view for inviting a contributor"""
    def post(self, request, user_id):
        if not request.user.role == 'team_leader':
            return JsonResponse({'error': 'You must be a team leader to send invitations'}, status=403)
            
        try:
            data = json.loads(request.body)
            description = data.get('description', '')
            title = f"Project with {request.user.username}"  # Create a title for the project
            
            recipient = User.objects.get(id=user_id)
            
            # Create the project with correct fields
            project = Project.objects.create(
                title=title,
                description=description,
                team_leader=request.user,  # Only use team_leader field
                team_size=5,  # Set a default team size
                duration="Not specified",  # Set a default duration
                status='open'
            )
            
            # Create a group for the project
            group = Group.objects.create(
                name=f"{project.title} Team",
                description=f"Group for {project.title} project",
                project=project
            )
            
            # Add project leader as admin and member
            GroupMembership.objects.create(
                group=group,
                user=request.user,
                role='admin'
            )
            
            ProjectMembership.objects.create(
                project=project,
                user=request.user,
                role='leader'
            )
            
            # Check if user is already invited
            if Invitation.objects.filter(project=project, recipient=recipient, status='pending').exists():
                return JsonResponse({'error': 'User has already been invited to this project'}, status=400)
            
            # Check if user is already a member
            if ProjectMembership.objects.filter(project=project, user=recipient).exists():
                return JsonResponse({'error': 'User is already a member of this project'}, status=400)
            
            # Create invitation
            invitation = Invitation.objects.create(
                project=project,
                sender=request.user,
                recipient=recipient,
                message=f"You've been invited to join {project.title}! Project Description: {description[:200]}..."
            )
            
            return JsonResponse({
                'status': 'success',
                'message': f'Invitation sent to {recipient.username}',
                'project_id': project.id
            })
            
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid request data'}, status=400)
        except Exception as e:
            print(f"Error creating invitation: {str(e)}")  # Add logging
            return JsonResponse({'error': str(e)}, status=500)

@require_POST
def rewrite_description(request):
    try:
        description = request.POST.get('description', '')
        if not description:
            return JsonResponse({'error': True, 'message': 'Description is required'})
        
        # Initialize Cohere client
        co = cohere.Client(settings.COHERE_API_KEY)
        
        # Generate a rewritten version of the description
        response = co.generate(
            prompt=f"Rewrite the following project description to be more professional and engaging while maintaining the same meaning:\n\n{description}",
            max_tokens=500,
            temperature=0.7,
            k=0,
            stop_sequences=[],
            return_likelihoods='NONE'
        )
        
        rewritten_description = response.generations[0].text.strip()
        
        return JsonResponse({
            'error': False,
            'rewritten_description': rewritten_description
        })
        
    except Exception as e:
        return JsonResponse({
            'error': True,
            'message': str(e)
        })
