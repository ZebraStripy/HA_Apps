################################################
# Home Assistant
#
# Module of routines to simplify writing Home Assistant Apps, with automatic detection of Local Development.
#

import json
import os
import urllib.request


# Run once to set a bunch of Global state constants.

# Do we have a token from Home Assistant?
TOKEN = os.environ.get("SUPERVISOR_TOKEN")

if TOKEN:

   # Assuming in a HA started app container - use provided enviroment.
   URL_ROOT         = "http://supervisor/core/api/"
   VERSION          = os.environ.get("ADDON_VERSION")
   LOG_FILE_PATH    = "/config/Log.txt"

else:

   # Use the Application Development setup.
   # Set TOKEN to a Long-lived development token and use IP address...
   print("Note: Running in Local mode.")
   TOKEN            = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJkYzY3NWZjYzNjODc0MDVjOGNjMzZkN2M2YjQwNDE0NyIsImlhdCI6MTc4ODQ2NzcxOCwiZXhwIjoyMTAzODI3NzE4fQ.xZVDONLFKaoGfU48kAofWWM18zk3AJKS90-bLpPzCgE"
   URL_ROOT         = "http://192.168.1.208:8123/api/"
   VERSION          = "Local"
   LOG_FILE_PATH    = "Log.txt"

# Various things we "do" with an Entity.
URL_STATE        = URL_ROOT + "states/"  
URL_BUTTON_PRESS = URL_ROOT + "services/button/press/"  
URL_NUMBER_PRESS = URL_ROOT + "services/number/set_value/" 

# Read an entity...
def Read(Entity : str):

   Entity_URL     = URL_STATE + Entity
   Entity_Request = urllib.request.Request(Entity_URL, headers={"Authorization": f"Bearer {TOKEN}"})

   try:
      with urllib.request.urlopen(Entity_Request, timeout=10) as Response:
         Result = json.loads(Response.read())

   except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
      # Put in App log for user to see if interested...
      print(f"Failed to fetch {Entity_URL}: {e}")
      Result = None
         
   return Result   


# Write an entity...
def Write(Entity : str, Data):

   Entity_URL     = URL_STATE + Entity

   # Convert Data to json
   JSON_Data = json.dumps(Data).encode("utf-8")

   Entity_Request = urllib.request.Request(Entity_URL, data = JSON_Data, headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}, method="POST")

   try:
      with urllib.request.urlopen(Entity_Request, timeout=10) as Response:
         Result = json.loads(Response.read())

   except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
      # Put in App log for user to see if interested...
      print(f"Failed to fetch {Entity_URL}: {e}")
      Result = None
         
   return Result   

# To Do - Add routines for pushing a button or setting a helper input number.
