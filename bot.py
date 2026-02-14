import discord
import feedparser
import os
import asyncio
import schedule
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

CHANNELS = {
    "dagens": int(os.getenv("CHANNEL_DAGENS")),
    "riksdagen": int(os.getenv("CHANNEL_RIKSDAGEN")),
    "eu": int(os.getenv("CHANNEL_EU")),
    "ekonomi": int(os.getenv("CHANNEL_EKONOMI")),
    "gang": int(os.getenv("CHANNEL_GANG")),
}

client = discord.Client(intents=discord.Intents.default())

SAVE_FILE = "posted_links.json"

MAX_AGE_DAYS = 30

LIMITS = {
    "dagens": 3,
    "ekonomi": 3,
    "eu": 3,
    "gang": 3,
    "riksdagen": None
}

FEEDS = {

    "dagens": [
        "https://www.svt.se/nyheter/inrikes/rss.xml"
    ],

    "riksdagen": [
        "https://www.riksdagen.se/sv/aktuellt/rss/aktuellt-fran-riksdagen/",
        "https://www.riksdagen.se/sv/press/rss/pressmeddelanden/"
    ],

    "ekonomi": [
        "https://www.svt.se/nyheter/ekonomi/rss.xml"
    ],

    "eu": [
        "https://www.svt.se/nyheter/utrikes/rss.xml"
    ],

    "gang": [
        "https://www.svt.se/nyheter/inrikes/rss.xml"
    ]
}

KEYWORDS = {

    "gang": [
        "skjutning",
        "gäng",
        "sprängning",
        "kriminell",
        "gängkriminalitet"
    ],

    "ekonomi": [
        "ränta",
        "inflation",
        "bank",
        "budget",
        "ekonomi",
        "riksbank"
    ],

    "eu": [
        "eu",
        "bryssel",
        "europa"
    ]
}

CATEGORY_NAMES = {
    "dagens": "📰 DAGENS NYHETER",
    "riksdagen": "🏛 RIKSDAGEN",
    "ekonomi": "💰 EKONOMI",
    "eu": "🇪🇺 EU-POLITIK",
    "gang": "🚨 GÄNGKRIMINALITET"
}


# load links
def load_links():

    if not os.path.exists(SAVE_FILE):
        return {}

    with open(SAVE_FILE, "r") as f:
        return json.load(f)


# save links
def save_links(data):

    with open(SAVE_FILE, "w") as f:
        json.dump(data, f)


# clean old links
def clean_old_links(data):

    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)

    new_data = {}

    for link, timestamp in data.items():

        post_time = datetime.fromisoformat(timestamp)

        if post_time > cutoff:
            new_data[link] = timestamp

    return new_data


posted_links = load_links()

posted_links = clean_old_links(posted_links)

save_links(posted_links)


def get_summary(entry):

    if hasattr(entry, "summary"):
        text = entry.summary

    elif hasattr(entry, "description"):
        text = entry.description

    else:
        return "Klicka för att läsa mer."

    text = text.replace("<p>", "").replace("</p>", "")

    return text[:200] + "..."


def get_text(entry):

    title = entry.title if hasattr(entry, "title") else ""

    summary = ""

    if hasattr(entry, "summary"):
        summary = entry.summary

    elif hasattr(entry, "description"):
        summary = entry.description

    return title + " " + summary


async def post_category(category):

    channel = client.get_channel(CHANNELS[category])

    if not channel:
        print(f"Kunde inte hitta kanal: {category}")
        return

    limit = LIMITS[category]

    new_posts = 0

    await channel.send(
        f"\n🇸🇪 **{CATEGORY_NAMES[category]} – {datetime.now().strftime('%Y-%m-%d %H:%M')}**\n"
    )

    for feed_url in FEEDS[category]:

        feed = feedparser.parse(feed_url)

        for entry in feed.entries:

            if limit is not None and new_posts >= limit:
                break

            if entry.link in posted_links:
                continue

            text = get_text(entry)

            if category in KEYWORDS:

                if not any(word in text.lower() for word in KEYWORDS[category]):
                    continue

            embed = discord.Embed(

                title=entry.title,
                description=get_summary(entry),
                url=entry.link,
                color=0x005BBB

            )

            embed.set_footer(
                text=CATEGORY_NAMES[category]
            )

            await channel.send(embed=embed)

            posted_links[entry.link] = datetime.now().isoformat()

            save_links(posted_links)

            new_posts += 1

    # om inga nyheter
    if new_posts == 0:

        await channel.send("Inga nya nyheter.")

    print(f"{category}: {new_posts} nya nyheter")


async def post_all():

    print("Kollar efter nya nyheter...")

    for category in CHANNELS:
        await post_category(category)


async def scheduler_loop():

    while True:

        schedule.run_pending()

        await asyncio.sleep(60)


@client.event
async def on_ready():

    print(f"Inloggad som {client.user}")

    await post_all()

    schedule.every(1).hours.do(
        lambda: asyncio.create_task(post_all())
    )

    asyncio.create_task(scheduler_loop())


client.run(DISCORD_TOKEN)
