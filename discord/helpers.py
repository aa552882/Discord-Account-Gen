from base64         import b64encode
from io             import BytesIO
from json           import dumps
from random         import choice, randint
from secrets        import token_hex
from time           import sleep
from configparser   import ConfigParser
from typing         import Final, Dict, Union, List, Optional
from types          import MappingProxyType
from functools      import wraps
from PIL            import Image
from kopeechka      import MailActivations
from requests       import get as rget, post as rpost
from discord        import exceptions
import capsolver

config_parser = ConfigParser()
config_parser.read('config.ini')

config_data: Dict[str, Union[int, bool, List[str]]] = {
    "HCOPTCHA_API_KEYS": config_parser.get("KEYS", 'HCOPTCHA_API_KEY').split(","),
    "KOPECHKA_API_KEY": config_parser.get("KEYS", 'KOPECHKA_API_KEY'),
    "CAPSOLVER_API_KEY": config_parser.get("KEYS", "CAPSOLVER_API_KEY"),
    "CAPMONSTER_API_KEY": config_parser.get("KEYS", "CAPMONSTER_API_KEY"),
    "KOPECHKA_MAIL_TYPE": config_parser.get("KEYS", 'KOPECHKA_MAIL_TYPE'),
    "SOLVER": config_parser.get("KEYS", 'SOLVER').lower(),
    "COMPRESS_PFP_RATIO": config_parser.getfloat("SETTINGS", "COMPRESS_PFP_RATIO"),
    "IMPLEX_SERVER": config_parser.get("KEYS", "IMPLEX_SERVER"),
    "TRACKING": config_parser.get("SETTINGS", "TRACKING")
}

CONFIG: Final[Dict[str, Union[int, bool, float]]] = MappingProxyType(config_data)

KOPEECHKA = None
if CONFIG["KOPECHKA_API_KEY"] != "none":
    KOPEECHKA = MailActivations(api_token=CONFIG["KOPECHKA_API_KEY"])

with open("usernames.txt", "r", encoding="utf-8") as file:
    USERNAMES: Final[List[str]] = file.read().splitlines()

with open("proxies.txt", "r", encoding="utf-8") as file:
    PROXIES: Final[List[str]] = file.read().splitlines()

def build_tracking(build_number: Optional[int] = 237546, encrypt: Optional[bool] = True) -> Union[dict[str, str], str]:
    payload = {"os": "Windows", "browser": "Chrome", "device": "", "system_locale": "en-US",
               "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
               "browser_version": "117.0.0.0", "os_version": "10", "referrer": "", "referring_domain": "",
               "referrer_current": "", "referring_domain_current": "", "release_channel": "stable",
               "client_build_number": build_number, "client_event_source": None}
    if encrypt:
        return b64encode(dumps(payload, separators=(',', ':')).encode("ascii")).decode("ascii")
    return payload

def solve_captcha(proxy: str, sitekey: Optional[str] = "4c672d35-0701-42b2-88c3-78380b0db560") -> str:
    if CONFIG["SOLVER"] == "hcoptcha":
        key = choice(CONFIG["HCOPTCHA_API_KEYS"])
        try:
            task = rpost(
                'https://api.hcoptcha.online/api/createTask',
                timeout=30,
                json={
                    "api_key": key,
                    "task_type": "hcaptchaEnterprise",
                    "data": {
                        "sitekey": sitekey,
                        "proxy": proxy,
                        "host": "discord.com"
                    }
                }
            ).json()
            if task['error']:
                raise Exception(f"Failed to create task: {task['message']}")

            task = task['task_id']

            result = rpost(
                'https://api.hcoptcha.online/api/getTaskData',
                timeout=30,
                json={
                    "api_key": key,
                    "task_id": task
                }
            ).json()

            while result['task']['state'] == "processing":
                result = rpost(
                    'https://api.hcoptcha.online/api/getTaskData',
                    timeout=30,
                    json={
                        "api_key": key,
                        "task_id": task
                    }
                ).json()
                sleep(2)
            if result['task']['state'] == "error":
                raise Exception("Failed to solve")
            return result['task']['captcha_key']
        except Exception as exception:
            raise Exception(f"Failed to solve: {exception}")
    elif CONFIG["SOLVER"] == "implex":
        try:
            server = f"{CONFIG['IMPLEX_SERVER'].replace('01', f'0{randint(1,3)}')}"
            headers = {"Content-Type": "application/json"}
            
            task = rpost(
                f"{server}/api/task/new",
                timeout=30,
                json = {
                    "domain": "discord.com",
                    "site_key": sitekey,
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                    "proxy": f"http://{proxy}",
                    "task_type": 0,
                    "invisible": False,
                    "a11y_tfe": True,
                    "turbo": True,
                    "turbo_st": 5000
                },
                headers=headers
            )
            if not task.status_code == 200:
                raise Exception(f"Failed to create task: {task.status_code}")

            task = task.json()["data"][0]["id"]

            result = rget(
                f"{server}/api/task/{task}",
                timeout=30,
                headers=headers
            )
            if not result.status_code == 200:
                raise Exception(f"Failed to get results: {result.status_code}")

            data = result.json()["data"]

            while data["status"] == 0: #Solving
                data = rget(
                    f"{server}/api/task/{task}",
                    timeout=30,
                    headers=headers
                ).json()["data"]
                sleep(2)

            if data["status"] == 2: #Error
                raise Exception(f"Failed to solve (Task: {task})")
            return data["token"]
        except Exception as exception:
            raise Exception(f"Failed to solve: {exception}")
    elif CONFIG["SOLVER"] == "capsolver":
        capsolver.api_key = CONFIG["CAPSOLVER_API_KEY"]
        solution = capsolver.solve({
            "type": "HCaptchaTurboTask",
            "websiteKey": sitekey,
            "websiteURL": "https://ptb.discord.com/",
            "proxy": proxy,
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        })

        return solution['gRecaptchaResponse']
    elif CONFIG["SOLVER"] == "capmonster":
        try:
            task = rpost(
                "https://api.capmonster.cloud/createTask",
                timeout=30,
                json={
                    "clientKey": CONFIG["CAPMONSTER_API_KEY"],
                    "task": {
                        "type": "HCaptchaTask",
                        "websiteURL": "https://ptb.discord.com/",
                        "websiteKey": sitekey,
                        "proxyType": "http", #if this doesnt work change to https (https://zennolab.atlassian.net/wiki/spaces/APIS/pages/1203240988/HCaptchaTask+hCaptcha+puzzle+solving)
                        "proxyLogin": proxy.split(":")[0],
                        "proxyPassword": proxy.split(":")[1].split("@")[0],
                        "proxyAddress": proxy.split("@")[1].split(":")[0],
                        "proxyPort": proxy.split("@")[1].split(":")[1],
                        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                    },
                }
            ).json()
            if task["errorId"] == "1":
                raise Exception(f"Failed to create task: {task['errorCode']}")

            task = task['taskId']

            result = rpost(
                "https://api.capmonster.cloud/getTaskResult",
                timeout=30,
                json={
                    "clientKey": CONFIG["CAPMONSTER_API_KEY"],
                    "taskId": task
                }
            ).json()
            while result["status"] == "processing" and result.get("errorId") != 1:
                result = rpost(
                    'https://api.capmonster.cloud/getTaskResult',
                    timeout=30,
                    json={
                        "clientKey": CONFIG["CAPMONSTER_API_KEY"],
                        "taskId": task
                    }
                ).json()
                sleep(2)
            if result["errorCode"] is not None:
                raise Exception(f"Failed to solve: {result['errorDescription']}")
            return result["solution"]["gRecaptchaResponse"]
        except Exception as exception:
            raise Exception(f"Failed to solve: {exception}")

class KopeechkaEmail:
    def __init__(self):
        self.email_data = None

        self._get_email()

    def _get_email(self):
        self.email_data = KOPEECHKA.mailbox_get_email(site="discord.com", mail_type=CONFIG["KOPECHKA_MAIL_TYPE"])

    def get_letter(self):
        letter = False
        retries = 0
        while not letter:
            retries += 1
            if retries > 20:
                raise exceptions.ExceededMailRetries(f"Failed to get letter after {retries} retries")
            try:
                sleep(2)
                data = KOPEECHKA.mailbox_get_message(full=1, task_id=self.email_data.id)
                fullmsg = str(data.fullmessage)
                letter = True
            except:
                pass
        verify_url = fullmsg.split('bgcolor="#5865f2"><a href="')[1].split('"')[0]
        return verify_url

def cache_wrapper(func):
    cache = {}
    @wraps(func)
    def wrapper(*args, **kwargs):
        key = str(args) + str(kwargs)

        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    return wrapper

@cache_wrapper #does this even help? idk, maybe
def get_image_base64(path: str):
    with Image.open(path) as image:
        resized_image = image.copy()
        resized_image.thumbnail((image.width * CONFIG["COMPRESS_PFP_RATIO"], image.height * CONFIG["COMPRESS_PFP_RATIO"]))

        image_buffer = BytesIO()

        resized_image.save(image_buffer, format="PNG")
        image_data = image_buffer.getvalue()

    encoded_image = b64encode(image_data).decode("utf-8")
    image_format = path.split(".")[-1].upper()
    data_url = f"data:image/{image_format};base64,{encoded_image}"

    return data_url

def get_proxy():
    return choice(PROXIES).replace('{sessionid}', token_hex(4))

def get_username():
    return choice(USERNAMES) + token_hex(1)
