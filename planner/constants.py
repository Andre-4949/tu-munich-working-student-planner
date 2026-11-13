"""Names and fixed values shared by the planner modules."""

REQUIRED_CSV_COLUMNS = ("DATUM", "VON", "BIS", "TITEL")
WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")  # index = date.weekday()
SHORT_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# The places of a day: home, TUM and the job.
HOME, TUM, JOB = "H", "T", "J"
PLACES = (HOME, TUM, JOB)

# Travel modes, and where the car is: parked at home, or with the user.
TRANSIT, CAR = "transit", "car"
CAR_HOME, CAR_OUT = "home", "out"

MAX_LEGS = 4   # longest walk between two lectures: TUM-home-job-home-TUM
STEP = 15      # planned visits are chosen in steps of this many minutes
