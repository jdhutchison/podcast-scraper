from abc import ABC, abstractmethod
import datetime
import requests
import re
import time
import os
import utils
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
import lxml


class Scraper(ABC):
    """
    The base class for all scrappers. Extending implementations need to only implement get_episodes_from_feed and
    get_episodes_from_feed to handle getting and processing the feed. This base class contains the logic for
    everything else. 
    """

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
        self.max_episode_age_in_days = config["max_episode_age_in_days"] if "max_episode_age_in_days" in config else 0
        if self.max_episode_age_in_days > 0:
            self.max_age_delta = datetime.timedelta(days=self.max_episode_age_in_days)

    def scrape_podcast(self):
        """
        Fetches the podcast feed, parses it, and then processes each episode, downloading those that meet all 
        the criteria. 
        """
        episodes = self.get_episodes_from_feed()
        print("There are {} episodes".format(len(episodes)))
        for ep in episodes:
            try:
                episode_data = self.get_episode_data(ep)
                episode_status = self.__check_episode(episode_data)
                if episode_status == "OK":
                    print("Downloading episode #{episode} - {title}".format(**episode_data))
                    self.__download_episode(episode_data)
                elif episode_status == "SKIP":
                    pass
                elif episode_status == "HALT":
                    break
            except Exception as e:
                print("Error while processing episode {} because {}: {}. Skipping.".format(ep.title.text, type(e), e))
                
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
        """
        """
        path_values = dict()
        path_values["ep_title"] = utils.tidy_up_title(episode_data["title"])
  
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
        if len(self.ignore_if_title_match_any) and utils.matches_any(episode_data["unparsed_title"], self.ignore_if_title_match_any):
            print("Skipping episode {} - title matches an exlcusion filter, one of: {}.".format(episode_data["unparsed_title"], self.ignore_if_title_match_any))
            return "SKIP"       
        
        # matches one good regex
        if len(self.title_must_match_one_of) and not utils.matches_any(episode_data["unparsed_title"], self.title_must_match_one_of):
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
        
        # not too old - HALT rather than skip on the (validated) assumption that feeds are in descending chonological order
        now = datetime.datetime.now()
        if self.max_episode_age_in_days > 0:
            if (now - self.max_age_delta) > episode_data["published_date"]:
                print("Halting on episode {} due to it being too old (published more than {} days ago)".format(episode_data["title"], self.max_episode_age_in_days))
                return "HALT"                
        
        # not too many existing or we can delete episodes if needed
        path = os.path.dirname(episode_data["download_path"])
        current_episodes = len(os.listdir(path)) if os.path.exists(path) else 0
        if current_episodes and (0 < self.max_episodes <= current_episodes) and not self.delete_episodes_if_over_limit:
            print("Halting on episode {} due to the maxium number of episodes for this podcast reached ({})".format(episode_data["title"], self.max_episodes))
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
        Where the magic happens. Downloads an episode, ensuring the containing paths such as for the podcast overall
        and the season if applicable exist before downloading commences so the episode has a directory to go to. 
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
        self.title_parsing_regex = config["title_parsing_regex"] if "title_parsing_regex" in config else None
        super(RssXmlScraper, self).__init__(config)

    def get_episodes_from_feed(self):
        response = requests.get(self.feed_url, headers={'User-Agent': 'curl/7.68.0'})
        dom = BeautifulSoup(response.text, 'xml')
        return dom.find_all('item')

    def get_episode_data(self, ep):
        episode_data = dict()
        if ep.find('itunes:season') is not None:
            episode_data["season"] = ep.find('itunes:season').text
        unzoned_timestamp = parsedate_to_datetime(ep.pubDate.text).timestamp()
        episode_data["published_date"] = datetime.datetime.utcfromtimestamp(unzoned_timestamp)
        episode_data["url"] = ep.find("enclosure")['url'] 
 
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

            
        
