import logging
import asyncio
from pyppeteer import launch
import re


# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%I:%M:%S %p",  # 12-hour clock with AM/PM
)


async def get_val_player_data(username):
    browser = None
    rank = ranked_kd = rank_img = None  # Initialize variables to avoid undefined errors

    try:
        
        match = re.match(r"([^#]+)#(\d{4})", username)
        if not match:
            raise ValueError("invalid Riot ID format. Expected 'username#1234'")
        
        username, playercode = match.groups()
        
        # Launch a headless browser
        url = f"https://tracker.gg/valorant/profile/riot/{username}%23{playercode}/overview"
        browser = await launch(
            headless=True,
            executablePath="/usr/bin/chromium-browser",
            args=["--no-sandbox"],
        )
        page = await browser.newPage()

        # Set a longer timeout if needed
        await page.goto(url, {"timeout": 60000})

        await page.waitForSelector("span", {"timeout": 60000})  # Wait for any span tag

        # Extract data using JavaScript evaluation
        
        # Extract KD
        kd = await page.evaluate(
    '''() => {
        const xpath = "//span[contains(text(), 'KD')]/following-sibling::span/span";
        const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        return result ? result.textContent.trim() : null;
    }'''
)

        # Extract Level
        level_element = await page.querySelector(
            "#app div[2] div[3] div main div[3] div[2] div[2] div[2] div[1] div div[2] div[2] div div div div[1] span[2]"
        )
        level = await level_element.getProperty("textContent") if level_element else None

        # Extract User Profile Image
        user_img_element = await page.querySelector(".user-avatar__image")
        user_profile_img = (
            await user_img_element.getProperty("src") if user_img_element else None
        )

        # Try to extract ranked data
        try:
            rank_element = await page.querySelector(
                "#app div[2] div[3] div main div[3] div[2] div[2] div[2] div[1] div[1] div[2] div[2] div div[1] div div[1] span[2]"
            )
            rank = await rank_element.getProperty("textContent") if rank_element else None

            ranked_kd_element = await page.querySelector(
                "#app div[2] div[3] div main div[3] div[2] div[2] div[2] div[1] div[1] div[3] div[2] div div[2] span[2] span"
            )
            ranked_kd = (
                await ranked_kd_element.getProperty("textContent")
                if ranked_kd_element
                else None
            )

            rank_img_element = await page.querySelector(
                "#app div[2] div[3] div main div[3] div[2] div[2] div[2] div[1] div[1] div[2] div[2] div div[1] img"
            )
            rank_img = (
                await rank_img_element.getProperty("src") if rank_img_element else None
            )

        except Exception as e:
            logging.warning("Unable to retrieve ranked data")

        # Log extracted data
        elements = {
            "KD": kd,
            "Level": level,
            "Rank": rank,
            "Ranked KD": ranked_kd,
        }
        img_elements = {"Player Profile Pic": user_profile_img, "Ranked Image": rank_img}

        logging.info(f"{username} Siege Data Successfully Found!")
        for key, value in elements.items():
            if value:
                logging.info(f"    *    {key}: {value}")
        for key, value in img_elements.items():
            if value and len(value) > 10:
                logging.info(f"    *    {key}: URL has been grabbed")

        return kd, level, rank, ranked_kd, user_profile_img, rank_img

    except Exception as e:
        logging.error(f"Error in Pyppeteer at line 107: {e}")
        return None, None, None, None, None, None  # Return None values on error

    finally:
        if browser:
            await browser.close()  # Ensure the browser closes



