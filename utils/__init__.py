"""
Utility modules for Deg Bot
"""
from .embeds import create_error_embed, create_success_embed, create_info_embed, create_booking_embed
from .permissions import is_coach, is_admin, coach_only, admin_only

__all__ = [
    'create_error_embed',
    'create_success_embed',
    'create_info_embed',
    'create_booking_embed',
    'is_coach',
    'is_admin',
    'coach_only',
    'admin_only'
]
