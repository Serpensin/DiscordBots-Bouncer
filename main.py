#Import
import time
startupTime_start = time.time()
import aiohttp
import asyncio
import datetime
import discord
import io
import json
import jsonschema
import os
import platform
import psutil
import random
import sentry_sdk
import signal
import sqlite3
import string
import sys
from aiohttp import web
from captcha.image import ImageCaptcha
from CustomModules import log_handler
from dotenv import load_dotenv
from pytimeparse.timeparse import timeparse
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile



#Init
discord.VoiceClient.warn_nacl = False
load_dotenv()
image_captcha = ImageCaptcha()
APP_FOLDER_NAME = 'Bouncer'
BOT_NAME = 'Bouncer'
if not os.path.exists(f'{APP_FOLDER_NAME}//Logs'):
    os.makedirs(f'{APP_FOLDER_NAME}//Logs')
if not os.path.exists(f'{APP_FOLDER_NAME}//Buffer'):
    os.makedirs(f'{APP_FOLDER_NAME}//Buffer')
LOG_FOLDER = f'{APP_FOLDER_NAME}//Logs//'
BUFFER_FOLDER = f'{APP_FOLDER_NAME}//Buffer//'
ACTIVITY_FILE = os.path.join(APP_FOLDER_NAME, 'activity.json')
DB_FILE = os.path.join(APP_FOLDER_NAME, f'{BOT_NAME}.db')
BOT_VERSION = "1.4.6"

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    environment='Production',
    release=f'{BOT_NAME}@{BOT_VERSION}'
)

#Load env
TOKEN = os.getenv('TOKEN')
OWNERID = os.getenv('OWNER_ID')
support_id = os.getenv('SUPPORT_SERVER')
topgg_token = os.getenv('TOPGG_TOKEN')
discordlist_token = os.getenv('DISCORDLIST_TOKEN')
discordbots_token = os.getenv('DISCORDBOTS_TOKEN')
discordbotlistcom_token = os.getenv('DISCORDBOTLIST_TOKEN')
discordbotlisteu_token = os.getenv('DISCORDBOTLISTEU_TOKEN')
discords_token = os.getenv('DISCORDS_TOKEN')
LOG_LEVEL = os.getenv('LOG_LEVEL')

#Logger init
log_manager = log_handler.LogManager(LOG_FOLDER, APP_FOLDER_NAME, LOG_LEVEL)
discord_logger = log_manager.get_logger('discord')
program_logger = log_manager.get_logger('Program')
program_logger.info('Engine powering up...')


#Create activity.json if not exists
class JSONValidator:
    schema = {
        "type" : "object",
        "properties" : {
            "activity_type" : {
                "type" : "string",
                "enum" : ["Playing", "Streaming", "Listening", "Watching", "Competing"]
            },
            "activity_title" : {"type" : "string"},
            "activity_url" : {"type" : "string"},
            "status" : {
                "type" : "string",
                "enum" : ["online", "idle", "dnd", "invisible"]
            },
        },
    }

    default_content = {
        "activity_type": "Playing",
        "activity_title": "Made by Serpensin: https://gitlab.bloodygang.com/Serpensin",
        "activity_url": "",
        "status": "online"
    }

    def __init__(self, file_path):
        self.file_path = file_path

    def validate_and_fix_json(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as file:
                try:
                    data = json.load(file)
                    jsonschema.validate(instance=data, schema=self.schema)  # validate the data
                except jsonschema.exceptions.ValidationError as ve:
                    program_logger.debug(f'ValidationError: {ve}')
                    self.write_default_content()
                except json.decoder.JSONDecodeError as jde:
                    program_logger.debug(f'JSONDecodeError: {jde}')
                    self.write_default_content()
        else:
            self.write_default_content()

    def write_default_content(self):
        with open(self.file_path, 'w') as file:
            json.dump(self.default_content, file, indent=4)
validator = JSONValidator(ACTIVITY_FILE)
validator.validate_and_fix_json()


#Bot Class
class aclient(discord.AutoShardedClient):
    def __init__(self):

        intents = discord.Intents.default()
        intents.members = True

        super().__init__(owner_id = OWNERID,
                          intents = intents,
                          status = discord.Status.invisible,
                          auto_reconnect = True
                        )

        self.synced = False
        self.db_conns = {}
        self.captcha_timeout = []
        self.initialized = False


    class Presence():
        @staticmethod
        def get_activity() -> discord.Activity:
            with open(ACTIVITY_FILE) as f:
                data = json.load(f)
                activity_type = data['activity_type']
                activity_title = data['activity_title']
                activity_url = data['activity_url']
            if activity_type == 'Playing':
                return discord.Game(name=activity_title)
            elif activity_type == 'Streaming':
                return discord.Streaming(name=activity_title, url=activity_url)
            elif activity_type == 'Listening':
                return discord.Activity(type=discord.ActivityType.listening, name=activity_title)
            elif activity_type == 'Watching':
                return discord.Activity(type=discord.ActivityType.watching, name=activity_title)
            elif activity_type == 'Competing':
                return discord.Activity(type=discord.ActivityType.competing, name=activity_title)

        @staticmethod
        def get_status() -> discord.Status:
            with open(ACTIVITY_FILE) as f:
                data = json.load(f)
                status = data['status']
            if status == 'online':
                return discord.Status.online
            elif status == 'idle':
                return discord.Status.idle
            elif status == 'dnd':
                return discord.Status.dnd
            elif status == 'invisible':
                return discord.Status.invisible


    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        options = interaction.data.get("options")
        option_values = ""
        if options:
            for option in options:
                option_values += f"{option['name']}: {option['value']}"
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            try:
                await interaction.response.send_message(f'This command is on cooldown.\nTime left: `{str(datetime.timedelta(seconds=int(error.retry_after)))}`', ephemeral=True)
            except discord.errors.NotFound:
                pass
        else:
            try:
                try:
                    await interaction.response.send_message(f"Error! Try again.", ephemeral=True)
                except:
                    try:
                        await interaction.followup.send(f"Error! Try again.", ephemeral=True)
                    except:
                        pass
            except discord.Forbidden:
                try:
                    await interaction.followup.send(f"{error}\n\n{option_values}", ephemeral=True)
                except discord.NotFound:
                    try:
                        await interaction.response.send_message(f"{error}\n\n{option_values}", ephemeral=True)
                    except discord.NotFound:
                        pass
                except Exception as e:
                    discord_logger.warning(f"Unexpected error while sending message: {e}")
            finally:
                try:
                    program_logger.warning(f"{error} -> {option_values} | Invoked by {interaction.user.name} ({interaction.user.id}) @ {interaction.guild.name} ({interaction.guild.id}) with Language {interaction.locale[1]}")
                except AttributeError:
                    program_logger.warning(f"{error} -> {option_values} | Invoked by {interaction.user.name} ({interaction.user.id}) with Language {interaction.locale[1]}")
                sentry_sdk.capture_exception(error)


    async def on_guild_join(self, guild):
        if not self.initialized:
            return
        discord_logger.info(f'I joined {guild}. (ID: {guild.id})')


    async def on_guild_remove(self, guild):
        if not self.initialized:
            return
        discord_logger.info(f'I got kicked from {guild}. (ID: {guild.id})')


    async def on_member_join(self, member: discord.Member):
        def account_age_in_seconds(member: discord.Member) -> int:
            now = datetime.datetime.now(datetime.UTC)
            created = member.created_at
            age = now - created
            return age.total_seconds()

        if not self.initialized:
            return
        if member.bot:
            return
        #Fetch account_age_min from DB and kick user if account age is less than account_age_min
        c.execute('SELECT account_age_min FROM servers WHERE guild_id = ?', (member.guild.id,))
        result = c.fetchone()
        if result is None or result[0] is None:
            return
        account_age_min = result[0]
        if account_age_in_seconds(member) < account_age_min:
            try:
                await member.kick(reason=f'Account age is less than {Functions.format_seconds(account_age_min)}.')
                await Functions.send_logging_message(member = member, kind = 'account_too_young')
                return
            except discord.Forbidden:
                return
        else:
            program_logger.debug(f'Account age is greater than {Functions.format_seconds(account_age_min)}.')

        c.execute('SELECT action FROM servers WHERE guild_id = ?', (member.guild.id,))
        result = c.fetchone()
        if result is None or result[0] is None:
            return
        c.execute('INSERT INTO processing_joined VALUES (?, ?, ?)', (member.guild.id, member.id, int(time.time(),)))
        conn.commit()


    async def on_member_remove(self, member: discord.Member):
        if not self.initialized:
            return
        c.execute('DELETE FROM processing_joined WHERE guild_id = ? AND user_id = ?', (member.guild.id, member.id,))
        conn.commit()


    async def on_interaction(self, interaction: discord.Interaction):
        if not self.initialized:
            return
        class WhyView(discord.ui.View):
            def __init__(self, *, timeout=None):
                super().__init__(timeout=timeout)

                self.add_item(discord.ui.Button(label='Secure your server', url = f'https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=268503046&scope=bot%20applications.commands', style=discord.ButtonStyle.link))


        if interaction.data and interaction.data.get('component_type') == 2:  # 2 is the component type for button
            button_id = interaction.data.get('custom_id')

            if button_id == 'verify':
                if interaction.user.id in bot.captcha_timeout:
                    try:
                        await interaction.response.send_message('Please wait a few seconds before trying again.', ephemeral=True)
                    except discord.NotFound:
                        try:
                            await interaction.followup.send('Please wait a few seconds before trying again.', ephemeral=True)
                        except discord.NotFound:
                            pass
                    return
                else:
                    await Functions.verify(interaction)
                    return
            elif button_id == 'why':
                try:
                    await interaction.response.send_message(f'This serever is protected by <@!{bot.user.id}> to prevent raids & malicious users.\n\nTo gain access to this server, you\'ll need to verify yourself by completing a captcha.\n\nYou don\'t need to connect your account for that.', view = WhyView(), ephemeral=True)
                except discord.NotFound:
                    try:
                        await interaction.followup.send(f'This serever is protected by <@!{bot.user.id}> to prevent raids & malicious users.\n\nTo gain access to this server, you\'ll need to verify yourself by completing a captcha.\n\nYou don\'t need to connect your account for that.', view = WhyView(), ephemeral=True)
                    except discord.NotFound:
                        pass


    async def setup_database(self, shard_id):
        def column_exists(conn, table, column_name):
            c = conn.cursor()
            c.execute(f'PRAGMA table_info({table})')
            for col in c.fetchall():
                if col[1] == column_name:
                    return True
            return False

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.executescript('''
            CREATE TABLE IF NOT EXISTS servers (
                guild_id INTEGER PRIMARY KEY,
                verify_channel INTEGER,
                verify_role INTEGER,
                log_channel INTEGER,
                timeout INTEGER,
                action TEXT,
                ban_time INTEGER
            );

            CREATE TABLE IF NOT EXISTS panels (
                guild_id INTEGER PRIMARY KEY,
                panel_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS temp_bans (
                guild_id INTEGER,
                user_id INTEGER,
                unban_time INTEGER
            );

            CREATE TABLE IF NOT EXISTS processing_joined (
                guild_id INTEGER,
                user_id INTEGER,
                join_time INTEGER
            )
        ''')
        if not column_exists(conn, 'servers', 'account_age_min'):
            c.execute('ALTER TABLE servers ADD COLUMN account_age_min INTEGER')
        self.db_conns[shard_id] = conn


    async def on_message(self, message):
        async def __wrong_selection():
            await message.channel.send('```'
                                       'Commands:\n'
                                       'help - Shows this message\n'
                                       'log - Get the log\n'
                                       'activity - Set the activity of the bot\n'
                                       'status - Set the status of the bot\n'
                                       'shutdown - Shutdown the bot\n'
                                       '```')

        if message.guild is None and message.author.id == int(OWNERID):
            args = message.content.split(' ')
            program_logger.debug(args)
            command, *args = args
            if command == 'help':
                await __wrong_selection()
                return

            elif command == 'log':
                await Owner.log(message, args)
                return

            elif command == 'activity':
                await Owner.activity(message, args)
                return

            elif command == 'status':
                await Owner.status(message, args)
                return

            elif command == 'shutdown':
                await Owner.shutdown(message)
                return

            else:
                await __wrong_selection()


    async def on_ready(self):
        if self.initialized:
            await bot.change_presence(activity = self.Presence.get_activity(), status = self.Presence.get_status())
            return
        global owner, start_time, conn, c, shutdown
        shard_id = self.shard_info.id if hasattr(self, 'shard_info') else 0
        #SQLite init
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        await self.setup_database(shard_id)

        try:
            owner = await self.fetch_user(OWNERID)
            if owner is None:
                program_logger.critical(f"Invalid ownerID: {OWNERID}")
                sys.exit(f"Invalid ownerID: {OWNERID}")
        except discord.HTTPException as e:
            program_logger.critical(f"Error fetching owner user: {e}")
            sys.exit(f"Error fetching owner user: {e}")
        discord_logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
        if not self.synced:
            program_logger.info('Syncing...')
            await tree.sync()
            program_logger.info('Synced.')
            self.synced = True
            await bot.change_presence(activity = self.Presence.get_activity(), status = self.Presence.get_status())
        start_time = datetime.datetime.now()

        #Start background tasks
        bot.loop.create_task(Functions.process_latest_joined())
        bot.loop.create_task(Functions.check_and_process_temp_bans())
        if topgg_token:
            bot.loop.create_task(update_stats.topgg())
        if discordlist_token:
            bot.loop.create_task(update_stats.discordlist())
        if discordbotlistcom_token:
            bot.loop.create_task(update_stats.discordbotlist_com())
        if discords_token:
            bot.loop.create_task(update_stats.discords())
        if discordbotlisteu_token:
            bot.loop.create_task(update_stats.discordbotlist_eu())
        if discordbots_token:
            bot.loop.create_task(update_stats.discordbots())
        bot.loop.create_task(Functions.health_server())

        shutdown = False
        self.initialized = True
        program_logger.info('All systems online...')
        clear()
        program_logger.info(f"Initialization completed in {time.time() - startupTime_start} seconds.")


    async def on_disconnect(self):
        shard_id = self.shard_info.id if hasattr(self, 'shard_info') else 0
        conn = self.db_conns.pop(shard_id, None)
        if conn:
            conn.close()
bot = aclient()
tree = discord.app_commands.CommandTree(bot)
tree.on_error = bot.on_app_command_error


class SignalHandler:
    def __init__(self):
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        program_logger.info('Received signal to shutdown...')
        program_logger.debug('Received signal to shutdown...')
        bot.loop.create_task(Owner.shutdown(owner))


# Check if all required variables are set
support_available = bool(support_id)

#Fix error on windows on shutdown
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
def clear():
    if platform.system() == 'Windows':
        os.system('cls')
    else:
        os.system('clear')



#Update botstats on websites
class update_stats():
    async def topgg():
        headers = {
            'Authorization': topgg_token,
            'Content-Type': 'application/json'
        }
        while not shutdown:
            async with aiohttp.ClientSession() as session:
                async with session.post(f'https://top.gg/api/bots/{bot.user.id}/stats', headers=headers, json={'server_count': len(bot.guilds), 'shard_count': len(bot.shards)}) as resp:
                    if resp.status != 200:
                        program_logger.error(f'Failed to update top.gg: {resp.status} {resp.reason}')
            try:
                await asyncio.sleep(60*30)
            except asyncio.CancelledError:
                pass

    async def discordlist():
        headers = {
            'Authorization': f'Bearer {discordlist_token}',
            'Content-Type': 'application/json; charset=utf-8'
        }
        while not shutdown:
            async with aiohttp.ClientSession() as session:
                async with session.post(f'https://api.discordlist.gg/v0/bots/{bot.user.id}/guilds', headers=headers, json={"count": len(bot.guilds)}) as resp:
                    if resp.status != 200:
                        program_logger.error(f'Failed to update discordlist.gg: {resp.status} {resp.reason}')
            try:
                await asyncio.sleep(60*30)
            except asyncio.CancelledError:
                pass

    async def discordbots():
        headers = {
            'Authorization': discordbots_token,
            'Content-Type': 'application/json'
        }
        while not shutdown:
            async with aiohttp.ClientSession() as session:
                async with session.post(f'https://discord.bots.gg/api/v1/bots/{bot.user.id}/stats', headers=headers, json={'guildCount': len(bot.guilds), 'shardCount': len(bot.shards)}) as resp:
                    if resp.status != 200:
                        program_logger.error(f'Failed to update discord.bots.gg: {resp.status} {resp.reason}')
            try:
                await asyncio.sleep(60*30)
            except asyncio.CancelledError:
                pass

    async def discordbotlist_com():
        headers = {
            'Authorization': discordbotlistcom_token,
            'Content-Type': 'application/json'
        }
        while not shutdown:
            async with aiohttp.ClientSession() as session:
                async with session.post(f'https://discordbotlist.com/api/v1/bots/{bot.user.id}/stats', headers=headers, json={'guilds': len(bot.guilds), 'users': sum(guild.member_count for guild in bot.guilds)}) as resp:
                    if resp.status != 200:
                        program_logger.error(f'Failed to update discordbotlist.com: {resp.status} {resp.reason}')
            try:
                await asyncio.sleep(60*30)
            except asyncio.CancelledError:
                pass

    async def discords():
        headers = {
            'Authorization': discords_token,
            'Content-Type': 'application/json'
        }
        while not shutdown:
            async with aiohttp.ClientSession() as session:
                async with session.post(f'https://discords.com/bots/api/bot/{bot.user.id}', headers=headers, json={"server_count": len(bot.guilds)}) as resp:
                    if resp.status != 200:
                        program_logger.error(f'Failed to update discords.com: {resp.status} {resp.reason}')
            try:
                await asyncio.sleep(60*30)
            except asyncio.CancelledError:
                pass

    async def discordbotlist_eu():
        headers = {
            'Authorization': f'Bearer {discordbotlisteu_token}',
            'Content-Type': 'application/json; charset=utf-8'
        }
        while not shutdown:
            async with aiohttp.ClientSession() as session:
                async with session.patch(f'https://api.discord-botlist.eu/v1/update', headers=headers, json={"serverCount": len(bot.guilds)}) as resp:
                    if resp.status != 200:
                        program_logger.error(f'Failed to update discordlist.gg: {resp.status} {resp.reason}')
            try:
                await asyncio.sleep(60*30)
            except asyncio.CancelledError:
                pass



#Functions
class Functions():
    async def health_server():
        async def __health_check(request):
            return web.Response(text="Healthy")

        app = web.Application()
        app.router.add_get('/health', __health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 5000)
        await site.start()

    def create_captcha():
        captcha_text = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        data = image_captcha.generate(captcha_text)
        return io.BytesIO(data.read()), captcha_text

    async def create_support_invite(interaction: discord.Interaction):
        try:
            guild = bot.get_guild(int(support_id))
        except ValueError:
            return "Could not find support guild."
        if guild is None:
            return "Could not find support guild."
        if not guild.text_channels:
            return "Support guild has no text channels."
        try:
            member = await guild.fetch_member(interaction.user.id)
        except discord.NotFound:
            member = None
        if member is not None:
            return "You are already in the support guild."
        channels: discord.TextChannel = guild.text_channels
        for channel in channels:
            try:
                invite: discord.Invite = await channel.create_invite(
                    reason=f"Created invite for {interaction.user.name} from server {interaction.guild.name} ({interaction.guild_id})",
                    max_age=60,
                    max_uses=1,
                    unique=True
                )
                return invite.url
            except discord.Forbidden:
                continue
            except discord.HTTPException:
                continue
        return "Could not create invite. There is either no text-channel, or I don't have the rights to create an invite."

    async def verify(interaction: discord.Interaction):
        class CaptchaInput(discord.ui.Modal, title = 'Verification'):
            def __init__(self):
                super().__init__()
                self.verification_successful = False

            answer = discord.ui.TextInput(label = 'Please enter the captcha text:', placeholder = 'Captcha text', min_length = 6, max_length = 6, style = discord.TextStyle.short, required = True)

            async def on_submit(self, interaction: discord.Interaction):
                if self.answer.value.upper() == captcha_text:
                    try:
                        await interaction.user.add_roles(interaction.guild.get_role(int(verified_role_id)))
                        await Functions.send_logging_message(interaction = interaction, kind = 'verify_success')
                        await interaction.response.edit_message(content = 'You have successfully verified yourself.', view = None)
                        c.execute('DELETE FROM processing_joined WHERE guild_id = ? AND user_id = ?', (interaction.guild.id, interaction.user.id,))
                        conn.commit()
                    except discord.Forbidden:
                        await interaction.response.edit_message(content = 'I do not have the permission to add the verified role.', view = None)
                    except discord.errors.NotFound:
                        pass
                    if interaction.user.id in bot.captcha_timeout:
                        bot.captcha_timeout.remove(interaction.user.id)
                    self.verification_successful = True
                else:
                    await Functions.send_logging_message(interaction = interaction, kind = 'verify_fail')
                    await interaction.response.edit_message(content = 'The captcha text you entered is incorrect.', view = None)


        captcha_input = CaptchaInput()


        class SubmitButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label='Enter Captcha', custom_id='captcha_submit', style=discord.ButtonStyle.blurple)

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.send_modal(captcha_input)


        class SubmitView(discord.ui.View):
            def __init__(self, *, timeout=60):
                super().__init__(timeout=timeout)
                self.add_item(SubmitButton())

            async def on_timeout(self):
                if not captcha_input.verification_successful:
                    self.remove_item(SubmitButton())
                    await interaction.edit_original_response(content = 'Captcha timed out. Request a new one.', view = None)
                    if interaction.user.id in bot.captcha_timeout:
                        bot.captcha_timeout.remove(interaction.user.id)


        #Load verify_role from db
        c.execute(f'SELECT verify_role FROM servers WHERE guild_id = {interaction.guild_id}')
        try:
            verified_role_id = c.fetchone()[0]
        except TypeError:
            await interaction.response.send_message('No verified role set. Please contact the server administrator.', ephemeral = True)
            return

        #Test if user allready has the role
        if interaction.guild.get_role(int(verified_role_id)) in interaction.user.roles:
            await interaction.response.send_message('You are already verified.', ephemeral = True)
            return

        await Functions.send_logging_message(interaction = interaction, kind = 'verify_start')
        captcha = Functions.create_captcha()
        captcha_picture = discord.File(captcha[0], filename = 'captcha.png')
        captcha_text = captcha[1]

        bot.captcha_timeout.append(interaction.user.id)
        await interaction.response.send_message(f'Please verify yourself to gain access to this server.\n\n**Captcha:**', file = captcha_picture, view = SubmitView(), ephemeral = True)

    async def process_latest_joined():
        while not shutdown:
            for guild in bot.guilds:
                try:
                    c.execute('SELECT * FROM servers WHERE guild_id = ?', (guild.id,))
                    server = c.fetchone()
                    if server is None:
                        continue
                    timeout = server[4]
                    verified_role_id = server[2]
                    action = server[5]
                    ban_time = server[6]
                    c.execute('SELECT * FROM processing_joined WHERE guild_id = ? AND (join_time + ?) < ?', (guild.id, timeout, int(time.time())))
                    rows = c.fetchall()
                    for row in rows:
                        guild = bot.get_guild(row[0])
                        if guild is None:
                            c.execute('DELETE FROM processing_joined WHERE guild_id = ?', (row[0],))
                            continue
                        member = guild.get_member(row[1])
                        if member is None:
                            try:
                                member = await guild.fetch_member(row[1])
                                if member is None:
                                    c.execute('DELETE FROM processing_joined WHERE guild_id = ? AND user_id = ?', (row[0], row[1]))
                                    continue
                            except discord.NotFound:
                                c.execute('DELETE FROM processing_joined WHERE guild_id = ? AND user_id = ?', (row[0], row[1]))
                                continue
                        if action is None:
                            continue
                        verified_role = guild.get_role(verified_role_id)
                        if verified_role is None:
                            continue
                        if verified_role not in member.roles:
                            if action == 'kick':
                                try:
                                    await member.kick(reason='Did not successfully verify in time.')
                                    await Functions.send_logging_message(member = member, kind = 'verify_kick')
                                    program_logger.debug(f'Kicked {member.name}#{member.discriminator} ({member.id}) from {guild.name} ({guild.id}).')
                                except discord.Forbidden:
                                    program_logger.debug(f'Could not kick {member.name}#{member.discriminator} ({member.id}) from {guild.name} ({guild.id}).')
                            elif action == 'ban':
                                try:
                                    if ban_time is not None:
                                        await member.ban(reason=f'Did not successfully verify in time. Banned for {Functions.format_seconds(ban_time)}')
                                        c.execute('INSERT INTO temp_bans VALUES (?, ?, ?)', (guild.id, member.id, int(time.time() + ban_time)))
                                    else:
                                        await member.ban(reason=f'Did not successfully verify in time.')
                                    await Functions.send_logging_message(member = member, kind = 'verify_ban')
                                    program_logger.debug(f'Banned {member.name}#{member.discriminator} ({member.id}) from {guild.name} ({guild.id}).')
                                except discord.Forbidden:
                                    program_logger.debug(f'Could not ban {member.name}#{member.discriminator} ({member.id}) from {guild.name} ({guild.id}).')
                        else:
                            c.execute('DELETE FROM processing_joined WHERE guild_id = ? AND user_id = ?', (row[0], row[1]))
                except Exception as e:
                    conn.commit()
                    raise e
            conn.commit()
            try:
                await asyncio.sleep(15)
            except asyncio.CancelledError:
                pass

    async def check_and_process_temp_bans():
        while not shutdown:
            c.execute('SELECT * FROM temp_bans WHERE unban_time < ?', (time.time(),))
            temp_bans = c.fetchall()
            for temp_ban in temp_bans:
                try:
                    guild = bot.get_guild(temp_ban[0])
                    if guild is None:
                        c.execute('DELETE FROM temp_bans WHERE guild_id = ?', (temp_ban[0],))
                        continue
                    member = bot.get_user(temp_ban[1])
                    if member is None:
                        try:
                            member = await bot.fetch_user(temp_ban[1])
                        except discord.NotFound:
                            c.execute('DELETE FROM temp_bans WHERE guild_id = ? AND user_id = ?', (temp_ban[0], temp_ban[1]))
                            continue
                    c.execute('SELECT log_channel FROM servers WHERE guild_id = ?', (guild.id,))
                    log_channel_id = c.fetchone()[0]
                    log_channel = guild.get_channel(int(log_channel_id))
                    if log_channel is None:
                        try:
                            log_channel = await guild.fetch_channel(int(log_channel_id))
                        except:
                            log_channel = None
                    try:
                        await guild.unban(member, reason='Temporary ban expired.')
                        embed = discord.Embed(title = 'Unban', description = f'User {member.mention} was unbanned.', color = discord.Color.green())
                        embed.timestamp = datetime.datetime.now(datetime.UTC)
                        program_logger.debug(f'Unbanned {member.name}#{member.discriminator} ({member.id}) from {guild.name} ({guild.id}).')
                        c.execute('DELETE FROM temp_bans WHERE guild_id = ? AND user_id = ?', (temp_ban[0], temp_ban[1]))
                        if log_channel is not None:
                            try:
                                await log_channel.send(embed = embed)
                            except discord.Forbidden:
                                program_logger.debug(f'Could not send unban log message in {guild.name} ({guild.id}).')
                    except discord.Forbidden:
                        program_logger.debug(f'Could not unban {member.name}#{member.discriminator} ({member.id}) from {guild.name} ({guild.id}).')
                except Exception as e:
                    conn.commit()
                    raise e

            conn.commit()
            try:
                await asyncio.sleep(15)
            except asyncio.CancelledError:
                pass

    async def send_logging_message(interaction: discord.Interaction = None, member: discord.Member = None, kind: str = '', mass_amount: int = 0):
        if interaction is not None:
            c.execute('SELECT * FROM servers WHERE guild_id = ?', (interaction.guild_id,))
            row = c.fetchone()
            log_channel_id = row[3]
            if log_channel_id is None:
                return
            log_channel = interaction.guild.get_channel(int(log_channel_id))
            if log_channel is None:
                return
        elif member is not None:
            c.execute('SELECT * FROM servers WHERE guild_id = ?', (member.guild.id,))
            row = c.fetchone()
            log_channel_id = row[3]
            if log_channel_id is None:
                return
            log_channel = member.guild.get_channel(int(log_channel_id))
            if log_channel is None:
                return
        ban_time = row[6]
        account_age = row[7]

        try:
            if kind == 'verify_start':
                embed = discord.Embed(title = 'Captcha sent', description = f'User {interaction.user.mention} requested a new captcha.', color = discord.Color.blurple())
                embed.timestamp = datetime.datetime.now(datetime.UTC)
                await log_channel.send(embed = embed)
            elif kind == 'verify_success':
                embed = discord.Embed(title = 'Verification successful', description = f'User {interaction.user.mention} successfully verified.', color = discord.Color.green())
                embed.timestamp = datetime.datetime.now(datetime.UTC)
                await log_channel.send(embed = embed)
            elif kind == 'verify_fail':
                embed = discord.Embed(title = 'Wrong captcha', description = f'User {interaction.user.mention} entered a wrong captcha.', color = discord.Color.red())
                embed.timestamp = datetime.datetime.now(datetime.UTC)
                await log_channel.send(embed = embed)
            elif kind == 'verify_kick':
                embed = discord.Embed(title = 'Time limit reached', color = discord.Color.red())
                embed.timestamp = datetime.datetime.now(datetime.UTC)
                embed.add_field(name = 'User', value = member.mention)
                embed.add_field(name = 'Action', value = 'Kick')
                await log_channel.send(embed = embed)
            elif kind == 'verify_ban':
                embed = discord.Embed(title = 'Time limit reached', color = discord.Color.red())
                embed.timestamp = datetime.datetime.now(datetime.UTC)
                embed.add_field(name = 'User', value = member.mention)
                embed.add_field(name = 'Action', value = 'Ban')
                if ban_time is not None:
                    embed.add_field(name = 'Duration', value = f'{Functions.format_seconds(ban_time)}')
                await log_channel.send(embed = embed)
            elif kind == 'verify_mass_started':
                embed = discord.Embed(title = 'Mass verification started', description = f'Mass verification started by {interaction.user.mention}.', color = discord.Color.blurple())
                embed.timestamp = datetime.datetime.now(datetime.UTC)
                await log_channel.send(embed = embed)
            elif kind == 'verify_mass_success':
                embed = discord.Embed(title = 'Mass verification successful', description = f'{interaction.user.mention} successfully applied the verified role to {mass_amount} users.', color = discord.Color.green())
                embed.timestamp = datetime.datetime.now(datetime.UTC)
                await log_channel.send(embed = embed)
            elif kind == 'unban':
                embed = discord.Embed(title = 'Unban', description = f'User {member.mention} was unbanned.', color = discord.Color.green())
                embed.timestamp = datetime.datetime.now(datetime.UTC)
                await log_channel.send(embed = embed)
            elif kind == 'account_too_young':
                embed = discord.Embed(title = 'Account too young', description = f'User {member.mention} was kicked because their account is youger than {Functions.format_seconds(account_age)}.', color = discord.Color.orange())
                embed.timestamp = datetime.datetime.now(datetime.UTC)
                await log_channel.send(embed = embed)
        except discord.errors.Forbidden:
            pass

    def format_seconds(seconds):
        years, remainder = divmod(seconds, 31536000)
        days, remainder = divmod(remainder, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if years:
            parts.append(f"{years}y")
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds:
            parts.append(f"{seconds}s")

        return " ".join(parts)



##Owner Commands
class Owner():
    async def log(message, args):
        async def __wrong_selection():
            await message.channel.send('```'
                                       'log [current/folder/lines] (Replace lines with a positive number, if you only want lines.) - Get the log\n'
                                       '```')

        if args == []:
            await __wrong_selection()
            return
        if args[0] == 'current':
            try:
                await message.channel.send(file=discord.File(r''+LOG_FOLDER+'Bouncer.log'))
            except discord.HTTPException as err:
                if err.status == 413:
                    with ZipFile(BUFFER_FOLDER+'Logs.zip', mode='w', compression=ZIP_DEFLATED, compresslevel=9, allowZip64=True) as f:
                        f.write(LOG_FOLDER+'Bouncer.log')
                    try:
                        await message.channel.send(file=discord.File(r''+BUFFER_FOLDER+'Logs.zip'))
                    except discord.HTTPException as err:
                        if err.status == 413:
                            await message.channel.send("The log is too big to be send directly.\nYou have to look at the log in your server (VPS).")
                    os.remove(BUFFER_FOLDER+'Logs.zip')
                    return
        elif args[0] == 'folder':
            if os.path.exists(BUFFER_FOLDER+'Logs.zip'):
                os.remove(BUFFER_FOLDER+'Logs.zip')
            with ZipFile(BUFFER_FOLDER+'Logs.zip', mode='w', compression=ZIP_DEFLATED, compresslevel=9, allowZip64=True) as f:
                for file in os.listdir(LOG_FOLDER):
                    if file.endswith(".zip"):
                        continue
                    f.write(LOG_FOLDER+file)
            try:
                await message.channel.send(file=discord.File(r''+BUFFER_FOLDER+'Logs.zip'))
            except discord.HTTPException as err:
                if err.status == 413:
                    await message.channel.send("The folder is too big to be send directly.\nPlease get the current file, or the last X lines.")
            os.remove(BUFFER_FOLDER+'Logs.zip')
            return
        else:
            try:
                if int(args[0]) < 1:
                    await __wrong_selection()
                    return
                else:
                    lines = int(args[0])
            except ValueError:
                await __wrong_selection()
                return
            with open(LOG_FOLDER+'Bouncer.log', 'r', encoding='utf8') as f:
                with open(BUFFER_FOLDER+'log-lines.txt', 'w', encoding='utf8') as f2:
                    count = 0
                    for line in (f.readlines()[-lines:]):
                        f2.write(line)
                        count += 1
            await message.channel.send(content = f'Here are the last {count} lines of the current logfile:', file = discord.File(r''+BUFFER_FOLDER+'log-lines.txt'))
            if os.path.exists(BUFFER_FOLDER+'log-lines.txt'):
                os.remove(BUFFER_FOLDER+'log-lines.txt')
            return

    async def activity(message, args):
        async def __wrong_selection():
            await message.channel.send('```'
                                       'activity [playing/streaming/listening/watching/competing] [title] (url) - Set the activity of the bot\n'
                                       '```')
        def isURL(zeichenkette):
            try:
                ergebnis = urlparse(zeichenkette)
                return all([ergebnis.scheme, ergebnis.netloc])
            except:
                return False

        def remove_and_save(liste):
            if liste and isURL(liste[-1]):
                return liste.pop()
            else:
                return None

        if args == []:
            await __wrong_selection()
            return
        action = args[0].lower()
        url = remove_and_save(args[1:])
        title = ' '.join(args[1:])
        program_logger.debug(title)
        program_logger.debug(url)
        with open(ACTIVITY_FILE, 'r', encoding='utf8') as f:
            data = json.load(f)
        if action == 'playing':
            data['activity_type'] = 'Playing'
            data['activity_title'] = title
            data['activity_url'] = ''
        elif action == 'streaming':
            data['activity_type'] = 'Streaming'
            data['activity_title'] = title
            data['activity_url'] = url
        elif action == 'listening':
            data['activity_type'] = 'Listening'
            data['activity_title'] = title
            data['activity_url'] = ''
        elif action == 'watching':
            data['activity_type'] = 'Watching'
            data['activity_title'] = title
            data['activity_url'] = ''
        elif action == 'competing':
            data['activity_type'] = 'Competing'
            data['activity_title'] = title
            data['activity_url'] = ''
        else:
            await __wrong_selection()
            return
        with open(ACTIVITY_FILE, 'w', encoding='utf8') as f:
            json.dump(data, f, indent=2)
        await bot.change_presence(activity = bot.Presence.get_activity(), status = bot.Presence.get_status())
        await message.channel.send(f'Activity set to {action} {title}{" " + url if url else ""}.')

    async def status(message, args):
        async def __wrong_selection():
            await message.channel.send('```'
                                       'status [online/idle/dnd/invisible] - Set the status of the bot\n'
                                       '```')

        if args == []:
            await __wrong_selection()
            return
        action = args[0].lower()
        with open(ACTIVITY_FILE, 'r', encoding='utf8') as f:
            data = json.load(f)
        if action == 'online':
            data['status'] = 'online'
        elif action == 'idle':
            data['status'] = 'idle'
        elif action == 'dnd':
            data['status'] = 'dnd'
        elif action == 'invisible':
            data['status'] = 'invisible'
        else:
            await __wrong_selection()
            return
        with open(ACTIVITY_FILE, 'w', encoding='utf8') as f:
            json.dump(data, f, indent=2)
        await bot.change_presence(activity = bot.Presence.get_activity(), status = bot.Presence.get_status())
        await message.channel.send(f'Status set to {action}.')

    async def shutdown(message):
        global shutdown
        program_logger.info('Engine powering down...')
        try:
            await message.channel.send('Engine powering down...')
        except:
            await owner.send('Engine powering down...')
        await bot.change_presence(status=discord.Status.invisible)
        shutdown = True

        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)

        await bot.close()



##Bot Commands
#Ping
@tree.command(name = 'ping', description = 'Test, if the bot is responding.')
@discord.app_commands.checks.cooldown(1, 30, key=lambda i: (i.user.id))
async def self(interaction: discord.Interaction):
    before = time.monotonic()
    await interaction.response.send_message('Pong!')
    ping = (time.monotonic() - before) * 1000
    await interaction.edit_original_response(content=f'Pong! \nCommand execution time: `{int(ping)}ms`\nPing to gateway: `{int(bot.latency * 1000)}ms`')



#Bot Info
@tree.command(name = 'botinfo', description = 'Get information about the bot.')
@discord.app_commands.checks.cooldown(1, 60, key=lambda i: (i.user.id))
async def self(interaction: discord.Interaction):
        member_count = sum(guild.member_count for guild in bot.guilds)

        embed = discord.Embed(
            title=f"Informationen about {bot.user.name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else '')

        embed.add_field(name="Created at", value=bot.user.created_at.strftime("%d.%m.%Y, %H:%M:%S"), inline=True)
        embed.add_field(name="Version", value=BOT_VERSION, inline=True)
        embed.add_field(name="Uptime", value=str(datetime.timedelta(seconds=int((datetime.datetime.now() - start_time).total_seconds()))), inline=True)

        embed.add_field(name="Owner", value=f"<@!{OWNERID}>", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="Server", value=f"{len(bot.guilds)}", inline=True)
        embed.add_field(name="Member count", value=str(member_count), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="Shards", value=f"{bot.shard_count}", inline=True)
        embed.add_field(name="Shard ID", value=f"{interaction.guild.shard_id if interaction.guild else 'N/A'}", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="Python", value=f"{platform.python_version()}", inline=True)
        embed.add_field(name="discord.py", value=f"{discord.__version__}", inline=True)
        embed.add_field(name="Sentry", value=f"{sentry_sdk.consts.VERSION}", inline=True)

        embed.add_field(name="Repo", value=f"[GitLab](https://gitlab.bloodygang.com/Serpensin/DiscordBots-Bouncer)", inline=True)
        embed.add_field(name="Invite", value=f"[Invite me](https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=67423232&scope=bot)", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        if interaction.user.id == int(OWNERID):
            # Add CPU and RAM usage
            process = psutil.Process(os.getpid())
            cpu_usage = process.cpu_percent()
            ram_usage = round(process.memory_percent(), 2)
            ram_real = round(process.memory_info().rss / (1024 ** 2), 2)

            embed.add_field(name="CPU", value=f"{cpu_usage}%", inline=True)
            embed.add_field(name="RAM", value=f"{ram_usage}%", inline=True)
            embed.add_field(name="RAM", value=f"{ram_real} MB", inline=True)

        await interaction.response.send_message(embed=embed)



#Change Nickname
@tree.command(name = 'change_nickname', description = 'Change the nickname of the bot.')
@discord.app_commands.checks.cooldown(1, 60, key=lambda i: (i.guild_id))
@discord.app_commands.checks.has_permissions(manage_nicknames = True)
@discord.app_commands.describe(nick='New nickname for me.')
async def self(interaction: discord.Interaction, nick: str):
    await interaction.guild.me.edit(nick=nick)
    await interaction.response.send_message(f'My new nickname is now **{nick}**.', ephemeral=True)



#Support Invite
if support_available:
    @tree.command(name = 'support', description = 'Get invite to our support server.')
    @discord.app_commands.checks.cooldown(1, 60, key=lambda i: (i.user.id))
    async def self(interaction: discord.Interaction):
        if str(interaction.guild.id) != support_id:
            await interaction.response.defer(ephemeral = True)
            await interaction.followup.send(await Functions.create_support_invite(interaction), ephemeral = True)
        else:
            await interaction.response.send_message('You are already in our support server!', ephemeral = True)



#Send pannel
@tree.command(name = 'send_pannel', description = 'Send pannel to varification channel.')
@discord.app_commands.checks.cooldown(1, 60, key=lambda i: (i.guild_id))
@discord.app_commands.checks.has_permissions(manage_guild = True)
async def self(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral= True)
    #Captcha Info View
    class CaptchaView(discord.ui.View):
        def __init__(self, *, timeout=None):
            super().__init__(timeout=timeout)

            self.add_item(discord.ui.Button(label='🤖 Verify', style=discord.ButtonStyle.blurple, custom_id='verify'))
            self.add_item(discord.ui.Button(label='Why?', style=discord.ButtonStyle.blurple, custom_id='why'))


    c.execute('SELECT * FROM servers WHERE guild_id = ?', (interaction.guild.id,))
    data = c.fetchone()
    if data:
        verify_channel_id = data[1]
        timeout = int(data[4] / 60)
        action = data[5]
        ban_time = data[6]
    else:
        verify_channel_id = None
    try:
        verify_channel = await bot.fetch_channel(verify_channel_id)
    except discord.NotFound:
        verify_channel = None
    except discord.Forbidden:
        await interaction.followup.send(f'I don\'t have permission to see the verification channel (<#{verify_channel_id}>).', ephemeral = True)
        return
    if not verify_channel:
        await interaction.followup.send('The verification channel is not set or doesn\'t exist. Please set it with `/setup`.', ephemeral = True)
        return


    embed = discord.Embed(title = ':robot: Verification required',
                          color = 0x2b63b0)
    action_text = {
        'ban': f"you'll be banned{f' for {Functions.format_seconds(ban_time)}' if ban_time else ''}, if you do not verify yourself within {timeout} minutes",
        'kick': f"you'll be kicked, if you do not verify yourself within {timeout} minutes",
        None: "",
    }[action]

    embed.description = f"To proceed to `{interaction.guild.name}`, we kindly ask you to confirm your humanity by solving a captcha. Simply click the button below to get started!"
    if action_text:
        embed.description += f"\n\nPlease note that {action_text}."

    c.execute('SELECT * FROM panels WHERE guild_id = ?', (interaction.guild_id,))
    data = c.fetchone()
    if data:
        panel_id = data[1]
        try:
            panel_id = await verify_channel.fetch_message(panel_id)
        except discord.NotFound:
            panel_id = None
        except discord.Forbidden:
            await interaction.followup.send(f'I don\'t have permission to see the verification channels (<#{verify_channel_id}>) history.\nI need the "Read Message History" permission.', ephemeral = True)
            return
        if not panel_id:
            try:
                panel = await verify_channel.send(embed = embed, view = CaptchaView())
            except discord.Forbidden:
                await interaction.followup.send(f'I don\'t have permission to send messages in the verification channel (<#{verify_channel_id}>).', ephemeral = True)
                return
        else:
            await interaction.followup.send('The verification panel already exists.\nTo update it, you have to first delete the old one.', ephemeral = True)
            return
    else:
        try:
            panel = await verify_channel.send(embed = embed, view = CaptchaView())
        except discord.Forbidden:
            await interaction.followup.send(f'I don\'t have permission to send messages in the verification channel (<#{verify_channel_id}>).', ephemeral = True)
            return

    c.execute('INSERT OR REPLACE INTO panels VALUES (?, ?)', (interaction.guild_id, panel.id))
    conn.commit()
    await interaction.followup.send(f'The verification panel has been sent to <#{verify_channel_id}>.', ephemeral = True)



#Protect server
@tree.command(name = 'setup', description = 'Setup the server for the bot.')
@discord.app_commands.checks.cooldown(1, 60, key=lambda i: (i.guild_id))
@discord.app_commands.checks.has_permissions(manage_guild = True)
@discord.app_commands.describe(verify_channel = 'Channel for the verification message.',
                               verify_role = 'Role assigned after successfull verification.',
                               log_channel = 'Channel used to send logs.',
                               timeout = 'After that timeframe the action gets executed.',
                               action = 'Action that gets executed after timeout.',
                               ban_time = 'Time a user gets banned for if action is ban. Leave empty for perma ban. (1d / 1h / 1m / 1s)',
                               account_age = 'Account age required to join the server.')
@discord.app_commands.choices(timeout = [
    discord.app_commands.Choice(name = '5 Minutes', value = 300),
    discord.app_commands.Choice(name = '10 Minutes', value = 600),
    discord.app_commands.Choice(name = '15 Minutes', value = 900),
    discord.app_commands.Choice(name = '20 Minutes', value = 1200),
    discord.app_commands.Choice(name = '25 Minutes', value = 1500),
    discord.app_commands.Choice(name = '30 Minutes', value = 1800)
    ],
                            action = [
    discord.app_commands.Choice(name = 'Kick', value = 'kick'),
    discord.app_commands.Choice(name = 'Ban', value = 'ban'),
    discord.app_commands.Choice(name = 'Nothing', value = '')
    ])
async def self(interaction: discord.Interaction, verify_channel: discord.TextChannel, verify_role: discord.Role, log_channel: discord.TextChannel, timeout: int, action: str, ban_time: str = None, account_age: str = None):
    if action == 'kick':
        if not interaction.guild.me.guild_permissions.kick_members:
            await interaction.response.send_message(f'I need the permission to {action} members.', ephemeral=True)
            return
    elif action == 'ban':
        if not interaction.guild.me.guild_permissions.ban_members:
            await interaction.response.send_message(f'I need the permission to {action} members.', ephemeral=True)
            return
    if action == '':
        action = None
    if not verify_channel.permissions_for(interaction.guild.me).send_messages:
        await interaction.response.send_message(f'I need the permission to send messages in {verify_channel.mention}.', ephemeral=True)
        return
    if not interaction.guild.me.top_role > verify_role:
        await interaction.response.send_message(f'My highest role needs to be above {verify_role.mention}, so I can assign it.', ephemeral=True)
        return
    bot_permissions = log_channel.permissions_for(interaction.guild.me)
    if not bot_permissions.view_channel:
        await interaction.response.send_message(f'I need the permission to see {log_channel.mention}.', ephemeral=True)
        return
    if not (bot_permissions.send_messages and bot_permissions.embed_links):
        await interaction.response.send_message(f'I need the permission to send messages and embed links in {log_channel.mention}.', ephemeral=True)
        return
    if ban_time is not None:
        ban_time = timeparse(ban_time)
        if ban_time is None:
            await interaction.response.send_message('Invalid ban time. Please use the following format: `1d / 1h / 1m / 1s`.\nFor example: `1d2h3m4s`', ephemeral=True)
            return
    if account_age is not None:
        if not interaction.guild.me.guild_permissions.kick_members:
            await interaction.response.send_message(f'I need the permission to kick members.', ephemeral=True)
            return
        account_age = timeparse(account_age)
        if account_age is None:
            await interaction.response.send_message('Invalid account age. Please use the following format: `1d / 1h / 1m / 1s`.\nFor example: `1d2h3m4s`', ephemeral=True)
            return
    c.execute('INSERT OR REPLACE INTO servers VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (interaction.guild.id, verify_channel.id, verify_role.id, log_channel.id, timeout, action, ban_time, account_age,))
    conn.commit()
    await interaction.response.send_message(f'Setup completed.\nYou can now run `/send_panel`, to send the panel to <#{verify_channel.id}>.', ephemeral=True)



#Show current settings
@tree.command(name = 'settings', description = 'Show the current settings.')
@discord.app_commands.checks.cooldown(1, 60, key=lambda i: (i.guild_id))
@discord.app_commands.checks.has_permissions(manage_guild = True)
async def self(interaction: discord.Interaction):
    c.execute('SELECT * FROM servers WHERE guild_id = ?', (interaction.guild.id,))
    data = c.fetchone()
    if data:
        verify_channel = data[1]
        verify_role = data[2]
        log_channel = data[3]
        timeout = data[4]
        action = data[5]
        ban_time = data[6]
        account_age = data[7]
        embed = discord.Embed(title = 'Current settings',
                              description = f'**Verify Channel:** <#{verify_channel}>\n**Verify Role:** <@&{verify_role}>\n**Log Channel:** <#{log_channel}>\n**Timeout:** {Functions.format_seconds(timeout)}\n**Action:** {action}\n**Banned for:** {(Functions.format_seconds(ban_time) if ban_time is not None else None)}\n**Min account age:** {(Functions.format_seconds(account_age) if account_age is not None else None)}',
                              color = 0x2b63b0)
        await interaction.response.send_message(embed = embed, ephemeral=True)
    else:
        await interaction.response.send_message('There are no settings for this server.\nUse `/setup` to set-up this server.', ephemeral=True)



#Verify all users
@tree.command(name = 'verify-all', description = 'Verify all non-bot users on the server.')
@discord.app_commands.checks.cooldown(1, 3600, key=lambda i: (i.guild_id))
@discord.app_commands.checks.has_permissions(manage_guild = True)
async def self(interaction: discord.Interaction):
    c.execute('SELECT * FROM servers WHERE guild_id = ?', (interaction.guild.id,))
    data = c.fetchone()
    if data:
        i = 0
        verify_role_id = data[2]
        if verify_role_id:
            await interaction.response.send_message('Verifying all users on the server. This can take a while.', ephemeral=True)
            await Functions.send_logging_message(interaction = interaction, kind = 'verify_mass_started')
            verify_role = interaction.guild.get_role(verify_role_id)
            for member in interaction.guild.members:
                if not member.bot:
                    if verify_role not in member.roles:
                        try:
                            await member.add_roles(verify_role, reason = 'Verify all users on the server.')
                            i += 1
                        except discord.Forbidden:
                            continue
            await Functions.send_logging_message(interaction = interaction, kind = 'verify_mass_success', mass_amount = i)
            await interaction.edit_original_response(content = f'{interaction.user.mention}\nVerified {i} users on the server.')
        else:
            await interaction.response.send_message('There are no settings for this server.\nUse `/setup` to set-up this server.', ephemeral=True)
    else:
        await interaction.response.send_message('There are no settings for this server.\nUse `/setup` to set-up this server.', ephemeral=True)



















if __name__ == '__main__':
    if not TOKEN:
        error_message = 'Missing token. Please check your .env file.'
        program_logger.critical(error_message)
        sys.exit(error_message)
    else:
        try:
            SignalHandler()
            bot.run(TOKEN, log_handler=None)
        except discord.errors.LoginFailure:
            error_message = 'Invalid token. Please check your .env file.'
            program_logger.critical(error_message)
            sys.exit(error_message)
        except asyncio.CancelledError:
            if shutdown:
                pass

