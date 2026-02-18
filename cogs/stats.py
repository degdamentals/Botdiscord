"""
Stats Cog - Statistics and client information
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import Optional
import config
from database import get_session, Booking, Client, Note, Feedback
from utils.embeds import create_error_embed, create_info_embed
from utils.permissions import is_coach


class Stats(commands.Cog):
    """
    Cog for statistics and client information
    """

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """
        Called when the cog is loaded
        """
        print("📊 Stats cog loaded")

    @app_commands.command(name="stats", description="[Coach] Voir les statistiques d'un client")
    @app_commands.describe(user="Le client à consulter")
    async def stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """
        View client statistics
        """
        if not is_coach(interaction.user) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed("Vous devez être coach pour utiliser cette commande."),
                ephemeral=True
            )
            return

        await interaction.response.defer()

        with get_session() as session:
            client = session.query(Client).filter_by(discord_id=str(user.id)).first()

            if not client:
                await interaction.followup.send(
                    embed=create_error_embed(f"{user.display_name} n'a jamais réservé de coaching."),
                    ephemeral=True
                )
                return

            # Get all bookings
            bookings = session.query(Booking).filter_by(client_id=client.id).all()

            # Calculate statistics
            total_sessions = len(bookings)
            completed = len([b for b in bookings if b.status == config.STATUS_COMPLETED])
            cancelled = len([b for b in bookings if b.status == config.STATUS_CANCELLED])
            no_shows = len([b for b in bookings if b.status == config.STATUS_NO_SHOW])
            free_sessions = len([b for b in bookings if b.booking_type == config.BOOKING_TYPE_FREE])
            paid_sessions = len([b for b in bookings if b.booking_type == config.BOOKING_TYPE_PAID])

            # Get feedbacks
            feedbacks = session.query(Feedback).join(Booking).filter(Booking.client_id == client.id).all()
            avg_rating = sum([f.rating for f in feedbacks]) / len(feedbacks) if feedbacks else 0

            # Get notes
            notes = session.query(Note).filter_by(client_id=client.id).order_by(Note.created_at.desc()).all()

            # Create embed
            embed = discord.Embed(
                title=f"📊 Statistiques - {client.discord_name}",
                description=f"Client depuis le {client.created_at.strftime('%d/%m/%Y')}",
                color=config.BOT_COLOR
            )

            # Add statistics
            embed.add_field(
                name="📈 Séances",
                value=f"**Total:** {total_sessions}\n"
                      f"✅ Complétées: {completed}\n"
                      f"❌ Annulées: {cancelled}\n"
                      f"👻 No-show: {no_shows}",
                inline=True
            )

            embed.add_field(
                name="💰 Types de coaching",
                value=f"🆓 Gratuit: {free_sessions}\n"
                      f"💰 Payant: {paid_sessions}",
                inline=True
            )

            if feedbacks:
                stars = "⭐" * int(avg_rating)
                embed.add_field(
                    name="⭐ Satisfaction",
                    value=f"{stars} ({avg_rating:.1f}/5)\n"
                          f"Basé sur {len(feedbacks)} avis",
                    inline=True
                )

            # Upcoming sessions
            upcoming = [b for b in bookings if b.status == config.STATUS_CONFIRMED and b.scheduled_at > datetime.now(config.TIMEZONE)]
            if upcoming:
                upcoming_text = ""
                for booking in upcoming[:3]:  # Show max 3
                    type_emoji = "🆓" if booking.booking_type == config.BOOKING_TYPE_FREE else "💰"
                    upcoming_text += f"{type_emoji} {booking.scheduled_at.strftime('%d/%m à %H:%M')} (ID: `{booking.id}`)\n"

                embed.add_field(
                    name=f"📅 Prochaines séances ({len(upcoming)})",
                    value=upcoming_text,
                    inline=False
                )

            # Recent notes
            if notes:
                recent_notes_text = ""
                for note in notes[:2]:  # Show last 2 notes
                    created_date = note.created_at.strftime('%d/%m/%Y')
                    recent_notes_text += f"📝 {created_date}: {note.content[:80]}{'...' if len(note.content) > 80 else ''}\n\n"

                embed.add_field(
                    name=f"📝 Notes récentes ({len(notes)} total)",
                    value=recent_notes_text or "Aucune note",
                    inline=False
                )

            embed.set_thumbnail(url=user.display_avatar.url)
            embed.timestamp = datetime.utcnow()

            await interaction.followup.send(embed=embed)

    @app_commands.command(name="notes", description="[Coach] Gérer les notes d'un client")
    @app_commands.describe(
        user="Le client",
        action="Action à effectuer"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Voir toutes les notes", value="view"),
        app_commands.Choice(name="Ajouter une note", value="add")
    ])
    async def notes(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        action: str
    ):
        """
        Manage client notes
        """
        if not is_coach(interaction.user) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed("Vous devez être coach pour utiliser cette commande."),
                ephemeral=True
            )
            return

        with get_session() as session:
            client = session.query(Client).filter_by(discord_id=str(user.id)).first()

            if not client:
                await interaction.response.send_message(
                    embed=create_error_embed(f"{user.display_name} n'a jamais réservé de coaching."),
                    ephemeral=True
                )
                return

            if action == "view":
                await interaction.response.defer()

                notes = session.query(Note).filter_by(client_id=client.id).order_by(Note.created_at.desc()).all()

                if not notes:
                    await interaction.followup.send(
                        embed=create_info_embed(f"Aucune note pour {client.discord_name}.")
                    )
                    return

                embed = discord.Embed(
                    title=f"📝 Notes - {client.discord_name}",
                    description=f"**{len(notes)}** note(s) enregistrée(s)",
                    color=config.BOT_COLOR
                )

                for note in notes[:10]:  # Show last 10 notes
                    embed.add_field(
                        name=f"📅 {note.created_at.strftime('%d/%m/%Y à %H:%M')}",
                        value=note.content,
                        inline=False
                    )

                embed.timestamp = datetime.utcnow()
                await interaction.followup.send(embed=embed)

            elif action == "add":
                # Show modal for adding note
                modal = AddNoteModal(client=client, user=user)
                await interaction.response.send_modal(modal)


class AddNoteModal(discord.ui.Modal):
    """
    Modal for adding a note about a client
    """

    def __init__(self, client: Client, user: discord.Member):
        super().__init__(title=f"Ajouter une note - {client.discord_name}")
        self.client = client
        self.user = user

        self.note_input = discord.ui.TextInput(
            label="Note",
            placeholder="Entrez vos observations...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.note_input)

    async def on_submit(self, interaction: discord.Interaction):
        """
        Save the note when submitted
        """
        note_content = self.note_input.value.strip()

        with get_session() as session:
            new_note = Note(
                client_id=self.client.id,
                content=note_content,
                created_by_discord_id=str(interaction.user.id)
            )
            session.add(new_note)
            session.commit()

        embed = discord.Embed(
            title="✅ Note ajoutée",
            description=f"Note ajoutée pour **{self.client.discord_name}**",
            color=config.SUCCESS_COLOR
        )
        embed.add_field(name="Contenu", value=note_content[:200], inline=False)
        embed.timestamp = datetime.utcnow()

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    """
    Setup function to add the cog to the bot
    """
    await bot.add_cog(Stats(bot))
