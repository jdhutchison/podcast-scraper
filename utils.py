import datetime
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


