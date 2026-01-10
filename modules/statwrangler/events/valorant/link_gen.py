import logging
import re

# def get_image_url():
#     with open('/home/DiscordPi/code/discord_bots/r6-discord-bot/images/fortnite_img.url', "r")as file:
#         file=file.read().strip()

#     return file


async def generate_val_link(username):
    try:
        
        match = re.match(r"([^#]+)#(\d{4})", username)
        if not match:
            raise ValueError("invalid Riot ID format. Expected 'username#1234'")
        
        username, playercode = match.groups()
        
        
        url = f"https://tracker.gg/valorant/profile/riot/{username}%23{playercode}/overview"
        return url
    except Exception as e:
        logging.warning(f'could not create the url {e}')
        return None, None , None
    
