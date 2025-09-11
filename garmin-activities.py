from datetime import datetime, timezone
from garminconnect import Garmin
from notion_client import Client
from dotenv import load_dotenv
import pytz
import os

# Your local time zone
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

def split_activity_name(activity_name):
    name_lower = activity_name.lower().strip()
    sorted_keys = sorted(ACTIVITY_MAPPING.keys(), key=lambda x: -len(x))
    for act_key in sorted_keys:
        if name_lower.endswith(act_key):
            activity = ACTIVITY_MAPPING[act_key][1]
            location = activity_name[:len(activity_name) - len(act_key)].strip()
            return activity, location
    parts = activity_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    else:
        return parts[-1], " ".join(parts[:-1])

def create_activity(client, database_id, activity):
    activity_date = activity.get('startTimeGMT')
    raw_name = format_entertainment(activity.get('activityName', 'Unnamed Activity'))
    activity_name, location = split_activity_name(raw_name)

    activity_type, activity_subtype = format_activity_type(
        activity.get('activityType', {}).get('typeKey', 'Unknown'),
        activity_name
    )

    icon_url = ACTIVITY_ICONS.get(activity_subtype if activity_subtype != activity_type else activity_type)

    properties = {
        "Date": {"date": {"start": activity_date}},
        "Activity Type": {"select": {"name": activity_type}},
        "Subactivity Type": {"select": {"name": activity_subtype}},
        "Activity Name": {"title": [{"text": {"content": activity_name}}]},
        "Distance (km)": {"number": round(activity.get('distance', 0) / 1000, 2)},
        "Duration (min)": {"number": round(activity.get('duration', 0) / 60, 2)},
        "Calories": {"number": round(activity.get('calories', 0))},
        "Avg Pace": {"rich_text": [{"text": {"content": format_pace(activity.get('averageSpeed', 0))}}]},
        "Avg Power": {"number": round(activity.get('avgPower', 0), 1)},
        "Max Power": {"number": round(activity.get('maxPower', 0), 1)},
        "Training Effect": {"select": {"name": format_training_effect(activity.get('trainingEffectLabel', 'Unknown'))}},
        "Aerobic": {"number": round(activity.get('aerobicTrainingEffect', 0), 1)},
        "Aerobic Effect": {"select": {"name": format_training_message(activity.get('aerobicTrainingEffectMessage', 'Unknown'))}},
        "Anaerobic": {"number": round(activity.get('anaerobicTrainingEffect', 0), 1)},
        "Anaerobic Effect": {"select": {"name": format_training_message(activity.get('anaerobicTrainingEffectMessage', 'Unknown'))}},
        "PR": {"checkbox": activity.get('pr', False)},
        "Fav": {"checkbox": activity.get('favorite', False)}
    }

    if location:
        properties["Location"] = {"rich_text": [{"text": {"content": location}}]}

    page = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }

    if icon_url:
        page["icon"] = {"type": "external", "external": {"url": icon_url}}

    client.pages.create(**page)

def update_activity(client, existing_activity, new_activity):
    raw_name = format_entertainment(new_activity.get('activityName', 'Unnamed Activity'))
    activity_name, location = split_activity_name(raw_name)

    activity_type, activity_subtype = format_activity_type(
        new_activity.get('activityType', {}).get('typeKey', 'Unknown'),
        activity_name
    )

    icon_url = ACTIVITY_ICONS.get(activity_subtype if activity_subtype != activity_type else activity_type)

    properties = {
        "Activity Type": {"select": {"name": activity_type}},
        "Subactivity Type": {"select": {"name": activity_subtype}},
        "Activity Name": {"title": [{"text": {"content": activity_name}}]},
        "Distance (km)": {"number": round(new_activity.get('distance', 0) / 1000, 2)},
        "Duration (min)": {"number": round(new_activity.get('duration', 0) / 60, 2)},
        "Calories": {"number": round(new_activity.get('calories', 0))},
        "Avg Pace": {"rich_text": [{"text": {"content": format_pace(new_activity.get('averageSpeed', 0))}}]},
        "Avg Power": {"number": round(new_activity.get('avgPower', 0), 1)},
        "Max Power": {"number": round(new_activity.get('maxPower', 0), 1)},
        "Training Effect": {"select": {"name": format_training_effect(new_activity.get('trainingEffectLabel', 'Unknown'))}},
        "Aerobic": {"number": round(new_activity.get('aerobicTrainingEffect', 0), 1)},
        "Aerobic Effect": {"select": {"name": format_training_message(new_activity.get('aerobicTrainingEffectMessage', 'Unknown'))}},
        "Anaerobic": {"number": round(new_activity.get('anaerobicTrainingEffect', 0), 1)},
        "Anaerobic Effect": {"select": {"name": format_training_message(new_activity.get('anaerobicTrainingEffectMessage', 'Unknown'))}},
        "PR": {"checkbox": new_activity.get('pr', False)},
        "Fav": {"checkbox": new_activity.get('favorite', False)}
    }

    if location:
        properties["Location"] = {"rich_text": [{"text": {"content": location}}]}
    else:
        properties["Location"] = {"rich_text": []}

    update = {
        "page_id": existing_activity['id'],
        "properties": properties,
    }

    if icon_url:
        update["icon"] = {"type": "external", "external": {"url": icon_url}}

    client.pages.update(**update)

def activity_exists(client, database_id, activity):
    """
    Recherche dans Notion si une activité existe déjà.
    Logique : on récupère toutes les pages pour la même Date, puis on compare
    Duration et Distance avec une petite tolérance. Si duration/distance manquent,
    on fallback sur le nom.
    """
    target_date = activity.get('startTimeGMT', '').split('T')[0]
    target_duration = round(activity.get('duration', 0) / 60, 2)
    target_distance = round(activity.get('distance', 0) / 1000, 2)
    target_name = format_entertainment(activity.get('activityName', '')).strip().lower()

    start_cursor = None
    while True:
        if start_cursor:
            res = client.databases.query(database_id=database_id, filter={
                "property": "Date",
                "date": {"equals": target_date}
            }, start_cursor=start_cursor)
        else:
            res = client.databases.query(database_id=database_id, filter={
                "property": "Date",
                "date": {"equals": target_date}
            })

        for page in res.get('results', []):
            props = page.get('properties', {})
            dur = props.get('Duration (min)', {}).get('number')
            dist = props.get('Distance (km)', {}).get('number')

            # Si on a dur+dist: comparaison avec tolérance (pour arrondis)
            if dur is not None and dist is not None:
                if abs(round(dur, 2) - target_duration) <= 0.02 and abs(round(dist, 2) - target_distance) <= 0.02:
                    return page

            # Sinon fallback sur le nom (si présent)
            title_arr = props.get('Activity Name', {}).get('title') or []
            page_name = (title_arr[0].get('plain_text', '') if title_arr else '').strip().lower()
            if target_name and page_name and target_name == page_name:
                return page

        if not res.get('has_more'):
            break
        start_cursor = res.get('next_cursor')

    return None

def remove_duplicates(client, database_id, archive_only=True):
    """
    Parcourt toute la base (pagination), construit des clés (date, durée, distance, nom)
    et archive toutes les pages qui apparaissent en doublon (garde la première).
    archive_only=True -> archive (safe). False -> on tente la même chose mais Notion ne propose
    pas de suppression définitive via API publique : on archive quand même.
    """
    # Récupérer toutes les pages (pagination)
    pages = []
    start_cursor = None
    while True:
        if start_cursor:
            res = client.databases.query(database_id=database_id, start_cursor=start_cursor, page_size=100)
        else:
            res = client.databases.query(database_id=database_id, page_size=100)
        pages.extend(res.get('results', []))
        if not res.get('has_more'):
            break
        start_cursor = res.get('next_cursor')

    seen = {}
    duplicates = []

    for page in pages:
        props = page.get('properties', {})
        date = props.get('Date', {}).get('date', {}).get('start')
        dur = props.get('Duration (min)', {}).get('number')
        dist = props.get('Distance (km)', {}).get('number')
        title_arr = props.get('Activity Name', {}).get('title') or []
        name = (title_arr[0].get('plain_text', '') if title_arr else '').strip().lower()

        key = (date, None if dur is None else round(dur, 2), None if dist is None else round(dist, 2), name)

        if key in seen:
            duplicates.append(page['id'])
        else:
            seen[key] = page['id']

    # Archive duplicates (Notion API: archived=True)
    for dup_id in duplicates:
        try:
            client.pages.update(page_id=dup_id, archived=True)
            print(f"Archived duplicate: {dup_id}")
        except Exception as e:
            print(f"Failed to archive {dup_id}: {e}")

def main():
    load_dotenv()

    garmin_email = os.getenv("GARMIN_EMAIL")
    garmin_password = os.getenv("GARMIN_PASSWORD")
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DB_ID")

    garmin = Garmin(garmin_email, garmin_password)
    garmin.login()
    client = Client(auth=notion_token)

    # 1) Nettoyer les doublons existants (archive)
    remove_duplicates(client, database_id, archive_only=True)

    # 2) Importer / mettre à jour
    activities = get_all_activities(garmin)
    for activity in activities:
        activity_date = activity.get('startTimeGMT')
        raw_name = format_entertainment(activity.get('activityName', 'Unnamed Activity'))
        activity_type, activity_subtype = format_activity_type(
            activity.get('activityType', {}).get('typeKey', 'Unknown'),
            raw_name
        )

        existing = activity_exists(client, database_id, activity)
        if existing:
            if activity_needs_update(existing, activity):
                update_activity(client, existing, activity)
                print(f"Updated: {raw_name}")
            else:
                print(f"Skipped (exists): {raw_name}")
        else:
            create_activity(client, database_id, activity)
            print(f"Created: {raw_name}")

if __name__ == '__main__':
    main()
