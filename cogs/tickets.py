"""
Tickets Cog - Manages ticket system and booking flow
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional
import asyncio
import config
from database import get_session, Client, Booking
from utils.embeds import (
    create_error_embed, create_success_embed, create_info_embed,
    create_booking_embed, create_ticket_embed, create_ticket_welcome_embed
)
from utils.permissions import is_coach, coach_only
from utils.google_calendar import GoogleCalendarManager
from views.booking_views import BookingTypeView, DateSelectorView, CalendarSlotsView, SessionQuantityView, CoachTicketControlsView, StudentBookingControlsView


class Tickets(commands.Cog):
    """
    Cog for handling ticket creation and booking process
    """

    def __init__(self, bot):
        self.bot = bot
        self.calendar_manager = GoogleCalendarManager()
        self.active_tickets = {}  # Store ticket states
        self.ticket_creation_locks = {}  # Lock per user ID to prevent race conditions
        self._global_ticket_lock = asyncio.Lock()  # Global lock to serialize all ticket checks
        self._creating_tickets = set()  # Track users currently creating tickets

    async def cog_load(self):
        """
        Called when the cog is loaded
        """
        print("📋 Tickets cog loaded")

    @app_commands.command(name="setup-booking", description="[Coach] Configure le message de réservation")
    @app_commands.default_permissions(administrator=True)
    async def setup_booking(self, interaction: discord.Interaction):
        """
        Setup the booking button message (admin/coach only)
        """
        if not is_coach(interaction.user) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed("Vous n'avez pas la permission d'utiliser cette commande."),
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎮 Réservation de Coaching",
            description="Bienvenue sur **Deg Coaching**!\n\n"
                        "Prêt à améliorer votre gameplay sur League of Legends?\n"
                        "Cliquez sur le bouton ci-dessous pour réserver votre session de coaching.",
            color=config.BOT_COLOR
        )
        embed.add_field(
            name="🆓 Coaching Gratuit",
            value="Session découverte pour les nouveaux élèves",
            inline=False
        )
        embed.add_field(
            name="💰 Coaching Payant",
            value="Session complète et personnalisée",
            inline=False
        )
        embed.set_footer(text="Un ticket privé sera créé pour votre réservation")

        view = BookingButtonView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            embed=create_success_embed("Message de réservation créé!"),
            ephemeral=True
        )

    @app_commands.command(name="ticket", description="Gestion des tickets")
    @app_commands.describe(
        action="Action à effectuer",
        user="Utilisateur concerné (pour close: ferme son ticket / pour add: l'ajoute au ticket actuel)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="close", value="close"),
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="create", value="create")
    ])
    async def ticket(
        self,
        interaction: discord.Interaction,
        action: str,
        user: Optional[discord.Member] = None
    ):
        """
        Manage tickets (close, add user, create for user)
        """
        if action == "close":
            # If user is specified, find and close their ticket
            if user:
                # Coach can close any user's ticket
                if not is_coach(interaction.user):
                    await interaction.response.send_message(
                        embed=create_error_embed("Seuls les coachs peuvent fermer les tickets d'autres utilisateurs."),
                        ephemeral=True
                    )
                    return
                await self._close_user_ticket(interaction, user)
            else:
                # Close current ticket
                if not interaction.channel.category_id == config.TICKET_CATEGORY_ID:
                    await interaction.response.send_message(
                        embed=create_error_embed("Cette commande doit être utilisée dans un ticket ou avec un @utilisateur."),
                        ephemeral=True
                    )
                    return
                await self._close_ticket(interaction, interaction.channel)

        elif action == "add":
            # Must be in a ticket channel
            if not interaction.channel.category_id == config.TICKET_CATEGORY_ID:
                await interaction.response.send_message(
                    embed=create_error_embed("Cette commande ne peut être utilisée que dans un ticket."),
                    ephemeral=True
                )
                return

            if not user:
                await interaction.response.send_message(
                    embed=create_error_embed("Vous devez mentionner un utilisateur à ajouter."),
                    ephemeral=True
                )
                return
            await self._add_user_to_ticket(interaction, user)

        elif action == "create":
            # Coach can create a ticket for a user
            if not is_coach(interaction.user):
                await interaction.response.send_message(
                    embed=create_error_embed("Seuls les coachs peuvent créer des tickets pour d'autres utilisateurs."),
                    ephemeral=True
                )
                return

            if not user:
                await interaction.response.send_message(
                    embed=create_error_embed("Vous devez mentionner un utilisateur."),
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)
            ticket_channel = await self.create_ticket(user)

            if ticket_channel:
                embed = create_success_embed(f"Ticket créé pour {user.mention}: {ticket_channel.mention}")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    embed=create_error_embed("Impossible de créer le ticket."),
                    ephemeral=True
                )

    async def _close_ticket(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """
        Close a ticket channel
        """
        target_channel = channel or interaction.channel
        embed = create_info_embed(
            "🔒 Fermeture du ticket dans 5 secondes...\n"
            "Le salon sera supprimé."
        )
        await interaction.response.send_message(embed=embed)

        # Wait 5 seconds then delete
        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=5))

        try:
            await target_channel.delete(reason=f"Ticket fermé par {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Je n'ai pas la permission de supprimer ce salon."),
                ephemeral=True
            )

    async def _close_user_ticket(self, interaction: discord.Interaction, user: discord.Member):
        """
        Find and close a user's ticket channel
        """
        guild = interaction.guild
        category = guild.get_channel(config.TICKET_CATEGORY_ID)

        if not category:
            await interaction.response.send_message(
                embed=create_error_embed("Catégorie de tickets introuvable."),
                ephemeral=True
            )
            return

        # Find user's ticket channel
        user_ticket = None
        for channel in category.channels:
            if channel.name.startswith(f"ticket-{user.name.lower()}"):
                user_ticket = channel
                break

        if not user_ticket:
            await interaction.response.send_message(
                embed=create_error_embed(f"Aucun ticket trouvé pour {user.mention}."),
                ephemeral=True
            )
            return

        # Close the ticket
        await interaction.response.send_message(
            embed=create_success_embed(f"Fermeture du ticket de {user.mention} ({user_ticket.mention})..."),
            ephemeral=True
        )

        try:
            await user_ticket.delete(reason=f"Ticket fermé par {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Permissions insuffisantes pour supprimer ce ticket."),
                ephemeral=True
            )

    async def _add_user_to_ticket(self, interaction: discord.Interaction, user: discord.Member):
        """
        Add a user to a ticket channel
        """
        try:
            await interaction.channel.set_permissions(
                user,
                read_messages=True,
                send_messages=True
            )
            embed = create_success_embed(f"{user.mention} a été ajouté au ticket.")
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=create_error_embed("Je n'ai pas la permission de modifier les permissions de ce salon."),
                ephemeral=True
            )

    @app_commands.command(name="clear-tickets", description="[Coach] Supprimer tous les tickets d'un utilisateur")
    @app_commands.describe(
        user="L'utilisateur dont vous voulez supprimer tous les tickets"
    )
    async def clear_tickets(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """
        Delete all tickets for a specific user (coach only)
        """
        # Check if user is coach
        if not is_coach(interaction.user) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed("Seuls les coachs peuvent utiliser cette commande."),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(config.TICKET_CATEGORY_ID)

        if not category:
            await interaction.followup.send(
                embed=create_error_embed("Catégorie de tickets introuvable."),
                ephemeral=True
            )
            return

        # Find all tickets for this user
        user_tickets = []
        for channel in category.channels:
            if not isinstance(channel, discord.TextChannel):
                continue

            if channel.name.startswith("ticket-"):
                # Check if user has explicit permissions in this channel
                if user in channel.overwrites:
                    user_overwrite = channel.overwrites[user]
                    if user_overwrite.read_messages is True:
                        user_tickets.append(channel)

        if not user_tickets:
            await interaction.followup.send(
                embed=create_info_embed(f"Aucun ticket trouvé pour {user.mention}."),
                ephemeral=True
            )
            return

        # Delete all tickets
        deleted_count = 0
        failed_tickets = []

        for ticket in user_tickets:
            try:
                await ticket.delete(reason=f"Tous les tickets supprimés par {interaction.user} via /clear-tickets")
                deleted_count += 1
            except discord.Forbidden:
                failed_tickets.append(ticket.name)
            except Exception as e:
                failed_tickets.append(f"{ticket.name} (erreur: {str(e)})")

        # Send result
        if deleted_count > 0:
            result_text = f"**{deleted_count}** ticket(s) supprimé(s) pour {user.mention}."
            if failed_tickets:
                result_text += f"\n\n⚠️ Échec pour {len(failed_tickets)} ticket(s):\n" + "\n".join(f"• {t}" for t in failed_tickets)

            embed = create_success_embed(result_text)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = create_error_embed(
                f"Impossible de supprimer les tickets.\n\n"
                f"Échecs:\n" + "\n".join(f"• {t}" for t in failed_tickets)
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def create_ticket(self, user: discord.Member):
        """
        Create a new ticket channel for a user

        Args:
            user: The member who requested the ticket

        Returns:
            The created ticket channel or None if failed
        """
        guild = user.guild
        category = guild.get_channel(config.TICKET_CATEGORY_ID)

        if not category:
            print(f"❌ Category {config.TICKET_CATEGORY_ID} not found")
            return None

        # CRITICAL: Double-check if non-coach user already has a ticket
        # This prevents race conditions from spam clicking
        if not is_coach(user):
            for channel in category.channels:
                if not isinstance(channel, discord.TextChannel):
                    continue
                if channel.name.startswith("ticket-"):
                    if user in channel.overwrites:
                        user_overwrite = channel.overwrites[user]
                        if user_overwrite.read_messages is True:
                            print(f"⚠️ User {user.name} already has ticket {channel.name}, aborting creation")
                            return None  # User already has a ticket, abort

        # Find ticket number
        ticket_number = len([c for c in category.channels if c.name.startswith("ticket-")]) + 1
        channel_name = config.TICKET_NAME_FORMAT.format(
            username=user.name.lower().replace(" ", "-"),
            number=ticket_number
        )

        # Get coach role
        coach_role = guild.get_role(config.COACH_ROLE_ID)

        # Create overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                embed_links=True,
                attach_files=True
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                embed_links=True,
                manage_messages=True
            )
        }

        if coach_role:
            overwrites[coach_role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                embed_links=True,
                attach_files=True
            )

        try:
            # Create channel
            ticket_channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason=f"Ticket créé par {user}"
            )

            # Send welcome message
            embed = create_ticket_welcome_embed()
            view = BookingTypeView(cog=self, user=user)

            await ticket_channel.send(
                content=f"{user.mention} - Bienvenue!",
                embed=embed,
                view=view
            )

            # Send coach-only controls in a separate message
            coach_embed = discord.Embed(
                title="🛠️ Contrôles Coach",
                description="Utilisez les boutons ci-dessous pour gérer ce ticket.",
                color=config.BOT_COLOR
            )
            coach_view = CoachTicketControlsView(cog=self, ticket_channel=ticket_channel)

            # Send as ephemeral wouldn't work here, so we send it normally
            # Only coaches will see the buttons work (permissions check)
            await ticket_channel.send(embed=coach_embed, view=coach_view)

            return ticket_channel

        except discord.Forbidden:
            print(f"❌ Missing permissions to create ticket channel")
            return None
        except Exception as e:
            print(f"❌ Error creating ticket: {e}")
            return None

    async def booking_type_selected(
        self,
        interaction: discord.Interaction,
        booking_type: str,
        user: discord.Member
    ):
        """
        Handle booking type selection

        Args:
            interaction: The interaction
            booking_type: Selected booking type (gratuit/payant)
            user: The user who is booking
        """
        # Store booking type for this ticket
        self.active_tickets[interaction.channel.id] = {
            'user': user,
            'booking_type': booking_type
        }

        # If paid coaching, ask for quantity first
        if booking_type == config.BOOKING_TYPE_PAID:
            embed = create_info_embed(
                f"Vous avez sélectionné: **Coaching Payant**\n\n"
                f"Combien de séances souhaitez-vous réserver?"
            )
            view = SessionQuantityView(cog=self, user=user)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            # For free coaching, go directly to date selection with quantity = 1
            self.active_tickets[interaction.channel.id]['quantity'] = 1
            embed = create_info_embed(
                f"Vous avez sélectionné: **Coaching Gratuit**\n\n"
                f"Sélectionnez une date pour voir les créneaux disponibles."
            )
            view = DateSelectorView(cog=self, ticket_channel_id=interaction.channel.id)
            await interaction.response.edit_message(embed=embed, view=view)

    async def quantity_selected(
        self,
        interaction: discord.Interaction,
        quantity: int,
        user: discord.Member
    ):
        """
        Handle session quantity selection (paid coaching only)

        Args:
            interaction: The interaction
            quantity: Number of sessions selected
            user: The user who is booking
        """
        # Store quantity for this ticket
        ticket_data = self.active_tickets.get(interaction.channel.id)
        if ticket_data:
            ticket_data['quantity'] = quantity

        # Show date selector
        embed = create_info_embed(
            f"Vous avez sélectionné: **{quantity} séance{'s' if quantity > 1 else ''}**\n\n"
            f"Sélectionnez la date de votre {'première' if quantity > 1 else ''} séance."
        )

        view = DateSelectorView(cog=self, ticket_channel_id=interaction.channel.id)
        await interaction.response.edit_message(embed=embed, view=view)

    async def date_selected(
        self,
        interaction: discord.Interaction,
        selected_date: datetime,
        ticket_channel_id: int
    ):
        """
        Handle date selection and show available slots

        Args:
            interaction: The interaction
            selected_date: Selected date
            ticket_channel_id: ID of the ticket channel
        """
        # Defer to show loading state
        await interaction.response.defer()

        ticket_data = self.active_tickets.get(ticket_channel_id)
        if not ticket_data:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embed=create_error_embed("Session expirée. Veuillez créer un nouveau ticket."),
                view=None
            )
            return

        # Get duration based on booking type
        duration = config.FREE_COACHING_DURATION if ticket_data['booking_type'] == config.BOOKING_TYPE_FREE else config.PAID_COACHING_DURATION

        # Get available slots from Google Calendar
        start_of_day = selected_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = selected_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        slots = self.calendar_manager.get_available_slots(
            start_date=start_of_day,
            end_date=end_of_day,
            duration_minutes=duration
        )

        if not slots:
            embed = create_error_embed(
                f"❌ Aucun créneau disponible pour le {selected_date.strftime('%d/%m/%Y')}\n\n"
                f"Veuillez sélectionner une autre date."
            )
            view = DateSelectorView(cog=self, ticket_channel_id=ticket_channel_id)
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embed=embed,
                view=view
            )
            return

        # Show available slots
        embed = create_info_embed(
            f"📅 Créneaux disponibles pour le **{selected_date.strftime('%d/%m/%Y')}**\n\n"
            f"Sélectionnez un créneau horaire:"
        )

        view = CalendarSlotsView(
            cog=self,
            slots=slots,
            ticket_channel_id=ticket_channel_id
        )
        await interaction.followup.edit_message(
            message_id=interaction.message.id,
            embed=embed,
            view=view
        )

    async def slot_selected(
        self,
        interaction: discord.Interaction,
        selected_slot: datetime,
        ticket_channel_id: int
    ):
        """
        Handle time slot selection and create booking

        Args:
            interaction: The interaction
            selected_slot: Selected time slot
            ticket_channel_id: ID of the ticket channel
        """
        await interaction.response.defer()

        ticket_data = self.active_tickets.get(ticket_channel_id)
        if not ticket_data:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embed=create_error_embed("Session expirée. Veuillez créer un nouveau ticket."),
                view=None
            )
            return

        user = ticket_data['user']
        booking_type = ticket_data['booking_type']
        quantity = ticket_data.get('quantity', 1)
        reschedule_booking_id = ticket_data.get('reschedule_booking_id')
        old_date = ticket_data.get('old_date')
        duration = config.FREE_COACHING_DURATION if booking_type == config.BOOKING_TYPE_FREE else config.PAID_COACHING_DURATION

        # Check if this is a reschedule
        if reschedule_booking_id:
            # Handle rescheduling
            with get_session() as session:
                booking = session.query(Booking).filter_by(id=reschedule_booking_id).first()

                if not booking:
                    await interaction.followup.send(
                        embed=create_error_embed("Réservation introuvable."),
                        ephemeral=True
                    )
                    return

                # Delete old Google Calendar event
                if booking.google_event_id:
                    try:
                        self.calendar_manager.delete_event(booking.google_event_id)
                    except Exception as e:
                        print(f"❌ Error deleting old calendar event: {e}")

                # Create new Google Calendar event
                new_event_id = self.calendar_manager.create_booking_event(
                    start_time=selected_slot,
                    duration_minutes=duration,
                    booking_type=booking_type,
                    client_name=user.display_name,
                    discord_id=str(user.id)
                )

                if not new_event_id:
                    await interaction.followup.send(
                        embed=create_error_embed("❌ Erreur lors de la création du nouvel événement."),
                        ephemeral=True
                    )
                    return

                # Update booking
                booking.scheduled_at = selected_slot
                booking.google_event_id = new_event_id
                session.commit()

                # Send confirmation
                embed = discord.Embed(
                    title="✅ Réservation reportée",
                    description=f"Votre session a été reportée avec succès!",
                    color=config.SUCCESS_COLOR
                )
                embed.add_field(
                    name="📅 Ancienne date",
                    value=old_date.strftime('%d/%m/%Y à %H:%M'),
                    inline=True
                )
                embed.add_field(
                    name="📅 Nouvelle date",
                    value=selected_slot.strftime('%d/%m/%Y à %H:%M'),
                    inline=True
                )
                embed.add_field(name="🆔 ID", value=f"`{reschedule_booking_id}`", inline=True)
                embed.set_footer(text="Vous recevrez des rappels 24h et 1h avant la session")
                embed.timestamp = datetime.utcnow()

                await interaction.followup.send(embed=embed, ephemeral=True)

                # Notify coaches
                coach_role = user.guild.get_role(config.COACH_ROLE_ID)
                if coach_role:
                    log_channel = user.guild.get_channel(config.LOG_CHANNEL_ID)
                    if log_channel:
                        try:
                            notify_embed = discord.Embed(
                                title="📅 Réservation reportée",
                                description=f"{user.mention} a reporté une réservation.",
                                color=config.WARNING_COLOR
                            )
                            notify_embed.add_field(name="👤 Client", value=user.display_name, inline=True)
                            notify_embed.add_field(name="📅 Ancienne date", value=old_date.strftime('%d/%m/%Y à %H:%M'), inline=True)
                            notify_embed.add_field(name="📅 Nouvelle date", value=selected_slot.strftime('%d/%m/%Y à %H:%M'), inline=True)
                            notify_embed.add_field(name="🆔 ID", value=f"`{reschedule_booking_id}`", inline=True)
                            notify_embed.timestamp = datetime.utcnow()
                            await log_channel.send(content=coach_role.mention, embed=notify_embed)
                        except:
                            pass

                # Clean up ticket data
                if ticket_channel_id in self.active_tickets:
                    del self.active_tickets[ticket_channel_id]

                return

        # Create bookings based on quantity
        booking_ids = []
        created_slots = []

        with get_session() as session:
            # Get or create client
            client = session.query(Client).filter_by(discord_id=str(user.id)).first()
            if not client:
                client = Client(
                    discord_id=str(user.id),
                    discord_name=user.display_name
                )
                session.add(client)
                session.flush()

            # Create the first booking (with selected slot)
            event_id = self.calendar_manager.create_booking_event(
                start_time=selected_slot,
                duration_minutes=duration,
                booking_type=booking_type,
                client_name=user.display_name,
                discord_id=str(user.id)
            )

            if not event_id:
                await interaction.followup.edit_message(
                    message_id=interaction.message.id,
                    embed=create_error_embed("❌ Erreur lors de la création de l'événement. Veuillez réessayer."),
                    view=None
                )
                return

            booking = Booking(
                client_id=client.id,
                google_event_id=event_id,
                booking_type=booking_type,
                scheduled_at=selected_slot,
                duration_minutes=duration,
                status=config.STATUS_CONFIRMED,
                ticket_channel_id=str(ticket_channel_id),
                notes=f"Pack de {quantity} séances - Séance 1/{quantity}" if quantity > 1 else None
            )
            session.add(booking)
            session.flush()
            client.total_sessions += 1
            booking_ids.append(booking.id)
            created_slots.append(selected_slot)

            # For packs: create placeholder bookings for remaining sessions
            for i in range(1, quantity):
                placeholder = Booking(
                    client_id=client.id,
                    google_event_id=None,
                    booking_type=booking_type,
                    scheduled_at=selected_slot,  # Placeholder date, to be updated by coach
                    duration_minutes=duration,
                    status="pending_schedule",
                    ticket_channel_id=str(ticket_channel_id),
                    notes=f"Pack de {quantity} séances - Séance {i+1}/{quantity} (à planifier)"
                )
                session.add(placeholder)
                session.flush()
                booking_ids.append(placeholder.id)
                created_slots.append(selected_slot)

        # Send confirmation
        if quantity == 1:
            embed = create_booking_embed(
                booking_type=booking_type,
                scheduled_at=created_slots[0],
                duration=duration,
                client_name=user.display_name,
                booking_id=booking_ids[0]
            )
        else:
            # Custom embed for multiple sessions
            embed = discord.Embed(
                title="✅ Réservation confirmée",
                description=f"Votre pack de **{quantity} séances** a été créé!\n\n"
                            f"**Première séance réservée:**",
                color=config.SUCCESS_COLOR
            )
            embed.add_field(
                name="📅 Date et heure",
                value=created_slots[0].strftime("%d/%m/%Y à %H:%M"),
                inline=True
            )
            embed.add_field(
                name="⏱️ Durée",
                value=f"{duration} minutes",
                inline=True
            )
            embed.add_field(
                name="🆔 ID",
                value=f"`{booking_ids[0]}`",
                inline=True
            )
            embed.add_field(
                name="ℹ️ Séances restantes",
                value=f"Il vous reste **{quantity - 1} séance(s)** à planifier.\n"
                      f"Contactez votre coach pour planifier les prochaines séances.",
                inline=False
            )
            embed.set_footer(text="Vous recevrez des rappels 24h et 1h avant chaque session")
            embed.timestamp = datetime.utcnow()

        await interaction.followup.edit_message(
            message_id=interaction.message.id,
            embed=embed,
            view=None
        )

        # Send student controls for managing their booking
        controls_embed = discord.Embed(
            title="🎮 Gérer votre réservation",
            description="Utilisez les boutons ci-dessous pour annuler ou reporter votre réservation.",
            color=config.BOT_COLOR
        )
        student_view = StudentBookingControlsView(cog=self, booking_id=booking_ids[0], user=user)
        await interaction.channel.send(embed=controls_embed, view=student_view)

        # Notify coaches
        await self.notify_coaches(user, booking_type, created_slots[0], booking_ids[0], quantity)

        # Clean up ticket data
        if ticket_channel_id in self.active_tickets:
            del self.active_tickets[ticket_channel_id]

    async def notify_coaches(
        self,
        user: discord.Member,
        booking_type: str,
        scheduled_at: datetime,
        booking_id: int,
        quantity: int = 1
    ):
        """
        Send notification to coaches about new booking

        Args:
            user: The user who made the booking
            booking_type: Type of booking
            scheduled_at: Scheduled time
            booking_id: Booking ID
            quantity: Number of sessions in the pack
        """
        coach_role = user.guild.get_role(config.COACH_ROLE_ID)
        if not coach_role:
            return

        type_emoji = "🆓" if booking_type == config.BOOKING_TYPE_FREE else "💰"
        type_label = "Coaching Gratuit" if booking_type == config.BOOKING_TYPE_FREE else "Coaching Payant"

        embed = discord.Embed(
            title=f"{type_emoji} Nouvelle réservation",
            description=f"Une nouvelle session de {type_label.lower()} a été réservée!",
            color=config.SUCCESS_COLOR
        )
        embed.add_field(name="👤 Client", value=user.mention, inline=True)
        embed.add_field(
            name="📅 Date (1ère séance)",
            value=scheduled_at.strftime("%d/%m/%Y à %H:%M"),
            inline=True
        )
        embed.add_field(name="🆔 ID", value=f"`{booking_id}`", inline=True)

        if quantity > 1:
            embed.add_field(
                name="📦 Pack",
                value=f"{quantity} séances ({quantity - 1} restante(s) à planifier)",
                inline=False
            )

        embed.timestamp = datetime.utcnow()

        # Send to log channel
        log_channel = user.guild.get_channel(config.LOG_CHANNEL_ID)
        if log_channel:
            try:
                await log_channel.send(
                    content=coach_role.mention,
                    embed=embed
                )
            except discord.Forbidden:
                print(f"❌ No permission to send to log channel")

    async def handle_cancel_booking(self, interaction: discord.Interaction, booking_id: int):
        """
        Handle booking cancellation request

        Args:
            interaction: The interaction
            booking_id: The booking ID to cancel
        """
        await interaction.response.defer(ephemeral=True)

        with get_session() as session:
            booking = session.query(Booking).filter_by(id=booking_id).first()

            if not booking:
                await interaction.followup.send(
                    embed=create_error_embed("Réservation introuvable."),
                    ephemeral=True
                )
                return

            if booking.status == config.STATUS_CANCELLED:
                await interaction.followup.send(
                    embed=create_error_embed("Cette réservation est déjà annulée."),
                    ephemeral=True
                )
                return

            # Cancel booking
            booking.status = config.STATUS_CANCELLED
            session.commit()

            # Delete from Google Calendar
            if booking.google_event_id:
                try:
                    self.calendar_manager.delete_event(booking.google_event_id)
                except Exception as e:
                    print(f"❌ Error deleting calendar event: {e}")

            # Get client info
            client = session.query(Client).filter_by(id=booking.client_id).first()

            # Send confirmation
            embed = discord.Embed(
                title="✅ Réservation annulée",
                description=f"Votre session du **{booking.scheduled_at.strftime('%d/%m/%Y à %H:%M')}** a été annulée.",
                color=config.SUCCESS_COLOR
            )
            embed.add_field(name="🆔 ID", value=f"`{booking_id}`", inline=False)
            embed.set_footer(text="Vous pouvez créer une nouvelle réservation à tout moment.")
            embed.timestamp = datetime.utcnow()

            await interaction.followup.send(embed=embed, ephemeral=True)

            # Notify coaches
            coach_role = interaction.guild.get_role(config.COACH_ROLE_ID)
            if coach_role and client:
                log_channel = interaction.guild.get_channel(config.LOG_CHANNEL_ID)
                if log_channel:
                    try:
                        notify_embed = discord.Embed(
                            title="❌ Réservation annulée",
                            description=f"{interaction.user.mention} a annulé une réservation.",
                            color=config.ERROR_COLOR
                        )
                        notify_embed.add_field(name="👤 Client", value=client.discord_name, inline=True)
                        notify_embed.add_field(name="📅 Date", value=booking.scheduled_at.strftime('%d/%m/%Y à %H:%M'), inline=True)
                        notify_embed.add_field(name="🆔 ID", value=f"`{booking_id}`", inline=True)
                        notify_embed.timestamp = datetime.utcnow()
                        await log_channel.send(content=coach_role.mention, embed=notify_embed)
                    except:
                        pass

    async def handle_reschedule_booking(self, interaction: discord.Interaction, booking_id: int):
        """
        Handle booking rescheduling request

        Args:
            interaction: The interaction
            booking_id: The booking ID to reschedule
        """
        await interaction.response.defer(ephemeral=True)

        with get_session() as session:
            booking = session.query(Booking).filter_by(id=booking_id).first()

            if not booking:
                await interaction.followup.send(
                    embed=create_error_embed("Réservation introuvable."),
                    ephemeral=True
                )
                return

            if booking.status == config.STATUS_CANCELLED:
                await interaction.followup.send(
                    embed=create_error_embed("Cette réservation est annulée. Créez une nouvelle réservation."),
                    ephemeral=True
                )
                return

            if booking.status == config.STATUS_COMPLETED:
                await interaction.followup.send(
                    embed=create_error_embed("Cette réservation est déjà complétée."),
                    ephemeral=True
                )
                return

            # Store booking info for rescheduling
            old_date = booking.scheduled_at
            duration = booking.duration_minutes
            booking_type = booking.booking_type

            # Show date selector to pick new date
            embed = create_info_embed(
                f"📅 **Reporter la réservation**\n\n"
                f"Ancienne date: {old_date.strftime('%d/%m/%Y à %H:%M')}\n\n"
                f"Sélectionnez une nouvelle date:"
            )

            # Store reschedule data
            ticket_channel_id = interaction.channel.id
            self.active_tickets[ticket_channel_id] = {
                'user': interaction.user,
                'booking_type': booking_type,
                'quantity': 1,
                'reschedule_booking_id': booking_id,
                'old_date': old_date
            }

            view = DateSelectorView(cog=self, ticket_channel_id=ticket_channel_id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class BookingButtonView(discord.ui.View):
    """
    Persistent view with booking button
    """

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📅 Réserver un Coaching",
        style=discord.ButtonStyle.primary,
        custom_id="create_booking_ticket"
    )
    async def booking_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Handle booking button click
        """
        # Get tickets cog
        cog = interaction.client.get_cog("Tickets")
        if not cog:
            await interaction.response.send_message(
                embed=create_error_embed("Le système de tickets n'est pas disponible."),
                ephemeral=True
            )
            return

        user_id = interaction.user.id

        # Check if user already has a ticket (only for non-coaches)
        if not is_coach(interaction.user):
            # CRITICAL: Defer OUTSIDE the lock to prevent Discord timeout
            await interaction.response.defer(ephemeral=True)

            # Use GLOBAL lock to serialize ALL ticket operations (prevents all race conditions)
            # IMPORTANT: Keep EVERYTHING inside the lock, including ticket creation
            async with cog._global_ticket_lock:
                print(f"🔒 [LOCK ACQUIRED] User {interaction.user.name} (ID: {user_id}) entered lock")

                # Check if user is already creating a ticket right now
                if user_id in cog._creating_tickets:
                    print(f"⚠️ User {interaction.user.name} already creating ticket, blocking")
                    await interaction.followup.send(
                        embed=create_error_embed(
                            "Création de ticket déjà en cours...\n\n"
                            "Veuillez patienter quelques secondes."
                        ),
                        ephemeral=True
                    )
                    return

                guild = interaction.guild
                category = guild.get_channel(config.TICKET_CATEGORY_ID)

                if category:
                    # Check if user already has an open ticket by checking channel overwrites
                    for channel in category.channels:
                        # Skip if not a text channel
                        if not isinstance(channel, discord.TextChannel):
                            continue

                        # Check if channel starts with "ticket-"
                        if channel.name.startswith("ticket-"):
                            # Check if the user has explicit permission overwrites in this channel
                            # This means they are the owner of the ticket
                            if interaction.user in channel.overwrites:
                                user_overwrite = channel.overwrites[interaction.user]
                                # If user has read_messages explicitly set to True, this is their ticket
                                if user_overwrite.read_messages is True:
                                    print(f"⚠️ User {interaction.user.name} already has ticket {channel.name}, blocking")
                                    await interaction.followup.send(
                                        embed=create_error_embed(
                                            f"Vous avez déjà un ticket ouvert: {channel.mention}\n\n"
                                            f"Veuillez fermer votre ticket actuel avant d'en créer un nouveau."
                                        ),
                                        ephemeral=True
                                    )
                                    return

                # Mark user as creating a ticket
                print(f"✅ User {interaction.user.name} passed checks, creating ticket...")
                cog._creating_tickets.add(user_id)

                # Create ticket INSIDE the lock to prevent race conditions
                try:
                    ticket_channel = await cog.create_ticket(interaction.user)

                    if ticket_channel:
                        print(f"✅ Ticket {ticket_channel.name} created successfully for {interaction.user.name}")
                        embed = create_ticket_embed(ticket_channel)
                        await interaction.followup.send(embed=embed, ephemeral=True)
                    else:
                        print(f"❌ Failed to create ticket for {interaction.user.name}")
                        await interaction.followup.send(
                            embed=create_error_embed("Impossible de créer le ticket. Contactez un administrateur."),
                            ephemeral=True
                        )
                finally:
                    # Always remove user from creating set
                    cog._creating_tickets.discard(user_id)
                    print(f"🔓 [LOCK RELEASED] User {interaction.user.name} (ID: {user_id}) exited lock")
        else:
            # Coaches bypass the lock but still need to defer
            await interaction.response.defer(ephemeral=True)
            ticket_channel = await cog.create_ticket(interaction.user)

            if ticket_channel:
                embed = create_ticket_embed(ticket_channel)
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    embed=create_error_embed("Impossible de créer le ticket. Contactez un administrateur."),
                    ephemeral=True
                )


async def setup(bot):
    """
    Setup function to add the cog to the bot
    """
    cog = Tickets(bot)
    await bot.add_cog(cog)

    
    bot.add_view(BookingButtonView())
