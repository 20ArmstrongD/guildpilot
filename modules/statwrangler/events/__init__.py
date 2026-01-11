from .bot_init import on_Ready
from .intents import botstuff, intent
from .env_check import get_env_vars
#from .key_hole import DISCORD_BOT_TOKEN
from .r6.r6_scraper import get_r6siege_player_data
from .fortnite.fort_scraper import get_fortnite_player_data
from .fortnite.link_gen import generate_link
from .username_processor import save_usernames, load_usernames, file_path
from .valorant.val_scraper import get_val_player_data
from .valorant.link_gen import generate_val_link


