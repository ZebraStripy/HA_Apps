###########################
# Immersion iBoost
#
# App to boost the immersion if electricity is free :-)
#
# To Do:
#    Use Water temperature to guide on/off. But no real value - just turn on anyway?
#
#    Check Predbat to see if we are charging - does it matter though? At best we issue a warning?
#
#    Check power comes on by looking at Entity - but tank may be hot and immersion correctly off?
#

from   dataclasses import dataclass, asdict
from   datetime import datetime, timezone, timedelta
from   enum import Enum
import json
import os
import time
import urllib.request
from   zoneinfo import ZoneInfo

###########################
# Constants

UK_TZ = ZoneInfo("Europe/London")

# Set to True for running as a local script in development - it sets up tokens for HA access from Mac.
DEBUG = False

if DEBUG:

   # Use the Application Development Long-lived token and IP address...
   TOKEN            = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJkYzY3NWZjYzNjODc0MDVjOGNjMzZkN2M2YjQwNDE0NyIsImlhdCI6MTc4ODQ2NzcxOCwiZXhwIjoyMTAzODI3NzE4fQ.xZVDONLFKaoGfU48kAofWWM18zk3AJKS90-bLpPzCgE"
   URL_ROOT         = "http://192.168.1.208:8123/api/states/"
   URL_BUTTON_PRESS = "http://192.168.1.208:8123/api/services/button/press"  
   URL_NUMBER_PRESS = "http://192.168.1.208:8123/api/services/number/set_value" 
   VERSION          = "Local"

else:

   # Assuming in a HA started app container - use provided enviroment.
   TOKEN            = os.environ.get("SUPERVISOR_TOKEN")
   URL_ROOT         = "http://supervisor/core/api/states/"
   URL_BUTTON_PRESS = "http://supervisor/core/api/services/button/press"   
   URL_NUMBER_PRESS = "http://supervisor/core/api/services/number/set_value" 
   VERSION          = os.environ.get("ADDON_VERSION")

###########################
# Store the entities we use (5 of them) and the payloads to read, write, or perform an action.
# Putting all this up here cleans up the code a lot.

# 2 Octopus entities we read to get rates.
TODAY_RATES_ENTITY_URL       = URL_ROOT + "event.octopus_energy_electricity_22l4130572_2000051531893_current_day_rates"
TOMORROWDAY_RATES_ENTITY_URL = URL_ROOT + "event.octopus_energy_electricity_22l4130572_2000051531893_next_day_rates"

TODAY_REQUEST    = urllib.request.Request(TODAY_RATES_ENTITY_URL,       headers={"Authorization": f"Bearer {TOKEN}"})
TOMORROW_REQUEST = urllib.request.Request(TOMORROWDAY_RATES_ENTITY_URL, headers={"Authorization": f"Bearer {TOKEN}"})

# The entity we write to store data for HA to display. (Data is dummy - we set each time we store.)
BOOST_SLOTS_ENTITY_URL = URL_ROOT + "sensor.todays_boost_slots"

BOOST_SLOTS_REQUEST = urllib.request.Request(BOOST_SLOTS_ENTITY_URL,
                                             data=json.dumps({"dummy": "dummy"}).encode("utf-8"),
                                             headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                                             method="POST")

# The length of a boost slot - we read and maybe update if it's not 30 mins. (Write is always 30.)
BOOST_LENGTH_ENTITY_URL = URL_ROOT + "number.iboost_iboost_manual_boost_time"

BOOST_LENGTH_READ_REQUEST =  urllib.request.Request(BOOST_LENGTH_ENTITY_URL, headers={"Authorization": f"Bearer {TOKEN}"})

BOOST_LENGTH_WRITE_REQUEST = urllib.request.Request(URL_NUMBER_PRESS,
                                                    data = json.dumps({"entity_id": "number.iboost_iboost_manual_boost_time", "value": 30}).encode("utf-8"),
                                                    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                                                    method="POST")

# Finally the entity which presses the "boost now" button.
BUTTON_REQUEST = urllib.request.Request(URL_BUTTON_PRESS,
                                        data=json.dumps({"entity_id": "button.iboost_iboost_manual_boost_start"}).encode("utf-8"),
                                        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                                        method="POST")
                                        
###########################
# Types

class Day(Enum):
    TODAY    = TODAY_REQUEST
    TOMORROW = TOMORROW_REQUEST

@dataclass
class Slot_Rate:
    Start: datetime
    Rate : float   

###########################
# Utility Routines

###########################
# Sleep until next 30 min slot start. Used to create a basic scheduler from the main loop.
def Sleep_Until_Next_Half_Hour():
    now = datetime.now()
    if now.minute < 30:
        next_boundary = now.replace(minute=30, second=0, microsecond=0)
    else:
        next_boundary = (now.replace(minute=0, second=0, microsecond=0)
                          + timedelta(hours=1))
    sleep_seconds = (next_boundary - now).total_seconds()
    time.sleep(sleep_seconds)

###########################
# Get Today or Tomorrows rates as a slot -> rate mapping.
def Get_Rates(When: Day):

    with urllib.request.urlopen(When.value, timeout=10) as Response:
        data = json.loads(Response.read())

    return data["attributes"]["rates"]

###########################
# Write sensor data back to HA.
def Set_Boost_Slots():

   # Apply asdict to all elements of a list.
   def asdict_list(items):
      return [asdict(item) for item in items]

   Data = json.dumps({
     "state": asdict_list(Remaining_Boost_Slots),
     "attributes": {
         "Session"          : Session,
         "Cheapest Slots"   : asdict_list(Cheapest_Slots),
         "Boost Slots"      : asdict_list(Boost_Slots),
         "Free Unused Slots": asdict_list(Free_Unused_Slots)  } }).encode("utf-8")

   # Replace dummy data with the current data.
   BOOST_SLOTS_REQUEST.data = Data

   with urllib.request.urlopen(BOOST_SLOTS_REQUEST, timeout=10) as Response:
      return json.loads(Response.read())

###########################
# Press boost button in HA.
def Press_Boost_Button():

   # First, check the Boost length is 30 as needed by reading it ...
   with urllib.request.urlopen(BOOST_LENGTH_READ_REQUEST, timeout=10) as Response:
        data = json.loads(Response.read())

   Boost_Length = float(data["state"])

   # Do we need to change?
   if Boost_Length != 30.0:
      print(f"Boost length {Boost_Length} mins - set to 30 mins.")
      with urllib.request.urlopen(BOOST_LENGTH_WRITE_REQUEST, timeout=10) as Response:
        Response.read()
   
   else:
      print("Boost length already 30 mins - nothing to do.")

   # Now we press the boost button, as length is confirmed 30 mins.
   print("Boost button pressed!")  

   with urllib.request.urlopen(BUTTON_REQUEST, timeout=10) as Response:
      return json.loads(Response.read())

###########################
# State

# The time period we are looking at.
Session = ""

# The 4 cheapest slots in the session, ordered by rate.
Cheapest_Slots = []

# The 4 (max) slots we have found to boost the immersion, ordered by rate.
Boost_Slots = []

# Initially Boost_Slots, but with past slots removed, and ordered by time.
Remaining_Boost_Slots = []

# Any slots <0 that are not boost slots, ordered by rate.
Free_Unused_Slots = []

###########################
# Main Script
 
print(f"Starting Boost monitoring... Version {VERSION}", flush=True)
 
while True:
#if True: # Debug

    Now = datetime.now(UK_TZ)
    #Now = datetime.now(UK_TZ).replace(hour=6, minute=0, second=0, microsecond=0) # Debug - fudge time :-)

    print(f"[heartbeat] {Now}")
    
    # Work out if we need a slot re-calculation this time....
    # 1) If Session blank, it indicates the app has just started so we need to calculate. 
    # 2) Periodic re-calculate every 6 o'clock. (We know hot water use is heaviest in morning and evening.)
    # 3) This is a corner case where we have done 4 boost slots, but there is more free time, so let's use it.
    Calculate = ( not Session or  
                  Now.strftime("%H:%M") in ["06:00", "18:00"] or    
                  (not Remaining_Boost_Slots and Free_Unused_Slots) )

    if Calculate:   
    
        #Log for user.
        print("Re-calculating slots ...")
        
	    # If 6am-6pm window, we only need todays rates. Assume this initially...
        Slots = Get_Rates(Day.TODAY)
        Session = "6am - 6pm"
        
        # If 6pm-6am window, add tomorrows rates.
        # ("Now.hour = 18" is not enough, as we could be calculating for reasons [1] or [3] above.)
        if 18 <= Now.hour or Now.hour <= 5 :
           Slots += Get_Rates(Day.TOMORROW)
           Session = "6pm - 6am"

		# Process rates into a more useable format.
        Slots = [Slot_Rate(datetime.fromisoformat(x['start']), x['value_inc_vat']) for x in Slots ]

        # Possible bug - consider fixing hour to 6 or 18, so that reasons [1] and [3] produce
        # 6 o'clock window-aligned results. Currently they do 12 hours from Now.
        # Fix: if 07 <= Now.hour <= 17            then Now.hour = 6
        #      if 19 <= Now.hour or Now.hour <= 5 then Now.hour = 18

        # Filter out slots in the past.
        Slots = [x for x in Slots if x.Start >= Now]
		
		# Just keep next 12 hours into the future, and simplify start time.
        Slots = [Slot_Rate(x.Start.strftime("%H:%M"), x.Rate) for x in Slots[:24]]

		# Find best 2 hours - can be 4 separate slots.
        Slots.sort(key=lambda e: e.Rate)

        # These are the cheapest slots, so Store this for the user to know.
        Cheapest_Slots = Slots[:4] 

		# Only interested in free electricity! 
        Slots = [x for x in Slots if x.Rate <= 0.0]

        # These are the Boost Slots.
        Boost_Slots = Slots[:4] 
                
        # Reset Remaining to the new Boost list, but time ordered, so we can start working through them.
        Remaining_Boost_Slots = sorted(Slots[:4], key=lambda e: e.Start)
    
        # Any unused free electricity?
        Free_Unused_Slots = Slots[4:] 
    
        # Useful Debug.
        #print(f"Session: {Session}\n")
        #print(f"Cheapest: {Cheapest_Slots}\n")
        #print(f"Boost Slots: {Boost_Slots}\n")
        #print(f"Remaining Boost Slots: {Remaining_Boost_Slots}\n")
        #print(f"Free Unused Slots: {Free_Unused_Slots}")
  
        # Update the Sensor to store slots.
        Set_Boost_Slots()
       
    # Irrelevant of calculation or not - Every 30 mins we look to see if we need to turn on. 
    if Remaining_Boost_Slots and Remaining_Boost_Slots[0].Start == Now.strftime("%H:%M"):
    
       # Front of Remaining_Boost_Slots is now - act!   
       Press_Boost_Button()
       del Remaining_Boost_Slots[0]
       Set_Boost_Slots()
       print("Boost button pressed.", flush=True)

    else:
       print("No Boost scheduled.", flush=True)
       
    # Wait until next slot...
    Sleep_Until_Next_Half_Hour()

       

