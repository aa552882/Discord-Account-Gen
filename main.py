from typing             import List, Final, Dict, Union, Optional
from time               import sleep, strftime, time
from types              import MappingProxyType
from secrets            import token_urlsafe
from configparser       import ConfigParser
from threading          import Thread, Lock
from traceback          import format_exc
from os                 import listdir
from ctypes             import windll
from random             import choice
from rich               import print as rprint, prompt
from colorama           import Fore, init as colorama_init
from discord            import helpers, Discord

class Creator():
    def __init__(self) -> None:
        self.config_parser = ConfigParser()
        self.config_parser.read('config.ini')
        self.config: Final[Dict[str, Union[int, bool]]] = MappingProxyType({
            "ONLINE_DELAY": self.config_parser.getint('SETTINGS', 'ONLINE_DELAY'),
            "CHECK_DELAY": self.config_parser.getint('SETTINGS', 'CHECK_DELAY'),
            "CAPTCHA_THREADS": self.config_parser.getint('KEYS', 'CAPTCHA_THREADS'),
            "SET_HYPESQUAD_DELAY": self.config_parser.getint('SETTINGS', 'SET_HYPESQUAD_DELAY'),
            "SET_PFP_DELAY": self.config_parser.getint('SETTINGS', 'SET_PFP_DELAY'),

            "SET_HYPESQUAD": self.config_parser.getboolean('SETTINGS', 'SET_HYPESQUAD'),
            "SET_PFP": self.config_parser.getboolean('SETTINGS', 'SET_PFP'),
            "IGNORE_ERRORS_ON_PFP_AND_HYPESQUAD": self.config_parser.getboolean('SETTINGS', 'IGNORE_ERRORS_ON_PFP_AND_HYPESQUAD'),
            "REMOVE_CAPTCHA_THREAD_PRINTS": self.config_parser.getboolean('SETTINGS', 'REMOVE_CAPTCHA_THREAD_PRINTS'),
            "SOLVE_CAPTCHAS": self.config_parser.getboolean('SETTINGS', 'SOLVE_CAPTCHAS'),

            "INVITE": None if self.config_parser.get('SETTINGS', 'INVITE') == "none" else self.config_parser.get('SETTINGS', 'INVITE'),
        })
        self.status_colors: Final[Dict[str, str]] = MappingProxyType({
            "CREATED": Fore.LIGHTGREEN_EX,
            "CAPTCHA": Fore.LIGHTBLUE_EX,
            "ERROR": Fore.LIGHTRED_EX,
            "STARTING": Fore.LIGHTCYAN_EX,
            "INFO": Fore.LIGHTYELLOW_EX,
        })
        self.lock = Lock()
        self.images: Final[List[str]] = [image for image in listdir("images/") if image[-3:] in ["png", "jpg"]]
        self.unlocked: int = 0
        self.locked: int = 0
        self.captcha_threads: int = 0
        self.all_tokens: List[str] = self._get_all_tokens()

    def formatted_print(self, status: str, text: str, end: Optional[str] = "\n") -> None:
        current_time = strftime('%H:%M:%S')
        print(f"[{Fore.MAGENTA}{current_time}{Fore.RESET}] [{self.status_colors.get(status, Fore.LIGHTWHITE_EX)}{status}{Fore.RESET}] - {text}", end=end, flush=True)

    def _get_all_tokens(self) -> List[str]:
        with open("./tokens/unclaimed.txt", "r", encoding="utf-8") as unclaimed, \
            open("./tokens/mail_verified.txt", "r", encoding="utf-8") as mail_verified:
            return list(set(unclaimed.read().splitlines() + mail_verified.read().splitlines()))

    def mail_verify(self, proxy: str) -> None:
        if self.captcha_threads >= self.config["CAPTCHA_THREADS"]:
            if not self.config["REMOVE_CAPTCHA_THREAD_PRINTS"]:
                self.formatted_print("INFO", f"Waiting for captcha threads to decrease... ({self.captcha_threads}/{self.config['CAPTCHA_THREADS']})")
            sleep(2)
            return

        self.formatted_print("CAPTCHA", "Solving Captcha...")

        time_zero = time()
        captcha_key = None
        try:
            self.captcha_threads += 1
            captcha_key = helpers.solve_captcha(proxy)
            self.captcha_threads -= 1
        except:
            self.formatted_print("ERROR", format_exc())
            self.captcha_threads -= 1
            return

        self.formatted_print("CAPTCHA", f"Got Captcha Key: {captcha_key[:32]}... in {(time() - time_zero):.2f}s")

        mail = helpers.KopeechkaEmail()

        password = token_urlsafe(20)
        email = mail.email_data.mail

        self.formatted_print("INFO", f"Email: {email} - Password: {password}")

        username = helpers.get_username()

        discockler = Discord(
            proxy=proxy,
            email_verify=True
        )

        register = discockler.register(
            username=username,
            captcha_key=captcha_key,
            email=email,
            password=password,
            invite=self.config["INVITE"]
        )

        if not register:
            return

        if self.config["ONLINE_DELAY"] > 0:
            self.formatted_print("INFO", f"Waiting {self.config['ONLINE_DELAY']}s before connecting to ws...")
            sleep(self.config["ONLINE_DELAY"])

        discockler.open_websocket()

        self.formatted_print("INFO", f"Waiting {self.config['CHECK_DELAY']}s to prevent skipping delayed locks...")

        sleep(self.config["CHECK_DELAY"])

        if discockler.is_locked():
            self.locked += 1
            self.formatted_print("ERROR", f"Locked: {discockler.token}")
            with self.lock:
                with open("./tokens/mail_locked.txt", "a+", encoding="utf-8") as file:
                    file.write(discockler.token + "\n")
        else:
            self.formatted_print("CREATED", f"Unlocked: {discockler.token}")

            with self.lock:
                with open("./tokens/mail_verified_pending.txt", "a+", encoding="utf-8") as file:
                    file.write(f"{email}:{password}:{discockler.token}\n")

            self.formatted_print("INFO", "Waiting for email...")

            url = mail.get_letter()

            self.formatted_print("INFO", f"Email received: {url[:20]}...{url[-20:]}")

            everified = discockler.verify_email(url)

            if not everified:
                return

            self.formatted_print("CREATED", f"Email verified: {discockler.token}")

            if self.config["SET_HYPESQUAD"]:

                if self.config["SET_HYPESQUAD_DELAY"] > 0:
                    self.formatted_print("INFO", f"Waiting {self.config['SET_HYPESQUAD_DELAY']}s before setting hypesquad...")
                    sleep(self.config["SET_HYPESQUAD_DELAY"])

                sethype = discockler.set_hypesquad()

                if not sethype:
                    if not self.config["IGNORE_ERRORS_ON_PFP_AND_HYPESQUAD"]:
                        return
                    self.formatted_print("ERROR", f"Error setting hypesquad: {discockler.token}")
                else:
                    self.formatted_print("INFO", f"Set Hypesquad: {discockler.token}")

            if self.config["SET_PFP"]:
                if self.config["SET_PFP_DELAY"] > 0:
                    self.formatted_print("INFO", f"Waiting {self.config['SET_PFP_DELAY']}s before setting pfp...")
                    sleep(self.config["SET_PFP_DELAY"])

                setpfp = discockler.set_profile_picture(path=f"images/{choice(self.images)}")

                if not setpfp:
                    if not self.config["IGNORE_ERRORS_ON_PFP_AND_HYPESQUAD"]:
                        return
                    self.formatted_print("ERROR", f"Error setting pfp: {discockler.token}")
                else:
                    self.formatted_print("INFO", f"Set PFP: {discockler.token}")

            self.unlocked += 1

            with self.lock:
                with open("./tokens/mail_verified.txt", "a+", encoding="utf-8") as file:
                    file.write(f"{email}:{password}:{discockler.token}\n")
            # remove from tokens_mail_verified_pending.txt
            with self.lock:
                with open("./tokens/mail_verified_pending.txt", "r", encoding="utf-8") as file:
                    lines = file.readlines()
                with open("./tokens/mail_verified_pending.txt", "w", encoding="utf-8") as file:
                    for line in lines:
                        if line.strip("\n") != f"{email}:{password}:{discockler.token}":
                            file.write(line)

    def unclaimed(self, proxy: str) -> None:
        if self.captcha_threads >= self.config["CAPTCHA_THREADS"]:
            if not self.config["REMOVE_CAPTCHA_THREAD_PRINTS"]:
                self.formatted_print("INFO", f"Waiting for captcha threads to decrease... ({self.captcha_threads}/{self.config['CAPTCHA_THREADS']})")
            sleep(2)
            return

        self.formatted_print("CAPTCHA", "Solving Captcha...\n")

        captcha_key = None
        try:
            self.captcha_threads += 1
            captcha_key = helpers.solve_captcha(proxy)
            self.captcha_threads -= 1
        except:
            self.formatted_print("ERROR", format_exc())
            self.captcha_threads -= 1
            return

        self.formatted_print("CAPTCHA", f"Captcha Key: {captcha_key[:32]}...")

        username = helpers.get_username()

        discockler = Discord(
            proxy=proxy,
            email_verify=True
        )

        register = discockler.register(
            username=username,
            captcha_key=captcha_key,
            invite=self.config["INVITE"]
        )

        if not register:
            return

        if self.config["ONLINE_DELAY"] > 0:
            self.formatted_print("INFO", f"Waiting {self.config['ONLINE_DELAY']}s before connecting to ws...")
            sleep(self.config["ONLINE_DELAY"])

        discockler.open_websocket()

        self.formatted_print("INFO", f"Waiting {self.config['CHECK_DELAY']}s to prevent skipping delayed locks...")

        sleep(self.config["CHECK_DELAY"])

        if discockler.is_locked():
            self.locked += 1
            self.formatted_print("ERROR", f"Locked: {discockler.token}")
            with self.lock:
                with open("./tokens/locked.txt", "a+", encoding="utf-8") as file:
                    file.write(discockler.token + "\n")
        else:
            self.unlocked += 1
            self.formatted_print("CREATED", f"Unlocked: {discockler.token}")

            with self.lock:
                with open("./tokens/unclaimed.txt", "a+", encoding="utf-8") as file:
                    file.write(discockler.token + "\n")

    def calculate_unlock_percentage(self) -> int:
        if self.unlocked + self.locked == 0:
            return 0
        return (self.unlocked / (self.unlocked + self.locked)) * 100

    @staticmethod
    def format_time(seconds: int) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

    def update_title(self) -> None:
        time_zero = time()
        while True:
            unlock_percentage = self.calculate_unlock_percentage()
            elapsed_time = time() - time_zero
            title = f"U: {self.unlocked} - L: {self.locked} - ({self.unlocked + self.locked}) - Unlocked %: {unlock_percentage:.2f}% - Elapsed: {self.format_time(elapsed_time)} - Threads/Max Threads: {self.captcha_threads}/{self.config['CAPTCHA_THREADS']}"
            if self.unlocked > 0:
                title = f"{title} - Unlocked/h: {int(self.unlocked / (elapsed_time / 3600))}"
            windll.kernel32.SetConsoleTitleW(title)
            sleep(0.1)

    def worker(self, func) -> None:
        while True:
            try:
                func(proxy=helpers.get_proxy())
            except:
                self.formatted_print("ERROR", format_exc())

    def chunkify(self, old_list: List[str], amount: int) -> List[List[str]]:
        chunk_size = len(old_list) // amount
        remainder = len(old_list) % amount
        start = 0
        chunks = [] # splitting the list into smaller chunks of equal size
        for _ in range(amount):
            end = start + chunk_size + (1 if _ < remainder else 0)
            chunks.append(old_list[start:end])
            start = end
        return chunks

    def friend_req(self, proxy: str) -> None:
        friend_threads = prompt.IntPrompt.ask("Threads")
        discord = Discord(proxy)
        with open("scraped/usernames.txt", "r", encoding="utf-8") as file:
            all_names = file.read().splitlines()
        chunks = self.chunkify(self.all_tokens, friend_threads)
        all_names = self.chunkify(all_names, friend_threads)

        for name_chunk, token_chunk in zip(all_names, chunks):
            Thread(
                target=discord.send_fr,
                args=(
                    name_chunk,
                    token_chunk,
                    self.config["SOLVE_CAPTCHAS"],
                )).start()

    def join(self, proxy: str) -> None:
        join_threads = prompt.IntPrompt.ask("Threads")
        mode = prompt.Prompt.ask("Mode", choices=["single", "multi"])
        delay = prompt.FloatPrompt.ask("Delay between joins?")

        with open("scraped/invites.txt", "r", encoding="utf-8") as file:
            invites = file.read().splitlines()
        discord = Discord(proxy)

        chunks = self.chunkify(self.all_tokens, join_threads)
        for chunk in chunks:
            Thread(
                target=discord.join_server,
                args=(
                    self.config["INVITE"] if mode == "single" else invites,
                    chunk,
                    mode,
                    delay,
                    self.config["SOLVE_CAPTCHAS"],
                )).start()

if __name__ == "__main__":
    colorama_init(autoreset=True)
    creator = Creator()
    options = MappingProxyType({
        1: creator.mail_verify,
        2: creator.unclaimed,
        3: creator.join,
        4: creator.friend_req,
    })
    rprint("Choose an option:\n\r1: Gen EV\n\r2: Gen UC\n\r3: Join Server\n\r4: Mass Friend Request")
    CHOICE = prompt.IntPrompt.ask("Choice", choices=map(str, options.keys()), show_choices=False, default=2)
    if options[CHOICE] in [creator.mail_verify, creator.unclaimed]:

        THREADS_AMOUNT = prompt.IntPrompt.ask("Threads")
        Thread(target=creator.update_title).start()
        for i in range(THREADS_AMOUNT):
            Thread(
                target=creator.worker,
                args=(options[CHOICE],)
            ).start()
    else:
        func = options[CHOICE]
        if "proxy" in func.__code__.co_varnames:
            func(proxy=helpers.get_proxy())
        else:
            func()
    