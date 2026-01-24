# run_both.py
import os
import subprocess
import sys

def run_instance(name: str, token: str):
    env = os.environ.copy()
    env["DISCORD_TOKEN"] = token
    env["BOT_NAME"] = name
    return subprocess.Popen([sys.executable, "-m", "modules.bot.main"], env=env)

if __name__ == "__main__":
    public = run_instance("public", os.environ["PUBLIC_DISCORD_TOKEN"])
    dev = run_instance("dev", os.environ["DEV_DISCORD_TOKEN"])

    public.wait()
    dev.wait()
