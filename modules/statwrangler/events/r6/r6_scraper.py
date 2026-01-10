import logging
import asyncio
from playwright.async_api import async_playwright

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%I:%M:%S %p",  # 12-hour clock with AM/PM
)

async def get_r6siege_player_data(username, platform):
    browser = None
    rank = ranked_kd = rank_img = None  # Initialize variables to avoid undefined errors

    try:
        # Launch a headless browser using Playwright
        url = f"https://r6.tracker.network/r6siege/profile/{platform}/{username}/overview"
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                executable_path="/usr/bin/chromium-browser",
                args=["--no-sandbox"]
            )
            page = await browser.new_page()

            # Set a longer timeout if needed
            await page.goto(url, timeout=60000)

            # Wait for the page to load and the required elements to appear
            await page.wait_for_timeout(3000)
            await page.wait_for_selector("span", timeout=60000)  # Wait for any span tag

            # Extract data using JavaScript evaluation
            kd = await page.evaluate(
                '''() => {
                    const xpath = "//span[contains(text(), 'KD')]/following-sibling::span/span";
                    const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                    return result.singleNodeValue ? result.singleNodeValue.innerText : null;
                }'''
            )

            level = await page.evaluate(
                '''() => {
                    const xpath = '//*[@id="app"]/div[2]/div[3]/div/main/div[3]/div[2]/div[3]/div[2]/section[1]/div/div[1]/span[1]/span';
                    const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                    return result.singleNodeValue ? result.singleNodeValue.innerText : null;
                }'''
            )


            playtime = await page.evaluate(
                '''() => {
                    const element = document.querySelector("span.text-secondary:nth-child(3) > span:nth-child(1)");
                    return element ? element.innerText : null;
                }'''
            )

            user_profile_img = await page.evaluate(
                '''() => {
                    const element = document.querySelector(".user-avatar__image");
                    return element ? element.src : null;
                }'''
            )

            # Try to extract ranked data
            try:
                rank = await page.evaluate(
                    '''() => {
                        const element = document.querySelector(".flex-1 > div:nth-child(1) > span:nth-child(1)");
                        return element ? element.innerText : null;
                    }'''
                )

                ranked_kd = await page.evaluate(
                    '''() => {
                        const element = document.querySelector("div.playlist:nth-child(1) > div:nth-child(2) > div:nth-child(5) > span:nth-child(2) > span:nth-child(1)");
                        return element ? element.innerText : null;
                    }'''
                )

                rank_img = await page.evaluate(
                    '''() => {
                        const element = document.querySelector("header.rounded-t-4 > div:nth-child(1) > img:nth-child(1)");
                        return element ? element.src : null;
                    }'''
                )

            except Exception as e:
                logging.warning("Unable to retrieve ranked data")

            # Log extracted data
            elements = {
                "KD": kd,
                "Level": level,
                "Playtime": playtime,
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

            return kd, level, playtime, rank, ranked_kd, user_profile_img, rank_img

    except Exception as e:
        logging.error(f"Error in Playwright: {e}")
        return None, None, None, None, None, None, None  # Return None values on error

    finally:
        if browser:
            await browser.close()  # Ensure the browser closes

# To run the script
# asyncio.run(get_r6siege_player_data("BigMcD0n", "ubi"))
