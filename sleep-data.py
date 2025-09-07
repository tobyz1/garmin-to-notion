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

    # Horaires de sommeil
    start_ts = daily_sleep.get('sleepStartTimestampGMT')
    end_ts = daily_sleep.get('sleepEndTimestampGMT')

    start_local = datetime.fromtimestamp(start_ts / 1000, local_tz) if start_ts else None
    end_local = datetime.fromtimestamp(end_ts / 1000, local_tz) if end_ts else None

    # Condition Sleep Goal
    sleep_goal = False
    if start_local and end_local:
        if start_local.time() < datetime.strptime("23:00", "%H:%M").time() \
           and end_local.time() < datetime.strptime("08:30", "%H:%M").time() \
           and (total_sleep / 3600) > 7.5:
            sleep_goal = True

    properties = {
        "Date": {"title": [{"text": {"content": format_date_for_name(sleep_date)}}]},
        "Times": {"rich_text": [{"text": {"content": f"{format_time_readable(start_ts)} → {format_time_readable(end_ts)}"}}]},
        "Long Date": {"date": {"start": sleep_date}},
        "Full Date/Time": {"date": {"start": format_time(start_ts), "end": format_time(end_ts)}},
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
        "Resting HR": {"number": sleep_data.get('restingHeartRate') or 0},
        "Sleep Goal": {"checkbox": sleep_goal}  # ✅ Ajout de la checkbox
    }
    
    try:
        client.pages.create(parent={"database_id": database_id}, properties=properties, icon={"emoji": "😴"})
        print(f"Created sleep entry for: {sleep_date} (Sleep Goal = {sleep_goal})")
    except Exception as e:
        print(f"Error creating sleep entry for {sleep_date}: {e}")
