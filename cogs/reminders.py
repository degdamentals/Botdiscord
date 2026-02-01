"""
Reminders Cog - Automatic reminders for coaching sessions
"""
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import config
from database import get_session, Booking, Client
from utils.embeds import create_info_embed


class Reminders(commands.Cog):
    """
    Cog for managing automatic reminders for coaching sessions
    """

    def __init__(self, bot):
        self.bot = bot
        self.check_reminders.start()

    def cog_unload(self):
        """
        Stop the reminder task when cog is unloaded
        """
        self.check_reminders.cancel()

    async def cog_load(self):
        """
        Called when the cog is loaded
        """
        print("🔔 Reminders cog loaded")

    @tasks.loop(minutes=15)  # Check every 15 minutes
    async def check_reminders(self):
        """
        Check for upcoming sessions and send reminders
        """
        now = datetime.now(config.TIMEZONE)

        # Get all confirmed bookings
        with get_session() as session:
            bookings = session.query(Booking).filter(
                Booking.status == config.STATUS_CONFIRMED,
                Booking.scheduled_at > now
            ).all()

            for booking in bookings:
                time_until = booking.scheduled_at.replace(tzinfo=config.TIMEZONE) - now

                # 24h reminder
                if config.REMINDER_24H_ENABLED and timedelta(hours=23, minutes=45) <= time_until <= timedelta(hours=24, minutes=15):
                    await self.send_24h_reminder(booking)

                # 1h reminder
                if config.REMINDER_1H_ENABLED and timedelta(minutes=45) <= time_until <= timedelta(hours=1, minutes=15):
                    await self.send_1h_reminder(booking)

    @check_reminders.before_loop
    async def before_check_reminders(self):
        """
        Wait until the bot is ready before starting the task
        """
        await self.bot.wait_until_ready()

    async def send_24h_reminder(self, booking: Booking):
        """
        Send 24h reminder to client

        Args:
            booking: The booking to send reminder for
        """
        with get_session() as session:
            client = session.query(Client).filter_by(id=booking.client_id).first()
            if not client:
                return

            # Get Discord user
            try:
                user = await self.bot.fetch_user(int(client.discord_id))
            except:
                print(f"❌ Could not fetch user {client.discord_id}")
                return

            # Create reminder embed
            type_label = "Coaching Gratuit" if booking.booking_type == config.BOOKING_TYPE_FREE else "Coaching Payant"
            embed = discord.Embed(
                title="🔔 Rappel de session - 24h",
                description=f"Votre session de **{type_label.lower()}** aura lieu demain!",
                color=config.BOT_COLOR
            )
            embed.add_field(
                name="📅 Date et heure",
                value=booking.scheduled_at.strftime("%d/%m/%Y à %H:%M"),
                inline=False
            )
            embed.add_field(
                name="⏱️ Durée",
                value=f"{booking.duration_minutes} minutes",
                inline=True
            )
            embed.add_field(
                name="🆔 ID de réservation",
                value=f"`{booking.id}`",
                inline=True
            )
            embed.set_footer(text="Vous recevrez un autre rappel 1h avant la session")
            embed.timestamp = datetime.utcnow()

            try:
                await user.send(embed=embed)
                print(f"✅ Sent 24h reminder to {client.discord_name} for booking {booking.id}")
            except discord.Forbidden:
                print(f"❌ Cannot send DM to {client.discord_name}")

    async def send_1h_reminder(self, booking: Booking):
        """
        Send 1h reminder to client

        Args:
            booking: The booking to send reminder for
        """
        with get_session() as session:
            client = session.query(Client).filter_by(id=booking.client_id).first()
            if not client:
                return

            # Get Discord user
            try:
                user = await self.bot.fetch_user(int(client.discord_id))
            except:
                print(f"❌ Could not fetch user {client.discord_id}")
                return

            # Create reminder embed
            type_label = "Coaching Gratuit" if booking.booking_type == config.BOOKING_TYPE_FREE else "Coaching Payant"
            embed = discord.Embed(
                title="🔔 Rappel de session - 1h",
                description=f"Votre session de **{type_label.lower()}** commence dans **1 heure**!",
                color=config.WARNING_COLOR
            )
            embed.add_field(
                name="📅 Heure de début",
                value=booking.scheduled_at.strftime("%H:%M"),
                inline=False
            )
            embed.add_field(
                name="⏱️ Durée",
                value=f"{booking.duration_minutes} minutes",
                inline=True
            )
            embed.add_field(
                name="🆔 ID",
                value=f"`{booking.id}`",
                inline=True
            )
            embed.set_footer(text="À tout de suite! 🎮")
            embed.timestamp = datetime.utcnow()

            try:
                await user.send(embed=embed)
                print(f"✅ Sent 1h reminder to {client.discord_name} for booking {booking.id}")
            except discord.Forbidden:
                print(f"❌ Cannot send DM to {client.discord_name}")

    @tasks.loop(hours=24)  # Every day at the same time
    async def daily_coach_summary(self):
        """
        Send daily summary to coaches
        """
        now = datetime.now(config.TIMEZONE)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Get today's bookings
        with get_session() as session:
            bookings = session.query(Booking).filter(
                Booking.status == config.STATUS_CONFIRMED,
                Booking.scheduled_at >= today_start,
                Booking.scheduled_at <= today_end
            ).order_by(Booking.scheduled_at).all()

            if not bookings:
                return

            # Create summary embed
            embed = discord.Embed(
                title="📅 Planning du jour",
                description=f"Vous avez **{len(bookings)}** session(s) prévue(s) aujourd'hui",
                color=config.BOT_COLOR
            )

            for booking in bookings:
                client = session.query(Client).filter_by(id=booking.client_id).first()
                if client:
                    type_emoji = "🆓" if booking.booking_type == config.BOOKING_TYPE_FREE else "💰"
                    embed.add_field(
                        name=f"{type_emoji} {booking.scheduled_at.strftime('%H:%M')} - {client.discord_name}",
                        value=f"Durée: {booking.duration_minutes}min | ID: `{booking.id}`",
                        inline=False
                    )

            embed.set_footer(text="Bonne journée de coaching! 🎮")
            embed.timestamp = datetime.utcnow()

            # Send to coaches (find them by role)
            guild = self.bot.get_guild(config.GUILD_ID)
            if guild:
                coach_role = guild.get_role(config.COACH_ROLE_ID)
                if coach_role:
                    for member in coach_role.members:
                        try:
                            await member.send(embed=embed)
                        except discord.Forbidden:
                            print(f"❌ Cannot send DM to coach {member.name}")


async def setup(bot):
    """
    Setup function to add the cog to the bot
    """
    await bot.add_cog(Reminders(bot))
