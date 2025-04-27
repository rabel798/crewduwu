from django.shortcuts import render

def index(request):
    """Landing page view with animated logo and auth transition"""
    context = {
        'hide_auth_links': True  # Hide auth links in the navbar since we're showing them in the animation
    }
    return render(request, 'index.html', context)
