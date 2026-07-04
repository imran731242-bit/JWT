def format_player_info(data):
    basic = data.get("basicInfo", {})

    return {
        "name": basic.get("nickname", "Not Found"),
        "uid": basic.get("accountId", "Not Found"),
        "level": basic.get("level", "Not Found"),
        "region": basic.get("region", "Not Found"),
        "likes": basic.get("liked", "Not Found"),
        "rank": basic.get("rank", "Not Found"),
        "cs_rank": basic.get("csRank", "Not Found"),
    }


def format_ban_info(data):
    return {
        "name": data.get("name", "Not Found"),
        "region": data.get("region", "Not Found"),
        "status": data.get("ban_status", "Not Found"),
        "since": data.get("banned_since", "Not Found")
    }