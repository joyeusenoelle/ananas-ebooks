#!/usr/bin/python3
import html
import json
import os
import sys
import getopt
import re
import markovify
from ananas import PineappleBot, hourly, schedule, reply, html_strip_tags, daily, interval
from mastodon import Mastodon

class ebooksBot(PineappleBot):

  def start(self):
    try:
      self.exclude_replies = bool(self.config.exclude_replies)
    except:
      self.exclude_replies = True
    try:
      self.reply_to_mentions = bool(self.config.reply_to_mentions)
    except:
      self.reply_to_mentions = True
    try:
      self.visibility = str(self.config.visibility)
      if self.visibility not in ['public', 'unlisted', 'private', 'direct']:
        self.visibility = 'unlisted'
    except:
      self.visibility = 'unlisted'
    try:
      self.bot_name = str(self.config.bot_name)
      self.model_name = "{}-model.json".format(self.bot_name)
      self.corpus_dir_name = "{}-corpus".format(self.bot_name)
      self.acct_file = "{}-accts.json".format(self.bot_name)
    except:
      self.bot_name = ""
      self.model_name = "model.json"
      self.corpus_dir_name = "corpus"
      self.acct_file = "accts.json"
    try:
      self.max_replies = int(self.config.max_replies)
    except:
      self.max_replies = 3
    self.recent_replies = {}
    self.scrape()

  # scrapes the accounts the bot is following to build corpus
  @daily(hour=2, minute=15)
  def scrape(self):
    me = self.mastodon.account_verify_credentials()
    following = self.mastodon.account_following(me['id'])
    acctfile = self.acct_file
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
    for (dirpath, _, filenames) in os.walk(self.corpus_dir_name):
      for filename in filenames:
        with open(os.path.join(dirpath, filename)) as f:
          model = markovify.NewlineText(f, retain_original=False)
          if combined_model:
            combined_model = markovify.combine(models=[combined_model, model])
          else:
            combined_model = model
    with open(self.model_name,'w') as f:
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
    corpusfile = '{}/{}.txt'.format(self.corpus_dir_name, id)
    i = 0
    with open(bufferfile, 'w') as output:
      while toots != None and len(toots) > 0:
        # writes current amount of scraped toots without breaking line
        i = i + len(toots)
        sys.stdout.write('\r%d' % i)
        sys.stdout.flush()
        filtered_toots = list(filter(lambda x: x['spoiler_text'] == "" and x['reblog'] is None and x['visibility'] in ["public", "unlisted"], toots))
        for toot in filtered_toots:
          output.write(html_strip_tags(toot['content'], True, chr(31))+'\n')
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
    modelfile = self.model_name
    if not os.path.exists(modelfile):
      sys.exit('no model -- please scrape first')
    with open(modelfile, 'r') as f:
      reconstituted_model = markovify.Text.from_json(f.read())
#    okay_to_return = False
#    excluded_pattern = re.compile(r'{}'.format("|".join(self.excluded_words.split(","))))
#    while not okay_to_return:
    if length:
      msg = reconstituted_model.make_short_sentence(length)
    else:
      msg = reconstituted_model.make_sentence()
      #if not excluded_pattern.findall(msg):
        #okay_to_return = True
    return msg.replace(chr(31), "\n")

  # perform a generated toot to mastodon
  @hourly(minute=0)
  @hourly(minute=30)
  def toot(self):
    msg = self.generate(500)
    msg = msg.replace("@","@\\")
    msg = msg[:500]
    self.mastodon.status_post(msg,
                              visibility = self.visibility)
    print('Tooted: %s' % msg)

  # scan all notifications for mentions and reply to them
  @reply
  def post_reply(self, mention, user):
    if self.reply_to_mentions == True:
      msg = html_strip_tags(mention["content"], True, chr(31))
      rsp = self.generate(300)
      tgt = user["acct"]
      irt = mention["id"]
      vis = mention["visibility"]
      print("Received toot from {}: {}".format(tgt, msg.replace(chr(31), "\n")))
      if (tgt not in self.recent_replies.keys() or 
          self.recent_replies[tgt] < self.max_replies or
          self.max_replies == -1):
        print("Responding with {} visibility: {}".format(vis, rsp))
        final_rsp = "@{} {}".format(tgt, rsp)
        final_rsp = final_rsp[:500]
        self.mastodon.status_post(final_rsp,
                      in_reply_to_id = irt,
                      visibility = vis)
        if tgt in self.recent_replies.keys():
          self.recent_replies[tgt] = self.recent_replies[tgt] + 1
        else:
          self.recent_replies[tgt] = 1
      else:
        print("...but I've talked to them too much recently.")
    else:
      pass

    @interval(300)
    def reset_replies(self):
      self.recent_replies = {}
