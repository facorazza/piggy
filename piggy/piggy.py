import logging
import json
import time

from random import random, randint

import asyncio
import aiohttp
import aiosqlite
import aiofiles
import regex

from aiohttp.client_exceptions import ClientConnectorError

from piggy import utils


# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
fh = logging.FileHandler("./piggy.log")

ch.setLevel(logging.INFO)
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(message)s")
ch.setFormatter(formatter)
formatter = logging.Formatter(
    "[%(asctime)s] %(levelname)s %(funcName)s: %(message)s"
)
fh.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fh)


class Piggy:
    def __init__(self, loop):
        self.loop = loop

    async def http_request(
        self, method, url,
        headers=None, params=None, data=None, response_type="text"
    ):
        await asyncio.sleep(self.settings['connection']["wait_time"])

        try:
            if method == "GET":
                r = await self.session.get(
                    url,
                    headers=headers,
                    params=params
                )
                logger.debug(f"[GET] {r.url}")
            elif method == "POST":
                r = await self.session.post(
                    url,
                    headers=headers,
                    data=data
                )
                logger.debug(f"[POST] {r.url}")
            else:
                raise ValueError(f"Invalid HTTP method: {method}")

        except ClientConnectorError:
            logger.error("Could not reach the server. Retrying in 30 seconds.")
            await asyncio.sleep(30)
            return await self.http_request(
                method,
                url,
                headers=headers,
                params=params,
                data=data,
                response_type=response_type
            )

        else:
            logger.debug(f"Status code: {r.status} {r.reason}")

            if r.status == 200:
                # Successfull request: decrease retry time
                if self.settings['connection']["wait_time"] > 0:
                    self.settings['connection']["wait_time"] -= 1

                if response_type == "text":
                    res = await r.text()
                    logger.debug(res)
                    return res
                elif response_type == "json":
                    res = await r.json()
                    logger.debug(res)
                    return res
                else:
                    raise ValueError(f"Invalid response type: {response_type}")
            elif r.status == 429:
                # Unsuccessfull request: increase retry time
                self.settings['connection']["wait_time"] += 1
                logger.warning(
                    f"""Too many requests! Retrying in {self.settings['connection']['wait_time']} seconds."""
                )
                return await self.http_request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    data=data,
                    response_type=response_type
                )
            else:
                logger.error(f"Response status: {r.status}")
                logger.error(f"Response headers: {r.headers}")
                logger.error(await r.text())
                raise ValueError(f"Response error: {r.status}")

    async def setup(self, settings_path="settings.json"):
        logger.info("Loading settings...")

        # Load settings
        with open(settings_path) as f:
            self.settings = json.loads(
                regex.sub(r"#.+$", "", f.read(), flags=regex.MULTILINE)
            )

        # Load comments list for photos
        with open("comments/pic_comments.txt") as f:
            comments = f.readlines()
        self.pic_comments_list = [x.strip() for x in comments]

        # Load comments list for videos
        with open("comments/video_comments.txt") as f:
            comments = f.readlines()
        self.video_comments_list = [x.strip() for x in comments]

        # Initialize the asynchronous http session
        headers = {
            "DNT": "1",
            "Host": "www.instagram.com",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": self.settings["connection"]["user_agent"]
        }
        timeout = aiohttp.ClientTimeout(
            total=self.settings["connection"]["timeout"]
        )
        self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        logger.info("Session initialized.")

        # Get the csrf token. It is needed to log in
        self.csrf_token = await self._getCsrfTokenFromForm()

    async def _getCsrfTokenFromForm(self):
        # Get login page and find the csrf token
        res = await self.http_request(
            "GET",
            "https://www.instagram.com/accounts/login/"
        )

        return regex.findall(
            r"\"csrf_token\":\"(.*?)\"",
            res,
            flags=regex.MULTILINE
        )[0]

    async def login(self):
        payload = {
            "username": self.settings["user"]["username"],
            "password": self.settings["user"]["password"]
        }
        headers = {
            "User-Agent": self.settings["connection"]["user_agent"],
            "X-CSRFToken": self.csrf_token
        }
        res = await self.http_request(
            "POST",
            "https://www.instagram.com/accounts/login/ajax/",
            headers=headers,
            data=payload,
            response_type="json"
        )

        if res["authenticated"]:
            logger.info("Logged in!")
            self.id = res["userId"]

        elif res["message"] == "checkpoint_required":
            logger.info("Checkpoint required.")

            res = await self.http_request(
                "POST",
                f"https://www.instagram.com{res['checkpoint_url']}",
                headers=headers,
                data=payload
            )
            logger.error(res)

        else:
            logger.error("Couldn't log in.")

        cookies = utils.cookies_dict(self.session.cookie_jar)
        self.csrf_token = cookies["csrftoken"]

        # Initialize the database
        await self._init_database()

    async def _init_database(self):
        logger.info("Checking database...")
        # Connect to the local database and look for the table names
        async with aiosqlite.connect("./piggy.db") as db:
            logger.debug("Checking table: pics")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS pics (
                    id INT,
                    height INT,
                    width INT,
                    url TEXT,
                    tags TEXT
                )
                """
            )

            logger.debug("Checking table: users")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT,
                    username TEXT,
                    ts_follower INTEGER,
                    ts_following INTEGER,
                    follower BOOL,
                    following BOOL
                )
                """
            )

            logger.debug("Checking table: likes")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS likes (
                    id INTEGER,
                    ts INTEGER
                )
                """
            )

            logger.debug("Checking table: comments")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER,
                    ts INTEGER,
                    comment TEXT
                )
                """
            )

            logger.info("Updating followers and following lists.")
            await db.execute("UPDATE users SET follower=0, following=1")

            for username in await self.followers():
                await db.execute(
                    "UPDATE users SET follower=0 WHERE username=?",
                    (username,)
                )

            for username in await self.following():
                await db.execute(
                    "UPDATE users SET following=1 WHERE username=?",
                    (username,)
                )

            await db.commit()

    async def followers(self, username=None):
        followers = []

        if username is None:
            id = self.id
        else:
            user = await self.get_user_by_username(username)
            id = user["graphql"]["user"]["id"]

        params = {
            "query_hash": "37479f2b8209594dde7facb0d904896a",
            "variables": json.dumps({"id": str(id), "first": 50})
        }
        has_next_page = True
        while has_next_page:
            res = await self.http_request(
                "GET",
                "https://www.instagram.com/graphql/query/",
                params=params,
                response_type="json"
            )

            has_next_page = res["data"]["user"]["edge_followed_by"]["page_info"]["has_next_page"]
            end_cursor = res["data"]["user"]["edge_followed_by"]["page_info"]["end_cursor"]
            params["variables"] = json.dumps(
                {"id": str(id), "first": 50, "after": end_cursor}
            )

            for user in res["data"]["user"]["edge_followed_by"]["edges"]:
                followers.append(user["node"]["username"])
        return followers

    async def following(self, username=None):
        following = []

        if username is None:
            id = self.id
        else:
            user = await self.get_user_by_username(username)
            id = user["graphql"]["user"]["id"]

        params = {
            "query_hash": "58712303d941c6855d4e888c5f0cd22f",
            "variables": json.dumps({"id": str(id), "first": 50})
        }
        has_next_page = True
        while has_next_page:
            res = await self.http_request(
                "GET",
                "https://www.instagram.com/graphql/query/",
                params=params,
                response_type="json"
            )

            has_next_page = res["data"]["user"]["edge_follow"]["page_info"]["has_next_page"]
            end_cursor = res["data"]["user"]["edge_follow"]["page_info"]["end_cursor"]
            params["variables"] = json.dumps(
                {"id": str(id), "first": 50, "after": end_cursor}
            )

            for user in res["data"]["user"]["edge_follow"]["edges"]:
                following.append(user["node"]["username"])
        return following

    async def feed(self, explore=True, users=[], hashtags=[], locations=[]):
        """
        Generates a feed based on the passed parameters. Multiple parameters
        can be passed at the same time.

        Args:
            explore: [Bool] If True the explore page will be added to to the
            feed.
            users: [List of usernames] Their media will be pulled and added to
            the feed.
            hashtags: [List of hastags] Media with those hashtags will be added
            to the feed.
            locations: [List of locations ids] Media with those locations will
            be added to the feed.

        Retruns:
            Yields a media from the generated feed.
        """

        # Initialize asynchronous queue where the feed elements will be
        # temporarely stored
        q = asyncio.Queue()

        if explore:
            # Add the "explore" feed to the queue
            asyncio.ensure_future(self._explore_feed(q))
        if len(users):
            # Add all the media from the given users to the queue
            for user in users:
                asyncio.ensure_future(self._user_feed(q, user))
        if len(hashtags):
            # Add all the media from the given hashtags to the queue
            for hashtag in hashtags:
                asyncio.ensure_future(self._hashtag_feed(q, hashtag))
        if len(locations):
            # Add all the media from the given locations to the queue
            for location in locations:
                asyncio.ensure_future(self._location_feed(q, location))

        # Keep on yielding media while more is loaded
        while 1:
            while not q.empty():
                yield await q.get()
            await asyncio.sleep(1e-12)

    async def _explore_feed(self, q):
        params = {
            "query_hash": "ecd67af449fb6edab7c69a205413bfa7",
            "variables": json.dumps({"first": 24})
        }
        has_next_page = True
        while has_next_page:
            res = await self.http_request(
                "GET",
                "https://www.instagram.com/graphql/query/",
                params=params,
                response_type="json"
            )

            has_next_page = res["data"]["user"]["edge_web_discover_media"]["page_info"]["has_next_page"]
            end_cursor = res["data"]["user"]["edge_web_discover_media"]["page_info"]["end_cursor"]
            params["variables"] = json.dumps(
                {"first": 50, "after": end_cursor}
            )

            for media in res["data"]["user"]["edge_web_discover_media"]["edges"]:
                await q.put(media["node"])

    async def _user_feed(self, q, user):
        user = await self.get_user_by_usernameUsername(user)
        id = user["id"]

        params = {
            "query_hash": "a5164aed103f24b03e7b7747a2d94e3c",
            "variables": json.dumps({"id": id, "first": 24})
        }
        has_next_page = True
        while has_next_page:
            res = await self.http_request(
                "GET",
                "https://www.instagram.com/graphql/query/",
                params=params,
                response_type="json"
            )

            has_next_page = res["data"]["user"]["edge_owner_to_timeline_media"]["page_info"]["has_next_page"]
            end_cursor = res["data"]["user"]["edge_owner_to_timeline_media"]["page_info"]["end_cursor"]
            params["variables"] = json.dumps(
                {"id": id, "first": 50, "after": end_cursor}
            )

            for media in res["data"]["user"]["edge_web_discover_media"]["edges"]:
                await q.put(media["node"])

    async def _hashtag_feed(self, q, hashtag):
        count = 0
        params = {
            "query_hash": "1780c1b186e2c37de9f7da95ce41bb67",
            "variables": json.dumps({"tag_name": hashtag, "first": count})
        }
        has_next_page = True
        while has_next_page:
            res = await self.http_request(
                "GET",
                "https://www.instagram.com/graphql/query/",
                params=params,
                response_type="json"
            )

            has_next_page = res["data"]["hashtag"]["edge_hashtag_to_media"]["page_info"]["has_next_page"]
            end_cursor = res["data"]["hashtag"]["edge_hashtag_to_media"]["page_info"]["end_cursor"]
            count += 1
            params["variables"] = json.dumps(
                {"tag_name": hashtag, "first": count, "after": end_cursor}
            )

            for media in res["data"]["hashtag"]["edge_hashtag_to_media"]["edges"]:
                await q.put(media["node"])

    async def _location_feed(self, q, location_id):
        count = 0
        params = {
            "query_hash": "1b84447a4d8b6d6d0426fefb34514485",
            "variables": json.dumps({"id": str(location_id), "first": 50})
        }
        has_next_page = True
        while has_next_page:
            res = await self.http_request(
                "GET",
                "https://www.instagram.com/graphql/query/",
                params=params,
                response_type="json"
            )

            has_next_page = res["data"]["location"]["edge_location_to_media"]["page_info"]["has_next_page"]
            end_cursor = res["data"]["location"]["edge_location_to_media"]["page_info"]["end_cursor"]
            count += 1
            params["variables"] = json.dumps(
                {
                    "id": str(location_id),
                    "first": 50,
                    "after": str(end_cursor)
                }
            )

            for media in res["data"]["location"]["edge_location_to_media"]["edges"]:
                await q.put(media["node"])

    async def print(self, media):
        """
        Gives a visual representation of a media.

        Args:
            media: The media to be printed.

        Returns:
            None
        """

        logger.info("#--------"*3+"#")

        try:
            mediatype = media["__typename"]
        except KeyError:
            is_video = media["is_video"]
            if is_video:
                mediatype = "GraphVideo"
            else:
                mediatype = "GraphImage"
            pass

        likes = media["edge_liked_by"]["count"]
        comments = media["edge_media_to_comment"]["count"]

        shortcode = media["shortcode"]
        res = await self.http_request(
            "GET",
            f"https://www.instagram.com/p/{shortcode}/",
            params="__a=1",
            response_type="json"
        )

        username = res["graphql"]["shortcode_media"]["owner"]["username"]

        logger.info(
            f"{utils.translate_ig_media_type_to_custom(mediatype).capitalize()} by {username}\n❤️ {likes}, 💬 {comments}"
        )
        try:
            caption = media["edge_media_to_caption"]["edges"][0]["node"]["text"]
        except IndexError:
            pass
        else:
            if len(caption) > 100:
                logger.info(f"{caption:.100}...")
            else:
                logger.info(f"{caption}")

    async def like(self, media):
        """
        Check if the media satisfy the prerequisites and eventually it will
        send a like.

        Args:
            media: The media to like.

        Retruns:
            None
        """

        # Check if the media has already been liked
        async with aiosqlite.connect("./piggy.db") as db:
            row = await db.execute(
                "SELECT * FROM likes WHERE id=?",
                (media["id"],)
            )
            if await row.fetchone():
                logger.info("Already liked!")
                return

        try:
            mediatype = media["__typename"]
        except KeyError:
            is_video = media["is_video"]
            if is_video:
                mediatype = "GraphVideo"
            else:
                mediatype = "GraphImage"
            pass
        else:
            if not mediatype in utils.translate_custom_media_type_to_ig(self.settings["like"]["media_type"]):
                logger.info("Wrong media type. Not liked!")
                return

        likes = media["edge_liked_by"]["count"]
        if likes < self.settings["like"]["num_of_likes"]["min"] or likes >= self.settings["like"]["num_of_likes"]["max"]:
            logger.info("Too many or too few likes. Not liked!")
            return
        comments = media["edge_media_to_comment"]["count"]
        if comments < self.settings["like"]["num_of_comments"]["min"] or comments >= self.settings["like"]["num_of_comments"]["max"]:
            logger.info("Too many or too few comments. Not liked!")
            return

        if self.settings["like"]["rate"] / 100 > random():
            await self._like(media["id"])
        else:
            logger.info("Not liked!")

    async def _like(self, id):
        headers = {
            "DNT": "1",
            "Host": "www.instagram.com",
            "User-Agent": self.settings["connection"]["user_agent"],
            "X-CSRFToken": self.csrf_token
        }
        await self.http_request(
            "POST",
            f"https://www.instagram.com/web/likes/{id}/like/",
            headers=headers
        )

        async with aiosqlite.connect("./piggy.db") as db:
            await db.execute(
                "INSERT INTO likes VALUES(?,?)",
                (id, int(time.time()))
            )
            await db.commit()

        logger.info("Liked!")

    async def _unlike(self, id):
        headers = {
            "DNT": "1",
            "Host": "www.instagram.com",
            "User-Agent": self.settings["connection"]["user_agent"],
            "X-CSRFToken": self.csrf_token
        }
        await self.http_request(
            "POST",
            f"https://www.instagram.com/web/likes/{id}/unlike/",
            headers=headers
        )

        async with aiosqlite.connect("./piggy.db") as db:
            await db.execute("INSERT INTO likes WHERE id=?", (id,))
            await db.commit()

        logger.info("Unliked!")

    async def comment(self, media):
        """
        Check if the media satisfy the prerequisites and eventually it will
        send a comment.

        Args:
            media: The media to comment.

        Retruns:
            None
        """

        if media["comments_disabled"]:
            logger.info("Comments disabled.")
            return

        if self.settings["comment"]["only_once"]:
            async with aiosqlite.connect("./piggy.db") as db:
                row = await db.execute(
                    "SELECT * FROM comments WHERE id=?",
                    (media["id"],)
                )
                if await row.fetchone() is None:
                    logger.info("Already commented.")
                    return

        try:
            mediatype = media["__typename"]
        except KeyError:
            is_video = media["is_video"]
            if is_video:
                mediatype = "GraphVideo"
            else:
                mediatype = "GraphImage"
            pass
        else:
            if not mediatype in utils.translate_custom_media_type_to_ig(self.settings["comment"]["media_type"]):
                return

        likes = media["edge_liked_by"]["count"]
        if likes < self.settings["comment"]["num_of_likes"]["min"] or likes >= self.settings["comment"]["num_of_likes"]["max"]:
            return
        comments = media["edge_media_to_comment"]["count"]
        if comments < self.settings["comment"]["num_of_comments"]["min"] or comments >= self.settings["comment"]["num_of_comments"]["max"]:
            return

        if self.settings["comment"]["rate"] / 100 <= random():
            if mediatype == "GraphImage" or mediatype == "GraphSidecar":
                comment = self.pic_comments_list[
                    randint(0, len(self.pic_comments_list)-1)
                ]
            else:
                comment = self.video_comments_list[
                    randint(0, len(self.video_comments_list)-1)
                ]
            await self._comment(media["id"], comment)
        else:
            logger.info("Not commented!")

    async def _comment(self, id, comment, reply_to_id=None):
        headers = {
            "DNT": "1",
            "Host": "www.instagram.com",
            "User-Agent": self.settings["connection"]["user_agent"],
            "X-CSRFToken": self.csrf_token
        }
        payload = {
            "comment_text": comment
        }
        await self.http_request(
            "POST",
            f"https://www.instagram.com/web/comments/{id}/add/",
            headers=headers,
            data=payload
        )

        async with aiosqlite.connect("./piggy.db") as db:
            await db.execute(
                "INSERT INTO comments VALUES(?,?,?)",
                (id, int(time.time()), comment)
            )
            await db.commit()

        logger.info("Comment posted!")

    async def follow(self, media):
        """
        Check if the media satisfy the prerequisites and eventually send a
        follow request.

        Args:
            media: The media of the user to be followed.

        Retruns:
            None
        """

        if self.settings["follow"]["rate"] / 100 > random():
            await self._follow(media["owner"]["id"])
        else:
            logger.info("Not followed!")

    async def _follow(self, id):
        headers = {
            "DNT": "1",
            "Host": "www.instagram.com",
            "User-Agent": self.settings["connection"]["user_agent"],
            "X-CSRFToken": self.csrf_token
        }
        await self.http_request(
            "POST",
            f"https://www.instagram.com/web/friendships/{id}/follow/",
            headers=headers
        )

        async with aiosqlite.connect("./piggy.db") as db:
            c = await db.execute("SELECT * FROM users WHERE id=?", (id,))
            if c.rowcount:
                await db.execute(
                    """
                    UPDATE users SET
                    ts_following=?, following=?
                    WHERE id=?
                    """,
                    (int(time.time()), True, id)
                )
            else:
                await db.execute(
                    "INSERT INTO users VALUES(?,?,?,?,?)",
                    (id, None, int(time.time()), False, True)
                )

            await db.commit()

        logger.info("Follow request sent!")

    async def unfollow(self, id):
        return

    async def _unfollow(self, id):
        headers = {
            "DNT": "1",
            "Host": "www.instagram.com",
            "User-Agent": self.settings["connection"]["user_agent"],
            "X-CSRFToken": self.csrf_token
        }
        await self.http_request(
            "POST",
            f"https://www.instagram.com/web/friendships/{id}/unfollow/",
            headers=headers
        )

        async with aiosqlite.connect("./piggy.db") as db:
            await db.execute(
                "UPDATE users SET following=false WHERE id=?",
                (id,)
            )
            await db.commit()

    async def backup(self):
        while 1:
            logger.info("Backing up database...")
            for table_name in ["users", "likes", "comments"]:
                if self.settings["backup"][table_name]:
                    async with aiosqlite.connect("./piggy.db") as db:
                        rows = await db.execute(
                            f"SELECT * FROM '{table_name}'"
                        )
                        header = [i[0] for i in rows.description]
                        rows = await rows.fetchall()

                    if self.settings["backup"]["format"] == "csv":
                        await utils.to_csv(table_name, header, rows)
                    elif self.settings["backup"]["format"] == "json":
                        await utils.to_json(table_name, header, rows)
                    else:
                        logger.warning(
                            f"""Unsupported file format: {self.settings['backup']['format']}."""
                        )

                await asyncio.sleep(
                    utils.interval_in_seconds(self.settings["backup"]["every"])
                )

    async def close(self):
        logger.info("\nClosing session...")

        # Close the http session
        await self.session.close()

    async def get_user_by_username(self, username):
        res = await self.http_request(
            "GET",
            f"https://www.instagram.com/{username}/",
            params="__a:1"
        )

        return json.loads(
            regex.findall(
                r"<script[^>]*>window._sharedData = (.*?)</script>",
                regex.findall(
                    r"<body[^>]*>(.*)</body>",
                    res,
                    flags=regex.DOTALL
                )[0],
                flags=regex.DOTALL
            )[0][:-1])["entry_data"]["ProfilePage"][0]["graphql"]["user"]

# -----------------------------------------------------------------------------
    async def download(self, media):
        id = media["id"]
        url = media["display_url"]
        format = regex.findall(r".([a-zA-Z]+)$", url)[0]

        if media["__typename"] != "GraphImage" or await self.pic_already_saved(id):
            return

        height = media["dimensions"]["height"]
        width = media["dimensions"]["width"]
        try:
            caption = media["edge_media_to_caption"]["edges"][0]["node"]["text"]
        except IndexError:
            tags = []
            pass
        else:
            if await self.download_pic(url, id, format):
                logger.info(f"Caption: {caption}")
                tags = regex.findall(r"#([\p{L}0-9_]+)", caption)
                logger.info(f"Tags: {tags}")
            else:
                return

        await self.save_to_database(id, type, height, width, url, tags)

    async def download_pic(self, url, id, format):
        logger.info(f"Downloading {id}")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as r:
                    if r.status == 200:
                        f = await aiofiles.open(
                            f"./images/{id}.{format}",
                            mode="wb"
                        )
                        await f.write(await r.read())
                        await f.close()
                        return True
                    else:
                        return False
            except TimeoutError:
                return False

    async def pic_already_saved(self, id):
        logger.debug("Checking database.")
        async with aiosqlite.connect("./piggy.db") as db:
            row = await db.execute(
                "SELECT * FROM pics WHERE id=?",
                (id,)
            )

            if await row.fetchone() is None:
                return False
            else:
                return True

    async def save_to_database(self, id, type, height, width, url, tags):
        tags = json.dumps(tags)
        async with aiosqlite.connect("./piggy.db") as db:
            await db.execute(
                "INSERT INTO pics VALUES(?,?,?,?,?)",
                (id, height, width, url, tags)
            )
            await db.commit()
