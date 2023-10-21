from time           import strftime, time, sleep
from json           import dumps
from random         import randint, choice
from secrets        import token_urlsafe, token_hex
from typing         import Optional, Final, Dict, Any, List, Union
from re             import compile as rcompile
from colorama       import Fore
from requests       import get as rget
from tls_client     import Session as TLS_Session
from websocket      import create_connection
from discord        import helpers, exceptions

def formatted_print(status: str, text: str) -> None:
    status_colors: Final[Dict[str, str]] = {
        "CREATED": Fore.LIGHTGREEN_EX,
        "CAPTCHA": Fore.LIGHTBLUE_EX,
        "ERROR": Fore.LIGHTRED_EX,
        "STARTING": Fore.LIGHTCYAN_EX,
        "INFO": Fore.LIGHTYELLOW_EX,
    }
    current_time = strftime('%H:%M:%S')
    print(f"[{Fore.MAGENTA}{current_time}{Fore.RESET}] [{status_colors.get(status, Fore.LIGHTWHITE_EX)}{status}{Fore.RESET}] - {text}", flush=True)

build_pattern = rcompile(r'\(t="(\d*)"\)')
asset_pattern = rcompile(r'assets/+([a-z0-9]+)\.js')

TIME_ZERO: Final[float] = time()

asset_index = asset_pattern.findall(rget("https://ptb.discord.com/login", timeout=30).text)[-2]
correct_asset = 'https://ptb.discord.com/assets/' + asset_index + '.js'

with rget(correct_asset, stream=True, timeout=30) as response:
    BUILD_NUMBER = None
    for chunk in response.iter_content(chunk_size=65536):
        if chunk:
            chunk_str = chunk.decode('utf-8', errors='ignore')

            found = build_pattern.search(chunk_str)
            if found:
                BUILD_NUMBER = int(found.group(1))
                break
print(f"Fetched build number: {BUILD_NUMBER} in {time() - TIME_ZERO:.2f}s")

class Discord:
    def __init__(self, proxy: str, email_verify: Optional[bool] = True) -> None:
        self._session = TLS_Session(client_identifier="chrome117", random_tls_extension_order=True)
        self.browser = token_urlsafe(8)

        self._session.headers = {
            'authority': 'ptb.discord.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'origin': 'https://ptb.discord.com',
            'pragma': 'no-cache',
            'referer': 'https://ptb.discord.com/',
            'sec-ch-ua': '"Not/A)Brand";v="99", "Google Chrome";v="117", "Chromium";v="117"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
        }

        self._session.proxies = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}",
        }

        # session data
        self.fingerprint = None
        self.token = None
        self.email_verify = email_verify

        self.tracking = {
            "x-super-properties": helpers.build_tracking(build_number=BUILD_NUMBER)}

        self._landing()  # this will gather cookies and fingerprint

    def _landing(self) -> None:
        headers = {
            **self.tracking
        }

        if self.email_verify:
            headers['x-context-properties'] = 'eyJsb2NhdGlvbiI6IlJlZ2lzdGVyIn0='

        data = self._session.get(
            'https://ptb.discord.com/api/v9/experiments',
            headers=headers
        )
        if data.status_code != 200:
            raise exceptions.DiscordHTTPException(
                f"Landing: Failed request: {data.status_code} {data.text}")

        self.fingerprint = data.json()['fingerprint']

    def register(self, username: str, captcha_key: str, password: str = None, email: str = None, invite: Optional[str] = None) -> bool:
        try:
            """Register account
            :param captcha_key: Captcha Key
            :param username: Username to use
            :param password: Optional: Password to use
            :param email: Optional: Email to use
            :param invite: Optional: Invite to use
            """

            if email and password:
                payload = {
                    "fingerprint": self.fingerprint,
                    "email": email,
                    "username": username,
                    "global_name": username,
                    "password": password,
                    "invite": invite,
                    "consent": True,
                    "date_of_birth": f"{randint(1990, 1999)}-{randint(1, 12)}-{randint(1, 12)}",
                    "gift_code_sku_id": None,
                    "promotional_email_opt_in": False,
                    "unique_username_registration": True
                }
            else:
                payload = {
                    "consent": True,
                    "fingerprint": self.fingerprint,
                    "global_name": username,
                    "unique_username_registration": True,
                }

            self._session.post(
                'https://ptb.discord.com/api/v9/auth/register',
                headers={
                    "x-fingerprint": self.fingerprint,
                    **self.tracking
                },
                json=payload
            )

            data = self._session.post(
                'https://ptb.discord.com/api/v9/auth/register',
                headers={
                    "x-fingerprint": self.fingerprint,
                    "x-captcha-key": captcha_key,
                    **self.tracking
                },
                json=payload
            )
            if data.status_code != 201:
                raise exceptions.DiscordHTTPException(
                    f"Register: Failed request: {data.status_code} {data.text}")

            self.token = data.json()['token']
            return True
        except Exception as exception:
            formatted_print("ERROR", f"Register Err: {exception}")
            return False

    def verify_email(self, url: str) -> bool:
        try:
            data = self._session.get(
                url
            )
            if data.status_code != 302:
                raise exceptions.DiscordHTTPException(
                    f"EmailVerify: Failed request: {data.status_code} {data.text}")


            location = data.headers.get(
                "Location"
            )
            if data.status_code != 200:
                raise exceptions.DiscordHTTPException(
                    f"EmailVerify: Failed request: {data.status_code} {data.text}")

            token = location.split('=')[1]

            data = self._session.post(
                'https://ptb.discord.com/api/v9/auth/verify',
                headers={
                    "authorization": self.token,
                    "x-fingerprint": self.fingerprint,
                    "x-super-properties": helpers.build_tracking(build_number=BUILD_NUMBER)
                },
                json={
                    "token": token
                }
            )
            if data.status_code != 200:
                raise exceptions.DiscordHTTPException(
                    f"EmailVerify: Failed request: {data.status_code} {data.text}")

            self.token = data.json()['token']
            return True
        except Exception as exception:
            formatted_print("ERROR", f"EmailVerify Err: {exception}")
            return False

    def set_profile_picture(self, path: str) -> bool:
        try:
            noised_pfp = helpers.get_image_base64(path)

            data = self._session.patch(
                'https://ptb.discord.com/api/v9/users/@me',
                headers={
                    "referer": "https://ptb.discord.com/channels/@me",
                    "authorization": self.token,
                    "x-super-properties": helpers.build_tracking(build_number=BUILD_NUMBER)
                },
                json={
                    "avatar": noised_pfp
                }
            )
            if data.status_code != 200:
                raise exceptions.DiscordHTTPException(
                    f"ProfilePicture: Failed request: {data.status_code} {data.text}")
            return True
        except Exception as exception:
            formatted_print("ERROR", f"ProfilePicture Err: {exception}")
            return False

    def set_hypesquad(self) -> bool:
        try:
            data = self._session.post(
                'https://ptb.discord.com/api/v9/hypesquad/online',
                headers={
                    "authorization": self.token,
                    "x-super-properties": helpers.build_tracking(build_number=BUILD_NUMBER)
                },
                json={
                    "house_id": randint(0, 2)
                }
            )
            if data.status_code != 204:
                raise exceptions.DiscordHTTPException(
                    f"Hypesquad: Failed request: {data.status_code} {data.text}")
            return True
        except Exception as exception:
            formatted_print("ERROR", f"Hypesquad Err: {exception}")
            return False

    def open_websocket(self) -> None:
        websocket = create_connection("wss://gateway.discord.gg/?encoding=json&v=9&compress=zlib-stream",
            header=[
                "User-Agent: Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/116.0",
                "Origin: https://ptb.discord.com"
            ]
        )
        websocket.send(
            dumps(
                {
                    "op": 2,
                    "d": {
                        "token": self.token,
                        "capabilities": 16381,
                        "properties": helpers.build_tracking(encrypt=False),
                        "presence": {
                            "status": "dnd",
                            "since": 0,
                            "activities": [],
                            "afk": False
                        },
                        "compress": False,
                        "client_state": {
                            "guild_versions": {},
                            "highest_last_message_id": "0",
                            "read_state_version": 0,
                            "user_guild_settings_version": -1,
                            "user_settings_version": -1,
                            "private_channels_version": "0",
                            "api_code_version": 0
                        }
                    }
                }
            )
        )

    def is_locked(self) -> bool:
        try:
            data = self._session.get(
                'https://ptb.discord.com/api/v9/users/@me/burst-credits',
                headers = {
                    "Authorization": self.token
                }
            )
            if data.status_code != 200:
                return True
            return False
        except Exception as exception:
            formatted_print("ERROR", f"IsLocked Err: {exception}")
            return True
