import os

import httpx
from dotenv import load_dotenv

load_dotenv()


class Bitoff:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:108.0) Gecko/20100101 Firefox/108.0",
            "Authorization": f"Bearer {os.getenv('BITOFF_AUTH_TOKEN')}",
            "Referer": "https://bitoff.io/"
        }

    def get_offer(self, offer_id: str):
        r = httpx.get(f"https://api.bitoff.io/o/{offer_id}/detail", headers=self.headers, timeout=20)
        if r.status_code != 200:
            if r.status_code == 404:
                return None
            raise ValueError(f"An unexpected error occurred while fetching offer {offer_id}. Response ({r.status_code}): {r.text}")
        return r.json()

    def get_offer_list(self, page: int = 1):
        r = httpx.get("https://api.bitoff.io/o/list", params={"page": page, "currency": "all", "source": "all"}, headers=self.headers, timeout=20)
        if r.status_code != 200:
            raise ValueError(f"An unexpected error occurred while fetching the offer list. Response ({r.status_code}): {r.text}")
        return r.json()
