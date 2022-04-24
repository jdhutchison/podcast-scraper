from abc import ABC, abstractmethod
import sys
import toml
import datetime
import requests
import re
import time
import os
from bs4 import BeautifulSoup


### ----------------------------------
### UTILITY METHODS
### ----------------------------------
def matches_any(s, regexes):
    for regex in regexes:
        if re.match(regex, s) is not None:
            return True

    return False

def tidy_up_title(title):
    title = re.sub('[!?$/:;]', '', title)
    title = re.sub(', ', ' - ', title)
    return title

def count_files_in_dir(path):
    return len(os.listdir(path))


### ----------------------------------
### UTILITY METHODS
### ----------------------------------
class Scraper(ABC):

    def __init__(self, config):
        self.feed_url = config["feed_url"]
        self.save_path = config["save_path"]
        self.delay = config["delay"]
        self.podcast_name = config["name"]
        self.min_season_width = config["min_season_width"]
        self.min_episode_width = config["min_ep_number_width"]
        self.download_path_format = config["download_path_format"]
        self.max_episodes = config["max_episodes"]
        self.halt_on_existing = config["halt_on_existing"]
        self.ignore_if_title_match_any = config["skip_if_matching"]
        self.title_must_match_one_of = config["fetch_if_matching"]
        self.get_episode_number_from_title = config["get_episode_number_from_title"]
        self.delete_episodes_if_over_limit = config["delete_episodes_if_over_limit"]

    def scrape_podcast(self):
        episodes = self.get_episodes_from_feed()
        print("There are {} episodes".format(len(episodes)))
        for ep in episodes:
            episode_data = self.get_episode_data(ep)
            episode_status = self.__check_episode(episode_data)
            if episode_status == "OK":
                print("Downloading episode #{episode} - {title}".format(**episode_data))
                self.__download_episode(episode_data)
            elif episode_status == "SKIP":
                pass
            elif episode_status == "HALT":
                break

        print("Scrape finished for {}.".format(self.podcast_name))



    @abstractmethod
    def get_episode_data(self, ep):
        """
        Must extract the following:
        - episode title
        - episode number
        - season number (if exists)
        - download url
        - published time
        """
        pass

    @abstractmethod
    def get_episodes_from_feed(self):
        pass

    def __determine_download_path(self, episode_data):
        path_values = dict()
        path_values["ep_title"] = tidy_up_title(episode_data["title"])
  
        # Pad out season and episode numbers
        if "season" in episode_data:
            path_values["season"] = episode_data["season"].zfill(self.min_season_width)
        path_values["ep_number"] = episode_data["episode"].zfill(self.min_episode_width)
        
        filename = self.download_path_format.format(**path_values)
        return os.path.join(self.save_path, self.podcast_name, filename)
        

    def __check_episode(self, episode_data):
        """
        Checks to see if the episode should be downloaded or not and if the scraper should skip this episode or stop altogether. 
        This method should return one of three string values:
        - "OK": episode can be downloaded
        - "SKIP": Skip episode but keep looking at others
        - "HALT": Do not process any more. 
        """
        # has no URL
        if "url" not in episode_data or episode_data["url"] is None:
            print("Skipping episode {} - no download URL.".format(episode_data["unparsed_title"]))
            return "SKIP"

        # no match bad regexes
        if len(self.ignore_if_title_match_any) and matches_any(episode_data["unparsed_title"], self.ignore_if_title_match_any):
            print("Skipping episode {} - title matches an exlcusion filter, one of: {}.".format(episode_data["unparsed_title"], self.ignore_if_title_match_any))
            return "SKIP"       
        
        # matches one good regex
        if len(self.title_must_match_one_of) and not matches_any(episode_data["unparsed_title"], self.title_must_match_one_of):
            print("Skipping episode {} - title does not meet requirements to match at least one of: {}.".format(episode_data["unparsed_title"], self.title_must_match_one_of))
            return "SKIP"

        # Already exists
        episode_data["download_path"] = self.__determine_download_path(episode_data)
        if os.path.exists(episode_data["download_path"]):
           # Halt or keep going? 
           if self.halt_on_existing:
               print("Halting on episode {} - already fetched. Scraper is up to date.".format(episode_data["unparsed_title"]))
               return "HALT"
           else:
               print("Skipping episode {} - already fetched.".format(episode_data["unparsed_title"]))
               return "SKIP"
        
        # not too old
        # TODO: implement age check
        
        # not too many existing or we can delete episodes if needed
        path = os.path.dirname(episode_data["download_path"])
        if 0 < self.max_episodes >= count_files_in_dir(path) and not self.delete_episodes_if_over_limit:
            print("Halting on episode {} due to the maxium number of episodes for this podcast reached ({})".format(episode_data["title"], self.max_episodes_before_halt))
            return "HALT"

        # No reason not to fetch it. 
        return "OK"

    def __delete_old_episodes_if_needed(self, download_path):
        """
        Deletes old episodes in order to get a podcast under the limit to download a new episode. Will delete as many episodes
        as required. 
  
        params: 
        download_path: (str) the path the new episode is to downloaded into. 
        """
        path = os.path.dirname(download_path)
        # The +1 is because we're about to download a new episode
        over_limit = len(os.listdir(path)) - (self.max_episodes + 1) 

        if self.delete_episodes_if_over_limit and over_limit > 0:
            # Determine the oldest n files and delete them
            files = [os.path.join(path, f) for f in os.listdir(path) if not os.path.isdir(os.path.join(path, f))] # Exclude directories
            episodes = sorted(files, key=os.path.getctime)
            for ep in episodes[0:over_limit]:
                print("Deleting epsiode '{}' to observe epsidoe limit ({}).".format(ep, self.max_episodes))
                os.remove(ep)

    def __download_episode(self, episode_data):
        """
        Where the magic happens. Downloads an episode, ensuring the containing paths 
        """
        # Check the directory for the podcast and the season (if applicable) exist
        podcast_home_path = os.path.join(self.save_path, self.podcast_name)
        if not os.path.exists(podcast_home_path):
            os.mkdir(podcast_home_path)

        season_path = os.path.split(episode_data["download_path"])[0]
        if not os.path.exists(season_path):
            os.mkdir(season_path)

        # Delete epsidoes if needed to stick to limit, if a limit exists AND permitted to delete stuff
        if self.max_episodes and self.delete_episodes_if_over_limit:
            self.__delete_old_episodes_if_needed(episode_data["download_path"])       

        fileResp = requests.get(episode_data["url"], stream = True)
        try:
            with open(episode_data["download_path"], 'wb') as fd:
                for chunk in fileResp.iter_content(chunk_size=1024):
                    fd.write(chunk)
            time.sleep(self.delay) # Delay to not overload servers
        except e:
            print("Unable to download {} due to {}".format(episode_data["url"], e))        


class RssXmlScraper(Scraper):

    def __init__(self, config):
        self.parse_episode_from_title = config["get_episode_number_from_title"]
        self.title_parsing_regex = config["title_parsing_regex"]
        super(RssXmlScraper, self).__init__(config)

    def get_episodes_from_feed(self):
        response = requests.get(self.feed_url)
        dom = BeautifulSoup(response.text, 'lxml')
        return dom.find_all('item')

    def get_episode_data(self, ep):
        episode_data = dict()
        if ep.find('itunes:season') is not None:
            episode_data["season"] = ep.find('itunes:season').text
        # episode_data["published_date"] = ep.pubDate.text # TODO: parse pub date into an actual timestamp  
        episode_data["url"] = ep.find("enclosure")['url'] 
        if self.podcast_name == "The Medici Podcast": 
            print(ep)  
        episode_data["title"] = ep.title.text
        episode_data["unparsed_title"] = ep.title.text
        if ep.find('itunes:episode') is not None:
            episode_data["episode"] = ep.find('itunes:episode').text

        # manual extract title and episode number
        if self.parse_episode_from_title:
           regex = re.search(self.title_parsing_regex, ep.title.text)
           # Title does not parse if there isnn't 2 groups
           if regex is not None and len(regex.groups()) >= 2:
               episode_data["episode"] = regex.group(1)
               episode_data["title"] = regex.group(2)

        return episode_data
           

### ----------------------------------
### MAIN AND FRIENDS
### ----------------------------------
def scraper_factory(scraper_config):
    scraper_type = scraper_config["type"]

    if scraper_type == "rss":
        return RssXmlScraper(scraper_config)

    else:
        raise Exception("Unsupported or unknown scrapper type of {}".format(scraper_type))

def read_config(args):
    """
    Checks if there is a command line argument and if so tries to use that argument as the path to 
    load configuration. If there is no command line argument then the config file is assumed to be
    'podcast_scraper.toml'. If whatever path is used doesn't exist an exception is thrown. 

    params:
    args: (str[]) Command line arguments, ie. sys.argv.

    returns: (dict) The loaded configuration.  
    """
    # Determine what config file to use - the default or one from the command line. 
    config_file_path = "podcast_scraper.toml"
    if len(args) >= 2:
        config_file_path = args[1]

    print("Using '{}' as the configuration file".format(config_file_path))

    # Better check it exists
    if not os.path.exists(config_file_path):
        raise Exception("Can't find the configuration file {}.".format(config_file_path))

    return toml.load(config_file_path)
    

if __name__ == "__main__":
    print("Commencing podcast scraping at {}".format(datetime.datetime.now())) # TODO: fix timestamp format
    config = read_config(sys.argv)

    # Determine the active scrapers
    scrapers = config["scrapers"]
    active_scrapers = [scrapers[s] for s in scrapers.keys() if scrapers[s]["enabled"]]
    active_scraper_names = [s["name"] for s in active_scrapers]
    print("There are {} active scrapers: {}.".format(len(active_scrapers), active_scraper_names))

    for scraper in active_scrapers:
        print("Scraping {}".format(scraper["name"]))
        # Merge default config with scraper specific conig
        scraper_config = config["defaults"].copy()
        scraper_config.update(scraper)
        scraper_config["delay"] = config["general"]["throttle_seconds"]
        scraper_config["save_path"] = config["general"]["save_path"]
        

        try:
            scraper_object = scraper_factory(scraper_config)
            scraper_object.scrape_podcast()
        except e:
            print("Unable to complete scraping for {} due to {}".format(scraper["name"], e))

    print("Podcast scraping finished.")

    
