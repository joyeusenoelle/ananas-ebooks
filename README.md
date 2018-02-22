# ananas-ebooks

Based on [Maple](https://computerfairi.es/@squirrel)'s [mastodon-ebooks.py](https://github.com/Lana-chan/mastodon-ebooks.py).

This simply takes Maple's work and adapts it for the ananas framework, allowing you to skip the cron jobs and manual posting.

Usage:

1. In the directory where ananas-ebooks is installed, run `pip3 install -r requirements.txt` to make sure you have all the requirements for the bot.
2. Create a Mastodon account to be the ebooks bot.
3. In Mastodon, use your bot account to follow each account you want to scrape to create your bot. **DO NOT** follow any accounts you don't want to scrape.
4. In Mastodon, under Preferences > Development, create a new app for the bot. You can just call it "Ebooks" and leave "Application Website" blank. Do not change the Redirect URI.
5. On the next screen, click on the name you gave your bot ("Ebooks" or something else). You'll get a client key, client secret, and access token.
    (Alternately, you can use a script [like this](https://gist.github.com/Lana-chan/b0d937968d22eca6dcd79a0524449f1d) to generate user secrets to be used by the ebooks script.)
6. Open `config.cfg`. Make the following changes:
    1. Change `domain` to whatever your bot's instance is.
    2. Paste your client key after `client_id`, your client secret after `client_secret`, and your access token after `access_token`.
    3. By default, your bot will not scrape toots that are replies to other users. set `exclude_replies = False` if you want your bot to scrape replies in addition to "raw" toots.
7. You're done! Type `ananas config.cfg` into your command line and watch your bot spring into action. It will start by scraping each account you've followed, then toot once each hour and look for replies so it can toot back.

If you want to re-scrape toots from your followed accounts, just stop the bot (with Ctrl-C) and start it again; it will check for new toots every time it starts up.

## Why do I have to follow everyone I want to scrape? Can't I just give it a list of usernames?

It's an anti-harassment measure. This way, if you want to make an ebooks bot of someone's toots, they're notified that the bot exists.

## What if I already have an ananas bot running and I'd like to run them in tandem?

Just copy `ebooks.py` and `requirements.txt` into that bot's directory, and modify that `config.cfg` to have an `[EBOOKS]` section as described in step 6 above. ananas bots play very nicely with each other.

If you've already scraped some accounts and want to keep that data, copy over `accts.json`, `model.json`, and the `corpus` directory too. All that data will stay intact the next time you launch ananas.

## This has been running for a long time, and I've tooted a lot since then. How do I get my new toots into the corpus?

The bot automatically scrapes new toots from its followed accounts once a day at 2:15 AM (to minimize collision with other tasks).

## What if I want my bot to toot at a different time?

I'd love to be able to include this in the `config.cfg` file, but for various technical reasons it's not possible right now. Instead, you'll have to actually open up `ebooks.py`.

In `ebooks.py`, go to line `129`. You'll see this:

    @hourly(minute=0)

If you want your bot to post once an hour, but not **on** the hour, change the value of `minute`. For example, if you want your bot to post at 12:15, 1:15, 2:15, etc., change it to `minute=15`.

If you want your bot to post **more** than once an hour, just add another line. For example:

    @hourly(minute=12)
    @hourly(minute=42)
    def toot(self):
      ...

will post every half-hour, at XX:12 and at XX:42.

If you want your bot to post **less** than once an hour, change `@hourly` to `@daily`. By default, this will make it post once a day, but like `@hourly`, you can stack them up. To post every four hours, you might do:

    @daily(hour=0, minute=15)
    @daily(hour=4, minute=15)
    @daily(hour=8, minute=15)
    @daily(hour=12, minute=15)
    @daily(hour=16, minute=15)
    @daily(hour=20, minute=15)
    def toot(self):
      ...

Note how that uses 24-hour time.

You can see more details at the [ananas repo](https://github.com/chr-1x/ananas).
