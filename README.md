# Aegis
_Aegis_ is a simple discord moderation bot that flags potentially compromised accounts.

## Usage
Use this link to invite the bot to your discord server:
https://discord.com/oauth2/authorize?client_id=1483867446770139326&permissions=4504699139222528&integration_type=0&scope=bot

## Detection Algorithm
_Aegis_ detects compromised accounts if a user sends the same message in multiple channels within a set time frame. _Aegis_ can also determine if the user sends the same image.

## Auto-Action
If _Aegis_ flags an account, it will delete all potentially malicious messages. By default, _Aegis_ does not timeout or kick the user, but can do either using `/setactiontype [Action]`

## Commands
_Aegis_ comes with commands that allows customization for which channel to send logs, time out duration, detection time window, and  the channel messages-sent threshold.

```
/setdetectiontime [Time in seconds]
```
Sets the amount of time that messages must be sent inbetween in order to be flagged. Defaults to 1 second.

```
/setchannelthreshold [Number of channels]
```
Sets the number of channels a flagged account must send a message within the detection time to get flagged. Defaults to 7 days.

```
/setactiontype [Action]
```
Sets the auto-action for _Aegis_ to perform if it detects a compromised account. 

```
/settimeoutduration [Time in days]
```
Sets the amount of time a flagged account is timed out for, if the current action is set to timeout. Defaults to 7 days.


```
/setloggingchannel [Channel ID]
```
Sets the channel in which _Aegis_ will send logs.




