# Available Slash Commands
/lit city:[city] - Reset basin timer (e.g. /lit city:Edron, /lit city:All)

/time city:[city] timer:[time] - Set basin timer. Time must be provided in HH:MM format. (e.g. /time city:Edron timer:1:43)


# Admin Commands
/alertTime [time] - set alert time. When any timer drops under that value, notification will be sent on the status channel. 
When timer drops under [time]/2, bot will send PM to all Lightkeepers

/statusChannel [channel_mention] - set status channel

/lightkeeperRole [role_mention] - set lightkeeper role

/prepareForEvent - prepare status message on the status channel

/restart - restart event if any timer hits 00:00:00

/soft_reset - remove timers only

/reset - remove all settings

/stop - stop event

/start - start event