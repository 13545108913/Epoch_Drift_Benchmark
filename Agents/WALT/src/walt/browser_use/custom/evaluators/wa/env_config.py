# websites domain
import os

REDDIT = os.environ.get("WA_REDDIT", "")
SHOPPING = os.environ.get("WA_SHOPPING", "")
SHOPPING_ADMIN = os.environ.get("WA_SHOPPING_ADMIN", "")
GITLAB = os.environ.get("WA_GITLAB", "")
WIKIPEDIA = os.environ.get("WA_WIKIPEDIA", "")
MAP = os.environ.get("WA_MAP", "")
HOMEPAGE = os.environ.get("WA_HOMEPAGE", "")
WORDPRESS = os.environ.get("WA_WORDPRESS", "")

assert (
    REDDIT
    and SHOPPING
    and SHOPPING_ADMIN
    and GITLAB
    and WIKIPEDIA
    and MAP
    and HOMEPAGE
    and WORDPRESS
), (
    f"Please setup the URLs to each site. Current: \n"
    + f"Reddit: {REDDIT}\n"
    + f"Shopping: {SHOPPING}\n"
    + f"Shopping Admin: {SHOPPING_ADMIN}\n"
    + f"Gitlab: {GITLAB}\n"
    + f"Wikipedia: {WIKIPEDIA}\n"
    + f"Map: {MAP}\n"
    + f"Homepage: {HOMEPAGE}\n"
    + f"Wordpress: {WORDPRESS}\n"
)


ACCOUNTS = {
    "reddit": {"username": "MarvelsGrantMan136", "password": "test1234"},
    "gitlab": {"username": "byteblaze", "password": "a_very_secure_password_123!"},
    "shopping": {
        "username": "emma.lopez@gmail.com",
        "password": "Password.123",
    },
    "shopping_admin": {"username": "admin", "password": "password123"},
    "shopping_site_admin": {"username": "admin", "password": "admin1234"},
}

URL_MAPPINGS = {
    REDDIT: "http://reddit.com",
    SHOPPING: "http://onestopmarket.com",
    SHOPPING_ADMIN: "http://luma.com/admin",
    GITLAB: "http://gitlab.com",
    WIKIPEDIA: "http://wikipedia.org",
    MAP: "http://openstreetmap.org",
    HOMEPAGE: "http://homepage.com",
    WORDPRESS: "http://localhost:8000",
}
