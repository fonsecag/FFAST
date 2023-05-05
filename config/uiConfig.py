from collections import defaultdict


def configStyleSheet(sheet):
    for key, value in config["envs"].items():
        sheet = sheet.replace(f"@{key}", value)

    return sheet


config = {
    "envs": {
        "HLColor1": "#4e747a",
        "HLColor2": "#1ca6bb",
        "BGColor1": "#202225",
        "BGColor2": "#2F3136",
        "BGColor3": "#36393F",
        "BGColor4": "#494d55",
        "BGColor5": "#575b63",
        "TextColor1": "#b9bbc2",
        "TextColor2": "#ffffff",
        "TextColor3": "#b9bbc2",
        "TextColorHover": "#dbdde4",
    },
    "icons": {
        "close": "close.png",
        "expanded": "expanded.png",
        "collapsed": "collapsed.png",
        "delete": "close.png",
        "rename": "rename.png",
        "legend": "legend.png",
        "subbing": "subbing.png",
        "leftArrow": "collapsedLeft.png",
        "rightArrow": "collapsed.png",
        "start": "start.png",
        "pause": "pause.png",
    },
}


def getIcon(name):
    icon = config["icons"].get(name, "default.png")
    return f"icon:{icon}"
