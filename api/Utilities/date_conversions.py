from datetime import datetime
import random


def format_availability(availability):
    """
    - Adds day names alongside ISO dates
    - Converts 24-hour time to 12-hour AM/PM format
    """
    formatted_availability = []

    for entry in availability:
        # Convert date to day of the week
        date_obj = datetime.strptime(entry["date"], "%Y-%m-%d")
        day_name = date_obj.strftime("%A")

        # Convert times to 12-hour AM/PM format
        formatted_times = [
            datetime.strptime(time, "%H:%M")
            .strftime("%I:%M %p")
            .lstrip("0")  # Remove leading zero
            for time in entry["slots"]
        ]

        formatted_availability.append(
            {
                "date": entry["date"],
                "day": day_name,
                "slots": formatted_times,
            }
        )
    return formatted_availability


def get_appointment_slots(formatted_availability):
    """
    - Identify the soonest available slot
    - Identify remaining availability
    - Pick a random available slot
    """
    if not formatted_availability:
        raise ValueError("No available appointment slots.")

    # Find the soonest available slot
    first_entry = formatted_availability[0]
    first_date = first_entry["date"]
    first_day = first_entry["day"]
    first_time = first_entry["slots"][0] if first_entry["slots"] else None

    if first_time is None:
        for entry in formatted_availability[1:]:  # Check other days
            if entry["slots"]:
                first_date = entry["date"]
                first_day = entry["day"]
                first_time = entry["slots"][0]
                break

    if first_time is None:
        return "No available appointments.", [], "No available appointments."

    soonest_available = f"{first_day} at {first_time}"

    # Remove the soonest slot from rest_available
    rest_available = [
        {
            "date": entry["date"],
            "day": entry["day"],
            "slots": (
                entry["slots"][1:] if entry["date"] == first_date else entry["slots"]
            ),
        }
        for entry in formatted_availability
        if entry["slots"][1:] or entry["date"] != first_date  # Keep only non-empty days
    ]

    # If no remaining slots, fallback to soonest_available
    if not rest_available:
        return soonest_available, rest_available, soonest_available

    # Choose a random slot from remaining availability
    random_entry = random.choice(rest_available)
    random_day = random_entry["day"]
    random_date = random_entry["date"]
    random_time = random.choice(random_entry["slots"])
    random_slot = [random_day, random_time]

    return soonest_available, rest_available, random_slot


# availability_data = {
#     "availability": [
#         {"date": "2025-02-24", "slots": ["11:00", "12:00"]},
#         {"date": "2025-02-25", "slots": ["09:00", "14:00"]},
#     ]
# }

# formatted_availability = format_availability(availability_data["availability"])
# soonest_available, rest_available, random_slot = get_appointment_slots(
#     formatted_availability
# )
# print("Formatted Availability:", formatted_availability)
# print("Soonest Available:", soonest_available)
# print("Remaining Availability:", rest_available)
# print("Random Slot:", random_slot)
