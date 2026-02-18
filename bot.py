"""
Deg Bot - Discord Bot for Coaching Management
Main entry point
"""
import discord
from discord.ext import commands
import asyncio
import sys
import traceback
import config
from database import init_db

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Create bot instance
bot = commands.Bot(
    command_prefix=config.BOT_PREFIX,
    intents=intents,
    help_command=None  # We'll create a custom help command
)

# List of cogs to load
COGS = [
    'cogs.tickets',
    'cogs.reminders',
    'cogs.feedback',
    'cogs.admin',
    'cogs.stats',
    'cogs.analytics',
    # 'cogs.calendar_sync',
    # 'cogs.events',
]


@bot.event
async def on_ready():
    """
    Called when the bot is ready and connected to Discord
    """
    print(f'\n{"-" * 50}')
    print(f'Bot connecté en tant que: {bot.user.name} (ID: {bot.user.id})')
    print(f'discord.py version: {discord.__version__}')
    print(f'{"-" * 50}\n')

    # Set bot status
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="vos réservations | /help"
    )
    await bot.change_presence(activity=activity)

    print(f'Serveurs: {len(bot.guilds)}')
    for guild in bot.guilds:
        print(f'  - {guild.name} (ID: {guild.id})')

    # Sync commands with Discord
    try:
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f'✅ Commandes synchronisées pour le serveur {config.GUILD_ID}')
        else:
            await bot.tree.sync()
            print('✅ Commandes synchronisées globalement')
    except Exception as e:
        print(f'❌ Erreur lors de la synchronisation des commandes: {e}')

    print(f'\nBot prêt! 🚀\n')


@bot.event
async def on_command_error(ctx, error):
    """
    Global error handler for commands
    """
    # Ignore command not found errors
    if isinstance(error, commands.CommandNotFound):
        return

    # Check failures (permissions)
    if isinstance(error, commands.CheckFailure):
        await ctx.send(str(error), ephemeral=True)
        return

    # Missing required argument
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"❌ Argument manquant: `{error.param.name}`\n"
            f"Utilisez `/help {ctx.command.name}` pour plus d'informations.",
            ephemeral=True
        )
        return

    # User input errors
    if isinstance(error, (commands.BadArgument, commands.BadUnionArgument)):
        await ctx.send(
            f"❌ Argument invalide.\n"
            f"Utilisez `/help {ctx.command.name}` pour plus d'informations.",
            ephemeral=True
        )
        return

    # Command on cooldown
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            f"⏰ Cette commande est en cooldown. Réessayez dans {error.retry_after:.1f} secondes.",
            ephemeral=True
        )
        return

    # Log unexpected errors
    print(f'\n{"=" * 50}')
    print(f'Erreur dans la commande {ctx.command}:')
    print(f'{"=" * 50}')
    traceback.print_exception(type(error), error, error.__traceback__)
    print(f'{"=" * 50}\n')

    # Inform user
    await ctx.send(
        "❌ Une erreur inattendue s'est produite. L'erreur a été enregistrée.",
        ephemeral=True
    )


@bot.event
async def on_application_command_error(ctx, error):
    """
    Global error handler for application commands (slash commands)
    """
    await on_command_error(ctx, error)


async def load_cogs():
    """
    Load all cogs
    """
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f'✅ Cog chargé: {cog}')
        except Exception as e:
            print(f'❌ Erreur lors du chargement de {cog}:')
            traceback.print_exception(type(e), e, e.__traceback__)


async def main():
    """
    Main async function to start the bot
    """
    # Validate configuration
    try:
        config.validate_config()
    except ValueError as e:
        print(f"\n❌ Erreur de configuration:\n{e}\n")
        sys.exit(1)

    # Initialize database
    try:
        init_db()
        print("✅ Base de données initialisée\n")
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la base de données:")
        traceback.print_exception(type(e), e, e.__traceback__)
        sys.exit(1)

    # Load cogs
    async with bot:
        await load_cogs()

        # Start the bot
        try:
            await bot.start(config.DISCORD_TOKEN)
        except discord.LoginFailure:
            print("\n❌ Token Discord invalide. Vérifiez votre fichier .env\n")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Erreur lors du démarrage du bot:")
            traceback.print_exception(type(e), e, e.__traceback__)
            sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt du bot...\n")
        sys.exit(0)
