"""
Discord views for the feedback system
"""
import discord
from discord.ui import Button, View, Select, Modal, TextInput
from typing import Callable, Optional
from utils.embeds import create_success_embed, create_error_embed


class FeedbackRatingView(View):
    """
    View for rating a coaching session (1-5 stars)
    """

    def __init__(self, callback: Callable, timeout: float = 3600):
        """
        Args:
            callback: Async function to call with (interaction, rating)
            timeout: Timeout in seconds (default 1 hour)
        """
        super().__init__(timeout=timeout)
        self.callback = callback

    @discord.ui.button(label="⭐", style=discord.ButtonStyle.secondary, custom_id="rating_1")
    async def one_star(self, button: Button, interaction: discord.Interaction):
        await self.callback(interaction, 1)
        self.stop()

    @discord.ui.button(label="⭐⭐", style=discord.ButtonStyle.secondary, custom_id="rating_2")
    async def two_stars(self, button: Button, interaction: discord.Interaction):
        await self.callback(interaction, 2)
        self.stop()

    @discord.ui.button(label="⭐⭐⭐", style=discord.ButtonStyle.secondary, custom_id="rating_3")
    async def three_stars(self, button: Button, interaction: discord.Interaction):
        await self.callback(interaction, 3)
        self.stop()

    @discord.ui.button(label="⭐⭐⭐⭐", style=discord.ButtonStyle.primary, custom_id="rating_4")
    async def four_stars(self, button: Button, interaction: discord.Interaction):
        await self.callback(interaction, 4)
        self.stop()

    @discord.ui.button(label="⭐⭐⭐⭐⭐", style=discord.ButtonStyle.success, custom_id="rating_5")
    async def five_stars(self, button: Button, interaction: discord.Interaction):
        await self.callback(interaction, 5)
        self.stop()


class FeedbackCommentModal(Modal):
    """
    Modal for collecting feedback comment
    """

    def __init__(self, rating: int, callback: Callable):
        """
        Args:
            rating: The rating given (1-5)
            callback: Async function to call with (interaction, rating, comment)
        """
        super().__init__(title=f"Feedback - {'⭐' * rating}")
        self.rating = rating
        self.callback = callback

        self.comment_input = TextInput(
            label="Commentaire (optionnel)",
            placeholder="Partagez votre expérience...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        self.add_item(self.comment_input)

    async def on_submit(self, interaction: discord.Interaction):
        comment = self.comment_input.value.strip() if self.comment_input.value else None
        await self.callback(interaction, self.rating, comment)


class FeedbackShareView(View):
    """
    View for asking permission to share feedback publicly
    """

    def __init__(self, callback: Callable, timeout: float = 300):
        """
        Args:
            callback: Async function to call with (interaction, should_share)
            timeout: Timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.callback = callback

    @discord.ui.button(
        label="✅ Oui, partager mon feedback",
        style=discord.ButtonStyle.success,
        custom_id="share_yes"
    )
    async def share_yes(self, button: Button, interaction: discord.Interaction):
        await self.callback(interaction, True)
        self.stop()

    @discord.ui.button(
        label="❌ Non, garder privé",
        style=discord.ButtonStyle.secondary,
        custom_id="share_no"
    )
    async def share_no(self, button: Button, interaction: discord.Interaction):
        await self.callback(interaction, False)
        self.stop()


class FeedbackView:
    """
    Complete feedback flow handler
    """

    def __init__(self, booking_id: int, client_name: str, final_callback: Callable):
        """
        Args:
            booking_id: ID of the booking
            client_name: Name of the client
            final_callback: Async function to call with (booking_id, rating, comment, should_share)
        """
        self.booking_id = booking_id
        self.client_name = client_name
        self.final_callback = final_callback
        self.rating = None
        self.comment = None

    async def start(self, channel_or_user):
        """
        Start the feedback flow

        Args:
            channel_or_user: Discord channel or user to send the feedback request to
        """
        embed = discord.Embed(
            title="📝 Votre avis compte!",
            description=f"Comment s'est passée votre session de coaching?\n\n"
                        f"Merci de prendre un moment pour évaluer votre expérience.",
            color=0x5865F2
        )
        embed.set_footer(text="Votre feedback nous aide à améliorer nos services")

        view = FeedbackRatingView(callback=self._rating_received)
        await channel_or_user.send(embed=embed, view=view)

    async def _rating_received(self, interaction: discord.Interaction, rating: int):
        """
        Handle rating selection
        """
        self.rating = rating

        # Show modal for comment
        modal = FeedbackCommentModal(rating=rating, callback=self._comment_received)
        await interaction.response.send_modal(modal)

    async def _comment_received(self, interaction: discord.Interaction, rating: int, comment: Optional[str]):
        """
        Handle comment submission
        """
        self.comment = comment

        # Ask about sharing
        embed = discord.Embed(
            title="🌟 Merci pour votre feedback!",
            description="Acceptez-vous que nous partagions votre avis dans le salon #feedback?\n\n"
                        "Cela aide d'autres élèves à découvrir nos services.",
            color=0x57F287
        )

        view = FeedbackShareView(callback=self._share_response)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _share_response(self, interaction: discord.Interaction, should_share: bool):
        """
        Handle share permission response
        """
        # Call final callback with all collected data
        await self.final_callback(self.booking_id, self.rating, self.comment, should_share)

        # Send confirmation
        embed = create_success_embed(
            "Votre feedback a été enregistré avec succès!\n\n"
            "Merci d'avoir pris le temps de partager votre expérience. 💙"
        )
        await interaction.response.edit_message(embed=embed, view=None)
