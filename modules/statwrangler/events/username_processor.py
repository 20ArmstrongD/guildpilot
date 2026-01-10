import json

<<<<<<< HEAD
file_path = "/home/bot-vm/code/guildpilot/modules/statwrangler/json/usernames.json"
=======
file_path = "/home/bot-vm/code/guildpilot/modules/statwrangler/json/usernames.json
>>>>>>> ff4c745 (ported over original stats wrangler code)

def load_usernames():
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return{}

def save_usernames(usernames):
    with open(file_path, "w") as file:
        json.dump(usernames, file, indent=4)
        
        