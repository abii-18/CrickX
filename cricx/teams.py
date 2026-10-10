"""2023 World Cup final XI names; synthetic outcomes, not historical replay.

Source: https://www.icc-cricket.com/news/awesome-australia-beat-india-to-win-the-icc-mens-cricket-world-cup
"""
PROFILE = "cwc2023-final"
INDIA = ["Rohit Sharma", "Shubman Gill", "Virat Kohli", "Shreyas Iyer", "KL Rahul",
         "Suryakumar Yadav", "Ravindra Jadeja", "Mohammed Shami", "Jasprit Bumrah",
         "Kuldeep Yadav", "Mohammed Siraj"]
AUSTRALIA = ["Travis Head", "David Warner", "Mitchell Marsh", "Steve Smith",
             "Marnus Labuschagne", "Glenn Maxwell", "Josh Inglis", "Mitchell Starc",
             "Pat Cummins", "Adam Zampa", "Josh Hazlewood"]
INDIA_BOWLERS = ["Jasprit Bumrah", "Mohammed Shami", "Mohammed Siraj", "Kuldeep Yadav", "Ravindra Jadeja"]
AUSTRALIA_BOWLERS = ["Mitchell Starc", "Josh Hazlewood", "Pat Cummins", "Adam Zampa", "Glenn Maxwell"]

# Selected XIs drawn from confirmed 2023 squads; these are synthetic fixtures.
# https://www.icc-cricket.com/media-releases/squads-confirmed-for-icc-mens-cricket-world-cup-2023
TEAMS = {
    "India": ("IND", INDIA, INDIA_BOWLERS),
    "Australia": ("AUS", AUSTRALIA, AUSTRALIA_BOWLERS),
    "New Zealand": ("NZ", ["Devon Conway", "Will Young", "Kane Williamson", "Rachin Ravindra", "Daryl Mitchell", "Tom Latham", "Glenn Phillips", "Mitchell Santner", "Matt Henry", "Lockie Ferguson", "Trent Boult"], ["Trent Boult", "Matt Henry", "Lockie Ferguson", "Mitchell Santner", "Glenn Phillips"]),
    "South Africa": ("SA", ["Quinton de Kock", "Temba Bavuma", "Rassie van der Dussen", "Aiden Markram", "Heinrich Klaasen", "David Miller", "Marco Jansen", "Keshav Maharaj", "Kagiso Rabada", "Lungi Ngidi", "Gerald Coetzee"], ["Kagiso Rabada", "Lungi Ngidi", "Gerald Coetzee", "Marco Jansen", "Keshav Maharaj"]),
    "England": ("ENG", ["Jonny Bairstow", "Dawid Malan", "Joe Root", "Ben Stokes", "Harry Brook", "Jos Buttler", "Moeen Ali", "Chris Woakes", "Adil Rashid", "Mark Wood", "David Willey"], ["Chris Woakes", "David Willey", "Mark Wood", "Adil Rashid", "Moeen Ali"]),
    "Pakistan": ("PAK", ["Abdullah Shafique", "Fakhar Zaman", "Babar Azam", "Mohammad Rizwan", "Saud Shakeel", "Iftikhar Ahmed", "Shadab Khan", "Mohammad Nawaz", "Shaheen Afridi", "Hasan Ali", "Haris Rauf"], ["Shaheen Afridi", "Hasan Ali", "Haris Rauf", "Shadab Khan", "Mohammad Nawaz"]),
}
MATCH_PROFILES = {
    PROFILE: ("India", "Australia"),
    "cwc2023-ind-nz": ("India", "New Zealand"),
    "cwc2023-aus-sa": ("Australia", "South Africa"),
    "cwc2023-eng-pak": ("England", "Pakistan"),
    "cwc2023-nz-aus": ("New Zealand", "Australia"),
    "cwc2023-ind-sa": ("India", "South Africa"),
}
