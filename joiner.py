import os
import re
import sys
import time
import json
import base64
import discord
import urllib3
import tls_client
import threading
import logging
import ctypes
from flask import Flask, request
from flask.cli import show_server_banner
from discord import app_commands
from colorama import Fore, init, Style
from pystyle import Colorate, Colors
from concurrent.futures import ThreadPoolExecutor
urllib3.disable_warnings()
init(autoreset=True)
def set_title(title):
    if os.name == "nt":
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    else:
        sys.stdout.write(f"]0;{title}")
        sys.stdout.flush()
def gradient(text):
    return Colorate.Horizontal(Colors.green_to_cyan, text, 1)
class Logger:
    def __init__(self):
        self._o = gradient("[")
        self._c = gradient("]")
        self._arrow = gradient("~>")
        self.size = os.get_terminal_size().columns if os.name == "nt" else 80
    def strip_ansi(self, text):
        ansi = re.compile(r'(?:[@-Z\-_]|\[[0-?]*[ -/]*[@-~])')
        return len(ansi.sub('', text))
    def center(self, text):
        vlen = self.strip_ansi(text)
        pad = max(0, (self.size - vlen) // 2)
        return " " * pad + text
    def brand(self):
        return f"{self._o} {Fore.WHITE}UtilityToolsV2{Style.RESET_ALL} {self._c}"
    def success(self, text, detail=None):
        det = f" {Fore.WHITE}| {Fore.LIGHTGREEN_EX}{detail}{Style.RESET_ALL}" if detail else ""
        print(f"      {self.brand()} {Fore.WHITE}{text}{Style.RESET_ALL}{det} {self._arrow} {Fore.GREEN}Success{Style.RESET_ALL}")
    def oauth(self, label):
        print(f"      {self.brand()} {Fore.WHITE}{label}{Style.RESET_ALL} {self._arrow} {Fore.GREEN}OAuth Obtained{Style.RESET_ALL}")
    def joined(self, text):
        print(f"      {self.brand()} {Fore.WHITE}{text}{Style.RESET_ALL} {self._arrow} {Fore.GREEN}Joined{Style.RESET_ALL}")
    def role(self, text):
        print(f"      {self.brand()} {Fore.WHITE}{text}{Style.RESET_ALL} {self._arrow} {Fore.GREEN}Role Assigned{Style.RESET_ALL}")
    def error(self, text, detail=None):
        det = f" {Fore.WHITE}| {Fore.LIGHTRED_EX}{detail}{Style.RESET_ALL}" if detail else ""
        print(f"      {self.brand()} {Fore.WHITE}{text}{Style.RESET_ALL}{det} {self._arrow} {Fore.RED}Failed{Style.RESET_ALL}")
    def info(self, text, detail=None):
        det = f" {Fore.WHITE}| {Fore.LIGHTCYAN_EX}{detail}{Style.RESET_ALL}" if detail else ""
        print(f"      {self.brand()} {Fore.WHITE}{text}{Style.RESET_ALL}{det}")
    def ratelimit(self, seconds):
        print(f"      {self.brand()} {Fore.YELLOW}Rate limited {self._arrow} Sleeping {seconds:.1f}s{Style.RESET_ALL}")
    def input(self, label=None):
        txt = f"{Fore.WHITE}{label}{Style.RESET_ALL} " if label else ""
        return input(f"      {self.brand()} {txt}{self._arrow} ").strip()
    def confirm(self, label=None):
        choices = f"{Fore.WHITE}({Fore.GREEN}y{Fore.WHITE}/{Fore.RED}n{Fore.WHITE}){Style.RESET_ALL}"
        txt = f"{Fore.WHITE}{label}{Style.RESET_ALL} " if label else ""
        return input(f"      {self.brand()} {txt}{choices} {self._arrow} ").strip().lower() == "y"
    def wait(self):
        input(f"      {self.brand()} {Fore.WHITE}Press Enter...{Style.RESET_ALL} {self._arrow} ")
class Config:
    def __init__(self):
        self.path = "assets/config.json"
        self.defaults = {
            "bot": {
                "BotToken": "",
                "Client_Id": "",
                "Client_Secret": "",
                "Whitelisted_Ids": ["2456789", ""],
                "RegisterCommand": True,
                "Auto_Role": False,
            },
            "tool": {
                "rotating_proxy": "",
                "max_workers": 4,
                "delay_between_join": 0.5,
                "token_file": "assets/tokens.txt",
                "redirect_uri": "http://localhost:8080/oauth2",
                "tls_client_identifier": "chrome_120",
                "save_Oauth_in_db": False
            }
        }
        self.data = self.load()
    def load(self):
        if not os.path.exists("assets"):
            os.makedirs("assets")
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                json.dump(self.defaults, f, indent=4)
            return self.defaults
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except:
            return self.defaults
    def get(self, section, key):
        return self.data.get(section, {}).get(key)
class Headers:
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ]
    @classmethod
    def pick(cls):
        return cls.agents[int(time.time()) % len(cls.agents)]
    @classmethod
    def build_props(cls, ua):
        props = {
            "os": "Windows",
            "browser": "Chrome",
            "device": "",
            "system_locale": "en-US",
            "browser_user_agent": ua,
            "browser_version": "120.0.0.0",
            "os_version": "10",
            "referrer": "",
            "referring_domain": "",
            "release_channel": "stable",
            "client_build_number": 269009
        }
        return base64.b64encode(json.dumps(props, separators=(",", ":")).encode()).decode()
class Proxy:
    @staticmethod
    def format(raw):
        if not raw:
            return None
        raw = raw.replace("http://", "").replace("https://", "")
        parts = raw.split(":")
        if len(parts) == 2:
            return {"http": f"http://{parts[0]}:{parts[1]}", "https": f"http://{parts[0]}:{parts[1]}"}
        elif len(parts) == 4:
            return {"http": f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}", "https": f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"}
        return None
class Token:
    def __init__(self, token, config, log):
        self.token = token
        self.config = config
        self.log = log
        self.ua = Headers.pick()
        self.session = tls_client.Session(
            client_identifier=config.get("tool", "tls_client_identifier"),
            random_tls_extension_order=True
        )
        self.proxy = Proxy.format(config.get("tool", "rotating_proxy"))
        if self.proxy:
            self.session.proxies = self.proxy
        self.session.headers.update({
            "authorization": self.token,
            "user-agent": self.ua,
            "x-super-properties": Headers.build_props(self.ua),
            "content-type": "application/json"
        })
    def auth(self):
        try:
            url = "https://discord.com/api/v9/oauth2/authorize"
            params = {
                "client_id": self.config.get("bot", "Client_Id"),
                "response_type": "code",
                "redirect_uri": self.config.get("tool", "redirect_uri"),
                "scope": "identify guilds.join"
            }
            res = self.session.post(url, params=params, json={"permissions": "0", "authorize": True})
            if res.status_code == 200:
                data = res.json()
                loc = data.get("location")
                if loc:
                    self.session.get(loc)
                    return True
                else:
                    self.log.error("No location in OAuth response")
            else:
                self.log.error("OAuth authorize failed", f"Status: {res.status_code}")
            return False
        except Exception as e:
            self.log.error("OAuth authorize exception", str(e))
            return False
    def give_role(self, guild_id, role_id, user_id):
        try:
            url = f"https://discord.com/api/v9/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
            res = self.session.put(url, headers={"authorization": f"Bot {self.config.get('bot', 'BotToken')}"})
            return res.status_code in [200, 204]
        except Exception as e:
            self.log.error("Add role exception", str(e))
            return False
def fetch_guild(invite_code, config, log):
    try:
        session = tls_client.Session(
            client_identifier=config.get("tool", "tls_client_identifier"),
            random_tls_extension_order=True
        )
        proxy = Proxy.format(config.get("tool", "rotating_proxy"))
        if proxy:
            session.proxies = proxy
        res = session.get(f"https://discord.com/api/v9/invites/{invite_code}?with_counts=true")
        if res.status_code == 200:
            return res.json().get("guild", {}).get("id")
        else:
            log.error("Failed to resolve invite", f"Status: {res.status_code}")
            return None
    except Exception as e:
        log.error("Exception resolving invite", str(e))
        return None
class Commands:
    def __init__(self, bot, config, log=None, parent=None):
        self.bot = bot
        self.config = config
        self.log = log
        self.parent = parent
        self.bio = "Made by https://www.utilitytoolsv2.store/tools/free\nFree and Open source"
        self.allowed = self.config.get("bot", "Whitelisted_Ids")
    async def setup(self):
        try:
            await self.bot.user.edit(description=self.bio)
        except:
            pass
        await self.register()
    async def register(self):
        @self.bot.tree.command(name="count", description="Shows the count of tokens")
        async def count(interaction: discord.Interaction):
            if str(interaction.user.id) not in self.allowed:
                return await interaction.response.send_message("Unauthorized", ephemeral=True)
            token_file = self.config.get("tool", "token_file")
            cnt = 0
            if os.path.exists(token_file):
                with open(token_file, "r") as f:
                    cnt = len([line for line in f if line.strip()])
            await interaction.response.send_message(f"Total tokens: {cnt}", ephemeral=True)
        @self.bot.tree.command(name="join", description="Join tokens to a server via OAuth")
        @app_commands.describe(
            member_count="Amount to join",
            invite="Discord invite link or code",
            autorole="Enable autorole",
            role_id="ID of the role to give"
        )
        async def join(interaction: discord.Interaction, member_count: int, invite: str, autorole: bool, role_id: str = None):
            if str(interaction.user.id) not in self.allowed:
                return await interaction.response.send_message("Unauthorized", ephemeral=True)
            await interaction.response.send_message(f"Starting OAuth join for {member_count} members...", ephemeral=True)
            if self.parent:
                self.parent.run_join(member_count, invite, autorole, role_id)
        @self.bot.tree.command(name="invite", description="Get the bot invite link")
        async def invite(interaction: discord.Interaction):
            if str(interaction.user.id) not in self.allowed:
                return await interaction.response.send_message("Unauthorized", ephemeral=True)
            client_id = self.config.get("bot", "Client_Id") or self.bot.user.id
            link = f"https://discord.com/api/oauth2/authorize?client_id={client_id}&permissions=8&scope=bot%20applications.commands"
            await interaction.response.send_message(f"Invite link: {link}", ephemeral=True)
        await self.bot.tree.sync()
class Manager:
    def __init__(self, config):
        self.config = config
        self.log = Logger()
        self.app = Flask(__name__)
        self.init_server()
        intents = discord.Intents.all()
        self.bot = discord.Client(intents=intents)
        self.bot.tree = discord.app_commands.CommandTree(self.bot)
        self.commands = Commands(self.bot, self.config, self.log, self)
        self.guild_id = None
        self.role_id = None
        self.auto_role = False
        self.ready = threading.Event()
    def init_server(self):
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        @self.app.route("/oauth2")
        def callback():
            code = request.args.get("code")
            guild_id = self.guild_id
            if not code:
                self.log.error("OAuth callback", "No code provided")
                return "Error: No code provided", 400
            if not guild_id:
                self.log.error("OAuth callback", "No guild ID set")
                return "Error: No guild ID", 400
            session = tls_client.Session(
                client_identifier=self.config.get("tool", "tls_client_identifier")
            )
            proxy = Proxy.format(self.config.get("tool", "rotating_proxy"))
            if proxy:
                session.proxies = proxy
            data = {
                "client_id": self.config.get("bot", "Client_Id"),
                "client_secret": self.config.get("bot", "Client_Secret"),
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.config.get("tool", "redirect_uri")
            }
            res = session.post(
                "https://discord.com/api/v9/oauth2/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if res.status_code != 200:
                self.log.error("OAuth token exchange failed", f"Status: {res.status_code}")
                return "Failed", 500
            acc_token = res.json().get("access_token")
            user_res = session.get(
                "https://discord.com/api/v9/users/@me",
                headers={"authorization": f"Bearer {acc_token}"}
            )
            user_id = user_res.json().get("id")
            join_res = session.put(
                f"https://discord.com/api/v9/guilds/{guild_id}/members/{user_id}",
                headers={
                    "authorization": f"Bot {self.config.get('bot', 'BotToken')}",
                    "Content-Type": "application/json"
                },
                json={"access_token": acc_token}
            )
            if join_res.status_code in [201, 204]:
                self.log.joined(f"User {user_id}")
                if self.auto_role and self.role_id:
                    role_res = session.put(
                        f"https://discord.com/api/v9/guilds/{guild_id}/members/{user_id}/roles/{self.role_id}",
                        headers={"authorization": f"Bot {self.config.get('bot', 'BotToken')}"}
                    )
                    if role_res.status_code in [200, 204]:
                        self.log.role(f"User {user_id}")
                        return "Joined + Role Assigned", 200
                return "Joined", 200
            else:
                self.log.error("Guild join failed", f"Status: {join_res.status_code}")
                return "Failed", 500
    def run_join(self, amount, invite_input, auto_role=False, role_id=None):
        if "discord.gg/" in invite_input:
            code = invite_input.split("discord.gg/")[-1].split("/")[0]
        elif invite_input.startswith("https://"):
            code = invite_input.rstrip("/").split("/")[-1]
        else:
            code = invite_input.strip()
        guild_id = fetch_guild(code, self.config, self.log)
        if not guild_id:
            self.log.error("Could not resolve guild ID from invite")
            return
        self.guild_id = guild_id
        self.auto_role = auto_role
        self.role_id = role_id
        token_file = self.config.get("tool", "token_file")
        if not os.path.exists(token_file):
            self.log.error("Token file not found", token_file)
            return
        with open(token_file, "r") as f:
            tokens = [l.strip() for l in f if l.strip()][:amount]
        if not tokens:
            self.log.error("No tokens found")
            return
        def worker(t):
            obj = Token(t, self.config, self.log)
            if obj.auth():
                self.log.oauth(f"{t[:50]}")
            else:
                self.log.error("OAuth failed", f"{t[:50]}")
            time.sleep(self.config.get("tool", "delay_between_join"))
        with ThreadPoolExecutor(max_workers=self.config.get("tool", "max_workers")) as pool:
            pool.map(worker, tokens)
    def banner(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        art = r"""
 _  _  ____  __  __    __  ____  _  _  ____  __    __   __    ____  _  _  ____ 
/ )( \(_  _)(  )(  )  (  )(_  _)( \/ )(_  _)/  \  /  \ (  )  / ___)/ )( \(___ \
) \/ (  )(   )( / (_/\ )(   )(   )  /   )( (  O )(  O )/ (_/\\___ \\ \/ / / __/
\____/ (__) (__)\____/(__) (__) (__/   (__) \__/  \__/ \____/(____/ \__/ (____)
"""
        for line in art.splitlines():
            print(self.log.center(gradient(line)))
        print(self.log.center(f"{Fore.CYAN}Bot Status:{Style.RESET_ALL} {Fore.GREEN}Online{Style.RESET_ALL}"))
        print()
        sep = f"{Fore.GREEN}|{Style.RESET_ALL}"
        print(f"      1 {sep} {Fore.WHITE}Join Members{Style.RESET_ALL}")
        print(f"      2 {sep} {Fore.WHITE}Exit{Style.RESET_ALL}")
        print(f"      3 {sep} {Fore.WHITE}Check Token Count{Style.RESET_ALL}")
        print()
    def start(self):
        set_title("UtilityToolsV2 | Oauth Joiner")
        flask_thread = threading.Thread(
            target=lambda: self.app.run(port=8080, debug=False, use_reloader=False),
            daemon=True
        )
        flask_thread.start()
        @self.bot.event
        async def on_ready():
            await self.commands.setup()
            self.ready.set()
        bot_thread = threading.Thread(
            target=lambda: self.bot.run(self.config.get("bot", "BotToken")),
            daemon=True
        )
        bot_thread.start()
        self.ready.wait()
        time.sleep(1)
        os.system('cls' if os.name == 'nt' else 'clear')
        while True:
            self.banner()
            choice = self.log.input("Choice")
            if choice == "1":
                try:
                    amt = int(self.log.input("Amount"))
                    invite = self.log.input("Invite Link or Code")
                    auto_role = self.log.confirm("Enable Auto-Role")
                    role_id = None
                    if auto_role:
                        role_id = self.log.input("Role ID")
                    self.run_join(amt, invite, auto_role, role_id)
                except ValueError:
                    self.log.error("Invalid amount")
                self.log.wait()
            elif choice == "2":
                sys.exit(0)
            elif choice == "3":
                token_file = self.config.get("tool", "token_file")
                cnt = 0
                if os.path.exists(token_file):
                    with open(token_file, "r") as f:
                        cnt = len([l for l in f if l.strip()])
                self.log.info(f"Total tokens: {cnt}")
                self.log.wait()
if __name__ == "__main__":
    app = Manager(Config())
    app.start()
