import os
import requests
from zebra import Zebra
from zebrafy import ZebrafyImage
from dotenv import load_dotenv
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatSub
import asyncio
import re
from collections import defaultdict
import datetime
from json import loads

load_dotenv()

USER_SCOPE = [AuthScope.CHAT_READ]
TARGET_CHANNELS = loads(os.getenv("TARGET_CHANNELS"))

z = Zebra()
z.setqueue('Zebra ZPL Direct')

lastPrintCall = "^XA^XZ"

# Track gifted subs accumulation
gifted_subs = defaultdict(int)

async def on_ready(ready_event: EventData):
    print('Bot ist bereit für Arbeit, Channels werden betreten...')
    print_text(f"{datetime.datetime.now().strftime("%H:%M:%S")} STARTUP - Bot ist bereit für Arbeit, Channels werden betreten...")
    await ready_event.chat.join_room(TARGET_CHANNELS)
    print_text(f"{datetime.datetime.now().strftime("%H:%M:%S")} STARTUP - Channels wurden betreten: {TARGET_CHANNELS}")
    

async def on_sub(sub: ChatSub):
    user_data = evalaute_sub(sub)

    if user_data["gifted"]:
        gifted_subs[user_data["username"]] += 1
        # Wait and accumulate subs for batch printing
        await asyncio.sleep(2)  # Adjust delay if necessary
        if gifted_subs[user_data["username"]] > 0:
            subscription_info = f"{gifted_subs[user_data['username']]} gifted {user_data["type"]} Subs"
            print_text_with_image(user_data["username"], get_twitch_profile_image_url(user_data["username"]), subscription_info)
            gifted_subs[user_data["username"]] = 0
    else:
        subscription_info = f"Neuer {user_data["type"]} Sub" if user_data["months"] is None else f"{user_data["type"]} im {str(user_data["months"])}. Monat"
        print_text_with_image(user_data["username"], get_twitch_profile_image_url(user_data["username"]), subscription_info)

def evalaute_sub(sub: ChatSub):
    message = re.sub(r"\\s", " ", sub.system_message)

    patterns = {
        "username": r"^(\w+)",
        "type": r"(Tier \d|Prime)",
        "gifted": r"gifted",
        "months": r"for (\d+) months"
    }

    user_data = {
        "username": None,
        "type": None,
        "gifted": False,
        "months": None,
        "avatar_url": None
    }

    user_data["username"] = re.search(patterns["username"], message).group(1) if re.search(patterns["username"], message) else None
    user_data["type"] = re.search(patterns["type"], message).group(1) if re.search(patterns["type"], message) else None
    user_data["gifted"] = bool(re.search(patterns["gifted"], message))
    user_data["months"] = int(re.search(patterns["months"], message).group(1)) if re.search(patterns["months"], message) else None
    user_data["avatar_url"] = get_twitch_profile_image_url(user_data["username"], os.getenv("CLIENT_ID"), os.getenv("ACCESS_TOKEN"))

    return user_data

async def on_message(message: EventData):
    # check if message contains Cheer
    cheercheck = r"(\s|^)((Cheer\d+)|(cheerwhal\d+)|(Corgo\d+)|(uni\d+)|(ShowLove\d+)|(Party\d+)|(SeemsGood\d+)|(Pride\d+)|(Kappa\d+)|(FrankerZ\d+)|(HeyGuys\d+)|(DansGame\d+)|(EleGiggle\d+)|(TriHard\d+)|(Kreygasm\d+)|(4Head\d+)|(SwiftRage\d+)|(NotLikeThis\d+)|(FailFish\d+)|(VoHiYo\d+)|(PJSalt\d+)|(MrDestructoid\d+)|(bday\d+)|(RIPCheer\d+)|(Shamrock\d+))(\s|$)"
    if re.search(cheercheck, message.text):
        print_text(f"{message.user.name}: {message.text}")
        
    # check if message contains !print
    if os.getenv("PRINT_CHAT") == "true":
        print_text(message.user.name + ": " + message.text)

async def chatrun():
    twitch = await Twitch(os.getenv("CLIENT_ID"), authenticate_app=False)
    await twitch.set_user_authentication(os.getenv("ACCESS_TOKEN"), USER_SCOPE, os.getenv("REFRESH_TOKEN"))

    chat = await Chat(twitch)

    chat.register_event(ChatEvent.READY, on_ready)
    chat.register_event(ChatEvent.SUB, on_sub)
    chat.register_event(ChatEvent.MESSAGE, on_message)

    chat.start()

    try:
        isRunning = True
        while isRunning:
            command = input('press ENTER to stop\n')
            if command == "exit" or command == "":
                isRunning = False
            elif command == "reprint":
                print("Reprinting last print call...")
                z.output(lastPrintCall)
            
    finally:
        chat.stop()
        await twitch.close()
        print_text(f"{datetime.datetime.now().strftime("%H:%M:%S")} Bot und Drucker wurden gestoppt. Goodbye :)")

def get_twitch_profile_image_url(username, client_id = os.getenv("CLIENT_ID"), access_token = os.getenv("ACCESS_TOKEN")):
    local_path = f"./avatars/{username}.png"
    if os.path.exists(local_path):
        return local_path

    url = f"https://api.twitch.tv/helix/users?login={username}"

    headers = {
        "Client-ID": client_id,
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        if "data" in data and len(data["data"]) > 0:
            profile_image_url = data["data"][0]["profile_image_url"]
            response = requests.get(profile_image_url)
            os.makedirs("./avatars", exist_ok=True)
            with open(local_path, "wb") as img_file:
                img_file.write(response.content)
            return local_path
    return None

def convert_image_to_zpl(image_path):
    with open(image_path, "rb") as img_file:
        zpl_data = ZebrafyImage(
            img_file.read(),
            compression_type="C",
            complete_zpl=False,
            invert=True,
            width=400,
            height=400,
            pos_x=120,
            pos_y=150,
        ).to_zpl()
    return zpl_data

def print_text_with_image(text, image_path, subtext):
    try:
        image_zpl = convert_image_to_zpl(image_path)

        zpl_code = f"""
        ^FX SETUP
        ^XA
        ^PW639
        ^LL639
        ^PON
        ^PR5,5
        ^PMN
        ^MNN
        ^LS0
        ^MTD
        
        ^FX CUTTING LINE
        ^FO0,0^GB639,1,3^FS

        ^FX TEXT
        ^FO50,50^A0N,50,50^FD{text}^FS

        ^FX IMAGE
        {image_zpl}^FS

        ^FX SUBSCRIPTION INFO
        ^FO50,560^A0N,30,30^FD{subtext}^FS
        
        ^XZ
        """
        
        global lastPrintCall
        lastPrintCall = zpl_code

        z.output(zpl_code)
    except Exception as e:
        print(f"Error: {e}")

def print_text(text):
    try:
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            if len(current_line) + len(word) + 1 <= 45:
                current_line += (" " if current_line else "") + word
            else:
                lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        field_elements = []
        font_height = 30
        y_offset = int(font_height/2)
        line_spacing = 0

        for line in lines:
            field_elements.append(f"^FO25,{y_offset}^A0N,{font_height},{font_height}^FD{line}^FS")
            y_offset += font_height + line_spacing

        # Adjust label length (^LL) based on total height of content
        label_length = y_offset + 50

        zpl_code = f"""
        ^XA
        ^PW639
        ^LL{label_length}
        ^PON
        ^PR5,5
        ^PMN
        ^MNN
        ^LS0
        {''.join(field_elements)}
        ^FX CUTTING LINE
        ^FO0,0^GB639,1,3^FS
        ^XZ
        """
        
        global lastPrintCall
        lastPrintCall = zpl_code

        z.output(zpl_code)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(chatrun())
