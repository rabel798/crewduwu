from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('role-selection/', views.RoleSelectionView.as_view(), name='role_selection'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('settings/', views.SettingsView.as_view(), name='settings'),
    path('logout/', views.logout_view, name='logout'),
    path('api/scrape-linkedin-skills/', views.ScrapeLinkedInSkillsView.as_view(), name='scrape_linkedin_skills'),
]