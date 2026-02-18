"""
Admin Cog - Admin and coach commands for managing bookings
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional
import config
from database import get_session, Booking, Client
from utils.embeds import create_error_embed, create_success_embed, create_info_embed
from utils.permissions import coach_only, is_coach
from utils.google_calendar import GoogleCalendarManager


class Admin(commands.Cog):
    """
    Cog for admin and coach commands
    """

    def __init__(self, bot):
        self.bot = bot
        self.calendar_manager = GoogleCalendarManager()

    async def cog_load(self):
        """
        Called when the cog is loaded
        """
        print("⚙️ Admin cog loaded")

    @app_commands.command(name="planning", description="[Coach] Afficher le planning")
    @app_commands.describe(
        period="Période à afficher",
        user="Utilisateur spécifique (optionnel)"
    )
    @app_commands.choices(period=[
        app_commands.Choice(name="Aujourd'hui", value="today"),
        app_commands.Choice(name="Cette semaine", value="week"),
        app_commands.Choice(name="Ce mois", value="month")
    ])
    async def planning(
        self,
        interaction: discord.Interaction,
        period: str,
        user: Optional[discord.Member] = None
    ):
        """
        Display planning for coaches
        """
        if not is_coach(interaction.user) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed("Vous devez être coach pour utiliser cette commande."),
                ephemeral=True
            )
            return

        await interaction.response.defer()

        now = datetime.now(config.TIMEZONE)

        # Calculate date range based on period
        if period == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            title = "📅 Planning d'aujourd'hui"
        elif period == "week":
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59)
            title = "📅 Planning de la semaine"
        else:  # month
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = start_date + timedelta(days=32)
            end_date = next_month.replace(day=1) - timedelta(seconds=1)
            title = f"📅 Planning de {now.strftime('%B %Y')}"

        # Get bookings
        with get_session() as session:
            query = session.query(Booking).filter(
                Booking.scheduled_at >= start_date,
                Booking.scheduled_at <= end_date
            )

            # Filter by user if specified
            if user:
                client = session.query(Client).filter_by(discord_id=str(user.id)).first()
                if client:
                    query = query.filter(Booking.client_id == client.id)
                    title += f" - {user.display_name}"

            bookings = query.order_by(Booking.scheduled_at).all()

            if not bookings:
                embed = create_info_embed(
                    "Aucune réservation pour cette période.",
                    title=title
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Create embed
            embed = discord.Embed(
                title=title,
                description=f"**{len(bookings)}** session(s) prévue(s)",
                color=config.BOT_COLOR
            )

            # Group by date
            bookings_by_date = {}
            for booking in bookings:
                date_key = booking.scheduled_at.strftime("%d/%m/%Y")
                if date_key not in bookings_by_date:
                    bookings_by_date[date_key] = []
                bookings_by_date[date_key].append(booking)

            # Add fields for each date
            for date_key, day_bookings in bookings_by_date.items():
                field_value = ""
                for booking in day_bookings:
                    client = session.query(Client).filter_by(id=booking.client_id).first()
                    if client:
                        type_emoji = "🆓" if booking.booking_type == config.BOOKING_TYPE_FREE else "💰"
                        status_emoji = {
                            config.STATUS_CONFIRMED: "✅",
                            config.STATUS_COMPLETED: "✔️",
                            config.STATUS_CANCELLED: "❌",
                            config.STATUS_NO_SHOW: "👻"
                        }.get(booking.status, "❓")

                        field_value += f"{status_emoji} {type_emoji} **{booking.scheduled_at.strftime('%H:%M')}** - {client.discord_name} ({booking.duration_minutes}min)\n"

                embed.add_field(
                    name=f"📆 {date_key}",
                    value=field_value or "Aucune session",
                    inline=False
                )

            embed.timestamp = datetime.utcnow()
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="booking", description="[Coach] Gérer une réservation")
    @app_commands.describe(
        action="Action à effectuer",
        booking_id="ID de la réservation"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Annuler", value="cancel"),
        app_commands.Choice(name="Marquer comme complétée", value="complete"),
        app_commands.Choice(name="Marquer comme no-show", value="noshow"),
        app_commands.Choice(name="Voir détails", value="view")
    ])
    async def booking(
        self,
        interaction: discord.Interaction,
        action: str,
        booking_id: int
    ):
        """
        Manage a booking
        """
        if not is_coach(interaction.user) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed("Vous devez être coach pour utiliser cette commande."),
                ephemeral=True
            )
            return

        await interaction.response.defer()

        with get_session() as session:
            booking = session.query(Booking).filter_by(id=booking_id).first()

            if not booking:
                await interaction.followup.send(
                    embed=create_error_embed(f"Aucune réservation trouvée avec l'ID `{booking_id}`."),
                    ephemeral=True
                )
                return

            client = session.query(Client).filter_by(id=booking.client_id).first()

            if action == "view":
                # Show booking details
                type_label = "Coaching Gratuit" if booking.booking_type == config.BOOKING_TYPE_FREE else "Coaching Payant"
                embed = discord.Embed(
                    title=f"📋 Détails de la réservation #{booking_id}",
                    color=config.BOT_COLOR
                )
                embed.add_field(name="👤 Client", value=client.discord_name if client else "Inconnu", inline=True)
                embed.add_field(name="📅 Date", value=booking.scheduled_at.strftime("%d/%m/%Y à %H:%M"), inline=True)
                embed.add_field(name="⏱️ Durée", value=f"{booking.duration_minutes} min", inline=True)
                embed.add_field(name="📝 Type", value=type_label, inline=True)
                embed.add_field(name="📊 Statut", value=booking.status, inline=True)
                if booking.notes:
                    embed.add_field(name="📝 Notes", value=booking.notes, inline=False)
                embed.timestamp = datetime.utcnow()
                await interaction.followup.send(embed=embed)

            elif action == "cancel":
                booking.status = config.STATUS_CANCELLED
                session.commit()

                # Notify client
                if client:
                    try:
                        user = await self.bot.fetch_user(int(client.discord_id))
                        embed = discord.Embed(
                            title="❌ Réservation annulée",
                            description=f"Votre session du {booking.scheduled_at.strftime('%d/%m/%Y à %H:%M')} a été annulée par votre coach.",
                            color=config.ERROR_COLOR
                        )
                        embed.add_field(name="🆔 ID", value=f"`{booking_id}`", inline=False)
                        embed.set_footer(text="Vous pouvez créer un nouveau ticket pour replanifier.")
                        await user.send(embed=embed)
                    except:
                        pass

                await interaction.followup.send(
                    embed=create_success_embed(f"Réservation #{booking_id} annulée. Le client a été notifié.")
                )

            elif action == "complete":
                booking.status = config.STATUS_COMPLETED
                session.commit()
                await interaction.followup.send(
                    embed=create_success_embed(f"Réservation #{booking_id} marquée comme complétée.")
                )

            elif action == "noshow":
                booking.status = config.STATUS_NO_SHOW
                session.commit()
                await interaction.followup.send(
                    embed=create_success_embed(f"Réservation #{booking_id} marquée comme no-show.")
                )

    @app_commands.command(name="my-sessions", description="Voir vos prochaines sessions de coaching")
    async def my_sessions(self, interaction: discord.Interaction):
        """
        Allow students to see their upcoming sessions
        """
        await interaction.response.defer(ephemeral=True)

        with get_session() as session:
            client = session.query(Client).filter_by(discord_id=str(interaction.user.id)).first()

            if not client:
                await interaction.followup.send(
                    embed=create_info_embed("Vous n'avez aucune réservation pour le moment.\n\nUtilisez le bouton de réservation pour créer une session."),
                    ephemeral=True
                )
                return

            now = datetime.now(config.TIMEZONE)
            all_bookings = session.query(Booking).filter_by(client_id=client.id).all()

            # Upcoming confirmed sessions
            upcoming = []
            for b in all_bookings:
                scheduled = b.scheduled_at
                if scheduled.tzinfo is None:
                    scheduled = config.TIMEZONE.localize(scheduled)
                if b.status == config.STATUS_CONFIRMED and scheduled > now:
                    upcoming.append((b, scheduled))
            upcoming.sort(key=lambda x: x[1])

            # Pack sessions to schedule
            pending = [b for b in all_bookings if b.status == "pending_schedule"]

            # Recent completed
            completed = [b for b in all_bookings if b.status == config.STATUS_COMPLETED]

            embed = discord.Embed(
                title="📅 Mes sessions de coaching",
                description=f"Bonjour **{interaction.user.display_name}**!",
                color=config.BOT_COLOR
            )

            if upcoming:
                upcoming_text = ""
                for booking, scheduled in upcoming[:5]:
                    type_emoji = "🆓" if booking.booking_type == config.BOOKING_TYPE_FREE else "💰"
                    upcoming_text += f"{type_emoji} **{scheduled.strftime('%d/%m/%Y à %H:%M')}** ({booking.duration_minutes}min) — ID: `{booking.id}`\n"
                embed.add_field(name=f"⏳ Prochaines sessions ({len(upcoming)})", value=upcoming_text, inline=False)
            else:
                embed.add_field(name="⏳ Prochaines sessions", value="Aucune session prévue.", inline=False)

            if pending:
                embed.add_field(
                    name=f"📋 Sessions à planifier ({len(pending)})",
                    value=f"Vous avez **{len(pending)}** séance(s) de pack en attente de planification.\nContactez votre coach pour les programmer.",
                    inline=False
                )

            embed.add_field(
                name="📊 Historique",
                value=f"✅ Complétées: **{len(completed)}** | ❌ Annulées: **{len([b for b in all_bookings if b.status == config.STATUS_CANCELLED])}**",
                inline=False
            )

            embed.set_footer(text="Utilisez le bouton de réservation pour créer une nouvelle session")
            embed.timestamp = datetime.utcnow()
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="add-sessions", description="[Coach] Ajouter des sessions manuellement pour un client")
    @app_commands.describe(
        user="Le client pour qui créer les sessions",
        quantity="Nombre de sessions à créer",
        booking_type="Type de coaching"
    )
    @app_commands.choices(
        quantity=[
            app_commands.Choice(name="1 séance", value=1),
            app_commands.Choice(name="2 séances", value=2),
            app_commands.Choice(name="3 séances", value=3),
            app_commands.Choice(name="4 séances", value=4),
            app_commands.Choice(name="5 séances", value=5),
            app_commands.Choice(name="8 séances (Pack 1 mois)", value=8),
        ],
        booking_type=[
            app_commands.Choice(name="🆓 Gratuit", value="gratuit"),
            app_commands.Choice(name="💰 Payant", value="payant"),
        ]
    )
    async def add_sessions(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        quantity: int,
        booking_type: str
    ):
        """
        Manually add multiple sessions for a client
        """
        if not is_coach(interaction.user) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed("Vous devez être coach pour utiliser cette commande."),
                ephemeral=True
            )
            return

        # Show modal to get session details
        modal = AddSessionsModal(
            cog=self,
            client_user=user,
            quantity=quantity,
            booking_type=booking_type
        )
        await interaction.response.send_modal(modal)


class AddSessionsModal(discord.ui.Modal):
    """
    Modal for adding session details manually
    """

    def __init__(self, cog, client_user: discord.Member, quantity: int, booking_type: str):
        super().__init__(title=f"Ajouter {quantity} session{'s' if quantity > 1 else ''}")
        self.cog = cog
        self.client_user = client_user
        self.quantity = quantity
        self.booking_type = booking_type

        # Add text input for session dates/times
        self.sessions_input = discord.ui.TextInput(
            label=f"Sessions (format: JJ/MM/AAAA HH:MM)",
            placeholder="Exemple:\n15/02/2026 14:00\n16/02/2026 16:30\n17/02/2026 10:00",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.sessions_input)

        # Add duration input
        duration_default = str(config.FREE_COACHING_DURATION if booking_type == config.BOOKING_TYPE_FREE else config.PAID_COACHING_DURATION)
        self.duration_input = discord.ui.TextInput(
            label="Durée (minutes)",
            placeholder=duration_default,
            default=duration_default,
            style=discord.TextStyle.short,
            required=True,
            max_length=3
        )
        self.add_item(self.duration_input)

        # Add notes input
        self.notes_input = discord.ui.TextInput(
            label="Notes (optionnel)",
            placeholder="Notes sur ces sessions...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.notes_input)

    async def on_submit(self, interaction: discord.Interaction):
        """
        Process the session creation
        """
        await interaction.response.defer(ephemeral=True)

        try:
            # Parse duration
            duration = int(self.duration_input.value.strip())
        except ValueError:
            await interaction.followup.send(
                embed=create_error_embed("Durée invalide. Veuillez entrer un nombre."),
                ephemeral=True
            )
            return

        # Parse session dates/times
        sessions_text = self.sessions_input.value.strip()
        session_lines = [line.strip() for line in sessions_text.split('\n') if line.strip()]

        if len(session_lines) != self.quantity:
            await interaction.followup.send(
                embed=create_error_embed(
                    f"Vous devez entrer exactement {self.quantity} session{'s' if self.quantity > 1 else ''}.\n"
                    f"Vous avez entré {len(session_lines)} ligne{'s' if len(session_lines) > 1 else ''}."
                ),
                ephemeral=True
            )
            return

        # Parse dates
        session_dates = []
        for line in session_lines:
            try:
                # Parse date in format DD/MM/YYYY HH:MM
                dt = datetime.strptime(line, "%d/%m/%Y %H:%M")
                # Add timezone
                dt = config.TIMEZONE.localize(dt)
                session_dates.append(dt)
            except ValueError:
                await interaction.followup.send(
                    embed=create_error_embed(
                        f"Format de date invalide: `{line}`\n\n"
                        f"Format attendu: JJ/MM/AAAA HH:MM\n"
                        f"Exemple: 15/02/2026 14:00"
                    ),
                    ephemeral=True
                )
                return

        # Check for past dates
        now = datetime.now(config.TIMEZONE)
        for dt in session_dates:
            if dt < now:
                await interaction.followup.send(
                    embed=create_error_embed(
                        f"Date dans le passé: {dt.strftime('%d/%m/%Y %H:%M')}\n\n"
                        f"Toutes les dates doivent être dans le futur."
                    ),
                    ephemeral=True
                )
                return

        # Get or create client
        with get_session() as session:
            client = session.query(Client).filter_by(discord_id=str(self.client_user.id)).first()

            if not client:
                client = Client(
                    discord_id=str(self.client_user.id),
                    discord_name=self.client_user.display_name
                )
                session.add(client)
                session.flush()

            # Create bookings
            created_bookings = []
            notes = self.notes_input.value.strip() or None

            for dt in session_dates:
                # Create Google Calendar event
                event_id = self.cog.calendar_manager.create_event(
                    title=f"Coaching - {self.client_user.display_name}",
                    start_time=dt,
                    duration_minutes=duration,
                    description=f"Type: {self.booking_type}\nClient: {self.client_user.display_name}\nNotes: {notes or 'Aucune'}"
                )

                if not event_id:
                    await interaction.followup.send(
                        embed=create_error_embed(
                            f"Erreur lors de la création de l'événement Google Calendar pour {dt.strftime('%d/%m/%Y %H:%M')}"
                        ),
                        ephemeral=True
                    )
                    return

                # Create booking in database
                booking = Booking(
                    client_id=client.id,
                    google_event_id=event_id,
                    booking_type=self.booking_type,
                    scheduled_at=dt,
                    duration_minutes=duration,
                    status=config.STATUS_CONFIRMED,
                    notes=notes
                )
                session.add(booking)
                created_bookings.append(booking)

            session.commit()

            # Create success embed
            type_emoji = "🆓" if self.booking_type == config.BOOKING_TYPE_FREE else "💰"
            embed = discord.Embed(
                title=f"✅ {len(created_bookings)} session{'s' if len(created_bookings) > 1 else ''} créée{'s' if len(created_bookings) > 1 else ''}",
                description=f"Sessions ajoutées pour {self.client_user.mention}",
                color=config.SUCCESS_COLOR
            )

            sessions_list = ""
            for booking in created_bookings:
                sessions_list += f"{type_emoji} {booking.scheduled_at.strftime('%d/%m/%Y à %H:%M')} ({duration}min) - ID: `{booking.id}`\n"

            embed.add_field(name="📅 Sessions", value=sessions_list, inline=False)
            if notes:
                embed.add_field(name="📝 Notes", value=notes, inline=False)

            embed.timestamp = datetime.utcnow()

            await interaction.followup.send(embed=embed, ephemeral=True)

            # Notify client
            try:
                embed_client = discord.Embed(
                    title=f"🎮 Nouvelles sessions de coaching",
                    description=f"Votre coach a programmé **{len(created_bookings)} session{'s' if len(created_bookings) > 1 else ''}** pour vous!",
                    color=config.BOT_COLOR
                )
                embed_client.add_field(name="📅 Sessions", value=sessions_list, inline=False)
                if notes:
                    embed_client.add_field(name="📝 Notes", value=notes, inline=False)
                embed_client.set_footer(text="Vous recevrez des rappels avant chaque session")
                await self.client_user.send(embed=embed_client)
            except discord.Forbidden:
                pass  # User has DMs disabled


    @app_commands.command(name="clear-bookings", description="[Coach] Supprimer des réservations et leurs événements Google Calendar")
    @app_commands.describe(
        user="Utilisateur dont supprimer les réservations (optionnel — tous si non précisé)",
        status="Statut des réservations à supprimer"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="Toutes", value="all"),
        app_commands.Choice(name="Confirmées seulement", value="confirmed"),
        app_commands.Choice(name="Annulées seulement", value="cancelled"),
        app_commands.Choice(name="À planifier (packs) seulement", value="pending_schedule"),
    ])
    async def clear_bookings(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        status: str = "all"
    ):
        """
        Delete bookings from DB and their Google Calendar events
        """
        if not is_coach(interaction.user) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed("Vous devez être coach pour utiliser cette commande."),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        with get_session() as session:
            query = session.query(Booking)

            # Filter by user if provided
            if user:
                client = session.query(Client).filter_by(discord_id=str(user.id)).first()
                if not client:
                    await interaction.followup.send(
                        embed=create_error_embed(f"{user.mention} n'a aucune réservation en base."),
                        ephemeral=True
                    )
                    return
                query = query.filter(Booking.client_id == client.id)

            # Filter by status
            if status != "all":
                query = query.filter(Booking.status == status)

            bookings = query.all()

            if not bookings:
                await interaction.followup.send(
                    embed=create_error_embed("Aucune réservation trouvée avec ces critères."),
                    ephemeral=True
                )
                return

            # Delete Google Calendar events
            deleted_cal = 0
            failed_cal = 0
            for booking in bookings:
                if booking.google_event_id:
                    success = self.calendar_manager.delete_event(booking.google_event_id)
                    if success:
                        deleted_cal += 1
                    else:
                        failed_cal += 1

            # Delete from DB
            count = len(bookings)
            for booking in bookings:
                session.delete(booking)
            session.commit()

        # Build result embed
        user_label = user.mention if user else "tous les utilisateurs"
        status_label = {
            "all": "toutes",
            "confirmed": "confirmées",
            "cancelled": "annulées",
            "pending_schedule": "à planifier"
        }.get(status, status)

        embed = discord.Embed(
            title="🗑️ Réservations supprimées",
            color=config.SUCCESS_COLOR
        )
        embed.add_field(name="👤 Utilisateur", value=user_label, inline=True)
        embed.add_field(name="📋 Statut", value=status_label, inline=True)
        embed.add_field(name="🗑️ Supprimées (DB)", value=f"**{count}** réservation(s)", inline=False)
        embed.add_field(
            name="📅 Google Calendar",
            value=f"✅ {deleted_cal} événement(s) supprimé(s)" + (f"\n⚠️ {failed_cal} échec(s)" if failed_cal else ""),
            inline=False
        )
        embed.timestamp = datetime.utcnow()
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    """
    Setup function to add the cog to the bot
    """
    await bot.add_cog(Admin(bot))
