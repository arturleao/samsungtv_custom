## Samsung TV H Series custom component for Home Assistant

Based on a simplified version of [ha-samsungtv-custom](https://github.com/roberodin/ha-samsungtv-custom) by [@roberodin](https://github.com/roberodin) using a modified version of [PySmartCrypto](https://github.com/eclair4151/SmartCrypto) by [@eclair4151](https://github.com/eclair4151)

### Usage
Replace the host ip with your Samsung TV ip address and add in configuration.yaml:
```
media_player:
  - platform: samsungtv_custom
    host: 10.0.0.1
    token: !secret samsung_token
    sessionid: !secret samsung_id
    port: "8080"
```
