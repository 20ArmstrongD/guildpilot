from .botInit import on_Ready
from .intents import botstuff, intent
from .EnvCheck import checkEnvVar
from .keyHole import DISCORD_BOT_TOKEN
from .r6siege.r6siege_scrapper import get_r6siege_player_data
from .fortnite.fortnite_scrapper import get_fortnite_player_data
from .fortnite.link_gen import generate_link
from .username_proc import save_usernames, load_usernames, file_path
from .valorant.valorant_scraper import get_val_player_data
from .valorant.link_gen import generate_val_link


