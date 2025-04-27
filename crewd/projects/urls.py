from django.urls import path
from . import views
from . import dashboard_views
from .chat_views import SendMessageView, GetNewMessagesView, ViewGroupChatView

app_name = 'projects'

urlpatterns = [
    # Regular project views
    path('', views.ProjectListView.as_view(), name='project_list'),
    path('create/', dashboard_views.CreateProjectView.as_view(), name='create_project'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('<int:pk>/apply/', views.ApplyToProjectView.as_view(), name='apply_project'),
    
    # Dashboard views - Shared
    path('dashboard/', dashboard_views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/switch-role/', dashboard_views.SwitchRoleView.as_view(), name='dashboard_switch_role'),
    path('profile/<int:user_id>/', dashboard_views.ViewProfileView.as_view(), name='view_profile'),
    
    # Dashboard views - Applicant
    path('dashboard/applicant/', dashboard_views.ApplicantDashboardView.as_view(), name='dashboard_applicant'),
    path('dashboard/contributors/', dashboard_views.ContributorsListView.as_view(), name='contributors_list'),
    path('dashboard/projects/list/', dashboard_views.ProjectsListView.as_view(), name='projects_list'),
    path('dashboard/invitations/', dashboard_views.InvitationsListView.as_view(), name='invitations_list'),
    path('dashboard/invitations/<int:invitation_id>/update/', dashboard_views.UpdateInvitationView.as_view(), name='update_invitation'),
    path('dashboard/contributions/', dashboard_views.MyContributionsView.as_view(), name='my_contributions'),
    path('dashboard/applications/', dashboard_views.MyApplicationsView.as_view(), name='my_applications'),
    path('dashboard/groups/', dashboard_views.GroupsListView.as_view(), name='groups_list'),
    
    # Dashboard views - Team Leader
    path('dashboard/leader/', dashboard_views.TeamLeaderDashboardView.as_view(), name='dashboard_leader'),
    path('dashboard/my-projects/', dashboard_views.MyProjectsView.as_view(), name='my_projects'),
    path('dashboard/create-project/', dashboard_views.CreateProjectView.as_view(), name='create_project'),
    path('dashboard/projects/<int:project_id>/manage/', dashboard_views.ManageProjectView.as_view(), name='manage_project'),
    path('dashboard/projects/<int:project_id>/find-contributors/', dashboard_views.FindContributorsView.as_view(), name='find_contributors'),
    path('dashboard/projects/<int:project_id>/invite/<int:user_id>/', dashboard_views.InviteContributorView.as_view(), name='invite_contributor'),
    path('dashboard/sent-invitations/', dashboard_views.SentInvitationsView.as_view(), name='sent_invitations'),
    path('dashboard/invitations/<int:invitation_id>/cancel/', dashboard_views.CancelInvitationView.as_view(), name='cancel_invitation'),
    path('dashboard/applications/', dashboard_views.ApplicationsListView.as_view(), name='applications_list'),
    path('dashboard/applications/<int:application_id>/', dashboard_views.ViewApplicationView.as_view(), name='view_application'),
    path('dashboard/applications/<int:application_id>/update/', dashboard_views.UpdateApplicationView.as_view(), name='update_application'),
    
    # API endpoints
    path('api/analyze-tech-stack/', dashboard_views.AnalyzeTechStackView.as_view(), name='analyze_tech_stack'),
    path('api/analyze-tech-stack/<int:project_id>/', dashboard_views.AnalyzeTechStackView.as_view(), name='analyze_tech_stack_project'),
    path('api/recommended-contributors/', dashboard_views.RecommendedContributorsView.as_view(), name='recommended_contributors'),
    path('api/invite-contributor/<int:user_id>/', dashboard_views.InviteContributorAPIView.as_view(), name='invite_contributor_api'),

    # Chat URLs
    path('groups/<int:group_id>/chat/', ViewGroupChatView.as_view(), name='group_chat'),
    path('groups/<int:group_id>/send-message/', SendMessageView.as_view(), name='send_message'),
    path('groups/<int:group_id>/get-messages/', GetNewMessagesView.as_view(), name='get_new_messages'),
    path('dashboard/company/', views.CompanyDashboardView.as_view(), name='dashboard_company'),
    path('talent-pool/', views.TalentPoolView.as_view(), name='talent_pool'),
    path('rewrite-description/', dashboard_views.rewrite_description, name='rewrite_description'),
]