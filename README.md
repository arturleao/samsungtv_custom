## Samsung TV H Series custom component for Home Assistant

Based on a simplified version of [ha-samsungtv-custom](https://github.com/roberodin/ha-samsungtv-custom) by 
[@roberodin](https://github.com/roberodin) using a modified version of 
[PySmartCrypto](https://github.com/eclair4151/SmartCrypto) by [@eclair4151](https://github.com/eclair4151)

### Usage
Create a folder called "samsungtv_custom" in your config directory and extract files to the folder.

Use get_token.py to get your Samsung TV token (use --port 8080)
```
get_token.py --ip <ip> --port <port>
```
Store ctx (token) and session id output.

Replace the host ip with your Samsung TV ip address and add it to configuration.yaml:
```
media_player:
  - platform: samsungtv_custom
    host: 10.0.0.1
    token: !secret samsung_token
    sessionid: !secret samsung_id
    port: "8080"
```
Add these tokens to secrets.yaml and replace it with your Samsung TV token and session id

```
samsung_token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
samsung_id: x
```

After this you are all done, add the Media Player card to your Lovelace layout.

This should work on H and J 2014/2015 models (according to [PySmartCrypto](https://github.com/eclair4151/SmartCrypto) specs)

Feel free to contribute with other working models and to submit fixes and improvements to the code. Enjoy!

#### Working Models
- UE55H6400
- UE40H6200 (caveat: off-state detection, see Issue #1)
- UE48H5500AW (caveat: off-state detection, see Issue #1)
- 55HU7500 (caveat: off-state detection, see Issue #1)
- HU8550 (caveat: off-state detection, see Issue #1)
