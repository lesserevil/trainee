"""Playwright browser lifecycle management."""

import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile

from playwright.async_api import async_playwright, BrowserContext, Page

from config import Config


MICROSOFT_SSO_EXTENSION_ID = "ppnbnpeolgkicgegkbkbjmhlideopiji"
MICROSOFT_SSO_EXTENSION_PUBLIC_KEY = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAi3iQDRjhZPFBKBhdtYmw"
    "nGuCdJFaL2ium4uGMsmm2pjZW8ZNSGMEiEOswJV5m+wWT/aOhW4pWWeAb8QVPWF"
    "aYUOQxUdYrjqGrAZYNcJNdvS8/xvmvOvabE81WozjGZkX0P7RLcBuqBVZNIRXHH"
    "6+wLosEFZ+Fk3kyb3iDnZeihAk7xZbZHe01qMqbP2lT8aSSnX102dDocrWzOyCpb"
    "wyRWHPAMKRuSj1HR4O07sBc19aObW2RsNTDu4oicdTk2CjmkOh49z07NyEWkyVi/"
    "Y5Fb31diwsirOoMFLTF5gy8o+1zLv2J7bRqI+I8t8o45OLBeWL8Gu69ji3NWLFU"
    "qw2uwIDAQAB"
)
MICROSOFT_SSO_EXTENSION_DOWNLOAD_URL = (
    "https://clients2.google.com/service/update2/crx"
    "?response=redirect"
    "&prodversion=120.0.0.0"
    "&acceptformat=crx2,crx3"
    f"&x=id%3D{MICROSOFT_SSO_EXTENSION_ID}%26uc"
)
MACOS_MICROSOFT_SSO_NATIVE_HOST = Path(
    "/Library/Google/Chrome/NativeMessagingHosts/com.microsoft.browsercore.json"
)


def _extension_id_from_manifest(manifest: dict) -> str | None:
    try:
        public_key = base64.b64decode(manifest["key"], validate=True)
    except (KeyError, TypeError, ValueError):
        return None
    digest = hashlib.sha256(public_key).hexdigest()[:32]
    return "".join(chr(ord("a") + int(character, 16)) for character in digest)


def _is_microsoft_sso_extension(extension_dir: Path) -> bool:
    try:
        manifest = json.loads(
            (extension_dir / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return False
    return (
        manifest.get("name") == "Microsoft Single Sign On"
        and _extension_id_from_manifest(manifest) == MICROSOFT_SSO_EXTENSION_ID
    )


def _install_microsoft_sso_extension(extension_dir: Path) -> None:
    print("[browser] Downloading Microsoft Single Sign On from the Chrome Web Store.")
    with urlopen(MICROSOFT_SSO_EXTENSION_DOWNLOAD_URL, timeout=30) as response:
        crx_data = response.read()

    try:
        archive = ZipFile(BytesIO(crx_data))
    except BadZipFile as error:
        raise RuntimeError(
            "Chrome Web Store returned an invalid Microsoft SSO extension package"
        ) from error

    extension_dir.parent.mkdir(parents=True, exist_ok=True)
    with archive, TemporaryDirectory(
        prefix="microsoft-sso-", dir=extension_dir.parent
    ) as temp_dir:
        unpacked_dir = Path(temp_dir)
        unpacked_root = unpacked_dir.resolve()
        for member in archive.infolist():
            target = (unpacked_dir / member.filename).resolve()
            if target != unpacked_root and unpacked_root not in target.parents:
                raise RuntimeError(
                    "Chrome Web Store returned an unsafe Microsoft SSO package"
                )
        archive.extractall(unpacked_dir)
        manifest_path = unpacked_dir / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "Chrome Web Store returned an invalid Microsoft SSO manifest"
            ) from error
        if manifest.get("name") != "Microsoft Single Sign On":
            raise RuntimeError(
                "Chrome Web Store returned an unexpected Microsoft SSO extension"
            )
        manifest["key"] = MICROSOFT_SSO_EXTENSION_PUBLIC_KEY
        manifest_path.write_text(
            json.dumps(manifest, indent=3) + "\n",
            encoding="utf-8",
        )
        if not _is_microsoft_sso_extension(unpacked_dir):
            raise RuntimeError(
                "Chrome Web Store returned an unexpected Microsoft SSO extension"
            )
        if extension_dir.exists():
            shutil.rmtree(extension_dir)
        shutil.copytree(unpacked_dir, extension_dir)


def prepare_microsoft_sso_profile(
    profile_dir: Path,
    *,
    native_host_manifest: Path = MACOS_MICROSOFT_SSO_NATIVE_HOST,
) -> Path | None:
    """Install Microsoft's SSO extension and broker manifest for Playwright."""
    if sys.platform != "darwin":
        return None

    try:
        native_host = json.loads(native_host_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(
            "[browser] Microsoft SSO unavailable: the Company Portal browser "
            "broker is not installed. Continuing without Microsoft SSO."
        )
        return None

    extension_origin = f"chrome-extension://{MICROSOFT_SSO_EXTENSION_ID}/"
    broker_path = Path(native_host.get("path", ""))
    if (
        extension_origin not in native_host.get("allowed_origins", [])
        or not broker_path.is_file()
    ):
        print(
            "[browser] Microsoft SSO unavailable: the Company Portal browser "
            "broker is incomplete. Continuing without Microsoft SSO."
        )
        return None

    extension_dir = (
        profile_dir / "Trainee Extensions" / MICROSOFT_SSO_EXTENSION_ID
    )
    if not _is_microsoft_sso_extension(extension_dir):
        try:
            _install_microsoft_sso_extension(extension_dir)
        except (OSError, RuntimeError) as error:
            print(
                "[browser] Microsoft SSO unavailable: could not install the "
                f"extension ({error}). Continuing without Microsoft SSO."
            )
            return None

    profile_native_hosts = profile_dir / "NativeMessagingHosts"
    profile_native_hosts.mkdir(parents=True, exist_ok=True)
    profile_native_host = profile_native_hosts / native_host_manifest.name
    expected_native_host = json.dumps(native_host, indent=2) + "\n"
    if (
        not profile_native_host.exists()
        or profile_native_host.read_text(encoding="utf-8") != expected_native_host
    ):
        profile_native_host.write_text(expected_native_host, encoding="utf-8")

    print("[browser] Microsoft SSO extension and Company Portal broker enabled.")
    return extension_dir


class BrowserController:
    def __init__(self, config: Config):
        self.config = config
        self._pw = None
        self.context: BrowserContext = None
        self.page: Page = None

    def _on_new_page(self, new_page: Page) -> None:
        """Switch focus to any new window/tab opened by the training platform."""
        print(f"[browser] New window detected — switching focus to: {new_page.url or '(loading)'}")
        self.page = new_page
        # Bring it to front once it has loaded enough to have a URL
        new_page.once("domcontentloaded", lambda: new_page.bring_to_front())
        # Revert focus when this tab closes
        new_page.on("close", lambda _: self._revert_page())

    def _revert_page(self) -> None:
        """Called when a tab closes; switch self.page to the last remaining open tab."""
        open_pages = self.context.pages
        if open_pages and self.page not in open_pages:
            self.page = open_pages[-1]
            print(f"[browser] Window closed — now watching: {self.page.url}")

    async def start(self, url: str) -> None:
        self._pw = await async_playwright().start()

        profile_dir = Path(self.config.browser_profile_dir).expanduser().resolve()
        profile_dir.mkdir(parents=True, exist_ok=True)
        print(f"[browser] Using profile: {profile_dir}")

        launch_options = {}
        browser_args = [
            "--autoplay-policy=no-user-gesture-required",
            "--disable-blink-features=AutomationControlled",
        ]
        extension_dir = None
        if self.config.enable_microsoft_sso:
            extension_dir = prepare_microsoft_sso_profile(profile_dir)
        if extension_dir:
            browser_args.extend(
                [
                    f"--disable-extensions-except={extension_dir}",
                    f"--load-extension={extension_dir}",
                ]
            )
            # The BrowserCore-backed SSO extension stalls SAML form submission
            # in Playwright's bundled Chromium. Use the installed Chrome build,
            # which is also the browser targeted by the native host manifest.
            launch_options = {
                "channel": "chrome",
                "ignore_default_args": ["--disable-extensions"],
            }

        self.context = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self.config.headless,
            args=browser_args,
            viewport={
                "width": self.config.browser_viewport_width,
                "height": self.config.browser_viewport_height,
            },
            **launch_options,
        )
        # Track any new windows/tabs opened by the training platform
        self.context.on("page", self._on_new_page)

        # Reuse the existing tab from a previous session if present
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
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
        if self.context:
            await self.context.close()
        if self._pw:
            await self._pw.stop()
