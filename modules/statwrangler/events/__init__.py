from .bot_init import on_ready_bot as on_ready_bot
from .intents import botstuff as botstuff, intent as intent
from .env_check import get_env_vars as get_env_vars
#from .key_hole import DISCORD_BOT_TOKEN
from .r6.r6_scraper import get_r6siege_player_data as get_r6siege_player_data
from .fortnite.fort_scraper import get_fortnite_player_data as get_fortnite_player_data
from .fortnite.link_gen import generate_link as generate_link
from .username_processor import save_usernames as save_usernames, load_usernames as load_usernames, file_path as file_path
from .valorant.val_scraper import get_val_player_data as get_val_player_data
from .valorant.link_gen import generate_val_link as generate_val_link


