import asyncio
import logging
import random

from playwright.async_api import async_playwright

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%I:%M:%S %p",
)

CHROMIUM_PATH = "/usr/bin/chromium-browser"


async def get_fortnite_player_data(username: str):
    browser = None

    try:
        url = f"https://fortnitetracker.com/profile/all/{username}"

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )
            page = await browser.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            # Rough equivalent to "waitForSelector('span')"
            await page.wait_for_selector("span", timeout=60_000)

            # Move mouse randomly
            await page.mouse.move(random.randint(100, 400), random.randint(100, 400))
            await asyncio.sleep(random.uniform(1, 3))

            # Scroll down
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(random.uniform(2, 4))

            # Defaults
            kd = level = playtime = user_profile_img = "N/A"

            # --- Stats via XPath ---
            try:
                kd_xpath = "//*[@id='overview']/div[2]/div/div[1]/div/div[1]/div[3]/div[2]/div[2]/div"
                kd_el = await page.query_selector(f"xpath={kd_xpath}")
                if kd_el:
                    kd_text = (await kd_el.inner_text()).strip()
                    kd = kd_text or "N/A"

                # NOTE: your original XPaths used /text(), which isn't an element node.
                # We'll grab the parent element's text and trim.
                level_xpath_parent = (
                    "//*[@id='overview']/div[2]/div/div[1]/header/div/div[2]"
                )
                level_el = await page.query_selector(f"xpath={level_xpath_parent}")
                if level_el:
                    level_text = (await level_el.inner_text()).strip()
                    level = level_text or "N/A"

                playtime_xpath_parent = (
                    "//*[@id='overview']/div[2]/div/div[1]/header/div/div[1]"
                )
                playtime_el = await page.query_selector(
                    f"xpath={playtime_xpath_parent}"
                )
                if playtime_el:
                    playtime_text = (await playtime_el.inner_text()).strip()
                    playtime = playtime_text or "N/A"

            except Exception as e:
                logging.warning(f"Failed to scrape player stats for {username}: {e!r}")

            # --- Profile image ---
            try:
                avatar = await page.query_selector(".profile-header-avatar")
                if avatar:
                    src = await avatar.get_attribute("src")
                    if src:
                        user_profile_img = src
            except Exception as e:
                logging.warning(f"Failed to scrape profile image for {username}: {e!r}")

            logging.info(f"{username} Fortnite Data Successfully Retrieved!")
            logging.info(
                f"    * KD: {kd}\n"
                f"    * Level: {level}\n"
                f"    * Playtime: {playtime}\n"
                f"    * Profile Pic: {user_profile_img}"
            )

            return kd, level, playtime, user_profile_img

    except Exception as e:
        logging.error(f"Error in Playwright: {e!r}")
        return "N/A", "N/A", "N/A", "N/A"

    finally:
        # In case browser was created outside async-with due to future edits
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
