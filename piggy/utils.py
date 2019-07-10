import json
import logging
import aiofiles
import regex


def translate_custom_media_type_to_ig(media_types):
    translated_media_types = []

    for mt in media_types:
        if mt == "photo":
            translated_media_types.append("GraphImage")
        elif mt == "album":
            translated_media_types.append("GraphSidecar")
        elif mt == "video":
            translated_media_types.append("GraphVideo")
        else:
            logging.warning(mt)
    return translated_media_types


def translate_ig_media_type_to_custom(media_type):
    if media_type == "GraphImage":
        return "photo"
    elif media_type == "GraphSidecar":
        return "album"
    elif media_type == "GraphVideo":
        return "video"
    else:
        raise (Exception, "Invalid media type: "+media_type)


def cookies_dict(cookie_jar):
    cookies = dict()
    for cookie in cookie_jar:
        cookies[cookie.key] = cookie.value
    return cookies


def interval_in_seconds(interval):
    exploded_interval = regex.findall(r"([0-9]+)([a-z])", interval)[0]
    value = int(exploded_interval[0])
    unit = exploded_interval[1]

    if unit == "s":
        return value
    elif unit == "m":
        return value * 60
    elif unit == "h":
        return value * 3600
    elif unit == "d":
        return value * 86400
    else:
        raise ValueError(f"Invalid unit: {unit}")


async def to_csv(filename, header, rows):
    async with aiofiles.open(f"backups/{filename}.csv", mode="w") as f:
        text = ""
        for h in header:
            text += f"{h},"
        text += "\n"

        for row in rows:
            for r in row:
                text += f"{r},"
            text = f"{text[:-1]}\n"

        await f.write(text)


async def to_json(filename, header, rows):
    list = []
    for row in rows:
        line = dict()
        for key, value in zip(header, row):
            line[key] = value
        list.append(line)

    async with aiofiles.open(f"backups/{filename}.json", mode="w") as f:
        await f.write(json.dumps(list).replace("},", "},\n"))
