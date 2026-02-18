"""
Reminders Cog - Automatic reminders for coaching sessions
"""
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import datetime as dt
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
        self.daily_coach_summary.start()
        self.check_pack_expiry.start()

    def cog_unload(self):
        """
        Stop the reminder task when cog is unloaded
        """
        self.check_reminders.cancel()
        self.daily_coach_summary.cancel()
        self.check_pack_expiry.cancel()

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
                scheduled = booking.scheduled_at
                # Ensure timezone-aware comparison
                if scheduled.tzinfo is None:
                    scheduled = config.TIMEZONE.localize(scheduled)
                time_until = scheduled - now

                # 24h reminder - only if not already sent
                if (config.REMINDER_24H_ENABLED
                        and not booking.reminder_24h_sent
                        and timedelta(hours=23, minutes=45) <= time_until <= timedelta(hours=24, minutes=15)):
                    await self.send_24h_reminder(booking)
                    booking.reminder_24h_sent = True
                    session.commit()

                # 1h reminder - only if not already sent
                if (config.REMINDER_1H_ENABLED
                        and not booking.reminder_1h_sent
                        and timedelta(minutes=45) <= time_until <= timedelta(hours=1, minutes=15)):
                    await self.send_1h_reminder(booking)
                    booking.reminder_1h_sent = True
                    session.commit()

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

    @tasks.loop(time=dt.time(hour=20, minute=0, tzinfo=config.TIMEZONE))
    async def daily_coach_summary(self):
        """
        Send daily summary to coaches at 20:00 with tomorrow's sessions
        """
        now = datetime.now(config.TIMEZONE)
        tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_end = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        tomorrow_label = tomorrow_start.strftime("%d/%m/%Y")

        # Get tomorrow's bookings
        with get_session() as session:
            bookings = session.query(Booking).filter(
                Booking.status == config.STATUS_CONFIRMED,
                Booking.scheduled_at >= tomorrow_start,
                Booking.scheduled_at <= tomorrow_end
            ).order_by(Booking.scheduled_at).all()

            if not bookings:
                return

            # Create summary embed
            embed = discord.Embed(
                title=f"📅 Planning de demain — {tomorrow_label}",
                description=f"Vous avez **{len(bookings)}** session(s) prévue(s) demain",
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

            embed.set_footer(text="Bonne séance de coaching demain! 🎮")
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


    @tasks.loop(hours=12)  # Check twice a day
    async def check_pack_expiry(self):
        """
        Check for expired pack sessions (pending_schedule older than PACK_EXPIRY_DAYS)
        and cancel them automatically
        """
        now = datetime.now(config.TIMEZONE)
        expiry_threshold = now - timedelta(days=config.PACK_EXPIRY_DAYS)

        with get_session() as session:
            expired_bookings = session.query(Booking).filter(
                Booking.status == config.STATUS_PENDING_SCHEDULE,
                Booking.created_at <= expiry_threshold
            ).all()

            for booking in expired_bookings:
                booking.status = config.STATUS_CANCELLED
                print(f"⚠️ Pack session {booking.id} expired after {config.PACK_EXPIRY_DAYS} days — cancelled")

            if expired_bookings:
                session.commit()
                # Notify coaches if any packs expired
                guild = self.bot.get_guild(config.GUILD_ID)
                if guild and config.LOG_CHANNEL_ID:
                    log_channel = guild.get_channel(config.LOG_CHANNEL_ID)
                    if log_channel:
                        embed = discord.Embed(
                            title="⚠️ Sessions pack expirées",
                            description=f"**{len(expired_bookings)}** session(s) pack ont expiré après {config.PACK_EXPIRY_DAYS} jours sans être planifiées et ont été annulées.",
                            color=config.WARNING_COLOR
                        )
                        embed.timestamp = datetime.utcnow()
                        try:
                            await log_channel.send(embed=embed)
                        except discord.Forbidden:
                            pass

    @check_pack_expiry.before_loop
    async def before_check_pack_expiry(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    """
    Setup function to add the cog to the bot
    """
    await bot.add_cog(Reminders(bot))
