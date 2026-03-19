# Aegis
_Aegis_ is a simple discord moderation bot that flags potentially compromised accounts.

## Detection Algorithm
_Aegis_ detects compromised accounts if a user sends the same message in multiple channels within a set time frame. _Aegis_ can also determine if the user sends the same image.

## Auto-Action
If _Aegis_ flags an account, it will delete all potentially malicious messages and time out the user for a set amount of time.

## Commands
_Aegis_ comes with commands that allows customization for which channel to send logs, time out duration, and the detection time window.

```
/setloggingchannel [Channel ID]
```

```
/setdetectiontime [Time in seconds, defaults to 1]
```

```
/settimeoutduration [Time in days, defaults to 7]
```