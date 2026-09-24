###########################
# Car Charger
#
# Work out the best time to charge the car.
#
#
# To Do:
#    Think about turning on automatically if car is connected to charger. Better here, or as Automation?
#

from   dataclasses import dataclass, asdict
from   datetime import datetime, timezone, timedelta
from   enum import Enum, IntEnum
import json
from   pathlib import Path
import time
from   zoneinfo import ZoneInfo

import HomeAssistant as HA


###########################
# Constants

UK_TZ = ZoneInfo("Europe/London")

###########################
# Store the entities we use with easy, sensible names.

# 2 Octopus entities we read to get rates.
Today_Rates_Entity    = "event.octopus_energy_electricity_22l4130572_2000051531893_current_day_rates"
Tomorrow_Rates_Entity = "event.octopus_energy_electricity_22l4130572_2000051531893_next_day_rates"

# BMW Battery level entity.
Battery_Entity = "sensor.330e_range_ev_remaining_range"

# The entity we write to store data for HA to display. 
Charge_Options_Entity = "sensor.bmw_charge_options"

###########################
# Types

class Day(Enum):
    Today    = Today_Rates_Entity
    Tomorrow = Tomorrow_Rates_Entity

@dataclass
class Slot_Rate:
    Start: datetime
    Rate : float   

class StatusT(IntEnum):
    OK            = 1
    Too_Short     = 2
    Too_Expensive = 3

@dataclass
class Charge_Option:
# The idea here is that you set the Request fields initially, and the algorithm fills in the
# Response fields. This lets us do several calculations at once.

    # These are the Request fields...
    Name       : str
    Length     : int 
    End_By_8am : bool = False
    Max_Rate   : float = 0.2 # £, so 0.2 is 20p.
    
    # These are the Response fields.
    Start  : str     = ""
    End    : str     = ""
    Rate   : float   = None
    Price  : float   = None
    Status : StatusT = None
    
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

    Data = HA.Read(When.value)
    return Data["attributes"]["rates"]

###########################
# Get current battery charge level. Return the proportion of
# charge needed to top up as value between 0 and 1.
def Get_Charge_Needed():

    Data = HA.Read(Battery_Entity)
    Current_Range = float(Data["state"])    

    # 25 miles is 100% fully charged.
    # Calculate proportion (range 0 - 1) of a full charge needed.
    Used_Range = 25 - Current_Range    
    Factor = Used_Range / 25

    return Factor
  
###########################
# Write sensor data back to HA.
def Set_Charge_Options():

   # Data is a dictionary with special keys.
   Data = {
     "state": Now.strftime("%H:%M"),
     "attributes": {
         "Fully Charge"          : asdict(Fully),
         "Fully Charge by 8am"   : asdict(Fully_by_8),
         "Top Up Charge"         : asdict(Top_Up),
         "Top Up Charge by 8am"  : asdict(Top_Up_by_8)  } 
     }

   Result = HA.Write(Charge_Options_Entity, Data)
   
   return Result

###########################
# Update a single request with the next slot option. If it's the best we have seen, update Response.
def Update_Option(Request, Slots):

   if Request.Length == 0:
      return

   Slot_Length = min(Request.Length, len(Slots))
   
   if Slot_Length < Request.Length and Request.Rate != None:
      # We already have a full length slot saved, and will never over-write 
      # with a shorter slot, so just stop now.
      return
      
   if Request.End_By_8am:
      if End_Target < Slots[Slot_Length - 1].Start:
         # Abort as end of slot is too late.
         # print(f"{Request.Name}: {End_Target.strftime('%H:%M')} < {Slots[Slot_Length - 1].Start.strftime('%H:%M')} - abort") # Debug
         return
         
   Next_Rate = sum([x.Rate for x in Slots[:Slot_Length]]) / Slot_Length

   if Request.Rate == None or Next_Rate < Request.Rate:
   
      # Found a cheaper rate.
      Request.Start = Slots[0].Start.strftime("%H:%M")
      Request.End   = (Slots[0].Start + timedelta(hours = Slot_Length //2)).strftime("%H:%M")
      Request.Rate  = Next_Rate
      Request.Price = Slot_Length * Next_Rate * 1.25 # 30 mins slots, at 2.5 KWH is 1.25 KW, at the average rate.
      
      if Slot_Length < Request.Length:
         Request.Status = StatusT.Too_Short
      elif Request.Rate > Request.Max_Rate:
         Request.Status = StatusT.Too_Expensive
      else:
         Request.Status = StatusT.OK


###########################
# State
            
###########################
# Main Script
 
print(f"Starting Charge Option Calculation ... Version {HA.VERSION}", flush=True)

config = Path("/config")

if config.is_dir():
    (config / "log.txt").touch() 
else:
   print("Failed to find config directory!")    

while True:
# if True:

   Now = datetime.now(UK_TZ)
   
   # Calculate charge time needed (in hours) by looking at battery level
   Fully_Charge_Time   = 5.5
   Top_Up_Charge_Time  = Fully_Charge_Time * Get_Charge_Needed()

   # Convert hours to 30-min electricity slots.
   Fully_Charge_Slots   = round(Fully_Charge_Time * 2)
   Top_Up_Charge_Slots  = round(Top_Up_Charge_Time * 2) 

   # Set up our 4 requests....
   Fully      = Charge_Option(Name = "F-", Length = Fully_Charge_Slots)
   Fully_by_8 = Charge_Option(Name = "F8", Length = Fully_Charge_Slots, End_By_8am = True)
   
   Top_Up      = Charge_Option(Name = "T-", Length = Top_Up_Charge_Slots)
   Top_Up_by_8 = Charge_Option(Name = "T8", Length = Top_Up_Charge_Slots, End_By_8am = True)

   # Store all requests to loop over later...
   Requests = [Fully, Fully_by_8, Top_Up, Top_Up_by_8]
   
   # Sort what "End by 8am" means ... today or tomorrow?
   Today_8am = Now.replace(hour=8, minute=0, second=0, microsecond=0)
   if Now < Today_8am:
      End_Target = Today_8am
   else:
      End_Target = Today_8am + timedelta(days = 1)
       
   # Get the electricity rates. 
   Slots = Get_Rates(Day.Today) + Get_Rates(Day.Tomorrow)

   # Process rates into a more useable format.
   Slots = [Slot_Rate(datetime.fromisoformat(x['start']), x['value_inc_vat']) for x in Slots ]

   # Filter out slots in the past.
   Slots = [x for x in Slots if x.Start >= Now]
   
   # Look for all candidate subsequences.   
   while len(Slots) > 0:
   
      # print(f"Time {Slots[0].Start} & Len Slots: {len(Slots)}") # Debug

      for Request in Requests:
         Update_Option(Request, Slots)	
 
      del Slots[0]
 
   # Store for HA to use.
   Set_Charge_Options()
   
   print(f"Recalculated slots at {Now.strftime('%H:%M')}", flush=True)  
   # for Request in Requests:
   #    print(f"{Request.Name} => {Request}")
 
   # Wait until next slot...
   Sleep_Until_Next_Half_Hour()
   
   
   
   
   
   
   
   
   
   
   
