---
name: rpi-deploy
description: Deploys project on Raspberry Pi. Use when finishing a feature or bugix, need to update already deployed code, or when explicitly asked to deploy.
---

When deploying:

1. Use hostname "disphat" for connections - it is already in .ssh/config. If host is unreachable, don't proceed - ask user to restart Raspberry Pi and wait for user's confirmation.
2. If there were changes to configuration file (config.example.yaml), adapt those changes to local config.yaml, and then to remote config.yaml. 
Do not simply overwrite remote config.yaml on raspberry pi - user might have it changed already. Carefully adapt new 
setting into existing config file. 
3. Sync back remote config.yaml to project directory to keep it in the repo.
4. Restart the service after deployment with `sudo systemctl restart deskinfopoint`
