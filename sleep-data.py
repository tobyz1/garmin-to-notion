from datetime import datetime, timedelta

def _normalize_to_iso(date_str):
    """
    Retourne 'YYYY-MM-DD' à partir de formats possibles :
    - 'YYYY-MM-DD' (déjà OK)
    - 'YYYY-MM-DDTHH:MM:SS...'
    - 'DD.MM.YYYY' ou 'DD/MM/YYYY'
    - autres -> tentative via fromisoformat sinon renvoie tel quel
    """
    if not date_str:
        return None
    try:
        # cas ISO avec time
        if 'T' in date_str:
            return date_str.split('T')[0]
        # cas 'DD.MM.YYYY'
        if '.' in date_str:
            d = datetime.strptime(date_str, '%d.%m.%Y').date()
            return d.isoformat()
        # cas 'DD/MM/YYYY'
        if '/' in date_str:
            d = datetime.strptime(date_str, '%d/%m/%Y').date()
            return d.isoformat()
        # cas 'YYYY-MM-DD'
        datetime.strptime(date_str, '%Y-%m-%d')
        return date_str
    except Exception:
        try:
            d = datetime.fromisoformat(date_str)
            return d.date().isoformat()
        except Exception:
            # fallback: renvoyer brut (comparaisons échoueront mais on aura essayé)
            return date_str

def create_sleep_data(client, database_id, sleep_data):
    daily_sleep = sleep_data.get('dailySleepDTO', {})
    if not daily_sleep:
        return

    raw_sleep_date = daily_sleep.get('calendarDate', None)
    if not raw_sleep_date:
        print("No calendarDate found, skipping.")
        return

    # Normalise la date d'entrée en YYYY-MM-DD
    sleep_date = _normalize_to_iso(raw_sleep_date)
    if not sleep_date:
        print(f"Impossible de normaliser la date: {raw_sleep_date}")
        return

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

    # --- calculer la semaine précédente en tenant compte du fuseau local si présent ---
    try:
        now_local = datetime.now(local_tz) if 'local_tz' in globals() and local_tz else datetime.now()
    except Exception:
        now_local = datetime.now()
    today = now_local.date()
    one_week_ago = today - timedelta(days=7)

    # --- interroger Notion avec pagination pour récupérer toutes les dates de la semaine précédente ---
    existing_dates = set()
    start_cursor = None
    while True:
        q = {
            "database_id": database_id,
            "filter": {
                "and": [
                    {"property": "Long Date", "date": {"on_or_after": str(one_week_ago)}},
                    {"property": "Long Date", "date": {"on_or_before": str(today)}}
                ]
            },
            "page_size": 100
        }
        if start_cursor:
            q["start_cursor"] = start_cursor

        res = client.databases.query(**q)
        for result in res.get("results", []):
            props = result.get("properties", {})
            long_date = props.get("Long Date", {}).get("date", {}).get("start")
            if long_date:
                # normalise la date renvoyée par Notion (ex : '2025-09-07T00:00:00.000+00:00' -> '2025-09-07')
                existing_dates.add(_normalize_to_iso(long_date))
        # pagination
        if not res.get("has_more"):
            break
        start_cursor = res.get("next_cursor")

    # Debug logs pour comprendre ce qui est présent
    print(f"Window: {one_week_ago} -> {today}")
    print(f"Dates existantes récupérées (dans la fenêtre) : {sorted(existing_dates)}")
    print(f"Date courante normalisée à insérer : {sleep_date}")

    # Si la date existe déjà, on ne recrée pas
    if sleep_date in existing_dates:
        print(f"Sleep entry already exists for {sleep_date}, skipping.")
        return

    properties = {
        "Date": {"title": [{"text": {"content": format_date_for_name(sleep_date)}}]},
        "Times": {"rich_text": [{"text": {"content": f"{format_time_readable(start_ts)} → {format_time_readable(end_ts)}"}}]},
        "Long Date": {"date": {"start": sleep_date}},  # utilise la date normalisée YYYY-MM-DD
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
        "Sleep Goal": {"checkbox": sleep_goal}
    }

    try:
        client.pages.create(parent={"database_id": database_id}, properties=properties, icon={"emoji": "😴"})
        print(f"Created sleep entry for: {sleep_date} (Sleep Goal = {sleep_goal})")
    except Exception as e:
        print(f"Error creating sleep entry for {sleep_date}: {e}")
