from django import template

register = template.Library()

@register.filter
def status_color(status):
    """Returns the appropriate Bootstrap color class for a hackathon status"""
    status_colors = {
        'upcoming': 'primary',
        'active': 'success',
        'completed': 'secondary',
        'cancelled': 'danger'
    }
    return status_colors.get(status.lower(), 'secondary') 