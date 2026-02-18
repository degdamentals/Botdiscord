"""
Analytics Cog - Global statistics and data export for coaches
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import csv
import io
import config
from database import get_session, Booking, Client, Feedback
from utils.embeds import create_error_embed
from utils.permissions import is_coach


class Analytics(commands.Cog):
    """
    Cog for global analytics and data export
    """

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        print("📈 Analytics cog loaded")

    @app_commands.command(name="analytics", description="[Coach] Voir les statistiques globales du coaching")
    @app_commands.describe(period="Période à analyser")
    @app_commands.choices(period=[
        app_commands.Choice(name="Cette semaine", value="week"),
        app_commands.Choice(name="Ce mois", value="month"),
        app_commands.Choice(name="Les 3 derniers mois", value="quarter"),
        app_commands.Choice(name="Tout le temps", value="all"),
    ])
    async def analytics(self, interaction: discord.Interaction, period: str = "month"):
        """
        Display global coaching analytics
        """
        if not is_coach(interaction.user) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed("Vous devez être coach pour utiliser cette commande."),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        now = datetime.now(config.TIMEZONE)

        if period == "week":
            start_date = now - timedelta(weeks=1)
            period_label = "Cette semaine"
        elif period == "month":
            start_date = now - timedelta(days=30)
            period_label = "Ce mois (30 jours)"
        elif period == "quarter":
            start_date = now - timedelta(days=90)
            period_label = "Les 3 derniers mois"
        else:
            start_date = None
            period_label = "Tout le temps"

        with get_session() as session:
            # Base query
            query = session.query(Booking)
            if start_date:
                query = query.filter(Booking.created_at >= start_date)

            all_bookings = query.all()

            # Session counts
            total = len(all_bookings)
            completed = len([b for b in all_bookings if b.status == config.STATUS_COMPLETED])
            confirmed = len([b for b in all_bookings if b.status == config.STATUS_CONFIRMED])
            cancelled = len([b for b in all_bookings if b.status == config.STATUS_CANCELLED])
            no_shows = len([b for b in all_bookings if b.status == config.STATUS_NO_SHOW])
            pending = len([b for b in all_bookings if b.status == "pending_schedule"])

            free_sessions = len([b for b in all_bookings if b.booking_type == config.BOOKING_TYPE_FREE])
            paid_sessions = len([b for b in all_bookings if b.booking_type == config.BOOKING_TYPE_PAID])

            # Rates
            completion_rate = (completed / total * 100) if total > 0 else 0
            no_show_rate = (no_shows / total * 100) if total > 0 else 0
            cancellation_rate = (cancelled / total * 100) if total > 0 else 0

            # Active clients (with at least 1 booking in period)
            client_ids = set(b.client_id for b in all_bookings)
            active_clients = len(client_ids)

            # New clients in period
            if start_date:
                new_clients = session.query(Client).filter(Client.created_at >= start_date).count()
            else:
                new_clients = session.query(Client).count()

            # Total hours coached
            completed_bookings = [b for b in all_bookings if b.status == config.STATUS_COMPLETED]
            total_minutes = sum(b.duration_minutes for b in completed_bookings)
            total_hours = total_minutes / 60

            # Feedback stats
            feedback_query = session.query(Feedback)
            if start_date:
                feedback_query = feedback_query.join(Booking).filter(Booking.created_at >= start_date)
            feedbacks = feedback_query.all()
            avg_rating = sum(f.rating for f in feedbacks) / len(feedbacks) if feedbacks else 0

            # Upcoming sessions this week
            week_from_now = now + timedelta(weeks=1)
            upcoming_week = [
                b for b in session.query(Booking).filter(
                    Booking.status == config.STATUS_CONFIRMED,
                    Booking.scheduled_at >= now,
                    Booking.scheduled_at <= week_from_now
                ).all()
            ]

            # Top clients (most sessions)
            client_session_counts = {}
            for b in all_bookings:
                if b.status in [config.STATUS_CONFIRMED, config.STATUS_COMPLETED]:
                    client_session_counts[b.client_id] = client_session_counts.get(b.client_id, 0) + 1

            top_client_ids = sorted(client_session_counts, key=client_session_counts.get, reverse=True)[:3]
            top_clients_text = ""
            for cid in top_client_ids:
                client = session.query(Client).filter_by(id=cid).first()
                if client:
                    count = client_session_counts[cid]
                    top_clients_text += f"• **{client.discord_name}** — {count} séance(s)\n"

        # Build embed
        embed = discord.Embed(
            title=f"📈 Analytics — {period_label}",
            color=config.BOT_COLOR
        )

        embed.add_field(
            name="📊 Sessions",
            value=(
                f"**Total:** {total}\n"
                f"✅ Complétées: **{completed}**\n"
                f"⏳ Confirmées (à venir): **{confirmed}**\n"
                f"📋 À planifier (packs): **{pending}**\n"
                f"❌ Annulées: **{cancelled}**\n"
                f"👻 No-show: **{no_shows}**"
            ),
            inline=True
        )

        embed.add_field(
            name="📉 Taux",
            value=(
                f"✅ Complétion: **{completion_rate:.1f}%**\n"
                f"❌ Annulation: **{cancellation_rate:.1f}%**\n"
                f"👻 No-show: **{no_show_rate:.1f}%**"
            ),
            inline=True
        )

        embed.add_field(
            name="💰 Types",
            value=(
                f"🆓 Gratuit: **{free_sessions}**\n"
                f"💰 Payant: **{paid_sessions}**"
            ),
            inline=True
        )

        embed.add_field(
            name="👥 Clients",
            value=(
                f"Actifs: **{active_clients}**\n"
                f"Nouveaux: **{new_clients}**"
            ),
            inline=True
        )

        embed.add_field(
            name="⏱️ Heures coachées",
            value=f"**{total_hours:.1f}h** ({total_minutes} min)",
            inline=True
        )

        stars = "⭐" * round(avg_rating) if avg_rating > 0 else "—"
        embed.add_field(
            name="⭐ Satisfaction",
            value=f"{stars}\n**{avg_rating:.1f}/5** ({len(feedbacks)} avis)" if feedbacks else "Aucun avis",
            inline=True
        )

        if upcoming_week:
            upcoming_text = ""
            for b in upcoming_week[:5]:
                scheduled = b.scheduled_at
                if scheduled.tzinfo is None:
                    scheduled = config.TIMEZONE.localize(scheduled)
                type_emoji = "🆓" if b.booking_type == config.BOOKING_TYPE_FREE else "💰"
                upcoming_text += f"{type_emoji} {scheduled.strftime('%d/%m à %H:%M')}\n"
            if len(upcoming_week) > 5:
                upcoming_text += f"_+{len(upcoming_week) - 5} autres..._"
            embed.add_field(name=f"📅 Cette semaine ({len(upcoming_week)} sessions)", value=upcoming_text, inline=False)

        if top_clients_text:
            embed.add_field(name="🏆 Top clients", value=top_clients_text, inline=False)

        embed.set_footer(text=f"Données au {now.strftime('%d/%m/%Y à %H:%M')}")
        embed.timestamp = datetime.utcnow()

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="export", description="[Coach] Exporter les données de réservations en CSV")
    @app_commands.describe(period="Période à exporter")
    @app_commands.choices(period=[
        app_commands.Choice(name="Ce mois", value="month"),
        app_commands.Choice(name="Les 3 derniers mois", value="quarter"),
        app_commands.Choice(name="Tout le temps", value="all"),
    ])
    async def export(self, interaction: discord.Interaction, period: str = "month"):
        """
        Export bookings data as CSV file
        """
        if not is_coach(interaction.user) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed("Vous devez être coach pour utiliser cette commande."),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        now = datetime.now(config.TIMEZONE)

        if period == "month":
            start_date = now - timedelta(days=30)
            period_label = "30_jours"
        elif period == "quarter":
            start_date = now - timedelta(days=90)
            period_label = "3_mois"
        else:
            start_date = None
            period_label = "tout"

        with get_session() as session:
            query = session.query(Booking).join(Client)
            if start_date:
                query = query.filter(Booking.created_at >= start_date)
            bookings = query.order_by(Booking.scheduled_at.desc()).all()

            if not bookings:
                await interaction.followup.send(
                    embed=create_error_embed("Aucune donnée à exporter pour cette période."),
                    ephemeral=True
                )
                return

            # Build CSV in memory
            output = io.StringIO()
            writer = csv.writer(output, delimiter=';')

            writer.writerow([
                "ID", "Client", "Discord ID", "Type", "Statut",
                "Date session", "Durée (min)", "Date création", "Notes"
            ])

            for b in bookings:
                client = session.query(Client).filter_by(id=b.client_id).first()
                scheduled = b.scheduled_at
                if scheduled.tzinfo is None:
                    scheduled = config.TIMEZONE.localize(scheduled)

                writer.writerow([
                    b.id,
                    client.discord_name if client else "Inconnu",
                    client.discord_id if client else "",
                    b.booking_type,
                    b.status,
                    scheduled.strftime("%d/%m/%Y %H:%M"),
                    b.duration_minutes,
                    b.created_at.strftime("%d/%m/%Y %H:%M"),
                    (b.notes or "").replace("\n", " ")
                ])

            output.seek(0)
            csv_bytes = output.getvalue().encode("utf-8-sig")  # utf-8-sig for Excel compatibility
            file = discord.File(
                fp=io.BytesIO(csv_bytes),
                filename=f"reservations_{period_label}_{now.strftime('%Y%m%d')}.csv"
            )

        await interaction.followup.send(
            content=f"📊 Export de **{len(bookings)}** réservation(s) — période: **{period_label.replace('_', ' ')}**",
            file=file,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Analytics(bot))
