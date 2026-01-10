from dotenv import load_dotenv
import os
import logging

def checkEnvVar():
    env_varibles = {
        "DISCORD_BOT_TOKEN" : os.getenv('DISCORD_BOT_TOKEN'),
        }

    for var_name, var_value in env_varibles.items():
        if var_value is None:
            try:
                logging.error(f'{var_name} is not set correctly in .env file')
                raise ValueError(f'{var_name} is not set correctly in .env file')
            except Exception as e:
                logging.error('Unable to do Enviorment variable value check')
        else:
            logging.info(f'{var_name} is ✅')

# Use for testing function by itself
# checkEnvVar()