#!/usr/bin/python3
from mastodon import Mastodon
from bs4 import BeautifulSoup
import markovify
import html
import json
import os
import sys
import getopt
from ananas import PineappleBot, hourly, schedule, reply, html_strip_tags

class ebooksBot(PineappleBot):
  exclude_replies = True

  def start(self):
    try:
      self.exclude_replies = bool(self.config.exclude_replies)
    except:
      self.exclude_replies = True
    self.scrape()

  # strip html tags for text alone
  def strip_tags(self, content):
    soup = BeautifulSoup(html.unescape(content), 'html.parser')
    # remove mentions
    tags = soup.select('.mention')
    for i in tags:
      i.extract()
    # clear shortened link captions
    tags = soup.select('.invisible, .ellipsis')
    for i in tags:
      i.unwrap()
    # replace link text to avoid caption breaking
    tags = soup.select('a')
    for i in tags:
      i.replace_with(i.get_text())
    # strip html tags, chr(31) joins text in different html tags
    return soup.get_text(chr(31)).strip()

  # scrapes the accounts the bot is following to build corpus
  @daily(hour=2, minute=15)
  def scrape(self):
    me = self.mastodon.account_verify_credentials()
    following = self.mastodon.account_following(me['id'])
    acctfile = 'accts.json'
    # acctfile contains info on last scraped toot id
    try:
      with open(acctfile, 'r') as f:
        acctjson = json.load(f)
    except:
      acctjson = {}
    
    print(acctjson)
    for acc in following:
      id = str(acc['id'])
      try:
        since_id = self.scrape_id(id, since=acctjson[id])
      except:
        since_id = self.scrape_id(id)
      acctjson[id] = since_id
    
    with open(acctfile, 'w') as f:
      json.dump(acctjson, f)
      
    # generate the whole corpus after scraping so we don't do at every runtime
    combined_model = None
    for (dirpath, _, filenames) in os.walk("corpus"):
      for filename in filenames:
        with open(os.path.join(dirpath, filename)) as f:
          model = markovify.NewlineText(f, retain_original=False)
          if combined_model:
            combined_model = markovify.combine(models=[combined_model, model])
          else:
            combined_model = model
    with open('model.json','w') as f:
      f.write(combined_model.to_json())

  def scrape_id(self, id, since=None):
    # excluding replies was a personal choice. i haven't made an easy setting for this yet
    toots = self.mastodon.account_statuses(id, since_id=since, exclude_replies=self.exclude_replies)
    # if this fails, there are no new toots and we just return old pointer
    try:
      new_since_id = toots[0]['id']
    except:
      return since
    bufferfile = 'buffer.txt'
    corpusfile = 'corpus/%s.txt' % id
    i = 0
    with open(bufferfile, 'w') as output:
      while toots != None:
        # writes current amount of scraped toots without breaking line
        i = i + len(toots)
        sys.stdout.write('\r%d' % i)
        sys.stdout.flush()
        filtered_toots = list(filter(lambda x: x['spoiler_text'] == "" and x['reblog'] is None and x['visibility'] in ["public", "unlisted"], toots))
        for toot in filtered_toots:
          output.write(html_strip_tags(toot['content'])+'\n')
        toots = self.mastodon.fetch_next(toots)
      # buffer is appended to the top of old corpus
      if os.path.exists(corpusfile):
        with open(corpusfile,'r') as old_corpus:
          output.write(old_corpus.read())
      directory = os.path.dirname(corpusfile)
      if not os.path.exists(directory):
        os.makedirs(directory)
      os.rename(bufferfile,corpusfile)
      sys.stdout.write('\n')
      sys.stdout.flush()
    return new_since_id

  # returns a markov generated toot
  def generate(self, length=None):
    modelfile = 'model.json'
    if not os.path.exists(modelfile):
      sys.exit('no model -- please scrape first')
    with open(modelfile, 'r') as f:
      reconstituted_model = markovify.Text.from_json(f.read())
    if length:
      msg = reconstituted_model.make_short_sentence(length)
    else:
      msg = reconstituted_model.make_sentence()
    return msg.replace(chr(31), "\n")

  # perform a generated toot to mastodon
  @hourly(minute=0)
  def toot(self):
    msg = self.generate(500)
    self.mastodon.toot(msg)
    print('Tooted: %s' % msg)

  # scan all notifications for mentions and reply to them
  @reply
  def post_reply(self, mention, user):
    msg = html_strip_tags(mention["content"])
    rsp = self.generate(400)
    tgt = user["acct"]
    irt = mention["id"]
    vis = mention["visibility"]
    print("Received toot from {}: {}".format(tgt, msg))
    print("Responding with {} visibility: {}".format(vis, rsp))
    final_rsp = "@{} {}".format(tgt, rsp)
    final_rsp = final_rsp[:500]
    self.mastodon.status_post(final_rsp,
                  in_reply_to_id = irt,
                  visibility = vis)
