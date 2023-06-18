#Import
print('Loading...')
import asyncio
import discord
import io
import json
import jsonschema
import logging
import logging.handlers
import os
import platform
import random
import sentry_sdk
import sqlite3
import string
import sys
import time
from captcha.image import ImageCaptcha
from datetime import timedelta, datetime
from dotenv import load_dotenv
from pytimeparse.timeparse import timeparse
from zipfile import ZIP_DEFLATED, ZipFile



#Init
discord.VoiceClient.warn_nacl = False
load_dotenv()
image_captcha = ImageCaptcha()
sentry_sdk.init(
	dsn=os.getenv('SENTRY_DSN'),
	traces_sample_rate=1.0,
	profiles_sample_rate=1.0,
	environment='Production'
)
app_folder_name = 'Bouncer'
bot_name = 'Bouncer'
if not os.path.exists(f'{app_folder_name}//Logs'):
	os.makedirs(f'{app_folder_name}//Logs')
if not os.path.exists(f'{app_folder_name}//Buffer'):
	os.makedirs(f'{app_folder_name}//Buffer')
log_folder = f'{app_folder_name}//Logs//'
buffer_folder = f'{app_folder_name}//Buffer//'
activity_file = os.path.join(app_folder_name, 'activity.json')
db_file = os.path.join(app_folder_name, f'{bot_name}.db')
bot_version = "1.0.0"

#Logger init
logger = logging.getLogger('discord')
manlogger = logging.getLogger('Program')
logger.setLevel(logging.INFO)
manlogger.setLevel(logging.INFO)
logging.getLogger('discord.http').setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
	filename = f'{log_folder}{bot_name}.log',
	encoding = 'utf-8',
	maxBytes = 8 * 1024 * 1024,
	backupCount = 5,
	mode='w')
dt_fmt = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
handler.setFormatter(formatter)
logger.addHandler(handler)
manlogger.addHandler(handler)
manlogger.info('Engine powering up...')


#Load env
TOKEN = os.getenv('TOKEN')
ownerID = os.getenv('OWNER_ID')
support_id = os.getenv('SUPPORT_SERVER')

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
					manlogger.debug(f'ValidationError: {ve}')
					self.write_default_content()
				except json.decoder.JSONDecodeError as jde:
					manlogger.debug(f'JSONDecodeError: {jde}')
					self.write_default_content()
		else:
			self.write_default_content()

	def write_default_content(self):
		with open(self.file_path, 'w') as file:
			json.dump(self.default_content, file, indent=4)
validator = JSONValidator(activity_file)
validator.validate_and_fix_json()


#Bot Class
class aclient(discord.AutoShardedClient):
	def __init__(self):
	
		intents = discord.Intents.default()
		intents.members = True
	
		super().__init__(owner_id = ownerID,
						  intents = intents,
						  status = discord.Status.invisible
						)
	
		self.synced = False
		self.db_conns = {}
		self.captcha_timeout = [] 


	class Presence():
		@staticmethod
		def get_activity() -> discord.Activity:
			with open(activity_file) as f:
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
			with open(activity_file) as f:
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
		if not self.initialized:
			return
		options = interaction.data.get("options")
		option_values = ""
		if options:
			for option in options:
				option_values += f"{option['name']}: {option['value']}"
		if isinstance(error, discord.app_commands.CommandOnCooldown):
			await interaction.response.send_message(f'This command is on cooldown.\nTime left: `{str(timedelta(seconds=int(error.retry_after)))}`.', ephemeral=True)
		else:
			try:
				await interaction.followup.send(f"{error}\n\n{option_values}", ephemeral=True)
			except:
				await interaction.response.send_message(f"{error}\n\n{option_values}", ephemeral=True)
			manlogger.warning(f"{error} -> {option_values} | Invoked by {interaction.user.name} ({interaction.user.id})")


	async def on_guild_join(self, guild):
		if not self.initialized:
			return
		manlogger.info(f'I joined {guild}. (ID: {guild.id})')


	async def on_guild_remove(self, guild):
		if not self.initialized:
			return
		manlogger.info(f'I got kicked from {guild}. (ID: {guild.id})')


	async def on_member_join(self, member: discord.Member):
		if not self.initialized:
			return
		if member.bot:
			return
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
					await interaction.response.send_message('Please wait a few seconds before trying again.', ephemeral=True)
					return
				else:
					await Functions.verify(interaction)
					return
			elif button_id == 'why':
				await interaction.response.send_message(f'This serever is protected by <@!{bot.user.id}> to prevent raids & malicious users.\n\nTo gain access to this server, you\'ll need to verify yourself by completing a captcha.\n\nYou don\'t need to connect your account for that.', view = WhyView(), ephemeral=True)


	async def setup_database(self, shard_id):
		conn = sqlite3.connect(db_file)
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
				guild_id INTEGER PRIMARY KEY,
				user_id INTEGER,
				unban_time INTEGER
			);

			CREATE TABLE IF NOT EXISTS processing_joined (
				guild_id INTEGER PRIMARY KEY,
				user_id INTEGER,
				join_time INTEGER
			)
		''')
		self.db_conns[shard_id] = conn


	async def on_ready(self):
		global owner, start_time, conn, c
		shard_id = self.shard_info.id if hasattr(self, 'shard_info') else 0
		#SQLite init
		conn = sqlite3.connect(db_file)
		c = conn.cursor()
		await self.setup_database(shard_id)
		
		try:
			owner = await self.fetch_user(ownerID)
			if owner is None:
				manlogger.critical(f"Invalid ownerID: {ownerID}")
				sys.exit(f"Invalid ownerID: {ownerID}")
		except discord.HTTPException as e:
			manlogger.critical(f"Error fetching owner user: {e}")
			sys.exit(f"Error fetching owner user: {e}")
		logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
		if not self.synced:
			manlogger.info('Syncing...')
			await tree.sync()
			manlogger.info('Synced.')
			self.synced = True
			await bot.change_presence(activity = self.Presence.get_activity(), status = self.Presence.get_status())
		start_time = datetime.now()

		#Start background tasks
		bot.loop.create_task(Functions.process_latest_joined())
		bot.loop.create_task(Functions.check_and_process_temp_bans())

		self.initialized = True
		manlogger.info('All systems online...')
		clear()
		print('READY')

	async def on_disconnect(self):
		shard_id = self.shard_info.id if hasattr(self, 'shard_info') else 0
		conn = self.db_conns.pop(shard_id, None)
		if conn:
			conn.close()
bot = aclient()
tree = discord.app_commands.CommandTree(bot)


# Check if all required variables are set
owner_available = bool(ownerID)
support_available = bool(support_id)

#Fix error on windows on shutdown
if platform.system() == 'Windows':
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
def clear():
	if platform.system() == 'Windows':
		os.system('cls')
	else:
		os.system('clear')



#Functions
class Functions():
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
				#self.timeout = 60
				#self.answer = discord.ui.TextInput(label = 'Please enter the captcha text:', placeholder = 'Captcha text', min_length = 6, max_length = 6, style = discord.TextStyle.short, required = True)
				self.verification_successful = False

			answer = discord.ui.TextInput(label = 'Please enter the captcha text:', placeholder = 'Captcha text', min_length = 6, max_length = 6, style = discord.TextStyle.short, required = True)	
			
			async def on_submit(self, interaction: discord.Interaction):
				if self.answer.value.upper() == captcha_text:
					await interaction.user.add_roles(interaction.guild.get_role(int(verified_role_id)))
					await Functions.send_logging_message(interaction = interaction, kind = 'verify_success')
					await interaction.response.edit_message(content = 'You have successfully verified yourself.', view = None)
					if interaction.user.id in bot.captcha_timeout:
						bot.captcha_timeout.remove(interaction.user.id)
					self.verification_successful = True
					print(self.verification_successful)
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
			def __init__(self, *, timeout=15):
				super().__init__(timeout=timeout)
				self.add_item(SubmitButton())

			async def on_timeout(self):
				print(captcha_input.verification_successful)
				if not captcha_input.verification_successful:
					self.remove_item(SubmitButton())
					await interaction.edit_original_response(content = 'Captcha timed out. Request a new one.', view = None)
					if interaction.user.id in bot.captcha_timeout:
						bot.captcha_timeout.remove(interaction.user.id)


		#Load verify_role from db
		c.execute(f'SELECT verify_role FROM servers WHERE guild_id = {interaction.guild_id}')
		verified_role_id = c.fetchone()[0]

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
		while True:
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
									manlogger.debug(f'Kicked {member.name}#{member.discriminator} ({member.id}) from {guild.name} ({guild.id}).')
								except discord.Forbidden:
									manlogger.debug(f'Could not kick {member.name}#{member.discriminator} ({member.id}) from {guild.name} ({guild.id}).')
							elif action == 'ban':
								try:
									if ban_time is not None:
										await member.ban(reason=f'Did not successfully verify in time. Banned for {Functions.format_seconds(ban_time)}')
										c.execute('INSERT INTO temp_bans VALUES (?, ?, ?)', (guild.id, member.id, int(time.time() + ban_time)))
									else:
										await member.ban(reason=f'Did not successfully verify in time.')
									await Functions.send_logging_message(member = member, kind = 'verify_ban')									
									manlogger.debug(f'Banned {member.name}#{member.discriminator} ({member.id}) from {guild.name} ({guild.id}).')
								except discord.Forbidden:
									manlogger.debug(f'Could not ban {member.name}#{member.discriminator} ({member.id}) from {guild.name} ({guild.id}).')
						else:
							c.execute('DELETE FROM processing_joined WHERE guild_id = ? AND user_id = ?', (row[0], row[1]))
				except Exception as e:
					conn.commit()
					raise e
			conn.commit()
			await asyncio.sleep(15)


	async def check_and_process_temp_bans():
		while True:
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
						embed.timestamp = datetime.utcnow()
						manlogger.debug(f'Unbanned {member.name}#{member.discriminator} ({member.id}) from {guild.name} ({guild.id}).')
						c.execute('DELETE FROM temp_bans WHERE guild_id = ? AND user_id = ?', (temp_ban[0], temp_ban[1]))
						if log_channel is not None:	
							try:
								await log_channel.send(embed = embed)
							except discord.Forbidden:
								manlogger.debug(f'Could not send unban log message in {guild.name} ({guild.id}).')
					except discord.Forbidden:
						manlogger.debug(f'Could not unban {member.name}#{member.discriminator} ({member.id}) from {guild.name} ({guild.id}).')
				except Exception as e:
					conn.commit()
					raise e
			
			conn.commit()
			await asyncio.sleep(5)


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

		if kind == 'verify_start':
			embed = discord.Embed(title = 'Captcha sent', description = f'User {interaction.user.mention} requested a new captcha.', color = discord.Color.blurple())
			embed.timestamp = datetime.utcnow()
			await log_channel.send(embed = embed)
		elif kind == 'verify_success':
			embed = discord.Embed(title = 'Verification successful', description = f'User {interaction.user.mention} successfully verified.', color = discord.Color.green())
			embed.timestamp = datetime.utcnow()
			await log_channel.send(embed = embed)
		elif kind == 'verify_fail':
			embed = discord.Embed(title = 'Wrong captcha', description = f'User {interaction.user.mention} entered a wrong captcha.', color = discord.Color.red())
			embed.timestamp = datetime.utcnow()
			await log_channel.send(embed = embed)
		elif kind == 'verify_kick':
			embed = discord.Embed(title = 'Time limit reached', color = discord.Color.red())
			embed.timestamp = datetime.utcnow()
			embed.add_field(name = 'User', value = member.mention)
			embed.add_field(name = 'Action', value = 'Kick')
			await log_channel.send(embed = embed)
		elif kind == 'verify_ban':
			embed = discord.Embed(title = 'Time limit reached', color = discord.Color.red())
			embed.timestamp = datetime.utcnow()
			embed.add_field(name = 'User', value = member.mention)
			embed.add_field(name = 'Action', value = 'Ban')
			if ban_time is not None:
				embed.add_field(name = 'Duration', value = f'{Functions.format_seconds(ban_time)}')
			await log_channel.send(embed = embed)
		elif kind == 'verify_mass_started':
			embed = discord.Embed(title = 'Mass verification started', description = f'Mass verification started by {interaction.user.mention}.', color = discord.Color.blurple())
			embed.timestamp = datetime.utcnow()
			await log_channel.send(embed = embed)
		elif kind == 'verify_mass_success':
			embed = discord.Embed(title = 'Mass verification successful', description = f'{interaction.user.mention} successfully applied the verified role to {mass_amount} users.', color = discord.Color.green())
			embed.timestamp = datetime.utcnow()
			await log_channel.send(embed = embed)
		elif kind == 'unban':
			embed = discord.Embed(title = 'Unban', description = f'User {member.mention} was unbanned.', color = discord.Color.green())
			embed.timestamp = datetime.utcnow()
			await log_channel.send(embed = embed)


	def format_seconds(seconds):
		days, remainder = divmod(seconds, 86400)
		hours, remainder = divmod(remainder, 3600)
		minutes, seconds = divmod(remainder, 60)
		
		parts = []
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
#Shutdown
if owner_available:
	@tree.command(name = 'shutdown', description = 'Savely shut down the bot.')
	async def self(interaction: discord.Interaction):
		if interaction.user.id == int(ownerID):
			manlogger.info('Engine powering down...')
			await interaction.response.send_message('Engine powering down...', ephemeral = True)
			await bot.change_presence(status = discord.Status.invisible)
			conn.commit()
			conn.close()
			sentry_sdk.init(dsn='', traces_sample_rate=0.0, profiles_sample_rate=0.0)
			for task in asyncio.all_tasks():
				task.cancel()
			await asyncio.gather(*asyncio.all_tasks(), return_exceptions = True)
			await bot.close()
		else:
			await interaction.response.send_message('Only the BotOwner can use this command!', ephemeral = True)


#Get Logs
if owner_available:
	@tree.command(name = 'get_logs', description = 'Get the current, or all logfiles.')
	@discord.app_commands.describe(choice = 'Choose which log files you want to receive.')
	@discord.app_commands.choices(choice = [
		discord.app_commands.Choice(name="Last X lines", value="xlines"),
		discord.app_commands.Choice(name="Current Log", value="current"),
		discord.app_commands.Choice(name="Whole Folder", value="whole")
	])
	async def self(interaction: discord.Interaction, choice: str):
		if interaction.user.id != int(ownerID):
			await interaction.response.send_message('Only the BotOwner can use this command!', ephemeral = True)
			return
		else:
			if choice == 'xlines':
				class LastXLines(discord.ui.Modal, title = 'Line Input'):
					def __init__(self, interaction):
						super().__init__()
						self.timeout = 15
						self.answer = discord.ui.TextInput(label = 'How many lines?', style = discord.TextStyle.short, required = True, min_length = 1, max_length = 4)
						self.add_item(self.answer)

					async def on_submit(self, interaction: discord.Interaction):
						try:
							int(self.answer.value)
						except:
							await interaction.response.send_message(content = 'You can only use numbers!', ephemeral = True)
							return
						if int(self.answer.value) == 0:
							await interaction.response.send_message(content = 'You can not use 0 as a number!', ephemeral = True)
							return
						with open(f'{log_folder}{bot_name}.log', 'r', encoding='utf8') as f:
							with open(buffer_folder+'log-lines.txt', 'w', encoding='utf8') as f2:
								count = 0
								for line in (f.readlines()[-int(self.answer.value):]):
									f2.write(line)
									count += 1
						await interaction.response.send_message(content = f'Here are the last {count} lines of the current logfile:', file = discord.File(r''+buffer_folder+'log-lines.txt') , ephemeral = True)
						if os.path.exists(buffer_folder+'log-lines.txt'):
							os.remove(buffer_folder+'log-lines.txt')
				await interaction.response.send_modal(LastXLines(interaction))
			elif choice == 'current':
				await interaction.response.defer(ephemeral = True)
				try:
					await interaction.followup.send(file=discord.File(r''f'{log_folder}{bot_name}.log'), ephemeral=True)
				except discord.HTTPException as err:
					if err.status == 413:
						with ZipFile(buffer_folder+'Logs.zip', mode='w', compression=ZIP_DEFLATED, compresslevel=9, allowZip64=True) as f:
							f.write(f'{log_folder}{bot_name}.log')
						try:
							await interaction.response.send_message(file=discord.File(r''+buffer_folder+'Logs.zip'))
						except discord.HTTPException as err:
							if err.status == 413:
								await interaction.followup.send("The log is too big to be send directly.\nYou have to look at the log in your server(VPS).")
						os.remove(buffer_folder+'Logs.zip')
			elif choice == 'whole':
				if os.path.exists(buffer_folder+'Logs.zip'):
					os.remove(buffer_folder+'Logs.zip')
				with ZipFile(buffer_folder+'Logs.zip', mode='w', compression=ZIP_DEFLATED, compresslevel=9, allowZip64=True) as f:
					for file in os.listdir(log_folder):
						if file.endswith(".zip"):
							continue
						f.write(log_folder+file)
				try:
					await interaction.response.send_message(file=discord.File(r''+buffer_folder+'Logs.zip'), ephemeral=True)
				except discord.HTTPException as err:
					if err.status == 413:
						await interaction.followup.send("The folder is too big to be send directly.\nPlease get the current file, or the last X lines.")
				os.remove(buffer_folder+'Logs.zip')


#Change Activity
if owner_available:
	@tree.command(name = 'activity', description = 'Change my activity.')
	@discord.app_commands.describe(type='The type of Activity you want to set.', title='What you want the bot to play, stream, etc...', url='Url of the stream. Only used if activity set to \'streaming\'.')
	@discord.app_commands.choices(type=[
		discord.app_commands.Choice(name='Competing', value='Competing'),
		discord.app_commands.Choice(name='Listening', value='Listening'),
		discord.app_commands.Choice(name='Playing', value='Playing'),
		discord.app_commands.Choice(name='Streaming', value='Streaming'),
		discord.app_commands.Choice(name='Watching', value='Watching')
		])
	async def self(interaction: discord.Interaction, type: str, title: str, url: str = ''):
		if interaction.user.id == int(ownerID):
			await interaction.response.defer(ephemeral = True)
			with open(activity_file) as f:
				data = json.load(f)
			if type == 'Playing':
				data['activity_type'] = 'Playing'
				data['activity_title'] = title
			elif type == 'Streaming':
				data['activity_type'] = 'Streaming'
				data['activity_title'] = title
				data['activity_url'] = url
			elif type == 'Listening':
				data['activity_type'] = 'Listening'
				data['activity_title'] = title
			elif type == 'Watching':
				data['activity_type'] = 'Watching'
				data['activity_title'] = title
			elif type == 'Competing':
				data['activity_type'] = 'Competing'
				data['activity_title'] = title
			with open(activity_file, 'w', encoding='utf8') as f:
				json.dump(data, f, indent=2)
			await bot.change_presence(activity = bot.Presence.get_activity(), status = bot.Presence.get_status())
			await interaction.followup.send('Activity changed!', ephemeral = True)
		else:
			await interaction.followup.send('Only the BotOwner can use this command!', ephemeral = True)


#Change Status
@tree.command(name = 'status', description = 'Change my status.')
@discord.app_commands.describe(status='The status you want to set.')
@discord.app_commands.choices(status=[
	discord.app_commands.Choice(name='Online', value='online'),
	discord.app_commands.Choice(name='Idle', value='idle'),
	discord.app_commands.Choice(name='Do not disturb', value='dnd'),
	discord.app_commands.Choice(name='Invisible', value='invisible')
	])
async def self(interaction: discord.Interaction, status: str):
	if interaction.user.id == int(ownerID):
		await interaction.response.defer(ephemeral = True)
		with open(activity_file) as f:
			data = json.load(f)
		data['status'] = status
		with open(activity_file, 'w', encoding='utf8') as f:
			json.dump(data, f, indent=2)
		await bot.change_presence(activity = bot.Presence.get_activity(), status = bot.Presence.get_status())
		await interaction.followup.send('Status changed!', ephemeral = True)
	else:
		await interaction.followup.send('Only the BotOwner can use this command!', ephemeral = True)



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
	embed.add_field(name="Bot-Version", value=bot_version, inline=True)
	embed.add_field(name="Uptime", value=str(timedelta(seconds=int((datetime.now() - start_time).total_seconds()))), inline=True)

	embed.add_field(name="Bot-Owner", value=f"<@!{ownerID}>", inline=True)
	embed.add_field(name="\u200b", value="\u200b", inline=True)
	embed.add_field(name="\u200b", value="\u200b", inline=True)

	embed.add_field(name="Server", value=f"{len(bot.guilds)}", inline=True)
	embed.add_field(name="Member count", value=str(member_count), inline=True)
	embed.add_field(name="\u200b", value="\u200b", inline=True)

	embed.add_field(name="Shards", value=f"{bot.shard_count}", inline=True)
	embed.add_field(name="Shard ID", value=f"{interaction.guild.shard_id if interaction.guild else 'N/A'}", inline=True)
	embed.add_field(name="\u200b", value="\u200b", inline=True)

	embed.add_field(name="Python-Version", value=f"{platform.python_version()}", inline=True)
	embed.add_field(name="discord.py-Version", value=f"{discord.__version__}", inline=True)
	embed.add_field(name="Sentry-Version", value=f"{sentry_sdk.consts.VERSION}", inline=True)

	embed.add_field(name="Repo", value=f"[GitLab](https://gitlab.bloodygang.com/Serpensin/DiscordBots-Bouncer)", inline=True)
	embed.add_field(name="Invite", value=f"[Invite me](https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=268519430&scope=bot%20applications.commands)", inline=True)
	embed.add_field(name="\u200b", value="\u200b", inline=True)

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
							   ban_time = 'Time a user gets banned for if action is ban. Leave empty for perma ban. (1d / 1h / 1m / 1s)')
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
async def self(interaction: discord.Interaction, verify_channel: discord.TextChannel, verify_role: discord.Role, log_channel: discord.TextChannel, timeout: int, action: str, ban_time: str = None):
	if ban_time is not None:
		ban_time = timeparse(ban_time)
		if ban_time is None:
			await interaction.response.send_message('Invalid ban time. Please use the following format: `1d / 1h / 1m / 1s`.\nFor example: `1d2h3m4s`', ephemeral=True)
			return
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
	if action == 'kick' or action == 'ban':
		if not interaction.guild.me.guild_permissions.kick_members:
			await interaction.response.send_message(f'I need the permission to {action} members.', ephemeral=True)
			return
	if action == '':
		action = None
	c.execute('INSERT OR REPLACE INTO servers VALUES (?, ?, ?, ?, ?, ?, ?)', (interaction.guild.id, verify_channel.id, verify_role.id, log_channel.id, timeout, action, ban_time))
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
		embed = discord.Embed(title = 'Current settings',
							  description = f'**Verify Channel:** <#{verify_channel}>\n**Verify Role:** <@&{verify_role}>\n**Log Channel:** <#{log_channel}>\n**Timeout:** {Functions.format_seconds(timeout)}\n**Action:** {action}',
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
			verify_role = interaction.guild.get_role(verify_role_id)
			for member in interaction.guild.members:
				if not member.bot:
					if verify_role not in member.roles:
						try:
							await member.add_roles(verify_role, reason = 'Verify all users on the server.')
							i += 1
						except discord.Forbidden:
							continue
			if i > 0:
				await Functions.send_logging_message(interaction = interaction, kind = 'verify_mass_success', mass_amount = i)
			await interaction.edit_original_response(content = f'{interaction.user.mention}\nVerified {i} users on the server.')
		else:
			await interaction.response.send_message('There are no settings for this server.\nUse `/setup` to set-up this server.', ephemeral=True)
	else:
		await interaction.response.send_message('There are no settings for this server.\nUse `/setup` to set-up this server.', ephemeral=True)



















if __name__ == '__main__':
    if not TOKEN:
        error_message = 'Missing token. Please check your .env file.'
        manlogger.critical(error_message)
        sys.exit(error_message)
    else:
        try:
            bot.run(TOKEN, log_handler=None)
        except discord.errors.LoginFailure:
            error_message = 'Invalid token. Please check your .env file.'
            manlogger.critical(error_message)
            sys.exit(error_message)

