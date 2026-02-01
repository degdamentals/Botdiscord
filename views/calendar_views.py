"""
Discord views for calendar interaction
"""
import discord
from discord.ui import Button, View
from typing import Callable


class CalendarNavigationView(View):
    """
    View for navigating through calendar pages
    """

    def __init__(
        self,
        current_page: int,
        total_pages: int,
        prev_callback: Callable,
        next_callback: Callable,
        timeout: float = 300
    ):
        """
        Args:
            current_page: Current page number (0-indexed)
            total_pages: Total number of pages
            prev_callback: Async function to call for previous page
            next_callback: Async function to call for next page
            timeout: Timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.current_page = current_page
        self.total_pages = total_pages
        self.prev_callback = prev_callback
        self.next_callback = next_callback

        # Disable buttons if at boundaries
        if current_page == 0:
            self.prev_button.disabled = True
        if current_page >= total_pages - 1:
            self.next_button.disabled = True

    @discord.ui.button(label="◀️ Précédent", style=discord.ButtonStyle.secondary, custom_id="prev_page")
    async def prev_button(self, button: Button, interaction: discord.Interaction):
        await self.prev_callback(interaction, self.current_page - 1)

    @discord.ui.button(label="Suivant ▶️", style=discord.ButtonStyle.secondary, custom_id="next_page")
    async def next_button(self, button: Button, interaction: discord.Interaction):
        await self.next_callback(interaction, self.current_page + 1)

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.danger, custom_id="cancel")
    async def cancel_button(self, button: Button, interaction: discord.Interaction):
        from utils.embeds import create_error_embed
        embed = create_error_embed("Navigation annulée.")
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
