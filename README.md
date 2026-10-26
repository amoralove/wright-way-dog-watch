# Wright-Way dog watch
Checks rescue shelters' adoptable dogs every 30 minutes and pushes new dogs to ntfy (topic in the `NTFY_TOPIC` secret).
The checks are triggered by a cron-job.org job that calls the workflow's `workflow_dispatch` endpoint.
A daily "still watching" check-in is sent at 9 AM Central (GitHub's own schedule).
New dogs are logged in `new_dogs.log`.

## Fees
Where a shelter's fee schedule can be read, new-dog alerts include the fee, and a separate alert is sent when the schedule changes (e.g. a fee special). The last known schedule is kept under `fees` in `seen.json`.
- Wright-Way: site-wide rates from https://wright-wayrescue.org/adoption-program-and-process (adult dog vs. puppy 9 months and younger) and the senior-adopter rate from https://wright-wayrescue.org/seniors.
- Border Tails: per-dog fee from each new dog's ShelterLuv entry (no schedule-change alert, since there is no site-wide schedule).

## Shelters
- Wright-Way: https://adopt.wright-wayrescue.org/?speciesID=1&stageID=2
- Border Tails: https://www.bordertailsrescue.org/adoptable-dogs-copy (ShelterLuv)
- One Tail: https://www.onetail.org/available-pets/ (breed is read from each new dog's detail page)

To add a ShelterLuv shelter, find `var GID = ...` in its adoptable-pets page source and add an entry to `SHELTERS` in `watch.py` with `"fetch": fetch_shelterluv`. A newly added shelter records its current dogs on the first run without sending alerts.
