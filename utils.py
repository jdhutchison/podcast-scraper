import datetime
import glob
import logging
import os
import re

### ----------------------------------
### UTILITY METHODS
### ----------------------------------
def matches_any(s: str, regexes: list) -> bool:
    """
    Tests if a string matches any of a list of regular expressions. Returns true on the first
    successful match. 

    params:
    s: (str) The test string
    regexes: (list) The tests. 

    returns bool: returns True if the string matches any one of the regular expressions. 
    """

    for regex in regexes:
        if re.match(regex, s) is not None:
            return True

    return False


def tidy_up_title(title: str) -> str:
    """
    Cleans up a title by removing characters we don't want in a filename. 

    params:
    title: (str) the string to clean up

    returns str: a nice, clean title. 
    """
    title = re.sub('[!?$/:;"\u0000\u0093â]', '', title)
    title = re.sub(', ', ' - ', title)
    return title


def simple_title_parsing(original_title: str) -> (str, str):
    """
    Parses the title without resorting to regular expressions. This is to assist with cases where the regexes
    seem to fail. Especially cases with titles like [num]: [title] or [num]-[title]. 

    If the input doesnt start with numeric characters then this function is no good. 

    params:
    original_title: (str) the original title

    returns tuple(str, str): the episode number and the title as a tuple. 
    """
    index = 0
    while original_title[index].isnumeric():
        index += 1
    
    episode = original_title[:index]
    title = original_title[index+1:].strip()
    return (episode, title)


def infer_episode_number_from_path(path: str) -> (int):
    """
    Used to determine the next episode number in sequence. To be used if the episode title or RSS feed cannot be used to 
    to determine the episode number. 

    If there are no MP3s in the download path then this is assumed to be the first episode. Otherwise the epsidoe number is
    parsed from the title of the newest M3 file in the directory. 

    params:
    path: (str) Diretory of where the podcast series is downloaded to.

    returns (int): The next episode number for the podcast.
    """
    # No directory - first episode
    if not os.path.exists(path):
        return 1

    files = os.listdir(path)
    
    # Nothing there: first episode
    if len(files) == 0:
        return 1

    # Identify the newest file
    newest_file = max(glob.iglob('{}/*.mp3'.format(path)), key=os.path.getmtime)
    newest_file = newest_file.split('/')[-1]
    episode = simple_title_parsing(newest_file)[0]
    return int(episode.lstrip('0')) + 1
