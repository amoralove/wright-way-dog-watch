# Wright-Way dog watch
Checks https://adopt.wright-wayrescue.org/?speciesID=1&stageID=2 every 5 minutes and pushes new dogs to ntfy (topic in the `NTFY_TOPIC` secret).
A daily "still watching" check-in is sent at 9 AM Central.
New dogs are logged in `new_dogs.log`.
