import discord
import feedparser
import os
import asyncio
import schedule
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
from openai import OpenAI

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

client_ai = OpenAI(api_key=OPENAI_KEY)

CHANNELS = {
    "regeringen": int(os.getenv("CHANNEL_REGERINGEN")),
    "riksdagen": int(os.getenv("CHANNEL_RIKSDAGEN")),
    "partier": int(os.getenv("CHANNEL_PARTIER")),
    "kriminalitet": int(os.getenv("CHANNEL_KRIMINALITET")),
    "ekonomi": int(os.getenv("CHANNEL_EKONOMI")),
    "globalt": int(os.getenv("CHANNEL_GLOBALT")),
    "eu": int(os.getenv("CHANNEL_EU")),
}

CATEGORY_NAMES = {
    "regeringen": "🏛 REGERINGEN",
    "riksdagen": "📜 RIKSDAGEN",
    "partier": "🗳 PARTIER & POLITIKER",
    "kriminalitet": "🚨 KRIMINALITET",
    "ekonomi": "💰 EKONOMI",
    "globalt": "🌍 GLOBAL POLITIK",
    "eu": "🇪🇺 EU",
}

LIMITS = {
    "regeringen": None,
    "riksdagen": None,
    "partier": 3,
    "kriminalitet": 3,
    "ekonomi": 3,
    "globalt": 3,
    "eu": 3,
}

FEEDS = {

    "regeringen": [
        "https://www.regeringen.se/pressmeddelanden/rss.xml"
    ],

    "riksdagen": [
        "https://www.riksdagen.se/sv/aktuellt/rss/aktuellt-fran-riksdagen/"
    ],

    "partier": [
        "https://www.svt.se/nyheter/inrikes/rss.xml"
    ],

    "kriminalitet": [
        "https://www.svt.se/nyheter/inrikes/rss.xml"
    ],

    "ekonomi": [
        "https://www.svt.se/nyheter/ekonomi/rss.xml"
    ],

    "globalt": [
        "https://www.svt.se/nyheter/utrikes/rss.xml"
    ],

    "eu": [
        "https://www.svt.se/nyheter/utrikes/rss.xml"
    ]
}

KEYWORDS = {

    "kriminalitet": [
        "skjutning",
        "sprängning",
        "gäng",
        "mord"
    ],

    "partier": [
        "regeringen",
        "riksdagen",
        "moderaterna",
        "socialdemokraterna",
        "sd",
        "vänsterpartiet"
    ],

    "eu": [
        "eu",
        "bryssel",
        "europa"
    ]
}

SAVE_FILE = "posted_links.json"

MAX_AGE_DAYS = 30

client = discord.Client(intents=discord.Intents.default())


def load_links():

    if not os.path.exists(SAVE_FILE):
        return {}

    with open(SAVE_FILE, "r") as f:
        return json.load(f)


def save_links(data):

    with open(SAVE_FILE, "w") as f:
        json.dump(data, f)


def clean_links(data):

    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)

    new = {}

    for link, timestamp in data.items():

        if datetime.fromisoformat(timestamp) > cutoff:
            new[link] = timestamp

    return new


posted_links = load_links()

posted_links = clean_links(posted_links)

save_links(posted_links)


def get_text(entry):

    title = entry.title if hasattr(entry, "title") else ""

    summary = ""

    if hasattr(entry, "summary"):
        summary = entry.summary

    elif hasattr(entry, "description"):
        summary = entry.description

    return title + " " + summary


async def summarize(text):

    try:

        response = client_ai.chat.completions.create(

            model="gpt-4o-mini",

            messages=[
                {
                    "role": "system",
                    "content": "Sammanfatta nyheten kort, sakligt och neutralt på svenska i max 2 meningar."
                },
                {
                    "role": "user",
                    "content": text
                }
            ]

        )

        return response.choices[0].message.content.strip()

    except Exception as e:

        print("AI error:", e)

        return "Kunde inte skapa sammanfattning."


async def post_category(category):

    channel = client.get_channel(CHANNELS[category])

    if not channel:
        return

    await channel.send(
        f"\n{CATEGORY_NAMES[category]} – {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    )

    limit = LIMITS[category]

    count = 0

    for feed_url in FEEDS[category]:

        feed = feedparser.parse(feed_url)

        for entry in feed.entries:

            if limit and count >= limit:
                break

            if entry.link in posted_links:
                continue

            text = get_text(entry)

            if category in KEYWORDS:

                if not any(k in text.lower() for k in KEYWORDS[category]):
                    continue

            summary = await summarize(text)

            embed = discord.Embed(

                title=entry.title,
                description=summary,
                url=entry.link,
                color=0x005BBB

            )

            await channel.send(embed=embed)

            posted_links[entry.link] = datetime.now().isoformat()

            save_links(posted_links)

            count += 1

    if count == 0:

        await channel.send("Inga nya nyheter.")


async def post_all():

    print("Kollar nyheter...")

    for category in CHANNELS:

        await post_category(category)


async def scheduler():

    while True:

        schedule.run_pending()

        await asyncio.sleep(60)


@client.event
async def on_ready():

    print("Bot online:", client.user)

    await post_all()

    schedule.every(15).minutes.do(
        lambda: asyncio.create_task(post_all())
    )

    asyncio.create_task(scheduler())


client.run(DISCORD_TOKEN)
