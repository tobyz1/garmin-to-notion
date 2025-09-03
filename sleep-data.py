from datetime import datetime, timedelta
from garminconnect import Garmin
from notion_client import Client
from dotenv import load_dotenv
import pytz
import os

# Constants
local_tz = pytz.timezone("Europe/paris")

# Load environment variables
load_dotenv()

def get_sleep_data(garmin, date_str):
    try:
        return garmin.get_sleep_data(date_str)
    except Exception as e:
        print(f"Error fetching sleep data for {date_str}: {e}")
        return None

def format_duration(seconds):
    minutes = (seconds or 0) // 60
    return f"{minutes // 60}h {minutes % 60}m"

def format_time(timestamp):
    return (
        datetime.utcfromtimestamp(timestamp / 1000).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if timestamp else None
    )

def format_time_readable(timestamp):
    return (
        datetime.fromtimestamp(timestamp / 1000, local_tz).strftime("%H:%M")
        if timestamp else "Unknown"
    )

def format_date_for_name(sleep_date):
    return datetime.strptime(sleep_date, "%Y-%m-%d").strftime("%d.%m.%Y") if sleep_date else "Unknown"

def sleep_data_exists(client, database_id, sleep_date):
    try:
        query = client.databases.query(
            database_id=database_id,
            filter={"property": "Long Date", "date": {"equals": sleep_date}}
        )
        results = query.get('results', [])
        return results[0] if results else None
    except Exception as e:
        print(f"Error checking existence for {sleep_date}: {e}")
        return None

def create_sleep_data(client, database_id, sleep_data):
    daily_sleep = sleep_data.get('dailySleepDTO', {})
    if not daily_sleep:
        return
    
    sleep_date = daily_sleep.get('calendarDate', "Unknown Date")

    # Convert None to 0
    light_sleep_sec = daily_sleep.get('lightSleepSeconds') or 0
    deep_sleep_sec = daily_sleep.get('deepSleepSeconds') or 0
    rem_sleep_sec = daily_sleep.get('remSleepSeconds') or 0
    awake_sleep_sec = daily_sleep.get('awakeSleepSeconds') or 0
    total_sleep = light_sleep_sec + deep_sleep_sec + rem_sleep_sec

    if total_sleep == 0:
        print(f"Skipping sleep data for {sleep_date} as total sleep is 0")
        return

    properties = {
        "Date": {"title": [{"text": {"content": format_date_for_name(sleep_date)}}]},
        "Times": {"rich_text": [{"text": {"content": f"{format_time_readable(daily_sleep.get('sleepStartTimestampGMT'))} → {format_time_readable(daily_sleep.get('sleepEndTimestampGMT'))}"}}]},
        "Long Date": {"date": {"start": sleep_date}},
        "Full Date/Time": {"date": {"start": format_time(daily_sleep.get('sleepStartTimestampGMT')), "end": format_time(daily_sleep.get('sleepEndTimestampGMT'))}},
        "Total Sleep (h)": {"number": round(total_sleep / 3600, 1)},
        "Light Sleep (h)": {"number": round(light_sleep_sec / 3600, 1)},
        "Deep Sleep (h)": {"number": round(deep_sleep_sec / 3600, 1)},
        "REM Sleep (h)": {"number": round(rem_sleep_sec / 3600, 1)},
        "Awake Time (h)": {"number": round(awake_sleep_sec / 3600, 1)},
        "Total Sleep": {"rich_text": [{"text": {"content": format_duration(total_sleep)}}]},
        "Light Sleep": {"rich_text": [{"text": {"content": format_duration(light_sleep_sec)}}]},
        "Deep Sleep": {"rich_text": [{"text": {"content": format_duration(deep_sleep_sec)}}]},
        "REM Sleep": {"rich_text": [{"text": {"content": format_duration(rem_sleep_sec)}}]},
        "Awake Time": {"rich_text": [{"text": {"content": format_duration(awake_sleep_sec)}}]},
        "Resting HR": {"number": sleep_data.get('restingHeartRate') or 0}
    }
    
    try:
        client.pages.create(parent={"database_id": database_id}, properties=properties, icon={"emoji": "😴"})
        print(f"Created sleep entry for: {sleep_date}")
    except Exception as e:
        print(f"Error creating sleep entry for {sleep_date}: {e}")

def main():
    load_dotenv()

    garmin_email = os.getenv("GARMIN_EMAIL")
    garmin_password = os.getenv("GARMIN_PASSWORD")
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_SLEEP_DB_ID")

    garmin = Garmin(garmin_email, garmin_password)
    try:
        garmin.login()
        print("Garmin login successful")
    except Exception as e:
        print("Garmin login failed:", e)
        return

    client = Client(auth=notion_token)

    # Ne récupérer que la nuit d'hier
    yesterday = (datetime.today()).date().isoformat()
    data = get_sleep_data(garmin, yesterday)
    if data:
        sleep_date = data.get('dailySleepDTO', {}).get('calendarDate')
        if sleep_date and not sleep_data_exists(client, database_id, sleep_date):
            create_sleep_data(client, database_id, data)
        else:
            print(f"Sleep data already exists for {sleep_date}")
    else:
        print(f"No sleep data for {yesterday}")

if __name__ == '__main__':
    main()
