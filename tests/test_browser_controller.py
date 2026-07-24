from io import BytesIO
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from zipfile import ZipFile

from browser.controller import (
    BrowserController,
    MICROSOFT_SSO_EXTENSION_ID,
    prepare_microsoft_sso_profile,
)
from config import Config


class MicrosoftSsoProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.broker = self.root / "BrowserCore"
        self.broker.write_text("", encoding="utf-8")
        self.native_host = self.root / "com.microsoft.browsercore.json"
        self.native_host.write_text(
            json.dumps(
                {
                    "path": str(self.broker),
                    "allowed_origins": [
                        f"chrome-extension://{MICROSOFT_SSO_EXTENSION_ID}/"
                    ],
                }
            ),
            encoding="utf-8",
        )
        manifest = {
            "manifest_version": 3,
            "name": "Microsoft Single Sign On",
            "version": "1.0.11",
        }
        self.extension_crx = BytesIO()
        with ZipFile(self.extension_crx, "w") as archive:
            archive.writestr("manifest.json", json.dumps(manifest))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @patch("browser.controller.urlopen")
    @patch("browser.controller.sys.platform", "darwin")
    def test_installs_extension_and_native_host_for_dedicated_profile(
        self,
        urlopen: Mock,
    ) -> None:
        profile = self.root / "profile"
        urlopen.return_value.__enter__.return_value.read.return_value = (
            self.extension_crx.getvalue()
        )

        extension_dir = prepare_microsoft_sso_profile(
            profile,
            native_host_manifest=self.native_host,
        )

        self.assertEqual(
            extension_dir,
            profile / "Trainee Extensions" / MICROSOFT_SSO_EXTENSION_ID,
        )
        self.assertTrue((extension_dir / "manifest.json").is_file())
        profile_native_host = (
            profile / "NativeMessagingHosts" / self.native_host.name
        )
        self.assertEqual(
            json.loads(profile_native_host.read_text(encoding="utf-8")),
            json.loads(self.native_host.read_text(encoding="utf-8")),
        )
        prepare_microsoft_sso_profile(
            profile,
            native_host_manifest=self.native_host,
        )
        urlopen.assert_called_once()

    @patch("browser.controller.sys.platform", "darwin")
    def test_falls_back_when_native_broker_is_missing(self) -> None:
        profile = self.root / "profile"

        extension_dir = prepare_microsoft_sso_profile(
            profile,
            native_host_manifest=self.root / "missing.json",
        )

        self.assertIsNone(extension_dir)
        self.assertFalse((profile / "Trainee Extensions").exists())


class BrowserControllerLaunchTest(unittest.IsolatedAsyncioTestCase):
    @patch("browser.controller.prepare_microsoft_sso_profile")
    @patch("browser.controller.async_playwright")
    async def test_loads_sso_extension_in_playwright_chromium(
        self,
        playwright_factory: Mock,
        prepare_sso: Mock,
    ) -> None:
        page = Mock()
        page.url = "about:blank"
        page.goto = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.bring_to_front = AsyncMock()

        context = Mock()
        context.pages = [page]
        context.on = Mock()

        chromium = Mock()
        chromium.launch_persistent_context = AsyncMock(return_value=context)
        playwright = Mock()
        playwright.chromium = chromium
        playwright_factory.return_value.start = AsyncMock(return_value=playwright)

        with tempfile.TemporaryDirectory() as temp_dir:
            extension_dir = Path(temp_dir) / "microsoft-sso"
            prepare_sso.return_value = extension_dir
            controller = BrowserController(
                Config(browser_profile_dir=temp_dir, enable_microsoft_sso=True)
            )
            await controller.start("https://example.com")

        launch_options = chromium.launch_persistent_context.await_args.kwargs
        self.assertEqual(launch_options["channel"], "chromium")
        self.assertEqual(
            launch_options["ignore_default_args"],
            ["--disable-extensions"],
        )
        self.assertIn(
            f"--disable-extensions-except={extension_dir}",
            launch_options["args"],
        )
        self.assertIn(
            f"--load-extension={extension_dir}",
            launch_options["args"],
        )


if __name__ == "__main__":
    unittest.main()
