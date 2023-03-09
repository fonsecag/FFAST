from collections import defaultdict

def configStyleSheet(sheet):
    for (key, value) in config["envs"].items():
        sheet = sheet.replace(f"@{key}", value)

    return sheet

config = {
    "envs": {
        "HLColor1": "#17a2b8",
        "HLColor2": "#138294",
        "BGColor1": "#202225",
        "BGColor2": "#2F3136",
        "BGColor3": "#36393F",
        "BGColor4": "#494d55",
        "TextColor1": "#b9bbc2",
        "TextColor2": "#ffffff",
        "TextColorHover": "#dbdde4",
    },
    "icons": defaultdict(lambda : "default.png"),
}

config['icons'].update(
    {"close":"close.png"}
)