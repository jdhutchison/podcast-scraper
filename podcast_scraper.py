import datetime
import logging
import os
import sys
import toml
from scrappers import Scraper, RssXmlScraper

### ----------------------------------
### MAIN AND FRIENDS
### ----------------------------------
def scraper_factory(scraper_config: dict) -> Scraper:
    """
    Turns scraper types from configuration into scraper objects. If there's a need to do any building as opposed
    to just instantiating then it will happen here, too. 

    params:
    scraper_config: (dict) The configuration for the scraper to create. MUST have a 'type' key with a string value mapped to it. 
    """
    scraper_type = scraper_config["type"]

    if scraper_type == "rss":
        return RssXmlScraper(scraper_config)

    else:
        raise Exception("Unsupported or unknown scrapper type of {}".format(scraper_type))


def read_config(args: list) -> dict:
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

    # Better check it exists
    if not os.path.exists(config_file_path):
        raise Exception("Can't find the configuration file {}.".format(config_file_path))

    return toml.load(config_file_path)
    

def main() -> None:
    """
    The entrypoint. Read the configuration, creates scrappers, lets them do their job. 
    """
    config = read_config(sys.argv)

    # Setup logging
    log_file = config["general"]["log_file"] if "log_file" in config["general"] else "-"
    log_level = config["general"]["log_level"] if "log_level" in config["general"] else "INFO"
    setup_logging(log_file, log_level)

    logging.info("Commencing podcast scraping at {}".format(datetime.datetime.now())) # TODO: fix timestamp format

    # Determine the active scrapers
    scrapers = config["scrapers"]
    active_scrapers = [scrapers[s] for s in scrapers.keys() if scrapers[s]["enabled"]]
    active_scraper_names = [s["name"] for s in active_scrapers]
    logging.info("There are {} active scrapers: {}.".format(len(active_scrapers), active_scraper_names))

    for scraper in active_scrapers:
        logging.info("Scraping {}".format(scraper["name"]))
        # Merge default config with scraper specific conig
        scraper_config = config["defaults"].copy()
        scraper_config.update(scraper)
        scraper_config["delay"] = config["general"]["throttle_seconds"]
        scraper_config["save_path"] = config["general"]["save_path"]

        try:
            scraper_object = scraper_factory(scraper_config)
            scraper_object.scrape_podcast()
        except Exception as e:
            logging.critical("Unable to complete scraping for {}".format(scraper["name"]))

    logging.info("Podcast scraping finished.")


def setup_logging(log_file: str = "-", log_level: str = 'INFO') -> None:
    """
    Sets up the logging with basic config. There's two modes - to stdout or to a file. 

    Other than the destination the logging to a file will also be timestamped. Defaults to stdout with a log level of INFO.

    params:
    log_file: (str) Where to log to. The value "-" is used to represent STDOUT and is the default. 
    log_level: (str) How much to log. Should be one of DEBUG, INFO, CRITICAL or FATAL. 
    """
    # String level to numeric equivalent
    level = getattr(logging, log_level.upper(), None)

    # To stdout or a file?
    if log_file == "-":
        logging.basicConfig(stream=sys.stdout, level=level, format="[%(levelname)s] %(message)s")
    else:
        logging.basicConfig(filename=log_file, level=level, format="%(asctime)s [%(levelname)s] %(message)s")


if __name__ == "__main__":
    main()

    
