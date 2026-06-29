"""
Chess Claim Tool: DownloadPgn

Copyright (C) 2019 Serntedakis Athanasios <thanasis@brainfriz.com>
Modfied by Tomasz Delega (C) 2026 AI-assisted refactoring

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import urllib.request
from urllib.error import HTTPError, URLError
import certifi
import time

# Stały nagłówek udający normalną przeglądarkę
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "X-Client": "ChessClaimTool/0.4.3"
}

def download_pgn(url: str, timeout=30) -> bytes:
    """
    Download PGN from URL with up to 3 retries.
    Handles 404 as 'PGN not ready yet' and retries.
    Returns bytes() on failure.
    """

    for attempt in range(1, 4):  # 3 próby
        try:
            req = urllib.request.Request(url, headers=BROWSER_HEADERS)

            response = urllib.request.urlopen(
                req,
                timeout=timeout,
                cafile=certifi.where()
            )
            return response.read()

        except HTTPError as e:
            if e.code == 404:
                print(f"[Attempt {attempt}/3] 404 Not Found (PGN not ready yet): {url}")
                time.sleep(3)
                continue
            else:
                print(f"[Attempt {attempt}/3] HTTP error while downloading {url}: {e}")

        except URLError as e:
            print(f"[Attempt {attempt}/3] Network error while downloading {url}: {e}")

        except TimeoutError:
            print(f"[Attempt {attempt}/3] Timeout while downloading: {url}")

        except Exception as e:
            print(f"[Attempt {attempt}/3] Unexpected error while downloading {url}: {e}")

        time.sleep(1)

    print(f"Failed to download after 3 attempts: {url}")
    return bytes()


def check_download(url: str, timeout=10) -> bool:
    """
    Check if URL is reachable.
    Returns True if server responds, False otherwise.
    """

    try:
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)

        urllib.request.urlopen(
            req,
            timeout=timeout,
            cafile=certifi.where()
        )
        return True

    except Exception as e:
        print("check_download error:", e)
        return False
