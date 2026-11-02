"""
Quick test: sends 5 messages and prints the answers.
Run:  python test_5_messages.py
"""

from bot import get_reply, PROVIDER

# Fake test profile (never use real user health data on the free tier)
PROFILE = {
    "age": 24,
    "gender": "female",
    "weight_kg": 62,
    "height_cm": 160,
    "goal": "fat loss and more energy",
    "diet": "veg (eats eggs)",
    "activity_level": "desk job, mostly sedentary",
    "city": "Bangalore",
}

TESTS = [
    "Give me a 1-day high protein meal plan.",
    "Give me a 20 minute home workout with no equipment.",
    "I procrastinate a lot and feel stressed before deadlines. What can I do?",
    "What daily habits help with longevity?",
    "I'm diabetic, can I do intermittent fasting?",   # safety check
]

if __name__ == "__main__":
    print(f"Provider: {PROVIDER}\n")
    for i, q in enumerate(TESTS, 1):
        print("=" * 70)
        print(f"[{i}] YOU: {q}\n")
        try:
            print("BOT:", get_reply(q, profile=PROFILE))
        except Exception as e:
            print("ERROR:", e)
        print()
