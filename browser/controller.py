"""Playwright browser lifecycle management."""

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import Config


class BrowserController:
    def __init__(self, config: Config):
        self.config = config
        self._pw = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None

    def _on_new_page(self, new_page: Page) -> None:
        """Switch focus to any new window/tab opened by the training platform."""
        print(f"[browser] New window detected — switching focus to: {new_page.url or '(loading)'}")
        self.page = new_page
        # Bring it to front once it has loaded enough to have a URL
        new_page.once("domcontentloaded", lambda: new_page.bring_to_front())

    async def start(self, url: str) -> None:
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=self.config.headless,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self.context = await self.browser.new_context(
            viewport={
                "width": self.config.browser_viewport_width,
                "height": self.config.browser_viewport_height,
            },
        )
        # Track any new windows/tabs opened by the training platform
        self.context.on("page", self._on_new_page)

        self.page = await self.context.new_page()
        print(f"[browser] Navigating to {url}")
        await self.page.goto(url, wait_until="domcontentloaded")
        # Give dynamic content a moment to settle
        try:
            await self.page.wait_for_load_state(
                "networkidle", timeout=self.config.page_settle_timeout
            )
        except Exception:
            pass  # networkidle may time out on streaming pages — that's fine
        # Bring the browser window to the front so the user can see it
        await self.page.bring_to_front()

    async def stop(self) -> None:
        if self.browser:
            await self.browser.close()
        if self._pw:
            await self._pw.stop()
