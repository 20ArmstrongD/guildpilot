import logging
import asyncio
import  random
from pyppeteer import launch

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%I:%M:%S %p'  # 12-hour clock with AM/PM
)

async def get_fortnite_player_data(username):
    try:
        # Launch a headless browser
        url = f'https://fortnitetracker.com/profile/all/{username}'
        browser = await launch(
            headless=False,
            executablePath='/usr/bin/chromium-browser',
            args=['--no-sandbox']
        )
        page = await browser.newPage()
        await page.goto(url, {'timeout': 60000})
        await page.waitForSelector("span", {'timeout': 60000})  


        # Move mouse randomly
        await page.mouse.move(random.randint(100, 400), random.randint(100, 400))
        await asyncio.sleep(random.uniform(1, 3))

        # Scroll down
        await page.evaluate('window.scrollBy(0, window.innerHeight)')
        await asyncio.sleep(random.uniform(2, 4))


        # Initialize variables with default values
        kd = level = playtime = user_profile_img = "N/A"

        try:
            kd = await page.evaluate('''() => {
                const xpath = "//*[@id='overview']/div[2]/div/div[1]/div/div[1]/div[3]/div[2]/div[2]/div";
                const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                const element = result.singleNodeValue;
                return element ? element.innerText : "N/A";
            }''')

            level = await page.evaluate('''() => {
                const xpath = "//*[@id='overview']/div[2]/div/div[1]/header/div/div[2]/text()";
                const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                const element = result.singleNodeValue;
                return element ? element.innerText : "N/A";
            }''')

            playtime = await page.evaluate('''() => {
                const xpath = "//*[@id='overview']/div[2]/div/div[1]/header/div/div[1]/text()";
                const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                const element = result.singleNodeValue;
                return element ? element.textContent.trim() : "N/A";
            }''')
        except Exception as e:
            logging.warning(f"Failed to scrape player stats for {username}: {e}")

        try:
            user_profile_img = await page.evaluate('''() => {
                const element = document.querySelector(".profile-header-avatar");
                return element ? element.src : "N/A";
            }''')
        except Exception as e:
            logging.warning(f"Failed to scrape profile image for {username}: {e}")

        logging.info(f"{username} Fortnite Data Successfully Retrieved!")
        logging.info(f"    * KD: {kd}\n    * Level: {level}\n    * Playtime: {playtime}\n    * Profile Pic: {user_profile_img}")

        return kd, level, playtime, user_profile_img

    except Exception as e:
        logging.error(f"Error in Pyppeteer: {e}")
        return "N/A", "N/A", "N/A", "N/A"

    finally:
        if browser:
            await browser.close()
