# Wright-Way dog watch
Checks https://adopt.wright-wayrescue.org/?speciesID=1&stageID=2 every 30 minutes and pushes new dogs to ntfy (topic in the `NTFY_TOPIC` secret).
The checks are triggered by a cron-job.org job that calls the workflow's `workflow_dispatch` endpoint.
A daily "still watching" check-in is sent at 9 AM Central (GitHub's own schedule).
New dogs are logged in `new_dogs.log`.
