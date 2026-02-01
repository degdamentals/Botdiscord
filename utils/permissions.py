"""
Permission checking utilities and decorators
"""
import discord
from discord.ext import commands
from functools import wraps
import config

def is_coach(member: discord.Member) -> bool:
    """
    Check if a member has the coach role
    """
    if not member.guild:
        return False
    coach_role = member.guild.get_role(config.COACH_ROLE_ID)
    return coach_role in member.roles if coach_role else False


def is_admin(member: discord.Member) -> bool:
    """
    Check if a member has administrator permissions
    """
    return member.guild_permissions.administrator


def coach_only():
    """
    Decorator to restrict commands to coaches only
    """
    async def predicate(ctx):
        if not isinstance(ctx.author, discord.Member):
            raise commands.CheckFailure("Cette commande ne peut être utilisée qu'en serveur.")

        if not is_coach(ctx.author) and not is_admin(ctx.author):
            raise commands.CheckFailure("❌ Vous devez être coach pour utiliser cette commande.")

        return True

    return commands.check(predicate)


def admin_only():
    """
    Decorator to restrict commands to admins only
    """
    async def predicate(ctx):
        if not isinstance(ctx.author, discord.Member):
            raise commands.CheckFailure("Cette commande ne peut être utilisée qu'en serveur.")

        if not is_admin(ctx.author):
            raise commands.CheckFailure("❌ Vous devez être administrateur pour utiliser cette commande.")

        return True

    return commands.check(predicate)


def in_ticket_channel():
    """
    Decorator to check if command is used in a ticket channel
    """
    async def predicate(ctx):
        if not ctx.channel.category_id == config.TICKET_CATEGORY_ID:
            raise commands.CheckFailure("❌ Cette commande ne peut être utilisée que dans un ticket.")

        return True

    return commands.check(predicate)
