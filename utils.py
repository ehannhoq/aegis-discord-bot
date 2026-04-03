def format_duration(days):
    hours = days * 24
    if hours < 24:
        return f'{hours:g} {"hour" if hours == 1 else "hours"}'
    return f'{days:g} {"day" if days == 1 else "days"}'