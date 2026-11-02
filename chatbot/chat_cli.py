"""
Chat with BeLiving Coach in the terminal, like a real user.
Run:  python chat_cli.py
Type 'quit' to exit, 'reset' to start a fresh conversation.
"""

import time

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from bot import stream_reply

console = Console()
GREEN = "#4ade80"


def coach_panel(body, subtitle: str = "") -> Panel:
    return Panel(body, title=f"[bold {GREEN}]🌿 BeLiving Coach[/]", title_align="left",
                 subtitle=subtitle, subtitle_align="right",
                 border_style=GREEN, padding=(1, 2))


def ask(question: str) -> str:
    return Prompt.ask(f"  [dim]{question}[/]", default="", show_default=False).strip()


console.clear()
console.print(coach_panel(
    "Hey! I'm your BeLiving coach 👋\n"
    "Quick setup so I can personalise things. [dim](Press Enter to skip any)[/]"
))

profile = {
    "name": ask("Your name?"),
    "age": ask("Age?"),
    "gender": ask("Gender?"),
    "height_cm": ask("Height (cm)?"),
    "weight_kg": ask("Weight (kg)?"),
    "goal": ask("Main goal? (fat loss / muscle gain / energy / better sleep / less stress)"),
    "diet": ask("Diet? (veg / egg / non-veg / jain / vegan)"),
    "activity_level": ask("Activity? (desk job / somewhat active / very active)"),
    "health_conditions": ask("Any health conditions or injuries?"),
    "allergies": ask("Any food allergies?"),
}
profile = {k: v for k, v in profile.items() if v}

name = profile.get("name", "there")
console.print()
console.print(coach_panel(
    Markdown(f"Nice, **{name}**! What do you want help with today?\n\n"
             "🍽️ Food · 🏋️ Workouts · 😴 Sleep & stress · 🧬 Longevity")
))
console.print("[dim]  Type 'reset' for a fresh chat, 'quit' to exit.[/]\n")

history = []
while True:
    msg = Prompt.ask(f"[bold cyan]You[/]").strip()
    if msg.lower() in ("quit", "exit"):
        console.print(coach_panel("Take care! See you soon 🌱"))
        break
    if msg.lower() == "reset":
        history = []
        console.print("[dim]  (conversation cleared)[/]\n")
        continue
    if not msg:
        continue

    start = time.time()
    first_word_at = None
    reply = ""
    try:
        # Show the answer live as it's written, then print the clean final version.
        with Live(coach_panel(Text("typing…", style="dim italic")), console=console,
                  refresh_per_second=10, transient=True, vertical_overflow="crop") as live:
            for piece in stream_reply(msg, profile=profile, history=history):
                if first_word_at is None:
                    first_word_at = time.time() - start
                reply += piece
                live.update(coach_panel(Markdown(reply)))
    except Exception as e:
        if reply:
            console.print(coach_panel(Markdown(reply)))
        console.print(f"[yellow]  Sorry, the AI servers are very busy right now. "
                      f"Please ask again in a minute.[/]\n[dim]  ({str(e)[:150]})[/]\n")
        continue

    total = time.time() - start
    console.print(coach_panel(Markdown(reply),
                              subtitle=f"[dim]first words {first_word_at or 0:.1f}s · "
                                       f"full answer {total:.1f}s[/]"))
    console.print()
    history += [{"role": "user", "content": msg}, {"role": "assistant", "content": reply.strip()}]
