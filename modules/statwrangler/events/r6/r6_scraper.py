import logging

from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%I:%M:%S %p",
)

# Toggle this to True if you want to SEE the browser (helps diagnose bot protection)
DEBUG_HEADFUL = False


async def get_r6siege_player_data(username: str, platform: str):
    url = f"https://r6.tracker.network/r6siege/profile/{platform}/{username}/overview"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=(not DEBUG_HEADFUL),
                args=["--no-sandbox"],
            )

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720},
                locale="en-US",
            )

            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            logging.info(f"[siege] title={await page.title()!r}")

            # Always print what we actually loaded (helps a TON)
            logging.info(
                f"[siege] Loaded page title={await page.title()!r} url={page.url!r}"
            )

            # Don't use networkidle here; many modern sites never go idle.
            # Instead wait for "real content" indicators (text anchors).
            try:
                await page.wait_for_selector(
                    "xpath=//*[contains(., 'KD') or contains(., 'K/D') or contains(., 'Kills') or contains(., 'Rank')]",
                    timeout=60_000,
                )
            except PlaywrightTimeoutError:
                html_head = (await page.content())[:2000]
                logging.error(
                    "[siege] Timed out waiting for page UI. Dumping HTML head:"
                )
                print("\n--- PLAYWRIGHT DEBUG ---")
                print("TITLE:", await page.title())
                print("URL:", page.url)
                print("HTML (first 2000 chars):\n", html_head)
                print("--- END DEBUG ---\n")
                await context.close()
                await browser.close()
                return None, None, None, None, None, None, None

            # ---- Extracts (keep your logic, but strip and guard) ----
            # kd = await page.evaluate(
            #     """() => {
            #         const xpath = "//span[contains(text(), 'KD')]/following-sibling::span/span";
            #         const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
            #         return result.singleNodeValue ? result.singleNodeValue.innerText.trim() : null;
            #     }"""
            # )

            kd_locator = page.locator(
                "xpath=//*[@id='app']/div[2]/div[3]/div/main/div[2]/div[2]/div[3]/div[2]/section[1]/div[1]/div[2]/div[2]/div/div/div"
            ).first
            await kd_locator.wait_for(state="visible", timeout=10000)
            kd = (await kd_locator.inner_text()).strip()

            level_locator = page.locator(
                "xpath=//*[@id='app']/div[2]/div[3]/div/main/div[2]/div[2]/div[3]/div[2]/section[1]/div[1]/div[1]/div/div[1]/div/div/span[2]/span"
            ).first
            await level_locator.wait_for(state="visible", timeout=10000)
            level = (await level_locator.inner_text()).strip()

            # commented out since playtime is not loading on the page in question
            # playtime = await page.evaluate(
            #     """() => {
            #         const element = document.querySelector("span.text-secondary:nth-child(3) > span:nth-child(1)");
            #         return element ? element.innerText.trim() : null;
            #     }"""
            # )

            user_profile_img_locator = page.locator(
                "xpath=//*[@id='app']/div[2]/div[3]/div/main/div[2]/div[1]/div[2]/header/div[4]/div[1]/div[1]/div/img"
            ).first
            await user_profile_img_locator.wait_for(state="visible", timeout=10000)
            user_profile_img = await user_profile_img_locator.get_attribute("src")

            rank = ranked_kd = rank_img = None

            # Ranked data (best effort)
            try:
                rank = await page.evaluate(
                    """() => {
                        const element = document.querySelector(".flex-1 > div:nth-child(1) > span:nth-child(1)");
                        return element ? element.innerText.trim() : null;
                    }"""
                )

                ranked_kd = await page.locator(
                    """//*[@id='app']//table//tr[
                    contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'ranked')
                    ]/td[2]//span[contains(@class,'truncate')]"""
                ).first.inner_text()

                rank_img = await page.evaluate(
                    """() => {
                        const element = document.querySelector("header.rounded-t-4 > div:nth-child(1) > img:nth-child(1)");
                        return element ? element.src : null;
                    }"""
                )
            except Exception:
                logging.warning("[siege] Unable to retrieve ranked data")

            logging.info(
                f"[siege] Extracted kd={kd!r} level={level!r} rank={rank!r} ranked_kd={ranked_kd!r}, ranked_img={rank_img}"
            )

            # use when playtime is a metric to be tracked again
            # logging.info(
            #     f"[siege] Extracted kd={kd!r} level={level!r} playtime={playtime!r} rank={rank!r} ranked_kd={ranked_kd!r}"
            # )

            await context.close()
            await browser.close()
            return kd, level, rank, ranked_kd, user_profile_img, rank_img

            # add back when palytime can be used again
            # return kd, level, playtime, rank, ranked_kd, user_profile_img, rank_img

    except Exception as e:
        logging.error(f"[siege] Error in Playwright: {e!r}")
        return None, None, None, None, None, None, None
