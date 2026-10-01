"""Director-only cipher specification. Never include the key in player handouts."""
from string import ascii_uppercase

PLAIN = ascii_uppercase
WRITTEN = "ZCLMHUTKOEVSDIPRQGFNXBWAYJ"
MEETING = "THIRD LEDGER LIFT YARD. THIRD BELL AFTER DARK IN TWO DAYS. BRING THE BOOK. COME ALONE."
NEUTRAL_REPLY = "THE BOOK IS SAFE. I WILL COME."
LABELS = ("GILT MASK", "PRIVATE SALE")


def encode(message):
    return message.upper().translate(str.maketrans(PLAIN, WRITTEN))


def decode(message):
    return message.upper().translate(str.maketrans(WRITTEN, PLAIN))


def handout(text, heading):
    """Extract only the contiguous player-facing block after a scene heading."""
    body = text.split(heading, 1)[1]
    lines = body.splitlines()
    result = []
    started = False
    for line in lines:
        if line.startswith(">"):
            started = True
            result.append(line[2:] if line.startswith("> ") else "")
        elif started:
            break
    if not started:
        raise ValueError("Missing player handout: " + heading)
    return "\n".join(result).strip()
