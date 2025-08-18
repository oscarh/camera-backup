# Back up video streams from my Unifi Cameras to Cloudflare R2 storage

I want to put video streams into 1h long segments on the local storage.
I want to finished segments to be moved to my Cloudflare R2 storage.
I can imagine that we create one systemd service / camera / rtsps stream, but I'm also open to just have a configuration file

The backup / move to CloudFlare R2 can be a separate service. It should remove the segment when its done.
