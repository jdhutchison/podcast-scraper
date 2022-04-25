import os
import re

### ----------------------------------
### UTILITY METHODS
### ----------------------------------
def matches_any(s, regexes):
    for regex in regexes:
        if re.match(regex, s) is not None:
            return True

    return False

def tidy_up_title(title):
    title = re.sub('[!?$/:;"]', '', title)
    title = re.sub(', ', ' - ', title)
    return title

