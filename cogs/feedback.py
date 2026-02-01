"""
Feedback Cog - Post-session feedback system
"""
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import config
from database import get_session, Booking, Client, Feedback
from views.feedback_views import FeedbackView


class FeedbackCog(commands.Cog):
    """
    Cog for managing post-session feedback
    """

    def __init__(self, bot):
        self.bot = bot
        self.check_completed_sessions.start()

    def cog_unload(self):
        """
        Stop the task when cog is unloaded
        """
        self.check_completed_sessions.cancel()

    async def cog_load(self):
        """
        Called when the cog is loaded
        """
        print("⭐ Feedback cog loaded")

    @tasks.loop(minutes=30)  # Check every 30 minutes
    async def check_completed_sessions(self):
        """
        Check for recently completed sessions and send feedback requests
        """
        now = datetime.now(config.TIMEZONE)

        with get_session() as session:
            # Get sessions that ended in the last hour and don't have feedback yet
            one_hour_ago = now - timedelta(hours=1)

            bookings = session.query(Booking).outerjoin(Feedback).filter(
                Booking.status == config.STATUS_CONFIRMED,
                Booking.scheduled_at < now,
                Booking.scheduled_at > one_hour_ago,
                Feedback.id == None  # No feedback exists
            ).all()

            for booking in bookings:
                # Check if session is really completed (scheduled_at + duration has passed)
                session_end = booking.scheduled_at + timedelta(minutes=booking.duration_minutes)
                if session_end <= now:
                    await self.send_feedback_request(booking)
                    # Mark booking as completed
                    booking.status = config.STATUS_COMPLETED
                    session.commit()

    @check_completed_sessions.before_loop
    async def before_check_completed_sessions(self):
        """
        Wait until the bot is ready before starting the task
        """
        await self.bot.wait_until_ready()

    async def send_feedback_request(self, booking: Booking):
        """
        Send feedback request to client after session

        Args:
            booking: The completed booking
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

            # Create and send feedback view
            feedback_view = FeedbackView(
                booking_id=booking.id,
                client_name=client.discord_name,
                final_callback=self.save_feedback
            )

            try:
                await feedback_view.start(user)
                print(f"✅ Sent feedback request to {client.discord_name} for booking {booking.id}")
            except discord.Forbidden:
                print(f"❌ Cannot send DM to {client.discord_name}")

    async def save_feedback(self, booking_id: int, rating: int, comment: str, should_share: bool):
        """
        Save feedback to database and optionally share in feedback channel

        Args:
            booking_id: ID of the booking
            rating: Rating (1-5)
            comment: Optional comment
            should_share: Whether to share in public channel
        """
        with get_session() as session:
            # Create feedback
            feedback = Feedback(
                booking_id=booking_id,
                rating=rating,
                comment=comment,
                posted_to_channel=should_share
            )
            session.add(feedback)
            session.commit()

            # If should share, post in feedback channel
            if should_share and config.FEEDBACK_CHANNEL_ID:
                guild = self.bot.get_guild(config.GUILD_ID)
                if guild:
                    feedback_channel = guild.get_channel(config.FEEDBACK_CHANNEL_ID)
                    if feedback_channel:
                        # Get booking and client info
                        booking = session.query(Booking).filter_by(id=booking_id).first()
                        if booking:
                            client = session.query(Client).filter_by(id=booking.client_id).first()
                            if client:
                                # Create feedback embed
                                stars = "⭐" * rating
                                embed = discord.Embed(
                                    title=f"{stars} Nouveau feedback!",
                                    description=comment if comment else "_Pas de commentaire_",
                                    color=config.SUCCESS_COLOR
                                )
                                embed.add_field(
                                    name="Client",
                                    value=client.discord_name,
                                    inline=True
                                )
                                embed.add_field(
                                    name="Date de la session",
                                    value=booking.scheduled_at.strftime("%d/%m/%Y"),
                                    inline=True
                                )
                                embed.timestamp = datetime.utcnow()

                                try:
                                    await feedback_channel.send(embed=embed)
                                except discord.Forbidden:
                                    print(f"❌ Cannot send to feedback channel")

        print(f"✅ Saved feedback for booking {booking_id}: {rating}/5 stars")


async def setup(bot):
    """
    Setup function to add the cog to the bot
    """
    await bot.add_cog(FeedbackCog(bot))
