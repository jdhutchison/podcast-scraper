import datetime
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
    title = re.sub('[!?$/:;"]', '', title)
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
