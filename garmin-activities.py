from datetime import datetime, timezone
from garminconnect import Garmin
from notion_client import Client
from dotenv import load_dotenv
import pytz
import os

# Your local time zone, replace with the appropriate one if needed
local_tz = pytz.timezone('Europe/Paris')

ACTIVITY_MAPPING = {
    "marche à pied": ("Walking", "Marche à pied"),
    "course à pied": ("Running", "Running"),
    "musculation": ("Strength", "Strength Training"),
    "barre": ("Strength", "Barre"),
    "cardio interieur": ("Cardio", "Indoor Cardio"),
    "vélo d'interieur": ("Cycling", "Indoor Cycling"),
    "rameur": ("Rowing", "Indoor Rowing"),
    "treadmill running": ("Running", "Treadmill Running"),
    "rowing v2": ("Rowing", "Rowing"),
    "yoga": ("Yoga/Pilates", "Yoga"),
    "pilates": ("Yoga/Pilates", "Pilates"),
    "meditation": ("Meditation", "Meditation"),
    "étirement": ("Stretching", "Stretching"),
    "natation en piscine": ("Swimming", "Swimming"),
    "natation en eau libre": ("Swimming", "Open Water Swimming"),
    "me suivre": ("Other", "Me Suivre")
}

ACTIVITY_ICONS = {
    "Barre": "https://img.icons8.com/?size=100&id=66924&format=png&color=000000",
    "Breathwork": "https://img.icons8.com/?size=100&id=9798&format=png&color=000000",
    "Cardio": "https://img.icons8.com/?size=100&id=71221&format=png&color=000000",
    "Cycling": "https://img.icons8.com/?size=100&id=47443&format=png&color=000000",
    "Hiking": "https://img.icons8.com/?size=100&id=9844&format=png&color=000000",
    "Marche à pied": "https://img.icons8.com/?size=100&id=9844&format=png&color=000000",
    "Me Suivre": "https://img.icons8.com/?size=100&id=9844&format=png&color=000000",
    "Indoor Cardio": "https://img.icons8.com/?size=100&id=62779&format=png&color=000000",
    "Indoor Cycling": "https://img.icons8.com/?size=100&id=47443&format=png&color=000000",
    "Indoor Rowing": "https://img.icons8.com/?size=100&id=71098&format=png&color=000000",
    "Pilates": "https://img.icons8.com/?size=100&id=9774&format=png&color=000000",
    "Meditation": "https://img.icons8.com/?size=100&id=9798&format=png&color=000000",
    "Rowing": "https://img.icons8.com/?size=100&id=71491&format=png&color=000000",
    "Running": "https://img.icons8.com/?size=100&id=k1l1XFkME39t&format=png&color=000000",
    "Strength Training": "https://img.icons8.com/?size=100&id=107640&format=png&color=000000",
    "Stretching": "https://img.icons8.com/?size=100&id=djfOcRn1m_kh&format=png&color=000000",
    "Swimming": "https://img.icons8.com/?size=100&id=9777&format=png&color=000000",
    "Treadmill Running": "https://img.icons8.com/?size=100&id=9794&format=png&color=000000",
    "Walking": "https://img.icons8.com/?size=100&id=9807&format=png&color=000000",
    "Yoga": "https://img.icons8.com/?size=100&id=9783&format=png&color=000000",
}

def get_all_activities(garmin, limit=1000):
    return garmin.get_activities(0, limit)

def format_activity_type(activity_type, activity_name=""):
    formatted_type = activity_type.replace('_', ' ').lower() if activity_type else "unknown"
    if formatted_type in ACTIVITY_MAPPING:
        return ACTIVITY_MAPPING[formatted_type]
    if activity_name:
        name_lower = activity_name.lower()
        for key in ACTIVITY_MAPPING.keys():
            if key in name_lower:
                return ACTIVITY_MAPPING[key]
    return formatted_type.title(), formatted_type.title()

def format_entertainment(activity_name):
    return activity_name.replace('ENTERTAINMENT', 'Netflix')

def format_training_message(message):
    messages = {
        'NO_': 'No Benefit',
        'MINOR_': 'Some Benefit',
        'RECOVERY_': 'Recovery',
        'MAINTAINING_': 'Maintaining',
        'IMPROVING_': 'Impacting',
        'IMPACTING_': 'Impacting',
        'HIGHLY_': 'Highly Impacting',
        'OVERREACHING_': 'Overreaching'
    }
    for key, value in messages.items():
        if message.startswith(key):
            return value
    return message

def format_training_effect(trainingEffect_label):
    return trainingEffect_label.replace('_', ' ').title()

def format_pace(average_speed):
    if average_speed > 0:
        pace_min_km = 1000 / (average_speed * 60)
        minutes = int(pace_min_km)
        seconds = int((pace_min_km - minutes) * 60)
        return f"{minutes}:{seconds:02d} min/km"
    else:
        return ""

def activity_exists(client, database_id, activity):
    """Vérifie si une activité existe déjà dans Notion (clé = Date + Durée + Distance)."""
    query = client.databases.query(
        database_id=database_id,
        filter={
            "and": [
                {"property": "Date", "date": {"equals": activity['startTimeGMT'].split('T')[0]}},
                {"property": "Duration (min)", "number": {"equals": round(activity.get('duration', 0) / 60, 2)}},
                {"property": "Distance (km)", "number": {"equals": round(activity.get('distance', 0) / 1000, 2)}},
            ]
        }
    )
    results = query['results']
    return results[0] if results else None

def remove_duplicates(client, database_id):
    """Archive les doublons déjà présents dans Notion (clé = Date + Durée + Distance)."""
    query = client.databases.query(database_id=database_id)
    seen = {}
    duplicates = []

    for page in query["results"]:
        props = page["properties"]
        date = props["Date"]["date"]["start"]
        duration = props["Duration (min)"]["number"]
        distance = props["Distance (km)"]["number"]
        key = (date, duration, distance)

        if key in seen:
            duplicates.append(page["id"])
        else:
            seen[key] = page["id"]

    for dup_id in duplicates:
        client.pages.update(dup_id, archived=True)  # Archive plutôt que suppression définitive
        print(f"Archived duplicate: {dup_id}")

# (tes fonctions create_activity, update_activity, split_activity_name, etc. inchangées)

def main():
    load_dotenv()
    garmin_email = os.getenv("GARMIN_EMAIL")
    garmin_password = os.getenv("GARMIN_PASSWORD")
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DB_ID")

    garmin = Garmin(garmin_email, garmin_password)
    garmin.login()
    client = Client(auth=notion_token)

    # Nettoyer les doublons existants
    remove_duplicates(client, database_id)

    # Import des nouvelles activités
    activities = get_all_activities(garmin)
    for activity in activities:
        if not activity_exists(client, database_id, activity):
            create_activity(client, database_id, activity)
            print(f"Created: {activity['activityName']}")
        else:
            print(f"Skipped duplicate: {activity['activityName']}")

if __name__ == '__main__':
    main()

