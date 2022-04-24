import datetime
import os
import sys
import toml
from scrappers import RssXmlScraper
           

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

    
