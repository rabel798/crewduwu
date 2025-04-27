from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField

# Define tech stack choices
TECH_CHOICES = [
    'Python', 'Django', 'Flask', 'JavaScript', 'React', 'Vue', 'Angular', 
    'Node.js', 'Express', 'HTML/CSS', 'Bootstrap', 'Tailwind CSS', 
    'PHP', 'Laravel', 'CodeIgniter', 'Ruby', 'Ruby on Rails', 
    'Java', 'Spring', 'C#', '.NET', 'Go', 'Rust', 'Swift', 'Kotlin',
    'SQL', 'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Firebase',
    'Docker', 'Kubernetes', 'AWS', 'Azure', 'Google Cloud',
    'GraphQL', 'REST API', 'WebSockets', 'Microservices', 
    'Machine Learning', 'Data Science', 'UI/UX Design', 'Mobile Development'
]

class User(AbstractUser):
    """Custom user model with additional fields"""
    email = models.EmailField(unique=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    tech_stack = models.TextField(null=True, blank=True)  # Comma-separated list
    ROLE_CHOICES = [
        ('applicant', 'Applicant'),
        ('team_leader', 'Team Leader'),
        ('company', 'Company'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, null=True, blank=True, default='applicant')
    created_at = models.DateTimeField(default=timezone.now)
    
    # Hackathon and rating fields
    hackathon_rating = models.FloatField(default=100.0)
    hackathon_wins = models.IntegerField(default=0)
    total_upvotes = models.IntegerField(default=0)
    total_projects = models.IntegerField(default=0)
    last_rating_update = models.DateTimeField(auto_now=True)
    
    def get_tech_stack_list(self):
        """Return tech stack as a list"""
        if not self.tech_stack:
            return []
        return [tech.strip() for tech in self.tech_stack.split(',')]
    
    def __str__(self):
        return self.username

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True)
    skills = models.TextField(
        blank=True,
        help_text="Comma-separated list of technical skills"
    )
    experience = models.IntegerField(default=0, help_text="Experience in years")
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)
    resume = models.FileField(upload_to='resumes/', blank=True)

    def get_skills_list(self):
        """Convert comma-separated skills string to list"""
        return [skill.strip() for skill in self.skills.split(',') if skill.strip()]

    def set_skills_list(self, skills_list):
        """Convert skills list to comma-separated string"""
        self.skills = ', '.join(skills_list)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    class Meta:
        db_table = 'accounts_userprofile'