import logging

# import asyncio
import re
from playwright.async_api import async_playwright

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%I:%M:%S %p",
)

CHROMIUM_PATH = "/usr/bin/chromium-browser"


async def get_val_player_data(username: str):
    browser = None
    rank = ranked_kd = rank_img = None

    try:
        match = re.match(r"([^#]+)#(\d{4})", username)
        if not match:
            raise ValueError("invalid Riot ID format. Expected 'username#1234'")

        riot_name, playercode = match.groups()

        url = f"https://tracker.gg/valorant/profile/riot/{riot_name}%23{playercode}/overview"

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )
            page = await browser.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_selector("span", timeout=60_000)

            # -------- Extract KD via XPath in evaluate (kept from your code) --------
            kd = await page.evaluate(
                """() => {
                    const xpath = "//span[contains(text(), 'KD')]/following-sibling::span/span";
                    const result = document
                        .evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null)
                        .singleNodeValue;
                    return result ? result.textContent.trim() : null;
                }"""
            )

            # -------- Extract Level --------
            level_selector = (
                "#app div[2] div[3] div main div[3] div[2] div[2] div[2] "
                "div[1] div div[2] div[2] div div div div[1] span[2]"
            )
            level_el = await page.query_selector(level_selector)
            level = (await level_el.inner_text()).strip() if level_el else None

            # -------- Extract User Profile Image --------
            user_img_el = await page.query_selector(".user-avatar__image")
            user_profile_img = (
                await user_img_el.get_attribute("src") if user_img_el else None
            )

            # -------- Try ranked data --------
            try:
                rank_selector = (
                    "#app div[2] div[3] div main div[3] div[2] div[2] div[2] "
                    "div[1] div[1] div[2] div[2] div div[1] div div[1] span[2]"
                )
                rank_el = await page.query_selector(rank_selector)
                rank = (await rank_el.inner_text()).strip() if rank_el else None

                ranked_kd_selector = (
                    "#app div[2] div[3] div main div[3] div[2] div[2] div[2] "
                    "div[1] div[1] div[3] div[2] div div[2] span[2] span"
                )
                ranked_kd_el = await page.query_selector(ranked_kd_selector)
                ranked_kd = (
                    (await ranked_kd_el.inner_text()).strip() if ranked_kd_el else None
                )

                rank_img_selector = (
                    "#app div[2] div[3] div main div[3] div[2] div[2] div[2] "
                    "div[1] div[1] div[2] div[2] div div[1] img"
                )
                rank_img_el = await page.query_selector(rank_img_selector)
                rank_img = (
                    await rank_img_el.get_attribute("src") if rank_img_el else None
                )

            except Exception:
                logging.warning("Unable to retrieve ranked data")

            # Log extracted data
            elements = {"KD": kd, "Level": level, "Rank": rank, "Ranked KD": ranked_kd}
            img_elements = {
                "Player Profile Pic": user_profile_img,
                "Ranked Image": rank_img,
            }

            logging.info(f"{riot_name} Valorant Data Successfully Found!")
            for key, value in elements.items():
                if value:
                    logging.info(f"    *    {key}: {value}")
            for key, value in img_elements.items():
                if value and len(value) > 10:
                    logging.info(f"    *    {key}: URL has been grabbed")

            return kd, level, rank, ranked_kd, user_profile_img, rank_img

    except Exception as e:
        logging.error(f"Error in Playwright: {e!r}")
        return None, None, None, None, None, None

    finally:
        # (async with closes it, but keep this as a safety net)
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
