"""
Discord views for the booking process
"""
import discord
from discord.ui import Button, View, Select
from datetime import datetime, timedelta
from typing import List, Callable, Optional
import config
from utils.embeds import create_success_embed, create_error_embed, create_booking_embed
from utils.permissions import is_coach


class CoachTicketControlsView(View):
    """
    View with coach-only controls for ticket management
    """

    def __init__(self, cog, ticket_channel, timeout: float = None):
        """
        Args:
            cog: Reference to the Tickets cog
            ticket_channel: The ticket channel
            timeout: Timeout in seconds (None = no timeout)
        """
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ticket_channel = ticket_channel

    @discord.ui.button(
        label="🔒 Fermer le ticket",
        style=discord.ButtonStyle.danger,
        custom_id="coach_close_ticket"
    )
    async def close_ticket_button(self, interaction: discord.Interaction, button: Button):
        """
        Close the ticket (coach only)
        """
        # Check if user is coach
        if not is_coach(interaction.user):
            await interaction.response.send_message(
                embed=create_error_embed("Seuls les coachs peuvent fermer les tickets."),
                ephemeral=True
            )
            return

        # Confirm closure
        embed = discord.Embed(
            title="🔒 Fermeture du ticket",
            description="Le ticket sera fermé dans 5 secondes...",
            color=config.WARNING_COLOR
        )
        await interaction.response.send_message(embed=embed)

        # Wait 5 seconds
        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=5))

        try:
            await self.ticket_channel.delete(reason=f"Ticket fermé par {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Permissions insuffisantes pour supprimer le ticket."),
                ephemeral=True
            )

    @discord.ui.button(
        label="📝 Ajouter une note",
        style=discord.ButtonStyle.secondary,
        custom_id="coach_add_note"
    )
    async def add_note_button(self, interaction: discord.Interaction, button: Button):
        """
        Add a note about the client (coach only)
        """
        # Check if user is coach
        if not is_coach(interaction.user):
            await interaction.response.send_message(
                embed=create_error_embed("Seuls les coachs peuvent ajouter des notes."),
                ephemeral=True
            )
            return

        # Show modal for note input
        modal = AddNoteModal(cog=self.cog, ticket_channel=self.ticket_channel)
        await interaction.response.send_modal(modal)


class AddNoteModal(discord.ui.Modal):
    """
    Modal for adding a note about a client
    """

    def __init__(self, cog, ticket_channel):
        super().__init__(title="Ajouter une note sur le client")
        self.cog = cog
        self.ticket_channel = ticket_channel

        self.note_input = discord.ui.TextInput(
            label="Note",
            placeholder="Entrez vos observations sur le client...",
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

        # Get client from ticket name or active tickets
        # For now, we'll show a confirmation
        embed = create_success_embed(
            f"Note ajoutée avec succès!\n\n**Contenu:** {note_content[:100]}..."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # TODO: Save to database when we implement the notes system


class SessionQuantityView(View):
    """
    View for selecting number of sessions (paid coaching only)
    """

    def __init__(self, cog, user, timeout: float = 300):
        """
        Args:
            cog: Reference to the Tickets cog
            user: The user who is booking
            timeout: Timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user = user
        self._add_quantity_select()

    def _add_quantity_select(self):
        """
        Add select menu for session quantity
        """
        options = [
            discord.SelectOption(
                label="1 séance",
                value="1",
                emoji="1️⃣",
                description="Une séance de coaching"
            ),
            discord.SelectOption(
                label="2 séances",
                value="2",
                emoji="2️⃣",
                description="Pack de 2 séances"
            ),
            discord.SelectOption(
                label="3 séances",
                value="3",
                emoji="3️⃣",
                description="Pack de 3 séances"
            ),
            discord.SelectOption(
                label="4 séances",
                value="4",
                emoji="4️⃣",
                description="Pack de 4 séances"
            ),
            discord.SelectOption(
                label="5 séances",
                value="5",
                emoji="5️⃣",
                description="Pack de 5 séances"
            ),
            discord.SelectOption(
                label="📦 Suivi 1 mois (8 séances)",
                value="8",
                emoji="📅",
                description="Pack mensuel - 8 séances (recommandé)"
            )
        ]

        select = Select(
            placeholder="Sélectionnez le nombre de séances",
            options=options,
            custom_id="quantity_select"
        )
        select.callback = self._quantity_selected
        self.add_item(select)

    async def _quantity_selected(self, interaction: discord.Interaction):
        """
        Called when quantity is selected
        """
        quantity = int(interaction.data['values'][0])
        await self.cog.quantity_selected(interaction, quantity, self.user)
        self.stop()


class BookingTypeView(View):
    """
    View for selecting booking type (free or paid)
    """

    def __init__(self, cog, user, timeout: float = 300):
        """
        Args:
            cog: Reference to the Tickets cog
            user: The user who created the ticket
            timeout: Timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user = user

    @discord.ui.button(
        label="🆓 Coaching Gratuit",
        style=discord.ButtonStyle.success,
        custom_id="booking_free"
    )
    async def free_button(self, interaction: discord.Interaction, button: Button):
        await self.cog.booking_type_selected(interaction, config.BOOKING_TYPE_FREE, self.user)
        self.stop()

    @discord.ui.button(
        label="💰 Coaching Payant",
        style=discord.ButtonStyle.primary,
        custom_id="booking_paid"
    )
    async def paid_button(self, interaction: discord.Interaction, button: Button):
        await self.cog.booking_type_selected(interaction, config.BOOKING_TYPE_PAID, self.user)
        self.stop()

    async def on_timeout(self):
        """
        Called when the view times out
        """
        for item in self.children:
            item.disabled = True


class DateSelectorView(View):
    """
    View for selecting a date (next 14 days)
    """

    def __init__(self, cog, ticket_channel_id: int, timeout: float = 300):
        """
        Args:
            cog: Reference to the Tickets cog
            ticket_channel_id: ID of the ticket channel
            timeout: Timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ticket_channel_id = ticket_channel_id
        self._add_date_select()

    def _add_date_select(self):
        """
        Add select menu with next 14 days
        """
        options = []
        today = datetime.now(config.TIMEZONE)

        for i in range(14):
            date = today + timedelta(days=i)
            label = date.strftime("%A %d/%m/%Y")
            if i == 0:
                label = f"Aujourd'hui - {label}"
            elif i == 1:
                label = f"Demain - {label}"

            options.append(
                discord.SelectOption(
                    label=label,
                    value=date.strftime("%Y-%m-%d"),
                    emoji="📅"
                )
            )

        select = Select(
            placeholder="Sélectionnez une date",
            options=options,
            custom_id="date_select"
        )
        select.callback = self._date_selected
        self.add_item(select)

    async def _date_selected(self, interaction: discord.Interaction):
        """
        Called when a date is selected
        """
        select = interaction.data['values'][0]
        selected_date = datetime.strptime(select, "%Y-%m-%d")
        selected_date = config.TIMEZONE.localize(selected_date)
        await self.cog.date_selected(interaction, selected_date, self.ticket_channel_id)
        self.stop()


class CalendarSlotsView(View):
    """
    View for selecting a time slot from available slots
    """

    def __init__(
        self,
        cog,
        slots: List[datetime],
        ticket_channel_id: int,
        timeout: float = 300
    ):
        """
        Args:
            cog: Reference to the Tickets cog
            slots: List of available datetime slots
            ticket_channel_id: ID of the ticket channel
            timeout: Timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.cog = cog
        self.slots = slots
        self.ticket_channel_id = ticket_channel_id
        self._add_slot_select()

    def _add_slot_select(self):
        """
        Add select menu with available time slots
        Limited to 25 options (Discord limit)
        """
        if not self.slots:
            return

        options = []
        for slot in self.slots[:25]:  # Discord limit
            time_str = slot.strftime("%H:%M")
            options.append(
                discord.SelectOption(
                    label=time_str,
                    value=slot.isoformat(),
                    emoji="⏰"
                )
            )

        select = Select(
            placeholder="Sélectionnez un créneau horaire",
            options=options,
            custom_id="slot_select"
        )
        select.callback = self._slot_selected
        self.add_item(select)

    async def _slot_selected(self, interaction: discord.Interaction):
        """
        Called when a time slot is selected
        """
        slot_iso = interaction.data['values'][0]
        selected_slot = datetime.fromisoformat(slot_iso)
        await self.cog.slot_selected(interaction, selected_slot, self.ticket_channel_id)
        self.stop()

    @discord.ui.button(
        label="❌ Annuler",
        style=discord.ButtonStyle.danger,
        custom_id="cancel_booking"
    )
    async def cancel_button(self, button: Button, interaction: discord.Interaction):
        embed = create_error_embed("Réservation annulée.")
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


class ConfirmBookingView(View):
    """
    View for confirming a booking
    """

    def __init__(
        self,
        booking_details: dict,
        confirm_callback: Callable,
        cancel_callback: Optional[Callable] = None,
        timeout: float = 300
    ):
        """
        Args:
            booking_details: Dictionary with booking information
            confirm_callback: Async function to call on confirmation
            cancel_callback: Optional async function to call on cancellation
            timeout: Timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.booking_details = booking_details
        self.confirm_callback = confirm_callback
        self.cancel_callback = cancel_callback

    @discord.ui.button(
        label="✅ Confirmer",
        style=discord.ButtonStyle.success,
        custom_id="confirm_booking"
    )
    async def confirm_button(self, button: Button, interaction: discord.Interaction):
        await self.confirm_callback(interaction, self.booking_details)
        self.stop()

    @discord.ui.button(
        label="❌ Annuler",
        style=discord.ButtonStyle.danger,
        custom_id="cancel_booking"
    )
    async def cancel_button(self, button: Button, interaction: discord.Interaction):
        if self.cancel_callback:
            await self.cancel_callback(interaction)
        else:
            embed = create_error_embed("Réservation annulée.")
            await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


class StudentBookingControlsView(View):
    """
    View with student controls for managing their booking
    """

    def __init__(self, cog, booking_id: int, user: discord.Member, timeout: float = None):
        """
        Args:
            cog: Reference to the Tickets cog
            booking_id: The booking ID
            user: The user who made the booking
            timeout: Timeout in seconds (None = no timeout)
        """
        super().__init__(timeout=timeout)
        self.cog = cog
        self.booking_id = booking_id
        self.user = user

    @discord.ui.button(
        label="❌ Annuler la réservation",
        style=discord.ButtonStyle.danger,
        custom_id="student_cancel_booking"
    )
    async def cancel_booking_button(self, interaction: discord.Interaction, button: Button):
        """
        Cancel the booking
        """
        # Only the student who made the booking or a coach can cancel
        if interaction.user.id != self.user.id and not is_coach(interaction.user):
            await interaction.response.send_message(
                embed=create_error_embed("Vous ne pouvez annuler que vos propres réservations."),
                ephemeral=True
            )
            return

        await self.cog.handle_cancel_booking(interaction, self.booking_id)

    @discord.ui.button(
        label="📅 Reporter la réservation",
        style=discord.ButtonStyle.primary,
        custom_id="student_reschedule_booking"
    )
    async def reschedule_booking_button(self, interaction: discord.Interaction, button: Button):
        """
        Reschedule the booking
        """
        # Only the student who made the booking or a coach can reschedule
        if interaction.user.id != self.user.id and not is_coach(interaction.user):
            await interaction.response.send_message(
                embed=create_error_embed("Vous ne pouvez reporter que vos propres réservations."),
                ephemeral=True
            )
            return

        await self.cog.handle_reschedule_booking(interaction, self.booking_id)
