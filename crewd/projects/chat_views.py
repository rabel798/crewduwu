from django.shortcuts import get_object_or_404, render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils import timezone
from django.template.defaultfilters import date as date_filter

from .models import Group, Message, GroupMembership

class SendMessageView(LoginRequiredMixin, View):
    """API view for sending a message in a group chat"""
    def post(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        
        # Ensure user is a member of the group
        if not group.members.filter(id=request.user.id).exists():
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        content = request.POST.get('content', '').strip()
        if not content:
            return JsonResponse({'error': 'Message content is required'}, status=400)
        
        # Create message
        message = Message.objects.create(
            group=group,
            sender=request.user,
            content=content
        )
        
        return JsonResponse({
            'status': 'success',
            'message': {
                'id': message.id,
                'content': message.content,
                'time': date_filter(message.created_at, "g:i A")
            }
        })

class GetNewMessagesView(LoginRequiredMixin, View):
    """API view for polling new messages"""
    def get(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        
        # Ensure user is a member of the group
        if not group.members.filter(id=request.user.id).exists():
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        last_message_id = request.GET.get('last_message_id', '0')
        
        # Get new messages
        messages = Message.objects.filter(
            group=group,
            id__gt=last_message_id
        ).select_related('sender').order_by('created_at')
        
        return JsonResponse({
            'messages': [{
                'id': message.id,
                'content': message.content,
                'sender_name': message.sender.username,
                'sender_avatar': message.sender.profile_picture.url if message.sender.profile_picture else None,
                'time': date_filter(message.created_at, "g:i A")
            } for message in messages]
        })

class ViewGroupChatView(LoginRequiredMixin, View):
    """View for the group chat page"""
    def get(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        
        # Ensure user is a member of the group
        if not group.members.filter(id=request.user.id).exists():
            return redirect('projects:groups_list')
        
        # Get messages with sender info
        chat_messages = Message.objects.filter(
            group=group
        ).select_related('sender').order_by('created_at')
        
        # Get group memberships with user info
        group_memberships = GroupMembership.objects.filter(
            group=group
        ).select_related('user').order_by('user__username')
        
        return render(request, 'dashboard/chat.html', {
            'group': group,
            'project': group.project,
            'messages': chat_messages,
            'group_memberships': group_memberships
        })
        
    def post(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        
        # Ensure user is a member of the group
        if not group.members.filter(id=request.user.id).exists():
            return redirect('projects:groups_list')
        
        content = request.POST.get('content', '').strip()
        if content:
            # Create message
            Message.objects.create(
                group=group,
                sender=request.user,
                content=content
            )
        
        return redirect('projects:group_chat', group_id=group_id) 