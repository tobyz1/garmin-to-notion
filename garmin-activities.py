from datetime import datetime, timezone
from garminconnect import Garmin
from notion_client import Client
from dotenv import load_dotenv
import pytz
import os

# Your local time zone, replace with the appropriate one if needed
local_tz = pytz.timezone('America/Toronto')

ACTIVITY_MAPPING = {
    "Musculation": ("Strength", "Barre"),
    "Cardio Interieur": ("Cardio", "Indoor Cardio"),
    "Vélo d'interieur": ("Cycling", "Indoor Cycling"),
    "Rameur": ("Rowing", "Indoor Rowing"),
    "Marche": ("Walking", "Speed Walking"),
    "Musculation": ("Strength", "Strength Training"),
    "treadmill running": ("Running", "Treadmill Running"),
    "rowing v2": ("Rowing", "Rowing"),
    "yoga": ("Yoga/Pilates", "Yoga"),
    "pilates": ("Yoga/Pilates", "Pilates"),
    "meditation": ("Meditation", "Meditation"),
    "Etirement": ("Stretching", "Stretching"),
}

ACTIVITY_ICONS = {
    "Barre": "https://img.icons8.com/?size=100&id=66924&format=png&color=000000",
    "Breathwork": "https://img.icons8.com/?size=100&id=9798&format=png&color=000000",
    "Cardio": "https://img.icons8.com/?size=100&id=71221&format=png&color=000000",
    "Cycling": "https://img.icons8.com/?size=100&id=47443&format=png&color=000000",
    "Hiking": "https://img.icons8.com/?size=100&id=9844&format=png&color=000000",
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
    # Add more mappings as needed
}

def get_all_activities(garmin, limit=1000):
    return garmin.get_activities(0, limit)

def format_activity_type(activity_type, activity_name=""):
    """
    Retourne (main_type, subtype) en normalisant les activités Garmin.
    """
    formatted_type = activity_type.replace('_', ' ').lower() if activity_type else "unknown"

    # Cherche dans le mapping global
    if formatted_type in ACTIVITY_MAPPING:
        return ACTIVITY_MAPPING[formatted_type]

    # Cas particuliers basés sur le nom d'activité
    if activity_name:
        name_lower = activity_name.lower()
        for key in ACTIVITY_MAPPING.keys():
            if key in name_lower:
                return ACTIVITY_MAPPING[key]

    # Fallback si aucune correspondance
    return formatted_type.title(), formatted_type.title()


    # Special replacement for Rowing V2
    if formatted_type == "Rowing V2":
        activity_type = "Rowing"

    # Special case for Yoga and Pilates
    elif formatted_type in ["Yoga", "Pilates"]:
        activity_type = "Yoga/Pilates"
        activity_subtype = formatted_type

    # If the formatted type is in our mapping, update both main type and subtype
    if formatted_type in activity_mapping:
        activity_type = activity_mapping[formatted_type]
        activity_subtype = formatted_type

    # Special cases for activity names
    if activity_name and "meditation" in activity_name.lower():
        return "Meditation", "Meditation"
    if activity_name and "barre" in activity_name.lower():
        return "Strength", "Barre"
    if activity_name and "stretch" in activity_name.lower():
        return "Stretching", "Stretching"
    
    return activity_type, activity_subtype

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
        pace_min_km = 1000 / (average_speed * 60)  # Convert to min/km
        minutes = int(pace_min_km)
        seconds = int((pace_min_km - minutes) * 60)
        return f"{minutes}:{seconds:02d} min/km"
    else:
        return ""
    
def activity_exists(client, database_id, activity_date, activity_type, activity_name):

    # Check if an activity already exists in the Notion database and return it if found.

    # Handle the activity_type which is now a tuple
    if isinstance(activity_type, tuple):
        main_type, _ = activity_type
    else:
        main_type = activity_type[0] if isinstance(activity_type, (list, tuple)) else activity_type
    
    # Determine the correct activity type for the lookup
    lookup_type = "Stretching" if "stretch" in activity_name.lower() else main_type
    
    query = client.databases.query(
        database_id=database_id,
        filter={
            "and": [
                {"property": "Date", "date": {"equals": activity_date.split('T')[0]}},
                {"property": "Activity Type", "select": {"equals": lookup_type}},
                {"property": "Activity Name", "title": {"equals": activity_name}}
            ]
        }
    )
    results = query['results']
    return results[0] if results else None


def activity_needs_update(existing_activity, new_activity):
    existing_props = existing_activity['properties']
    
    activity_name = new_activity.get('activityName', '').lower()
    activity_type, activity_subtype = format_activity_type(
        new_activity.get('activityType', {}).get('typeKey', 'Unknown'),
        activity_name
    )
    
    # Check if 'Subactivity Type' property exists
    has_subactivity = (
        'Subactivity Type' in existing_props and 
        existing_props['Subactivity Type'] is not None and
        existing_props['Subactivity Type'].get('select') is not None
    )
    
    return (
        existing_props['Distance (km)']['number'] != round(new_activity.get('distance', 0) / 1000, 2) or
        existing_props['Duration (min)']['number'] != round(new_activity.get('duration', 0) / 60, 2) or
        existing_props['Calories']['number'] != round(new_activity.get('calories', 0)) or
        existing_props['Avg Pace']['rich_text'][0]['text']['content'] != format_pace(new_activity.get('averageSpeed', 0)) or
        existing_props['Avg Power']['number'] != round(new_activity.get('avgPower', 0), 1) or
        existing_props['Max Power']['number'] != round(new_activity.get('maxPower', 0), 1) or
        existing_props['Training Effect']['select']['name'] != format_training_effect(new_activity.get('trainingEffectLabel', 'Unknown')) or
        existing_props['Aerobic']['number'] != round(new_activity.get('aerobicTrainingEffect', 0), 1) or
        existing_props['Aerobic Effect']['select']['name'] != format_training_message(new_activity.get('aerobicTrainingEffectMessage', 'Unknown')) or
        existing_props['Anaerobic']['number'] != round(new_activity.get('anaerobicTrainingEffect', 0), 1) or
        existing_props['Anaerobic Effect']['select']['name'] != format_training_message(new_activity.get('anaerobicTrainingEffectMessage', 'Unknown')) or
        existing_props['PR']['checkbox'] != new_activity.get('pr', False) or
        existing_props['Fav']['checkbox'] != new_activity.get('favorite', False) or
        existing_props['Activity Type']['select']['name'] != activity_type or
        (has_subactivity and existing_props['Subactivity Type']['select']['name'] != activity_subtype) or
        (not has_subactivity)  # If the property doesn't exist, we need an update
    )

def split_activity_name(activity_name):
    """
    Sépare le lieu et l'activité Garmin.
    Le lieu peut avoir plusieurs mots. L'activité est recherchée parmi les clés connues à la fin de la chaîne.
    """
    name_lower = activity_name.lower().strip()

    # Trier les clés par longueur décroissante pour matcher la plus longue en premier
    sorted_keys = sorted(ACTIVITY_MAPPING.keys(), key=lambda x: -len(x))

    for act_key in sorted_keys:
        if name_lower.endswith(act_key):
            activity = ACTIVITY_MAPPING[act_key][1]  # Nom lisible pour Notion
            location = activity_name[:len(activity_name) - len(act_key)].strip()
            return activity, location

    # Fallback : dernier mot = activité
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
        properties["Location"] = {"rich_text": []}  # clear location if none

    update = {
        "page_id": existing_activity['id'],
        "properties": properties,
    }

    if icon_url:
        update["icon"] = {"type": "external", "external": {"url": icon_url}}

    client.pages.update(**update)

def main():
    load_dotenv()

    # Initialize Garmin and Notion clients using environment variables
    garmin_email = os.getenv("GARMIN_EMAIL")
    garmin_password = os.getenv("GARMIN_PASSWORD")
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DB_ID")

    # Initialize Garmin client and login
    garmin = Garmin(garmin_email, garmin_password)
    garmin.login()
    client = Client(auth=notion_token)
    
    # Get all activities
    activities = get_all_activities(garmin)

    # Process all activities
    for activity in activities:
        activity_date = activity.get('startTimeGMT')
        activity_name = format_entertainment(activity.get('activityName', 'Unnamed Activity'))
        activity_type, activity_subtype = format_activity_type(
            activity.get('activityType', {}).get('typeKey', 'Unknown'),
            activity_name
        )
        
        # Check if activity already exists in Notion
        existing_activity = activity_exists(client, database_id, activity_date, activity_type, activity_name)
        
        if existing_activity:
            if activity_needs_update(existing_activity, activity):
                update_activity(client, existing_activity, activity)
                # print(f"Updated: {activity_type} - {activity_name}")
        else:
            create_activity(client, database_id, activity)
            # print(f"Created: {activity_type} - {activity_name}")

if __name__ == '__main__':
    main()
