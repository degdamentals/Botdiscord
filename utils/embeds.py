"""
Reusable Discord embed utilities
"""
import discord
from datetime import datetime
from typing import Optional
import config

def create_base_embed(
    title: str,
    description: str,
    color: int,
    timestamp: bool = True
) -> discord.Embed:
    """
    Create a base embed with common settings
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    if timestamp:
        embed.timestamp = datetime.utcnow()
    return embed


def create_error_embed(description: str, title: str = "❌ Erreur") -> discord.Embed:
    """
    Create an error embed
    """
    return create_base_embed(title, description, config.ERROR_COLOR)


def create_success_embed(description: str, title: str = "✅ Succès") -> discord.Embed:
    """
    Create a success embed
    """
    return create_base_embed(title, description, config.SUCCESS_COLOR)


def create_info_embed(description: str, title: str = "ℹ️ Information") -> discord.Embed:
    """
    Create an info embed
    """
    return create_base_embed(title, description, config.BOT_COLOR)


def create_warning_embed(description: str, title: str = "⚠️ Attention") -> discord.Embed:
    """
    Create a warning embed
    """
    return create_base_embed(title, description, config.WARNING_COLOR)


def create_booking_embed(
    booking_type: str,
    scheduled_at: datetime,
    duration: int,
    client_name: str,
    booking_id: Optional[int] = None
) -> discord.Embed:
    """
    Create an embed for booking confirmation
    """
    type_emoji = "🆓" if booking_type == config.BOOKING_TYPE_FREE else "💰"
    type_label = "Coaching Gratuit" if booking_type == config.BOOKING_TYPE_FREE else "Coaching Payant"

    embed = discord.Embed(
        title=f"{type_emoji} Réservation confirmée",
        description=f"Votre session de {type_label.lower()} a été réservée avec succès!",
        color=config.SUCCESS_COLOR
    )

    # Format date
    scheduled_str = scheduled_at.strftime("%d/%m/%Y à %H:%M")

    embed.add_field(
        name="📅 Date et heure",
        value=scheduled_str,
        inline=True
    )
    embed.add_field(
        name="⏱️ Durée",
        value=f"{duration} minutes",
        inline=True
    )
    embed.add_field(
        name="👤 Client",
        value=client_name,
        inline=True
    )
    embed.add_field(
        name="📝 Type",
        value=type_label,
        inline=True
    )

    if booking_id:
        embed.add_field(
            name="🆔 ID de réservation",
            value=f"`{booking_id}`",
            inline=True
        )

    embed.set_footer(text="Vous recevrez des rappels 24h et 1h avant la session")
    embed.timestamp = datetime.utcnow()

    return embed


def create_ticket_embed(ticket_channel: discord.TextChannel) -> discord.Embed:
    """
    Create an embed for ticket creation
    """
    embed = discord.Embed(
        title="🎫 Ticket créé",
        description=f"Votre ticket a été créé avec succès!\n\n"
                    f"Rendez-vous dans {ticket_channel.mention} pour continuer.",
        color=config.SUCCESS_COLOR
    )
    embed.timestamp = datetime.utcnow()
    return embed


def create_ticket_welcome_embed() -> discord.Embed:
    """
    Create welcome embed for new tickets
    """
    embed = discord.Embed(
        title="👋 Bienvenue sur votre ticket de réservation",
        description="Merci d'avoir choisi Deg Coaching! Choisissez le type de coaching que vous souhaitez réserver.",
        color=config.BOT_COLOR
    )
    embed.add_field(
        name="🆓 Coaching Gratuit",
        value="Session découverte pour nouveaux élèves",
        inline=False
    )
    embed.add_field(
        name="💰 Coaching Payant",
        value="Session complète personnalisée",
        inline=False
    )
    embed.set_footer(text="Sélectionnez une option ci-dessous pour continuer")
    embed.timestamp = datetime.utcnow()
    return embed


def create_calendar_slots_embed(slots: list, date_str: str) -> discord.Embed:
    """
    Create an embed displaying available time slots
    """
    embed = discord.Embed(
        title="📅 Créneaux disponibles",
        description=f"Sélectionnez un créneau horaire pour le **{date_str}**",
        color=config.BOT_COLOR
    )

    if not slots:
        embed.description = "❌ Aucun créneau disponible pour cette date"
        embed.color = config.ERROR_COLOR
    else:
        slots_text = "\n".join([f"• {slot}" for slot in slots[:10]])  # Limit to 10 for display
        embed.add_field(
            name=f"⏰ {len(slots)} créneau(x) disponible(s)",
            value=slots_text,
            inline=False
        )

    embed.timestamp = datetime.utcnow()
    return embed
