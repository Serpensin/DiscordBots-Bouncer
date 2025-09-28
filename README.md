# Discord Bouncer [![Discord Bot Invite](https://img.shields.io/badge/Invite-blue)](https://discord.com/oauth2/authorize?client_id=1251187046329094314)[![Discord Bots](https://top.gg/api/widget/servers/1251187046329094314.svg)](https://top.gg/bot/1251187046329094314)

**Force users to solve a captcha to get access to the server!**

Discord Bouncer is a bot specifically designed to protect servers and facilitate user verification, by sending the user a captcha inside the verification channel.
This means, that users wont need to connect there discord-account with a third-party (like captcha.bot).
If they don't verify within the time limit specified by the server, they will be either kicked, perma banned, temp banned, or nothing.
The bot will only kick/ban users who join during the time, the bot is online.
Here is an example of a captcha:

![Example Captcha](https://imgur.com/WfzvPON.png)
<audio controls>
  <source src="https://cdn.serpensin.com/captcha_1759064957.mp3" type="audio/mpeg">
  Your browser does not support the audio element.
</audio>

## Features

- `/setup` followed by the required values will setup your server. There will be an explanation on what each option is for.
- `/send_panel` will send the verification panel to the registered verification channel.
- `/settings` will show you the current settings that are applied for this server.
- `/verify-all` will apply the verified role to every member that isn't a bot.

**Keep in mind that every of the above mentioned commands requires you to have `MANAGE_GUILD` permissions.**





## Setup

### Classic Method

1. Ensure Python 3.11 is installed. This bot was developed using Python 3.12.2. Download it [here](https://www.python.org/downloads/).
2. Clone this repository or download the zip file.
3. Open a terminal in the folder where you cloned the repository or extracted the zip file.
4. Run `pip install -r requirements.txt` to install the dependencies.
5. Open the file ".env.template" and complete all variables:
   - `TOKEN`: The token of your bot. Obtain it from the [Discord Developer Portal](https://discord.com/developers/applications).
       - Make sure to enable the `SERVER MEMBERS INTENT` in the bot settings.
   - `OWNER_ID`: Your Discord ID.
   - `SUPPORT_SERVER`: ID of your support-server. Bot needs the right to create invites there. You can leave it empty.
   - `SENTRY_DSN`: Leave it empty. If you know, what it is for, you can add it.
6. Rename the file ".env.template" to ".env".
7. Run `python main.py` or `python3 main.py` to start the bot.

### Docker Method

#### Docker Compose Method

If you have cloned the repository, you will find a docker-compose.yml file in the folder.

1. Make sure Docker and Docker Compose are installed. Download Docker [here](https://docs.docker.com/get-docker/) and Docker Compose [here](https://docs.docker.com/compose/install/).
2. Navigate to the folder where you cloned the repository or extracted the zip file.
3. Open the `docker-compose.yml` file and update the environment variables as needed (such as `TOKEN` and `OWNER_ID`).
4. In the terminal, run the following command from the folder to start the bot:
`docker-compose up -d`

#### Docker Run

1. Ensure Docker is installed. Download it from the [Docker website](https://docs.docker.com/get-docker/).
2. Open a terminal.
3. Run the bot with the command below:
   - Modify the variables according to your requirements.
   - Set the `TOKEN` and `OWNER_ID`.

#### Run the bot
```bash
docker run -d \
-e TOKEN=BOT_TOKEN \
-e OWNER_ID=DISCORD_ID_OF_OWNER \
--name Bouncer \
--restart any \
--health-cmd="curl -f http://localhost:5000/health || exit 1" \
--health-interval=30s \
--health-timeout=10s \
--health-retries=3 \
--health-start-period=40s \
-p 5000:5000 \
-v bouncer:/app/Bouncer \
ghcr.io/serpensin/discordbots-bouncer
```
