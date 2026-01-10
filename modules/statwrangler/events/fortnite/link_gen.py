import logging


# def get_image_url():
#     with open('/home/DiscordPi/code/discord_bots/r6-discord-bot/images/fortnite_img.url', "r")as file:
#         file=file.read().strip()

#     return file


async def generate_link(username):
    try:
        url = f'https://fortnitetracker.com/profile/all/{username}'
        #file = f"https://static.wikia.nocookie.net/logopedia/images/d/db/Fortnite_S1.svg/revision/latest?cb=20210330161743"
        return url    #, file
    except Exception as e:
        logging.warning(f'could not create the url {e}')
        return None, None , None
    