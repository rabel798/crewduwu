from django import template

register = template.Library()

@register.filter
def status_color(status):
    color_map = {
        'upcoming': 'info',
        'ongoing': 'success',
        'completed': 'secondary',
        'cancelled': 'danger',
        'registered': 'info',
        'submitted': 'primary',
        'disqualified': 'danger',
        'winner': 'success',
        'runner_up': 'warning'
    }
    return color_map.get(status, 'secondary') 