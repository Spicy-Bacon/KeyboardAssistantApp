TYPO_MAP = {
    "teh": "the",
    "recieve": "receive",
    "definately": "definitely",
    "seperate": "separate",
    "occured": "occurred",
    "untill": "until",
    "adress": "address",
    "becuase": "because",
    "wierd": "weird",
    "helllo": "hello",
    "thier": "their",
    "acheive": "achieve",
}

CONTRACTIONS = {
    "dont": "don't",
    "cant": "can't",
    "im": "I'm",
    "ill": "I'll",
    "wont": "won't",
    "isnt": "isn't",
    "arent": "aren't",
    "wasnt": "wasn't",
    "werent": "weren't",
    "shouldnt": "shouldn't",
    "couldnt": "couldn't",
    "wouldnt": "wouldn't",
}

CONTEXTUAL_REPLACEMENTS = {
    ("will", "meat"): "meet",
    ("to", "much"): "too",
    ("too", "go"): "to",
}

DEFAULT_EXCLUDED_APP_HINTS = {
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "windowsterminal.exe",
    "code.exe",
    "devenv.exe",
    "pycharm64.exe",
    "rider64.exe",
}

